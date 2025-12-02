"""
Unit tests for submit service.
Tests file submission processing logic with mocked dependencies.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from app.services.submit_service import SubmitService, submit_service
from app.models.email import DocumentInfo


class TestSubmitService:
    """Test suite for SubmitService."""

    def test_service_initialization(self):
        """Test that service initializes correctly."""
        service = SubmitService()
        assert service is not None

    def test_extract_user_name_from_transaction(self):
        """Test extracting user name from transaction with user_name field."""
        service = SubmitService()

        transaction = {
            "user_name": "John Doe",
            "user_id": "john.doe@example.com"
        }

        result = service._extract_user_name(transaction, "john.doe@example.com")
        assert result == "John Doe"

    def test_extract_user_name_from_user_id(self):
        """Test extracting user name from user_id when user_name not present."""
        service = SubmitService()

        transaction = {
            "user_id": "jane.smith@example.com"
        }

        result = service._extract_user_name(transaction, "jane@example.com")
        assert result == "Jane Smith"

    def test_extract_user_name_from_email(self):
        """Test extracting user name from email address."""
        service = SubmitService()

        transaction = {
            "user_id": "bob_jones@example.com"
        }

        result = service._extract_user_name(transaction, "bob_jones@example.com")
        assert result == "Bob Jones"

    def test_extract_user_name_fallback(self):
        """Test fallback to 'User' when extraction fails."""
        service = SubmitService()

        transaction = {}

        # When no @ in email, the code still attempts to parse it
        # "invalid-email" -> splits on @ -> ["invalid-email"]
        # -> takes first part -> "invalid-email"
        # -> replaces - with . -> "invalid.email"
        # -> splits on . and capitalizes -> "Invalid Email"
        result = service._extract_user_name(transaction, "invalid-email")
        assert result == "Invalid Email"

    @pytest.mark.asyncio
    async def test_process_submission_enterprise_success(self):
        """Test successful submission processing for enterprise customer."""
        service = SubmitService()

        # Mock transaction update service
        mock_update_result = {
            "success": True,
            "transaction_id": "TXN-ABC123",
            "document_name": "report.pdf",
            "translated_url": "https://drive.google.com/translated",
            "translated_name": "report_translated.pdf",
            "transaction": {
                "transaction_id": "TXN-ABC123",
                "user_name": "Alice Johnson",
                "documents": [
                    {
                        "file_name": "report.pdf",
                        "original_url": "https://drive.google.com/original",
                        "translated_url": "https://drive.google.com/translated"
                    }
                ],
                "completed_documents": 1,
                "total_documents": 1,
                "batch_email_sent": False
            }
        }

        # Mock email service
        mock_email_result = Mock()
        mock_email_result.success = True
        mock_email_result.error = None

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            with patch('app.services.submit_service.email_service') as mock_email:
                mock_txn_service.update_enterprise_transaction = AsyncMock(return_value=mock_update_result)
                mock_txn_service.check_transaction_complete = AsyncMock(return_value=True)
                mock_email.send_translation_notification.return_value = mock_email_result

                result = await service.process_submission(
                    file_name="report.pdf",
                    file_url="https://drive.google.com/translated",
                    user_email="alice@acme.com",
                    company_name="Acme Corp",
                    transaction_id="TXN-ABC123"
                )

        assert result["status"] == "success"
        assert result["transaction_id"] == "TXN-ABC123"
        assert result["email_sent"] is True
        assert result["all_documents_complete"] is True
        assert "documents_count" in result

    @pytest.mark.asyncio
    async def test_process_submission_individual_success(self):
        """Test successful submission processing for individual customer."""
        service = SubmitService()

        mock_update_result = {
            "success": True,
            "transaction_id": "TXN-XYZ789",
            "document_name": "document.docx",
            "translated_url": "https://drive.google.com/translated",
            "translated_name": "document_translated.docx",
            "transaction": {
                "transaction_id": "TXN-XYZ789",
                "user_id": "john.doe@example.com",
                "documents": [
                    {
                        "file_name": "document.docx",
                        "original_url": "https://drive.google.com/original",
                        "translated_url": "https://drive.google.com/translated"
                    }
                ],
                "completed_documents": 0,
                "total_documents": 1,
                "batch_email_sent": False
            }
        }

        mock_email_result = Mock()
        mock_email_result.success = True

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            with patch('app.services.submit_service.email_service') as mock_email:
                mock_txn_service.update_individual_transaction = AsyncMock(return_value=mock_update_result)
                mock_txn_service.check_transaction_complete = AsyncMock(return_value=False)
                mock_email.send_translation_notification.return_value = mock_email_result

                result = await service.process_submission(
                    file_name="document.docx",
                    file_url="https://drive.google.com/translated",
                    user_email="john@example.com",
                    company_name="Ind",  # Individual customer
                    transaction_id="TXN-XYZ789"
                )

        assert result["status"] == "success"
        # Email is blocked until all documents are complete
        assert result["email_sent"] is False
        assert result["all_documents_complete"] is False

    @pytest.mark.asyncio
    async def test_process_submission_database_update_failed(self):
        """Test handling database update failure."""
        service = SubmitService()

        mock_update_result = {
            "success": False,
            "error": "Transaction TXN-NOTFOUND not found"
        }

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            mock_txn_service.update_enterprise_transaction = AsyncMock(return_value=mock_update_result)

            result = await service.process_submission(
                file_name="report.pdf",
                file_url="https://drive.google.com/translated",
                user_email="test@example.com",
                company_name="Test Corp",
                transaction_id="TXN-NOTFOUND"
            )

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()
        assert result["email_sent"] is False

    @pytest.mark.asyncio
    async def test_process_submission_no_transaction_data(self):
        """Test handling when transaction data is not available."""
        service = SubmitService()

        mock_update_result = {
            "success": True,
            "transaction_id": "TXN-ABC123",
            # Missing "transaction" field
        }

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            mock_txn_service.update_enterprise_transaction = AsyncMock(return_value=mock_update_result)
            mock_txn_service.check_transaction_complete = AsyncMock(return_value=False)

            result = await service.process_submission(
                file_name="report.pdf",
                file_url="https://drive.google.com/translated",
                user_email="test@example.com",
                company_name="Test Corp",
                transaction_id="TXN-ABC123"
            )

        assert result["status"] == "success"
        assert result["email_sent"] is False
        assert "unavailable" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_process_submission_no_translated_documents(self):
        """Test handling when no documents have been translated yet."""
        service = SubmitService()

        mock_update_result = {
            "success": True,
            "transaction_id": "TXN-ABC123",
            "transaction": {
                "transaction_id": "TXN-ABC123",
                "documents": [
                    {
                        "file_name": "report.pdf",
                        "original_url": "https://drive.google.com/original",
                        "translated_url": None  # Not translated
                    }
                ],
                "completed_documents": 0,
                "total_documents": 1,
                "batch_email_sent": False
            }
        }

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            mock_txn_service.update_enterprise_transaction = AsyncMock(return_value=mock_update_result)
            mock_txn_service.check_transaction_complete = AsyncMock(return_value=False)

            result = await service.process_submission(
                file_name="report.pdf",
                file_url="https://drive.google.com/translated",
                user_email="test@example.com",
                company_name="Test Corp",
                transaction_id="TXN-ABC123"
            )

        assert result["status"] == "success"
        assert result["email_sent"] is False
        assert "no translated documents" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_process_submission_email_failure(self):
        """Test handling email notification failure."""
        service = SubmitService()

        mock_update_result = {
            "success": True,
            "transaction_id": "TXN-ABC123",
            "document_name": "report.pdf",
            "translated_url": "https://drive.google.com/translated",
            "transaction": {
                "transaction_id": "TXN-ABC123",
                "user_name": "Test User",
                "documents": [
                    {
                        "file_name": "report.pdf",
                        "original_url": "https://drive.google.com/original",
                        "translated_url": "https://drive.google.com/translated"
                    }
                ],
                "completed_documents": 1,
                "total_documents": 1,
                "batch_email_sent": False
            }
        }

        mock_email_result = Mock()
        mock_email_result.success = False
        mock_email_result.error = "SMTP connection failed"

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            with patch('app.services.submit_service.email_service') as mock_email:
                mock_txn_service.update_enterprise_transaction = AsyncMock(return_value=mock_update_result)
                mock_txn_service.check_transaction_complete = AsyncMock(return_value=True)
                mock_email.send_translation_notification.return_value = mock_email_result

                result = await service.process_submission(
                    file_name="report.pdf",
                    file_url="https://drive.google.com/translated",
                    user_email="test@example.com",
                    company_name="Test Corp",
                    transaction_id="TXN-ABC123"
                )

        assert result["status"] == "success"
        assert result["email_sent"] is False
        assert "email_error" in result
        assert result["email_error"] == "SMTP connection failed"

    @pytest.mark.asyncio
    async def test_process_submission_multiple_documents(self):
        """Test processing with multiple translated documents."""
        service = SubmitService()

        mock_update_result = {
            "success": True,
            "transaction_id": "TXN-ABC123",
            "document_name": "file3.pdf",
            "translated_url": "https://drive.google.com/file3_trans",
            "transaction": {
                "transaction_id": "TXN-ABC123",
                "user_name": "Test User",
                "documents": [
                    {
                        "file_name": "file1.pdf",
                        "original_url": "https://drive.google.com/file1",
                        "translated_url": "https://drive.google.com/file1_trans"
                    },
                    {
                        "file_name": "file2.docx",
                        "original_url": "https://drive.google.com/file2",
                        "translated_url": "https://drive.google.com/file2_trans"
                    },
                    {
                        "file_name": "file3.pdf",
                        "original_url": "https://drive.google.com/file3",
                        "translated_url": "https://drive.google.com/file3_trans"
                    }
                ],
                "completed_documents": 3,
                "total_documents": 3,
                "batch_email_sent": False
            }
        }

        mock_email_result = Mock()
        mock_email_result.success = True

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            with patch('app.services.submit_service.email_service') as mock_email:
                mock_txn_service.update_enterprise_transaction = AsyncMock(return_value=mock_update_result)
                mock_txn_service.check_transaction_complete = AsyncMock(return_value=True)
                mock_email.send_translation_notification.return_value = mock_email_result

                result = await service.process_submission(
                    file_name="file3.pdf",
                    file_url="https://drive.google.com/file3_trans",
                    user_email="test@example.com",
                    company_name="Test Corp",
                    transaction_id="TXN-ABC123"
                )

        assert result["status"] == "success"
        assert result["documents_count"] == 3
        assert result["all_documents_complete"] is True

    @pytest.mark.asyncio
    async def test_process_submission_exception_handling(self):
        """Test handling unexpected exceptions."""
        service = SubmitService()

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            mock_txn_service.update_enterprise_transaction = AsyncMock(
                side_effect=Exception("Unexpected error")
            )

            result = await service.process_submission(
                file_name="report.pdf",
                file_url="https://drive.google.com/translated",
                user_email="test@example.com",
                company_name="Test Corp",
                transaction_id="TXN-ABC123"
            )

        assert result["status"] == "error"
        assert "unexpected error" in result["message"].lower()
        assert result["email_sent"] is False

    @pytest.mark.asyncio
    async def test_process_submission_customer_type_routing(self):
        """Test that customer type correctly routes to appropriate service method."""
        service = SubmitService()

        mock_result = {
            "success": True,
            "transaction_id": "TXN-ABC123",
            "transaction": {
                "transaction_id": "TXN-ABC123",
                "user_name": "Test User",
                "documents": [
                    {
                        "file_name": "test.pdf",
                        "original_url": "https://drive.google.com/original",
                        "translated_url": "https://drive.google.com/translated"
                    }
                ],
                "completed_documents": 1,
                "total_documents": 1,
                "batch_email_sent": False
            }
        }

        mock_email_result = Mock()
        mock_email_result.success = True

        with patch('app.services.submit_service.transaction_update_service') as mock_txn_service:
            with patch('app.services.submit_service.email_service') as mock_email:
                mock_txn_service.update_enterprise_transaction = AsyncMock(return_value=mock_result)
                mock_txn_service.update_individual_transaction = AsyncMock(return_value=mock_result)
                mock_txn_service.check_transaction_complete = AsyncMock(return_value=False)
                mock_email.send_translation_notification.return_value = mock_email_result

                # Test enterprise routing
                await service.process_submission(
                    file_name="test.pdf",
                    file_url="https://drive.google.com/translated",
                    user_email="test@acme.com",
                    company_name="Acme Corp",
                    transaction_id="TXN-ABC123"
                )
                mock_txn_service.update_enterprise_transaction.assert_called_once()
                mock_txn_service.update_individual_transaction.assert_not_called()

                # Reset mocks
                mock_txn_service.update_enterprise_transaction.reset_mock()
                mock_txn_service.update_individual_transaction.reset_mock()

                # Test individual routing
                await service.process_submission(
                    file_name="test.pdf",
                    file_url="https://drive.google.com/translated",
                    user_email="test@example.com",
                    company_name="Ind",
                    transaction_id="TXN-XYZ789"
                )
                mock_txn_service.update_individual_transaction.assert_called_once()
                mock_txn_service.update_enterprise_transaction.assert_not_called()

    def test_singleton_instance(self):
        """Test that submit_service is a singleton instance."""
        assert submit_service is not None
        assert isinstance(submit_service, SubmitService)
