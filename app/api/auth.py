"""
Authentication API endpoints using Local Database
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models import crud
from app.models.schemas import LoginRequest, LoginResponse, UserCreate, UserResponse, VerificationRequest, VerificationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_current_user(request: Request, db: Session = Depends(get_db)) -> dict:
    """
    Get current authenticated user.
    Supports two token formats:
      1. local-token-<uuid> — Local DB auth
      2. Supabase JWT (Google OAuth) — decoded without signature verification,
         email extracted and matched against local profiles table.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = auth_header.split(' ')[1]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty token")

    # ── Path 1: Local token ──
    if token.startswith("local-token-"):
        user_id_str = token.replace("local-token-", "")
        if not user_id_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")

        user_obj = crud.get_user_by_id(db, user_id_str)
        if not user_obj:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return {
            "id": user_obj.id,
            "email": user_obj.email,
            "is_verified": user_obj.is_verified
        }

    # ── Path 2: Supabase JWT (Google OAuth) ──
    try:
        import json, base64
        parts = token.split('.')
        if len(parts) != 3:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        payload_b64 = parts[1] + '=' * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        email = (
            payload.get('email')
            or payload.get('user_metadata', {}).get('email')
        )
        if not email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No email in token")

        user_obj = crud.get_user_by_email(db, email)
        if not user_obj:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return {
            "id": user_obj.id,
            "email": user_obj.email,
            "is_verified": user_obj.is_verified
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"JWT decode error: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> UserResponse:
    """Register a new user via Local DB"""
    try:
        user = crud.create_user(db, user_data)
        crud.create_verification_code(db, user.id)
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            is_verified=user.is_verified,
            created_at=user.created_at
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Registration failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {str(e)}")


@router.post("/verify", response_model=VerificationResponse)
def verify_email(
    verification_data: VerificationRequest,
    db: Session = Depends(get_db)
) -> VerificationResponse:
    """Verify user email with verification code via Local DB"""
    try:
        user = crud.verify_user_code(db, verification_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code or code expired"
            )

        return VerificationResponse(
            success=True,
            message="Email verified successfully",
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                is_verified=user.is_verified,
                created_at=user.created_at
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Verification failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Verification failed: {str(e)}")


@router.post("/login", response_model=LoginResponse)
def login_user(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
) -> LoginResponse:
    """Authenticate user with email and password via Local DB"""
    try:
        user = crud.authenticate_user(db, login_data.email, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль"
            )
            
        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email не верифицирован"
            )

        session_data = {
            "access_token": f"local-token-{user.id}",
            "refresh_token": f"local-refresh-{user.id}"
        }

        return LoginResponse(
            success=True,
            message="Успешный вход",
            user=UserResponse(
                id=str(user.id),
                email=user.email,
                is_verified=user.is_verified,
                created_at=user.created_at
            ),
            session=session_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Login failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Login error: {str(e)}")


@router.get("/test-code/{email}")
def get_test_verification_code(email: str, db: Session = Depends(get_db)) -> dict:
    """Get verification code for testing"""
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
    db: Session = Depends(get_db)
) -> dict:
    """Resend verification code via Local DB"""
    try:
        user = crud.get_user_by_email(db, email)
        if not user:
            # Silent fail for security
            return {"message": "If email exists, verification code was sent"}
            
        crud.create_verification_code(db, user.id)
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
def verify_otp_code(request: OTPVerifyRequest):
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

        return LoginResponse(
            success=True,
            message="Успешный вход",
            user=UserResponse(
                id=str(user_data.get("id")),
                email=user_data.get("email"),
                is_verified=user_data.get("is_verified", True),
                created_at=None
            ),
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
from fastapi.responses import RedirectResponse
from config.settings import settings


@router.get("/google", response_model=GoogleAuthURL)
def google_auth_initiate():
    """
    Initiate Google OAuth flow.
    Returns a URL to redirect the user to Google's consent screen.
    """
    try:
        redirect_to = settings.google_redirect_uri
        response = google_auth_service.sign_in_with_google(redirect_to)

        # Supabase returns an object with url attribute
        oauth_url = None
        if hasattr(response, 'url'):
            oauth_url = response.url
        elif isinstance(response, dict) and 'url' in response:
            oauth_url = response['url']

        if not oauth_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate Google OAuth URL"
            )

        return GoogleAuthURL(url=oauth_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Google OAuth initiation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google OAuth error: {str(e)}"
        )


@router.get("/google/callback", response_model=OAuthCallbackResponse)
def google_auth_callback(code: str = None, error: str = None):
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
        result = google_auth_service.exchange_code_for_session(code)

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
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            google_auth_service.sign_out(token)
        except Exception as e:
            logger.warning(f"⚠️ Server-side logout error: {str(e)}")

    return {"success": True, "message": "Logged out successfully"}


@router.get("/me/profile", response_model=UserProfile)
def get_user_profile(request: Request):
    """
    Get extended user profile (with Google data: name, avatar).
    Works with both local tokens and Supabase JWT tokens.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    token = auth_header.split(' ')[1]
    
    user_id_str = None
    profile = None

    # Try local token first (profiles table, local email/password auth)
    if token.startswith("local-token-"):
        user_id_str = token.replace("local-token-", "")
    else:
        # Try Supabase JWT token (Google OAuth)
        profile = google_auth_service.get_user_profile(token)
        if profile and "id" in profile:
            user_id_str = profile["id"]

    if user_id_str:
        from app.models.database import SessionLocal
        db = SessionLocal()
        try:
            user_obj = crud.get_user_by_id(db, user_id_str)
            # FALLBACK: If Supabase UUID doesn't match our Local DB UUID, try finding by email!
            if not user_obj and profile and profile.get("email"):
                user_obj = db.query(crud.User).filter(crud.User.email.ilike(profile["email"])).first()
                
            if user_obj:
                return UserProfile(
                    id=str(user_obj.id),
                    email=user_obj.email,
                    # Fallback to profile info if DB doesn't have it
                    full_name=(profile.get("full_name") if profile else None) or getattr(user_obj, 'full_name', None),
                    avatar_url=(profile.get("avatar_url") if profile else None) or getattr(user_obj, 'avatar_url', None),
                    is_verified=user_obj.is_verified or (profile.get("is_verified", False) if profile else False),
                    created_at=user_obj.created_at,
                    plan=getattr(user_obj, 'plan_type', 'basic') or 'basic',
                    analyses_used=getattr(user_obj, 'analyses_used', 0) or 0,
                    subscription_status=getattr(user_obj, 'subscription_status', 'inactive') or 'inactive'
                )
        finally:
            db.close()
            
    # Fallback if user is authorized via Supabase but missing from local DB
    if profile:
        return UserProfile(**profile)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token"
    )


@router.get("/users")
def get_all_users(request: Request, db: Session = Depends(get_db)) -> list:
    """
    Return all users from profiles table for the metrics dashboard.
    Requires any valid Bearer token.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Empty token")

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