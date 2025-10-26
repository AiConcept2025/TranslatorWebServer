"""
Authentication models for user signup and login.

These models are specifically for the users_login collection
and provide basic username/email/password authentication.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
import re


class UserSignupRequest(BaseModel):
    """Request model for user signup."""
    user_name: str = Field(..., min_length=1, max_length=100, description="Username")
    user_email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, max_length=128, description="User password")

    @validator('user_name')
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        if len(v.strip()) < 1:
            raise ValueError("Username must be at least 1 character")
        if len(v.strip()) > 100:
            raise ValueError("Username cannot exceed 100 characters")
        return v.strip()

    @validator('user_email')
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        # Additional email validation
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        if not email_pattern.match(v):
            raise ValueError("Invalid email format")
        return v.lower().strip()

    @validator('password')
    def validate_password(cls, v):
        if not v or len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if len(v) > 128:
            raise ValueError("Password cannot exceed 128 characters")
        # Check for at least one letter and one number for basic security
        if not re.search(r'[A-Za-z]', v) or not re.search(r'\d', v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class UserSignupResponse(BaseModel):
    """Response model for user signup."""
    success: bool
    message: str
    user: Optional[dict] = None


class UserLoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")

    @validator('email')
    def validate_email(cls, v):
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        return v.lower().strip()

    @validator('password')
    def validate_password(cls, v):
        if not v:
            raise ValueError("Password cannot be empty")
        return v


class UserLoginResponse(BaseModel):
    """Response model for user login."""
    success: bool
    message: str
    user: Optional[dict] = None


# Export all models
__all__ = [
    "UserSignupRequest",
    "UserSignupResponse",
    "UserLoginRequest",
    "UserLoginResponse"
]
