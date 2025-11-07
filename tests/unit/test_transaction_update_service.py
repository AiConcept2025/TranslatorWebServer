"""
Unit tests for transaction update service.
Tests database update operations with mocked MongoDB connections.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from app.services.transaction_update_service import (
    TransactionUpdateService,
    transaction_update_service,
    normalize_filename_for_comparison,
    normalize_filename_for_lookup
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
                    "file_name": "report.pdf",
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
                    "file_name": "other_file.pdf",
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
                {"file_name": "report.pdf", "original_url": "https://example.com"}
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
                    "file_name": "document.docx",
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
                    "file_name": "file1.pdf",
                    "translated_url": "https://drive.google.com/file1"
                },
                {
                    "file_name": "file2.docx",
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
                    "file_name": "file1.pdf",
                    "translated_url": "https://drive.google.com/file1"
                },
                {
                    "file_name": "file2.docx",
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
                    "file_name": "file.pdf",
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
                    "file_name": "file1.pdf",
                    "original_url": "https://drive.google.com/file1",
                    "translated_url": "https://drive.google.com/file1_trans"  # Already translated
                },
                {
                    "file_name": "file2.docx",
                    "original_url": "https://drive.google.com/file2",
                    "translated_url": None  # Being updated now
                },
                {
                    "file_name": "file3.xlsx",
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


class TestFilenameNormalization:
    """Test filename normalization functions for extension-agnostic comparison."""

    def test_normalize_for_comparison_basic(self):
        """Test basic filename normalization."""
        assert normalize_filename_for_comparison("report.pdf") == "report"
        assert normalize_filename_for_comparison("report.docx") == "report"
        assert normalize_filename_for_comparison("document.txt") == "document"

    def test_normalize_for_comparison_with_translated_suffix(self):
        """Test normalization with _translated suffix."""
        assert normalize_filename_for_comparison("report_translated.pdf") == "report"
        assert normalize_filename_for_comparison("report_translated.docx") == "report"
        assert normalize_filename_for_comparison("document_translated.txt") == "document"

    def test_normalize_for_comparison_case_insensitive(self):
        """Test case-insensitive normalization."""
        assert normalize_filename_for_comparison("Report.PDF") == "report"
        assert normalize_filename_for_comparison("DOCUMENT_TRANSLATED.DOCX") == "document"
        assert normalize_filename_for_comparison("MyFile.TxT") == "myfile"

    def test_normalize_for_comparison_multiple_dots(self):
        """Test filenames with multiple dots."""
        assert normalize_filename_for_comparison("file.backup.pdf") == "file.backup"
        assert normalize_filename_for_comparison("my.document.v2.docx") == "my.document.v2"
        assert normalize_filename_for_comparison("report.2024.03.15.pdf") == "report.2024.03.15"

    def test_normalize_for_comparison_special_characters(self):
        """Test filenames with special characters."""
        assert normalize_filename_for_comparison("Kevin questions[81].docx") == "kevin questions[81]"
        assert normalize_filename_for_comparison("file (copy).pdf") == "file (copy)"
        assert normalize_filename_for_comparison("report_v1.0.pdf") == "report_v1.0"

    def test_normalize_for_comparison_real_world_bug(self):
        """Test the actual scenario from the bug report - PDF to DOCX conversion."""
        # Original file in DB (PDF)
        original = "NuVIZ_Cable_Management_Market_Comparison_Report.pdf"
        # Translated file from webhook (DOCX)
        translated = "NuVIZ_Cable_Management_Market_Comparison_Report_translated.docx"

        # Both should normalize to the same value
        assert normalize_filename_for_comparison(original) == \
               normalize_filename_for_comparison(translated)

        # Expected normalized value
        expected = "nuviz_cable_management_market_comparison_report"
        assert normalize_filename_for_comparison(original) == expected
        assert normalize_filename_for_comparison(translated) == expected

    def test_normalize_for_comparison_edge_cases(self):
        """Test edge cases."""
        # No extension
        assert normalize_filename_for_comparison("file") == "file"

        # Only extension (os.path.splitext treats this as name, not extension)
        assert normalize_filename_for_comparison(".pdf") == ".pdf"

        # Empty string
        assert normalize_filename_for_comparison("") == ""

        # Just _translated (becomes empty after removing suffix)
        assert normalize_filename_for_comparison("_translated.txt") == ""

    def test_normalize_for_lookup_backward_compatibility(self):
        """Test the deprecated normalize_filename_for_lookup function."""
        # This function is kept for backward compatibility
        assert normalize_filename_for_lookup("report_translated.pdf") == "report.pdf"
        assert normalize_filename_for_lookup("document_translated.docx") == "document.docx"
        assert normalize_filename_for_lookup("file.pdf") == "file.pdf"

    def test_extension_agnostic_matching(self):
        """Test that files with different extensions match after normalization."""
        test_cases = [
            ("report.pdf", "report_translated.docx"),
            ("document.txt", "document_translated.pdf"),
            ("presentation.pptx", "presentation_translated.pdf"),
            ("spreadsheet.xlsx", "spreadsheet_translated.docx"),
        ]

        for original, translated in test_cases:
            orig_normalized = normalize_filename_for_comparison(original)
            trans_normalized = normalize_filename_for_comparison(translated)
            assert orig_normalized == trans_normalized, \
                f"Failed to match: {original} vs {translated}"

    def test_case_insensitive_matching(self):
        """Test that filename matching is case-insensitive."""
        test_cases = [
            ("Report.PDF", "report_translated.docx"),
            ("DOCUMENT.txt", "document_translated.pdf"),
            ("MyFile.DOCX", "myfile_translated.pdf"),
        ]

        for original, translated in test_cases:
            orig_normalized = normalize_filename_for_comparison(original)
            trans_normalized = normalize_filename_for_comparison(translated)
            assert orig_normalized == trans_normalized, \
                f"Failed case-insensitive match: {original} vs {translated}"

    def test_preserved_dots_in_filename(self):
        """Test that dots in the filename (not extension) are preserved."""
        original = "my.document.v2.pdf"
        translated = "my.document.v2_translated.docx"

        orig_normalized = normalize_filename_for_comparison(original)
        trans_normalized = normalize_filename_for_comparison(translated)

        assert orig_normalized == trans_normalized
        assert orig_normalized == "my.document.v2"

    def test_complex_real_world_examples(self):
        """Test complex real-world filename scenarios."""
        test_cases = [
            # (DB filename, webhook filename, expected normalized)
            (
                "NuVIZ_Cable_Management_Market_Comparison_Report.pdf",
                "NuVIZ_Cable_Management_Market_Comparison_Report_translated.docx",
                "nuviz_cable_management_market_comparison_report"
            ),
            (
                "Contract_2024.Q1.Final.pdf",
                "Contract_2024.Q1.Final_translated.docx",
                "contract_2024.q1.final"
            ),
            (
                "Invoice #12345.pdf",
                "Invoice #12345_translated.docx",
                "invoice #12345"
            ),
            (
                "Proposal (Draft v2).docx",
                "Proposal (Draft v2)_translated.pdf",
                "proposal (draft v2)"
            ),
        ]

        for db_name, webhook_name, expected_normalized in test_cases:
            db_normalized = normalize_filename_for_comparison(db_name)
            webhook_normalized = normalize_filename_for_comparison(webhook_name)

            assert db_normalized == expected_normalized, \
                f"DB filename '{db_name}' normalized incorrectly"
            assert webhook_normalized == expected_normalized, \
                f"Webhook filename '{webhook_name}' normalized incorrectly"
            assert db_normalized == webhook_normalized, \
                f"Mismatch: '{db_name}' vs '{webhook_name}'"

    def test_matching_logic_simulation(self):
        """Simulate the matching logic used in TransactionUpdateService."""
        # Simulate database documents
        db_documents = [
            {"file_name": "report1.pdf", "index": 0},
            {"file_name": "NuVIZ_Cable_Management_Market_Comparison_Report.pdf", "index": 1},
            {"file_name": "contract.docx", "index": 2},
        ]

        # Simulate webhook filename
        webhook_filename = "NuVIZ_Cable_Management_Market_Comparison_Report_translated.docx"

        # Normalize webhook filename
        search_normalized = normalize_filename_for_comparison(webhook_filename)

        # Find matching document
        matched_index = None
        for doc in db_documents:
            db_normalized = normalize_filename_for_comparison(doc["file_name"])
            if db_normalized == search_normalized:
                matched_index = doc["index"]
                break

        # Should match document at index 1
        assert matched_index == 1

    def test_no_match_scenario(self):
        """Test when no document matches."""
        db_documents = [
            {"file_name": "report1.pdf", "index": 0},
            {"file_name": "contract.docx", "index": 1},
        ]

        webhook_filename = "nonexistent_file_translated.pdf"
        search_normalized = normalize_filename_for_comparison(webhook_filename)

        matched_index = None
        for doc in db_documents:
            db_normalized = normalize_filename_for_comparison(doc["file_name"])
            if db_normalized == search_normalized:
                matched_index = doc["index"]
                break

        assert matched_index is None

    def test_multiple_documents_same_basename_different_extension(self):
        """Test edge case: multiple documents with same basename but different extensions."""
        # This shouldn't happen in practice, but test the behavior
        db_documents = [
            {"file_name": "report.pdf", "index": 0},
            {"file_name": "report.docx", "index": 1},
        ]

        webhook_filename = "report_translated.txt"
        search_normalized = normalize_filename_for_comparison(webhook_filename)

        # Should match the first one it finds (index 0)
        matched_index = None
        for doc in db_documents:
            db_normalized = normalize_filename_for_comparison(doc["file_name"])
            if db_normalized == search_normalized:
                matched_index = doc["index"]
                break

        assert matched_index == 0
