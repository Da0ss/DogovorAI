"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime


class UserCreate(BaseModel):
    """
    Schema for user registration request
    """
    email: EmailStr
    password: str


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