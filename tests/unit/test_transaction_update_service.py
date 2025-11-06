"""
Unit tests for transaction update service.
Tests database update operations with mocked MongoDB connections.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from app.services.transaction_update_service import (
    TransactionUpdateService,
    transaction_update_service
)


class TestTransactionUpdateService:
    """Test suite for TransactionUpdateService."""

    def test_service_initialization(self):
        """Test that service initializes correctly."""
        service = TransactionUpdateService()
        assert service is not None

    def test_generate_translated_name_simple(self):
        """Test generating translated name for simple file."""
        service = TransactionUpdateService()

        result = service._generate_translated_name("report.pdf")
        assert result == "report_translated.pdf"

    def test_generate_translated_name_with_language_code(self):
        """Test removing language code from translated name."""
        service = TransactionUpdateService()

        # Should remove _en suffix
        result = service._generate_translated_name("document_en.docx")
        assert result == "document_translated.docx"

        # Should remove _es suffix
        result = service._generate_translated_name("file_es.pdf")
        assert result == "file_translated.pdf"

    def test_generate_translated_name_complex(self):
        """Test generating name for complex filename."""
        service = TransactionUpdateService()

        # Keep underscores but remove language code
        result = service._generate_translated_name("my_complex_file_fr.xlsx")
        assert result == "my_complex_file_translated.xlsx"

    def test_generate_translated_name_no_extension(self):
        """Test generating name for file without extension."""
        service = TransactionUpdateService()

        result = service._generate_translated_name("document")
        assert result == "document_translated"

    @pytest.mark.asyncio
    async def test_update_enterprise_transaction_success(self):
        """Test successful enterprise transaction update."""
        service = TransactionUpdateService()

        # Mock database collection
        mock_collection = AsyncMock()

        # Mock transaction document
        mock_transaction = {
            "transaction_id": "TXN-ABC123",
            "company_name": "Acme Corp",
            "documents": [
                {
                    "document_name": "report.pdf",
                    "original_url": "https://drive.google.com/original",
                    "translated_url": None,
                    "translated_name": None
                }
            ]
        }

        # Mock database responses
        mock_collection.find_one.return_value = mock_transaction
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        mock_collection.update_one.return_value = mock_update_result

        # Mock updated transaction (with translated fields)
        updated_transaction = mock_transaction.copy()
        updated_transaction["documents"][0]["translated_url"] = "https://drive.google.com/translated"
        updated_transaction["documents"][0]["translated_name"] = "report_translated.pdf"
        mock_collection.find_one.side_effect = [mock_transaction, updated_transaction]

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.update_enterprise_transaction(
                transaction_id="TXN-ABC123",
                file_name="report.pdf",
                file_url="https://drive.google.com/translated"
            )

        assert result["success"] is True
        assert result["transaction_id"] == "TXN-ABC123"
        assert result["document_name"] == "report.pdf"
        assert result["translated_url"] == "https://drive.google.com/translated"
        assert result["translated_name"] == "report_translated.pdf"
        assert "transaction" in result

    @pytest.mark.asyncio
    async def test_update_enterprise_transaction_not_found(self):
        """Test enterprise transaction update when transaction not found."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.update_enterprise_transaction(
                transaction_id="TXN-NOTFOUND",
                file_name="report.pdf",
                file_url="https://drive.google.com/translated"
            )

        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["transaction_id"] == "TXN-NOTFOUND"

    @pytest.mark.asyncio
    async def test_update_enterprise_transaction_document_not_found(self):
        """Test enterprise transaction update when document not found in array."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()

        # Transaction exists but document name doesn't match
        mock_transaction = {
            "transaction_id": "TXN-ABC123",
            "documents": [
                {
                    "document_name": "other_file.pdf",
                    "original_url": "https://drive.google.com/other"
                }
            ]
        }
        mock_collection.find_one.return_value = mock_transaction

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.update_enterprise_transaction(
                transaction_id="TXN-ABC123",
                file_name="missing_file.pdf",
                file_url="https://drive.google.com/translated"
            )

        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert "missing_file.pdf" in result["error"]

    @pytest.mark.asyncio
    async def test_update_enterprise_transaction_no_modifications(self):
        """Test enterprise transaction update when no modifications are made."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()

        mock_transaction = {
            "transaction_id": "TXN-ABC123",
            "documents": [
                {"document_name": "report.pdf", "original_url": "https://example.com"}
            ]
        }
        mock_collection.find_one.return_value = mock_transaction

        # Update returns 0 modified documents
        mock_update_result = Mock()
        mock_update_result.modified_count = 0
        mock_collection.update_one.return_value = mock_update_result

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.update_enterprise_transaction(
                transaction_id="TXN-ABC123",
                file_name="report.pdf",
                file_url="https://drive.google.com/translated"
            )

        assert result["success"] is False
        assert "no modifications" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_update_enterprise_transaction_database_error(self):
        """Test handling database errors in enterprise transaction update."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()
        mock_collection.find_one.side_effect = Exception("Database connection failed")

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.update_enterprise_transaction(
                transaction_id="TXN-ABC123",
                file_name="report.pdf",
                file_url="https://drive.google.com/translated"
            )

        assert result["success"] is False
        assert "database error" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_update_individual_transaction_success(self):
        """Test successful individual transaction update."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()

        mock_transaction = {
            "transaction_id": "TXN-XYZ789",
            "user_id": "user@example.com",
            "documents": [
                {
                    "document_name": "document.docx",
                    "original_url": "https://drive.google.com/original"
                }
            ]
        }

        mock_collection.find_one.return_value = mock_transaction
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        mock_collection.update_one.return_value = mock_update_result

        # Mock updated transaction
        updated_transaction = mock_transaction.copy()
        updated_transaction["documents"][0]["translated_url"] = "https://drive.google.com/translated"
        mock_collection.find_one.side_effect = [mock_transaction, updated_transaction]

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.user_transactions = mock_collection

            result = await service.update_individual_transaction(
                transaction_id="TXN-XYZ789",
                file_name="document.docx",
                file_url="https://drive.google.com/translated"
            )

        assert result["success"] is True
        assert result["transaction_id"] == "TXN-XYZ789"
        assert result["translated_name"] == "document_translated.docx"

    @pytest.mark.asyncio
    async def test_update_individual_transaction_not_found(self):
        """Test individual transaction update when transaction not found."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.user_transactions = mock_collection

            result = await service.update_individual_transaction(
                transaction_id="TXN-NOTFOUND",
                file_name="document.docx",
                file_url="https://drive.google.com/translated"
            )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_check_transaction_complete_all_translated(self):
        """Test checking transaction completion when all documents are translated."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()

        # All documents have translated_url
        mock_transaction = {
            "transaction_id": "TXN-ABC123",
            "documents": [
                {
                    "document_name": "file1.pdf",
                    "translated_url": "https://drive.google.com/file1"
                },
                {
                    "document_name": "file2.docx",
                    "translated_url": "https://drive.google.com/file2"
                }
            ]
        }
        mock_collection.find_one.return_value = mock_transaction
        mock_collection.update_one.return_value = Mock()

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.check_transaction_complete(
                transaction_id="TXN-ABC123",
                is_enterprise=True
            )

        assert result is True
        # Verify status was updated to completed
        mock_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_transaction_complete_partial(self):
        """Test checking transaction completion when some documents are not translated."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()

        # Some documents missing translated_url
        mock_transaction = {
            "transaction_id": "TXN-ABC123",
            "documents": [
                {
                    "document_name": "file1.pdf",
                    "translated_url": "https://drive.google.com/file1"
                },
                {
                    "document_name": "file2.docx",
                    "translated_url": None  # Not yet translated
                }
            ]
        }
        mock_collection.find_one.return_value = mock_transaction

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.check_transaction_complete(
                transaction_id="TXN-ABC123",
                is_enterprise=True
            )

        assert result is False
        # Verify status was NOT updated
        mock_collection.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_transaction_complete_individual(self):
        """Test checking completion for individual transaction."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()

        mock_transaction = {
            "transaction_id": "TXN-XYZ789",
            "documents": [
                {
                    "document_name": "file.pdf",
                    "translated_url": "https://drive.google.com/file"
                }
            ]
        }
        mock_collection.find_one.return_value = mock_transaction
        mock_collection.update_one.return_value = Mock()

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.user_transactions = mock_collection

            result = await service.check_transaction_complete(
                transaction_id="TXN-XYZ789",
                is_enterprise=False  # Individual customer
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_check_transaction_complete_no_documents(self):
        """Test checking completion when transaction has no documents."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()

        mock_transaction = {
            "transaction_id": "TXN-ABC123",
            "documents": []
        }
        mock_collection.find_one.return_value = mock_transaction

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.check_transaction_complete(
                transaction_id="TXN-ABC123",
                is_enterprise=True
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_check_transaction_complete_transaction_not_found(self):
        """Test checking completion when transaction doesn't exist."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.check_transaction_complete(
                transaction_id="TXN-NOTFOUND",
                is_enterprise=True
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_enterprise_transaction_multiple_documents(self):
        """Test updating one document in a transaction with multiple documents."""
        service = TransactionUpdateService()

        mock_collection = AsyncMock()

        # Transaction with multiple documents
        mock_transaction = {
            "transaction_id": "TXN-ABC123",
            "documents": [
                {
                    "document_name": "file1.pdf",
                    "original_url": "https://drive.google.com/file1",
                    "translated_url": "https://drive.google.com/file1_trans"  # Already translated
                },
                {
                    "document_name": "file2.docx",
                    "original_url": "https://drive.google.com/file2",
                    "translated_url": None  # Being updated now
                },
                {
                    "document_name": "file3.xlsx",
                    "original_url": "https://drive.google.com/file3",
                    "translated_url": None  # Not yet translated
                }
            ]
        }

        mock_collection.find_one.return_value = mock_transaction
        mock_update_result = Mock()
        mock_update_result.modified_count = 1
        mock_collection.update_one.return_value = mock_update_result

        # Mock updated transaction
        updated_transaction = mock_transaction.copy()
        updated_transaction["documents"][1]["translated_url"] = "https://drive.google.com/file2_trans"
        mock_collection.find_one.side_effect = [mock_transaction, updated_transaction]

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = mock_collection

            result = await service.update_enterprise_transaction(
                transaction_id="TXN-ABC123",
                file_name="file2.docx",  # Update second document
                file_url="https://drive.google.com/file2_trans"
            )

        assert result["success"] is True
        assert result["document_name"] == "file2.docx"
        assert result["translated_name"] == "file2_translated.docx"

    @pytest.mark.asyncio
    async def test_update_enterprise_transaction_database_unavailable(self):
        """Test handling when database collection is unavailable."""
        service = TransactionUpdateService()

        with patch('app.services.transaction_update_service.database') as mock_db:
            mock_db.translation_transactions = None  # Database not available

            result = await service.update_enterprise_transaction(
                transaction_id="TXN-ABC123",
                file_name="report.pdf",
                file_url="https://drive.google.com/translated"
            )

        assert result["success"] is False
        assert "database connection error" in result["error"].lower()

    def test_singleton_instance(self):
        """Test that transaction_update_service is a singleton instance."""
        assert transaction_update_service is not None
        assert isinstance(transaction_update_service, TransactionUpdateService)
