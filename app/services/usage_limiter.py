"""
Usage Limiter Service — проверка и обновление лимитов анализов.

Работает с двумя источниками данных:
- Supabase profiles (Google OAuth / production users)
- Local SQLAlchemy User model (local-token users)

Лимиты:
- basic: 3 анализа/месяц
- pro:   30 анализов/месяц
- max:   безлимит
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.models.database import SessionLocal
from app.models.models import User

logger = logging.getLogger(__name__)

# Plan limits configuration
PLAN_LIMITS: Dict[str, Optional[int]] = {
    "basic": 3,
    "pro": 30,
    "max": None,   # unlimited
}

# Human-readable plan names
PLAN_NAMES: Dict[str, str] = {
    "basic": "Basic",
    "pro": "Pro",
    "max": "Max",
}


class UsageLimitError(Exception):
    """Raised when user has exceeded their plan limit."""
    def __init__(self, used: int, limit: int, plan: str):
        self.used = used
        self.limit = limit
        self.plan = plan
        super().__init__(
            f"Лимит бесплатных анализов исчерпан ({used}/{limit}). "
            f"Пожалуйста, приобретите подписку для продолжения."
        )


class UsageLimiter:
    """
    Service for checking and updating usage limits.

    Supports both local-token users (SQLAlchemy) and Supabase JWT users.
    """

    def get_plan_limit(self, plan: str) -> Optional[int]:
        """Get the analysis limit for a given plan."""
        return PLAN_LIMITS.get(plan.lower(), PLAN_LIMITS["basic"])

    # ================================================================
    # LOCAL TOKEN USERS (SQLAlchemy)
    # ================================================================

    def _get_local_user(self, user_id: int) -> Optional[User]:
        """Get local user by ID."""
        db = SessionLocal()
        try:
            return db.query(User).filter(User.id == user_id).first()
        finally:
            db.close()

    def _check_monthly_reset_local(self, user: User) -> None:
        """
        Reset analyses_used to 0 if a new month has started.
        For local users (no analyses_reset_at field in local model),
        we skip monthly reset logic — it's handled by Supabase profiles.
        """
        pass

    def check_limit_local(self, user_id: int) -> Dict[str, Any]:
        """
        Check if a local user can perform an analysis.

        Returns:
            Dict with keys: allowed, used, limit, plan, plan_name

        Raises:
            UsageLimitError if limit is exceeded
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                # Unknown user — allow with basic limits
                return {
                    "allowed": True,
                    "used": 0,
                    "limit": PLAN_LIMITS["basic"],
                    "plan": "basic",
                    "plan_name": "Basic",
                }

            plan = getattr(user, "plan_type", "basic") or "basic"
            used = getattr(user, "analyses_used", 0) or 0
            limit = self.get_plan_limit(plan)

            info = {
                "allowed": True,
                "used": used,
                "limit": limit,
                "plan": plan,
                "plan_name": PLAN_NAMES.get(plan, plan.title()),
            }

            # Unlimited plan
            if limit is None:
                return info

            # Check limit
            if used >= limit:
                info["allowed"] = False
                raise UsageLimitError(used=used, limit=limit, plan=plan)

            return info
        finally:
            db.close()

    def increment_local(self, user_id: int) -> int:
        """
        Increment analyses_used for a local user.

        Returns:
            New value of analyses_used
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"⚠️ Cannot increment: user {user_id} not found")
                return 0

            current = getattr(user, "analyses_used", 0) or 0
            user.analyses_used = current + 1
            db.commit()
            db.refresh(user)

            logger.info(f"📊 Usage incremented: user={user_id}, now={user.analyses_used}")
            return user.analyses_used
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to increment usage: {e}")
            return 0
        finally:
            db.close()

    def get_usage_local(self, user_id: int) -> Dict[str, Any]:
        """Get usage info for a local user (no error raised)."""
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {
                    "used": 0,
                    "limit": PLAN_LIMITS["basic"],
                    "plan": "basic",
                    "plan_name": "Basic",
                }

            plan = getattr(user, "plan_type", "basic") or "basic"
            used = getattr(user, "analyses_used", 0) or 0
            limit = self.get_plan_limit(plan)

            return {
                "used": used,
                "limit": limit,
                "plan": plan,
                "plan_name": PLAN_NAMES.get(plan, plan.title()),
            }
        finally:
            db.close()

    # ================================================================
    # SUPABASE USERS (profiles table)
    # ================================================================

    def check_limit_supabase(self, user_id: str) -> Dict[str, Any]:
        """
        Check if a Supabase user can perform an analysis.
        Uses BillingManager for Supabase profile lookup.
        """
        try:
            from app.services.subscription_service import billing_manager
            profile = billing_manager.get_profile(user_id)
        except Exception as e:
            logger.warning(f"⚠️ Supabase profile lookup failed: {e}")
            return {
                "allowed": True,
                "used": 0,
                "limit": PLAN_LIMITS["basic"],
                "plan": "basic",
                "plan_name": "Basic",
            }

        if not profile:
            return {
                "allowed": True,
                "used": 0,
                "limit": PLAN_LIMITS["basic"],
                "plan": "basic",
                "plan_name": "Basic",
            }

        plan = profile.get("plan_type", "basic")
        used = profile.get("analyses_used", 0) or 0
        limit = self.get_plan_limit(plan)

        # Check monthly reset
        reset_at = profile.get("analyses_reset_at")
        if reset_at and isinstance(reset_at, str):
            try:
                reset_dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if now >= reset_dt:
                    # Reset counter
                    from app.services.subscription_service import billing_manager
                    next_reset = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                    if now.month == 12:
                        next_reset = next_reset.replace(year=now.year + 1, month=1)
                    else:
                        next_reset = next_reset.replace(month=now.month + 1)

                    billing_manager.supabase.table("profiles").update({
                        "analyses_used": 0,
                        "analyses_reset_at": next_reset.isoformat(),
                    }).eq("id", user_id).execute()
                    used = 0
                    logger.info(f"🔄 Monthly reset for user {user_id}")
            except Exception as e:
                logger.warning(f"⚠️ Could not parse reset_at: {e}")

        info = {
            "allowed": True,
            "used": used,
            "limit": limit,
            "plan": plan,
            "plan_name": PLAN_NAMES.get(plan, plan.title()),
        }

        if limit is not None and used >= limit:
            info["allowed"] = False
            raise UsageLimitError(used=used, limit=limit, plan=plan)

        return info

    def increment_supabase(self, user_id: str) -> bool:
        """Increment analyses_used for a Supabase user."""
        try:
            from app.services.subscription_service import billing_manager
            return billing_manager.increment_usage(user_id)
        except Exception as e:
            logger.error(f"❌ Failed to increment Supabase usage: {e}")
            return False

    def get_usage_supabase(self, user_id: str) -> Dict[str, Any]:
        """Get usage info for a Supabase user."""
        try:
            from app.services.subscription_service import billing_manager
            usage = billing_manager.get_usage(user_id)
            plan = usage.get("plan", "basic")
            return {
                "used": usage.get("used", 0),
                "limit": usage.get("limit", PLAN_LIMITS["basic"]),
                "plan": plan,
                "plan_name": PLAN_NAMES.get(plan, plan.title()),
            }
        except Exception as e:
            logger.error(f"❌ Failed to get Supabase usage: {e}")
            return {
                "used": 0,
                "limit": PLAN_LIMITS["basic"],
                "plan": "basic",
                "plan_name": "Basic",
            }

    # ================================================================
    # UNIVERSAL METHODS (auto-detect token type)
    # ================================================================

    def resolve_user(self, token: str) -> Dict[str, Any]:
        """
        Resolve user from auth token. Returns dict with:
        - user_type: 'local' | 'supabase' | 'anonymous'
        - user_id: str or int
        """
        if not token:
            return {"user_type": "anonymous", "user_id": None}

        if token.startswith("local-token-"):
            try:
                uid = int(token.replace("local-token-", ""))
                return {"user_type": "local", "user_id": uid}
            except ValueError:
                return {"user_type": "anonymous", "user_id": None}

        # Supabase JWT — try to get user
        try:
            from app.services.auth_service import auth_service
            profile = auth_service.get_user_profile(token)
            if profile and profile.get("id"):
                return {"user_type": "supabase", "user_id": profile["id"]}
        except Exception:
            pass

        return {"user_type": "anonymous", "user_id": None}

    def check_limit(self, token: str) -> Dict[str, Any]:
        """
        Universal limit check. Returns usage info dict.
        Raises UsageLimitError if exceeded.
        """
        user = self.resolve_user(token)

        if user["user_type"] == "local":
            return self.check_limit_local(user["user_id"])
        elif user["user_type"] == "supabase":
            return self.check_limit_supabase(user["user_id"])
        else:
            # Anonymous — allow but don't track
            return {
                "allowed": True,
                "used": 0,
                "limit": PLAN_LIMITS["basic"],
                "plan": "basic",
                "plan_name": "Basic",
            }

    def increment(self, token: str) -> None:
        """Universal usage increment after successful analysis."""
        user = self.resolve_user(token)

        if user["user_type"] == "local":
            self.increment_local(user["user_id"])
        elif user["user_type"] == "supabase":
            self.increment_supabase(user["user_id"])
        # Anonymous — no tracking

    def get_usage(self, token: str) -> Dict[str, Any]:
        """Universal usage info getter."""
        user = self.resolve_user(token)

        if user["user_type"] == "local":
            return self.get_usage_local(user["user_id"])
        elif user["user_type"] == "supabase":
            return self.get_usage_supabase(user["user_id"])
        else:
            return {
                "used": 0,
                "limit": PLAN_LIMITS["basic"],
                "plan": "basic",
                "plan_name": "Basic",
            }


# Global singleton
usage_limiter = UsageLimiter()
