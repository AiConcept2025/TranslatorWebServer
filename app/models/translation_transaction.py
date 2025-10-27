"""
Translation transaction models for transaction management and tracking.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# Translation Transaction Models (for translation_transactions collection)
# ============================================================================

class TranslationTransactionListItem(BaseModel):
    """
    Individual translation transaction item in the company transactions list.

    This schema represents a transaction record as returned in the list endpoint.
    All datetime fields are returned as ISO 8601 strings.
    """
    id: str = Field(..., alias="_id", description="MongoDB ObjectId of the transaction record")
    transaction_id: str = Field(..., description="Unique transaction identifier (e.g., TXN-20FEF6D8FE)")
    user_id: str = Field(..., description="User email address")
    original_file_url: str = Field(..., description="Google Drive URL of original file")
    translated_file_url: str = Field(default="", description="Google Drive URL of translated file (empty if not yet translated)")
    source_language: str = Field(..., description="Source language code (e.g., en)")
    target_language: str = Field(..., description="Target language code (e.g., fr)")
    file_name: str = Field(..., description="Original filename")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    units_count: int = Field(..., ge=0, description="Number of translation units (pages or words)")
    price_per_unit: float = Field(..., ge=0, description="Price per translation unit in dollars")
    total_price: float = Field(..., ge=0, description="Total transaction price in dollars")
    status: str = Field(..., description="Transaction status: started | confirmed | pending | failed")
    error_message: str = Field(default="", description="Error message if status is failed")
    created_at: str = Field(..., description="Record creation timestamp in ISO 8601 format")
    updated_at: str = Field(..., description="Record update timestamp in ISO 8601 format")
    company_id: Optional[str] = Field(None, description="Company identifier (ObjectId) if enterprise customer")
    company_name: Optional[str] = Field(None, description="Company name (from $lookup) if enterprise customer")
    subscription_id: Optional[str] = Field(None, description="Subscription identifier (ObjectId) if enterprise customer")
    unit_type: str = Field(..., description="Unit type for billing: page | word")

    model_config = {
        'populate_by_name': True,
        'json_schema_extra': {
            'example': {
                '_id': '68fe1edeac2359ccbc6b05b2',
                'transaction_id': 'TXN-20FEF6D8FE',
                'user_id': 'danishevsky@yahoo.com',
                'original_file_url': 'https://docs.google.com/document/d/1ABCdef123/edit',
                'translated_file_url': '',
                'source_language': 'en',
                'target_language': 'fr',
                'file_name': 'TCG.docx',
                'file_size': 838186,
                'units_count': 33,
                'price_per_unit': 0.01,
                'total_price': 0.33,
                'status': 'started',
                'error_message': '',
                'created_at': '2025-10-26T13:15:10.913+00:00',
                'updated_at': '2025-10-26T13:15:10.913+00:00',
                'company_id': '68ec42a48ca6a1781d9fe5c9',
                'company_name': 'Iris Trading',
                'subscription_id': '68fa6add22b0c739f4f4b273',
                'unit_type': 'page'
            }
        }
    }


class TranslationTransactionListFilters(BaseModel):
    """Filters applied to the translation transaction list query."""
    company_id: str = Field(..., description="Company identifier used for filtering")
    status: Optional[str] = Field(None, description="Transaction status filter (started, confirmed, pending, failed) or None if not filtered")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'company_id': '68ec42a48ca6a1781d9fe5c9',
                    'status': 'started'
                },
                {
                    'company_id': '68ec42a48ca6a1781d9fe5c9',
                    'status': None
                }
            ]
        }
    }


class TranslationTransactionListData(BaseModel):
    """Data payload containing transactions list with pagination and filter information."""
    transactions: List[TranslationTransactionListItem] = Field(..., description="Array of transaction records matching the query")
    count: int = Field(..., ge=0, description="Number of transactions returned in this response")
    limit: int = Field(..., ge=1, le=100, description="Maximum number of results requested")
    skip: int = Field(..., ge=0, description="Number of results skipped (pagination offset)")
    filters: TranslationTransactionListFilters = Field(..., description="Filters applied to the query")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'summary': 'Multiple transactions',
                    'description': 'Response with multiple translation transactions',
                    'value': {
                        'transactions': [
                            {
                                '_id': '68fe1edeac2359ccbc6b05b2',
                                'transaction_id': 'TXN-20FEF6D8FE',
                                'user_id': 'danishevsky@yahoo.com',
                                'original_file_url': 'https://docs.google.com/document/d/1ABCdef123/edit',
                                'translated_file_url': '',
                                'source_language': 'en',
                                'target_language': 'fr',
                                'file_name': 'TCG.docx',
                                'file_size': 838186,
                                'units_count': 33,
                                'price_per_unit': 0.01,
                                'total_price': 0.33,
                                'status': 'started',
                                'error_message': '',
                                'created_at': '2025-10-26T13:15:10.913+00:00',
                                'updated_at': '2025-10-26T13:15:10.913+00:00',
                                'company_id': '68ec42a48ca6a1781d9fe5c9',
                                'company_name': 'Iris Trading',
                                'subscription_id': '68fa6add22b0c739f4f4b273',
                                'unit_type': 'page'
                            },
                            {
                                '_id': '68fe1edeac2359ccbc6b05b3',
                                'transaction_id': 'TXN-30FEF6D8FF',
                                'user_id': 'user@company.com',
                                'original_file_url': 'https://docs.google.com/document/d/2XYZabc456/edit',
                                'translated_file_url': 'https://docs.google.com/document/d/3XYZabc789/edit',
                                'source_language': 'es',
                                'target_language': 'de',
                                'file_name': 'Document.pdf',
                                'file_size': 524288,
                                'units_count': 15,
                                'price_per_unit': 0.01,
                                'total_price': 0.15,
                                'status': 'confirmed',
                                'error_message': '',
                                'created_at': '2025-10-25T10:30:00.000+00:00',
                                'updated_at': '2025-10-25T11:00:00.000+00:00',
                                'company_id': '68ec42a48ca6a1781d9fe5c9',
                                'company_name': 'Iris Trading',
                                'subscription_id': '68fa6add22b0c739f4f4b273',
                                'unit_type': 'page'
                            }
                        ],
                        'count': 2,
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'company_id': '68ec42a48ca6a1781d9fe5c9',
                            'status': None
                        }
                    }
                },
                {
                    'summary': 'Empty result',
                    'description': 'No transactions found for the given filters',
                    'value': {
                        'transactions': [],
                        'count': 0,
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'company_id': '68ec42a48ca6a1781d9fe999',
                            'status': None
                        }
                    }
                }
            ]
        }
    }


class TranslationTransactionListResponse(BaseModel):
    """
    Standardized response wrapper for company translation transactions list endpoint.

    This is the root response object returned by GET /api/v1/translation-transactions/company/{company_id}
    """
    success: bool = Field(True, description="Indicates if the request was successful")
    data: TranslationTransactionListData = Field(..., description="Transaction list data with pagination and filters")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'summary': 'Success with transactions',
                    'description': 'Successful response with multiple transactions',
                    'value': {
                        'success': True,
                        'data': {
                            'transactions': [
                                {
                                    '_id': '68fe1edeac2359ccbc6b05b2',
                                    'transaction_id': 'TXN-20FEF6D8FE',
                                    'user_id': 'danishevsky@yahoo.com',
                                    'original_file_url': 'https://docs.google.com/document/d/1ABCdef123/edit',
                                    'translated_file_url': '',
                                    'source_language': 'en',
                                    'target_language': 'fr',
                                    'file_name': 'TCG.docx',
                                    'file_size': 838186,
                                    'units_count': 33,
                                    'price_per_unit': 0.01,
                                    'total_price': 0.33,
                                    'status': 'started',
                                    'error_message': '',
                                    'created_at': '2025-10-26T13:15:10.913+00:00',
                                    'updated_at': '2025-10-26T13:15:10.913+00:00',
                                    'company_id': '68ec42a48ca6a1781d9fe5c9',
                                    'company_name': 'Iris Trading',
                                    'subscription_id': '68fa6add22b0c739f4f4b273',
                                    'unit_type': 'page'
                                }
                            ],
                            'count': 1,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_id': '68ec42a48ca6a1781d9fe5c9',
                                'status': 'started'
                            }
                        }
                    }
                },
                {
                    'summary': 'Empty result',
                    'description': 'No transactions found',
                    'value': {
                        'success': True,
                        'data': {
                            'transactions': [],
                            'count': 0,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_id': '68ec42a48ca6a1781d9fe999',
                                'status': None
                            }
                        }
                    }
                },
                {
                    'summary': 'Filtered by status',
                    'description': 'Example showing filtered transactions by confirmed status',
                    'value': {
                        'success': True,
                        'data': {
                            'transactions': [
                                {
                                    '_id': '68fe1edeac2359ccbc6b05b3',
                                    'transaction_id': 'TXN-30FEF6D8FF',
                                    'user_id': 'user@company.com',
                                    'original_file_url': 'https://docs.google.com/document/d/2XYZabc456/edit',
                                    'translated_file_url': 'https://docs.google.com/document/d/3XYZabc789/edit',
                                    'source_language': 'es',
                                    'target_language': 'de',
                                    'file_name': 'Document.pdf',
                                    'file_size': 524288,
                                    'units_count': 15,
                                    'price_per_unit': 0.01,
                                    'total_price': 0.15,
                                    'status': 'confirmed',
                                    'error_message': '',
                                    'created_at': '2025-10-25T10:30:00.000+00:00',
                                    'updated_at': '2025-10-25T11:00:00.000+00:00',
                                    'company_id': '68ec42a48ca6a1781d9fe5c9',
                                    'company_name': 'Iris Trading',
                                    'subscription_id': '68fa6add22b0c739f4f4b273',
                                    'unit_type': 'page'
                                }
                            ],
                            'count': 1,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_id': '68ec42a48ca6a1781d9fe5c9',
                                'status': 'confirmed'
                            }
                        }
                    }
                }
            ]
        }
    }
