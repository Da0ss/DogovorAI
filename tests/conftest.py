"""
Конфигурация pytest — фикстуры и настройки для всех тестов.
"""

# Первой строкой: приложение использует Supabase-ветку auth, а не локальный SMTP-режим
import os

os.environ["PYTEST_RUNNING"] = "1"
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key-for-testing")
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# Регистрация компилятора JSONB для совместимости со SQLite
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

# Мокаем создание Supabase клиента глобально
mock_client = MagicMock()
mock_auth = MagicMock()
mock_client.auth = mock_auth

_registered_emails: set = set()


def mock_sign_up(options):
    email = options.get("email", "test@example.com")
    _registered_emails.add(email)
    return {"user": {"id": f"supabase-{abs(hash(email))}", "email": email}}


def mock_verify_otp(options):
    email = options.get("email", "test@example.com")
    if email not in _registered_emails:
        raise Exception("Invalid verification code")
    return {
        "user": {
            "id": f"supabase-{abs(hash(email))}",
            "email": email,
            "email_confirmed_at": "2026-01-01T00:00:00Z",
        }
    }


def mock_resend(options):
    return {"message": "Code sent successfully"}


def mock_sign_in_with_password(options):
    email = options.get("email", "test@example.com")
    if email not in _registered_emails:
        raise Exception("Invalid login credentials")
    return {
        "user": {
            "id": f"supabase-{abs(hash(email))}",
            "email": email,
            "email_confirmed_at": "2026-01-01T00:00:00Z",
        },
        "session": {
            "access_token": f"test-token-{email}",
            "refresh_token": f"test-refresh-{email}",
            "token_type": "bearer",
        },
    }


def mock_get_user(token):
    email = token.replace("test-token-", "", 1) if token.startswith("test-token-") else "admin@example.com"
    return SimpleNamespace(
        user=SimpleNamespace(
            id=f"supabase-{abs(hash(email))}",
            email=email,
            email_confirmed_at="2026-01-01T00:00:00Z",
            user_metadata={},
        )
    )

mock_auth.sign_up = mock_sign_up
mock_auth.verify_otp = mock_verify_otp
mock_auth.resend = mock_resend
mock_auth.sign_in_with_password = mock_sign_in_with_password
mock_auth.get_user = mock_get_user

# Применяем патч
patch("supabase.create_client", return_value=mock_client).start()


@pytest.fixture
def client():
    """
    Provide TestClient for integration tests.
    Supabase connection is mocked.
    """
    # Мокаем создание Supabase клиента
    mock_client = MagicMock()
    mock_auth = MagicMock()
    mock_client.auth = mock_auth

    # Создаем синхронные моки для методов
    def mock_sign_up(options):
        email = options.get("email", "test@example.com")
        _registered_emails.add(email)
        return {"user": {"id": f"supabase-{abs(hash(email))}", "email": email}}

    def mock_verify_otp(options):
        email = options.get("email", "test@example.com")
        if email not in _registered_emails:
            raise Exception("Invalid verification code")
        return {
            "user": {
                "id": f"supabase-{abs(hash(email))}",
                "email": email,
                "email_confirmed_at": "2026-01-01T00:00:00Z",
            }
        }

    def mock_resend(options):
        return {"message": "Code sent successfully"}

    def mock_sign_in_with_password(options):
        email = options.get("email", "test@example.com")
        if email not in _registered_emails:
            raise Exception("Invalid login credentials")
        return {
            "user": {
                "id": f"supabase-{abs(hash(email))}",
                "email": email,
                "email_confirmed_at": "2026-01-01T00:00:00Z",
            },
            "session": {
                "access_token": f"test-token-{email}",
                "refresh_token": f"test-refresh-{email}",
                "token_type": "bearer",
            },
        }

    def mock_get_user(token):
        email = token.replace("test-token-", "", 1) if token.startswith("test-token-") else "admin@example.com"
        return SimpleNamespace(
            user=SimpleNamespace(
                id=f"supabase-{abs(hash(email))}",
                email=email,
                email_confirmed_at="2026-01-01T00:00:00Z",
                user_metadata={},
            )
        )

    # Настраиваем моки для auth методов
    mock_auth.sign_up = mock_sign_up
    mock_auth.verify_otp = mock_verify_otp
    mock_auth.resend = mock_resend
    mock_auth.sign_in_with_password = mock_sign_in_with_password
    mock_auth.get_user = mock_get_user

    with patch("supabase.create_client", return_value=mock_client):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)


@pytest.fixture
def mock_supabase():
    """Мок Supabase клиента для unit-тестов."""
    mock = MagicMock()
    mock.auth = MagicMock()
    return mock


def pytest_sessionstart(session):
    """
    Создание тестовой базы данных SQLite перед запуском тестов.
    """
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except Exception:
            pass

    from app.models.database import engine
    from app.models.models import Base
    Base.metadata.create_all(bind=engine)


def pytest_sessionfinish(session, exitstatus):
    """
    Удаление тестовой базы данных SQLite после завершения тестов.
    """
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except Exception:
            pass
