"""
Invoice models for invoice management and tracking.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, computed_field


# ============================================================================
# Invoice Supporting Models
# ============================================================================

class BillingPeriod(BaseModel):
    """Billing period for quarterly invoices."""
    period_numbers: List[int] = Field(..., description="Period numbers (e.g., [1, 2, 3] for Q1)")
    period_start: datetime = Field(..., description="Start date of billing period")
    period_end: datetime = Field(..., description="End date of billing period")

    @field_validator('period_numbers')
    @classmethod
    def validate_period_numbers(cls, v):
        """Validate period numbers are 1-12 and sorted."""
        if not v:
            raise ValueError('period_numbers cannot be empty')
        if not all(1 <= p <= 12 for p in v):
            raise ValueError('Period numbers must be between 1 and 12')
        if v != sorted(v):
            raise ValueError('Period numbers must be sorted')
        return v

    model_config = {
        'json_schema_extra': {
            'example': {
                'period_numbers': [1, 2, 3],
                'period_start': '2025-01-01T00:00:00Z',
                'period_end': '2025-03-31T23:59:59Z'
            }
        }
    }


class LineItem(BaseModel):
    """Line item for invoice."""
    description: str = Field(..., description="Line item description")
    period_numbers: List[int] = Field(..., description="Periods this line item applies to")
    quantity: int = Field(..., gt=0, description="Quantity")
    unit_price: float = Field(..., ge=0, description="Unit price")
    amount: float = Field(..., ge=0, description="Total amount (quantity × unit_price)")

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v, info):
        """Validate amount equals quantity × unit_price."""
        if 'quantity' in info.data and 'unit_price' in info.data:
            expected = info.data['quantity'] * info.data['unit_price']
            if abs(v - expected) > 0.01:
                raise ValueError(f'amount must equal quantity × unit_price (expected {expected}, got {v})')
        return v

    @field_validator('period_numbers')
    @classmethod
    def validate_period_numbers(cls, v):
        """Validate period numbers are 1-12."""
        if not v:
            raise ValueError('period_numbers cannot be empty')
        if not all(1 <= p <= 12 for p in v):
            raise ValueError('Period numbers must be between 1 and 12')
        return v

    model_config = {
        'json_schema_extra': {
            'example': {
                'description': 'Base Subscription Charge',
                'period_numbers': [1, 2, 3],
                'quantity': 3,
                'unit_price': 100.00,
                'amount': 300.00
            }
        }
    }


# ============================================================================
# Invoice Models (for invoices collection)
# ============================================================================

class InvoiceListItem(BaseModel):
    """
    Individual invoice item in the company invoices list.

    This schema represents an invoice record as returned in the list endpoint.
    All datetime fields are returned as ISO 8601 strings.
    """
    id: str = Field(..., alias="_id", description="MongoDB ObjectId of the invoice record")
    invoice_id: Optional[str] = Field(None, description="Legacy invoice ID field (optional)")
    company_name: str = Field(..., description="Company name (e.g., 'Acme Health LLC')")
    subscription_id: str = Field(..., description="Subscription identifier linked to this invoice")
    invoice_number: str = Field(..., description="Unique invoice number (e.g., INV-2025-001)")
    invoice_date: str = Field(..., description="Invoice date in ISO 8601 format")
    due_date: str = Field(..., description="Payment due date in ISO 8601 format")
    total_amount: float = Field(..., ge=0, description="Total invoice amount in dollars (e.g., 106.00)")
    tax_amount: float = Field(..., ge=0, description="Tax amount in dollars (e.g., 6.00)")
    status: str = Field(..., description="Invoice status: sent | paid | overdue | cancelled")
    pdf_url: Optional[str] = Field(None, description="URL to the invoice PDF document")
    payment_applications: List[dict] = Field(default_factory=list, description="Array of payment applications (optional)")
    created_at: str = Field(..., description="Record creation timestamp in ISO 8601 format")

    # New billing enhancement fields
    billing_period: Optional[BillingPeriod] = Field(None, description="Billing period for quarterly invoices")
    line_items: List[LineItem] = Field(default_factory=list, description="Line items for detailed billing")
    subtotal: float = Field(default=0.0, ge=0, description="Subtotal before tax")
    amount_paid: float = Field(default=0.0, ge=0, description="Amount paid towards this invoice")
    stripe_invoice_id: Optional[str] = Field(None, description="Stripe invoice ID (if applicable)")

    @computed_field
    @property
    def amount_due(self) -> float:
        """Calculate amount due (total_amount - amount_paid)."""
        return max(0.0, self.total_amount - self.amount_paid)

    model_config = {
        'populate_by_name': True,
        'json_schema_extra': {
            'example': {
                '_id': '671b2bc25c62a0b61c084b34',
                'invoice_id': 'inv_legacy_001',
                'company_name': 'Acme Health LLC',
                'subscription_id': 'sub_abc123',
                'invoice_number': 'INV-2025-001',
                'invoice_date': '2025-10-08T00:07:00.396Z',
                'due_date': '2025-11-07T00:07:00.396Z',
                'total_amount': 106.00,
                'tax_amount': 6.00,
                'status': 'sent',
                'pdf_url': 'https://storage.example.com/invoices/INV-2025-001.pdf',
                'payment_applications': [],
                'created_at': '2025-10-08T00:07:00.396Z'
            }
        }
    }


class InvoiceListFilters(BaseModel):
    """Filters applied to the invoice list query."""
    company_name: str = Field(..., description="Company name used for filtering")
    status: Optional[str] = Field(None, description="Invoice status filter (sent, paid, overdue, cancelled) or None if not filtered")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'company_name': 'Acme Health LLC',
                    'status': 'sent'
                },
                {
                    'company_name': 'Acme Health LLC',
                    'status': None
                }
            ]
        }
    }


class InvoiceListData(BaseModel):
    """Data payload containing invoices list with pagination and filter information."""
    invoices: List[InvoiceListItem] = Field(..., description="Array of invoice records matching the query")
    count: int = Field(..., ge=0, description="Number of invoices returned in this response")
    limit: int = Field(..., ge=1, le=100, description="Maximum number of results requested")
    skip: int = Field(..., ge=0, description="Number of results skipped (pagination offset)")
    filters: InvoiceListFilters = Field(..., description="Filters applied to the query")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'summary': 'Multiple invoices',
                    'description': 'Response with multiple sent invoices',
                    'value': {
                        'invoices': [
                            {
                                '_id': '671b2bc25c62a0b61c084b34',
                                'invoice_id': 'inv_001',
                                'company_name': 'Acme Health LLC',
                                'subscription_id': 'sub_abc123',
                                'invoice_number': 'INV-2025-001',
                                'invoice_date': '2025-10-08T00:07:00.396Z',
                                'due_date': '2025-11-07T00:07:00.396Z',
                                'total_amount': 106.00,
                                'tax_amount': 6.00,
                                'status': 'sent',
                                'pdf_url': 'https://storage.example.com/invoices/INV-2025-001.pdf',
                                'payment_applications': [],
                                'created_at': '2025-10-08T00:07:00.396Z'
                            },
                            {
                                '_id': '671b2bc25c62a0b61c084b35',
                                'invoice_id': 'inv_002',
                                'company_name': 'Acme Health LLC',
                                'subscription_id': 'sub_abc123',
                                'invoice_number': 'INV-2025-002',
                                'invoice_date': '2025-09-08T00:07:00.396Z',
                                'due_date': '2025-10-08T00:07:00.396Z',
                                'total_amount': 212.00,
                                'tax_amount': 12.00,
                                'status': 'paid',
                                'pdf_url': 'https://storage.example.com/invoices/INV-2025-002.pdf',
                                'payment_applications': [],
                                'created_at': '2025-09-08T00:07:00.396Z'
                            }
                        ],
                        'count': 2,
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'company_name': 'Acme Health LLC',
                            'status': None
                        }
                    }
                },
                {
                    'summary': 'Empty result',
                    'description': 'No invoices found for the given filters',
                    'value': {
                        'invoices': [],
                        'count': 0,
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


class InvoiceListResponse(BaseModel):
    """
    Standardized response wrapper for company invoices list endpoint.

    This is the root response object returned by GET /api/v1/invoices/company/{company_name}
    """
    success: bool = Field(True, description="Indicates if the request was successful")
    data: InvoiceListData = Field(..., description="Invoice list data with pagination and filters")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'summary': 'Success with invoices',
                    'description': 'Successful response with multiple invoices',
                    'value': {
                        'success': True,
                        'data': {
                            'invoices': [
                                {
                                    '_id': '671b2bc25c62a0b61c084b34',
                                    'invoice_id': 'inv_001',
                                    'company_name': 'Acme Health LLC',
                                    'subscription_id': 'sub_abc123',
                                    'invoice_number': 'INV-2025-001',
                                    'invoice_date': '2025-10-08T00:07:00.396Z',
                                    'due_date': '2025-11-07T00:07:00.396Z',
                                    'total_amount': 106.00,
                                    'tax_amount': 6.00,
                                    'status': 'sent',
                                    'pdf_url': 'https://storage.example.com/invoices/INV-2025-001.pdf',
                                    'payment_applications': [],
                                    'created_at': '2025-10-08T00:07:00.396Z'
                                }
                            ],
                            'count': 1,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_name': 'Acme Health LLC',
                                'status': 'sent'
                            }
                        }
                    }
                },
                {
                    'summary': 'Empty result',
                    'description': 'No invoices found',
                    'value': {
                        'success': True,
                        'data': {
                            'invoices': [],
                            'count': 0,
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
# Invoice Create/Update Models
# ============================================================================

class InvoiceCreate(BaseModel):
    """
    Schema for creating a new invoice.

    All fields are required except pdf_url which is optional.
    """
    company_name: str = Field(..., description="Company name (e.g., 'Acme Health LLC')")
    subscription_id: str = Field(..., description="Subscription identifier linked to this invoice")
    invoice_number: str = Field(..., description="Unique invoice number (e.g., INV-2025-001)")
    invoice_date: str = Field(..., description="Invoice date in ISO 8601 format")
    due_date: str = Field(..., description="Payment due date in ISO 8601 format")
    total_amount: float = Field(..., ge=0, description="Total invoice amount in dollars (e.g., 106.00)")
    tax_amount: float = Field(..., ge=0, description="Tax amount in dollars (e.g., 6.00)")
    status: str = Field(..., description="Invoice status: sent | paid | overdue | cancelled")
    pdf_url: Optional[str] = Field(None, description="URL to the invoice PDF document")

    model_config = {
        'json_schema_extra': {
            'example': {
                'company_name': 'Acme Health LLC',
                'subscription_id': 'sub_abc123',
                'invoice_number': 'INV-2025-001',
                'invoice_date': '2025-10-08T00:07:00.396Z',
                'due_date': '2025-11-07T00:07:00.396Z',
                'total_amount': 106.00,
                'tax_amount': 6.00,
                'status': 'sent',
                'pdf_url': 'https://storage.example.com/invoices/INV-2025-001.pdf'
            }
        }
    }


class InvoiceUpdate(BaseModel):
    """
    Schema for updating an existing invoice.

    All fields are optional. Only provided fields will be updated.
    Note: company_name, subscription_id, and invoice_number are immutable and will be ignored.
    """
    status: Optional[str] = Field(None, description="Invoice status: sent | paid | overdue | cancelled")
    invoice_date: Optional[str] = Field(None, description="Invoice date in ISO 8601 format")
    due_date: Optional[str] = Field(None, description="Payment due date in ISO 8601 format")
    total_amount: Optional[float] = Field(None, ge=0, description="Total invoice amount in dollars")
    tax_amount: Optional[float] = Field(None, ge=0, description="Tax amount in dollars")
    pdf_url: Optional[str] = Field(None, description="URL to the invoice PDF document")

    model_config = {
        'json_schema_extra': {
            'example': {
                'status': 'paid',
                'pdf_url': 'https://storage.example.com/invoices/INV-2025-001-updated.pdf'
            }
        }
    }


class InvoiceCreateResponse(BaseModel):
    """Response for successful invoice creation."""
    success: bool = Field(True, description="Indicates if the request was successful")
    message: str = Field(..., description="Success message")
    data: InvoiceListItem = Field(..., description="Created invoice data")

    model_config = {
        'json_schema_extra': {
            'example': {
                'success': True,
                'message': 'Invoice created successfully',
                'data': {
                    '_id': '671b2bc25c62a0b61c084b34',
                    'invoice_id': None,
                    'company_name': 'Acme Health LLC',
                    'subscription_id': 'sub_abc123',
                    'invoice_number': 'INV-2025-001',
                    'invoice_date': '2025-10-08T00:07:00.396Z',
                    'due_date': '2025-11-07T00:07:00.396Z',
                    'total_amount': 106.00,
                    'tax_amount': 6.00,
                    'status': 'sent',
                    'pdf_url': 'https://storage.example.com/invoices/INV-2025-001.pdf',
                    'payment_applications': [],
                    'created_at': '2025-10-08T00:07:00.396Z'
                }
            }
        }
    }


class InvoiceUpdateResponse(BaseModel):
    """Response for successful invoice update."""
    success: bool = Field(True, description="Indicates if the request was successful")
    message: str = Field(..., description="Success message")
    data: InvoiceListItem = Field(..., description="Updated invoice data")

    model_config = {
        'json_schema_extra': {
            'example': {
                'success': True,
                'message': 'Invoice updated successfully',
                'data': {
                    '_id': '671b2bc25c62a0b61c084b34',
                    'invoice_id': None,
                    'company_name': 'Acme Health LLC',
                    'subscription_id': 'sub_abc123',
                    'invoice_number': 'INV-2025-001',
                    'invoice_date': '2025-10-08T00:07:00.396Z',
                    'due_date': '2025-11-07T00:07:00.396Z',
                    'total_amount': 106.00,
                    'tax_amount': 6.00,
                    'status': 'paid',
                    'pdf_url': 'https://storage.example.com/invoices/INV-2025-001.pdf',
                    'payment_applications': [],
                    'created_at': '2025-10-08T00:07:00.396Z'
                }
            }
        }
    }

