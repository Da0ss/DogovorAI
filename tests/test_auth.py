"""
Tests for authentication endpoints
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from main import app
from app.models.database import get_db
from app.models.crud import get_user_by_email

client = TestClient(app)


class TestAuthentication:
    """Authentication endpoints tests"""

    def test_register_user_success(self):
        """
        Test successful user registration
        """
        user_data = {
            "email": "test@example.com",
            "password": "password123"
        }

        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 201

        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["is_verified"] is False
        assert "id" in data
        assert "created_at" in data

    def test_register_duplicate_email(self):
        """
        Test registration with existing email fails
        """
        user_data = {
            "email": "test@example.com",
            "password": "password123"
        }

        # First registration
        client.post("/api/auth/register", json=user_data)

        # Second registration with same email
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_verify_email_success(self, db_session):
        """
        Test successful email verification
        """
        # Register user
        user_data = {
            "email": "verify@example.com",
            "password": "password123"
        }
        client.post("/api/auth/register", json=user_data)

        # Get verification code from database (in real app, it would be sent via email)
        user = get_user_by_email(db_session, user_data["email"])
        verification_code = db_session.query(VerificationCode).filter(
            VerificationCode.user_id == user.id
        ).first()

        # Verify email
        verify_data = {
            "email": user_data["email"],
            "code": verification_code.code
        }
        response = client.post("/api/auth/verify", json=verify_data)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Email verified successfully"
        assert data["user"]["is_verified"] is True

    def test_verify_invalid_code(self):
        """
        Test verification with invalid code fails
        """
        verify_data = {
            "email": "test@example.com",
            "code": "000000"
        }

        response = client.post("/api/auth/verify", json=verify_data)
        assert response.status_code == 400
        assert "Invalid verification code" in response.json()["detail"]

    def test_resend_verification_code(self):
        """
        Test resending verification code
        """
        # Register user first
        user_data = {
            "email": "resend@example.com",
            "password": "password123"
        }
        client.post("/api/auth/register", json=user_data)

        # Resend code
        response = client.post("/api/auth/resend-code", params={"email": user_data["email"]})
        assert response.status_code == 200
        assert "Verification code sent successfully" in response.json()["message"]


@pytest.fixture
def db_session():
    """
    Provide database session for tests
    """
    from app.models.database import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Import here to avoid circular imports
from app.models.models import VerificationCode