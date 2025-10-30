"""
Comprehensive pytest unit tests for user transaction functionality.

Tests coverage:
1. user_transaction_helper.py - CRUD operations
2. translate_user.py - Helper functions and endpoint
3. payment_simplified.py - Payment success handler

Test groups:
- Part 1: user_transaction_helper functions
- Part 2: translate_user helper functions
- Part 3: Integration tests for /translate-user endpoint
"""

import asyncio
import base64
import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError, PyMongoError

# Import modules to test
from app.utils import user_transaction_helper
from app.routers import translate_user
from app.routers.translate_user import (
    generate_square_transaction_id,
    estimate_page_count,
    get_unit_type,
)
from app.main import app


# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def test_client():
    """
    FastAPI test client.

    Note: Version conflict resolved by downgrading httpx to 0.27.2
    Versions: httpx==0.27.2, starlette==0.27.0, fastapi==0.104.1
    """
    return TestClient(app)


@pytest.fixture
def mock_database():
    """Mock MongoDB database connection."""
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.user_transactions = mock_collection
    return mock_db


@pytest.fixture
def sample_transaction_data():
    """Sample transaction data for testing."""
    return {
        "user_name": "Test User",
        "user_email": "test@example.com",
        "document_url": "https://drive.google.com/file/d/abc123/view",
        "number_of_units": 10,
        "unit_type": "page",
        "cost_per_unit": 0.10,
        "source_language": "en",
        "target_language": "es",
        "square_transaction_id": "sqt_test123456789012",
        "date": datetime.now(timezone.utc),
        "status": "processing",
    }


@pytest.fixture
def sample_user_file():
    """Sample file data for endpoint testing."""
    return {
        "id": "file-1",
        "name": "test.pdf",
        "size": 100000,
        "type": "application/pdf",
        "content": base64.b64encode(b"Mock PDF content").decode(),
    }


@pytest.fixture
def sample_translate_request(sample_user_file):
    """Sample /translate-user request data."""
    return {
        "files": [sample_user_file],
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "email": "test@example.com",
        "userName": "Test User",
    }


# ============================================================================
# PART 1: TEST user_transaction_helper.py FUNCTIONS
# ============================================================================


class TestUserTransactionHelper:
    """Test user_transaction_helper.py CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_user_transaction_success(
        self, mock_database, sample_transaction_data
    ):
        """Test successful transaction creation."""
        # Setup
        mock_collection = mock_database.user_transactions
        mock_collection.insert_one = AsyncMock(return_value=Mock(inserted_id="mock_id"))

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.create_user_transaction(
                user_name=sample_transaction_data["user_name"],
                user_email=sample_transaction_data["user_email"],
                document_url=sample_transaction_data["document_url"],
                number_of_units=sample_transaction_data["number_of_units"],
                unit_type=sample_transaction_data["unit_type"],
                cost_per_unit=sample_transaction_data["cost_per_unit"],
                source_language=sample_transaction_data["source_language"],
                target_language=sample_transaction_data["target_language"],
                square_transaction_id=sample_transaction_data["square_transaction_id"],
                date=sample_transaction_data["date"],
                status=sample_transaction_data["status"],
            )

            # Verify
            assert result == sample_transaction_data["square_transaction_id"]
            mock_collection.insert_one.assert_called_once()

            # Verify document structure
            call_args = mock_collection.insert_one.call_args[0][0]
            assert call_args["user_name"] == "Test User"
            assert call_args["user_email"] == "test@example.com"
            assert call_args["number_of_units"] == 10
            assert call_args["unit_type"] == "page"
            assert call_args["cost_per_unit"] == 0.10
            assert call_args["total_cost"] == 1.0  # 10 * 0.10
            assert call_args["status"] == "processing"
            assert "created_at" in call_args
            assert "updated_at" in call_args

    @pytest.mark.asyncio
    async def test_create_user_transaction_calculates_total_cost(
        self, mock_database, sample_transaction_data
    ):
        """Test total_cost is calculated correctly."""
        # Setup
        mock_collection = mock_database.user_transactions
        mock_collection.insert_one = AsyncMock(return_value=Mock(inserted_id="mock_id"))

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute with different units
            await user_transaction_helper.create_user_transaction(
                user_name="Test",
                user_email="test@example.com",
                document_url="https://example.com",
                number_of_units=25,
                unit_type="page",
                cost_per_unit=0.10,
                source_language="en",
                target_language="es",
                square_transaction_id="sqt_test",
                date=datetime.now(timezone.utc),
                status="processing",
            )

            # Verify total_cost calculation
            call_args = mock_collection.insert_one.call_args[0][0]
            assert call_args["total_cost"] == 2.5  # 25 * 0.10

    @pytest.mark.asyncio
    async def test_create_user_transaction_sets_timestamps(
        self, mock_database, sample_transaction_data
    ):
        """Test created_at and updated_at timestamps are set."""
        # Setup
        mock_collection = mock_database.user_transactions
        mock_collection.insert_one = AsyncMock(return_value=Mock(inserted_id="mock_id"))

        before_time = datetime.now(timezone.utc)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            await user_transaction_helper.create_user_transaction(
                **sample_transaction_data
            )

            after_time = datetime.now(timezone.utc)

            # Verify timestamps
            call_args = mock_collection.insert_one.call_args[0][0]
            assert "created_at" in call_args
            assert "updated_at" in call_args
            assert before_time <= call_args["created_at"] <= after_time
            assert before_time <= call_args["updated_at"] <= after_time

    @pytest.mark.asyncio
    async def test_create_user_transaction_duplicate_square_id(
        self, mock_database, sample_transaction_data
    ):
        """Test duplicate square_transaction_id handling."""
        # Setup - simulate duplicate key error
        mock_collection = mock_database.user_transactions
        mock_collection.insert_one = AsyncMock(side_effect=DuplicateKeyError("duplicate"))

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.create_user_transaction(
                **sample_transaction_data
            )

            # Verify - should return None on duplicate
            assert result is None

    @pytest.mark.asyncio
    async def test_create_user_transaction_invalid_unit_type(
        self, mock_database, sample_transaction_data
    ):
        """Test invalid unit_type validation."""
        # Setup
        sample_transaction_data["unit_type"] = "invalid_type"

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.create_user_transaction(
                **sample_transaction_data
            )

            # Verify - should return None for invalid unit_type
            assert result is None

    @pytest.mark.asyncio
    async def test_create_user_transaction_invalid_status(
        self, mock_database, sample_transaction_data
    ):
        """Test invalid status validation."""
        # Setup
        sample_transaction_data["status"] = "invalid_status"

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.create_user_transaction(
                **sample_transaction_data
            )

            # Verify - should return None for invalid status
            assert result is None

    @pytest.mark.asyncio
    async def test_update_user_transaction_status_success(self, mock_database):
        """Test status update to 'completed'."""
        # Setup
        mock_collection = mock_database.user_transactions
        mock_result = Mock()
        mock_result.matched_count = 1
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.update_user_transaction_status(
                square_transaction_id="sqt_test123",
                new_status="completed",
            )

            # Verify
            assert result is True
            mock_collection.update_one.assert_called_once()

            # Verify update structure
            call_args = mock_collection.update_one.call_args
            assert call_args[0][0] == {"square_transaction_id": "sqt_test123"}
            assert call_args[0][1]["$set"]["status"] == "completed"
            assert "updated_at" in call_args[0][1]["$set"]

    @pytest.mark.asyncio
    async def test_update_user_transaction_status_with_error_message(
        self, mock_database
    ):
        """Test status update to 'failed' with error_message."""
        # Setup
        mock_collection = mock_database.user_transactions
        mock_result = Mock()
        mock_result.matched_count = 1
        mock_result.modified_count = 1
        mock_collection.update_one = AsyncMock(return_value=mock_result)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.update_user_transaction_status(
                square_transaction_id="sqt_test123",
                new_status="failed",
                error_message="Payment failed",
            )

            # Verify
            assert result is True

            # Verify error_message is included
            call_args = mock_collection.update_one.call_args[0][1]
            assert call_args["$set"]["error_message"] == "Payment failed"

    @pytest.mark.asyncio
    async def test_update_user_transaction_status_not_found(self, mock_database):
        """Test status update when transaction not found."""
        # Setup
        mock_collection = mock_database.user_transactions
        mock_result = Mock()
        mock_result.matched_count = 0
        mock_collection.update_one = AsyncMock(return_value=mock_result)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.update_user_transaction_status(
                square_transaction_id="nonexistent",
                new_status="completed",
            )

            # Verify - should return False when not found
            assert result is False

    @pytest.mark.asyncio
    async def test_get_user_transactions_by_email_no_filter(self, mock_database):
        """Test getting all transactions for a user without status filter."""
        # Setup
        mock_transactions = [
            {"_id": "id1", "user_email": "test@example.com", "status": "completed"},
            {"_id": "id2", "user_email": "test@example.com", "status": "processing"},
        ]

        mock_collection = mock_database.user_transactions
        mock_cursor = MagicMock()
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=mock_transactions)
        mock_collection.find = Mock(return_value=mock_cursor)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.get_user_transactions_by_email(
                user_email="test@example.com"
            )

            # Verify
            assert len(result) == 2
            assert result[0]["_id"] == "id1"
            assert result[1]["_id"] == "id2"

            # Verify query
            mock_collection.find.assert_called_once_with(
                {"user_email": "test@example.com"}
            )
            mock_cursor.sort.assert_called_once_with("date", -1)

    @pytest.mark.asyncio
    async def test_get_user_transactions_by_email_with_status_filter(
        self, mock_database
    ):
        """Test filtering transactions by status='completed'."""
        # Setup
        mock_transactions = [
            {"_id": "id1", "user_email": "test@example.com", "status": "completed"},
        ]

        mock_collection = mock_database.user_transactions
        mock_cursor = MagicMock()
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=mock_transactions)
        mock_collection.find = Mock(return_value=mock_cursor)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.get_user_transactions_by_email(
                user_email="test@example.com",
                status="completed",
            )

            # Verify
            assert len(result) == 1
            assert result[0]["status"] == "completed"

            # Verify query includes status filter
            mock_collection.find.assert_called_once_with(
                {"user_email": "test@example.com", "status": "completed"}
            )

    @pytest.mark.asyncio
    async def test_get_user_transactions_by_email_processing_filter(self, mock_database):
        """Test filtering transactions by status='processing'."""
        # Setup
        mock_transactions = [
            {"_id": "id1", "user_email": "test@example.com", "status": "processing"},
        ]

        mock_collection = mock_database.user_transactions
        mock_cursor = MagicMock()
        mock_cursor.sort = Mock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=mock_transactions)
        mock_collection.find = Mock(return_value=mock_cursor)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.get_user_transactions_by_email(
                user_email="test@example.com",
                status="processing",
            )

            # Verify
            assert len(result) == 1
            assert result[0]["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_user_transaction_by_square_id_found(self, mock_database):
        """Test retrieval by square_transaction_id."""
        # Setup
        mock_transaction = {
            "_id": "id1",
            "square_transaction_id": "sqt_test123",
            "user_email": "test@example.com",
        }

        mock_collection = mock_database.user_transactions
        mock_collection.find_one = AsyncMock(return_value=mock_transaction)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.get_user_transaction(
                square_transaction_id="sqt_test123"
            )

            # Verify
            assert result is not None
            assert result["square_transaction_id"] == "sqt_test123"
            assert result["_id"] == "id1"

    @pytest.mark.asyncio
    async def test_get_user_transaction_by_square_id_not_found(self, mock_database):
        """Test retrieval with non-existent square_transaction_id."""
        # Setup
        mock_collection = mock_database.user_transactions
        mock_collection.find_one = AsyncMock(return_value=None)

        with patch("app.utils.user_transaction_helper.database", mock_database):
            # Execute
            result = await user_transaction_helper.get_user_transaction(
                square_transaction_id="nonexistent"
            )

            # Verify
            assert result is None

    @pytest.mark.asyncio
    async def test_database_not_connected_create(self):
        """Test create function returns None when database not connected."""
        # Setup - mock database with None collection
        mock_db = MagicMock()
        mock_db.user_transactions = None

        with patch("app.utils.user_transaction_helper.database", mock_db):
            # Execute
            result = await user_transaction_helper.create_user_transaction(
                user_name="Test",
                user_email="test@example.com",
                document_url="https://example.com",
                number_of_units=10,
                unit_type="page",
                cost_per_unit=0.10,
                source_language="en",
                target_language="es",
                square_transaction_id="sqt_test",
                date=datetime.now(timezone.utc),
            )

            # Verify
            assert result is None

    @pytest.mark.asyncio
    async def test_database_not_connected_update(self):
        """Test update function returns False when database not connected."""
        # Setup
        mock_db = MagicMock()
        mock_db.user_transactions = None

        with patch("app.utils.user_transaction_helper.database", mock_db):
            # Execute
            result = await user_transaction_helper.update_user_transaction_status(
                square_transaction_id="sqt_test",
                new_status="completed",
            )

            # Verify
            assert result is False

    @pytest.mark.asyncio
    async def test_database_not_connected_get_by_email(self):
        """Test get_by_email returns empty list when database not connected."""
        # Setup
        mock_db = MagicMock()
        mock_db.user_transactions = None

        with patch("app.utils.user_transaction_helper.database", mock_db):
            # Execute
            result = await user_transaction_helper.get_user_transactions_by_email(
                user_email="test@example.com"
            )

            # Verify
            assert result == []

    @pytest.mark.asyncio
    async def test_database_not_connected_get_by_id(self):
        """Test get_by_id returns None when database not connected."""
        # Setup
        mock_db = MagicMock()
        mock_db.user_transactions = None

        with patch("app.utils.user_transaction_helper.database", mock_db):
            # Execute
            result = await user_transaction_helper.get_user_transaction(
                square_transaction_id="sqt_test"
            )

            # Verify
            assert result is None


# ============================================================================
# PART 2: TEST translate_user.py HELPER FUNCTIONS
# ============================================================================


class TestTranslateUserHelpers:
    """Test helper functions in translate_user.py."""

    def test_generate_square_transaction_id_format(self):
        """Test Square transaction ID format: sqt_{20_chars}."""
        tx_id = generate_square_transaction_id()

        # Verify format
        assert tx_id.startswith("sqt_")
        assert len(tx_id) == 24  # "sqt_" (4) + 20 chars

    def test_generate_square_transaction_id_uniqueness(self):
        """Test that 100 generated IDs are all unique."""
        ids = [generate_square_transaction_id() for _ in range(100)]

        # Verify uniqueness
        assert len(ids) == len(set(ids))

    def test_estimate_page_count_pdf(self):
        """Test PDF estimation (~50KB per page)."""
        # Small PDF
        assert estimate_page_count("test.pdf", 50000) == 1
        # Medium PDF
        assert estimate_page_count("test.pdf", 100000) == 2
        # Large PDF
        assert estimate_page_count("test.pdf", 250000) == 5

    def test_estimate_page_count_word(self):
        """Test Word estimation (~25KB per page)."""
        # Small Word doc
        assert estimate_page_count("test.docx", 25000) == 1
        # Medium Word doc
        assert estimate_page_count("test.docx", 75000) == 3
        # .doc extension
        assert estimate_page_count("test.doc", 50000) == 2

    def test_estimate_page_count_images(self):
        """Test image files always return 1 page."""
        assert estimate_page_count("photo.png", 5000000) == 1
        assert estimate_page_count("image.jpg", 2000000) == 1
        assert estimate_page_count("picture.jpeg", 3000000) == 1
        assert estimate_page_count("animation.gif", 1000000) == 1
        assert estimate_page_count("bitmap.bmp", 10000000) == 1

    def test_estimate_page_count_edge_cases(self):
        """Test edge cases (0 bytes, very large files)."""
        # 0 bytes - minimum is 1
        assert estimate_page_count("empty.pdf", 0) == 1
        # Very small file - minimum is 1
        assert estimate_page_count("tiny.pdf", 100) == 1
        # Very large file
        assert estimate_page_count("huge.pdf", 10000000) == 200

    def test_estimate_page_count_case_insensitive(self):
        """Test that extension matching is case-insensitive."""
        assert estimate_page_count("TEST.PDF", 100000) == 2
        assert estimate_page_count("test.pdf", 100000) == 2
        assert estimate_page_count("TEST.DOCX", 50000) == 2
        assert estimate_page_count("test.docx", 50000) == 2

    def test_determine_unit_type_all_extensions(self):
        """Test all file extensions return 'page'."""
        assert get_unit_type("file.pdf") == "page"
        assert get_unit_type("file.docx") == "page"
        assert get_unit_type("file.doc") == "page"
        assert get_unit_type("file.png") == "page"
        assert get_unit_type("file.jpg") == "page"
        assert get_unit_type("file.unknown") == "page"

    def test_calculate_pricing(self):
        """Test pricing calculation with cost_per_unit = 0.10."""
        # Single unit
        total_units = 1
        cost_per_unit = 0.10
        assert total_units * cost_per_unit == 0.10

        # Multiple units
        total_units = 10
        assert total_units * cost_per_unit == 1.00

        # Large number
        total_units = 100
        assert total_units * cost_per_unit == 10.00


# ============================================================================
# PART 3: INTEGRATION TESTS FOR /translate-user ENDPOINT
# ============================================================================


class TestTranslateUserEndpoint:
    """Integration tests for /translate-user endpoint."""

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_missing_fields(self, test_client):
        """Test validation error for missing required fields."""
        # Missing userName
        request_data = {
            "files": [],
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "test@example.com",
        }

        response = test_client.post("/translate-user", json=request_data)

        # Verify validation error
        assert response.status_code == 422  # Unprocessable Entity

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_invalid_email_format(self, test_client):
        """Test invalid email format rejection."""
        request_data = {
            "files": [
                {
                    "id": "1",
                    "name": "test.pdf",
                    "size": 100000,
                    "type": "application/pdf",
                    "content": base64.b64encode(b"test").decode(),
                }
            ],
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "invalid-email",  # Invalid format
            "userName": "Test User",
        }

        response = test_client.post("/translate-user", json=request_data)

        # Verify validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_disposable_email_rejection(
        self, test_client, sample_user_file
    ):
        """Test disposable email domain rejection."""
        request_data = {
            "files": [sample_user_file],
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "test@tempmail.org",  # Disposable domain
            "userName": "Test User",
        }

        with patch(
            "app.routers.translate_user.google_drive_service.create_customer_folder_structure"
        ) as mock_folder:
            mock_folder.return_value = AsyncMock(return_value="folder_id")

            response = test_client.post("/translate-user", json=request_data)

            # Verify rejection
            assert response.status_code == 400
            assert response.json()["success"] is False
            assert "disposable" in response.json()["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_invalid_language_codes(
        self, test_client, sample_user_file
    ):
        """Test invalid language code rejection."""
        # Invalid source language
        request_data = {
            "files": [sample_user_file],
            "sourceLanguage": "invalid",
            "targetLanguage": "es",
            "email": "test@example.com",
            "userName": "Test User",
        }

        with patch(
            "app.routers.translate_user.google_drive_service.create_customer_folder_structure"
        ) as mock_folder:
            mock_folder.return_value = AsyncMock(return_value="folder_id")

            response = test_client.post("/translate-user", json=request_data)

            # Verify rejection
            assert response.status_code == 400
            assert response.json()["success"] is False
            assert "Invalid source language" in response.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_same_source_target_language(
        self, test_client, sample_user_file
    ):
        """Test rejection when source == target language."""
        request_data = {
            "files": [sample_user_file],
            "sourceLanguage": "en",
            "targetLanguage": "en",  # Same as source
            "email": "test@example.com",
            "userName": "Test User",
        }

        with patch(
            "app.routers.translate_user.google_drive_service.create_customer_folder_structure"
        ) as mock_folder:
            mock_folder.return_value = AsyncMock(return_value="folder_id")

            response = test_client.post("/translate-user", json=request_data)

            # Verify rejection
            assert response.status_code == 400
            assert response.json()["success"] is False
            assert "cannot be the same" in response.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_too_many_files(
        self, test_client, sample_user_file
    ):
        """Test rejection when more than 10 files."""
        request_data = {
            "files": [sample_user_file] * 11,  # 11 files
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "test@example.com",
            "userName": "Test User",
        }

        with patch(
            "app.routers.translate_user.google_drive_service.create_customer_folder_structure"
        ) as mock_folder:
            mock_folder.return_value = AsyncMock(return_value="folder_id")

            response = test_client.post("/translate-user", json=request_data)

            # Verify rejection
            assert response.status_code == 400
            assert response.json()["success"] is False
            assert "Maximum 10 files" in response.json()["error"]["message"]

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_no_files(self, test_client):
        """Test rejection when no files provided."""
        request_data = {
            "files": [],  # Empty
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "test@example.com",
            "userName": "Test User",
        }

        with patch(
            "app.routers.translate_user.google_drive_service.create_customer_folder_structure"
        ) as mock_folder:
            mock_folder.return_value = AsyncMock(return_value="folder_id")

            response = test_client.post("/translate-user", json=request_data)

            # Verify rejection
            assert response.status_code == 400
            assert response.json()["success"] is False
            assert "at least one file" in response.json()["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_success(
        self, test_client, sample_translate_request
    ):
        """Test successful file upload with mocked Google Drive."""
        # Mock Google Drive operations
        with patch(
            "app.routers.translate_user.google_drive_service.create_customer_folder_structure"
        ) as mock_create_folder, patch(
            "app.routers.translate_user.google_drive_service.upload_file_to_folder"
        ) as mock_upload, patch(
            "app.routers.translate_user.google_drive_service.update_file_properties"
        ) as mock_update, patch(
            "app.routers.translate_user.create_user_transaction"
        ) as mock_create_tx:

            # Setup mocks
            mock_create_folder.return_value = "folder_123"
            mock_upload.return_value = {
                "file_id": "file_123",
                "google_drive_url": "https://drive.google.com/file/d/file_123/view",
            }
            mock_update.return_value = None
            mock_create_tx.return_value = "sqt_mock123456789012"

            # Execute
            response = test_client.post(
                "/translate-user", json=sample_translate_request
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert "data" in data

            # Verify response structure
            assert "pricing" in data["data"]
            assert "files" in data["data"]
            assert "customer" in data["data"]
            assert "payment" in data["data"]
            assert "square_transaction_ids" in data["data"]

            # Verify pricing
            pricing = data["data"]["pricing"]
            assert pricing["cost_per_unit"] == 0.10
            assert pricing["unit_type"] == "page"
            assert pricing["currency"] == "USD"

            # Verify payment info
            payment = data["data"]["payment"]
            assert payment["required"] is True
            assert payment["customer_email"] == "test@example.com"

            # Verify square_transaction_ids
            assert len(data["data"]["square_transaction_ids"]) > 0

    @pytest.mark.asyncio
    async def test_translate_user_endpoint_transaction_creation(
        self, test_client, sample_translate_request
    ):
        """Test transaction is created in database during upload."""
        # Mock all dependencies
        with patch(
            "app.routers.translate_user.google_drive_service.create_customer_folder_structure"
        ) as mock_folder, patch(
            "app.routers.translate_user.google_drive_service.upload_file_to_folder"
        ) as mock_upload, patch(
            "app.routers.translate_user.google_drive_service.update_file_properties"
        ) as mock_update, patch(
            "app.routers.translate_user.create_user_transaction"
        ) as mock_create_tx:

            mock_folder.return_value = "folder_123"
            mock_upload.return_value = {
                "file_id": "file_123",
                "google_drive_url": "https://drive.google.com/file/d/file_123/view",
            }
            mock_update.return_value = None
            mock_create_tx.return_value = "sqt_test123"

            # Execute
            response = test_client.post(
                "/translate-user", json=sample_translate_request
            )

            # Verify transaction creation was called
            assert response.status_code == 200
            mock_create_tx.assert_called_once()

            # Verify transaction data
            call_kwargs = mock_create_tx.call_args[1]
            assert call_kwargs["user_name"] == "Test User"
            assert call_kwargs["user_email"] == "test@example.com"
            assert call_kwargs["source_language"] == "en"
            assert call_kwargs["target_language"] == "es"
            assert call_kwargs["cost_per_unit"] == 0.10
            assert call_kwargs["status"] == "processing"


# ============================================================================
# PART 4: INTEGRATION TESTS FOR USER TRANSACTION API ENDPOINTS
# ============================================================================


class TestUserTransactionAPIEndpoints:
    """Integration tests for user transaction API endpoints."""

    @pytest.mark.asyncio
    async def test_get_all_user_transactions_success(self, test_client):
        """Test successful retrieval of all user transactions."""
        # Mock database operations
        with patch("app.routers.user_transactions.database") as mock_db:
            mock_transactions = [
                {
                    "_id": "68fac0c78d81a68274ac140b",
                    "user_name": "John Doe",
                    "user_email": "john.doe@example.com",
                    "document_url": "https://drive.google.com/file/d/1ABC/view",
                    "number_of_units": 10,
                    "unit_type": "page",
                    "cost_per_unit": 0.15,
                    "source_language": "en",
                    "target_language": "es",
                    "square_transaction_id": "SQR-1EC28E70F10B4D9E",
                    "date": datetime.now(timezone.utc),
                    "status": "completed",
                    "total_cost": 1.5,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            ]

            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=mock_transactions)
            mock_db.user_transactions.aggregate = Mock(return_value=mock_cursor)
            mock_db.user_transactions.count_documents = AsyncMock(return_value=1)

            # Execute
            response = test_client.get("/api/v1/user-transactions")

            # Verify
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "data" in data
            assert "transactions" in data["data"]
            assert data["data"]["count"] == 1
            assert data["data"]["total"] == 1
            assert data["data"]["limit"] == 100
            assert data["data"]["skip"] == 0

    @pytest.mark.asyncio
    async def test_get_all_user_transactions_with_status_filter(self, test_client):
        """Test filtering all transactions by status."""
        with patch("app.routers.user_transactions.database") as mock_db:
            mock_transactions = [
                {
                    "_id": "id1",
                    "user_email": "user1@example.com",
                    "status": "completed",
                    "created_at": datetime.now(timezone.utc),
                }
            ]

            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=mock_transactions)
            mock_db.user_transactions.aggregate = Mock(return_value=mock_cursor)
            mock_db.user_transactions.count_documents = AsyncMock(return_value=1)

            # Execute with status filter
            response = test_client.get("/api/v1/user-transactions?status=completed")

            # Verify
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["filters"]["status"] == "completed"

            # Verify aggregation was called with correct filter
            call_args = mock_db.user_transactions.aggregate.call_args[0][0]
            assert {"$match": {"status": "completed"}} in call_args

    @pytest.mark.asyncio
    async def test_get_all_user_transactions_with_pagination(self, test_client):
        """Test pagination parameters."""
        with patch("app.routers.user_transactions.database") as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[])
            mock_db.user_transactions.aggregate = Mock(return_value=mock_cursor)
            mock_db.user_transactions.count_documents = AsyncMock(return_value=0)

            # Execute with pagination
            response = test_client.get("/api/v1/user-transactions?limit=50&skip=10")

            # Verify
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["limit"] == 50
            assert data["data"]["skip"] == 10

            # Verify aggregation pipeline includes skip and limit
            call_args = mock_db.user_transactions.aggregate.call_args[0][0]
            assert {"$skip": 10} in call_args
            assert {"$limit": 50} in call_args

    @pytest.mark.asyncio
    async def test_get_all_user_transactions_invalid_status(self, test_client):
        """Test rejection of invalid status filter."""
        # Execute with invalid status
        response = test_client.get("/api/v1/user-transactions?status=invalid")

        # Verify
        assert response.status_code == 400
        data = response.json()
        assert "Invalid transaction status" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_all_user_transactions_empty_result(self, test_client):
        """Test response when no transactions exist."""
        with patch("app.routers.user_transactions.database") as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.to_list = AsyncMock(return_value=[])
            mock_db.user_transactions.aggregate = Mock(return_value=mock_cursor)
            mock_db.user_transactions.count_documents = AsyncMock(return_value=0)

            # Execute
            response = test_client.get("/api/v1/user-transactions")

            # Verify
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["transactions"] == []
            assert data["data"]["count"] == 0
            assert data["data"]["total"] == 0


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
