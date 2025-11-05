"""
Request models for the Translation Web Server API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
from datetime import datetime


class TranslationServiceType(str, Enum):
    """Available translation services."""
    GOOGLE = "google"
    DEEPL = "deepl"
    AZURE = "azure"
    AUTO = "auto"  # Automatically select best service


class SortOrder(str, Enum):
    """Sort order options."""
    ASC = "asc"
    DESC = "desc"


# Text Translation Requests
class TextTranslationRequest(BaseModel):
    """Request model for text translation."""
    text: str = Field(..., min_length=1, max_length=5000, description="Text to translate")
    source_language: Optional[str] = Field(None, description="Source language code (auto-detect if not provided)")
    target_language: str = Field(..., description="Target language code")
    service: TranslationServiceType = Field(TranslationServiceType.AUTO, description="Translation service to use")
    preserve_formatting: bool = Field(True, description="Whether to preserve text formatting")
    
    @validator('text')
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Text cannot be empty or whitespace only")
        return v.strip()
    
    @validator('source_language', 'target_language')
    def validate_language_code(cls, v):
        if v and len(v) not in [2, 5]:  # ISO 639-1 (2 chars) or full locale (5 chars like en-US)
            raise ValueError("Language code must be ISO 639-1 format (e.g., 'en', 'fr') or locale format (e.g., 'en-US')")
        return v.lower() if v else v


class BatchTextTranslationRequest(BaseModel):
    """Request model for batch text translation."""
    texts: List[str] = Field(..., min_items=1, max_items=100, description="List of texts to translate")
    source_language: Optional[str] = Field(None, description="Source language code")
    target_language: str = Field(..., description="Target language code")
    service: TranslationServiceType = Field(TranslationServiceType.AUTO, description="Translation service to use")
    preserve_formatting: bool = Field(True, description="Whether to preserve text formatting")
    
    @validator('texts')
    def validate_texts(cls, v):
        if not v:
            raise ValueError("At least one text is required")
        
        total_chars = sum(len(text) for text in v)
        if total_chars > 50000:  # 50k character limit for batch
            raise ValueError("Total character count exceeds limit (50,000)")
        
        for i, text in enumerate(v):
            if not text or not text.strip():
                raise ValueError(f"Text at index {i} cannot be empty")
        
        return [text.strip() for text in v]


# File Translation Requests
class FileTranslationRequest(BaseModel):
    """Request model for file translation."""
    file_id: str = Field(..., description="Uploaded file identifier")
    source_language: Optional[str] = Field(None, description="Source language code")
    target_language: str = Field(..., description="Target language code")
    service: TranslationServiceType = Field(TranslationServiceType.AUTO, description="Translation service to use")
    preserve_formatting: bool = Field(True, description="Whether to preserve document formatting")
    output_format: Optional[str] = Field(None, description="Desired output format (if different from input)")


class BatchFileTranslationRequest(BaseModel):
    """Request model for batch file translation."""
    file_ids: List[str] = Field(..., min_items=1, max_items=10, description="List of uploaded file identifiers")
    source_language: Optional[str] = Field(None, description="Source language code")
    target_language: str = Field(..., description="Target language code")
    service: TranslationServiceType = Field(TranslationServiceType.AUTO, description="Translation service to use")
    preserve_formatting: bool = Field(True, description="Whether to preserve document formatting")


# Language Detection Request
class LanguageDetectionRequest(BaseModel):
    """Request model for language detection."""
    text: str = Field(..., min_length=1, max_length=1000, description="Text to analyze")
    
    @validator('text')
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Text cannot be empty")
        return v.strip()


# File Upload Requests
class FileUploadMetadata(BaseModel):
    """Metadata for file upload."""
    filename: str = Field(..., description="Original filename")
    content_type: Optional[str] = Field(None, description="MIME type of the file")
    description: Optional[str] = Field(None, max_length=500, description="File description")
    tags: Optional[List[str]] = Field(None, description="File tags for organization")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        
        # Check for valid file extension
        allowed_extensions = ['txt', 'doc', 'docx', 'pdf', 'rtf', 'odt']
        if '.' not in v or v.split('.')[-1].lower() not in allowed_extensions:
            raise ValueError(f"File extension must be one of: {', '.join(allowed_extensions)}")
        
        return v.strip()


class FileUploadRequest(BaseModel):
    """Request model for file upload with customer and language information."""
    customer_email: Optional[str] = Field(None, description="Customer email address (uses default if not provided)")
    target_language: str = Field(..., description="Target language code for translation")
    
    @validator('customer_email')
    def validate_email(cls, v):
        import re
        if v is None:
            return v  # Allow None, will be handled by the service
        
        if not v or not v.strip():
            raise ValueError("Customer email cannot be empty")
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v.strip()):
            raise ValueError("Invalid email format")
        
        return v.strip().lower()
    
    @validator('target_language')
    def validate_target_language(cls, v):
        if not v or not v.strip():
            raise ValueError("Target language cannot be empty")
        
        # Validate language code format (ISO 639-1 or locale format)
        if len(v.strip()) not in [2, 5]:  # e.g., 'en' or 'en-US'
            raise ValueError("Language code must be ISO 639-1 format (e.g., 'en', 'fr') or locale format (e.g., 'en-US')")
        
        return v.strip().lower()


# Payment Requests
class PaymentIntentRequest(BaseModel):
    """Request model for creating payment intent."""
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: str = Field("USD", description="Payment currency")
    description: Optional[str] = Field(None, max_length=500, description="Payment description")
    metadata: Optional[Dict[str, str]] = Field(None, description="Additional metadata")
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        if v > 10000:  # $10,000 limit
            raise ValueError("Amount cannot exceed $10,000")
        return round(v, 2)
    
    @validator('currency')
    def validate_currency(cls, v):
        supported_currencies = ['USD', 'EUR', 'GBP', 'JPY']
        if v.upper() not in supported_currencies:
            raise ValueError(f"Currency must be one of: {', '.join(supported_currencies)}")
        return v.upper()


class CostEstimationRequest(BaseModel):
    """Request model for cost estimation."""
    text: Optional[str] = Field(None, description="Text to estimate cost for")
    file_id: Optional[str] = Field(None, description="File ID to estimate cost for")
    target_language: str = Field(..., description="Target language code")
    service: TranslationServiceType = Field(TranslationServiceType.AUTO, description="Translation service")
    
    @validator('text', 'file_id')
    def validate_text_or_file(cls, v, values):
        # Note: In Pydantic v2, we can't access field info directly in validator
        # This validation will be handled at model level or through a custom validator
        return v


# Query and Pagination Requests
class PaginationRequest(BaseModel):
    """Base pagination request model."""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")


class TranslationHistoryRequest(PaginationRequest):
    """Request model for translation history."""
    source_language: Optional[str] = Field(None, description="Filter by source language")
    target_language: Optional[str] = Field(None, description="Filter by target language")
    status: Optional[str] = Field(None, description="Filter by status")
    service: Optional[str] = Field(None, description="Filter by translation service")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")


class PaymentHistoryRequest(PaginationRequest):
    """Request model for payment history."""
    status: Optional[str] = Field(None, description="Filter by payment status")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")


class FileListRequest(PaginationRequest):
    """Request model for file listing."""
    file_type: Optional[str] = Field(None, description="Filter by file type")
    status: Optional[str] = Field(None, description="Filter by processing status")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")
    search: Optional[str] = Field(None, max_length=100, description="Search in filename")
    sort_by: str = Field("created_at", description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")


# Webhook Requests
class WebhookRequest(BaseModel):
    """Request model for webhook registration."""
    url: str = Field(..., description="Webhook URL")
    events: List[str] = Field(..., description="List of events to subscribe to")
    secret: Optional[str] = Field(None, description="Webhook secret for validation")
    active: bool = Field(True, description="Whether webhook is active")
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v
    
    @validator('events')
    def validate_events(cls, v):
        valid_events = [
            'translation.completed',
            'translation.failed',
            'payment.succeeded',
            'payment.failed',
            'file.uploaded',
            'file.processed'
        ]
        for event in v:
            if event not in valid_events:
                raise ValueError(f"Invalid event type: {event}")
        return v


# Settings and Configuration Requests
class UserPreferencesRequest(BaseModel):
    """Request model for user preferences."""
    default_source_language: Optional[str] = Field(None, description="Default source language")
    default_target_language: Optional[str] = Field(None, description="Default target language")
    preferred_service: Optional[TranslationServiceType] = Field(None, description="Preferred translation service")
    email_notifications: bool = Field(True, description="Enable email notifications")
    webhook_notifications: bool = Field(False, description="Enable webhook notifications")
    auto_detect_language: bool = Field(True, description="Auto-detect source language")


class ServiceConfigurationRequest(BaseModel):
    """Request model for service configuration."""
    service: TranslationServiceType = Field(..., description="Translation service")
    api_key: Optional[str] = Field(None, description="API key for the service")
    endpoint: Optional[str] = Field(None, description="Custom endpoint URL")
    region: Optional[str] = Field(None, description="Service region")
    enabled: bool = Field(True, description="Whether service is enabled")


# Submit Request
class SubmitRequest(BaseModel):
    """Request model for /submit endpoint."""
    file_name: str = Field(..., description="Name of the file")
    file_url: str = Field(..., description="Google Drive shareable URL")
    user_email: str = Field(..., description="User's email address")
    company_name: str = Field(..., description="Company name")
    transaction_id: Optional[str] = Field(None, description="Optional transaction ID")

    @validator('file_name')
    def validate_file_name(cls, v):
        if not v or not v.strip():
            raise ValueError("File name cannot be empty")
        return v.strip()

    @validator('file_url')
    def validate_file_url(cls, v):
        if not v or not v.strip():
            raise ValueError("File URL cannot be empty")
        # Basic URL validation for Google Drive URLs
        if not v.startswith(('http://', 'https://')):
            raise ValueError("File URL must be a valid HTTP/HTTPS URL")
        return v.strip()

    @validator('user_email')
    def validate_user_email(cls, v):
        import re
        if not v or not v.strip():
            raise ValueError("User email cannot be empty")

        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v.strip()):
            raise ValueError("Invalid email format")

        return v.strip().lower()

    @validator('company_name')
    def validate_company_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Company name cannot be empty")
        return v.strip()


# Export all models
__all__ = [
    "TextTranslationRequest",
    "BatchTextTranslationRequest",
    "FileTranslationRequest",
    "BatchFileTranslationRequest",
    "LanguageDetectionRequest",
    "FileUploadMetadata",
    "FileUploadRequest",
    "PaymentIntentRequest",
    "CostEstimationRequest",
    "PaginationRequest",
    "TranslationHistoryRequest",
    "PaymentHistoryRequest",
    "FileListRequest",
    "WebhookRequest",
    "UserPreferencesRequest",
    "ServiceConfigurationRequest",
    "SubmitRequest",
    "TranslationServiceType",
    "SortOrder"
]