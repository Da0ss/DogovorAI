"""
Authentication API endpoints using Supabase Auth.
"""

import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import crud
from app.models.schemas import LoginRequest, LoginResponse, UserCreate, UserResponse, VerificationRequest, VerificationResponse
from app.services.auth_context import (
    ensure_local_profile,
    extract_bearer_token,
    is_debug_or_test,
    require_admin_user as require_admin_user_context,
    resolve_authenticated_user,
)
from app.services.auth_service import auth_service as supabase_auth_service
from config.settings import settings as app_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

RECAPTCHA_VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def verify_recaptcha(token: str | None) -> None:
    """Verify a reCAPTCHA v2 token with Google.

    Skips verification if RECAPTCHA_SECRET_KEY is not configured (dev mode).
    Raises HTTPException on failure.
    """
    if is_debug_or_test():
        return

    secret = app_settings.recaptcha_secret_key
    if not secret:
        # reCAPTCHA not configured — skip (dev/local)
        return

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пожалуйста, пройдите проверку reCAPTCHA."
        )

    try:
        resp = httpx.post(RECAPTCHA_VERIFY_URL, data={
            "secret": secret,
            "response": token,
        }, timeout=5.0)
        result = resp.json()
    except Exception as e:
        logger.error(f"❌ reCAPTCHA verification request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось проверить reCAPTCHA. Попробуйте позже."
        )

    if not result.get("success"):
        logger.warning(f"⚠️ reCAPTCHA failed: {result.get('error-codes', [])}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Проверка reCAPTCHA не пройдена. Попробуйте снова."
        )


def _get_response_value(obj, key: str, default=None):
    """Read a value from a dict or Supabase response object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _normalize_auth_response(response) -> tuple[dict, dict | None]:
    """Normalize Supabase auth responses to plain user/session dicts."""
    user_obj = _get_response_value(response, "user")
    session_obj = _get_response_value(response, "session")

    if not user_obj:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Authentication provider did not return a user",
        )

    metadata = _get_response_value(user_obj, "user_metadata", {}) or {}
    user_data = {
        "id": str(_get_response_value(user_obj, "id", "")),
        "email": _get_response_value(user_obj, "email"),
        "full_name": metadata.get("full_name") or metadata.get("name"),
        "avatar_url": metadata.get("avatar_url") or metadata.get("picture"),
        "is_verified": bool(
            _get_response_value(user_obj, "email_confirmed_at")
            or _get_response_value(user_obj, "confirmed_at")
            or _get_response_value(user_obj, "is_verified", False)
        ),
    }

    session_data = None
    if session_obj:
        session_data = {
            "access_token": _get_response_value(session_obj, "access_token"),
            "refresh_token": _get_response_value(session_obj, "refresh_token"),
            "expires_in": _get_response_value(session_obj, "expires_in"),
            "token_type": _get_response_value(session_obj, "token_type", "bearer"),
        }
        session_data = {k: v for k, v in session_data.items() if v is not None}

    return user_data, session_data


def _user_response_from_profile(db: Session, profile: dict, provider: str, consent_accepted: bool = False) -> UserResponse:
    user = ensure_local_profile(
        db,
        user_id=profile.get("id") or None,
        email=profile["email"],
        is_verified=bool(profile.get("is_verified", False)),
        auth_provider=provider,
        full_name=profile.get("full_name"),
        avatar_url=profile.get("avatar_url"),
        consent_accepted=consent_accepted,
    )
    return UserResponse(
        id=str(user.id),
        email=user.email,
        is_verified=bool(user.is_verified),
        created_at=user.created_at,
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> dict:
    """Get the current authenticated user."""
    return resolve_authenticated_user(request, db)


def require_admin_user(request: Request, db: Session = Depends(get_db)) -> dict:
    """FastAPI dependency for admin-only endpoints."""
    return require_admin_user_context(request, db)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> UserResponse:
    """Register a new user via Supabase Auth or log in if already registered."""
    if not user_data.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы должны согласиться с Условиями использования, чтобы продолжить."
        )

    # Server-side reCAPTCHA validation
    verify_recaptcha(user_data.recaptcha_token)

    # Check if user already exists
    existing_user = crud.get_user_by_email(db, user_data.email)
    if existing_user:
        logger.info(f"🔄 User {user_data.email} already exists. Attempting auto-login...")
        try:
            # Try logging in with the provided password
            response = supabase_auth_service.login_user(user_data.email, user_data.password)
            profile, session_data = _normalize_auth_response(response)
            user = _user_response_from_profile(db, profile, provider="supabase")
            
            return UserResponse(
                id=user.id,
                email=user.email,
                is_verified=user.is_verified,
                created_at=user.created_at,
                session=session_data
            )
        except Exception as login_err:
            logger.warning(f"⚠️ Auto-login failed for existing user {user_data.email}: {str(login_err)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже зарегистрирован. Введен неверный пароль."
            )

    try:
        response = supabase_auth_service.register_user(user_data.email, user_data.password)
        profile, _ = _normalize_auth_response(response)
        return _user_response_from_profile(db, profile, provider="supabase", consent_accepted=True)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Registration failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration failed")


@router.post("/verify", response_model=VerificationResponse)
def verify_email(
    verification_data: VerificationRequest,
    db: Session = Depends(get_db)
) -> VerificationResponse:
    """Verify user email with Supabase verification code."""
    try:
        response = supabase_auth_service.verify_email(
            verification_data.email,
            verification_data.code,
        )
        profile, _ = _normalize_auth_response(response)
        user = _user_response_from_profile(db, profile, provider="supabase")

        return VerificationResponse(
            success=True,
            message="Email verified successfully",
            user=user,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Verification failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code or code expired")


@router.post("/login", response_model=LoginResponse)
def login_user(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> LoginResponse:
    """Authenticate user with email and password via Supabase Auth."""
    try:
        response = supabase_auth_service.login_user(login_data.email, login_data.password)
        profile, session_data = _normalize_auth_response(response)
        user = _user_response_from_profile(db, profile, provider="supabase")

        return LoginResponse(
            success=True,
            message="Успешный вход",
            user=user,
            session=session_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный email или пароль")


@router.get("/test-code/{email}")
def get_test_verification_code(email: str, db: Session = Depends(get_db)) -> dict:
    """Get verification code for local tests only."""
    if not is_debug_or_test():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    user = crud.get_user_by_email(db, email)
    if not user:
        return {"error": "User not found"}
        
    code_obj = db.query(crud.VerificationCode).filter(
        crud.VerificationCode.user_id == user.id
    ).order_by(crud.VerificationCode.expires_at.desc()).first()
    
    if code_obj:
        return {
            "email": email,
            "code": code_obj.code,
            "expires_at": code_obj.expires_at
        }
    return {"error": "No code found for this email"}


@router.post("/resend-code")
def resend_verification_code(
    email: str,
) -> dict:
    """Resend verification code via Supabase Auth."""
    try:
        supabase_auth_service.resend_verification_code(email)
        return {"message": "If email exists, verification code was sent"}

    except Exception as e:
        logger.error(f"❌ Resend code failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to resend verification code")


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        is_verified=current_user["is_verified"],
        created_at=None
    )


# ================================================================
# Passwordless OTP Login Endpoints
# ================================================================

from app.models.schemas import OTPLoginRequest, OTPVerifyRequest


@router.post("/otp/send")
def send_otp_code(request: OTPLoginRequest):
    """
    Send OTP code to email for passwordless login.
    """
    try:
        from app.services.auth_service import auth_service as auth_svc
        
        auth_svc.send_login_otp(request.email)
        return {"success": True, "message": "Если email корректен, вы получите код на почту"}
        
    except Exception as e:
        logger.error(f"❌ OTP send failed: {str(e)}")
        # We don't expose internal errors to the client for security, just generic message
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось отправить код. Попробуйте позже."
        )


@router.post("/otp/verify", response_model=LoginResponse)
def verify_otp_code(request: OTPVerifyRequest, db: Session = Depends(get_db)):
    """
    Verify OTP code and login user.
    """
    try:
        from app.services.auth_service import auth_service as auth_svc
        
        result = auth_svc.verify_login_otp(request.email, request.code)
        
        if not result or not result.get("user") or not result.get("session"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неправильный код. Попробуйте снова."
            )
            
        user_data = result.get("user", {})
        session_data = result.get("session", {})
        user = _user_response_from_profile(db, user_data, provider="supabase")

        return LoginResponse(
            success=True,
            message="Успешный вход",
            user=user,
            session=session_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ OTP verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или просроченный код"
        )


# ================================================================
# Google OAuth Endpoints
# ================================================================

from app.services.auth_service import auth_service as google_auth_service
from app.models.schemas import GoogleAuthURL, OAuthCallbackResponse, UserProfile
from config.settings import settings


@router.get("/google", response_model=GoogleAuthURL)
def google_auth_initiate(consent: bool = False):
    """
    Initiate Google OAuth flow.
    Returns a URL to redirect the user to Google's consent screen.
    The optional consent param is passed from the registration page;
    login page does not send it (user already accepted terms).
    """
    try:
        redirect_to = settings.google_redirect_uri
        response = google_auth_service.sign_in_with_google(redirect_to)

        # Supabase returns an object with url attribute
        oauth_url = None
        code_verifier = None
        if isinstance(response, dict):
            oauth_url = response.get('url')
            code_verifier = response.get('code_verifier')
        elif hasattr(response, 'url'):
            oauth_url = response.url

        if not oauth_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate Google OAuth URL"
            )

        return GoogleAuthURL(url=oauth_url, code_verifier=code_verifier)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Google OAuth initiation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google OAuth error: {str(e)}"
        )


@router.get("/google/callback", response_model=OAuthCallbackResponse)
def google_auth_callback(code: str = None, code_verifier: str = None, error: str = None, db: Session = Depends(get_db)):
    """
    Handle Google OAuth callback.
    Exchanges the authorization code for a Supabase session.
    """
    if error:
        logger.warning(f"⚠️ Google OAuth error: {error}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Google authentication failed: {error}"
        )

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No authorization code received"
        )

    try:
        result = google_auth_service.exchange_code_for_session(code, code_verifier)
        user_data = result.get("user") or {}
        if user_data.get("email"):
            _user_response_from_profile(db, user_data, provider="supabase", consent_accepted=True)

        return OAuthCallbackResponse(
            success=True,
            message="Authentication successful",
            user=result.get("user"),
            session=result.get("session")
        )

    except Exception as e:
        logger.error(f"❌ Google OAuth callback failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete authentication: {str(e)}"
        )


@router.post("/logout")
def logout_user(request: Request):
    """
    Logout user by invalidating their session.
    Clears the Supabase session on the server side.
    """
    token = extract_bearer_token(request)
    if token:
        try:
            google_auth_service.sign_out(token)
        except Exception as e:
            logger.warning(f"⚠️ Server-side logout error: {str(e)}")

    return {"success": True, "message": "Logged out successfully"}


@router.get("/me/profile", response_model=UserProfile)
def get_user_profile(request: Request, db: Session = Depends(get_db)):
    """
    Get extended user profile (with Google data: name, avatar).
    Works with both local tokens and Supabase JWT tokens.
    """
    current_user = resolve_authenticated_user(request, db)
    user_obj = crud.get_user_by_id(db, current_user["id"])
    profile = current_user.get("profile") or {}
    if not user_obj:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    return UserProfile(
        id=str(user_obj.id),
        email=user_obj.email,
        full_name=profile.get("full_name") or getattr(user_obj, "full_name", None),
        avatar_url=profile.get("avatar_url") or getattr(user_obj, "avatar_url", None),
        is_verified=bool(user_obj.is_verified or profile.get("is_verified", False)),
        created_at=user_obj.created_at,
        plan=getattr(user_obj, "plan_type", "basic") or "basic",
        analyses_used=getattr(user_obj, "analyses_used", 0) or 0,
        subscription_status=getattr(user_obj, "subscription_status", "inactive") or "inactive",
    )


@router.get("/users")
def get_all_users(
    db: Session = Depends(get_db),
    _admin_user: dict = Depends(require_admin_user),
) -> list:
    """
    Return all users from profiles table for the metrics dashboard.
    Requires an admin Supabase user listed in ADMIN_EMAILS.
    """
    users = db.query(crud.User).order_by(crud.User.created_at.desc()).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "is_verified": u.is_verified,
            "plan": getattr(u, "plan_type", "basic") or "basic",
            "plan_type": getattr(u, "plan_type", "basic") or "basic",
            "analyses_used": getattr(u, "analyses_used", 0) or 0,
            "subscription_status": getattr(u, "subscription_status", "inactive") or "inactive",
            "auth_provider": getattr(u, "auth_provider", "local") or "local",
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]
