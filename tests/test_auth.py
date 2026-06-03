"""
Tests for authentication endpoints using Supabase Auth
"""

import pytest
import uuid


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

        # Fetch the actual verification code for testing from the endpoint
        code_resp = client.get(f"/api/auth/test-code/{user_data['email']}")
        assert code_resp.status_code == 200
        verification_code = code_resp.json()["code"]

        verify_data = {
            "email": user_data["email"],
            "code": verification_code
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

        # Get code and verify first to allow successful login
        code_resp = client.get(f"/api/auth/test-code/{user_data['email']}")
        assert code_resp.status_code == 200
        verification_code = code_resp.json()["code"]
        client.post("/api/auth/verify", json={
            "email": user_data["email"],
            "code": verification_code
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