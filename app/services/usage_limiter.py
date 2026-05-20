"""
Usage Limiter Service — проверка и обновление лимитов анализов.

ЕДИНАЯ СХЕМА: все пользователи (local-token И Google OAuth/Supabase JWT)
трекаются в локальной PostgreSQL по таблице users.

Для Supabase JWT-пользователей поиск ведётся по email из профиля.
Если пользователь ещё не в локальной DB — создаётся запись на лету.

Лимиты (анализов/месяц):
  basic → 3
  pro   → 30
  max   → None (безлимит)

Ежемесячный сброс:
  При каждой проверке смотрим User.analyses_reset_at.
  Если now >= reset_at → counter = 0, reset_at = 1-е следующего месяца.
"""

import logging
import base64
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.models.database import SessionLocal
from app.models.models import User

logger = logging.getLogger(__name__)


def _decode_jwt_email(token: str) -> Optional[str]:
    """
    Извлекаем email из JWT payload БЕЗ проверки подписи.
    Используется ТОЛЬКО для трекинга лимитов — НЕ для авторизации.
    Работает даже если токен истёк (token is expired).
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        # Добавляем padding для base64
        payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        # Supabase хранит email в payload.email или payload.user_metadata.email
        email = (
            payload.get('email')
            or payload.get('user_metadata', {}).get('email')
            or payload.get('app_metadata', {}).get('email')
        )
        return email or None
    except Exception:
        return None

# ── Plan limits ──────────────────────────────────────────────────────────────
PLAN_LIMITS: Dict[str, Optional[int]] = {
    "basic": 3,
    "pro":   30,
    "max":   None,
}

PLAN_NAMES: Dict[str, str] = {
    "basic": "Basic",
    "pro":   "Pro",
    "max":   "Max",
}


def _now_utc() -> datetime:
    """Текущее UTC время, timezone-aware (совместимо с timestamptz в Supabase)."""
    return datetime.now(timezone.utc)


def _next_month_reset(now: datetime) -> datetime:
    """1-е число следующего месяца, 00:00:00 UTC, timezone-aware."""
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class UsageLimitError(Exception):
    """Поднимается когда пользователь превысил лимит."""
    def __init__(self, used: int, limit: int, plan: str, reset_at: Optional[str] = None):
        self.used = used
        self.limit = limit
        self.plan = plan
        self.reset_at = reset_at
        reset_msg = ""
        if reset_at:
            try:
                d = datetime.fromisoformat(reset_at)
                reset_msg = f" Лимит обновится {d.strftime('%d.%m.%Y')}."
            except Exception:
                pass
        super().__init__(
            f"Лимит анализов исчерпан ({used}/{limit}).{reset_msg} "
            f"Перейдите на более высокий тариф для продолжения."
        )


class UsageLimiter:
    """
    Универсальный сервис проверки и обновления лимитов.
    Все данные хранятся в локальной PostgreSQL (таблица users).
    """

    def get_plan_limit(self, plan: str) -> Optional[int]:
        return PLAN_LIMITS.get((plan or "basic").lower(), PLAN_LIMITS["basic"])

    # ─── Internal helpers ────────────────────────────────────────────────────

    def _maybe_reset_monthly(self, db, user: User) -> None:
        """Сброс счётчика, если наступил новый месяц."""
        now = _now_utc()
        if user.analyses_reset_at is None:
            user.analyses_reset_at = _next_month_reset(now)
            db.commit()
            return
        # Нормализуем reset_at: если naive — добавляем UTC timezone для сравнения
        reset_at = user.analyses_reset_at
        if reset_at.tzinfo is None:
            reset_at = reset_at.replace(tzinfo=timezone.utc)
        if now >= reset_at:
            old = user.analyses_used
            user.analyses_used = 0
            user.analyses_reset_at = _next_month_reset(now)
            db.commit()
            logger.info(
                f"🔄 Monthly reset: user_id={user.id} email={user.email} "
                f"was={old}, next_reset={user.analyses_reset_at}"
            )

    def _get_or_create_user_by_email(self, db, email: str, plan: str = "basic") -> Optional[User]:
        """
        Найти или создать запись пользователя в profiles по email (для OAuth-юзеров).
        hashed_password = None (НЕ '__oauth__' — совместимо с nullable полем).
        """
        user = db.query(User).filter(User.email == email).first()
        if user:
            return user
        # Создаём stub-запись для OAuth-пользователя
        try:
            user = User(
                email=email,
                hashed_password=None,       # OAuth — пароля нет
                is_verified=True,
                auth_provider="google",
                plan_type=plan,
                subscription_status="inactive",
                analyses_used=0,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"✅ Auto-created profiles stub for OAuth user: {email}")
            return user
        except Exception as e:
            db.rollback()
            logger.warning(f"⚠️ Could not auto-create user stub for {email}: {e}")
            return None

    def _build_info(self, user: User) -> Dict[str, Any]:
        """Build the standard usage info dict from a User ORM object."""
        plan  = (getattr(user, "plan_type", "basic") or "basic").lower()
        used  = getattr(user, "analyses_used", 0) or 0
        limit = self.get_plan_limit(plan)
        reset_at = (
            user.analyses_reset_at.isoformat()
            if getattr(user, "analyses_reset_at", None) else None
        )
        return {
            "allowed":   True,
            "used":      used,
            "limit":     limit,
            "plan":      plan,
            "plan_name": PLAN_NAMES.get(plan, plan.title()),
            "reset_at":  reset_at,
        }

    # ─── Core limit check (DB) ───────────────────────────────────────────────

    def _check_limit_by_user(self, user: User, db) -> Dict[str, Any]:
        """
        Check limit for a given User ORM object.
        Applies monthly reset, then checks used >= limit.
        Raises UsageLimitError if exceeded.
        """
        self._maybe_reset_monthly(db, user)
        info = self._build_info(user)

        if info["limit"] is None:        # unlimited
            return info

        if info["used"] >= info["limit"]:
            info["allowed"] = False
            raise UsageLimitError(
                used=info["used"],
                limit=info["limit"],
                plan=info["plan"],
                reset_at=info["reset_at"],
            )
        return info

    def _increment_by_user(self, user: User, db) -> int:
        """Increment analyses_used and persist."""
        if user.analyses_reset_at is None:
            user.analyses_reset_at = _next_month_reset(_now_utc())
        current = getattr(user, "analyses_used", 0) or 0
        user.analyses_used = current + 1
        db.commit()
        db.refresh(user)
        logger.info(
            f"📊 Usage incremented: user_id={user.id} email={user.email} "
            f"now={user.analyses_used}/{self.get_plan_limit(user.plan_type or 'basic')}"
        )
        return user.analyses_used

    # ─── LOCAL TOKEN ─────────────────────────────────────────────────────────

    def check_limit_local(self, user_id: str) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"allowed": True, "used": 0, "limit": PLAN_LIMITS["basic"],
                        "plan": "basic", "plan_name": "Basic", "reset_at": None}
            return self._check_limit_by_user(user, db)
        finally:
            db.close()

    def increment_local(self, user_id: str) -> int:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"⚠️ Cannot increment: user {user_id} not found")
                return 0
            return self._increment_by_user(user, db)
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to increment usage: {e}")
            return 0
        finally:
            db.close()

    def get_usage_local(self, user_id: str) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"used": 0, "limit": PLAN_LIMITS["basic"],
                        "plan": "basic", "plan_name": "Basic", "reset_at": None}
            self._maybe_reset_monthly(db, user)
            return self._build_info(user)
        finally:
            db.close()

    # ─── SUPABASE / GOOGLE OAUTH (mapped via email in local DB) ─────────────

    def _resolve_supabase_email(self, token: str) -> Optional[str]:
        """
        Извлекаем email из Supabase/Google JWT-токена.
        1. Сначала пробуем через auth_service (с проверкой подписи).
        2. Если токен истёк/невалиден — читаем payload без проверки (fallback).
        """
        # Попытка 1: через Supabase auth (Google OAuth, валидный токен)
        try:
            from app.services.auth_service import auth_service
            profile = auth_service.get_user_profile(token)
            if profile and profile.get("email"):
                return profile["email"]
        except Exception as e:
            logger.debug(f"auth_service.get_user_profile failed: {e}")

        # Попытка 2: читаем JWT payload без проверки (работает даже для истёкшего токена)
        email = _decode_jwt_email(token)
        if email:
            logger.info(f"ℹ️ JWT fallback email resolved: {email}")
            return email

        logger.warning("⚠️ Could not resolve Supabase user email from token")
        return None

    def check_limit_supabase(self, token: str) -> Dict[str, Any]:
        """
        Check limit for a Supabase/Google OAuth user.
        Looks up (or creates) a local User record by email.
        """
        email = self._resolve_supabase_email(token)
        if not email:
            logger.warning("⚠️ Could not resolve Supabase user email — allowing with basic limits")
            return {"allowed": True, "used": 0, "limit": PLAN_LIMITS["basic"],
                    "plan": "basic", "plan_name": "Basic", "reset_at": None}

        db = SessionLocal()
        try:
            user = self._get_or_create_user_by_email(db, email)
            if not user:
                return {"allowed": True, "used": 0, "limit": PLAN_LIMITS["basic"],
                        "plan": "basic", "plan_name": "Basic", "reset_at": None}
            return self._check_limit_by_user(user, db)
        finally:
            db.close()

    def increment_supabase(self, token: str) -> None:
        """Increment usage for a Supabase/Google OAuth user."""
        email = self._resolve_supabase_email(token)
        if not email:
            return
        db = SessionLocal()
        try:
            user = self._get_or_create_user_by_email(db, email)
            if user:
                self._increment_by_user(user, db)
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Failed to increment Supabase usage for {email}: {e}")
        finally:
            db.close()

    def get_usage_supabase(self, token: str) -> Dict[str, Any]:
        """Get usage info for a Supabase/Google OAuth user."""
        email = self._resolve_supabase_email(token)
        if not email:
            return {"used": 0, "limit": PLAN_LIMITS["basic"],
                    "plan": "basic", "plan_name": "Basic", "reset_at": None}
        db = SessionLocal()
        try:
            user = self._get_or_create_user_by_email(db, email)
            if not user:
                return {"used": 0, "limit": PLAN_LIMITS["basic"],
                        "plan": "basic", "plan_name": "Basic", "reset_at": None}
            self._maybe_reset_monthly(db, user)
            return self._build_info(user)
        finally:
            db.close()

    # ─── UNIVERSAL (auto-detect token type) ──────────────────────────────────

    def resolve_user(self, token: str) -> Dict[str, Any]:
        """
        Resolve user type from token.
        Returns {user_type: 'local'|'supabase'|'anonymous', user_id/token: ...}
        """
        if not token:
            return {"user_type": "anonymous"}
        if token.startswith("local-token-"):
            # user_id is UUID string after the prefix
            uid = token.replace("local-token-", "")
            if uid:
                return {"user_type": "local", "user_id": uid}
            return {"user_type": "anonymous"}
        # Treat all other tokens as Supabase JWT
        return {"user_type": "supabase", "token": token}

    def check_limit(self, token: str) -> Dict[str, Any]:
        """Universal limit check. Raises UsageLimitError if exceeded."""
        user = self.resolve_user(token)
        if user["user_type"] == "local":
            return self.check_limit_local(user["user_id"])
        elif user["user_type"] == "supabase":
            return self.check_limit_supabase(token)
        return {"allowed": True, "used": 0, "limit": PLAN_LIMITS["basic"],
                "plan": "basic", "plan_name": "Basic", "reset_at": None}

    def increment(self, token: str) -> None:
        """Universal usage increment — call AFTER a successful analysis."""
        user = self.resolve_user(token)
        if user["user_type"] == "local":
            self.increment_local(user["user_id"])
        elif user["user_type"] == "supabase":
            self.increment_supabase(token)

    def get_usage(self, token: str) -> Dict[str, Any]:
        """Universal usage info getter (no error raised)."""
        user = self.resolve_user(token)
        if user["user_type"] == "local":
            return self.get_usage_local(user["user_id"])
        elif user["user_type"] == "supabase":
            return self.get_usage_supabase(token)
        return {"used": 0, "limit": PLAN_LIMITS["basic"],
                "plan": "basic", "plan_name": "Basic", "reset_at": None}


# Global singleton
usage_limiter = UsageLimiter()
