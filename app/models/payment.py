"""
Payment models for Square payment integration.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId


class CompanyAddress(BaseModel):
    """Company address information."""
    street: str
    city: str
    state: str
    postal_code: str
    country: str = "US"


class PaymentMetadataInfo(BaseModel):
    """Additional payment metadata."""
    subscription_plan: Optional[str] = None
    invoice_number: Optional[str] = None

    model_config = {'extra': 'allow'}  # Allow additional fields


class Payment(BaseModel):
    """
    Payment document schema for Square payments.

    Stores comprehensive payment information including:
    - Core identifiers (company, subscription, user)
    - Denormalized customer data (snapshot at transaction time)
    - Square payment identifiers
    - Payment amounts and fees
    - Card details
    - Refund tracking
    - Risk evaluation
    """

    # Core identifiers
    company_id: Optional[str] = Field(None, description="Company ObjectId as string")
    subscription_id: Optional[str] = Field(None, description="Subscription ObjectId as string")
    user_id: Optional[str] = Field(None, description="User ObjectId as string")

    # Denormalized customer data (snapshot at transaction time)
    company_name: Optional[str] = None
    company_address: Optional[CompanyAddress] = None
    user_email: EmailStr
    user_name: Optional[str] = None

    # Square identifiers
    square_payment_id: str = Field(..., description="Square payment ID (unique)")
    square_order_id: Optional[str] = None
    square_customer_id: Optional[str] = None
    square_location_id: Optional[str] = None
    square_receipt_url: Optional[str] = None

    # Payment amounts (in cents)
    amount: int = Field(..., description="Payment amount in cents")
    currency: str = Field(default="USD", description="Currency code")
    processing_fee: Optional[int] = Field(None, description="Processing fee in cents")
    net_amount: Optional[int] = Field(None, description="Net amount after fees in cents")
    refunded_amount: int = Field(default=0, description="Refunded amount in cents")

    # Payment details
    payment_status: str = Field(..., description="Payment status (completed, pending, failed, refunded)")
    payment_method: Optional[str] = Field(default="card", description="Payment method type")
    payment_source: Optional[str] = Field(default="web", description="Payment source")

    # Card details
    card_brand: Optional[str] = None
    last_4_digits: Optional[str] = Field(None, max_length=4)
    card_exp_month: Optional[int] = Field(None, ge=1, le=12)
    card_exp_year: Optional[int] = Field(None, ge=2020)

    # Customer info
    buyer_email_address: Optional[EmailStr] = None

    # Refund tracking
    refund_id: Optional[str] = None
    refund_date: Optional[datetime] = None
    refund_reason: Optional[str] = None

    # Risk & fraud
    risk_evaluation: Optional[str] = Field(default="NORMAL", description="Risk evaluation status")

    # Dates
    payment_date: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Additional tracking
    notes: Optional[str] = None
    webhook_event_id: Optional[str] = None

    # Metadata
    metadata: Optional[PaymentMetadataInfo] = None

    # Raw Square response
    square_raw_response: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = {
        'populate_by_name': True,
        'json_schema_extra': {
            'example': {
                'company_id': '68ec42a48ca6a1781d9fe5c2',
                'subscription_id': '68ec42a48ca6a1781d9fe5c4',
                'user_id': '68ec42a48ca6a1781d9fe5c5',
                'company_name': 'Acme Corporation',
                'company_address': {
                    'street': '123 Main Street',
                    'city': 'San Francisco',
                    'state': 'CA',
                    'postal_code': '94102',
                    'country': 'US'
                },
                'user_email': 'john.doe@acme.com',
                'user_name': 'John Doe',
                'square_payment_id': 'sq_payment_68ec42a48ca6a178',
                'square_order_id': 'sq_order_68ec42a48ca6a178',
                'square_customer_id': 'sq_customer_abc123',
                'square_location_id': 'sq_location_xyz789',
                'square_receipt_url': 'https://square.example.com/receipts/12345',
                'amount': 10600,
                'currency': 'USD',
                'processing_fee': 338,
                'net_amount': 10262,
                'refunded_amount': 0,
                'payment_status': 'completed',
                'payment_method': 'card',
                'payment_source': 'web',
                'card_brand': 'VISA',
                'last_4_digits': '4242',
                'card_exp_month': 12,
                'card_exp_year': 2026,
                'buyer_email_address': 'john.doe@acme.com',
                'risk_evaluation': 'NORMAL',
                'notes': 'Payment for annual subscription',
                'webhook_event_id': 'evt_abc123xyz',
                'metadata': {
                    'subscription_plan': 'annual',
                    'invoice_number': 'INV-2025-001'
                }
            }
        }
    }


class PaymentCreate(BaseModel):
    """Schema for creating a new payment."""
    company_id: Optional[str] = None
    subscription_id: Optional[str] = None
    user_id: Optional[str] = None
    company_name: Optional[str] = None
    company_address: Optional[CompanyAddress] = None
    user_email: EmailStr
    user_name: Optional[str] = None
    square_payment_id: str
    square_order_id: Optional[str] = None
    square_customer_id: Optional[str] = None
    square_location_id: Optional[str] = None
    square_receipt_url: Optional[str] = None
    amount: int
    currency: str = "USD"
    processing_fee: Optional[int] = None
    net_amount: Optional[int] = None
    payment_status: str = "pending"
    payment_method: str = "card"
    payment_source: str = "web"
    card_brand: Optional[str] = None
    last_4_digits: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None
    buyer_email_address: Optional[EmailStr] = None
    risk_evaluation: str = "NORMAL"
    notes: Optional[str] = None
    webhook_event_id: Optional[str] = None
    metadata: Optional[PaymentMetadataInfo] = None
    square_raw_response: Optional[Dict[str, Any]] = None


class PaymentUpdate(BaseModel):
    """Schema for updating an existing payment."""
    payment_status: Optional[str] = None
    refund_id: Optional[str] = None
    refund_date: Optional[datetime] = None
    refund_reason: Optional[str] = None
    refunded_amount: Optional[int] = None
    notes: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PaymentResponse(BaseModel):
    """Schema for payment API responses."""
    id: str = Field(..., alias="_id")
    company_id: Optional[str] = None
    subscription_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: EmailStr
    square_payment_id: str
    amount: int
    currency: str
    payment_status: str
    payment_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {'populate_by_name': True}
