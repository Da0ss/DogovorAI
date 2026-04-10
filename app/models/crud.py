"""
CRUD operations for users and verification codes
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
import secrets

from app.models.models import User, VerificationCode
from app.models.schemas import UserCreate, VerificationRequest

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        bool: True if password matches
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password

    Args:
        password: Plain text password

    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def generate_verification_code() -> str:
    """
    Generate a 6-digit verification code

    Returns:
        str: 6-digit code
    """
    return "".join(secrets.choice("0123456789") for _ in range(6))


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Get user by email

    Args:
        db: Database session
        email: User email

    Returns:
        Optional[User]: User object or None
    """
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user: UserCreate) -> User:
    """
    Create a new user

    Args:
        db: Database session
        user: User creation data

    Returns:
        User: Created user

    Raises:
        ValueError: If user already exists
    """
    # Check if user already exists
    db_user = get_user_by_email(db, user.email)
    if db_user:
        raise ValueError("User with this email already exists")

    # Hash password
    hashed_password = get_password_hash(user.password)

    # Create user
    db_user = User(
        email=user.email,
        hashed_password=hashed_password,
        is_verified=False
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"✅ User created: {user.email}")
        return db_user
    except IntegrityError:
        db.rollback()
        raise ValueError("User with this email already exists")


def create_verification_code(db: Session, user_id: int) -> VerificationCode:
    """
    Create a verification code for user

    Args:
        db: Database session
        user_id: User ID

    Returns:
        VerificationCode: Created verification code
    """
    # Generate code and expiration time (10 minutes)
    code = generate_verification_code()
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Create verification code
    verification_code = VerificationCode(
        user_id=user_id,
        code=code,
        expires_at=expires_at
    )

    db.add(verification_code)
    db.commit()
    db.refresh(verification_code)

    # Log code (in production, this would be sent via email)
    logger.info(f"📧 Verification code for user {user_id}: {code}")

    return verification_code


def verify_user_code(db: Session, verification: VerificationRequest) -> Optional[User]:
    """
    Verify user email with code

    Args:
        db: Database session
        verification: Verification request data

    Returns:
        Optional[User]: Verified user or None if verification failed
    """
    # Get user
    user = get_user_by_email(db, verification.email)
    if not user:
        return None

    # Get latest verification code for user
    verification_code = (
        db.query(VerificationCode)
        .filter(
            VerificationCode.user_id == user.id,
            VerificationCode.code == verification.code,
            VerificationCode.expires_at > datetime.utcnow()
        )
        .order_by(VerificationCode.expires_at.desc())
        .first()
    )

    if not verification_code:
        return None

    # Mark user as verified
    user.is_verified = True
    db.commit()
    db.refresh(user)

    # Delete used verification code
    db.delete(verification_code)
    db.commit()

    logger.info(f"✅ User verified: {user.email}")
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate user with email and password

    Args:
        db: Database session
        email: User email
        password: User password

    Returns:
        Optional[User]: Authenticated user or None
    """
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user