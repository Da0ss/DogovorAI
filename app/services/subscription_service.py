import logging
import os
from typing import Optional, Dict, Any

from config.database import get_supabase_admin_client
from config.settings import settings

logger = logging.getLogger(__name__) 

WEBHOOK_SECRET = settings.stripe_webhook_secret or ""
APP_URL = settings.app_url

PLANS = {
    "basic": {"price_id": None, "limit": 3},
    "pro":   {"price_id": "price_1TiRAF2MK0YOPZban716STqe", "limit": 30},
    "max":   {"price_id": "price_1TiRAc2MK0YOPZba3y9ftJvw", "limit": None},
}


class BillingManager:

    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase_admin_client()
        return self._supabase

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        from app.models.database import SessionLocal
        from app.models import crud
        db = SessionLocal()
        try:
            # Query by user_id first
            user_obj = crud.get_user_by_id(db, user_id)
            if user_obj:
                profile_dict = {
                    "id": str(user_obj.id),
                    "email": user_obj.email,
                    "plan_type": user_obj.plan_type,
                    "subscription_status": user_obj.subscription_status,
                    "stripe_customer_id": getattr(user_obj, "stripe_customer_id", None),
                    "analyses_used": getattr(user_obj, "analyses_used", 0)
                }
                return profile_dict
            return None
        finally:
            db.close()

    def _ensure_customer(self, user_id: str, email: str) -> str:
        profile = self.get_profile(user_id)
        if profile and profile.get("stripe_customer_id"):
            return profile["stripe_customer_id"]

        import stripe
        stripe.api_key = settings.stripe_secret_key or ""
        customer = stripe.Customer.create(
            email=email,
            metadata={"supabase_user_id": user_id}
        )

        from app.models.database import SessionLocal
        from app.models.models import User
        db = SessionLocal()
        try:
            db.query(User).filter(User.id == user_id).update({"stripe_customer_id": customer.id})
            db.commit()
        finally:
            db.close()

        return customer.id

    def create_checkout(self, user_id: str, plan_name: str, origin: Optional[str] = None) -> Optional[str]:
        plan_name = plan_name.lower()
        if plan_name not in PLANS:
            raise ValueError(f"Unknown plan: {plan_name}")

        if plan_name == "basic":
            from app.models.database import SessionLocal
            from app.models.models import User
            db = SessionLocal()
            try:
                db.query(User).filter(User.id == user_id).update({
                    "plan_type": "basic",
                    "subscription_status": "active"
                })
                db.commit()
            finally:
                db.close()
            return None

        profile = self.get_profile(user_id)
        if not profile:
            raise ValueError("Profile not found")

        customer_id = self._ensure_customer(user_id, profile.get("email", ""))
        price_id = PLANS[plan_name]["price_id"]

        base_url = origin or APP_URL
        if base_url.endswith("/"):
            base_url = base_url[:-1]

        import stripe
        stripe.api_key = settings.stripe_secret_key or ""
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{base_url}/app/profile?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/app/profile?payment=canceled",
            metadata={"supabase_user_id": user_id, "plan": plan_name}
        )

        return session.url

    def verify_checkout_session(self, session_id: str, user_id: str, db: Optional[Any] = None) -> Dict[str, Any]:
        import stripe
        stripe.api_key = settings.stripe_secret_key or ""
        
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception as e:
            logger.error(f"Failed to retrieve Stripe session {session_id}: {e}")
            raise ValueError("Invalid Stripe session ID.")
            
        # Convert Stripe object to dict for backward compatibility and uniform dictionary access
        session_dict = session.to_dict() if hasattr(session, "to_dict") else session
            
        metadata = session_dict.get("metadata", {}) or {}
        session_user_id = metadata.get("supabase_user_id")
        if session_user_id != user_id:
            logger.error(f"Stripe session user ID mismatch: session={session_user_id}, user={user_id}")
            raise ValueError("Session ownership verification failed.")
            
        if session_dict.get("payment_status") != "paid":
            logger.error(f"Stripe session not paid: {session_dict.get('payment_status')}")
            raise ValueError("Payment verification failed. Session status is not paid.")
            
        if db is not None:
            return self._on_checkout_completed(session_dict, db)

        from app.models.database import SessionLocal
        db_session = SessionLocal()
        try:
            res = self._on_checkout_completed(session_dict, db_session)
            return res
        finally:
            db_session.close()

    def handle_webhook(self, payload: bytes, sig: str, db: Optional[Any] = None) -> Dict[str, Any]:
        import stripe
        stripe.api_key = settings.stripe_secret_key or ""
        
        # Determine if we can bypass signature verification
        bypass_verification = False
        if not WEBHOOK_SECRET:
            from app.services.auth_context import is_debug_or_test
            if is_debug_or_test() or settings.debug:
                bypass_verification = True
            else:
                logger.error("❌ STRIPE_WEBHOOK_SECRET is not configured in production. Cannot verify Stripe webhooks.")
                raise ValueError("STRIPE_WEBHOOK_SECRET is not configured.")

        if bypass_verification:
            import json
            logger.warning("⚠️ STRIPE_WEBHOOK_SECRET is not configured. Parsing Stripe webhook payload directly in debug/test mode.")
            event = json.loads(payload.decode("utf-8"))
        else:
            event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
            
        event_type = event["type"]
        obj = event["data"]["object"]

        logger.info(f"🔔 Received Stripe Webhook event: {event_type}")

        if db is not None:
            return self._handle_webhook_events(event_type, obj, db)

        from app.models.database import SessionLocal
        db_session = SessionLocal()
        try:
            return self._handle_webhook_events(event_type, obj, db_session)
        finally:
            db_session.close()

    def _handle_webhook_events(self, event_type: str, obj: dict, db) -> Dict[str, Any]:
        if event_type == "checkout.session.completed":
            res = self._on_checkout_completed(obj, db)
            logger.info(f"Result for checkout.session.completed: {res}")
            return res

        if event_type == "customer.subscription.deleted":
            res = self._on_subscription_deleted(obj, db)
            logger.info(f"Result for customer.subscription.deleted: {res}")
            return res

        if event_type == "customer.subscription.updated":
            res = self._on_subscription_updated(obj, db)
            logger.info(f"Result for customer.subscription.updated: {res}")
            return res

        if event_type == "invoice.payment_failed":
            res = self._on_payment_failed(obj, db)
            logger.info(f"Result for invoice.payment_failed: {res}")
            return res

        return {"status": "ignored", "event": event_type}

    def _resolve_user(self, obj: dict, db) -> Optional[str]:
        metadata = obj.get("metadata", {}) or {}
        user_id = metadata.get("supabase_user_id")
        logger.info(f"🔍 Resolving user: metadata.supabase_user_id = {user_id}")
        if user_id:
            return user_id

        customer_id = obj.get("customer")
        logger.info(f"🔍 Resolving user: customer_id = {customer_id}")
        if not customer_id:
            return None

        from app.models.models import User
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        resolved_id = str(user.id) if user else None
        logger.info(f"🔍 Resolved user ID from database: {resolved_id}")
        return resolved_id

    def _on_checkout_completed(self, session_obj: dict, db) -> Dict[str, Any]:
        user_id = self._resolve_user(session_obj, db)
        plan = session_obj.get("metadata", {}).get("plan", "pro")
        logger.info(f"Processing checkout completed for user_id={user_id}, plan={plan}")

        if not user_id:
            logger.error(f"Checkout completed failed: user not found in metadata: {session_obj.get('metadata')}")
            return {"status": "error", "reason": "user_not_found"}

        from app.models.models import User, Subscription
        
        # 1. Update profiles table
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.plan_type = plan
            user.subscription_status = "active"
            user.analyses_limit = self.get_plan_limit(plan)
            stripe_cust_id = session_obj.get("customer")
            if stripe_cust_id:
                user.stripe_customer_id = stripe_cust_id

        # 2. Update/create record in subscriptions table
        stripe_sub_id = session_obj.get("subscription")
        stripe_cust_id = session_obj.get("customer")
        
        sub = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.provider == "stripe"
        ).first()
        
        if not sub:
            sub = Subscription(
                user_id=user_id,
                provider="stripe",
                plan_type=plan,
            )
            db.add(sub)
            
        sub.stripe_subscription_id = stripe_sub_id
        sub.provider_subscription_id = stripe_sub_id
        sub.stripe_customer_id = stripe_cust_id
        sub.provider_customer_id = stripe_cust_id
        sub.status = "active"
        sub.plan_type = plan
        sub.provider_event_data = session_obj
        
        db.commit()

        logger.info(f"Subscription activated: user={user_id}, plan={plan}")
        return {"status": "ok", "user_id": user_id, "plan": plan}

    def _on_subscription_deleted(self, sub_obj: dict, db) -> Dict[str, Any]:
        from app.models.models import Subscription, User
        
        stripe_sub_id = sub_obj.get("id")
        sub = db.query(Subscription).filter(
            Subscription.provider == "stripe",
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()
        
        if sub:
            sub.status = "canceled"
            if sub.user:
                sub.user.plan_type = "basic"
                sub.user.subscription_status = "canceled"
                sub.user.analyses_limit = 3
            db.commit()
            return {"status": "ok", "user_id": sub.user_id, "plan": "basic"}
            
        user_id = self._resolve_user(sub_obj, db)
        if not user_id:
            return {"status": "error", "reason": "customer_not_found"}
            
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.plan_type = "basic"
            user.subscription_status = "canceled"
            user.analyses_limit = 3
            db.commit()
            return {"status": "ok", "user_id": user_id, "plan": "basic"}
            
        return {"status": "error", "reason": "user_not_found"}

    def _on_subscription_updated(self, sub_obj: dict, db) -> Dict[str, Any]:
        from app.models.models import Subscription, User
        
        stripe_sub_id = sub_obj.get("id")
        stripe_status = sub_obj.get("status")
        status = "active" if stripe_status == "active" else "past_due"
        
        # Find plan from price_id in sub_obj if possible
        items = sub_obj.get("items", {}).get("data", [])
        plan = None
        if items:
            price_id = items[0].get("price", {}).get("id")
            for name, cfg in PLANS.items():
                if cfg["price_id"] == price_id:
                    plan = name
                    break
        
        sub = db.query(Subscription).filter(
            Subscription.provider == "stripe",
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()
        
        if sub:
            sub.status = status
            sub.provider_event_data = sub_obj
            if plan:
                sub.plan_type = plan
            if sub.user:
                sub.user.subscription_status = status
                if plan:
                    sub.user.plan_type = plan
                    sub.user.analyses_limit = self.get_plan_limit(plan)
            db.commit()
            return {"status": "ok", "user_id": sub.user_id, "subscription_status": status}
            
        user_id = self._resolve_user(sub_obj, db)
        if not user_id:
            return {"status": "error", "reason": "customer_not_found"}
            
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.subscription_status = status
            if plan:
                user.plan_type = plan
                user.analyses_limit = self.get_plan_limit(plan)
            db.commit()
            return {"status": "ok", "user_id": user_id, "subscription_status": status}
            
        return {"status": "error", "reason": "user_not_found"}

    def _on_payment_failed(self, invoice_obj: dict, db) -> Dict[str, Any]:
        from app.models.models import Subscription, User
        
        user_id = self._resolve_user(invoice_obj, db)
        if not user_id:
            return {"status": "error", "reason": "customer_not_found"}
            
        stripe_sub_id = invoice_obj.get("subscription")
        if stripe_sub_id:
            sub = db.query(Subscription).filter(
                Subscription.provider == "stripe",
                Subscription.stripe_subscription_id == stripe_sub_id
            ).first()
            if sub:
                sub.status = "past_due"
                
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.subscription_status = "past_due"
            
        db.commit()
        return {"status": "ok", "user_id": user_id, "subscription_status": "past_due"}

    def get_plan_limit(self, plan_name: str) -> Optional[int]:
        config = PLANS.get(plan_name.lower())
        return config["limit"] if config else 3

    def increment_usage(self, user_id: str) -> bool:
        from app.models.database import SessionLocal
        from app.models.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False

            plan = user.plan_type or "basic"
            limit = self.get_plan_limit(plan)
            used = user.analyses_used or 0

            if limit is not None and used >= limit:
                return False

            user.analyses_used = used + 1
            db.commit()
            return True
        finally:
            db.close()

    def get_usage(self, user_id: str) -> Dict[str, Any]:
        profile = self.get_profile(user_id)
        if not profile:
            return {"used": 0, "limit": 3, "plan": "basic", "status": "inactive"}

        plan = profile.get("plan_type", "basic")
        return {
            "used": profile.get("analyses_used", 0),
            "limit": self.get_plan_limit(plan),
            "plan": plan,
            "status": profile.get("subscription_status", "inactive")
        }


billing_manager = BillingManager()
