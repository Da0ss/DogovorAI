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

# Мокаем создание Supabase клиента глобально
mock_client = MagicMock()
mock_auth = MagicMock()
mock_client.auth = mock_auth

_registered_emails: set = set()


def mock_sign_up(options):
    email = options.get("email", "test@example.com")
    _registered_emails.add(email)
    return {"user": {"id": "test-user-id", "email": email}}


def mock_verify_otp(options):
    email = options.get("email", "test@example.com")
    if email not in _registered_emails:
        raise Exception("Invalid verification code")
    return {"user": {"id": "test-user-id", "email": email}}


def mock_resend(options):
    return {"message": "Code sent successfully"}


def mock_sign_in_with_password(options):
    email = options.get("email", "test@example.com")
    if email not in _registered_emails:
        raise Exception("Invalid login credentials")
    return {"user": {"id": "test-user-id", "email": email}}

mock_auth.sign_up = mock_sign_up
mock_auth.verify_otp = mock_verify_otp
mock_auth.resend = mock_resend
mock_auth.sign_in_with_password = mock_sign_in_with_password

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
        return {"user": {"id": "test-user-id", "email": email}}

    def mock_verify_otp(options):
        email = options.get("email", "test@example.com")
        if email not in _registered_emails:
            raise Exception("Invalid verification code")
        return {"user": {"id": "test-user-id", "email": email}}

    def mock_resend(options):
        return {"message": "Code sent successfully"}

    def mock_sign_in_with_password(options):
        email = options.get("email", "test@example.com")
        if email not in _registered_emails:
            raise Exception("Invalid login credentials")
        return {"user": {"id": "test-user-id", "email": email}}

    # Настраиваем моки для auth методов
    mock_auth.sign_up = mock_sign_up
    mock_auth.verify_otp = mock_verify_otp
    mock_auth.resend = mock_resend
    mock_auth.sign_in_with_password = mock_sign_in_with_password

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
