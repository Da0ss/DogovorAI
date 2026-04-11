"""
Authentication API endpoints using Supabase Auth
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.auth_service import get_auth_service
from app.models.schemas import LoginRequest, LoginResponse, UserCreate, UserResponse, VerificationRequest, VerificationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Auth dependencies
def get_current_user(request: Request) -> dict:
    """
    Get current authenticated user from JWT token

    Args:
        request: FastAPI request object

    Returns:
        dict: User data

    Raises:
        HTTPException: If user is not authenticated
    """
    # For local testing, check localStorage via headers
    # In production, this would validate JWT tokens
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    # For local mode, we accept any token
    token = auth_header.split(' ')[1]
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    # Mock user data - in production, decode JWT
    return {
        "id": "user-123",
        "email": "user@example.com",
        "is_verified": True
    }


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    auth_service = Depends(get_auth_service)
) -> UserResponse:
    """
    Register a new user via Supabase Auth

    Creates user account and sends verification code via email/SMS

    Args:
        user_data: User registration data
        auth_service: Supabase Auth service

    Returns:
        UserResponse: Created user data

    Raises:
        HTTPException: If user already exists or registration fails
    """
    from fastapi.concurrency import run_in_threadpool
    try:
        response = await run_in_threadpool(auth_service.register_user, user_data.email, user_data.password)

        # Extract user data from Supabase response (dict or object)
        if hasattr(response, 'user'):
            user_info = response.user
        else:
            user_info = response.get('user')

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed - no user data returned"
            )

        return UserResponse(
            id=user_info.get('id') if isinstance(user_info, dict) else user_info.id,
            email=user_info.get('email') if isinstance(user_info, dict) else user_info.email,
            is_verified=getattr(user_info, 'email_confirmed_at', None) is not None,
            created_at=getattr(user_info, 'created_at', None)
        )

    except Exception as e:
        logger.error(f"❌ Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/verify", response_model=VerificationResponse)
async def verify_email(
    verification_data: VerificationRequest,
    auth_service = Depends(get_auth_service)
) -> VerificationResponse:
    """
    Verify user email with verification code via Supabase Auth

    Args:
        verification_data: Email and verification code
        auth_service: Supabase Auth service

    Returns:
        VerificationResponse: Verification result

    Raises:
        HTTPException: If verification fails
    """
    from fastapi.concurrency import run_in_threadpool
    try:
        response = await run_in_threadpool(auth_service.verify_email, verification_data.email, verification_data.code)

        # Extract user data from Supabase response (dict or object)
        if hasattr(response, 'user'):
            user_info = response.user
        else:
            user_info = response.get('user')

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code or code expired"
            )

        return VerificationResponse(
            success=True,
            message="Email verified successfully",
            user=UserResponse(
                id=user_info.get('id') if isinstance(user_info, dict) else user_info.id,
                email=user_info.get('email') if isinstance(user_info, dict) else user_info.email,
                is_verified=getattr(user_info, 'email_confirmed_at', None) is not None,
                created_at=getattr(user_info, 'created_at', None)
            )
        )

    except Exception as e:
        logger.error(f"❌ Verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Verification failed: {str(e)}"
        )


@router.post("/login", response_model=LoginResponse)
async def login_user(
    login_data: LoginRequest,
    auth_service = Depends(get_auth_service)
) -> LoginResponse:
    """
    Authenticate user with email and password via Supabase Auth.

    Args:
        login_data: Login request data
        auth_service: Supabase Auth service

    Returns:
        LoginResponse: Authentication result
    """
    from fastapi.concurrency import run_in_threadpool
    try:
        response = await run_in_threadpool(auth_service.login_user, login_data.email, login_data.password)

        # Extract user data from Supabase response (dict or object)
        if hasattr(response, 'user'):
            user_info = response.user
        else:
            user_info = response.get('user')

        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль"
            )

        return LoginResponse(
            success=True,
            message="Успешный вход",
            user=UserResponse(
                id=user_info.get('id') if isinstance(user_info, dict) else user_info.id,
                email=user_info.get('email') if isinstance(user_info, dict) else user_info.email,
                is_verified=getattr(user_info, 'email_confirmed_at', None) is not None,
                created_at=getattr(user_info, 'created_at', None)
            ),
            session=response.get('session') if isinstance(response, dict) else getattr(response, 'session', None)
        )

    except Exception as e:
        logger.error(f"❌ Login failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Неверный email или пароль: {str(e)}"
        )


@router.get("/test-code/{email}")
async def get_test_verification_code(email: str) -> dict:
    """
    Get verification code for testing (local mode only)

    Args:
        email: User email

    Returns:
        dict: Verification code info
    """
    try:
        from app.services.verification_service import get_verification_service
        service = get_verification_service()

        if email in service.codes:
            code_data = service.codes[email]
            return {
                "email": email,
                "code": code_data.code,
                "expires_at": code_data.expires_at,
                "used": code_data.used
            }
        else:
            return {"error": "No code found for this email"}

    except Exception as e:
        return {"error": str(e)}


@router.post("/resend-code")
async def resend_verification_code(
    email: str,
    auth_service = Depends(get_auth_service)
) -> dict:
    """
    Resend verification code to user email via Supabase Auth

    Args:
        email: User email
        auth_service: Supabase Auth service

    Returns:
        dict: Success message

    Raises:
        HTTPException: If resend fails
    """
    from fastapi.concurrency import run_in_threadpool
    try:
        await run_in_threadpool(auth_service.resend_verification_code, email)
        return {"message": "Verification code sent successfully"}

    except Exception as e:
        logger.error(f"❌ Resend code failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resend verification code: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)) -> UserResponse:
    """
    Get current authenticated user information

    Returns:
        UserResponse: Current user data

    Raises:
        HTTPException: If user is not authenticated
    """
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        is_verified=current_user["is_verified"],
        created_at=None
    )