import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

# SQLite compatibility with JSONB for testing
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


from main import app
from app.models.models import Base, User, Subscription
from app.models.database import get_db

client = TestClient(app)


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    """Create a clean in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Override FastAPI dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
            
    app.dependency_overrides[get_db] = override_get_db
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture(name="test_data")
def fixture_test_data(db_session):
    """Seed database with test user and subscription."""
    user = User(
        id="test-user-id",
        email="test_user@example.com",
        is_verified=True,
    )
    db_session.add(user)
    
    sub = Subscription(
        id="sub-id-123",
        user_id="test-user-id",
        provider="paypal",
        provider_subscription_id="I-TESTSUBSCRIPTION1",
        provider_customer_id="payer-id-123",
        status="inactive"
    )
    db_session.add(sub)
    db_session.commit()
    return {"user": user, "subscription": sub}


class TestPayPalWebhook:
    
    @patch("app.services.paypal_service.verify_webhook_signature", new_callable=AsyncMock)
    def test_webhook_unauthorized_when_signature_invalid(self, mock_verify, db_session, test_data):
        mock_verify.return_value = False
        
        headers = {
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "url",
            "PAYPAL-TRANSMISSION-ID": "tx-id",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "time"
        }
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-TESTSUBSCRIPTION1"
            }
        }
        
        # We need to temporarily configure webhook ID to bypass settings check
        with patch("config.settings.settings.paypal_webhook_id", "wh-id-123"):
            response = client.post("/api/paypal/webhook", json=payload, headers=headers)
            
        assert response.status_code == 401
        assert response.json()["detail"] == "Signature verification failed"
        
        # Verify DB subscription remains inactive
        db_session.refresh(test_data["subscription"])
        assert test_data["subscription"].status == "inactive"

    @patch("app.services.paypal_service.verify_webhook_signature", new_callable=AsyncMock)
    def test_webhook_unconfigured_server_error(self, mock_verify, db_session, test_data):
        headers = {
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "url",
            "PAYPAL-TRANSMISSION-ID": "tx-id",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "time"
        }
        
        # With empty webhook ID, it should return 500
        with patch("config.settings.settings.paypal_webhook_id", None):
            response = client.post("/api/paypal/webhook", json={}, headers=headers)
            
        assert response.status_code == 500
        assert "unconfigured" in response.json()["detail"]

    @patch("app.services.paypal_service.verify_webhook_signature", new_callable=AsyncMock)
    def test_webhook_activates_subscription(self, mock_verify, db_session, test_data):
        mock_verify.return_value = True
        
        headers = {
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "url",
            "PAYPAL-TRANSMISSION-ID": "tx-id",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "time"
        }
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "I-TESTSUBSCRIPTION1",
                "status": "ACTIVE",
                "start_time": "2026-06-17T03:25:00Z"
            }
        }
        
        with patch("config.settings.settings.paypal_webhook_id", "wh-id-123"):
            response = client.post("/api/paypal/webhook", json=payload, headers=headers)
            
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # Verify DB subscription is now active
        db_session.refresh(test_data["subscription"])
        assert test_data["subscription"].status == "active"
        assert test_data["subscription"].current_period_start is not None
        assert test_data["subscription"].provider_event_data == payload

    @patch("app.services.paypal_service.verify_webhook_signature", new_callable=AsyncMock)
    def test_webhook_cancels_subscription(self, mock_verify, db_session, test_data):
        mock_verify.return_value = True
        
        # Set to active first
        test_data["subscription"].status = "active"
        db_session.commit()
        
        headers = {
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "url",
            "PAYPAL-TRANSMISSION-ID": "tx-id",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "time"
        }
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.CANCELLED",
            "resource": {
                "id": "I-TESTSUBSCRIPTION1",
                "status": "CANCELLED",
                "status_update_time": "2026-06-17T05:00:00Z"
            }
        }
        
        with patch("config.settings.settings.paypal_webhook_id", "wh-id-123"):
            response = client.post("/api/paypal/webhook", json=payload, headers=headers)
            
        assert response.status_code == 200
        
        # Verify DB subscription is canceled
        db_session.refresh(test_data["subscription"])
        assert test_data["subscription"].status == "canceled"
        assert test_data["subscription"].canceled_at is not None

    @patch("app.services.paypal_service.verify_webhook_signature", new_callable=AsyncMock)
    def test_webhook_payment_completed(self, mock_verify, db_session, test_data):
        mock_verify.return_value = True
        
        headers = {
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "url",
            "PAYPAL-TRANSMISSION-ID": "tx-id",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "time"
        }
        payload = {
            "event_type": "PAYMENT.SALE.COMPLETED",
            "resource": {
                "billing_agreement_id": "I-TESTSUBSCRIPTION1",
                "state": "completed",
                "create_time": "2026-06-17T06:00:00Z"
            }
        }
        
        with patch("config.settings.settings.paypal_webhook_id", "wh-id-123"):
            response = client.post("/api/paypal/webhook", json=payload, headers=headers)
            
        assert response.status_code == 200
        
        # Verify status is active and date updated
        db_session.refresh(test_data["subscription"])
        assert test_data["subscription"].status == "active"
        actual_dt = test_data["subscription"].current_period_start
        if actual_dt and actual_dt.tzinfo is not None:
            actual_dt = actual_dt.replace(tzinfo=None)
        assert actual_dt == datetime.fromisoformat("2026-06-17T06:00:00")

    @patch("app.services.paypal_service.verify_webhook_signature", new_callable=AsyncMock)
    def test_webhook_subscription_not_found(self, mock_verify, db_session):
        mock_verify.return_value = True
        
        headers = {
            "PAYPAL-AUTH-ALGO": "algo",
            "PAYPAL-CERT-URL": "url",
            "PAYPAL-TRANSMISSION-ID": "tx-id",
            "PAYPAL-TRANSMISSION-SIG": "sig",
            "PAYPAL-TRANSMISSION-TIME": "time"
        }
        payload = {
            "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
            "resource": {
                "id": "NON-EXISTENT-ID"
            }
        }
        
        with patch("config.settings.settings.paypal_webhook_id", "wh-id-123"):
            response = client.post("/api/paypal/webhook", json=payload, headers=headers)
            
        assert response.status_code == 200
        # Should return error status in payload rather than HTTP error
        assert response.json()["status"] == "error"
        assert "skipped or failed" in response.json()["message"]
