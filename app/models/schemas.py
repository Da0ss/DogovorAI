"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime


class UserCreate(BaseModel):
    """
    Schema for user registration request
    """
    email: EmailStr
    password: str
    consent: bool = Field(True, description="Consent to Terms of Service and Privacy Policy")


class UserResponse(BaseModel):
    """
    Schema for user response (without sensitive data)
    """
    id: str
    email: EmailStr
    is_verified: bool
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class VerificationRequest(BaseModel):
    """
    Schema for email verification request
    """
    email: EmailStr
    code: str


class VerificationResponse(BaseModel):
    """
    Schema for verification response
    """
    success: bool
    message: str
    user: Optional[UserResponse] = None


class LoginRequest(BaseModel):
    """
    Schema for login request
    """
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """
    Schema for login response
    """
    success: bool
    message: str
    user: Optional[UserResponse] = None
    session: Optional[Dict[str, Any]] = None


class Token(BaseModel):
    """
    Schema for authentication token (future use)
    """
    access_token: str
    token_type: str


class TokenData(BaseModel):
    """
    Schema for token payload data
    """
    email: Optional[str] = None


class GoogleAuthURL(BaseModel):
    """
    Schema for Google OAuth redirect URL response
    """
    url: str
    message: str = "Redirect to Google for authentication"


class OAuthCallbackResponse(BaseModel):
    """
    Schema for OAuth callback response after successful authentication
    """
    success: bool
    message: str
    user: Optional[Dict[str, Any]] = None
    session: Optional[Dict[str, Any]] = None


class UserProfile(BaseModel):
    """
    Extended user profile with Google account data and subscription info
    """
    id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool = True
    created_at: Optional[datetime] = None
    plan: str = "basic"
    analyses_used: int = 0
    subscription_status: str = "inactive"

    model_config = ConfigDict(from_attributes=True)


class OTPLoginRequest(BaseModel):
    """
    Schema for OTP login request
    """
    email: EmailStr


class OTPVerifyRequest(BaseModel):
    """
    Schema for OTP verification request
    """
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)