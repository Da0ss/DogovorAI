import logging
import os
from typing import Optional, Dict, Any

from config.database import get_supabase_client
from config.settings import settings

logger = logging.getLogger(__name__)

WEBHOOK_SECRET = settings.stripe_webhook_secret or ""
APP_URL = settings.app_url

PLANS = {
    "basic": {"price_id": None, "limit": 3},
    "pro":   {"price_id": settings.stripe_price_id_pro or "price_1TNSws3Kw83n0jLXdLNtSN2h", "limit": 30},
    "max":   {"price_id": settings.stripe_price_id_max or "price_1TNSx73Kw83n0jLX06otxhnJ", "limit": None},
}


class BillingManager:

    def __init__(self):
        self._supabase = None

    @property
    def supabase(self):
        if self._supabase is None:
            self._supabase = get_supabase_client()
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

    def create_checkout(self, user_id: str, plan_name: str) -> Optional[str]:
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

        import stripe
        stripe.api_key = settings.stripe_secret_key or ""
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{APP_URL}/app/profile?payment=success",
            cancel_url=f"{APP_URL}/app/profile?payment=canceled",
            metadata={"supabase_user_id": user_id, "plan": plan_name}
        )

        return session.url

    def handle_webhook(self, payload: bytes, sig: str) -> Dict[str, Any]:
        import stripe
        stripe.api_key = settings.stripe_secret_key or ""
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
        event_type = event["type"]
        obj = event["data"]["object"]

        if event_type == "checkout.session.completed":
            return self._on_checkout_completed(obj)

        if event_type == "customer.subscription.deleted":
            return self._on_subscription_deleted(obj)

        if event_type == "customer.subscription.updated":
            return self._on_subscription_updated(obj)

        if event_type == "invoice.payment_failed":
            return self._on_payment_failed(obj)

        return {"status": "ignored", "event": event_type}

    def _resolve_user(self, obj: dict) -> Optional[str]:
        user_id = obj.get("metadata", {}).get("supabase_user_id")
        if user_id:
            return user_id

        customer_id = obj.get("customer")
        if not customer_id:
            return None

        result = self.supabase.table("profiles").select("id").eq(
            "stripe_customer_id", customer_id
        ).execute()
        return result.data[0]["id"] if result.data else None

    def _on_checkout_completed(self, session_obj: dict) -> Dict[str, Any]:
        user_id = self._resolve_user(session_obj)
        plan = session_obj.get("metadata", {}).get("plan", "pro")

        if not user_id:
            return {"status": "error", "reason": "user_not_found"}

        self.supabase.table("profiles").update({
            "plan_type": plan,
            "subscription_status": "active"
        }).eq("id", user_id).execute()

        logger.info(f"Subscription activated: user={user_id}, plan={plan}")
        return {"status": "ok", "user_id": user_id, "plan": plan}

    def _on_subscription_deleted(self, sub_obj: dict) -> Dict[str, Any]:
        user_id = self._resolve_user(sub_obj)
        if not user_id:
            return {"status": "error", "reason": "customer_not_found"}

        self.supabase.table("profiles").update({
            "plan_type": "basic",
            "subscription_status": "canceled"
        }).eq("id", user_id).execute()

        logger.info(f"Subscription canceled: user={user_id}")
        return {"status": "ok", "user_id": user_id, "plan": "basic"}

    def _on_subscription_updated(self, sub_obj: dict) -> Dict[str, Any]:
        user_id = self._resolve_user(sub_obj)
        if not user_id:
            return {"status": "error", "reason": "customer_not_found"}

        status = "active" if sub_obj.get("status") == "active" else "past_due"
        self.supabase.table("profiles").update({
            "subscription_status": status
        }).eq("id", user_id).execute()

        return {"status": "ok", "user_id": user_id, "subscription_status": status}

    def _on_payment_failed(self, invoice_obj: dict) -> Dict[str, Any]:
        user_id = self._resolve_user(invoice_obj)
        if not user_id:
            return {"status": "error", "reason": "customer_not_found"}

        self.supabase.table("profiles").update({
            "subscription_status": "past_due"
        }).eq("id", user_id).execute()

        return {"status": "ok", "user_id": user_id, "subscription_status": "past_due"}

    def get_plan_limit(self, plan_name: str) -> Optional[int]:
        config = PLANS.get(plan_name.lower())
        return config["limit"] if config else 3

    def increment_usage(self, user_id: str) -> bool:
        profile = self.get_profile(user_id)
        if not profile:
            return False

        plan = profile.get("plan_type", "basic")
        limit = self.get_plan_limit(plan)
        used = profile.get("analyses_used", 0)

        if limit is not None and used >= limit:
            return False

        self.supabase.table("profiles").update({
            "analyses_used": used + 1
        }).eq("id", user_id).execute()
        return True

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
