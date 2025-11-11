"""
Integration tests for user transaction structure validation.

This test module validates that transaction_id exists ONLY at the parent level,
NOT in the documents array.

Correct Structure:
{
  "_id": ObjectId("..."),
  "transaction_id": "USER123456",  // At parent level
  "square_transaction_id": "SQR-...",
  "documents": [
    {
      "file_name": "doc1.pdf",
      // NO transaction_id here
    }
  ]
}

Test Database: translation_test
"""

import pytest
from datetime import datetime, timezone
import uuid

from app.database.mongodb import database
from app.utils.user_transaction_helper import create_user_transaction


class TestUserTransactionStructure:
    """Test that transaction_id is at parent level, NOT in documents array."""

    @pytest.mark.asyncio
    async def test_transaction_id_at_parent_level_only(self):
        """
        Verify transaction_id exists at parent level with USER format.

        transaction_id should be at the transaction level, not nested in documents.
        """
        await database.connect()

        # Create test transaction
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        documents = [
            {
                "file_name": "test_doc.pdf",
                "file_size": 102400,
                "original_url": "https://drive.google.com/file/d/TEST/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]

        result_id = await create_user_transaction(
            user_name="Test User",
            user_email="test@example.com",
            documents=documents,
            number_of_units=10,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="es",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        # Retrieve from database
        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify parent-level transaction_id exists
        assert "transaction_id" in transaction, "transaction_id should exist at parent level"
        assert isinstance(transaction["transaction_id"], str), "transaction_id should be string"
        assert transaction["transaction_id"].startswith("USER"), "transaction_id should start with USER"
        assert len(transaction["transaction_id"]) in [10, 17], "transaction_id should be USER format"

        # Verify documents array does NOT contain transaction_id
        assert "documents" in transaction
        assert len(transaction["documents"]) > 0

        for i, doc in enumerate(transaction["documents"]):
            assert "transaction_id" not in doc, \
                f"Document {i} should NOT have transaction_id field (should only be at parent level)"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_multiple_documents_no_transaction_id_in_array(self):
        """
        Verify that even with multiple documents, none have transaction_id in them.

        All documents should NOT have transaction_id field.
        """
        await database.connect()

        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        documents = [
            {
                "file_name": f"doc{i}.pdf",
                "file_size": 102400 * i,
                "original_url": f"https://drive.google.com/file/d/TEST{i}/view",
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
            }
            for i in range(1, 4)
        ]

        result_id = await create_user_transaction(
            user_name="Multi Doc User",
            user_email="multitest@example.com",
            documents=documents,
            number_of_units=30,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="fr",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify parent has transaction_id
        assert "transaction_id" in transaction
        assert transaction["transaction_id"].startswith("USER")

        # Verify NO documents have transaction_id
        assert len(transaction["documents"]) == 3
        for i, doc in enumerate(transaction["documents"]):
            assert "transaction_id" not in doc, \
                f"Document {i} ({doc['file_name']}) should NOT have transaction_id"

            # Verify document has expected fields
            assert "file_name" in doc
            assert "original_url" in doc
            assert "status" in doc

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_transaction_id_format_validation(self):
        """
        Verify transaction_id follows USER + 6-digit format.

        Format: USER######  or  USER{timestamp}{random}
        """
        await database.connect()

        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        documents = [
            {
                "file_name": "format_test.pdf",
                "file_size": 50000,
                "original_url": "https://drive.google.com/file/d/FORMAT/view",
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
            }
        ]

        result_id = await create_user_transaction(
            user_name="Format Test User",
            user_email="format@example.com",
            documents=documents,
            number_of_units=5,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="de",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        transaction_id = transaction["transaction_id"]

        # Verify format
        assert transaction_id.startswith("USER"), f"Should start with USER, got {transaction_id}"

        numeric_part = transaction_id[4:]  # Remove "USER" prefix
        assert numeric_part.isdigit(), f"Numeric part should be digits, got {numeric_part}"

        # Standard format: 6 digits, Fallback format: 16+ digits
        assert len(numeric_part) == 6 or len(numeric_part) >= 16, \
            f"Should be 6 digits (standard) or 16+ (fallback), got {len(numeric_part)} digits"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})


"""
Test Coverage Summary:

1. Parent-Level Structure (1 test)
   - transaction_id exists at parent level
   - transaction_id uses USER format
   - Documents array does NOT contain transaction_id

2. Multiple Documents (1 test)
   - Multiple documents verified to NOT have transaction_id
   - Parent-level transaction_id is preserved

3. Format Validation (1 test)
   - USER + 6-digit format validation
   - Fallback format support

Total: 3 focused tests covering the correct structure

All tests:
- Use real MongoDB connection
- Verify transaction_id at parent level ONLY
- Verify documents array does NOT have transaction_id
- Clean up test data automatically
"""
