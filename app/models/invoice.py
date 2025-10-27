"""
Invoice models for invoice management and tracking.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


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
    company_id: str = Field(..., description="Company identifier (e.g., cmp_00123)")
    company_name: Optional[str] = Field(None, description="Full company name (optional)")
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

    model_config = {
        'populate_by_name': True,
        'json_schema_extra': {
            'example': {
                '_id': '671b2bc25c62a0b61c084b34',
                'invoice_id': 'inv_legacy_001',
                'company_id': 'cmp_00123',
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
    company_id: str = Field(..., description="Company identifier used for filtering")
    status: Optional[str] = Field(None, description="Invoice status filter (sent, paid, overdue, cancelled) or None if not filtered")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'company_id': 'cmp_00123',
                    'status': 'sent'
                },
                {
                    'company_id': 'cmp_00123',
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
                                'company_id': 'cmp_00123',
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
                                'company_id': 'cmp_00123',
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
                            'company_id': 'cmp_00123',
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
                            'company_id': 'cmp_00999',
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

    This is the root response object returned by GET /api/v1/invoices/company/{company_id}
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
                                    'company_id': 'cmp_00123',
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
                                'company_id': 'cmp_00123',
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
                                'company_id': 'cmp_00999',
                                'status': None
                            }
                        }
                    }
                }
            ]
        }
    }
