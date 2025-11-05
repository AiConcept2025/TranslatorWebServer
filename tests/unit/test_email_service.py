"""
Unit tests for email service.
Tests email functionality with mocked SMTP connections.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import smtplib

from app.services.email_service import EmailService, EmailServiceError, email_service
from app.models.email import DocumentInfo, EmailRequest, TranslationNotificationContext


class TestEmailService:
    """Test suite for EmailService."""

    def test_email_service_initialization(self):
        """Test that email service initializes with correct configuration."""
        service = EmailService()

        assert service.smtp_host == "smtp.mail.yahoo.com"
        assert service.smtp_port == 587
        assert service.smtp_use_tls is True
        assert service.email_from_name == "Iris Solutions Translation Services"

    def test_validate_smtp_config_with_credentials(self):
        """Test SMTP configuration validation with valid credentials."""
        service = EmailService()

        # Mock the configuration
        with patch.object(service, 'smtp_username', 'test@yahoo.com'):
            with patch.object(service, 'smtp_password', 'password123'):
                with patch.object(service, 'email_from', 'test@yahoo.com'):
                    result = service._validate_smtp_config()
                    assert result is True

    def test_validate_smtp_config_missing_username(self):
        """Test validation fails when username is missing."""
        service = EmailService()

        with patch.object(service, 'smtp_username', None):
            with patch.object(service, 'smtp_password', 'password'):
                result = service._validate_smtp_config()
                assert result is False

    def test_validate_smtp_config_email_disabled(self):
        """Test validation fails when email is disabled."""
        service = EmailService()

        with patch.object(service, 'email_enabled', False):
            result = service._validate_smtp_config()
            assert result is False

    @patch('app.services.email_service.smtplib.SMTP')
    def test_create_smtp_connection_tls(self, mock_smtp):
        """Test creating SMTP connection with TLS."""
        service = EmailService()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance

        with patch.object(service, 'smtp_username', 'test@yahoo.com'):
            with patch.object(service, 'smtp_password', 'password123'):
                with patch.object(service, 'smtp_use_tls', True):
                    with patch.object(service, 'smtp_use_ssl', False):
                        connection = service._create_smtp_connection()

                        # Verify connection was established
                        mock_smtp.assert_called_once()
                        mock_smtp_instance.starttls.assert_called_once()
                        mock_smtp_instance.login.assert_called_once_with('test@yahoo.com', 'password123')

    @patch('app.services.email_service.smtplib.SMTP')
    def test_create_smtp_connection_auth_failure(self, mock_smtp):
        """Test SMTP connection with authentication failure."""
        service = EmailService()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance
        mock_smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, 'Authentication failed')

        with patch.object(service, 'smtp_username', 'test@yahoo.com'):
            with patch.object(service, 'smtp_password', 'wrong_password'):
                with patch.object(service, 'smtp_use_tls', True):
                    with patch.object(service, 'smtp_use_ssl', False):
                        with pytest.raises(EmailServiceError) as exc_info:
                            service._create_smtp_connection()

                        assert "authentication failed" in str(exc_info.value).lower()

    def test_build_email_message(self):
        """Test building MIME email message."""
        service = EmailService()

        with patch.object(service, 'email_from', 'sender@example.com'):
            with patch.object(service, 'email_from_name', 'Test Sender'):
                msg = service._build_email_message(
                    to_email="recipient@example.com",
                    to_name="Test Recipient",
                    subject="Test Subject",
                    body_html="<p>HTML Body</p>",
                    body_text="Plain Text Body"
                )

                assert msg['Subject'] == "Test Subject"
                assert "recipient@example.com" in msg['To']
                assert "Test Recipient" in msg['To']
                assert "sender@example.com" in msg['From']
                assert "Test Sender" in msg['From']

    def test_build_email_message_with_reply_to(self):
        """Test building email message with reply-to address."""
        service = EmailService()

        with patch.object(service, 'email_from', 'noreply@example.com'):
            with patch.object(service, 'email_from_name', 'Test Service'):
                msg = service._build_email_message(
                    to_email="user@example.com",
                    to_name="User",
                    subject="Test",
                    body_html="<p>Test</p>",
                    body_text="Test",
                    reply_to="support@example.com"
                )

                assert msg['Reply-To'] == "support@example.com"

    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_email_success(self, mock_smtp):
        """Test successful email sending."""
        service = EmailService()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance

        email_request = EmailRequest(
            to_email="test@example.com",
            to_name="Test User",
            subject="Test Email",
            body_html="<p>Test HTML</p>",
            body_text="Test Text"
        )

        with patch.object(service, '_validate_smtp_config', return_value=True):
            result = service.send_email(email_request)

            assert result.success is True
            assert result.recipient == "test@example.com"
            assert "sent successfully" in result.message.lower()
            assert result.sent_at is not None

    def test_send_email_config_invalid(self):
        """Test email sending with invalid configuration."""
        service = EmailService()

        email_request = EmailRequest(
            to_email="test@example.com",
            to_name="Test User",
            subject="Test",
            body_html="<p>Test</p>",
            body_text="Test"
        )

        with patch.object(service, '_validate_smtp_config', return_value=False):
            result = service.send_email(email_request)

            assert result.success is False
            assert "not configured" in result.message.lower()

    @patch('app.services.email_service.template_service')
    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_translation_notification_individual(self, mock_smtp, mock_template_service):
        """Test sending translation notification to individual customer."""
        service = EmailService()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance

        # Mock template rendering
        mock_template_service.render_template.side_effect = [
            "<html>Rendered HTML</html>",
            "Rendered Text"
        ]

        documents = [
            DocumentInfo(
                document_name="test.pdf",
                original_url="https://example.com/original",
                translated_url="https://example.com/translated"
            )
        ]

        with patch.object(service, '_validate_smtp_config', return_value=True):
            result = service.send_translation_notification(
                documents=documents,
                user_name="John Doe",
                user_email="john@example.com",
                company_name="Ind"
            )

            assert result.success is True
            assert result.recipient == "john@example.com"

            # Verify individual template was used
            calls = mock_template_service.render_template.call_args_list
            assert "individual_notification.html" in str(calls[0])

    @patch('app.services.email_service.template_service')
    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_translation_notification_corporate(self, mock_smtp, mock_template_service):
        """Test sending translation notification to corporate customer."""
        service = EmailService()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance

        # Mock template rendering
        mock_template_service.render_template.side_effect = [
            "<html>Corporate HTML</html>",
            "Corporate Text"
        ]

        documents = [
            DocumentInfo(
                document_name="report.docx",
                original_url="https://example.com/original",
                translated_url="https://example.com/translated"
            )
        ]

        with patch.object(service, '_validate_smtp_config', return_value=True):
            result = service.send_translation_notification(
                documents=documents,
                user_name="Alice Johnson",
                user_email="alice@company.com",
                company_name="Acme Corp"
            )

            assert result.success is True

            # Verify corporate template was used
            calls = mock_template_service.render_template.call_args_list
            assert "corporate_notification.html" in str(calls[0])

    @patch('app.services.email_service.template_service')
    @patch('app.services.email_service.smtplib.SMTP')
    def test_send_translation_notification_multiple_documents(self, mock_smtp, mock_template_service):
        """Test sending notification with multiple documents."""
        service = EmailService()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance

        mock_template_service.render_template.side_effect = [
            "<html>HTML</html>",
            "Text"
        ]

        documents = [
            DocumentInfo(
                document_name="file1.pdf",
                original_url="https://example.com/file1",
                translated_url="https://example.com/file1_trans"
            ),
            DocumentInfo(
                document_name="file2.docx",
                original_url="https://example.com/file2",
                translated_url="https://example.com/file2_trans"
            ),
            DocumentInfo(
                document_name="file3.xlsx",
                original_url="https://example.com/file3",
                translated_url="https://example.com/file3_trans"
            )
        ]

        with patch.object(service, '_validate_smtp_config', return_value=True):
            result = service.send_translation_notification(
                documents=documents,
                user_name="Test User",
                user_email="test@example.com",
                company_name="Ind"
            )

            assert result.success is True

            # Verify all documents were passed to template
            calls = mock_template_service.render_template.call_args_list
            context = calls[0][0][1]  # Get context from first call
            assert len(context['documents']) == 3

    @patch('app.services.email_service.smtplib.SMTP')
    def test_test_connection_success(self, mock_smtp):
        """Test SMTP connection testing."""
        service = EmailService()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance

        with patch.object(service, '_validate_smtp_config', return_value=True):
            result = service.test_connection()

            assert result['success'] is True
            assert "successful" in result['message'].lower()
            assert 'details' in result

    def test_test_connection_config_invalid(self):
        """Test connection testing with invalid configuration."""
        service = EmailService()

        with patch.object(service, '_validate_smtp_config', return_value=False):
            result = service.test_connection()

            assert result['success'] is False
            assert "not configured" in result['message'].lower()

    @patch('app.services.email_service.smtplib.SMTP')
    def test_test_connection_failure(self, mock_smtp):
        """Test connection testing with connection failure."""
        service = EmailService()
        mock_smtp.side_effect = smtplib.SMTPConnectError(421, 'Service unavailable')

        with patch.object(service, 'smtp_username', 'test@yahoo.com'):
            with patch.object(service, 'smtp_password', 'password'):
                with patch.object(service, 'email_from', 'test@yahoo.com'):
                    result = service.test_connection()

                    assert result['success'] is False
                    assert 'error' in result


class TestDocumentInfo:
    """Test DocumentInfo model."""

    def test_document_info_valid(self):
        """Test creating valid DocumentInfo."""
        doc = DocumentInfo(
            document_name="test.pdf",
            original_url="https://example.com/original",
            translated_url="https://example.com/translated"
        )

        assert doc.document_name == "test.pdf"
        assert doc.original_url == "https://example.com/original"
        assert doc.translated_url == "https://example.com/translated"

    def test_document_info_empty_name(self):
        """Test validation of empty document name."""
        with pytest.raises(ValueError):
            DocumentInfo(
                document_name="",
                original_url="https://example.com/original",
                translated_url="https://example.com/translated"
            )

    def test_document_info_invalid_url(self):
        """Test validation of invalid URL."""
        with pytest.raises(ValueError):
            DocumentInfo(
                document_name="test.pdf",
                original_url="not-a-url",
                translated_url="https://example.com/translated"
            )


class TestTranslationNotificationContext:
    """Test TranslationNotificationContext model."""

    def test_context_is_individual(self):
        """Test identifying individual customer."""
        doc = DocumentInfo(
            document_name="test.pdf",
            original_url="https://example.com/original",
            translated_url="https://example.com/translated"
        )

        context = TranslationNotificationContext(
            user_name="John Doe",
            user_email="john@example.com",
            company_name="Ind",
            documents=[doc]
        )

        assert context.is_individual is True
        assert context.template_type.value == "individual_notification"

    def test_context_is_corporate(self):
        """Test identifying corporate customer."""
        doc = DocumentInfo(
            document_name="test.pdf",
            original_url="https://example.com/original",
            translated_url="https://example.com/translated"
        )

        context = TranslationNotificationContext(
            user_name="Alice Johnson",
            user_email="alice@company.com",
            company_name="Acme Corp",
            documents=[doc]
        )

        assert context.is_individual is False
        assert context.template_type.value == "corporate_notification"

    def test_context_no_documents(self):
        """Test validation of empty documents list."""
        with pytest.raises(ValueError):
            TranslationNotificationContext(
                user_name="Test",
                user_email="test@example.com",
                company_name="Ind",
                documents=[]
            )
