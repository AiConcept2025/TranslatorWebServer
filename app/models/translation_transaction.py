"""
Translation transaction models for transaction management and tracking.
"""

from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# Translation Transaction Models (for translation_transactions collection)
# ============================================================================

class TranslationDocumentSchema(BaseModel):
    """
    Schema for individual documents in a translation transaction.

    Represents a single document within a translation transaction,
    including its original and translated URLs, processing status,
    and timing information.
    """
    file_name: str = Field(..., description="Original filename (e.g., 'contract.pdf')")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    original_url: str = Field(..., description="Google Drive URL of the original file")
    translated_url: Optional[str] = Field(None, description="Google Drive URL of the translated file (None if not yet translated)")
    translated_name: Optional[str] = Field(None, description="Translated filename (None if not yet translated)")
    status: str = Field(
        default="uploaded",
        description="Document processing status: uploaded | translating | completed | failed"
    )
    uploaded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when document was uploaded"
    )
    translated_at: Optional[datetime] = Field(
        None,
        description="Timestamp when translation completed (None if not yet translated)"
    )
    processing_started_at: Optional[datetime] = Field(
        None,
        description="Timestamp when translation processing started (None if not started)"
    )
    processing_duration: Optional[float] = Field(
        None,
        ge=0,
        description="Processing duration in seconds (None if not completed)"
    )
    transaction_id: Optional[str] = Field(
        None,
        description="MongoDB _id of parent transaction (only populated for enterprise customers)"
    )

    model_config = {
        'json_schema_extra': {
            'example': {
                'file_name': 'Business_Contract_2024.pdf',
                'file_size': 524288,
                'original_url': 'https://drive.google.com/file/d/1ABC_contract_2024/view',
                'translated_url': 'https://drive.google.com/file/d/1ABC_contract_2024_es/view',
                'translated_name': 'Business_Contract_2024_es.pdf',
                'status': 'completed',
                'uploaded_at': '2025-10-20T10:00:00Z',
                'translated_at': '2025-10-20T10:15:00Z',
                'processing_started_at': '2025-10-20T10:00:05Z',
                'processing_duration': 895.5
            }
        }
    }


class TranslationTransactionListItem(BaseModel):
    """
    Individual translation transaction item in the company transactions list.

    This schema represents a transaction record as returned in the list endpoint.
    All datetime fields are returned as ISO 8601 strings.
    Supports multiple documents per transaction via the documents array.
    """
    id: str = Field(..., alias="_id", description="MongoDB ObjectId of the transaction record")
    transaction_id: str = Field(..., description="Unique transaction identifier (e.g., TXN-20FEF6D8FE)")
    user_id: str = Field(..., description="User email address")
    documents: List[TranslationDocumentSchema] = Field(
        ...,
        min_length=1,
        description="List of documents in this transaction (at least one required)"
    )
    source_language: str = Field(..., description="Source language code (e.g., en)")
    target_language: str = Field(..., description="Target language code (e.g., fr)")
    units_count: int = Field(..., ge=0, description="Number of translation units (pages or words)")
    price_per_unit: float = Field(..., ge=0, description="Price per translation unit in dollars")
    total_price: float = Field(..., ge=0, description="Total transaction price in dollars")
    status: str = Field(..., description="Transaction status: started | confirmed | pending | failed")
    error_message: str = Field(default="", description="Error message if status is failed")
    created_at: str = Field(..., description="Record creation timestamp in ISO 8601 format")
    updated_at: str = Field(..., description="Record update timestamp in ISO 8601 format")
    company_name: Optional[str] = Field(None, description="Company name if enterprise customer")
    subscription_id: Optional[str] = Field(None, description="Subscription identifier (ObjectId) if enterprise customer")
    unit_type: str = Field(..., description="Unit type for billing: page | word")

    model_config = {
        'populate_by_name': True,
        'json_schema_extra': {
            'example': {
                '_id': '68fe1edeac2359ccbc6b05b2',
                'transaction_id': 'TXN-20FEF6D8FE',
                'user_id': 'danishevsky@yahoo.com',
                'documents': [
                    {
                        'file_name': 'TCG.docx',
                        'file_size': 838186,
                        'original_url': 'https://docs.google.com/document/d/1ABCdef123/edit',
                        'translated_url': 'https://docs.google.com/document/d/1ABCdef123_fr/edit',
                        'translated_name': 'TCG_fr.docx',
                        'status': 'completed',
                        'uploaded_at': '2025-10-26T13:15:10+00:00',
                        'translated_at': '2025-10-26T13:30:45+00:00',
                        'processing_started_at': '2025-10-26T13:15:15+00:00',
                        'processing_duration': 935.0
                    }
                ],
                'source_language': 'en',
                'target_language': 'fr',
                'units_count': 33,
                'price_per_unit': 0.01,
                'total_price': 0.33,
                'status': 'started',
                'error_message': '',
                'created_at': '2025-10-26T13:15:10.913+00:00',
                'updated_at': '2025-10-26T13:15:10.913+00:00',
                'company_name': 'Iris Trading',
                'subscription_id': '68fa6add22b0c739f4f4b273',
                'unit_type': 'page'
            }
        }
    }


class TranslationTransactionListFilters(BaseModel):
    """Filters applied to the translation transaction list query."""
    company_name: str = Field(..., description="Company name used for filtering")
    status: Optional[str] = Field(None, description="Transaction status filter (started, confirmed, pending, failed) or None if not filtered")

    model_config = {
        'json_schema_extra': {
            'examples': [
                {
                    'company_name': 'Iris Trading',
                    'status': 'started'
                },
                {
                    'company_name': 'Iris Trading',
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
                                'documents': [
                                    {
                                        'file_name': 'TCG.docx',
                                        'file_size': 838186,
                                        'original_url': 'https://docs.google.com/document/d/1ABCdef123/edit',
                                        'translated_url': None,
                                        'translated_name': None,
                                        'status': 'translating',
                                        'uploaded_at': '2025-10-26T13:15:10+00:00',
                                        'translated_at': None,
                                        'processing_started_at': '2025-10-26T13:15:15+00:00',
                                        'processing_duration': None
                                    }
                                ],
                                'source_language': 'en',
                                'target_language': 'fr',
                                'units_count': 33,
                                'price_per_unit': 0.01,
                                'total_price': 0.33,
                                'status': 'started',
                                'error_message': '',
                                'created_at': '2025-10-26T13:15:10.913+00:00',
                                'updated_at': '2025-10-26T13:15:10.913+00:00',
                                'company_name': 'Iris Trading',
                                'subscription_id': '68fa6add22b0c739f4f4b273',
                                'unit_type': 'page'
                            },
                            {
                                '_id': '68fe1edeac2359ccbc6b05b3',
                                'transaction_id': 'TXN-30FEF6D8FF',
                                'user_id': 'user@company.com',
                                'documents': [
                                    {
                                        'file_name': 'Document.pdf',
                                        'file_size': 524288,
                                        'original_url': 'https://docs.google.com/document/d/2XYZabc456/edit',
                                        'translated_url': 'https://docs.google.com/document/d/3XYZabc789/edit',
                                        'translated_name': 'Document_de.pdf',
                                        'status': 'completed',
                                        'uploaded_at': '2025-10-25T10:30:00+00:00',
                                        'translated_at': '2025-10-25T11:00:00+00:00',
                                        'processing_started_at': '2025-10-25T10:30:05+00:00',
                                        'processing_duration': 1795.0
                                    }
                                ],
                                'source_language': 'es',
                                'target_language': 'de',
                                'units_count': 15,
                                'price_per_unit': 0.01,
                                'total_price': 0.15,
                                'status': 'confirmed',
                                'error_message': '',
                                'created_at': '2025-10-25T10:30:00.000+00:00',
                                'updated_at': '2025-10-25T11:00:00.000+00:00',
                                'company_name': 'Iris Trading',
                                'subscription_id': '68fa6add22b0c739f4f4b273',
                                'unit_type': 'page'
                            }
                        ],
                        'count': 2,
                        'limit': 50,
                        'skip': 0,
                        'filters': {
                            'company_name': 'Iris Trading',
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
                            'company_name': 'Unknown Company',
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

    This is the root response object returned by GET /api/v1/translation-transactions/company/{company_name}
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
                                    'documents': [
                                        {
                                            'file_name': 'TCG.docx',
                                            'file_size': 838186,
                                            'original_url': 'https://docs.google.com/document/d/1ABCdef123/edit',
                                            'translated_url': None,
                                            'translated_name': None,
                                            'status': 'translating',
                                            'uploaded_at': '2025-10-26T13:15:10+00:00',
                                            'translated_at': None,
                                            'processing_started_at': '2025-10-26T13:15:15+00:00',
                                            'processing_duration': None
                                        }
                                    ],
                                    'source_language': 'en',
                                    'target_language': 'fr',
                                    'units_count': 33,
                                    'price_per_unit': 0.01,
                                    'total_price': 0.33,
                                    'status': 'started',
                                    'error_message': '',
                                    'created_at': '2025-10-26T13:15:10.913+00:00',
                                    'updated_at': '2025-10-26T13:15:10.913+00:00',
                                    'company_name': 'Iris Trading',
                                    'subscription_id': '68fa6add22b0c739f4f4b273',
                                    'unit_type': 'page'
                                }
                            ],
                            'count': 1,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_name': 'Iris Trading',
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
                                'company_name': 'Unknown Company',
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
                                    'documents': [
                                        {
                                            'file_name': 'Document.pdf',
                                            'file_size': 524288,
                                            'original_url': 'https://docs.google.com/document/d/2XYZabc456/edit',
                                            'translated_url': 'https://docs.google.com/document/d/3XYZabc789/edit',
                                            'translated_name': 'Document_de.pdf',
                                            'status': 'completed',
                                            'uploaded_at': '2025-10-25T10:30:00+00:00',
                                            'translated_at': '2025-10-25T11:00:00+00:00',
                                            'processing_started_at': '2025-10-25T10:30:05+00:00',
                                            'processing_duration': 1795.0
                                        }
                                    ],
                                    'source_language': 'es',
                                    'target_language': 'de',
                                    'units_count': 15,
                                    'price_per_unit': 0.01,
                                    'total_price': 0.15,
                                    'status': 'confirmed',
                                    'error_message': '',
                                    'created_at': '2025-10-25T10:30:00.000+00:00',
                                    'updated_at': '2025-10-25T11:00:00.000+00:00',
                                    'company_name': 'Iris Trading',
                                    'subscription_id': '68fa6add22b0c739f4f4b273',
                                    'unit_type': 'page'
                                }
                            ],
                            'count': 1,
                            'limit': 50,
                            'skip': 0,
                            'filters': {
                                'company_name': 'Iris Trading',
                                'status': 'confirmed'
                            }
                        }
                    }
                }
            ]
        }
    }
