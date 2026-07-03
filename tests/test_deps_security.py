import pytest
import os
from fastapi import Request, HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.api.deps import get_current_user, check_admin_role, RequireRoles, verify_owner
from app.models.models import Base, User
from config.settings import settings


class MockClient:
    def __init__(self, host: str):
        self.host = host


class MockRequest:
    def __init__(self, path: str, method: str = "GET", headers: dict = None, path_params: dict = None, query_params: dict = None, host: str = "127.0.0.1"):
        self.url = type("URL", (object,), {"path": path})()
        self.method = method
        self.headers = headers or {}
        self.path_params = path_params or {}
        self.query_params = query_params or {}
        self.client = MockClient(host)


@pytest.fixture(scope="function")
def db_session():
    """Create a temporary SQLite database for testing."""
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
def test_user(db_session: Session) -> User:
    """Create a test user in database."""
    user = User(
        id="test-user-id-123",
        email="regular@example.com",
        is_verified=True,
        plan_type="basic",
        subscription_status="active"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def banned_user(db_session: Session) -> User:
    """Create a banned user in database."""
    user = User(
        id="banned-user-id-456",
        email="banned@example.com",
        is_verified=True,
        plan_type="basic",
        subscription_status="banned"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_current_user_no_token():
    """Verify that requests without authorization token are rejected."""
    request = MockRequest("/api/some-endpoint")
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request)
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Токен отсутствует" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_current_user_valid_local_token(db_session: Session, test_user: User):
    """Verify that local development tokens are accepted in test mode."""
    request = MockRequest(
        "/api/some-endpoint",
        headers={"Authorization": f"Bearer local-token-{test_user.id}"}
    )
    user = await get_current_user(request, db_session)
    assert user.id == test_user.id
    assert user.email == test_user.email


@pytest.mark.asyncio
async def test_get_current_user_banned(db_session: Session, banned_user: User):
    """Verify that banned users are blocked."""
    request = MockRequest(
        "/api/some-endpoint",
        headers={"Authorization": f"Bearer local-token-{banned_user.id}"}
    )
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(request, db_session)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "заблокирован" in exc_info.value.detail


@pytest.mark.asyncio
async def test_check_admin_role_success(test_user: User, monkeypatch):
    """Verify check_admin_role accepts users in settings.admin_emails."""
    # Configure admin emails settings
    monkeypatch.setattr(settings, "admin_emails", "regular@example.com,other@admin.com")
    
    request = MockRequest("/api/admin-route")
    admin = await check_admin_role(request, test_user)
    assert admin.id == test_user.id


@pytest.mark.asyncio
async def test_check_admin_role_forbidden(test_user: User, monkeypatch):
    """Verify check_admin_role rejects users not in settings.admin_emails."""
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    
    request = MockRequest("/api/admin-route")
    with pytest.raises(HTTPException) as exc_info:
        await check_admin_role(request, test_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Доступ запрещен" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_roles_success(test_user: User):
    """Verify RequireRoles allows users with correct plan type."""
    rbac = RequireRoles("pro", "basic")
    request = MockRequest("/api/premium-route")
    allowed_user = await rbac(request, test_user)
    assert allowed_user.id == test_user.id


@pytest.mark.asyncio
async def test_require_roles_denied(test_user: User):
    """Verify RequireRoles blocks users without matching plan type."""
    rbac = RequireRoles("pro", "max")
    request = MockRequest("/api/premium-route")
    with pytest.raises(HTTPException) as exc_info:
        await rbac(request, test_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Недостаточно прав" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_owner_match(test_user: User):
    """Verify Anti-IDOR allows access when owner ID matches path parameter."""
    request = MockRequest("/api/users/test-user-id-123", path_params={"user_id": "test-user-id-123"})
    dependency = verify_owner("user_id")
    # Should execute successfully without throwing an exception
    await dependency(request, test_user)


@pytest.mark.asyncio
async def test_verify_owner_mismatch(test_user: User):
    """Verify Anti-IDOR blocks access when owner ID is mismatched (preventing IDOR)."""
    request = MockRequest("/api/users/another-user-id", path_params={"user_id": "another-user-id"})
    dependency = verify_owner("user_id")
    with pytest.raises(HTTPException) as exc_info:
        await dependency(request, test_user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Несовпадение идентификатора владельца" in exc_info.value.detail
