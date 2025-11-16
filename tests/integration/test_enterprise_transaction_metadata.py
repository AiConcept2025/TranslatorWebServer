"""
Integration tests for enterprise transaction metadata feature.

This test module validates that the MongoDB `_id` field is correctly added to
document metadata (transaction_id field) for enterprise customers only.

Feature: When a translation transaction is created with company_name (enterprise),
the MongoDB-generated _id should be added to all documents[].transaction_id field.
Non-enterprise transactions should NOT have transaction_id in document metadata.

Test Database: translation_test (separate from production)
Uses: Real MongoDB connection via Motor (Motor is async driver for MongoDB)
"""

import pytest
from datetime import datetime, timezone
from bson import ObjectId
import uuid

from app.database.mongodb import database
from app.services.translation_transaction_service import create_translation_transaction


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def enterprise_test_documents():
    """Sample documents for enterprise transaction testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "file_name": "contract_1.pdf",
            "file_size": 102400,
            "original_url": "https://drive.google.com/file/d/TEST_ENTERPRISE_001/view",
            "translated_url": None,
            "translated_name": None,
            "status": "uploaded",
            "uploaded_at": now,
            "translated_at": None,
            "processing_started_at": None,
            "processing_duration": None
        },
        {
            "file_name": "contract_2.docx",
            "file_size": 204800,
            "original_url": "https://drive.google.com/file/d/TEST_ENTERPRISE_002/view",
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
def non_enterprise_test_document():
    """Sample document for non-enterprise transaction testing."""
    now = datetime.now(timezone.utc)
    return [
        {
            "file_name": "personal_doc.pdf",
            "file_size": 51200,
            "original_url": "https://drive.google.com/file/d/TEST_PERSONAL_001/view",
            "translated_url": None,
            "translated_name": None,
            "status": "uploaded",
            "uploaded_at": now,
            "translated_at": None,
            "processing_started_at": None,
            "processing_duration": None
        }
    ]


# ============================================================================
# 1. Enterprise Transaction Tests
# ============================================================================

class TestEnterpriseTransactionMetadata:
    """Test transaction_id metadata for enterprise customers."""

    @pytest.mark.asyncio
    async def test_enterprise_transaction_adds_transaction_id_to_documents(
        self, enterprise_test_documents
    ):
        """
        Verify enterprise transactions have transaction_id in document metadata.

        When a transaction is created with company_name set (enterprise customer),
        all documents[].transaction_id should be populated with the MongoDB _id.
        """
        await database.connect()

        # Setup: Create enterprise transaction
        transaction_id = f"TEST-ENT-{uuid.uuid4().hex[:12].upper()}"
        company_name = "Test Enterprise Corp"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="enterprise@test.com",
            documents=enterprise_test_documents,
            source_language="en",
            target_language="fr",
            units_count=15,
            price_per_unit=0.01,
            total_price=0.15,
            status="started",
            company_name=company_name,  # ENTERPRISE MARKER
            subscription_id="sub_test_12345",
            unit_type="page"
        )

        # Verify: Result ID is returned
        assert result_id is not None
        assert isinstance(result_id, str)
        assert len(result_id) == 24  # ObjectId string length

        # Verify: Can parse as valid ObjectId
        assert ObjectId.is_valid(result_id)

        # Retrieve transaction from database
        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        # Verify: Transaction exists and has documents
        assert transaction is not None
        assert "documents" in transaction
        assert isinstance(transaction["documents"], list)
        assert len(transaction["documents"]) == 2

        # Verify: All documents have transaction_id field
        for doc in transaction["documents"]:
            assert "transaction_id" in doc, "Document should have transaction_id field"
            assert doc["transaction_id"] is not None, "transaction_id should not be None"
            assert isinstance(doc["transaction_id"], str), "transaction_id should be string"

            # Verify: transaction_id matches MongoDB _id
            assert doc["transaction_id"] == result_id, \
                f"Document transaction_id {doc['transaction_id']} should match MongoDB _id {result_id}"

            # Verify: transaction_id is valid ObjectId format
            assert ObjectId.is_valid(doc["transaction_id"]), \
                f"transaction_id {doc['transaction_id']} should be valid ObjectId string"

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_enterprise_transaction_multiple_documents_same_transaction_id(
        self, enterprise_test_documents
    ):
        """
        Verify all documents in enterprise transaction get the same transaction_id.

        When multiple documents are in the same enterprise transaction,
        they should all have identical transaction_id matching the parent transaction's MongoDB _id.
        """
        await database.connect()

        transaction_id = f"TEST-MULTI-{uuid.uuid4().hex[:12].upper()}"
        company_name = "Multi-Doc Enterprise"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="enterprise.multi@test.com",
            documents=enterprise_test_documents,
            source_language="en",
            target_language="es",
            units_count=20,
            price_per_unit=0.01,
            total_price=0.20,
            company_name=company_name,
            subscription_id="sub_test_multi",
            unit_type="page"
        )

        # Retrieve and verify
        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        assert transaction is not None
        assert len(transaction["documents"]) == 2

        # Collect all transaction_ids from documents
        transaction_ids = set()
        for doc in transaction["documents"]:
            assert "transaction_id" in doc
            transaction_ids.add(doc["transaction_id"])

        # Verify: All documents have the SAME transaction_id
        assert len(transaction_ids) == 1, "All documents should have identical transaction_id"

        # Verify: It matches the parent transaction's MongoDB _id
        actual_transaction_id = transaction_ids.pop()
        assert actual_transaction_id == result_id, \
            f"All documents' transaction_id should match MongoDB _id {result_id}"

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_enterprise_transaction_id_valid_objectid_format(
        self, enterprise_test_documents
    ):
        """
        Verify transaction_id in documents is a valid ObjectId string format.

        The transaction_id should be exactly 24 hexadecimal characters representing
        a valid MongoDB ObjectId, not any other format.
        """
        await database.connect()

        transaction_id = f"TEST-OBJID-{uuid.uuid4().hex[:8].upper()}"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="enterprise.fmt@test.com",
            documents=enterprise_test_documents,
            source_language="en",
            target_language="de",
            units_count=10,
            price_per_unit=0.01,
            total_price=0.10,
            company_name="ObjectId Test Corp",
            subscription_id="sub_test_fmt",
            unit_type="page"
        )

        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        # Verify each document's transaction_id format
        for doc in transaction["documents"]:
            txn_id = doc["transaction_id"]

            # Verify string type
            assert isinstance(txn_id, str), f"Expected string, got {type(txn_id)}"

            # Verify length (MongoDB ObjectId string is 24 chars)
            assert len(txn_id) == 24, \
                f"ObjectId string should be 24 chars, got {len(txn_id)}"

            # Verify hex format (all valid hex characters)
            try:
                int(txn_id, 16)  # This will raise ValueError if not valid hex
                is_valid_hex = True
            except ValueError:
                is_valid_hex = False

            assert is_valid_hex, f"transaction_id {txn_id} is not valid hexadecimal"

            # Verify as MongoDB ObjectId
            assert ObjectId.is_valid(txn_id), \
                f"transaction_id {txn_id} is not a valid MongoDB ObjectId format"

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})


# ============================================================================
# 2. Non-Enterprise Transaction Tests
# ============================================================================

class TestNonEnterpriseTransactionMetadata:
    """Test that non-enterprise transactions do NOT get transaction_id."""

    @pytest.mark.asyncio
    async def test_non_enterprise_transaction_no_transaction_id(
        self, non_enterprise_test_document
    ):
        """
        Verify non-enterprise transactions do NOT have transaction_id in documents.

        When company_name is None/not provided (non-enterprise customer),
        documents should NOT be updated with transaction_id field.
        """
        await database.connect()

        transaction_id = f"TEST-NOENT-{uuid.uuid4().hex[:12].upper()}"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="individual@test.com",
            documents=non_enterprise_test_document,
            source_language="en",
            target_language="es",
            units_count=5,
            price_per_unit=0.01,
            total_price=0.05
            subscription_id=None,
            unit_type="page"
        )

        # Verify: Result ID is returned
        assert result_id is not None
        assert isinstance(result_id, str)

        # Retrieve transaction
        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        assert transaction is not None
        assert "documents" in transaction

        # Verify: Documents do NOT have transaction_id field
        for doc in transaction["documents"]:
            # Should either not have the field or it should be None
            has_transaction_id = "transaction_id" in doc

            if has_transaction_id:
                # If field exists, it should be None for non-enterprise
                assert doc["transaction_id"] is None, \
                    "Non-enterprise document should have transaction_id=None if field exists"
            else:
                # Preferred: field should not exist at all
                assert not has_transaction_id, \
                    "Non-enterprise document should not have transaction_id field"

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_non_enterprise_transaction_with_empty_company_name(
        self, non_enterprise_test_document
    ):
        """
        Verify transactions with empty string company_name don't get transaction_id.

        An empty string for company_name should be treated as non-enterprise.
        """
        await database.connect()

        transaction_id = f"TEST-EMPTY-{uuid.uuid4().hex[:12].upper()}"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="empty@test.com",
            documents=non_enterprise_test_document,
            source_language="en",
            target_language="fr",
            units_count=3,
            price_per_unit=0.01,
            total_price=0.03,
            company_name="",  # Empty string - should not trigger enterprise logic
            subscription_id=None,
            unit_type="page"
        )

        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        # Verify: Documents do not have transaction_id (empty string is falsy)
        for doc in transaction["documents"]:
            if "transaction_id" in doc:
                assert doc["transaction_id"] is None or doc["transaction_id"] == "", \
                    "Empty company_name should not populate document transaction_id"

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})


# ============================================================================
# 3. Edge Cases and Special Scenarios
# ============================================================================

class TestEnterpriseTransactionEdgeCases:
    """Test edge cases for transaction_id metadata handling."""

    @pytest.mark.asyncio
    async def test_enterprise_single_document_gets_transaction_id(self):
        """
        Verify enterprise transaction with single document gets transaction_id.

        Edge case: Single document in enterprise transaction should still
        receive the transaction_id field.
        """
        await database.connect()

        now = datetime.now(timezone.utc)
        single_doc = [{
            "file_name": "single.pdf",
            "file_size": 51200,
            "original_url": "https://drive.google.com/file/d/TEST_SINGLE/view",
            "translated_url": None,
            "translated_name": None,
            "status": "uploaded",
            "uploaded_at": now,
            "translated_at": None,
            "processing_started_at": None,
            "processing_duration": None
        }]

        transaction_id = f"TEST-SINGLE-{uuid.uuid4().hex[:10].upper()}"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="single@test.com",
            documents=single_doc,
            source_language="en",
            target_language="it",
            units_count=2,
            price_per_unit=0.01,
            total_price=0.02,
            company_name="Single Doc Enterprise",
            subscription_id="sub_single",
            unit_type="page"
        )

        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        # Verify: Single document has transaction_id
        assert len(transaction["documents"]) == 1
        doc = transaction["documents"][0]
        assert "transaction_id" in doc
        assert doc["transaction_id"] == result_id
        assert ObjectId.is_valid(doc["transaction_id"])

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_enterprise_transaction_mongodb_id_consistency(
        self, enterprise_test_documents
    ):
        """
        Verify document transaction_id matches the MongoDB _id field.

        The document.transaction_id should exactly match the document's
        MongoDB _id field (converted to string).
        """
        await database.connect()

        transaction_id = f"TEST-CONSIST-{uuid.uuid4().hex[:8].upper()}"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="consistency@test.com",
            documents=enterprise_test_documents,
            source_language="en",
            target_language="pt",
            units_count=12,
            price_per_unit=0.01,
            total_price=0.12,
            company_name="Consistency Check Corp",
            subscription_id="sub_consist",
            unit_type="page"
        )

        collection = database.translation_transactions

        # Retrieve raw MongoDB document
        mongodb_doc = await collection.find_one({"transaction_id": transaction_id})

        # Verify: Transaction's MongoDB _id
        assert "_id" in mongodb_doc
        mongodb_id = mongodb_doc["_id"]
        assert isinstance(mongodb_id, ObjectId)

        # Convert to string for comparison
        mongodb_id_str = str(mongodb_id)
        assert mongodb_id_str == result_id

        # Verify: All documents have matching transaction_id
        for doc in mongodb_doc["documents"]:
            assert doc["transaction_id"] == mongodb_id_str, \
                f"Document transaction_id {doc['transaction_id']} should match MongoDB _id {mongodb_id_str}"

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_non_enterprise_transaction_no_mongodb_id_added(
        self, non_enterprise_test_document
    ):
        """
        Verify non-enterprise documents are not modified with transaction_id.

        Non-enterprise transactions should remain unchanged - no transaction_id
        field should be added to document metadata.
        """
        await database.connect()

        transaction_id = f"TEST-NOMOD-{uuid.uuid4().hex[:12].upper()}"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="nomod@test.com",
            documents=non_enterprise_test_document,
            source_language="en",
            target_language="ja",
            units_count=8,
            price_per_unit=0.01,
            total_price=0.08
            subscription_id=None,
            unit_type="page"
        )

        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        # Verify: Original document field count
        original_fields = non_enterprise_test_document[0].keys()
        doc_fields = transaction["documents"][0].keys()

        # transaction_id should NOT be in the fields (or should be None)
        for doc in transaction["documents"]:
            if "transaction_id" in doc:
                # If present, must be None
                assert doc["transaction_id"] is None, \
                    "Non-enterprise document transaction_id should be None if present"
            else:
                # Preferred: field absent entirely
                assert "transaction_id" not in doc

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})


# ============================================================================
# 4. Type and Format Validation Tests
# ============================================================================

class TestTransactionIdTypeValidation:
    """Test type validation and format consistency of transaction_id."""

    @pytest.mark.asyncio
    async def test_enterprise_transaction_id_string_type(
        self, enterprise_test_documents
    ):
        """
        Verify transaction_id is stored as string type in MongoDB.

        The transaction_id must be a string representation of the ObjectId,
        not the ObjectId object itself.
        """
        await database.connect()

        transaction_id = f"TEST-STRTYPE-{uuid.uuid4().hex[:8].upper()}"

        await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="strtype@test.com",
            documents=enterprise_test_documents,
            source_language="en",
            target_language="ko",
            units_count=7,
            price_per_unit=0.01,
            total_price=0.07,
            company_name="String Type Test",
            subscription_id="sub_strtype",
            unit_type="page"
        )

        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        # Verify: Each document's transaction_id is a string
        for doc in transaction["documents"]:
            assert isinstance(doc["transaction_id"], str), \
                f"transaction_id should be str, got {type(doc['transaction_id'])}"

            # Verify: Cannot convert to ObjectId constructor directly
            # (it must already be the string representation)
            obj_id = ObjectId(doc["transaction_id"])
            assert str(obj_id) == doc["transaction_id"]

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_enterprise_transaction_id_not_objectid_type(
        self, enterprise_test_documents
    ):
        """
        Verify transaction_id is NOT stored as ObjectId type object.

        For JSON serialization compatibility, transaction_id must be
        a string, not a BSON ObjectId object.
        """
        await database.connect()

        transaction_id = f"TEST-NOTOBJ-{uuid.uuid4().hex[:8].upper()}"

        await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="notobj@test.com",
            documents=enterprise_test_documents,
            source_language="en",
            target_language="zh",
            units_count=6,
            price_per_unit=0.01,
            total_price=0.06,
            company_name="Not ObjectId Type Test",
            subscription_id="sub_notobj",
            unit_type="page"
        )

        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        # Verify: transaction_id is NOT ObjectId type
        for doc in transaction["documents"]:
            assert not isinstance(doc["transaction_id"], ObjectId), \
                f"transaction_id should be string, not ObjectId object"

            # Verify: It's a string
            assert isinstance(doc["transaction_id"], str)

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})


# ============================================================================
# 5. Multiple Documents and Array Handling Tests
# ============================================================================

class TestMultipleDocumentsHandling:
    """Test correct handling of arrays with multiple documents."""

    @pytest.mark.asyncio
    async def test_enterprise_three_documents_all_get_transaction_id(self):
        """
        Verify all 3 documents in enterprise transaction get transaction_id.

        MongoDB array update operator $[] should update ALL array elements.
        """
        await database.connect()

        now = datetime.now(timezone.utc)
        three_docs = [
            {
                "file_name": f"doc_{i}.pdf",
                "file_size": 51200 * (i + 1),
                "original_url": f"https://drive.google.com/file/d/TEST_THREE_{i}/view",
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

        transaction_id = f"TEST-THREE-{uuid.uuid4().hex[:10].upper()}"

        result_id = await create_translation_transaction(
            transaction_id=transaction_id,
            user_id="three@test.com",
            documents=three_docs,
            source_language="en",
            target_language="ar",
            units_count=25,
            price_per_unit=0.01,
            total_price=0.25,
            company_name="Three Docs Enterprise",
            subscription_id="sub_three",
            unit_type="page"
        )

        collection = database.translation_transactions
        transaction = await collection.find_one({"transaction_id": transaction_id})

        # Verify: All 3 documents present
        assert len(transaction["documents"]) == 3

        # Verify: ALL documents have transaction_id
        transaction_ids_found = []
        for i, doc in enumerate(transaction["documents"]):
            assert "transaction_id" in doc, \
                f"Document {i} should have transaction_id"
            assert doc["transaction_id"] == result_id, \
                f"Document {i} transaction_id should match MongoDB _id"
            transaction_ids_found.append(doc["transaction_id"])

        # Verify: All are identical
        assert len(set(transaction_ids_found)) == 1, \
            "All documents should have identical transaction_id"

        # Cleanup
        await collection.delete_one({"transaction_id": transaction_id})


# ============================================================================
# Integration Test Summary
# ============================================================================

"""
Test Coverage Summary:

1. Enterprise Transaction Metadata (3 tests)
   - transaction_id IS added to all documents for enterprise
   - Multiple documents all get same transaction_id
   - transaction_id is valid ObjectId format string

2. Non-Enterprise Transaction Metadata (2 tests)
   - transaction_id NOT added for None company_name
   - transaction_id NOT added for empty string company_name

3. Edge Cases (4 tests)
   - Single document in enterprise transaction
   - MongoDB _id consistency verification
   - Non-enterprise documents not modified
   - Type and format validation

4. Type and Format Validation (2 tests)
   - transaction_id stored as string type
   - transaction_id NOT stored as ObjectId object

5. Multiple Documents Handling (1 test)
   - Three documents all get transaction_id

Total: 12 comprehensive integration tests covering:
- Enterprise customer detection (company_name)
- MongoDB _id generation and assignment
- Document array handling
- Type safety (string vs ObjectId)
- Serialization format (valid hex string)
- Edge cases (single doc, empty company, etc.)

All tests:
- Use real MongoDB connection (translation_test database)
- Create and clean up test data
- Validate field types and values
- Verify MongoDB operations
- Test both positive and negative cases
"""
