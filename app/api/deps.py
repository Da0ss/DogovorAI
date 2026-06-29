"""
Re-usable security, authentication, and RBAC dependencies for FastAPI endpoints.
Ensures strict validation, Anti-IDOR checks, and event logging with IP tracking.
"""

import logging
from typing import Any, List, Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.models import User
from config.settings import settings
from app.services.auth_context import (
    extract_bearer_token,
    is_debug_or_test,
    get_supabase_profile,
    ensure_local_profile,
)

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to validate JWT session/token and return the current authenticated User.
    Supports local development tokens in debug/test mode.
    
    Strictly uses SQLAlchemy ORM to prevent SQL injection.
    Logs failed login/auth attempts with client IP tracking.
    """
    client_ip = request.client.host if request.client else "unknown"
    token = extract_bearer_token(request)
    
    if not token:
        logger.warning(
            f"🔒 Security Alert: Unauthenticated access attempt to secure endpoint: "
            f"{request.url.path}. IP: {client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима авторизация. Токен отсутствует.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 1. Local development token processing
    if token.startswith("local-token-"):
        if not is_debug_or_test():
            logger.error(
                f"🚨 Critical Security Alert: Local dev token bypassed to production! "
                f"Token: {token[:15]}... IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недопустимый токен авторизации."
            )

        user_id = token.replace("local-token-", "", 1)
        # ORM Only Query
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(
                f"🔒 Security Warning: Dev token reference to non-existent user ID {user_id}. IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден."
            )
    else:
        # 2. Supabase JWT validation
        try:
            profile = get_supabase_profile(token)
        except Exception as e:
            logger.error(
                f"🔒 Authentication system error during token validation: {str(e)}. IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка аутентификации. Попробуйте позже."
            )

        if not profile or not profile.get("email"):
            logger.warning(
                f"🔒 Security Alert: Invalid or expired JWT token attempted. IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный или истекший токен авторизации."
            )

        # 3. Resolve and sync local profile
        try:
            user = ensure_local_profile(
                db,
                user_id=str(profile.get("id")) if profile.get("id") else None,
                email=profile["email"],
                is_verified=bool(profile.get("is_verified", True)),
                auth_provider="supabase",
                full_name=profile.get("full_name"),
                avatar_url=profile.get("avatar_url"),
            )
        except Exception as e:
            logger.error(
                f"❌ Database error while syncing user profile: {str(e)}. Email: {profile['email']}. IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка синхронизации профиля."
            )

    # 4. Check if account is banned/deactivated
    if getattr(user, "subscription_status", None) == "banned":
        logger.warning(
            f"🔒 Access Denied: Banned user attempted to access the system: {user.email}. IP: {client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ваш аккаунт заблокирован администратором."
        )

    return user


async def check_admin_role(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency to verify the current authenticated user has administrative privileges.
    Checks if email is configured in ADMIN_EMAILS.
    Logs failed admin access attempts and successful admin actions.
    """
    client_ip = request.client.host if request.client else "unknown"
    admin_emails = settings.admin_email_set

    if not admin_emails or current_user.email.lower() not in admin_emails:
        logger.warning(
            f"🚨 Unauthorized Admin Action Attempt: User {current_user.email} (ID: {current_user.id}) "
            f"tried to access admin route {request.url.path}. IP: {client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен. Необходимы права администратора."
        )

    # Log access for auditing
    logger.info(
        f"👑 Admin Operation: Admin {current_user.email} (ID: {current_user.id}) "
        f"accessed {request.url.path}. IP: {client_ip}"
    )
    return current_user


class RequireRoles:
    """
    Role-Based Access Control (RBAC) Dependency.
    Allows routing restriction based on subscription plans or custom roles.
    
    Usage:
        @app.get("/premium-feature", dependencies=[Depends(RequireRoles("pro", "max"))])
    """
    def __init__(self, *allowed_roles: str):
        self.allowed_roles = [role.lower().strip() for role in allowed_roles]

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user)
    ) -> User:
        client_ip = request.client.host if request.client else "unknown"
        
        # Build user roles list
        user_roles = ["user"]  # Every active user gets the 'user' role
        
        if current_user.plan_type:
            user_roles.append(current_user.plan_type.lower())
            
        admin_emails = settings.admin_email_set
        if admin_emails and current_user.email.lower() in admin_emails:
            user_roles.append("admin")

        # Check intersection
        has_access = any(role in user_roles for role in self.allowed_roles)
        
        if not has_access:
            logger.warning(
                f"🔒 RBAC Denied: User {current_user.email} (Roles: {user_roles}) "
                f"denied access to {request.url.path} (Required: {self.allowed_roles}). IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Недостаточно прав. Требуемые роли: {', '.join(self.allowed_roles)}"
            )

        return current_user


def verify_owner(owner_id_param: str = "user_id"):
    """
    Anti-IDOR Dependency Generator.
    Ensures that the current authenticated user matches the owner ID specified
    in path parameters, query parameters, or request headers.
    
    Usage:
        @app.get("/users/{user_id}/documents", dependencies=[Depends(verify_owner("user_id"))])
    """
    async def dependency(
        request: Request,
        current_user: User = Depends(get_current_user)
    ) -> None:
        client_ip = request.client.host if request.client else "unknown"
        
        # Retrieve target owner ID from path params or query params
        target_owner_id = request.path_params.get(owner_id_param) or request.query_params.get(owner_id_param)
        
        if not target_owner_id:
            # Fallback check of custom headers if parameter is not in URL
            target_owner_id = request.headers.get(f"X-{owner_id_param.replace('_', '-')}")

        if not target_owner_id:
            # If not specified anywhere, allow passing (cannot enforce if parameter not found)
            return

        # Perform ownership match
        if str(current_user.id) != str(target_owner_id):
            logger.error(
                f"🚨 Anti-IDOR Violation: User {current_user.email} (ID: {current_user.id}) "
                f"tried to access/modify resources owned by User ID {target_owner_id} "
                f"on path {request.url.path}. IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ запрещен. Несовпадение идентификатора владельца."
            )

    return dependency
