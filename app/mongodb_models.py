"""
MongoDB Pydantic Models for Translation Software
Based on translation-schema.js

IMPORTANT: These are MongoDB-specific models, separate from existing API models.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator
from datetime import datetime, timezone
from enum import Enum
from bson import ObjectId


# Custom ObjectId field for Pydantic
class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic models."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, _info=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, _schema):
        return {"type": "string"}


# ==============================================================================
# ENUMS
# ==============================================================================

class UserStatus(str, Enum):
    """User status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class PermissionLevel(str, Enum):
    """User permission levels."""
    ADMIN = "admin"
    USER = "user"


class SubscriptionUnit(str, Enum):
    """Subscription unit types."""
    PAGE = "page"
    WORD = "word"
    CHARACTER = "character"


class SubscriptionStatus(str, Enum):
    """Subscription status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


class InvoiceStatus(str, Enum):
    """Invoice status."""
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentStatus(str, Enum):
    """Payment status."""
    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class TransactionStatus(str, Enum):
    """Translation transaction status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


# ==============================================================================
# EMBEDDED DOCUMENT MODELS
# ==============================================================================

class UsagePeriod(BaseModel):
    """Embedded usage period in subscriptions."""
    period_start: datetime
    period_end: datetime
    units_allocated: int
    units_used: int = 0
    units_remaining: int
    promotional_units: int = 0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PaymentApplication(BaseModel):
    """Embedded payment application in invoices."""
    payment_id: PyObjectId
    amount_applied: float
    applied_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FileMetadata(BaseModel):
    """Embedded file metadata in translation transactions."""
    file_name: Optional[str] = None
    file_size_bytes: Optional[int] = None
    file_format: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    character_count: Optional[int] = None


class TranslationDocumentEmbedded(BaseModel):
    """
    Embedded document in translation transactions (nested structure).
    Represents a single document in a transaction's documents[] array.
    """
    file_name: str
    file_size: int
    original_url: str
    translated_url: Optional[str] = None
    translated_name: Optional[str] = None
    status: str = "uploaded"
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    translated_at: Optional[datetime] = None
    processing_started_at: Optional[datetime] = None
    processing_duration: Optional[float] = None
    transaction_id: Optional[str] = None  # MongoDB _id for enterprise


class Address(BaseModel):
    """Embedded address information for companies."""
    address0: Optional[str] = Field(None, description="Primary address line")
    address1: Optional[str] = Field(None, description="Secondary address line")
    city: Optional[str] = Field(None, description="City name")
    state: Optional[str] = Field(None, description="State or province")
    postal_code: Optional[str] = Field(None, description="Postal or ZIP code")
    country: Optional[str] = Field(None, description="Country name")


class ContactPerson(BaseModel):
    """Embedded contact person information for companies."""
    name: Optional[str] = Field(None, description="Contact person full name")
    type: Optional[str] = Field(None, description="Contact type (e.g., primary, billing, technical)")
    title: Optional[str] = Field(None, description="Job title or position")
    email: Optional[EmailStr] = Field(None, description="Contact email address")
    phone: Optional[str] = Field(None, description="Contact phone number")


# ==============================================================================
# CORE COLLECTIONS
# ==============================================================================

class Company(BaseModel):
    """Company/customer information."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    company_name: str = Field(..., max_length=255)
    description: Optional[str] = None
    address: Optional[Address] = None
    contact_person: Optional[ContactPerson] = None
    contact_email: Optional[EmailStr] = None
    phone_number: Optional[List[str]] = None
    company_url: Optional[List[str]] = None
    line_of_business: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True


class CompanyUser(BaseModel):
    """Authorized users per company with role-based access."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str = Field(..., max_length=255)
    company_name: str = Field(..., max_length=255)
    user_name: str = Field(..., max_length=255)
    email: EmailStr
    phone_number: Optional[str] = Field(None, max_length=50)
    permission_level: PermissionLevel = PermissionLevel.USER
    status: UserStatus = UserStatus.ACTIVE
    password_hash: Optional[str] = None
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True


# ==============================================================================
# SUBSCRIPTION & BILLING COLLECTIONS
# ==============================================================================

class Subscription(BaseModel):
    """Customer subscription plans with usage tracking."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    company_name: str = Field(..., max_length=255)
    subscription_unit: SubscriptionUnit
    units_per_subscription: int
    price_per_unit: float
    promotional_units: int = 0
    discount: float = 1.0
    subscription_price: float
    start_date: datetime
    end_date: Optional[datetime] = None
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE

    # Embedded arrays
    usage_periods: List[UsagePeriod] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True


class Invoice(BaseModel):
    """Customer invoices for billing."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    company_name: str = Field(..., max_length=255)
    subscription_id: Optional[PyObjectId] = None
    invoice_number: str = Field(..., max_length=50)
    invoice_date: datetime
    due_date: datetime
    total_amount: float
    tax_amount: float = 0
    status: InvoiceStatus = InvoiceStatus.DRAFT
    pdf_url: Optional[str] = None

    # Embedded payment applications
    payment_applications: List[PaymentApplication] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True


class Payment(BaseModel):
    """Square payment transactions."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    company_name: str = Field(..., max_length=255)
    subscription_id: Optional[PyObjectId] = None
    square_payment_id: str = Field(..., max_length=255)
    square_order_id: Optional[str] = None
    square_receipt_url: Optional[str] = None
    amount: float
    currency: str = Field(default="USD", max_length=3)
    payment_status: PaymentStatus
    payment_method: Optional[str] = None
    card_brand: Optional[str] = None
    last_4_digits: Optional[str] = Field(None, max_length=4)
    processing_fee: Optional[float] = None
    net_amount: Optional[float] = None
    refunded_amount: float = 0
    payment_date: datetime
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True


# ==============================================================================
# TRANSLATION OPERATIONS
# ==============================================================================

class TranslationTransaction(BaseModel):
    """
    Translation job transactions with nested documents[] array.

    STRUCTURE: Uses nested documents[] array for multiple files per transaction.
    This model supports both legacy flat structure and new nested structure for backward compatibility.
    """
    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    # Core transaction fields
    transaction_id: Optional[str] = None
    user_id: Optional[str] = None  # User email for folder lookup
    company_name: Optional[str] = Field(None, max_length=255)
    subscription_id: Optional[PyObjectId] = None
    user_name: Optional[str] = None

    # Translation details
    source_language: str = Field(..., max_length=10)
    target_language: str = Field(..., max_length=10)

    # Pricing
    units_count: Optional[int] = None
    price_per_unit: Optional[float] = None
    total_price: Optional[float] = None
    unit_type: Optional[str] = None

    # Status tracking
    status: TransactionStatus = TransactionStatus.COMPLETED
    error_message: Optional[str] = None

    # Document completion tracking (for email batching)
    total_documents: Optional[int] = 0  # Total documents in transaction
    completed_documents: Optional[int] = 0  # Completed translations count

    # Timestamps
    transaction_date: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # NESTED documents array - NEW STRUCTURE
    documents: Optional[List[TranslationDocumentEmbedded]] = Field(default_factory=list)

    # LEGACY flat structure fields - keep for backward compatibility
    requester_id: Optional[str] = None
    units_consumed: Optional[int] = None
    original_file_url: Optional[str] = None
    translated_file_url: Optional[str] = None
    file_metadata: Optional[FileMetadata] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Enums
    "UserStatus",
    "PermissionLevel",
    "SubscriptionUnit",
    "SubscriptionStatus",
    "InvoiceStatus",
    "PaymentStatus",
    "TransactionStatus",

    # Embedded Models
    "UsagePeriod",
    "PaymentApplication",
    "FileMetadata",
    "TranslationDocumentEmbedded",
    "Address",
    "ContactPerson",

    # Core Models
    "Company",
    "CompanyUser",

    # Subscription & Billing Models
    "Subscription",
    "Invoice",
    "Payment",

    # Translation Models
    "TranslationTransaction",

    # Custom Types
    "PyObjectId"
]
