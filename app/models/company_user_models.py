"""
Company User API models for creating and managing company users.

These models are for the Company User management API endpoints
and provide validation for user creation and response formatting.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import datetime
from app.mongodb_models import PermissionLevel, UserStatus
import re


class CompanyUserCreate(BaseModel):
    """
    Request model for creating a company user.

    The password will be hashed before storage and never stored in plain text.
    """
    user_name: str = Field(..., max_length=255, description="User's full name")
    email: EmailStr = Field(..., description="User's email address")
    phone_number: Optional[str] = Field(None, max_length=50, description="User's phone number")
    password: str = Field(..., min_length=6, max_length=128, description="User password (will be hashed)")
    permission_level: PermissionLevel = Field(
        default=PermissionLevel.USER,
        description="User's permission level (admin or user)"
    )
    status: UserStatus = Field(
        default=UserStatus.ACTIVE,
        description="User's account status (active, inactive, suspended)"
    )

    @validator('user_name')
    def validate_user_name(cls, v):
        """Validate user name is not empty and within length limits."""
        if not v or not v.strip():
            raise ValueError("User name cannot be empty")
        if len(v.strip()) > 255:
            raise ValueError("User name cannot exceed 255 characters")
        return v.strip()

    @validator('email')
    def validate_email(cls, v):
        """Validate and normalize email address."""
        if not v or not v.strip():
            raise ValueError("Email cannot be empty")
        return v.lower().strip()

    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number length if provided."""
        if v is not None:
            if len(v.strip()) > 50:
                raise ValueError("Phone number cannot exceed 50 characters")
            return v.strip() if v.strip() else None
        return v

    @validator('password')
    def validate_password(cls, v):
        """
        Validate password strength requirements.

        Rules:
        - Minimum 6 characters
        - Maximum 128 characters
        - Must contain at least one letter (A-Z, a-z)
        - Must contain at least one number (0-9)
        """
        if not v or len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if len(v) > 128:
            raise ValueError("Password cannot exceed 128 characters")
        # Check for at least one letter and one number for basic security
        if not re.search(r'[A-Za-z]', v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r'\d', v):
            raise ValueError("Password must contain at least one number")
        return v

    class Config:
        """Pydantic configuration with example."""
        json_schema_extra = {
            "example": {
                "user_name": "John Doe",
                "email": "john.doe@company.com",
                "phone_number": "+1-555-0123",
                "password": "SecurePass123",
                "permission_level": "user",
                "status": "active"
            }
        }


class CompanyUserUpdate(BaseModel):
    """
    Request model for updating a company user (partial update).

    All fields are optional - only provided fields will be updated.
    """
    user_name: Optional[str] = Field(None, max_length=255, description="User's full name")
    email: Optional[EmailStr] = Field(None, description="User's email address")
    phone_number: Optional[str] = Field(None, max_length=50, description="User's phone number")
    password: Optional[str] = Field(None, min_length=6, max_length=128, description="New password (will be hashed)")
    permission_level: Optional[PermissionLevel] = Field(None, description="User's permission level")
    status: Optional[UserStatus] = Field(None, description="User's account status")

    @validator('user_name')
    def validate_user_name(cls, v):
        """Validate user name if provided."""
        if v is not None:
            if not v.strip():
                raise ValueError("User name cannot be empty")
            if len(v.strip()) > 255:
                raise ValueError("User name cannot exceed 255 characters")
            return v.strip()
        return v

    @validator('email')
    def validate_email(cls, v):
        """Validate and normalize email if provided."""
        if v is not None:
            if not v.strip():
                raise ValueError("Email cannot be empty")
            return v.lower().strip()
        return v

    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Validate phone number if provided."""
        if v is not None:
            if len(v.strip()) > 50:
                raise ValueError("Phone number cannot exceed 50 characters")
            return v.strip() if v.strip() else None
        return v

    @validator('password')
    def validate_password(cls, v):
        """Validate password strength if provided."""
        if v is not None:
            if len(v) < 6:
                raise ValueError("Password must be at least 6 characters")
            if len(v) > 128:
                raise ValueError("Password cannot exceed 128 characters")
            if not re.search(r'[A-Za-z]', v):
                raise ValueError("Password must contain at least one letter")
            if not re.search(r'\d', v):
                raise ValueError("Password must contain at least one number")
            return v
        return v

    class Config:
        """Pydantic configuration with example."""
        json_schema_extra = {
            "example": {
                "user_name": "Jane Doe",
                "email": "jane.doe@company.com",
                "phone_number": "+1-555-9999",
                "permission_level": "admin",
                "status": "active"
            }
        }


class CompanyUserResponse(BaseModel):
    """
    Response model for company user data.

    This model excludes sensitive information like password_hash
    and includes company_name for convenience (added by endpoint).
    """
    user_id: str = Field(..., description="Unique user identifier")
    company_name: str = Field(..., description="Company name (added by endpoint)")
    user_name: str = Field(..., description="User's full name")
    email: str = Field(..., description="User's email address")
    phone_number: Optional[str] = Field(None, description="User's phone number")
    permission_level: str = Field(..., description="User's permission level")
    status: str = Field(..., description="User's account status")
    created_at: datetime = Field(..., description="Account creation timestamp")

    class Config:
        """Pydantic configuration with example."""
        json_schema_extra = {
            "example": {
                "user_id": "user_abc123",
                "company_name": "Acme Corporation",
                "user_name": "John Doe",
                "email": "john.doe@company.com",
                "phone_number": "+1-555-0123",
                "permission_level": "user",
                "status": "active",
                "created_at": "2025-01-15T10:30:00Z"
            }
        }


# Export all models
__all__ = [
    "CompanyUserCreate",
    "CompanyUserUpdate",
    "CompanyUserResponse"
]
