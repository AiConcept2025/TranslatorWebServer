"""
Email service for sending translation notification emails via SMTP.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.config import settings
from app.models.email import (
    DocumentInfo,
    EmailTemplate,
    EmailRequest,
    TranslationNotificationContext,
    EmailSendResult
)
from app.services.template_service import template_service

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Custom exception for email service errors."""
    pass


class EmailService:
    """Service for sending emails via SMTP with template support."""

    def __init__(self):
        """Initialize email service with configuration."""
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.smtp_use_tls = settings.smtp_use_tls
        self.smtp_use_ssl = settings.smtp_use_ssl
        self.smtp_timeout = settings.smtp_timeout
        self.email_from = settings.email_from or settings.smtp_username
        self.email_from_name = settings.email_from_name
        self.email_reply_to = settings.email_reply_to
        self.email_enabled = settings.email_enabled

    def _validate_smtp_config(self) -> bool:
        """
        Validate SMTP configuration.

        Returns:
            True if configuration is valid, False otherwise
        """
        if not self.email_enabled:
            logger.warning("Email service is disabled in configuration")
            return False

        if not self.smtp_username or not self.smtp_password:
            logger.error("SMTP credentials not configured (smtp_username or smtp_password missing)")
            return False

        if not self.email_from:
            logger.error("Sender email (email_from) not configured")
            return False

        return True

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """
        Create and authenticate SMTP connection.

        Returns:
            Authenticated SMTP connection

        Raises:
            EmailServiceError: If connection or authentication fails
        """
        try:
            if self.smtp_use_ssl:
                # Use SSL from the start (port 465)
                smtp = smtplib.SMTP_SSL(
                    self.smtp_host,
                    self.smtp_port,
                    timeout=self.smtp_timeout
                )
                logger.info(f"Connected to SMTP server via SSL: {self.smtp_host}:{self.smtp_port}")
            else:
                # Use regular connection, then upgrade to TLS if needed
                smtp = smtplib.SMTP(
                    self.smtp_host,
                    self.smtp_port,
                    timeout=self.smtp_timeout
                )
                logger.info(f"Connected to SMTP server: {self.smtp_host}:{self.smtp_port}")

                if self.smtp_use_tls:
                    smtp.starttls()
                    logger.info("Upgraded connection to TLS")

            # Authenticate
            smtp.login(self.smtp_username, self.smtp_password)
            logger.info(f"Authenticated with SMTP server as: {self.smtp_username}")

            return smtp

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            raise EmailServiceError(f"SMTP authentication failed: {e}")

        except smtplib.SMTPConnectError as e:
            logger.error(f"Failed to connect to SMTP server: {e}")
            raise EmailServiceError(f"Failed to connect to SMTP server: {e}")

        except Exception as e:
            logger.error(f"Unexpected error creating SMTP connection: {e}")
            raise EmailServiceError(f"Unexpected error creating SMTP connection: {e}")

    def _build_email_message(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body_html: str,
        body_text: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> MIMEMultipart:
        """
        Build MIME email message with HTML and plain text alternatives.

        Args:
            to_email: Recipient email address
            to_name: Recipient name
            subject: Email subject
            body_html: HTML email body
            body_text: Plain text email body
            from_email: Sender email (override)
            from_name: Sender name (override)
            reply_to: Reply-to address (override)

        Returns:
            MIME multipart message
        """
        msg = MIMEMultipart('alternative')

        # Set headers
        msg['Subject'] = subject
        msg['From'] = f"{from_name or self.email_from_name} <{from_email or self.email_from}>"
        msg['To'] = f"{to_name} <{to_email}>"

        if reply_to or self.email_reply_to:
            msg['Reply-To'] = reply_to or self.email_reply_to

        # Attach plain text and HTML parts
        part_text = MIMEText(body_text, 'plain')
        part_html = MIMEText(body_html, 'html')

        msg.attach(part_text)
        msg.attach(part_html)

        return msg

    def send_email(self, email_request: EmailRequest) -> EmailSendResult:
        """
        Send an email using SMTP.

        Args:
            email_request: Email request with all necessary information

        Returns:
            EmailSendResult with send status
        """
        # Validate configuration
        if not self._validate_smtp_config():
            return EmailSendResult(
                success=False,
                message="Email service not configured properly",
                error="SMTP credentials or configuration missing",
                recipient=email_request.to_email
            )

        try:
            # Build email message
            msg = self._build_email_message(
                to_email=email_request.to_email,
                to_name=email_request.to_name,
                subject=email_request.subject,
                body_html=email_request.body_html,
                body_text=email_request.body_text,
                from_email=email_request.from_email,
                from_name=email_request.from_name,
                reply_to=email_request.reply_to
            )

            # Create SMTP connection and send
            smtp = self._create_smtp_connection()
            try:
                smtp.send_message(msg)
                logger.info(f"Email sent successfully to: {email_request.to_email}")

                return EmailSendResult(
                    success=True,
                    message=f"Email sent successfully to {email_request.to_email}",
                    recipient=email_request.to_email,
                    sent_at=datetime.now(timezone.utc).isoformat()
                )

            finally:
                smtp.quit()
                logger.debug("SMTP connection closed")

        except EmailServiceError as e:
            logger.error(f"Email service error: {e}")
            return EmailSendResult(
                success=False,
                message=f"Failed to send email to {email_request.to_email}",
                error=str(e),
                recipient=email_request.to_email
            )

        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}", exc_info=True)
            return EmailSendResult(
                success=False,
                message=f"Unexpected error sending email to {email_request.to_email}",
                error=str(e),
                recipient=email_request.to_email
            )

    def send_translation_notification(
        self,
        documents: List[DocumentInfo],
        user_name: str,
        user_email: str,
        company_name: str
    ) -> EmailSendResult:
        """
        Send translation notification email to user.

        Automatically selects the appropriate template based on company_name:
        - "Ind" -> Individual customer template
        - Other -> Corporate employee template

        Args:
            documents: List of translated documents
            user_name: Recipient name
            user_email: Recipient email address
            company_name: Company name ("Ind" for individuals)

        Returns:
            EmailSendResult with send status
        """
        try:
            # Create notification context
            context = TranslationNotificationContext(
                user_name=user_name,
                user_email=user_email,
                company_name=company_name,
                documents=documents,
                translation_service_company=settings.translation_service_company
            )

            # Determine template type
            template_type = context.template_type
            is_individual = context.is_individual

            logger.info(
                f"Preparing translation notification email for {user_email} "
                f"(customer type: {'individual' if is_individual else 'corporate'})"
            )

            # Render templates
            template_html = f"{template_type.value}.html"
            template_txt = f"{template_type.value}.txt"

            template_context = {
                "user_name": user_name,
                "company_name": company_name,
                "documents": [doc.dict() for doc in documents],
                "translation_service_company": context.translation_service_company
            }

            body_html = template_service.render_template(template_html, template_context)
            body_text = template_service.render_template(template_txt, template_context)

            # Determine subject based on customer type
            if is_individual:
                subject = "Your translated documents are ready for download"
            else:
                subject = "Translated documents are now available for download"

            # Create email request
            email_request = EmailRequest(
                to_email=user_email,
                to_name=user_name,
                subject=subject,
                body_html=body_html,
                body_text=body_text
            )

            # Send email
            result = self.send_email(email_request)

            if result.success:
                logger.info(f"Translation notification sent successfully to {user_email}")
            else:
                logger.error(f"Failed to send translation notification to {user_email}: {result.error}")

            return result

        except Exception as e:
            logger.error(f"Error preparing translation notification for {user_email}: {e}", exc_info=True)
            return EmailSendResult(
                success=False,
                message=f"Failed to prepare email for {user_email}",
                error=str(e),
                recipient=user_email
            )

    def test_connection(self) -> Dict[str, Any]:
        """
        Test SMTP connection and authentication.

        Returns:
            Dictionary with connection test results
        """
        logger.info("Testing SMTP connection...")

        if not self._validate_smtp_config():
            return {
                "success": False,
                "message": "Email service not configured properly",
                "details": "SMTP credentials or configuration missing"
            }

        try:
            smtp = self._create_smtp_connection()
            smtp.quit()

            return {
                "success": True,
                "message": "SMTP connection successful",
                "details": {
                    "host": self.smtp_host,
                    "port": self.smtp_port,
                    "username": self.smtp_username,
                    "tls": self.smtp_use_tls,
                    "ssl": self.smtp_use_ssl
                }
            }

        except EmailServiceError as e:
            return {
                "success": False,
                "message": "SMTP connection failed",
                "error": str(e)
            }

        except Exception as e:
            return {
                "success": False,
                "message": "Unexpected error testing SMTP connection",
                "error": str(e)
            }


# Create singleton instance
email_service = EmailService()
