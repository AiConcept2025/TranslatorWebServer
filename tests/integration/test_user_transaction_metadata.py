"""
Integration tests for user transaction metadata feature.

This test module validates that the MongoDB `_id` field is correctly added to
document metadata (transaction_id field) for ALL user transactions.

Feature: When a user transaction is created, the MongoDB-generated _id should be
added to all documents[].transaction_id field, regardless of whether the transaction
is for an enterprise or individual customer.

Test Database: translation_test (separate from production)
Uses: Real MongoDB connection via Motor (Motor is async driver for MongoDB)
"""

import pytest
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from app.database.mongodb import database
from app.utils.user_transaction_helper import create_user_transaction


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def user_test_documents():
    """Sample documents for user transaction testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "file_name": "resume.pdf",
            "file_size": 102400,
            "original_url": "https://drive.google.com/file/d/TEST_USER_001/view",
            "translated_url": None,
            "translated_name": None,
            "status": "uploaded",
            "uploaded_at": now,
            "translated_at": None,
            "processing_started_at": None,
            "processing_duration": None
        },
        {
            "file_name": "cover_letter.docx",
            "file_size": 51200,
            "original_url": "https://drive.google.com/file/d/TEST_USER_002/view",
            "translated_url": None,
            "translated_name": None,
            "status": "uploaded",
            "uploaded_at": now,
            "translated_at": None,
            "processing_started_at": None,
            "processing_duration": None
        }
    ]


@pytest.fixture
def single_user_test_document():
    """Single document for user transaction testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "file_name": "passport.pdf",
            "file_size": 76800,
            "original_url": "https://drive.google.com/file/d/TEST_USER_SINGLE/view",
            "translated_url": None,
            "translated_name": None,
            "status": "uploaded",
            "uploaded_at": now,
            "translated_at": None,
            "processing_started_at": None,
            "processing_duration": None
        }
    ]


@pytest.fixture
def multiple_user_test_documents():
    """Multiple documents (3) for user transaction testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "file_name": f"document_{i}.pdf",
            "file_size": 51200 * (i + 1),
            "original_url": f"https://drive.google.com/file/d/TEST_USER_MULTI_{i}/view",
            "translated_url": None,
            "translated_name": None,
            "status": "uploaded",
            "uploaded_at": now,
            "translated_at": None,
            "processing_started_at": None,
            "processing_duration": None
        }
        for i in range(1, 4)
    ]


# ============================================================================
# 1. User Transaction Transaction_ID Tests
# ============================================================================

class TestUserTransactionMetadata:
    """Test transaction_id metadata for user transactions."""

    @pytest.mark.asyncio
    async def test_user_transaction_adds_transaction_id_to_documents(
        self, user_test_documents
    ):
        """
        Verify user transactions have transaction_id in document metadata.

        When a user transaction is created, all documents[].transaction_id
        should be populated with the MongoDB _id.
        """
        await database.connect()

        # Setup: Create user transaction
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Test User",
            user_email="testuser@example.com",
            documents=user_test_documents,
            number_of_units=10,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="es",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing",
            square_payment_id=square_transaction_id,
            amount_cents=1000,
            currency="USD",
            payment_status="COMPLETED",
            payment_date=datetime.now(timezone.utc),
            refunds=[]
        )

        # Verify: Function returns square_transaction_id
        assert result_id is not None, "create_user_transaction should return transaction ID"
        assert result_id == square_transaction_id, "Should return square_transaction_id"

        # Retrieve transaction from database using square_transaction_id
        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify: Transaction exists and has documents
        assert transaction is not None, "Transaction should exist in database"
        assert "documents" in transaction, "Transaction should have documents field"
        assert isinstance(transaction["documents"], list), "Documents should be a list"
        assert len(transaction["documents"]) == 2, "Should have 2 documents"

        # Get the MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])
        assert ObjectId.is_valid(mongodb_id), "MongoDB _id should be valid ObjectId"

        # Verify: All documents have transaction_id field
        for i, doc in enumerate(transaction["documents"]):
            assert "transaction_id" in doc, \
                f"Document {i} should have transaction_id field"
            assert doc["transaction_id"] is not None, \
                f"Document {i} transaction_id should not be None"
            assert isinstance(doc["transaction_id"], str), \
                f"Document {i} transaction_id should be string, got {type(doc['transaction_id'])}"

            # Verify: transaction_id matches MongoDB _id
            assert doc["transaction_id"] == mongodb_id, \
                f"Document {i} transaction_id {doc['transaction_id']} should match MongoDB _id {mongodb_id}"

            # Verify: transaction_id is valid ObjectId format
            assert ObjectId.is_valid(doc["transaction_id"]), \
                f"Document {i} transaction_id {doc['transaction_id']} should be valid ObjectId string"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_single_document_gets_transaction_id(
        self, single_user_test_document
    ):
        """
        Verify single-document user transactions get transaction_id.

        Edge case: Single document in user transaction should still
        receive the transaction_id field.
        """
        await database.connect()

        # Setup: Create user transaction with single document
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Single Doc User",
            user_email="singleuser@example.com",
            documents=single_user_test_document,
            number_of_units=3,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="fr",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        # Verify: Function returns square_transaction_id
        assert result_id is not None
        assert result_id == square_transaction_id

        # Retrieve transaction
        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify: Only one document
        assert transaction is not None
        assert len(transaction["documents"]) == 1, "Should have exactly 1 document"

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])
        assert ObjectId.is_valid(mongodb_id), "MongoDB _id should be valid ObjectId"

        # Verify: Single document has transaction_id
        doc = transaction["documents"][0]
        assert "transaction_id" in doc, "Single document should have transaction_id"
        assert doc["transaction_id"] == mongodb_id, \
            f"Document transaction_id {doc['transaction_id']} should match MongoDB _id {mongodb_id}"
        assert ObjectId.is_valid(doc["transaction_id"]), \
            f"Document transaction_id {doc['transaction_id']} should be valid ObjectId"
        assert isinstance(doc["transaction_id"], str), \
            f"Document transaction_id should be string, got {type(doc['transaction_id'])}"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_multiple_documents_same_transaction_id(
        self, user_test_documents
    ):
        """
        Verify all documents in user transaction get the same transaction_id.

        When multiple documents are in the same user transaction,
        they should all have identical transaction_id matching the parent transaction's MongoDB _id.
        """
        await database.connect()

        # Setup: Create user transaction
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Multi Doc User",
            user_email="multiuser@example.com",
            documents=user_test_documents,
            number_of_units=15,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="de",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        # Retrieve and verify
        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        assert transaction is not None
        assert len(transaction["documents"]) == 2, "Should have 2 documents"

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])

        # Collect all transaction_ids from documents
        transaction_ids = set()
        for doc in transaction["documents"]:
            assert "transaction_id" in doc, "Document should have transaction_id"
            transaction_ids.add(doc["transaction_id"])

        # Verify: All documents have the SAME transaction_id
        assert len(transaction_ids) == 1, \
            "All documents should have identical transaction_id"

        # Verify: It matches the parent transaction's MongoDB _id
        actual_transaction_id = transaction_ids.pop()
        assert actual_transaction_id == mongodb_id, \
            f"All documents' transaction_id should match MongoDB _id {mongodb_id}"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_id_valid_objectid_format(
        self, user_test_documents
    ):
        """
        Verify transaction_id in documents is a valid ObjectId string format.

        The transaction_id should be exactly 24 hexadecimal characters representing
        a valid MongoDB ObjectId, not any other format.
        """
        await database.connect()

        # Setup: Create user transaction
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Format Check User",
            user_email="formatuser@example.com",
            documents=user_test_documents,
            number_of_units=8,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="it",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify each document's transaction_id format
        for i, doc in enumerate(transaction["documents"]):
            txn_id = doc["transaction_id"]

            # Verify string type
            assert isinstance(txn_id, str), \
                f"Document {i}: Expected string, got {type(txn_id)}"

            # Verify length (MongoDB ObjectId string is 24 chars)
            assert len(txn_id) == 24, \
                f"Document {i}: ObjectId string should be 24 chars, got {len(txn_id)}"

            # Verify hex format (all valid hex characters)
            try:
                int(txn_id, 16)  # This will raise ValueError if not valid hex
                is_valid_hex = True
            except ValueError:
                is_valid_hex = False

            assert is_valid_hex, \
                f"Document {i}: transaction_id {txn_id} is not valid hexadecimal"

            # Verify as MongoDB ObjectId
            assert ObjectId.is_valid(txn_id), \
                f"Document {i}: transaction_id {txn_id} is not a valid MongoDB ObjectId format"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_id_string_type(self, user_test_documents):
        """
        Verify transaction_id is stored as string type in MongoDB.

        The transaction_id must be a string representation of the ObjectId,
        not the ObjectId object itself.
        """
        await database.connect()

        # Setup: Create user transaction
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        await create_user_transaction(
            user_name="String Type User",
            user_email="stringtypeuser@example.com",
            documents=user_test_documents,
            number_of_units=6,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="pt",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify: Each document's transaction_id is a string
        for i, doc in enumerate(transaction["documents"]):
            assert isinstance(doc["transaction_id"], str), \
                f"Document {i}: transaction_id should be str, got {type(doc['transaction_id'])}"

            # Verify: Cannot convert to ObjectId constructor directly
            # (it must already be the string representation)
            obj_id = ObjectId(doc["transaction_id"])
            assert str(obj_id) == doc["transaction_id"], \
                f"Document {i}: ObjectId string conversion should match"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_id_not_objectid_type(
        self, user_test_documents
    ):
        """
        Verify transaction_id is NOT stored as ObjectId type object.

        For JSON serialization compatibility, transaction_id must be
        a string, not a BSON ObjectId object.
        """
        await database.connect()

        # Setup: Create user transaction
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        await create_user_transaction(
            user_name="Not ObjectId Type User",
            user_email="notobjtypeuser@example.com",
            documents=user_test_documents,
            number_of_units=7,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="zh",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify: transaction_id is NOT ObjectId type
        for i, doc in enumerate(transaction["documents"]):
            assert not isinstance(doc["transaction_id"], ObjectId), \
                f"Document {i}: transaction_id should be string, not ObjectId object"

            # Verify: It's a string
            assert isinstance(doc["transaction_id"], str), \
                f"Document {i}: transaction_id should be string type"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})


# ============================================================================
# 2. Multiple Documents and Array Handling Tests
# ============================================================================

class TestUserTransactionMultipleDocuments:
    """Test correct handling of arrays with multiple documents."""

    @pytest.mark.asyncio
    async def test_user_transaction_three_documents_all_get_transaction_id(
        self, multiple_user_test_documents
    ):
        """
        Verify all 3 documents in user transaction get transaction_id.

        MongoDB array update operator $[] should update ALL array elements.
        """
        await database.connect()

        # Setup: Create user transaction with 3 documents
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Three Docs User",
            user_email="threedocsuser@example.com",
            documents=multiple_user_test_documents,
            number_of_units=25,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="ar",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify: All 3 documents present
        assert len(transaction["documents"]) == 3, "Should have exactly 3 documents"

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])

        # Verify: ALL documents have transaction_id
        transaction_ids_found = []
        for i, doc in enumerate(transaction["documents"]):
            assert "transaction_id" in doc, \
                f"Document {i} should have transaction_id"
            assert doc["transaction_id"] == mongodb_id, \
                f"Document {i} transaction_id should match MongoDB _id"
            transaction_ids_found.append(doc["transaction_id"])

        # Verify: All are identical
        assert len(set(transaction_ids_found)) == 1, \
            "All 3 documents should have identical transaction_id"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_mongodb_id_consistency(
        self, user_test_documents
    ):
        """
        Verify document transaction_id matches the MongoDB _id field.

        The document.transaction_id should exactly match the transaction's
        MongoDB _id field (converted to string).
        """
        await database.connect()

        # Setup: Create user transaction
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Consistency Check User",
            user_email="consistencyuser@example.com",
            documents=user_test_documents,
            number_of_units=12,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="ko",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions

        # Retrieve raw MongoDB document
        mongodb_doc = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Verify: Transaction's MongoDB _id
        assert "_id" in mongodb_doc, "Transaction should have _id field"
        mongodb_id = mongodb_doc["_id"]
        assert isinstance(mongodb_id, ObjectId), f"_id should be ObjectId, got {type(mongodb_id)}"

        # Convert to string for comparison
        mongodb_id_str = str(mongodb_id)

        # Verify: All documents have matching transaction_id
        for i, doc in enumerate(mongodb_doc["documents"]):
            assert doc["transaction_id"] == mongodb_id_str, \
                f"Document {i} transaction_id {doc['transaction_id']} should match MongoDB _id {mongodb_id_str}"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})


# ============================================================================
# 3. Square Payment Integration Tests
# ============================================================================

class TestUserTransactionPaymentIntegration:
    """Test transaction_id with various Square payment scenarios."""

    @pytest.mark.asyncio
    async def test_user_transaction_with_custom_payment_fields(
        self, user_test_documents
    ):
        """
        Verify transaction_id is added regardless of payment field values.

        Transaction_id should be consistently added to all documents
        regardless of different payment status or amount configurations.
        """
        await database.connect()

        # Setup: Create user transaction with custom payment fields
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Payment Fields User",
            user_email="paymentuser@example.com",
            documents=user_test_documents,
            number_of_units=5,
            unit_type="word",
            cost_per_unit=0.05,
            source_language="en",
            target_language="ja",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing",
            square_payment_id="custom_payment_id_12345",
            amount_cents=2500,  # $25.00
            currency="USD",
            payment_status="APPROVED",  # Different from default COMPLETED
            payment_date=datetime.now(timezone.utc)
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])

        # Verify: All documents still have transaction_id
        for doc in transaction["documents"]:
            assert "transaction_id" in doc
            assert doc["transaction_id"] == mongodb_id
            assert ObjectId.is_valid(doc["transaction_id"])

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_with_refunds_array(
        self, single_user_test_document
    ):
        """
        Verify transaction_id is added even when refunds array is populated.

        The presence of refund data should not affect document metadata updates.
        """
        await database.connect()

        # Setup: Create refund data
        refund_data = [
            {
                "refund_id": "REFUND_123",
                "amount_cents": 500,
                "currency": "USD",
                "status": "COMPLETED",
                "idempotency_key": "idempotent_123",
                "reason": "Partial refund"
            }
        ]

        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Refund User",
            user_email="refunduser@example.com",
            documents=single_user_test_document,
            number_of_units=2,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="ru",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing",
            payment_status="COMPLETED",
            refunds=refund_data
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])

        # Verify: Document still has transaction_id
        doc = transaction["documents"][0]
        assert "transaction_id" in doc
        assert doc["transaction_id"] == mongodb_id

        # Verify: Refund data is preserved
        assert "refunds" in transaction
        assert len(transaction["refunds"]) == 1

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})


# ============================================================================
# 4. Edge Cases and Error Handling Tests
# ============================================================================

class TestUserTransactionEdgeCases:
    """Test edge cases for transaction_id metadata handling."""

    @pytest.mark.asyncio
    async def test_user_transaction_different_unit_types(
        self, user_test_documents
    ):
        """
        Verify transaction_id is added regardless of unit_type.

        Should work with page, word, and character unit types.
        """
        await database.connect()

        # Test with "word" unit type
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Word Count User",
            user_email="worduser@example.com",
            documents=user_test_documents,
            number_of_units=1000,
            unit_type="word",
            cost_per_unit=0.01,
            source_language="en",
            target_language="hi",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])

        # Verify: All documents have transaction_id
        for doc in transaction["documents"]:
            assert "transaction_id" in doc
            assert doc["transaction_id"] == mongodb_id

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_different_statuses(
        self, user_test_documents
    ):
        """
        Verify transaction_id is added for different transaction statuses.

        Should work with processing, completed, and failed statuses.
        """
        await database.connect()

        # Test with "completed" status
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Completed User",
            user_email="completeduser@example.com",
            documents=user_test_documents,
            number_of_units=4,
            unit_type="page",
            cost_per_unit=0.15,
            source_language="en",
            target_language="th",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="completed"  # Different status
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])

        # Verify: All documents have transaction_id
        for doc in transaction["documents"]:
            assert "transaction_id" in doc
            assert doc["transaction_id"] == mongodb_id

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_datetime_fields_preserved(
        self, user_test_documents
    ):
        """
        Verify transaction_id addition doesn't affect datetime field integrity.

        Datetime fields in documents should remain as datetime objects
        even after transaction_id is added.
        """
        await database.connect()

        # Setup: Create user transaction
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Datetime User",
            user_email="datetimeuser@example.com",
            documents=user_test_documents,
            number_of_units=5,
            unit_type="page",
            cost_per_unit=0.10,
            source_language="en",
            target_language="tr",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])

        # Verify: Datetime fields are preserved as datetime objects
        for i, doc in enumerate(transaction["documents"]):
            assert "uploaded_at" in doc
            assert isinstance(doc["uploaded_at"], datetime), \
                f"Document {i}: uploaded_at should be datetime, got {type(doc['uploaded_at'])}"

            # transaction_id should still be string
            assert isinstance(doc["transaction_id"], str), \
                f"Document {i}: transaction_id should be string after date preservation"
            assert doc["transaction_id"] == mongodb_id, \
                f"Document {i}: transaction_id should match MongoDB _id"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})

    @pytest.mark.asyncio
    async def test_user_transaction_all_documents_same_transaction_id_with_different_names(
        self, multiple_user_test_documents
    ):
        """
        Verify all documents with different names get same transaction_id.

        Even though documents have different file_names, they should all
        receive the same transaction_id.
        """
        await database.connect()

        # Setup: Create user transaction with distinctly named documents
        square_transaction_id = f"sqt_TEST{uuid.uuid4().hex[:16].upper()}"

        result_id = await create_user_transaction(
            user_name="Different Names User",
            user_email="diffnamesuser@example.com",
            documents=multiple_user_test_documents,
            number_of_units=9,
            unit_type="page",
            cost_per_unit=0.12,
            source_language="en",
            target_language="vi",
            square_transaction_id=square_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing"
        )

        collection = database.user_transactions
        transaction = await collection.find_one({"square_transaction_id": square_transaction_id})

        # Get MongoDB _id for comparison
        mongodb_id = str(transaction["_id"])

        # Verify: All documents with different names have same transaction_id
        transaction_ids = []
        file_names = []
        for doc in transaction["documents"]:
            file_names.append(doc["file_name"])
            transaction_ids.append(doc["transaction_id"])

        # All file names should be different
        assert len(set(file_names)) == len(file_names), \
            "Documents should have different file_names"

        # But all transaction_ids should be identical
        assert len(set(transaction_ids)) == 1, \
            "All documents should have same transaction_id despite different names"

        # And should match the MongoDB _id
        assert transaction_ids[0] == mongodb_id, \
            f"transaction_id should match MongoDB _id {mongodb_id}"

        # Cleanup
        await collection.delete_one({"square_transaction_id": square_transaction_id})


# ============================================================================
# Integration Test Summary
# ============================================================================

"""
Test Coverage Summary:

1. User Transaction Metadata (5 tests)
   - transaction_id IS added to all documents
   - Single document gets transaction_id
   - Multiple documents all get same transaction_id
   - transaction_id is valid ObjectId format string
   - transaction_id is string type, not ObjectId object

2. Multiple Documents Handling (2 tests)
   - Three documents all get transaction_id
   - MongoDB _id consistency verification

3. Square Payment Integration (2 tests)
   - transaction_id added with custom payment fields
   - transaction_id added even with refunds array

4. Edge Cases (4 tests)
   - Different unit_type values
   - Different transaction statuses
   - Datetime fields preserved
   - All documents get same transaction_id despite different names

Total: 13 comprehensive integration tests covering:
- MongoDB _id generation and assignment to document metadata
- Document array handling with $[] array operator
- Type safety (string vs ObjectId)
- Serialization format (valid hex string)
- Edge cases (single doc, multiple docs, various configs)
- Data integrity (datetime fields preserved)
- Square payment field interactions

All tests:
- Use real MongoDB connection (translation_test database)
- Create and clean up test data (using sqt_TEST prefix)
- Validate field types and values
- Verify MongoDB operations
- Test both basic and advanced scenarios
- Ensure transaction_id consistency across all documents
"""
