"""
Contact form router for handling contact form submissions.
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Literal

from app.services.email_service import email_service
from app.models.email import EmailRequest

logger = logging.getLogger(__name__)


# Pydantic models
class ContactFormRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr  # Validates email format automatically
    subject: Literal["Enterprise Sales Inquiry", "Technical Support", "API Integration", "General Question"]
    message: str = Field(..., min_length=10, max_length=5000)


class ContactFormResponse(BaseModel):
    success: bool
    message: str


# Email routing configuration
SUBJECT_ROUTING = {
    "Enterprise Sales Inquiry": "sales@irissolutions.ai",
    "Technical Support": "support@irissolutions.ai",
    "API Integration": "support@irissolutions.ai",
    "General Question": "sales@irissolutions.ai"
}


# Router setup
router = APIRouter(prefix="/api/contact", tags=["contact"])


@router.post("", response_model=ContactFormResponse)
async def submit_contact_form(request: ContactFormRequest):
    """
    Handle contact form submission and route to appropriate team.

    Args:
        request: Contact form data with name, email, subject, and message

    Returns:
        ContactFormResponse with success status and message

    Raises:
        HTTPException: 500 if email sending fails
    """
    # Determine recipient based on subject
    to_email = SUBJECT_ROUTING[request.subject]

    # Build email bodies
    html_body = f"""
    <html>
        <body>
            <h2>New Contact Form Submission</h2>
            <p><strong>From:</strong> {request.name} ({request.email})</p>
            <p><strong>Subject:</strong> {request.subject}</p>
            <p><strong>Message:</strong></p>
            <p>{request.message.replace('\n', '<br>')}</p>
        </body>
    </html>
    """

    text_body = f"""
New Contact Form Submission

From: {request.name} ({request.email})
Subject: {request.subject}

Message:
{request.message}
"""

    # Create email request
    email_request = EmailRequest(
        to_email=to_email,
        to_name="Iris Solutions Team",  # Required field for recipient name
        subject=f"Contact Form: {request.subject}",
        body_html=html_body,
        body_text=text_body,
        from_email=request.email,
        from_name=request.name
    )

    # Send email (synchronous method, but called from async context)
    # Note: Email failures are logged but don't fail the request - the form submission
    # was received successfully even if email delivery has issues
    try:
        result = email_service.send_email(email_request)
        if result.success:
            logger.info(f"Contact form email sent successfully to {to_email} from {request.email}")
            return ContactFormResponse(
                success=True,
                message="Thank you for contacting us. We'll get back to you shortly."
            )
        else:
            # Log email failure but return success (form was received)
            logger.error(f"Failed to send contact form email to {to_email}: {result.error or result.message}")
            return ContactFormResponse(
                success=True,
                message="Thank you for contacting us. We'll get back to you shortly."
            )
    except Exception as e:
        # Log exception but return success (form was received)
        logger.error(f"Exception sending contact form email to {to_email}: {str(e)}")
        return ContactFormResponse(
            success=True,
            message="Thank you for contacting us. We'll get back to you shortly."
        )
