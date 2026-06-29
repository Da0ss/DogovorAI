"""
CRUD operations for profiles and verification_codes.
Таблица profiles (бывшая users) использует UUID строки в качестве PK.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
import secrets

from app.models.models import User, VerificationCode
from app.models.schemas import UserCreate, VerificationRequest
from app.services.auth_context import is_debug_or_test

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return "".join(secrets.choice("0123456789") for _ in range(6))


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email from profiles table."""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: str) -> Optional[User]:
    """Get user by UUID string id from profiles table."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user: UserCreate) -> User:
    """
    Create a new user in profiles table.
    id генерируется автоматически как UUID.
    """
    db_user = get_user_by_email(db, user.email)
    if db_user:
        raise ValueError("Пользователь с таким email уже существует")

    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        is_verified=False,
        auth_provider="local",
    )
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"✅ Пользователь создан: {user.email} (id={db_user.id})")
        return db_user
    except IntegrityError:
        db.rollback()
        raise ValueError("Пользователь с таким email уже существует")


def create_verification_code(db: Session, user_id: str,
                              purpose: str = "email_verify") -> VerificationCode:
    """
    Create a verification code for user.
    user_id — UUID строка.
    """
    code = generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    verification_code = VerificationCode(
        user_id=user_id,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
    )
    db.add(verification_code)
    db.commit()
    db.refresh(verification_code)

    if is_debug_or_test():
        logger.info(f"📧 Код верификации для user_id={user_id}: {code}")
    return verification_code


def verify_user_code(db: Session, verification: VerificationRequest) -> Optional[User]:
    """Verify user email with code."""
    user = get_user_by_email(db, verification.email)
    if not user:
        return None

    verification_code = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.user_id == user.id,
            VerificationCode.code == str(verification.code),
            VerificationCode.is_used == False,
            VerificationCode.expires_at > datetime.now(timezone.utc),
        )
        .order_by(VerificationCode.expires_at.desc())
        .first()
    )

    if not verification_code:
        return None

    # Mark code as used
    verification_code.is_used = True
    user.is_verified = True
    db.commit()
    db.refresh(user)

    logger.info(f"✅ Пользователь верифицирован: {user.email}")
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate user with email and password."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not user.hashed_password:
        # OAuth user — no local password
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
