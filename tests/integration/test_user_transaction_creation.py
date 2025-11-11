"""
Integration tests for user transaction creation with transaction_id generation.

Tests cover:
- Transaction ID generation on payment processing
- Uniqueness enforcement
- Format validation
- Database persistence
- API response correctness

All tests run against real MongoDB test database and real server.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from app.database import database
from app.utils.user_transaction_helper import create_user_transaction
from app.utils.transaction_id_generator import validate_transaction_id_format


# Set pytest-asyncio to use module scope for event loop
pytestmark = pytest.mark.asyncio(scope="module")


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_database():
    """Setup database connection once for all tests in this module."""
    if not database._connected:
        await database.connect()
    yield


class TestTransactionIdGeneration:
    """Test transaction_id generation during user transaction creation."""

    @pytest.mark.asyncio
    async def test_transaction_id_generated_on_creation(self):
        """Test that transaction_id is auto-generated when creating transaction."""
        # Arrange
        test_email = f"test-{datetime.now().timestamp()}@example.com"
        test_square_id = f"TEST-SQR-{datetime.now().timestamp()}"

        documents = [{
            "file_name": "test_document.pdf",
            "file_size": 12345,
            "original_url": "https://drive.google.com/file/d/test123/view",
            "translated_url": None,
            "translated_name": None,
            "status": "uploaded",
            "uploaded_at": datetime.now(timezone.utc),
            "translated_at": None,
            "processing_started_at": None,
            "processing_duration": None
        }]

        # Act
        result = await create_user_transaction(
            user_name="Test User",
            user_email=test_email,
            documents=documents,
            number_of_units=10,
            unit_type="page",
            cost_per_unit=0.15,
            source_language="en",
            target_language="es",
            square_transaction_id=test_square_id,
            date=datetime.now(timezone.utc),
            status="processing",
            square_payment_id=test_square_id,
            amount_cents=150,
            currency="USD",
            payment_status="COMPLETED",
        )

        # Assert
        assert result is not None, "Transaction creation should return transaction_id"
        assert isinstance(result, str), "Result should be a string"

        # Verify transaction_id format
        assert result.startswith("USER"), f"Transaction ID should start with 'USER', got: {result}"
        assert validate_transaction_id_format(result) is True, f"Invalid transaction_id format: {result}"

        # Verify in database
        collection = database.user_transactions
        transaction = await collection.find_one({"transaction_id": result})

        assert transaction is not None, "Transaction should exist in database"
        assert transaction["transaction_id"] == result
        assert transaction["square_transaction_id"] == test_square_id
        assert transaction["user_email"] == test_email

        # Cleanup
        await collection.delete_one({"transaction_id": result})

    @pytest.mark.asyncio
    async def test_transaction_id_format_standard(self):
        """Test that generated transaction_id uses standard format (USER + 6 digits)."""
        # Arrange
        test_email = f"test-{datetime.now().timestamp()}@example.com"
        test_square_id = f"TEST-SQR-{datetime.now().timestamp()}"

        documents = [{
            "file_name": "test_document.pdf",
            "file_size": 12345,
            "original_url": "https://drive.google.com/file/d/test123/view",
            "status": "uploaded",
            "uploaded_at": datetime.now(timezone.utc),
        }]

        # Act
        transaction_id = await create_user_transaction(
            user_name="Test User",
            user_email=test_email,
            documents=documents,
            number_of_units=5,
            unit_type="page",
            cost_per_unit=0.20,
            source_language="en",
            target_language="fr",
            square_transaction_id=test_square_id,
            date=datetime.now(timezone.utc),
        )

        # Assert
        assert transaction_id is not None

        # Standard format: USER + 6 digits = 10 characters total
        # Fallback format: USER + timestamp + 3 digits = 17+ characters
        # Most should be standard format
        if len(transaction_id) == 10:
            # Standard format
            numeric_part = transaction_id[4:]  # Remove "USER" prefix
            assert numeric_part.isdigit(), "Numeric part should be all digits"
            assert len(numeric_part) == 6, "Should have exactly 6 digits"
        else:
            # Fallback format (rare)
            assert len(transaction_id) >= 17, "Fallback format should be at least 17 characters"

        # Cleanup
        collection = database.user_transactions
        await collection.delete_one({"transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_transaction_id_uniqueness_enforced(self):
        """Test that duplicate transaction_id is prevented by database unique index."""
        # Arrange
        test_email = f"test-{datetime.now().timestamp()}@example.com"
        test_square_id_1 = f"TEST-SQR-{datetime.now().timestamp()}-1"
        test_square_id_2 = f"TEST-SQR-{datetime.now().timestamp()}-2"

        documents = [{
            "file_name": "test_document.pdf",
            "file_size": 12345,
            "original_url": "https://drive.google.com/file/d/test123/view",
            "status": "uploaded",
            "uploaded_at": datetime.now(timezone.utc),
        }]

        # Act: Create first transaction
        transaction_id_1 = await create_user_transaction(
            user_name="Test User",
            user_email=test_email,
            documents=documents,
            number_of_units=5,
            unit_type="page",
            cost_per_unit=0.20,
            source_language="en",
            target_language="es",
            square_transaction_id=test_square_id_1,
            date=datetime.now(timezone.utc),
        )

        assert transaction_id_1 is not None

        # Act: Create second transaction (should get different transaction_id)
        transaction_id_2 = await create_user_transaction(
            user_name="Test User",
            user_email=test_email,
            documents=documents,
            number_of_units=8,
            unit_type="page",
            cost_per_unit=0.20,
            source_language="en",
            target_language="fr",
            square_transaction_id=test_square_id_2,
            date=datetime.now(timezone.utc),
        )

        assert transaction_id_2 is not None

        # Assert: Transaction IDs should be different
        assert transaction_id_1 != transaction_id_2, "Transaction IDs must be unique"

        # Verify both exist in database
        collection = database.user_transactions
        txn1 = await collection.find_one({"transaction_id": transaction_id_1})
        txn2 = await collection.find_one({"transaction_id": transaction_id_2})

        assert txn1 is not None
        assert txn2 is not None
        assert txn1["square_transaction_id"] == test_square_id_1
        assert txn2["square_transaction_id"] == test_square_id_2

        # Cleanup
        await collection.delete_many({"transaction_id": {"$in": [transaction_id_1, transaction_id_2]}})

    @pytest.mark.asyncio
    async def test_transaction_id_persists_in_database(self):
        """Test that transaction_id is correctly stored in MongoDB."""
        # Arrange
        test_email = f"test-{datetime.now().timestamp()}@example.com"
        test_square_id = f"TEST-SQR-{datetime.now().timestamp()}"

        documents = [{
            "file_name": "persistence_test.pdf",
            "file_size": 54321,
            "original_url": "https://drive.google.com/file/d/persist123/view",
            "status": "uploaded",
            "uploaded_at": datetime.now(timezone.utc),
        }]

        # Act
        transaction_id = await create_user_transaction(
            user_name="Persistence Test User",
            user_email=test_email,
            documents=documents,
            number_of_units=15,
            unit_type="page",
            cost_per_unit=0.12,
            source_language="en",
            target_language="de",
            square_transaction_id=test_square_id,
            date=datetime.now(timezone.utc),
        )

        # Assert
        collection = database.user_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        assert transaction is not None, "Transaction should be persisted in database"
        assert "transaction_id" in transaction, "transaction_id field should exist"
        assert transaction["transaction_id"] == transaction_id
        assert transaction["transaction_id"].startswith("USER")

        # Verify all expected fields exist
        assert "square_transaction_id" in transaction
        assert "user_email" in transaction
        assert "user_name" in transaction
        assert "documents" in transaction
        assert "total_cost" in transaction
        assert "created_at" in transaction

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_transaction_id_in_multiple_documents(self):
        """Test transaction_id generation with multiple documents."""
        # Arrange
        test_email = f"test-{datetime.now().timestamp()}@example.com"
        test_square_id = f"TEST-SQR-{datetime.now().timestamp()}"

        documents = [
            {
                "file_name": "doc1.pdf",
                "file_size": 10000,
                "original_url": "https://drive.google.com/file/d/doc1/view",
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
            },
            {
                "file_name": "doc2.docx",
                "file_size": 20000,
                "original_url": "https://drive.google.com/file/d/doc2/view",
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
            },
            {
                "file_name": "doc3.txt",
                "file_size": 5000,
                "original_url": "https://drive.google.com/file/d/doc3/view",
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
            }
        ]

        # Act
        transaction_id = await create_user_transaction(
            user_name="Multi-Doc Test User",
            user_email=test_email,
            documents=documents,
            number_of_units=25,
            unit_type="page",
            cost_per_unit=0.15,
            source_language="en",
            target_language="es",
            square_transaction_id=test_square_id,
            date=datetime.now(timezone.utc),
        )

        # Assert
        assert transaction_id is not None
        assert validate_transaction_id_format(transaction_id)

        # Verify in database
        collection = database.user_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        assert transaction is not None
        assert len(transaction["documents"]) == 3
        assert transaction["transaction_id"] == transaction_id

        # Verify documents do NOT have transaction_id (should only be at parent level)
        for doc in transaction["documents"]:
            assert "transaction_id" not in doc, "Documents should NOT have transaction_id (only parent level)"

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})


class TestTransactionIdIndexes:
    """Test database indexes for transaction_id field."""

    @pytest.mark.asyncio
    async def test_transaction_id_index_exists(self):
        """Test that unique index exists on transaction_id field."""
        collection = database.user_transactions
        indexes = await collection.index_information()

        # Check if transaction_id_unique index exists
        assert "transaction_id_unique" in indexes, "transaction_id_unique index should exist"

        # Verify it's a unique index
        index_info = indexes["transaction_id_unique"]
        assert index_info["unique"] is True, "transaction_id index should be unique"

        # Verify it's on the correct field
        assert index_info["key"][0][0] == "transaction_id", "Index should be on transaction_id field"

    @pytest.mark.asyncio
    async def test_square_transaction_id_index_still_exists(self):
        """Test that square_transaction_id index is preserved for backward compatibility."""
        collection = database.user_transactions
        indexes = await collection.index_information()

        # Check if square_transaction_id_unique index still exists
        assert "square_transaction_id_unique" in indexes, "square_transaction_id_unique index should still exist"

        # Verify it's still unique
        index_info = indexes["square_transaction_id_unique"]
        assert index_info["unique"] is True, "square_transaction_id index should remain unique"
