"""
Конфигурация pytest — фикстуры и настройки для всех тестов.
"""

import pytest
from unittest.mock import MagicMock, patch


# Мокируем настройки ДО импорта приложения
import os
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key-for-testing")


@pytest.fixture
def client():
    """
    Provide TestClient for integration tests.
    Supabase connection is mocked.
    """
    with patch("config.database.get_supabase_client", return_value=MagicMock()):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)


@pytest.fixture
def mock_supabase():
    """Мок Supabase клиента для unit-тестов."""
    mock = MagicMock()
    return mock
