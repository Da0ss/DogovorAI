"""
Тесты для CRUD-операций с пользователями и кодами верификации.
Используют SQLite in-memory базу данных.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


# Совместимость SQLite с JSONB
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


from app.models.models import Base, User, VerificationCode
from app.models.crud import (
    get_user_by_email,
    get_user_by_id,
    create_user,
    create_verification_code,
    verify_user_code,
    authenticate_user,
    generate_verification_code,
    get_password_hash,
    verify_password,
)
from app.models.schemas import UserCreate, VerificationRequest


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="function")
def db_session():
    """Создаёт in-memory SQLite базу данных для каждого теста."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_user_create():
    return UserCreate(email="test@example.com", password="SecurePass123!")


@pytest.fixture
def created_user(db_session, sample_user_create):
    """Создаёт пользователя в БД для тестов."""
    return create_user(db_session, sample_user_create)


# ============================================================
# Тесты: Password Hashing
# ============================================================

class TestPasswordHashing:
    """Тесты хеширования и проверки паролей."""

    def test_hash_password_returns_string(self):
        hashed = get_password_hash("mypassword")
        assert isinstance(hashed, str)
        assert hashed != "mypassword"

    def test_verify_correct_password(self):
        password = "SecurePass123!"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Bcrypt генерирует разные хеши для одного пароля (из-за соли)."""
        h1 = get_password_hash("same_pass")
        h2 = get_password_hash("same_pass")
        assert h1 != h2
        # But both should verify
        assert verify_password("same_pass", h1) is True
        assert verify_password("same_pass", h2) is True


# ============================================================
# Тесты: generate_verification_code
# ============================================================

class TestGenerateVerificationCode:
    """Тесты генерации кодов верификации."""

    def test_code_is_6_digits(self):
        code = generate_verification_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_codes_are_unique(self):
        codes = {generate_verification_code() for _ in range(20)}
        # With 6 digits and 20 codes, very unlikely to have all equal
        assert len(codes) > 1


# ============================================================
# Тесты: create_user
# ============================================================

class TestCreateUser:
    """Тесты создания пользователя в БД."""

    def test_create_user_success(self, db_session, sample_user_create):
        user = create_user(db_session, sample_user_create)
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.hashed_password is not None
        assert user.hashed_password != "SecurePass123!"
        assert user.is_verified is False
        assert user.auth_provider == "local"

    def test_duplicate_email_raises(self, db_session, sample_user_create):
        create_user(db_session, sample_user_create)
        with pytest.raises(ValueError, match="email уже существует"):
            create_user(db_session, sample_user_create)

    def test_user_has_uuid_id(self, db_session, sample_user_create):
        import uuid
        user = create_user(db_session, sample_user_create)
        # Should be parseable as UUID
        uuid.UUID(user.id)


# ============================================================
# Тесты: get_user_by_email / get_user_by_id
# ============================================================

class TestGetUser:
    """Тесты поиска пользователя."""

    def test_get_user_by_email_found(self, db_session, created_user):
        user = get_user_by_email(db_session, "test@example.com")
        assert user is not None
        assert user.id == created_user.id

    def test_get_user_by_email_not_found(self, db_session):
        user = get_user_by_email(db_session, "nonexistent@example.com")
        assert user is None

    def test_get_user_by_id_found(self, db_session, created_user):
        user = get_user_by_id(db_session, created_user.id)
        assert user is not None
        assert user.email == created_user.email

    def test_get_user_by_id_not_found(self, db_session):
        user = get_user_by_id(db_session, "00000000-0000-0000-0000-000000000000")
        assert user is None


# ============================================================
# Тесты: create_verification_code
# ============================================================

class TestCreateVerificationCode:
    """Тесты создания кодов верификации."""

    def test_creates_code_for_user(self, db_session, created_user):
        code_obj = create_verification_code(db_session, created_user.id)
        assert code_obj.id is not None
        assert code_obj.user_id == created_user.id
        assert len(code_obj.code) == 6
        assert code_obj.is_used is False
        assert code_obj.purpose == "email_verify"

    def test_code_expires_in_10_minutes(self, db_session, created_user):
        code_obj = create_verification_code(db_session, created_user.id)
        now = datetime.now(timezone.utc)
        # expires_at should be ~10 minutes in the future
        delta = code_obj.expires_at.replace(tzinfo=timezone.utc) - now
        assert timedelta(minutes=8) < delta < timedelta(minutes=12)

    def test_otp_purpose(self, db_session, created_user):
        code_obj = create_verification_code(db_session, created_user.id, purpose="otp_login")
        assert code_obj.purpose == "otp_login"


# ============================================================
# Тесты: verify_user_code
# ============================================================

class TestVerifyUserCode:
    """Тесты верификации email кода."""

    def test_valid_code_verifies_user(self, db_session, created_user):
        code_obj = create_verification_code(db_session, created_user.id)
        verification = VerificationRequest(email=created_user.email, code=code_obj.code)
        user = verify_user_code(db_session, verification)
        assert user is not None
        assert user.is_verified is True

    def test_wrong_code_returns_none(self, db_session, created_user):
        create_verification_code(db_session, created_user.id)
        verification = VerificationRequest(email=created_user.email, code="000000")
        user = verify_user_code(db_session, verification)
        assert user is None

    def test_wrong_email_returns_none(self, db_session, created_user):
        code_obj = create_verification_code(db_session, created_user.id)
        verification = VerificationRequest(email="wrong@example.com", code=code_obj.code)
        user = verify_user_code(db_session, verification)
        assert user is None

    def test_code_cannot_be_used_twice(self, db_session, created_user):
        code_obj = create_verification_code(db_session, created_user.id)
        verification = VerificationRequest(email=created_user.email, code=code_obj.code)
        # First use
        user1 = verify_user_code(db_session, verification)
        assert user1 is not None
        # Second use — should fail (is_used=True)
        user2 = verify_user_code(db_session, verification)
        assert user2 is None


# ============================================================
# Тесты: authenticate_user
# ============================================================

class TestAuthenticateUser:
    """Тесты аутентификации по email/паролю."""

    def test_correct_credentials(self, db_session, created_user, sample_user_create):
        user = authenticate_user(db_session, sample_user_create.email, sample_user_create.password)
        assert user is not None
        assert user.email == sample_user_create.email

    def test_wrong_password(self, db_session, created_user, sample_user_create):
        user = authenticate_user(db_session, sample_user_create.email, "wrong_password")
        assert user is None

    def test_nonexistent_user(self, db_session):
        user = authenticate_user(db_session, "nobody@example.com", "password")
        assert user is None

    def test_oauth_user_without_password(self, db_session):
        """OAuth-пользователи без пароля не должны аутентифицироваться по паролю."""
        oauth_user = User(
            email="google@example.com",
            hashed_password=None,
            auth_provider="supabase",
            is_verified=True,
        )
        db_session.add(oauth_user)
        db_session.commit()

        user = authenticate_user(db_session, "google@example.com", "any_password")
        assert user is None
