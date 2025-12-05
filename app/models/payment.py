"""
Payment models for Square payment integration.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr, field_validator, computed_field
from bson import ObjectId


# ============================================================================
# Payment Models (for payments collection)
# ============================================================================

class RefundSchema(BaseModel):
    """Schema for refund in payments collection refunds array."""
    refund_id: str = Field(..., description="Square refund ID")
    amount: int = Field(..., gt=0, description="Refund amount in cents")
    currency: str = Field(default="USD", description="Currency code")
    status: str = Field(..., description="Refund status: COMPLETED | PENDING | FAILED")
    idempotency_key: str = Field(..., description="Unique idempotency key for Square API")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Refund creation timestamp")

    model_config = {
        'json_schema_extra': {
            'example': {
                'refund_id': 'rfn_01J2M9ABCD',
                'amount': 500,
                'currency': 'USD',
                'status': 'COMPLETED',
                'idempotency_key': 'rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62',
                'created_at': '2025-10-23T19:05:13Z'
            }
        }
    }


class Payment(BaseModel):
    """Payment schema for payments collection."""
    company_name: str = Field(..., description="Company name")
    user_email: EmailStr = Field(..., description="User email address")
    stripe_payment_intent_id: str = Field(..., description="Square payment ID")
    amount: int = Field(..., gt=0, description="Payment amount in cents")
    currency: str = Field(default="USD", description="Currency code (ISO 4217)")
    payment_status: str = Field(..., description="Payment status: COMPLETED | PENDING | FAILED | REFUNDED")
    refunds: List[RefundSchema] = Field(default_factory=list, description="Array of refund objects")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    payment_date: datetime = Field(default_factory=datetime.utcnow, description="Payment processing date")

    # New billing enhancement fields
    invoice_id: Optional[str] = Field(None, description="Invoice ID (only for subscription payments)")
    subscription_id: Optional[str] = Field(None, description="Subscription ID (only for subscription payments)")
    total_refunded: float = Field(default=0.0, ge=0, description="Total amount refunded in dollars")

    @computed_field
    @property
    def net_amount(self) -> float:
        """Calculate net amount (amount - total_refunded)."""
        amount_dollars = self.amount / 100.0
        return max(0.0, amount_dollars - self.total_refunded)

    @field_validator('total_refunded')
    @classmethod
    def validate_total_refunded(cls, v, info):
        """Validate total_refunded does not exceed payment amount."""
        if 'amount' in info.data:
            amount_dollars = info.data['amount'] / 100.0
            if v > amount_dollars:
                raise ValueError(f'total_refunded ({v}) cannot exceed payment amount ({amount_dollars})')
        return v

    model_config = {
        'json_schema_extra': {
            'example': {
                'company_name': 'Acme Health LLC',
                'user_email': 'test5@yahoo.com',
                'stripe_payment_intent_id': 'payment_sq_1761244600756_u12vb3tx6',
                'amount': 1299,
                'currency': 'USD',
                'payment_status': 'COMPLETED',
                'refunds': [],
                'created_at': '2025-10-23T18:36:51.154Z',
                'updated_at': '2025-10-23T18:36:51.154Z',
                'payment_date': '2025-10-23T18:36:51.154Z'
            }
        }
    }


class PaymentCreate(BaseModel):
    """Schema for creating a new payment."""
    company_name: Optional[str] = None  # Optional: Individual users don't have companies
    user_email: EmailStr
    stripe_payment_intent_id: str
    amount: int = Field(..., gt=0, description="Payment amount in cents")
    currency: str = Field(default="USD")
    payment_status: str = Field(default="PENDING", description="PENDING | COMPLETED | FAILED | REFUNDED")
    payment_date: Optional[datetime] = None

    model_config = {
        'json_schema_extra': {
            'example': {
                'company_name': 'Acme Health LLC',
                'user_email': 'test5@yahoo.com',
                'stripe_payment_intent_id': 'payment_sq_1761244600756_u12vb3tx6',
                'amount': 1299,
                'currency': 'USD',
                'payment_status': 'COMPLETED'
            }
        }
    }


class PaymentUpdate(BaseModel):
    """Schema for updating an existing payment."""
    payment_status: Optional[str] = Field(None, description="COMPLETED | PENDING | FAILED | REFUNDED")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PaymentResponse(BaseModel):
    """Schema for payment API responses."""
    id: str = Field(..., alias="_id")
    company_name: str
    user_email: EmailStr
    stripe_payment_intent_id: str
    amount: int
    currency: str
    payment_status: str
    refunds: List[RefundSchema]
    created_at: datetime
    updated_at: datetime
    payment_date: datetime

    model_config = {'populate_by_name': True}


class RefundRequest(BaseModel):
    """Schema for processing a refund on a payment."""
    refund_id: str = Field(..., description="Square refund ID")
    amount: int = Field(..., gt=0, description="Refund amount in cents")
    currency: str = Field(default="USD", description="Currency code")
    idempotency_key: str = Field(..., description="Unique idempotency key")

    model_config = {
        'json_schema_extra': {
            'example': {
                'refund_id': 'rfn_01J2M9ABCD',
                'amount': 500,
                'currency': 'USD',
                'idempotency_key': 'rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62'
            }
        }
    }


class SubscriptionPaymentCreate(BaseModel):
    """Schema for manually creating a subscription payment record (admin use)."""
    company_name: str = Field(..., description="Company name")
    subscription_id: str = Field(..., description="Subscription ObjectId")
    stripe_payment_intent_id: str = Field(..., description="Square payment ID")
    stripe_invoice_id: Optional[str] = Field(None, description="Square order ID")
    stripe_customer_id: Optional[str] = Field(None, description="Square customer ID")
    user_email: EmailStr = Field(..., description="User email who made payment")
    user_id: Optional[str] = Field(None, description="User ID")
    amount: int = Field(..., gt=0, description="Amount in cents")
    currency: str = Field(default="USD", description="Currency code")
    payment_status: str = Field(default="COMPLETED", description="Payment status")
    payment_method: Optional[str] = Field("card", description="Payment method")
    card_brand: Optional[str] = Field(None, description="Card brand (VISA, MASTERCARD)")
    card_last_4: Optional[str] = Field(None, description="Last 4 digits of card")
    receipt_url: Optional[str] = Field(None, description="Receipt URL")
    payment_date: Optional[datetime] = Field(None, description="Payment date (defaults to now)")

    model_config = {
        'json_schema_extra': {
            'example': {
                'company_name': 'Acme Translation Corp',
                'subscription_id': '690023c7eb2bceb90e274133',
                'stripe_payment_intent_id': 'sq_payment_e59858fff0794614',
                'stripe_invoice_id': 'sq_order_e4dce86988a847b1',
                'stripe_customer_id': 'sq_customer_c7b478ddc7b04f99',
                'user_email': 'admin@acme.com',
                'user_id': 'user_9db5a0fbe769442d',
                'amount': 9000,
                'currency': 'USD',
                'payment_status': 'COMPLETED',
                'payment_method': 'card',
                'card_brand': 'VISA',
                'card_last_4': '1234',
                'receipt_url': 'https://squareup.com/receipt/preview/b05a59b993294167',
                'payment_date': '2025-10-28T11:18:04.213Z'
            }
        }
    }


class PaymentListItem(BaseModel):
    """
    Individual payment item in the company payments list.

    This schema represents a payment record as returned in the list endpoint.
    All datetime fields are returned as ISO 8601 strings.
    """
    id: str = Field(..., alias="_id", description="MongoDB ObjectId of the payment record")
    company_name: str = Field(..., description="Full company name")
    user_email: EmailStr = Field(..., description="Email address of the user who made the payment")
    stripe_payment_intent_id: str = Field(..., description="Square payment identifier")
    amount: int = Field(..., gt=0, description="Payment amount in cents (e.g., 1299 = $12.99)")
    currency: str = Field(..., description="Currency code (ISO 4217, e.g., USD, EUR)")
    payment_status: str = Field(..., description="Payment status: COMPLETED | PENDING | FAILED | REFUNDED")
    refunds: List[RefundSchema] = Field(default_factory=list, description="Array of refund objects (empty if no refunds)")
    payment_date: str = Field(..., description="Payment processing date in ISO 8601 format")
    created_at: str = Field(..., description="Record creation timestamp in ISO 8601 format")
    updated_at: str = Field(..., description="Last update timestamp in ISO 8601 format")

    # New billing enhancement fields
    invoice_id: Optional[str] = Field(None, description="Invoice ID (only for subscription payments)")
    subscription_id: Optional[str] = Field(None, description="Subscription ID (only for subscription payments)")
    total_refunded: float = Field(default=0.0, ge=0, description="Total amount refunded in dollars")
    net_amount: Optional[float] = Field(None, description="Net amount (amount - total_refunded)")

    model_config = {
        'populate_by_name': True,
        'json_schema_extra': {
            'example': {
                '_id': '68fad3c2a0f41c24037c4810',
                'company_name': 'Acme Health LLC',
                'user_email': 'test5@yahoo.com',
                'stripe_payment_intent_id': 'payment_sq_1761244600756',
                'amount': 1299,
                'currency': 'USD',
                'payment_status': 'COMPLETED',
                'refunds': [],
                'payment_date': '2025-10-24T01:17:54.544Z',
                'created_at': '2025-10-24T01:17:54.544Z',
                'updated_at': '2025-10-24T01:17:54.544Z'
            }
        }
    }


class PaymentListFilters(BaseModel):
    """Filters applied to the payment list query."""
    company_name: Optional[str] = Field(None, description="Company name used for filtering")
    status: Optional[str] = Field(None, description="Payment status filter (COMPLETED, PENDING, FAILED, REFUNDED) or None if not filtered")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'company_name': 'Acme Health LLC',
                    'status': 'COMPLETED'
                },
                {
                    'company_name': 'Acme Health LLC',
                    'status': None
                },
                {
                    'company_name': None,
                    'status': None
                }
            ]
        }
    }


class PaymentListData(BaseModel):
    """Data payload containing payments list with pagination and filter information."""
    payments: List[PaymentListItem] = Field(..., description="Array of payment records matching the query")
    count: int = Field(..., ge=0, description="Number of payments returned in this response")
    total: int = Field(..., ge=0, description="Total number of payments matching the filters (for pagination)")
    limit: int = Field(..., ge=1, le=100, description="Maximum number of results requested")
    skip: int = Field(..., ge=0, description="Number of results skipped (pagination offset)")
    filters: PaymentListFilters = Field(..., description="Filters applied to the query")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'summary': 'Multiple payments',
                    'description': 'Response with multiple completed payments',
                    'value': {
                        'payments': [
                            {
                                '_id': '68fad3c2a0f41c24037c4810',
                                'company_name': 'Acme Health LLC',
                                'user_email': 'test5@yahoo.com',
                                'stripe_payment_intent_id': 'payment_sq_1761244600756',
                                'amount': 1299,
                                'currency': 'USD',
                                'payment_status': 'COMPLETED',
                                'refunds': [],
                                'payment_date': '2025-10-24T01:17:54.544Z',
                                'created_at': '2025-10-24T01:17:54.544Z',
                                'updated_at': '2025-10-24T01:17:54.544Z'
                            },
                            {
                                '_id': '68fad3c2a0f41c24037c4811',
                                'company_name': 'Acme Health LLC',
                                'user_email': 'admin@acmehealth.com',
                                'stripe_payment_intent_id': 'payment_sq_1761268674',
                                'amount': 2499,
                                'currency': 'USD',
                                'payment_status': 'COMPLETED',
                                'refunds': [],
                                'payment_date': '2025-10-24T02:30:15.123Z',
                                'created_at': '2025-10-24T02:30:15.123Z',
                                'updated_at': '2025-10-24T02:30:15.123Z'
                            }
                        ],
                        'count': 2,
                        'total': 2,
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'company_name': 'Acme Health LLC',
                            'status': 'COMPLETED'
                        }
                    }
                },
                {
                    'summary': 'Empty result',
                    'description': 'No payments found for the given filters',
                    'value': {
                        'payments': [],
                        'count': 0,
                        'total': 0,
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'company_name': 'Unknown Company',
                            'status': None
                        }
                    }
                }
            ]
        }
    }


class PaymentListResponse(BaseModel):
    """
    Standardized response wrapper for company payments list endpoint.

    This is the root response object returned by GET /api/v1/payments/company/{company_name}
    """
    success: bool = Field(True, description="Indicates if the request was successful")
    data: PaymentListData = Field(..., description="Payment list data with pagination and filters")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'summary': 'Success with payments',
                    'description': 'Successful response with multiple payments',
                    'value': {
                        'success': True,
                        'data': {
                            'payments': [
                                {
                                    '_id': '68fad3c2a0f41c24037c4810',
                                    'company_name': 'Acme Health LLC',
                                    'user_email': 'test5@yahoo.com',
                                    'stripe_payment_intent_id': 'payment_sq_1761244600756',
                                    'amount': 1299,
                                    'currency': 'USD',
                                    'payment_status': 'COMPLETED',
                                    'refunds': [],
                                    'payment_date': '2025-10-24T01:17:54.544Z',
                                    'created_at': '2025-10-24T01:17:54.544Z',
                                    'updated_at': '2025-10-24T01:17:54.544Z'
                                }
                            ],
                            'count': 1,
                            'total': 1,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_name': 'Acme Health LLC',
                                'status': 'COMPLETED'
                            }
                        }
                    }
                },
                {
                    'summary': 'Empty result',
                    'description': 'No payments found',
                    'value': {
                        'success': True,
                        'data': {
                            'payments': [],
                            'count': 0,
                            'total': 0,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_name': 'Unknown Company',
                                'status': None
                            }
                        }
                    }
                }
            ]
        }
    }


# ============================================================================
# User Transaction Models (for users_transactions collection)
# ============================================================================

class DocumentSchema(BaseModel):
    """Schema for individual documents in a user transaction."""
    document_name: str = Field(..., description="Document filename (e.g., 'contract.pdf')")
    document_url: str = Field(..., description="URL to the original document (Google Drive)")
    translated_url: Optional[str] = Field(None, description="URL to the translated document (Google Drive)")
    status: str = Field(
        default="uploaded",
        description="Document status: uploaded, translating, completed, failed"
    )
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, description="Document upload timestamp")
    translated_at: Optional[datetime] = Field(None, description="Translation completion timestamp")

    model_config = {
        'json_schema_extra': {
            'example': {
                'document_name': 'contract.pdf',
                'document_url': 'https://drive.google.com/file/d/1ABC_original/view',
                'translated_url': 'https://drive.google.com/file/d/1ABC_translated/view',
                'status': 'completed',
                'uploaded_at': '2025-10-23T12:00:00Z',
                'translated_at': '2025-10-23T12:30:00Z'
            }
        }
    }


class UserTransactionRefundSchema(BaseModel):
    """Schema for refund information in user transactions."""
    refund_id: str = Field(..., description="Square refund ID")
    amount_cents: int = Field(..., gt=0, description="Refund amount in cents")
    currency: str = Field(default="USD", description="Currency code")
    status: str = Field(..., description="Refund status: COMPLETED, PENDING, FAILED")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Refund creation timestamp")
    idempotency_key: str = Field(..., description="Unique idempotency key for refund")
    reason: Optional[str] = Field(None, description="Reason for refund")

    model_config = {
        'json_schema_extra': {
            'example': {
                'refund_id': 'rfn_01J2M9ABCD',
                'amount_cents': 50,
                'currency': 'USD',
                'status': 'COMPLETED',
                'created_at': '2025-10-23T12:00:00Z',
                'idempotency_key': 'rfd_uuid_12345',
                'reason': 'Customer request'
            }
        }
    }


class UserTransactionSchema(BaseModel):
    """
    Schema for user_transactions collection with Stripe payment integration.

    This model represents individual translation transactions with full payment details.
    Supports multiple documents per transaction.
    """
    # Core transaction fields
    user_name: str = Field(..., description="Full name of the user")
    user_email: EmailStr = Field(..., description="Email address of the user")
    documents: List[DocumentSchema] = Field(..., min_length=1, description="List of documents in this transaction")
    number_of_units: int = Field(..., gt=0, description="Number of units (pages, words, or characters)")
    unit_type: str = Field(..., description="Type of unit: page, word, or character")
    cost_per_unit: float = Field(..., gt=0, description="Cost per single unit")
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")
    transaction_id: str = Field(..., description="Primary unique transaction identifier (USER + 6-digit number)")
    stripe_checkout_session_id: str = Field(..., description="Stripe Checkout Session ID")
    date: datetime = Field(..., description="Transaction date")
    status: str = Field(default="processing", description="Transaction status: processing, completed, failed")
    total_cost: float = Field(..., ge=0, description="Total cost (auto-calculated)")

    # Stripe payment fields
    stripe_payment_intent_id: str = Field(..., description="Stripe Payment Intent ID")
    amount_cents: int = Field(..., gt=0, description="Payment amount in cents")
    currency: str = Field(default="USD", description="Currency code (ISO 4217)")
    payment_status: str = Field(
        default="COMPLETED",
        description="Payment status: APPROVED, COMPLETED, CANCELED, FAILED"
    )
    refunds: List[UserTransactionRefundSchema] = Field(default_factory=list, description="List of refunds for this transaction")
    payment_date: datetime = Field(default_factory=datetime.utcnow, description="Payment processing date")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Record update timestamp")

    model_config = {
        'populate_by_name': True,
        'json_schema_extra': {
            'example': {
                'user_name': 'John Doe',
                'user_email': 'john.doe@example.com',
                'documents': [
                    {
                        'document_name': 'contract.pdf',
                        'document_url': 'https://drive.google.com/file/d/1ABC_contract/view',
                        'translated_url': 'https://drive.google.com/file/d/1ABC_contract_es/view',
                        'status': 'completed',
                        'uploaded_at': '2025-10-23T23:56:55.438Z',
                        'translated_at': '2025-10-23T23:58:30.438Z'
                    },
                    {
                        'document_name': 'invoice.docx',
                        'document_url': 'https://drive.google.com/file/d/1DEF_invoice/view',
                        'translated_url': 'https://drive.google.com/file/d/1DEF_invoice_es/view',
                        'status': 'completed',
                        'uploaded_at': '2025-10-23T23:57:00.438Z',
                        'translated_at': '2025-10-23T23:59:15.438Z'
                    }
                ],
                'number_of_units': 10,
                'unit_type': 'page',
                'cost_per_unit': 0.15,
                'source_language': 'en',
                'target_language': 'es',
                'transaction_id': 'USER123456',
                'stripe_checkout_session_id': 'cs_test_1EC28E70F10B4D9E',
                'date': '2025-10-23T23:56:55.438Z',
                'status': 'completed',
                'total_cost': 1.5,
                'stripe_payment_intent_id': 'pi_1EC28E70F10B4D9E',
                'amount_cents': 150,
                'currency': 'USD',
                'payment_status': 'COMPLETED',
                'refunds': [],
                'payment_date': '2025-10-23T23:56:55.438Z',
                'created_at': '2025-10-23T23:56:55.438Z',
                'updated_at': '2025-10-23T23:56:55.438Z'
            }
        }
    }


class UserTransactionCreate(BaseModel):
    """Schema for creating a new user transaction with multiple documents support."""
    user_name: str
    user_email: EmailStr
    documents: List[DocumentSchema] = Field(..., min_length=1, description="List of documents (at least one required)")
    number_of_units: int = Field(..., gt=0)
    unit_type: str = Field(..., pattern="^(page|word|character)$")
    cost_per_unit: float = Field(..., gt=0)
    source_language: str
    target_language: str
    stripe_checkout_session_id: str
    date: Optional[datetime] = None
    status: str = Field(default="processing", pattern="^(processing|completed|failed)$")

    # Square payment fields
    stripe_payment_intent_id: str
    amount_cents: Optional[int] = Field(None, gt=0, description="Payment amount in cents (auto-calculated if not provided)")
    currency: str = Field(default="USD")
    payment_status: str = Field(
        default="COMPLETED",
        pattern="^(APPROVED|COMPLETED|CANCELED|FAILED)$"
    )
    payment_date: Optional[datetime] = None

    model_config = {
        'json_schema_extra': {
            'example': {
                # Required fields
                'user_name': 'John Doe',
                'user_email': 'john.doe@example.com',
                'documents': [
                    {
                        'document_name': 'contract.pdf',
                        'document_url': 'https://drive.google.com/file/d/1ABC_contract/view',
                        'translated_url': None,
                        'status': 'uploaded',
                        'uploaded_at': '2025-10-23T23:56:55.438Z',
                        'translated_at': None
                    }
                ],
                'number_of_units': 10,
                'unit_type': 'page',
                'cost_per_unit': 0.15,
                'source_language': 'en',
                'target_language': 'es',
                'stripe_checkout_session_id': 'SQR-1EC28E70F10B4D9E',
                'stripe_payment_intent_id': 'SQR-1EC28E70F10B4D9E',
                # Optional fields (with defaults shown)
                'currency': 'USD',
                'payment_status': 'COMPLETED',
                'status': 'processing',
                # Optional fields
                'date': '2025-10-23T23:56:55.438Z',
                'payment_date': '2025-10-23T23:56:55.438Z',
                'amount_cents': 150
            }
        }
    }


class UserTransactionResponse(BaseModel):
    """Schema for user transaction API responses with multiple documents support."""
    id: str = Field(..., alias="_id")
    user_name: str
    user_email: EmailStr
    documents: List[DocumentSchema]
    number_of_units: int
    unit_type: str
    cost_per_unit: float
    source_language: str
    target_language: str
    transaction_id: str
    stripe_checkout_session_id: str
    date: datetime
    status: str
    total_cost: float
    stripe_payment_intent_id: str
    amount_cents: int
    currency: str
    payment_status: str
    refunds: List[UserTransactionRefundSchema]
    payment_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = {'populate_by_name': True}


class UserTransactionRefundRequest(BaseModel):
    """Schema for processing a refund on a user transaction."""
    refund_id: str = Field(..., description="Square refund ID")
    amount_cents: int = Field(..., gt=0, description="Refund amount in cents")
    currency: str = Field(default="USD", description="Currency code")
    idempotency_key: str = Field(..., description="Unique idempotency key")
    reason: Optional[str] = Field(None, description="Reason for refund")

    model_config = {
        'json_schema_extra': {
            'example': {
                'refund_id': 'rfn_01J2M9ABCD',
                'amount_cents': 50,
                'currency': 'USD',
                'idempotency_key': 'rfd_c8e1a4b5-1c7a-4f9b-9f2d-1a2b3c4d5e6f',
                'reason': 'Customer request'
            }
        }
    }


# ============================================================================
# Admin Payment Models (for GET /api/v1/payments - Admin View)
# ============================================================================

class AllPaymentsFilters(BaseModel):
    """Filters applied to the admin all payments query."""
    status: Optional[str] = Field(None, description="Payment status filter (COMPLETED, PENDING, FAILED, REFUNDED) or None")
    company_name: Optional[str] = Field(None, description="Company name filter or None")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'status': 'COMPLETED',
                    'company_name': 'Acme Health LLC'
                },
                {
                    'status': None,
                    'company_name': None
                }
            ]
        }
    }


class AllPaymentsData(BaseModel):
    """Data payload for admin all payments list with pagination and filters."""
    payments: List[PaymentListItem] = Field(..., description="Array of payment records matching the query")
    count: int = Field(..., ge=0, description="Number of payments returned in this response")
    total: int = Field(..., ge=0, description="Total number of payments matching filters (across all pages)")
    limit: int = Field(..., ge=1, le=100, description="Maximum number of results requested")
    skip: int = Field(..., ge=0, description="Number of results skipped (pagination offset)")
    filters: AllPaymentsFilters = Field(..., description="Filters applied to the query")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'summary': 'Multiple payments across companies',
                    'value': {
                        'payments': [
                            {
                                '_id': '68fad3c2a0f41c24037c4810',
                                'company_name': 'Acme Health LLC',
                                'user_email': 'test5@yahoo.com',
                                'stripe_payment_intent_id': 'payment_sq_1761244600756',
                                'amount': 1299,
                                'currency': 'USD',
                                'payment_status': 'COMPLETED',
                                'refunds': [],
                                'payment_date': '2025-10-24T01:17:54.544Z',
                                'created_at': '2025-10-24T01:17:54.544Z',
                                'updated_at': '2025-10-24T01:17:54.544Z'
                            },
                            {
                                '_id': '68fad3c2a0f41c24037c4811',
                                'company_name': 'TechCorp Inc',
                                'user_email': 'admin@techcorp.com',
                                'stripe_payment_intent_id': 'payment_sq_1761268674',
                                'amount': 2499,
                                'currency': 'USD',
                                'payment_status': 'COMPLETED',
                                'refunds': [],
                                'payment_date': '2025-10-24T02:30:15.123Z',
                                'created_at': '2025-10-24T02:30:15.123Z',
                                'updated_at': '2025-10-24T02:30:15.123Z'
                            }
                        ],
                        'count': 2,
                        'total': 125,
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'status': 'COMPLETED',
                            'company_name': None
                        }
                    }
                }
            ]
        }
    }


class AllPaymentsResponse(BaseModel):
    """
    Standardized response wrapper for admin all payments endpoint.

    This is the root response object returned by GET /api/v1/payments (admin only)
    """
    success: bool = Field(True, description="Indicates if the request was successful")
    data: AllPaymentsData = Field(..., description="All payments data with pagination and filters")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'summary': 'Success with payments',
                    'value': {
                        'success': True,
                        'data': {
                            'payments': [
                                {
                                    '_id': '68fad3c2a0f41c24037c4810',
                                    'company_name': 'Acme Health LLC',
                                    'user_email': 'test5@yahoo.com',
                                    'stripe_payment_intent_id': 'payment_sq_1761244600756',
                                    'amount': 1299,
                                    'currency': 'USD',
                                    'payment_status': 'COMPLETED',
                                    'refunds': [],
                                    'payment_date': '2025-10-24T01:17:54.544Z',
                                    'created_at': '2025-10-24T01:17:54.544Z',
                                    'updated_at': '2025-10-24T01:17:54.544Z'
                                }
                            ],
                            'count': 1,
                            'total': 125,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'status': None,
                                'company_name': None
                            }
                        }
                    }
                },
                {
                    'summary': 'Empty result',
                    'value': {
                        'success': True,
                        'data': {
                            'payments': [],
                            'count': 0,
                            'total': 0,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'status': 'PENDING',
                                'company_name': None
                            }
                        }
                    }
                }
            ]
        }
    }
