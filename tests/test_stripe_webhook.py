import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

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
    """Seed database with test user."""
    user = User(
        id="test-user-id",
        email="test_user@example.com",
        is_verified=True,
        plan_type="basic",
        subscription_status="inactive"
    )
    db_session.add(user)
    db_session.commit()
    return {"user": user}


class TestStripeWebhook:

    @patch("stripe.Webhook.construct_event")
    def test_webhook_activates_subscription_and_updates_profile(self, mock_construct_event, db_session, test_data):
        # Setup mock event
        session_obj = {
            "id": "cs_test_123",
            "customer": "cus_test_123",
            "subscription": "sub_test_123",
            "metadata": {
                "supabase_user_id": "test-user-id",
                "plan": "pro"
            }
        }
        
        mock_construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": session_obj
            }
        }
        
        headers = {"stripe-signature": "t=123,v1=sig"}
        
        with patch("app.services.subscription_service.WEBHOOK_SECRET", "whsec_test"):
            response = client.post("/api/subscriptions/webhook", json={}, headers=headers)
            
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        
        # Verify user profile in DB
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == "test-user-id").first()
        assert user.plan_type == "pro"
        assert user.subscription_status == "active"
        assert user.stripe_customer_id == "cus_test_123"
        
        # Verify subscription in DB
        sub = db_session.query(Subscription).filter(
            Subscription.user_id == "test-user-id",
            Subscription.provider == "stripe"
        ).first()
        assert sub is not None
        assert sub.stripe_subscription_id == "sub_test_123"
        assert sub.provider_subscription_id == "sub_test_123"
        assert sub.stripe_customer_id == "cus_test_123"
        assert sub.provider_customer_id == "cus_test_123"
        assert sub.status == "active"
        assert sub.plan_type == "pro"

    @patch("stripe.Webhook.construct_event")
    def test_webhook_unconfigured_secret_bypass_in_debug(self, mock_construct_event, db_session, test_data):
        session_obj = {
            "id": "cs_test_123",
            "customer": "cus_test_123",
            "subscription": "sub_test_123",
            "metadata": {
                "supabase_user_id": "test-user-id",
                "plan": "max"
            }
        }
        
        # We'll mock Settings.debug to True and stripe_webhook_secret to None
        with patch("config.settings.settings.debug", True), \
             patch("app.services.subscription_service.WEBHOOK_SECRET", ""):
                 
            # If signature bypass works, it should parse the json body directly without using Webhook.construct_event
            payload = {
                "type": "checkout.session.completed",
                "data": {
                    "object": session_obj
                }
            }
            response = client.post("/api/subscriptions/webhook", json=payload, headers={"stripe-signature": "t=123,v1=sig"})
            
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == "test-user-id").first()
        assert user.plan_type == "max"
        assert user.subscription_status == "active"

    @patch("app.services.auth_context.resolve_authenticated_user")
    @patch("stripe.checkout.Session.retrieve")
    def test_verify_session_success(self, mock_retrieve, mock_resolve_user, db_session, test_data):
        mock_resolve_user.return_value = {
            "id": "test-user-id",
            "email": "test_user@example.com",
            "is_verified": True
        }
        
        mock_retrieve.return_value = {
            "id": "cs_test_999",
            "customer": "cus_test_999",
            "subscription": "sub_test_999",
            "payment_status": "paid",
            "metadata": {
                "supabase_user_id": "test-user-id",
                "plan": "pro"
            }
        }
        
        response = client.post(
            "/api/subscriptions/verify-session",
            json={"session_id": "cs_test_999", "user_id": "test-user-id"},
            headers={"Authorization": "Bearer local-token-test-user-id"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        
        # Verify db changes
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == "test-user-id").first()
        assert user.plan_type == "pro"
        assert user.subscription_status == "active"
        assert user.analyses_limit == 30

    @patch("app.services.auth_context.resolve_authenticated_user")
    def test_verify_session_unauthorized_user_mismatch(self, mock_resolve_user, db_session, test_data):
        mock_resolve_user.return_value = {
            "id": "different-user-id",
            "email": "diff@example.com",
            "is_verified": True
        }
        
        response = client.post(
            "/api/subscriptions/verify-session",
            json={"session_id": "cs_test_999", "user_id": "test-user-id"},
            headers={"Authorization": "Bearer local-token-different-user-id"}
        )
        
        assert response.status_code == 403
        assert "mismatch" in response.json()["detail"]
