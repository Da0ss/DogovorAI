"""
Authentication context helpers shared by API modules.

Production trusts Supabase sessions only. Local tokens are accepted only in
debug/test mode so development fixtures keep working without weakening Vercel.
"""

import logging
import os
from typing import Any, Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.models import User
from config.settings import settings

logger = logging.getLogger(__name__)


def is_debug_or_test() -> bool:
    """Return True for explicitly local/test-only behavior."""
    return settings.debug or os.getenv("PYTEST_RUNNING") == "1"


def extract_bearer_token(request: Request) -> Optional[str]:
    """Extract Bearer token from an incoming request."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    return token or None


def get_supabase_profile(token: str) -> Optional[dict[str, Any]]:
    """Validate a Supabase access token and return profile data."""
    from app.services.auth_service import auth_service

    return auth_service.get_user_profile(token)


def ensure_local_profile(
    db: Session,
    *,
    user_id: Optional[str],
    email: str,
    is_verified: bool = True,
    auth_provider: str = "supabase",
    full_name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    consent_accepted: bool = False,
) -> User:
    """Create or update a local profiles row for Supabase-backed users."""
    from datetime import datetime as _dt

    normalized_email = email.lower()
    user = None

    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        user = db.query(User).filter(User.email.ilike(normalized_email)).first()

    if user is None:
        kwargs: dict[str, Any] = {
            "email": normalized_email,
            "hashed_password": None,
            "is_verified": is_verified,
            "auth_provider": auth_provider,
            "full_name": full_name,
            "avatar_url": avatar_url,
            "consent_accepted": consent_accepted,
            "consent_accepted_at": _dt.utcnow() if consent_accepted else None,
        }
        if user_id:
            kwargs["id"] = user_id
        user = User(**kwargs)
        db.add(user)
    else:
        user.email = normalized_email
        user.is_verified = bool(user.is_verified or is_verified)
        user.auth_provider = getattr(user, "auth_provider", None) or auth_provider
        if full_name and not getattr(user, "full_name", None):
            user.full_name = full_name
        if avatar_url and not getattr(user, "avatar_url", None):
            user.avatar_url = avatar_url
        # Update consent if newly accepted
        if consent_accepted and not getattr(user, "consent_accepted", False):
            user.consent_accepted = True
            user.consent_accepted_at = _dt.utcnow()

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        user = db.query(User).filter(User.email.ilike(normalized_email)).first()
        if user is None:
            raise
    return user


def resolve_authenticated_user(request: Request, db: Session) -> dict[str, Any]:
    """Resolve the current user from a local dev token or Supabase token."""
    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    if token.startswith("local-token-"):
        if not is_debug_or_test():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        user_id = token.replace("local-token-", "", 1)
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return {
            "id": str(user.id),
            "email": user.email,
            "is_verified": bool(user.is_verified),
            "auth_provider": getattr(user, "auth_provider", "local") or "local",
        }

    profile = get_supabase_profile(token)
    if not profile or not profile.get("email"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = ensure_local_profile(
        db,
        user_id=str(profile.get("id")) if profile.get("id") else None,
        email=profile["email"],
        is_verified=bool(profile.get("is_verified", True)),
        auth_provider="supabase",
        full_name=profile.get("full_name"),
        avatar_url=profile.get("avatar_url"),
    )
    return {
        "id": str(user.id),
        "email": user.email,
        "is_verified": bool(user.is_verified),
        "auth_provider": getattr(user, "auth_provider", "supabase") or "supabase",
        "profile": profile,
    }


def require_admin_user(request: Request, db: Session) -> dict[str, Any]:
    """Require an authenticated user whose email is listed in ADMIN_EMAILS."""
    user = resolve_authenticated_user(request, db)
    admin_emails = settings.admin_email_set
    if not admin_emails:
        logger.warning("ADMIN_EMAILS is not configured; admin endpoint denied")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is not configured")

    if (user.get("email") or "").lower() not in admin_emails:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
