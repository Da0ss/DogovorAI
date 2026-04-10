"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, EmailStr
from typing import Optional
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
    id: int
    email: EmailStr
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


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