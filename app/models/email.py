"""
Email-related models for the Translation Web Server API.
"""

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, validator
from enum import Enum


class DocumentInfo(BaseModel):
    """Document information for email notifications."""
    document_name: str = Field(..., description="Name of the document")
    original_url: str = Field(..., description="URL to the original document")
    translated_url: str = Field(..., description="URL to the translated document")

    @validator('document_name')
    def validate_document_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Document name cannot be empty")
        return v.strip()

    @validator('original_url', 'translated_url')
    def validate_urls(cls, v):
        if not v or not v.strip():
            raise ValueError("Document URL cannot be empty")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()


class EmailTemplate(str, Enum):
    """Available email templates."""
    INDIVIDUAL_NOTIFICATION = "individual_notification"
    CORPORATE_NOTIFICATION = "corporate_notification"


class EmailRequest(BaseModel):
    """Request model for sending emails."""
    to_email: EmailStr = Field(..., description="Recipient email address")
    to_name: str = Field(..., description="Recipient name")
    subject: str = Field(..., description="Email subject")
    body_html: str = Field(..., description="HTML email body")
    body_text: str = Field(..., description="Plain text email body")
    from_email: Optional[EmailStr] = Field(None, description="Sender email (override)")
    from_name: Optional[str] = Field(None, description="Sender name (override)")
    reply_to: Optional[EmailStr] = Field(None, description="Reply-to email address")

    @validator('subject', 'body_text', 'body_html')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Email subject and body cannot be empty")
        return v.strip() if isinstance(v, str) else v


class TranslationNotificationContext(BaseModel):
    """Context data for translation notification emails."""
    user_name: str = Field(..., description="Recipient user name")
    user_email: EmailStr = Field(..., description="Recipient email address")
    company_name: str = Field(..., description="Company name ('Ind' for individuals)")
    documents: List[DocumentInfo] = Field(..., min_items=1, description="List of translated documents")
    translation_service_company: str = Field(default="Iris Solutions", description="Translation service provider name")

    @validator('documents')
    def validate_documents(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one document must be provided")
        return v

    @property
    def is_individual(self) -> bool:
        """Check if recipient is an individual customer."""
        return self.company_name == "Ind"

    @property
    def template_type(self) -> EmailTemplate:
        """Get the appropriate template type based on customer type."""
        return EmailTemplate.INDIVIDUAL_NOTIFICATION if self.is_individual else EmailTemplate.CORPORATE_NOTIFICATION


class EmailSendResult(BaseModel):
    """Result of email sending operation."""
    success: bool = Field(..., description="Whether email was sent successfully")
    message: str = Field(..., description="Result message")
    error: Optional[str] = Field(None, description="Error message if failed")
    recipient: EmailStr = Field(..., description="Recipient email address")
    sent_at: Optional[str] = Field(None, description="Timestamp when email was sent")


# Export all models
__all__ = [
    "DocumentInfo",
    "EmailTemplate",
    "EmailRequest",
    "TranslationNotificationContext",
    "EmailSendResult"
]
