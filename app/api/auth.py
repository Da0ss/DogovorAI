"""
Authentication API endpoints for user registration and verification
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.crud import create_user, create_verification_code, verify_user_code
from app.models.schemas import UserCreate, UserResponse, VerificationRequest, VerificationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Register a new user

    Creates user account and sends verification code via email (simulated)

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        UserResponse: Created user data

    Raises:
        HTTPException: If user already exists or registration fails
    """
    try:
        # Create user
        user = create_user(db, user_data)

        # Create verification code
        verification_code = create_verification_code(db, user.id)

        # In production, send email here
        logger.info(f"📧 Verification code sent to {user.email}: {verification_code.code}")

        return UserResponse.from_orm(user)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/verify", response_model=VerificationResponse)
async def verify_email(
    verification_data: VerificationRequest,
    db: Session = Depends(get_db)
) -> VerificationResponse:
    """
    Verify user email with verification code

    Args:
        verification_data: Email and verification code
        db: Database session

    Returns:
        VerificationResponse: Verification result

    Raises:
        HTTPException: If verification fails
    """
    try:
        user = verify_user_code(db, verification_data)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code or code expired"
            )

        return VerificationResponse(
            success=True,
            message="Email verified successfully",
            user=UserResponse.from_orm(user)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed"
        )


@router.post("/resend-code")
async def resend_verification_code(
    email: str,
    db: Session = Depends(get_db)
) -> dict:
    """
    Resend verification code to user email

    Args:
        email: User email
        db: Database session

    Returns:
        dict: Success message

    Raises:
        HTTPException: If user not found or already verified
    """
    from app.models.crud import get_user_by_email

    try:
        user = get_user_by_email(db, email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already verified"
            )

        # Create new verification code
        verification_code = create_verification_code(db, user.id)

        # In production, send email here
        logger.info(f"📧 New verification code sent to {user.email}: {verification_code.code}")

        return {"message": "Verification code sent successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Resend code failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend verification code"
        )