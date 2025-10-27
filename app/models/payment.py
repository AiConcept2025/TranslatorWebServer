"""
Payment models for Square payment integration.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr
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
    company_id: str = Field(..., description="Company identifier")
    company_name: str = Field(..., description="Company name")
    user_email: EmailStr = Field(..., description="User email address")
    square_payment_id: str = Field(..., description="Square payment ID")
    amount: int = Field(..., gt=0, description="Payment amount in cents")
    currency: str = Field(default="USD", description="Currency code (ISO 4217)")
    payment_status: str = Field(..., description="Payment status: COMPLETED | PENDING | FAILED | REFUNDED")
    refunds: List[RefundSchema] = Field(default_factory=list, description="Array of refund objects")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Record creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    payment_date: datetime = Field(default_factory=datetime.utcnow, description="Payment processing date")

    model_config = {
        'json_schema_extra': {
            'example': {
                'company_id': 'cmp_00123',
                'company_name': 'Acme Health LLC',
                'user_email': 'test5@yahoo.com',
                'square_payment_id': 'payment_sq_1761244600756_u12vb3tx6',
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
    company_id: str
    company_name: str
    user_email: EmailStr
    square_payment_id: str
    amount: int = Field(..., gt=0, description="Payment amount in cents")
    currency: str = Field(default="USD")
    payment_status: str = Field(default="PENDING", description="PENDING | COMPLETED | FAILED | REFUNDED")
    payment_date: Optional[datetime] = None

    model_config = {
        'json_schema_extra': {
            'example': {
                'company_id': 'cmp_00123',
                'company_name': 'Acme Health LLC',
                'user_email': 'test5@yahoo.com',
                'square_payment_id': 'payment_sq_1761244600756_u12vb3tx6',
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
    company_id: str
    company_name: str
    user_email: EmailStr
    square_payment_id: str
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


class PaymentListItem(BaseModel):
    """
    Individual payment item in the company payments list.

    This schema represents a payment record as returned in the list endpoint.
    All datetime fields are returned as ISO 8601 strings.
    """
    id: str = Field(..., alias="_id", description="MongoDB ObjectId of the payment record")
    company_id: str = Field(..., description="Company identifier (e.g., cmp_00123)")
    company_name: str = Field(..., description="Full company name")
    user_email: EmailStr = Field(..., description="Email address of the user who made the payment")
    square_payment_id: str = Field(..., description="Square payment identifier")
    amount: int = Field(..., gt=0, description="Payment amount in cents (e.g., 1299 = $12.99)")
    currency: str = Field(..., description="Currency code (ISO 4217, e.g., USD, EUR)")
    payment_status: str = Field(..., description="Payment status: COMPLETED | PENDING | FAILED | REFUNDED")
    refunds: List[RefundSchema] = Field(default_factory=list, description="Array of refund objects (empty if no refunds)")
    payment_date: str = Field(..., description="Payment processing date in ISO 8601 format")
    created_at: str = Field(..., description="Record creation timestamp in ISO 8601 format")
    updated_at: str = Field(..., description="Last update timestamp in ISO 8601 format")

    model_config = {
        'populate_by_name': True,
        'json_schema_extra': {
            'example': {
                '_id': '68fad3c2a0f41c24037c4810',
                'company_id': 'cmp_00123',
                'company_name': 'Acme Health LLC',
                'user_email': 'test5@yahoo.com',
                'square_payment_id': 'payment_sq_1761244600756',
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
    company_id: str = Field(..., description="Company identifier used for filtering")
    status: Optional[str] = Field(None, description="Payment status filter (COMPLETED, PENDING, FAILED, REFUNDED) or None if not filtered")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'company_id': 'cmp_00123',
                    'status': 'COMPLETED'
                },
                {
                    'company_id': 'cmp_00123',
                    'status': None
                }
            ]
        }
    }


class PaymentListData(BaseModel):
    """Data payload containing payments list with pagination and filter information."""
    payments: List[PaymentListItem] = Field(..., description="Array of payment records matching the query")
    count: int = Field(..., ge=0, description="Number of payments returned in this response")
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
                                'company_id': 'cmp_00123',
                                'company_name': 'Acme Health LLC',
                                'user_email': 'test5@yahoo.com',
                                'square_payment_id': 'payment_sq_1761244600756',
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
                                'company_id': 'cmp_00123',
                                'company_name': 'Acme Health LLC',
                                'user_email': 'admin@acmehealth.com',
                                'square_payment_id': 'payment_sq_1761268674',
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
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'company_id': 'cmp_00123',
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
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'company_id': 'cmp_00999',
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

    This is the root response object returned by GET /api/v1/payments/company/{company_id}
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
                                    'company_id': 'cmp_00123',
                                    'company_name': 'Acme Health LLC',
                                    'user_email': 'test5@yahoo.com',
                                    'square_payment_id': 'payment_sq_1761244600756',
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
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_id': 'cmp_00123',
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
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_id': 'cmp_00999',
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
    Schema for user_transactions collection with Square payment integration.

    This model represents individual translation transactions with full payment details.
    """
    # Core transaction fields
    user_name: str = Field(..., description="Full name of the user")
    user_email: EmailStr = Field(..., description="Email address of the user")
    document_url: str = Field(..., description="URL or path to the document")
    translated_url: Optional[str] = Field(None, description="URL or path to the translated document")
    number_of_units: int = Field(..., gt=0, description="Number of units (pages, words, or characters)")
    unit_type: str = Field(..., description="Type of unit: page, word, or character")
    cost_per_unit: float = Field(..., gt=0, description="Cost per single unit")
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")
    square_transaction_id: str = Field(..., description="Unique Square transaction ID")
    date: datetime = Field(..., description="Transaction date")
    status: str = Field(default="processing", description="Transaction status: processing, completed, failed")
    total_cost: float = Field(..., ge=0, description="Total cost (auto-calculated)")

    # Square payment fields
    square_payment_id: str = Field(..., description="Square payment ID")
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
                'document_url': 'https://drive.google.com/file/d/1ABC_sample_document/view',
                'translated_url': 'https://drive.google.com/file/d/1ABC_transl_document/view',
                'number_of_units': 10,
                'unit_type': 'page',
                'cost_per_unit': 0.15,
                'source_language': 'en',
                'target_language': 'es',
                'square_transaction_id': 'SQR-1EC28E70F10B4D9E',
                'date': '2025-10-23T23:56:55.438Z',
                'status': 'completed',
                'total_cost': 1.5,
                'square_payment_id': 'SQR-1EC28E70F10B4D9E',
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
    """Schema for creating a new user transaction."""
    user_name: str
    user_email: EmailStr
    document_url: str
    translated_url: Optional[str] = None
    number_of_units: int = Field(..., gt=0)
    unit_type: str = Field(..., pattern="^(page|word|character)$")
    cost_per_unit: float = Field(..., gt=0)
    source_language: str
    target_language: str
    square_transaction_id: str
    date: Optional[datetime] = None
    status: str = Field(default="processing", pattern="^(processing|completed|failed)$")

    # Square payment fields
    square_payment_id: str
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
                'document_url': 'https://drive.google.com/file/d/1ABC_sample_document/view',
                'translated_url': 'https://drive.google.com/file/d/1ABC_transl_document/view',
                'number_of_units': 10,
                'unit_type': 'page',
                'cost_per_unit': 0.15,
                'source_language': 'en',
                'target_language': 'es',
                'square_transaction_id': 'SQR-1EC28E70F10B4D9E',
                'square_payment_id': 'SQR-1EC28E70F10B4D9E',
                # Optional fields (with defaults shown)
                'currency': 'USD',
                'payment_status': 'COMPLETED',
                'status': 'completed',
                # Optional fields
                'date': '2025-10-23T23:56:55.438Z',
                'payment_date': '2025-10-23T23:56:55.438Z',
                'amount_cents': 150
            }
        }
    }


class UserTransactionResponse(BaseModel):
    """Schema for user transaction API responses."""
    id: str = Field(..., alias="_id")
    user_name: str
    user_email: EmailStr
    document_url: str
    translated_url: Optional[str] = None
    number_of_units: int
    unit_type: str
    cost_per_unit: float
    source_language: str
    target_language: str
    square_transaction_id: str
    date: datetime
    status: str
    total_cost: float
    square_payment_id: str
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
