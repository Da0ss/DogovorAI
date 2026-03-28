"""
Configuration for pytest
"""

import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """
    Provide TestClient for tests
    """
    return TestClient(app)


@pytest.fixture
def mock_supabase_client(mocker):
    """
    Provide mock Supabase client for testing
    """
    mock_client = mocker.MagicMock()
    return mock_client
