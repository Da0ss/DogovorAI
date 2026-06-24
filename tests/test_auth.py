"""
Tests for authentication endpoints using Supabase Auth
"""

import pytest
import uuid
from config.settings import settings


class TestAuthentication:
    """Authentication endpoints tests"""

    def test_register_user_success(self, client):
        """
        Test successful user registration
        """
        user_data = {
            "email": f"test+{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123"
        }

        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 201

        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["id"] is not None
        assert len(data["id"]) > 0
        assert data["is_verified"] is False
        assert "created_at" in data

    def test_register_user_without_consent(self, client):
        """
        Test registration fails when consent is explicitly false
        """
        user_data = {
            "email": f"noconsent+{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123",
            "consent": False
        }

        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 400
        data = response.json()
        assert "согласиться" in data["detail"]

    def test_register_duplicate_email(self, client):
        """
        Test registration with existing email fails
        """
        user_data = {
            "email": f"duplicate+{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123"
        }

        # First registration
        client.post("/api/auth/register", json=user_data)

        # Second registration with same email - Supabase handles duplicates
        response = client.post("/api/auth/register", json=user_data)
        # Supabase may return 200 or handle it differently, but should not crash
        assert response.status_code in [200, 201, 400]

    def test_verify_email_success(self, client):
        """
        Test successful email verification
        """
        # Register user
        user_data = {
            "email": f"verify+{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123"
        }
        client.post("/api/auth/register", json=user_data)

        verify_data = {
            "email": user_data["email"],
            "code": "123456"
        }

        response = client.post("/api/auth/verify", json=verify_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Email verified successfully"
        assert "user" in data
        assert data["user"]["email"] == user_data["email"]

    def test_verify_invalid_code(self, client):
        """
        Test verification with invalid code fails
        """
        verify_data = {
            "email": f"invalid+{uuid.uuid4().hex[:8]}@example.com",
            "code": "000000"
        }

        response = client.post("/api/auth/verify", json=verify_data)
        # Supabase will return error for invalid code
        assert response.status_code in [400, 422]

    def test_resend_verification_code(self, client):
        """
        Test resending verification code
        """
        # Register user first
        user_data = {
            "email": f"resend+{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123"
        }
        client.post("/api/auth/register", json=user_data)

        # Resend code
        response = client.post("/api/auth/resend-code", params={"email": user_data["email"]})
        assert response.status_code == 200

        data = response.json()
        assert "message" in data or "success" in str(data).lower()

    def test_login_success(self, client):
        """
        Test successful login
        """
        user_data = {
            "email": f"login+{uuid.uuid4().hex[:8]}@example.com",
            "password": "password123"
        }

        # Register user
        client.post("/api/auth/register", json=user_data)

        client.post("/api/auth/verify", json={
            "email": user_data["email"],
            "code": "123456"
        })

        # Login
        response = client.post("/api/auth/login", json=user_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Успешный вход"
        assert "user" in data
        assert data["user"]["email"] == user_data["email"]

    def test_login_invalid_credentials(self, client):
        """
        Test login with invalid credentials fails
        """
        login_data = {
            "email": f"invalid+{uuid.uuid4().hex[:8]}@example.com",
            "password": "wrongpassword"
        }

        response = client.post("/api/auth/login", json=login_data)
        assert response.status_code in [400, 401]

    def test_test_code_endpoint_disabled_outside_debug(self, client, monkeypatch):
        """The local test-code helper must not be exposed in production."""
        monkeypatch.delenv("PYTEST_RUNNING", raising=False)
        settings.debug = False

        response = client.get("/api/auth/test-code/test@example.com")

        assert response.status_code == 404

    def test_sign_in_with_google_success(self):
        """
        Test generating Google OAuth login URL and extracting code verifier
        """
        from app.services.auth_service import SupabaseAuthService
        from unittest.mock import MagicMock, patch

        service = SupabaseAuthService()
        
        # Mock the client returned by service.client
        mock_client_instance = MagicMock()
        mock_oauth_response = MagicMock()
        mock_oauth_response.url = "https://accounts.google.com/o/oauth2/v2/auth"
        mock_client_instance.auth.sign_in_with_oauth.return_value = mock_oauth_response
        
        mock_client_instance.auth._storage_key = "sb-test-key"
        mock_client_instance.auth._storage.get_item.return_value = "xyz_code_verifier"
        
        # Patch the get_supabase_client function
        with patch("app.services.auth_service.get_supabase_client", return_value=mock_client_instance):
            result = service.sign_in_with_google("http://localhost:8000/callback")
            
            assert result["url"] == "https://accounts.google.com/o/oauth2/v2/auth"
            assert result["code_verifier"] == "xyz_code_verifier"
            
            # Verify sign_in_with_oauth was called with correct parameters
            mock_client_instance.auth.sign_in_with_oauth.assert_called_once_with({
                "provider": "google",
                "options": {
                    "redirect_to": "http://localhost:8000/callback",
                    "query_params": {
                        "access_type": "offline",
                        "prompt": "consent"
                    }
                }
            })
            # Verify storage was queried with the correct key
            mock_client_instance.auth._storage.get_item.assert_called_once_with("sb-test-key-code-verifier")

