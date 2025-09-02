"""
Response models for the Translation Web Server API.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class TranslationStatus(str, Enum):
    """Translation task status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileType(str, Enum):
    """Supported file types."""
    TXT = "txt"
    DOC = "doc"
    DOCX = "docx"
    PDF = "pdf"
    RTF = "rtf"
    ODT = "odt"


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


# Base Response Models
class BaseResponse(BaseModel):
    """Base response model with common fields."""
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseResponse):
    """Error response model."""
    success: bool = False
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = {}


# Language Models
class Language(BaseModel):
    """Language information model."""
    code: str = Field(..., description="ISO 639-1 language code")
    name: str = Field(..., description="Language name in English")
    native_name: Optional[str] = Field(None, description="Language name in native script")
    supported_by: List[str] = Field(default_factory=list, description="Translation services supporting this language")


class LanguageListResponse(BaseResponse):
    """Response model for language listing."""
    languages: List[Language]
    total_count: int


class LanguageDetectionResponse(BaseResponse):
    """Response model for language detection."""
    detected_language: str = Field(..., description="Detected language code")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    alternatives: Optional[List[Dict[str, Union[str, float]]]] = None


# File Upload Models
class FileInfo(BaseModel):
    """File information model."""
    filename: str
    size: int
    content_type: str
    file_type: FileType
    checksum: str


class UploadResponse(BaseResponse):
    """Response model for file upload."""
    file_id: str = Field(..., description="Unique file identifier")
    file_info: FileInfo
    upload_url: Optional[str] = None


class FileListResponse(BaseResponse):
    """Response model for file listing."""
    files: List[Dict[str, Any]]
    total_count: int
    page: int
    page_size: int


# Translation Models
class TranslationRequest(BaseModel):
    """Internal translation request model."""
    text: Optional[str] = None
    file_id: Optional[str] = None
    source_language: Optional[str] = None
    target_language: str
    service: Optional[str] = None


class TranslationResult(BaseModel):
    """Translation result model."""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence: Optional[float] = None
    service_used: str
    characters_count: int
    word_count: int


class TranslationResponse(BaseResponse):
    """Response model for translation."""
    task_id: str = Field(..., description="Translation task identifier")
    status: TranslationStatus
    result: Optional[TranslationResult] = None
    progress: Optional[float] = Field(None, ge=0.0, le=1.0, description="Task progress percentage")
    estimated_completion: Optional[datetime] = None


class TranslationHistoryItem(BaseModel):
    """Translation history item model."""
    task_id: str
    source_language: str
    target_language: str
    original_text: Optional[str] = None
    translated_text: Optional[str] = None
    filename: Optional[str] = None
    status: TranslationStatus
    service_used: str
    characters_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    cost: Optional[float] = None


class TranslationHistoryResponse(BaseResponse):
    """Response model for translation history."""
    translations: List[TranslationHistoryItem]
    total_count: int
    page: int
    page_size: int


class BatchTranslationResponse(BaseResponse):
    """Response model for batch translation."""
    batch_id: str
    task_ids: List[str]
    total_tasks: int
    estimated_completion: Optional[datetime] = None


# Payment Models
class PricingTier(BaseModel):
    """Pricing tier model."""
    name: str
    price_per_character: float
    min_characters: int
    max_characters: Optional[int] = None
    features: List[str] = Field(default_factory=list)


class PricingResponse(BaseResponse):
    """Response model for pricing information."""
    tiers: List[PricingTier]
    currency: str = "USD"


class CostEstimate(BaseModel):
    """Cost estimation model."""
    characters_count: int
    word_count: int
    estimated_cost: float
    currency: str = "USD"
    tier: str


class CostEstimateResponse(BaseResponse):
    """Response model for cost estimation."""
    estimate: CostEstimate


class PaymentIntent(BaseModel):
    """Payment intent model."""
    payment_intent_id: str
    client_secret: str
    amount: float
    currency: str = "USD"
    status: PaymentStatus


class PaymentIntentResponse(BaseResponse):
    """Response model for payment intent creation."""
    payment_intent: PaymentIntent


class PaymentHistory(BaseModel):
    """Payment history model."""
    payment_id: str
    amount: float
    currency: str
    status: PaymentStatus
    description: str
    created_at: datetime
    updated_at: Optional[datetime] = None


class PaymentHistoryResponse(BaseResponse):
    """Response model for payment history."""
    payments: List[PaymentHistory]
    total_count: int
    page: int
    page_size: int


# Statistics and Analytics Models
class UsageStats(BaseModel):
    """Usage statistics model."""
    total_translations: int
    total_characters: int
    total_files: int
    languages_used: Dict[str, int]
    services_used: Dict[str, int]
    date_range: Dict[str, datetime]


class UsageStatsResponse(BaseResponse):
    """Response model for usage statistics."""
    stats: UsageStats


class ServiceStatus(BaseModel):
    """Service status model."""
    service_name: str
    status: str  # "online", "offline", "degraded"
    response_time: Optional[float] = None
    last_check: datetime
    error_message: Optional[str] = None


class ServicesStatusResponse(BaseResponse):
    """Response model for services status."""
    services: List[ServiceStatus]
    overall_status: str


# Webhook Models
class WebhookEvent(BaseModel):
    """Webhook event model."""
    event_type: str
    event_id: str
    timestamp: datetime
    data: Dict[str, Any]


class WebhookResponse(BaseResponse):
    """Response model for webhook handling."""
    event_id: str
    processed: bool = True


# Validation Models
class ValidationError(BaseModel):
    """Validation error model."""
    field: str
    message: str
    code: str


class ValidationErrorResponse(ErrorResponse):
    """Response model for validation errors."""
    validation_errors: List[ValidationError]


# Rate Limit Models
class RateLimitInfo(BaseModel):
    """Rate limit information model."""
    limit: int
    remaining: int
    reset_time: datetime
    window_seconds: int


class RateLimitResponse(BaseResponse):
    """Response model including rate limit info."""
    rate_limit: RateLimitInfo


# Export all models
__all__ = [
    "BaseResponse",
    "ErrorResponse",
    "HealthResponse",
    "Language",
    "LanguageListResponse",
    "LanguageDetectionResponse",
    "FileInfo",
    "UploadResponse",
    "FileListResponse",
    "TranslationResult",
    "TranslationResponse",
    "TranslationHistoryItem",
    "TranslationHistoryResponse",
    "BatchTranslationResponse",
    "PricingTier",
    "PricingResponse",
    "CostEstimate",
    "CostEstimateResponse",
    "PaymentIntent",
    "PaymentIntentResponse",
    "PaymentHistory",
    "PaymentHistoryResponse",
    "UsageStats",
    "UsageStatsResponse",
    "ServiceStatus",
    "ServicesStatusResponse",
    "WebhookEvent",
    "WebhookResponse",
    "ValidationError",
    "ValidationErrorResponse",
    "RateLimitInfo",
    "RateLimitResponse",
    "TranslationStatus",
    "FileType",
    "PaymentStatus"
]