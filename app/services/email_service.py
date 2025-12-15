"""
Email service for sending translation notification emails via SMTP.
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
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

        # Sanitize email configuration values - strip inline comments from .env file
        # Some .env files have: EMAIL_FROM=email@domain.com  # Optional
        # The "# Optional" gets included as part of the value, breaking RFC 5322
        self.email_from = self._sanitize_email_config(settings.email_from) or settings.smtp_username
        self.email_from_name = self._sanitize_email_config(settings.email_from_name)
        self.email_reply_to = self._sanitize_email_config(settings.email_reply_to)

        self.email_enabled = settings.email_enabled

    def _sanitize_email_config(self, value: Optional[str]) -> Optional[str]:
        """
        Remove inline comments from .env configuration values.

        Args:
            value: Configuration value that may contain inline comments

        Returns:
            Sanitized value with comments removed, or None if value is None/empty

        Example:
            "email@domain.com  # Optional" → "email@domain.com"
            "email@domain.com" → "email@domain.com"
            None → None
        """
        if not value:
            return value

        # Strip inline comments (anything after #)
        if '#' in value:
            value = value.split('#')[0]

        # Remove surrounding whitespace
        value = value.strip()

        # Return None if empty after sanitization
        return value if value else None

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

    def _create_smtp_connection(self, debug_level: int = 0) -> smtplib.SMTP:
        """
        Create and authenticate SMTP connection.

        Args:
            debug_level: SMTP debug level (0=off, 1=basic, 2=full protocol trace)

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

            # Enable SMTP debug if requested
            if debug_level > 0:
                smtp.set_debuglevel(debug_level)
                logger.info("=" * 80)
                logger.info(f"SMTP DEBUG MODE ENABLED (level {debug_level}) - Full protocol trace will appear below")
                logger.info("=" * 80)

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
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
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
            attachments: Optional list of attachments, each dict with 'data' (bytes) and 'filename' (str)

        Returns:
            MIME multipart message
        """
        msg = MIMEMultipart('alternative')

        # Set headers
        msg['Subject'] = subject

        # Build From header - only include name if non-empty
        sender_name = from_name or self.email_from_name
        sender_email = from_email or self.email_from
        if sender_name and sender_name.strip():
            msg['From'] = f"{sender_name.strip()} <{sender_email}>"
        else:
            msg['From'] = sender_email

        # Build To header - only include name if non-empty (prevents malformed headers)
        if to_name and to_name.strip():
            msg['To'] = f"{to_name.strip()} <{to_email}>"
        else:
            msg['To'] = to_email

        if reply_to or self.email_reply_to:
            msg['Reply-To'] = reply_to or self.email_reply_to

        # Attach plain text and HTML parts
        part_text = MIMEText(body_text, 'plain')
        part_html = MIMEText(body_html, 'html')

        msg.attach(part_text)
        msg.attach(part_html)

        # Attach files if provided
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['data'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{attachment["filename"]}"'
                )
                msg.attach(part)

        return msg

    def send_email(self, email_request: EmailRequest, debug: bool = False) -> EmailSendResult:
        """
        Send an email using SMTP.

        Args:
            email_request: Email request with all necessary information
            debug: Enable SMTP debug mode for troubleshooting

        Returns:
            EmailSendResult with send status
        """
        logger.info("=" * 80)
        logger.info("EMAIL SERVICE - Sending Email")
        logger.info("=" * 80)
        logger.info(f"Preparing to send email to: {email_request.to_email}")
        logger.debug(
            "Email request parameters",
            extra={
                "to_email": email_request.to_email,
                "to_name": email_request.to_name,
                "subject": email_request.subject,
                "from_email": email_request.from_email or self.email_from,
                "from_name": email_request.from_name or self.email_from_name,
                "reply_to": email_request.reply_to or self.email_reply_to,
                "body_html_length": len(email_request.body_html),
                "body_text_length": len(email_request.body_text)
            }
        )

        # Validate configuration
        if not self._validate_smtp_config():
            logger.error("SMTP configuration validation failed")
            return EmailSendResult(
                success=False,
                message="Email service not configured properly",
                error="SMTP credentials or configuration missing",
                recipient=email_request.to_email
            )

        try:
            # Build email message
            logger.debug("Building email MIME message")
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

            # Log complete email content for debugging
            logger.debug("=" * 80)
            logger.debug("EMAIL CONTENT - Plain Text Body")
            logger.debug("=" * 80)
            logger.debug(f"\n{email_request.body_text}")
            logger.debug("=" * 80)
            logger.debug("EMAIL CONTENT - HTML Body")
            logger.debug("=" * 80)
            logger.debug(f"\n{email_request.body_html}")
            logger.debug("=" * 80)

            # DIAGNOSTIC LOGGING
            if debug:
                logger.info("=" * 80)
                logger.info("EMAIL DIAGNOSTIC INFORMATION")
                logger.info("=" * 80)
                logger.info(f"SMTP Server: {self.smtp_host}:{self.smtp_port}")
                logger.info(f"Authenticated as: {self.smtp_username}")
                logger.info(f"Email From (envelope): {self.email_from}")
                logger.info(f"Email From (header): {msg.get('From')}")
                logger.info(f"Email To (header): {msg.get('To')}")
                logger.info(f"Subject: {msg.get('Subject')}")
                logger.info(f"Content-Type: {msg.get('Content-Type')}")
                logger.info(f"Has HTML: {'text/html' in str(msg)}")
                logger.info(f"Has Text: {'text/plain' in str(msg)}")

                # Check envelope vs header mismatch
                if self.email_from != self.smtp_username:
                    logger.error(f"WARNING: email_from ({self.email_from}) != smtp_username ({self.smtp_username})")
                    logger.error("Yahoo requires these to match!")

                logger.info("=" * 80)

            # Create SMTP connection and send
            debug_level = 2 if debug else 0
            logger.info(f"Creating SMTP connection (debug_level={debug_level})")
            smtp = self._create_smtp_connection(debug_level=debug_level)
            try:
                logger.info(f"Sending email message to {email_request.to_email}")
                logger.debug(
                    "SMTP send_message parameters",
                    extra={
                        "from": msg.get('From'),
                        "to": msg.get('To'),
                        "subject": msg.get('Subject'),
                        "message_id": msg.get('Message-ID'),
                        "date": msg.get('Date')
                    }
                )

                smtp.send_message(msg)

                logger.info(f"✅ Email sent successfully to: {email_request.to_email}")
                logger.info("=" * 80)
                logger.info("EMAIL SERVICE - Email Sent Successfully")
                logger.info("=" * 80)

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
            logger.error(
                f"❌ Email service error: {e}",
                extra={
                    "error_type": "EmailServiceError",
                    "error": str(e),
                    "recipient": email_request.to_email,
                    "subject": email_request.subject
                },
                exc_info=True
            )
            return EmailSendResult(
                success=False,
                message=f"Failed to send email to {email_request.to_email}",
                error=str(e),
                recipient=email_request.to_email
            )

        except Exception as e:
            logger.error(
                f"❌ Unexpected error sending email: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "recipient": email_request.to_email,
                    "subject": email_request.subject
                },
                exc_info=True
            )
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
        company_name: str,
        transaction_id: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        total_documents: Optional[int] = None
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
            transaction_id: Transaction ID string (optional)
            completed_at: Timestamp when translation completed (optional)
            total_documents: Total number of documents in batch (optional)

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

            # COMPREHENSIVE LOGGING: Email preparation details
            logger.info("=" * 80)
            logger.info("EMAIL NOTIFICATION - Preparing to Send")
            logger.info("=" * 80)
            logger.info(f"Recipient: {user_name} <{user_email}>")
            logger.info(f"Email Type: {'Individual' if is_individual else 'Corporate'}")
            logger.info(f"Company: {company_name}")
            logger.info(f"Number of documents: {len(documents)}")
            if transaction_id:
                logger.info(f"Transaction ID: {transaction_id}")
            if completed_at:
                logger.info(f"Completed At: {completed_at.strftime('%B %d, %Y at %I:%M %p UTC')}")
            logger.info("-" * 80)
            logger.info("Documents:")
            for i, doc in enumerate(documents, 1):
                logger.info(f"  {i}. {doc.document_name}")
                logger.info(f"     Original:   {doc.original_url}")
                logger.info(f"     Translated: {doc.translated_url}")
            logger.info("=" * 80)

            logger.info(
                f"Preparing translation notification email for {user_email} "
                f"(customer type: {'individual' if is_individual else 'corporate'})"
            )

            # Render templates
            template_html = f"{template_type.value}.html"
            template_txt = f"{template_type.value}.txt"

            # Format completed_at as human-readable string if provided
            completed_at_formatted = None
            if completed_at:
                # Format as "January 8, 2025 at 3:45 PM UTC"
                completed_at_formatted = completed_at.strftime("%B %d, %Y at %I:%M %p UTC")

            template_context = {
                "user_name": user_name,
                "company_name": company_name,
                "documents": [doc.dict() for doc in documents],
                "translation_service_company": context.translation_service_company,
                "transaction_id": transaction_id,
                "completed_at": completed_at_formatted,
                "total_documents": total_documents or len(documents)
            }

            # Log new metadata fields for debugging
            logger.debug(
                "Email template context includes transaction metadata",
                extra={
                    "transaction_id": transaction_id,
                    "completed_at_formatted": completed_at_formatted,
                    "total_documents": total_documents or len(documents)
                }
            )

            body_html = template_service.render_template(template_html, template_context)
            body_text = template_service.render_template(template_txt, template_context)

            # Determine subject based on customer type
            if is_individual:
                subject = "Your translated documents are ready for download"
            else:
                subject = "Translated documents are now available for download"

            # Log email content preview
            logger.info("-" * 80)
            logger.info("Email Content Preview:")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body (first 500 chars):")
            logger.info(f"{body_text[:500]}...")
            logger.info("=" * 80)

            # Create email request
            email_request = EmailRequest(
                to_email=user_email,
                to_name=user_name,
                subject=subject,
                body_html=body_html,
                body_text=body_text
            )

            # Send email (debug disabled to prevent base64 MIME dumps in logs)
            # Human-readable preview is logged above instead
            result = self.send_email(email_request, debug=False)

            # Post-send logging with detailed summary
            logger.info("=" * 80)
            logger.info("EMAIL NOTIFICATION - Send Complete")
            logger.info("=" * 80)
            if result.success:
                logger.info(f"Status: SUCCESS")
                logger.info(f"Recipient: {user_email}")
                logger.info(f"Total emails sent in this batch: 1")
                logger.info(f"Documents included: {len(documents)}")
                logger.info(f"Email type: {'Individual' if is_individual else 'Corporate'}")
            else:
                logger.error(f"Status: FAILED")
                logger.error(f"Recipient: {user_email}")
                logger.error(f"Error: {result.error}")
            logger.info("=" * 80)

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

    def test_minimal_smtp(self, to_email: str) -> Dict[str, Any]:
        """
        Send ultra-minimal email to test SMTP at protocol level.

        Args:
            to_email: Recipient email address

        Returns:
            Dictionary with diagnostic information
        """
        import traceback
        import re

        results = {
            "connection_ok": False,
            "auth_ok": False,
            "send_ok": False,
            "error": None,
            "smtp_command_that_failed": None,
            "yahoo_error_code": None
        }

        logger.info("=" * 80)
        logger.info("MINIMAL SMTP TEST - Ultra-basic email send")
        logger.info("=" * 80)

        try:
            # Create connection
            logger.info(f"Creating SMTP connection to {self.smtp_host}:{self.smtp_port}")
            smtp = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
            smtp.set_debuglevel(2)  # Full debug
            results["connection_ok"] = True
            logger.info("✅ Connection successful")

            # Start TLS
            if self.smtp_use_tls:
                logger.info("Starting TLS...")
                smtp.starttls()
                logger.info("✅ TLS upgrade successful")

            # Authenticate
            logger.info(f"Authenticating as {self.smtp_username}...")
            smtp.login(self.smtp_username, self.smtp_password)
            results["auth_ok"] = True
            logger.info("✅ Authentication successful")

            # Validate recipient email format
            logger.info(f"Validating recipient email: {to_email}")
            email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
            if not email_pattern.match(to_email):
                results["error"] = f"Invalid recipient email format: {to_email}"
                logger.error(f"❌ Invalid email format: {to_email}")
                smtp.quit()
                return results

            logger.info("✅ Recipient email format valid")

            # Try sending with MINIMAL message (no MIME, just raw)
            from_addr = self.smtp_username  # Use authenticated address
            to_addr = to_email

            # Simplest possible email message
            from email.utils import formatdate, make_msgid
            message = """Subject: SMTP Test
From: {}
To: {}
Date: {}
Message-ID: {}

This is a minimal test email from the translation service.
""".format(from_addr, to_addr, formatdate(localtime=True), make_msgid())

            logger.info(f"Attempting to send from {from_addr} to {to_addr}")
            logger.info("Message content:")
            logger.info(message)
            logger.info("=" * 80)

            # This is the call that may fail with 550
            smtp.sendmail(from_addr, [to_addr], message)

            results["send_ok"] = True
            logger.info("✅ Email sent successfully!")
            logger.info("=" * 80)

            smtp.quit()

        except smtplib.SMTPRecipientsRefused as e:
            results["error"] = f"Recipients refused: {e}"
            results["smtp_command_that_failed"] = "RCPT TO"
            logger.error(f"❌ Recipients refused: {e}")
            logger.error("This means Yahoo rejected the recipient email address")

        except smtplib.SMTPDataError as e:
            results["error"] = f"SMTP Data Error: {e}"
            # Extract error code from exception
            if hasattr(e, 'smtp_code'):
                results["yahoo_error_code"] = e.smtp_code
            results["smtp_command_that_failed"] = "DATA" if results["auth_ok"] else "Unknown"
            logger.error(f"❌ SMTP 550 Data Error: {e}")
            logger.error("This means Yahoo is rejecting the recipient or message content")

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"❌ Unexpected error: {e}")
            logger.error(traceback.format_exc())

        logger.info("=" * 80)
        logger.info("MINIMAL SMTP TEST RESULTS:")
        logger.info(f"  Connection: {'✅' if results['connection_ok'] else '❌'}")
        logger.info(f"  Authentication: {'✅' if results['auth_ok'] else '❌'}")
        logger.info(f"  Send: {'✅' if results['send_ok'] else '❌'}")
        if results['error']:
            logger.info(f"  Error: {results['error']}")
            logger.info(f"  Failed Command: {results['smtp_command_that_failed']}")
        logger.info("=" * 80)

        return results

    def diagnose_yahoo_account(self) -> List[str]:
        """
        Check Yahoo SMTP account for common configuration issues.

        Returns:
            List of configuration issues found (empty if all OK)
        """
        issues = []

        logger.info("=" * 80)
        logger.info("YAHOO SMTP CONFIGURATION DIAGNOSTICS")
        logger.info("=" * 80)

        # Check configuration
        logger.info(f"Checking configuration...")
        logger.info(f"  SMTP Host: {self.smtp_host}")
        logger.info(f"  SMTP Port: {self.smtp_port}")
        logger.info(f"  SMTP Username: {self.smtp_username}")
        logger.info(f"  Email From: {self.email_from}")
        logger.info(f"  Use TLS: {self.smtp_use_tls}")

        if self.email_from != self.smtp_username:
            issue = f"email_from ({self.email_from}) doesn't match smtp_username ({self.smtp_username})"
            issues.append(issue)
            logger.error(f"❌ {issue}")
        else:
            logger.info("✅ email_from matches smtp_username")

        if self.smtp_port != 587:
            issue = f"Yahoo requires port 587 for TLS (current: {self.smtp_port})"
            issues.append(issue)
            logger.error(f"❌ {issue}")
        else:
            logger.info("✅ Port 587 (correct for Yahoo TLS)")

        if not self.smtp_use_tls:
            issue = "Yahoo requires TLS (smtp_use_tls=False)"
            issues.append(issue)
            logger.error(f"❌ {issue}")
        else:
            logger.info("✅ TLS enabled")

        # Check password format
        logger.info(f"Checking password format...")
        logger.info(f"  Password length: {len(self.smtp_password)}")
        logger.info(f"  Password has spaces: {' ' in self.smtp_password}")
        logger.info(f"  Password is alphanumeric: {self.smtp_password.isalnum()}")

        if ' ' in self.smtp_password:
            issue = "Password contains spaces (should be 16-char app password with no spaces)"
            issues.append(issue)
            logger.error(f"❌ {issue}")
        else:
            logger.info("✅ No spaces in password")

        if len(self.smtp_password) != 16:
            issue = f"Password length is {len(self.smtp_password)}, Yahoo app password should be 16 characters"
            issues.append(issue)
            logger.warning(f"⚠️  {issue}")
        else:
            logger.info("✅ Password length is 16 characters")

        if not self.smtp_password.isalnum():
            issue = "Password contains non-alphanumeric characters (Yahoo app passwords are alphanumeric only)"
            issues.append(issue)
            logger.warning(f"⚠️  {issue}")
        else:
            logger.info("✅ Password is alphanumeric")

        logger.info("=" * 80)
        if issues:
            logger.info(f"FOUND {len(issues)} CONFIGURATION ISSUE(S)")
            for i, issue in enumerate(issues, 1):
                logger.info(f"  {i}. {issue}")
        else:
            logger.info("✅ ALL CONFIGURATION CHECKS PASSED")
        logger.info("=" * 80)

        return issues

    def test_with_email_message(self, to_email: str) -> Dict[str, Any]:
        """
        Test with newer EmailMessage API instead of MIME.

        Args:
            to_email: Recipient email address

        Returns:
            Dictionary with test results
        """
        from email.message import EmailMessage

        results = {
            "email_message_api": False,
            "sendmail_api": False,
            "error": None
        }

        logger.info("=" * 80)
        logger.info("TESTING WITH EmailMessage API")
        logger.info("=" * 80)

        try:
            msg = EmailMessage()
            msg['Subject'] = 'SMTP API Test'
            msg['From'] = self.smtp_username  # Must match auth
            msg['To'] = to_email
            msg.set_content('Test email body - testing EmailMessage API')

            logger.info(f"Created EmailMessage from {msg['From']} to {msg['To']}")

            smtp = self._create_smtp_connection(debug_level=2)
            try:
                # Try send_message (higher level)
                logger.info("Attempting send_message()...")
                smtp.send_message(msg)
                results["email_message_api"] = True
                logger.info("✅ EmailMessage API worked")

            except Exception as e:
                logger.error(f"❌ EmailMessage API failed: {e}")
                results["error"] = f"send_message failed: {e}"

                # Try lower-level sendmail
                try:
                    logger.info("Attempting lower-level sendmail()...")
                    smtp.sendmail(
                        self.smtp_username,
                        [to_email],
                        msg.as_string()
                    )
                    results["sendmail_api"] = True
                    logger.info("✅ sendmail() worked")
                except Exception as e2:
                    logger.error(f"❌ sendmail() also failed: {e2}")
                    results["error"] = f"Both APIs failed. send_message: {e}, sendmail: {e2}"
            finally:
                smtp.quit()

        except Exception as e:
            logger.error(f"❌ Connection/setup failed: {e}")
            results["error"] = f"Connection failed: {e}"

        logger.info("=" * 80)
        logger.info("EmailMessage API TEST RESULTS:")
        logger.info(f"  send_message(): {'✅' if results['email_message_api'] else '❌'}")
        logger.info(f"  sendmail(): {'✅' if results['sendmail_api'] else '❌'}")
        if results['error']:
            logger.info(f"  Error: {results['error']}")
        logger.info("=" * 80)

        return results

    async def send_invoice_email(
        self,
        invoice_data: Dict[str, Any],
        recipient_email: str,
        recipient_name: str,
        pdf_data: bytes,
        payment_link_url: Optional[str] = None
    ) -> EmailSendResult:
        """
        Send invoice notification email with PDF attachment.

        Args:
            invoice_data: Invoice document from MongoDB
            recipient_email: Customer email address
            recipient_name: Customer name
            pdf_data: PDF invoice bytes

        Returns:
            EmailSendResult with send status
        """
        logger.info("=" * 80)
        logger.info("INVOICE EMAIL - Sending invoice email with PDF attachment")
        logger.info("=" * 80)
        logger.info(f"Recipient: {recipient_name} <{recipient_email}>")
        logger.info(f"Invoice: {invoice_data.get('invoice_number', 'N/A')}")

        try:
            # Render invoice email template
            invoice_number = invoice_data.get('invoice_number', 'N/A')
            company_name = invoice_data.get('company_name', 'N/A')
            invoice_date = invoice_data.get('invoice_date', 'N/A')
            due_date = invoice_data.get('due_date', 'N/A')
            total_amount = invoice_data.get('total_amount', 0.0)
            line_items = invoice_data.get('line_items', [])
            subtotal = invoice_data.get('subtotal', 0.0)
            tax_amount = invoice_data.get('tax_amount', 0.0)

            # Convert Decimal128 to float in line_items for template rendering
            from bson import Decimal128
            processed_line_items = []
            for item in line_items:
                processed_item = item.copy()
                # Convert Decimal128 values to float
                for key in ['unit_price', 'amount', 'quantity']:
                    if key in processed_item:
                        value = processed_item[key]
                        if isinstance(value, Decimal128):
                            processed_item[key] = float(value.to_decimal())
                processed_line_items.append(processed_item)

            # Convert Decimal128 to float for totals, handle None
            if isinstance(total_amount, Decimal128):
                total_amount = float(total_amount.to_decimal())
            elif total_amount is None:
                total_amount = 0.0

            if isinstance(subtotal, Decimal128):
                subtotal = float(subtotal.to_decimal())
            elif subtotal is None:
                subtotal = 0.0

            if isinstance(tax_amount, Decimal128):
                tax_amount = float(tax_amount.to_decimal())
            elif tax_amount is None:
                tax_amount = 0.0

            # Template context
            context = {
                'customer_name': recipient_name,
                'invoice_number': invoice_number,
                'company_name': company_name,
                'invoice_date': invoice_date,
                'due_date': due_date,
                'total_amount': f"{total_amount:.2f}",
                'line_items': processed_line_items,
                'subtotal': f"{subtotal:.2f}",
                'tax_amount': f"{tax_amount:.2f}",
                'payment_link_url': payment_link_url
            }

            # Render HTML and text templates
            body_html = template_service.render_template(
                'invoice_notification.html',
                context
            )
            body_text = template_service.render_template(
                'invoice_notification.txt',
                context
            )

            # Build email message with attachment
            msg = self._build_email_message(
                to_email=recipient_email,
                to_name=recipient_name,
                subject=f"Invoice {invoice_number} from {settings.email_from_name}",
                body_html=body_html,
                body_text=body_text,
                attachments=[{
                    'data': pdf_data,
                    'filename': f"{invoice_number}.pdf"
                }]
            )

            # Send email via SMTP
            logger.info(f"Connecting to SMTP server: {self.smtp_host}:{self.smtp_port}")
            smtp = self._create_smtp_connection()

            try:
                logger.info(f"Sending invoice email to {recipient_email}...")
                smtp.sendmail(
                    self.email_from,
                    [recipient_email],
                    msg.as_string()
                )
                logger.info(f"✅ Invoice email sent successfully to {recipient_email}")

                return EmailSendResult(
                    success=True,
                    message=f"Invoice email sent to {recipient_email}",
                    recipient=recipient_email,
                    sent_at=datetime.now(timezone.utc).isoformat()
                )

            finally:
                smtp.quit()
                logger.info("SMTP connection closed")

        except Exception as e:
            logger.error(f"Failed to send invoice email: {e}", exc_info=True)
            return EmailSendResult(
                success=False,
                message="Failed to send invoice email",
                error=str(e),
                recipient=recipient_email
            )


# Create singleton instance
email_service = EmailService()
