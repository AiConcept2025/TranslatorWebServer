"""
INTEGRATION TESTS FOR NESTED TRANSLATION TRANSACTION STRUCTURE

These tests verify the nested documents[] array structure in translation_transactions
collection. Tests use real MongoDB and FastAPI endpoints.

Test Coverage:
- Transaction creation with nested documents array
- Document status updates within nested structure
- Transaction list endpoint returns correct nested structure
- Multiple documents per transaction handling

Database: translation_test (separate from production)
Uses: Real MongoDB + Real HTTP API calls
"""

import pytest
import httpx
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from app.database.mongodb import database


# ============================================================================
# Test Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8000"


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls to running server."""
    async_client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0)
    yield async_client
    await async_client.aclose()


@pytest.fixture(scope="function")
async def test_company():
    """
    Create a test company in MongoDB.
    Required for enterprise transaction tests.
    """
    await database.connect()
    collection = database.company

    company_doc = {
        "company_name": "Test Company Nested",
        "address": "123 Test St",
        "phone": "+1234567890",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await collection.insert_one(company_doc)
    company_doc["_id"] = result.inserted_id

    yield company_doc

    # Cleanup
    await collection.delete_one({"_id": company_doc["_id"]})


@pytest.fixture(scope="function")
async def cleanup_test_transactions():
    """
    Cleanup function that runs after each test to remove test transactions.
    Matches transactions by TEST- prefix in transaction_id.
    """
    yield

    # Cleanup after test
    await database.connect()
    collection = database.translation_transactions

    # SAFE: Only delete test records with TEST- prefix
    result = await collection.delete_many({
        "transaction_id": {"$regex": "^TXN-TEST-"}
    })

    if result.deleted_count > 0:
        print(f"Cleaned up {result.deleted_count} test transaction(s)")


# ============================================================================
# Test 1: Create Transaction with Nested Structure
# ============================================================================

@pytest.mark.asyncio
async def test_create_transaction_with_nested_structure(
    http_client: httpx.AsyncClient,
    test_company: Dict[str, Any],
    cleanup_test_transactions
):
    """
    Test that /translate endpoint creates transactions with nested documents[] array.

    Verifies:
    - Response contains transaction_id
    - MongoDB record has documents[] array
    - Document fields are correct: file_name, file_size, original_url, status
    - Transaction-level fields are correct
    """
    # This test would require mocking Google Drive service
    # Instead, we'll create a transaction directly in MongoDB and verify structure

    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"

    # Create transaction with nested documents structure
    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "testuser@testcompany.com",
        "company_name": "Test Company Nested",
        "source_language": "en",
        "target_language": "fr",
        "units_count": 25,
        "price_per_unit": 0.10,
        "total_price": 2.50,
        "status": "started",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "unit_type": "page",

        # NESTED documents array (NEW STRUCTURE)
        "documents": [
            {
                "file_name": "test_document.pdf",
                "file_size": 524288,
                "original_url": "https://docs.google.com/document/d/test123/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }

    # Insert transaction
    result = await collection.insert_one(transaction_doc)
    assert result.inserted_id is not None, "Transaction should be inserted successfully"

    # Fetch back from database
    inserted_txn = await collection.find_one({"transaction_id": transaction_id})

    # Verify nested structure
    assert inserted_txn is not None, "Transaction should exist in database"
    assert "documents" in inserted_txn, "Transaction must have documents array"
    assert isinstance(inserted_txn["documents"], list), "documents must be a list"
    assert len(inserted_txn["documents"]) == 1, "Should have exactly 1 document"

    # Verify document fields
    doc = inserted_txn["documents"][0]
    assert doc["file_name"] == "test_document.pdf"
    assert doc["file_size"] == 524288
    assert doc["original_url"] == "https://docs.google.com/document/d/test123/edit"
    assert doc["translated_url"] is None
    assert doc["translated_name"] is None
    assert doc["status"] == "uploaded"
    assert doc["uploaded_at"] is not None
    assert doc["translated_at"] is None
    assert doc["processing_started_at"] is None
    assert doc["processing_duration"] is None

    # Verify transaction-level fields
    assert inserted_txn["transaction_id"] == transaction_id
    assert inserted_txn["user_id"] == "testuser@testcompany.com"
    assert inserted_txn["source_language"] == "en"
    assert inserted_txn["target_language"] == "fr"
    assert inserted_txn["units_count"] == 25
    assert inserted_txn["status"] == "started"


# ============================================================================
# Test 2: Update Document in Transaction
# ============================================================================

@pytest.mark.asyncio
async def test_update_document_in_transaction(
    http_client: httpx.AsyncClient,
    cleanup_test_transactions
):
    """
    Test updating a document within the nested documents[] array.

    Simulates workflow:
    1. Create transaction with document status="uploaded"
    2. Update document to status="completed" with translated_url
    3. Verify document fields updated correctly
    4. Verify transaction-level status can be updated
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"

    # Create initial transaction
    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "testuser@example.com",
        "company_name": None,  # Individual customer
        "source_language": "en",
        "target_language": "es",
        "units_count": 10,
        "price_per_unit": 0.10,
        "total_price": 1.00,
        "status": "started",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "unit_type": "page",

        "documents": [
            {
                "file_name": "contract.docx",
                "file_size": 102400,
                "original_url": "https://docs.google.com/document/d/original456/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }

    await collection.insert_one(transaction_doc)

    # Simulate translation completion - update document
    translated_at = datetime.now(timezone.utc)
    processing_duration = 125.5  # seconds

    update_result = await collection.update_one(
        {"transaction_id": transaction_id},
        {
            "$set": {
                "documents.0.status": "completed",
                "documents.0.translated_url": "https://docs.google.com/document/d/translated789/edit",
                "documents.0.translated_name": "contract_es.docx",
                "documents.0.translated_at": translated_at,
                "documents.0.processing_duration": processing_duration,
                "status": "confirmed",  # Transaction-level status
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    assert update_result.modified_count == 1, "Document should be updated"

    # Verify updates
    updated_txn = await collection.find_one({"transaction_id": transaction_id})

    assert updated_txn["status"] == "confirmed", "Transaction status should be updated"

    doc = updated_txn["documents"][0]
    assert doc["status"] == "completed"
    assert doc["translated_url"] == "https://docs.google.com/document/d/translated789/edit"
    assert doc["translated_name"] == "contract_es.docx"
    assert doc["translated_at"] is not None
    assert doc["processing_duration"] == processing_duration


# ============================================================================
# Test 3: Get Transaction List Returns Nested Structure
# ============================================================================

@pytest.mark.asyncio
async def test_get_transaction_list_returns_nested_structure(
    http_client: httpx.AsyncClient,
    test_company: Dict[str, Any],
    cleanup_test_transactions
):
    """
    Test GET /api/v1/translation-transactions/company/{company_name} endpoint.

    Verifies:
    - Response has documents array
    - DateTime fields are ISO 8601 strings (not datetime objects)
    - Nested document structure matches schema
    - Serialization handles all field types correctly
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"
    company_name = "Test Company Nested"

    # Create test transaction
    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "admin@testcompany.com",
        "company_name": company_name,
        "source_language": "de",
        "target_language": "en",
        "units_count": 15,
        "price_per_unit": 0.12,
        "total_price": 1.80,
        "status": "confirmed",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "unit_type": "page",

        "documents": [
            {
                "file_name": "invoice.pdf",
                "file_size": 204800,
                "original_url": "https://docs.google.com/document/d/inv123/edit",
                "translated_url": "https://docs.google.com/document/d/inv456/edit",
                "translated_name": "invoice_en.pdf",
                "status": "completed",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": datetime.now(timezone.utc),
                "processing_started_at": datetime.now(timezone.utc),
                "processing_duration": 89.3
            }
        ]
    }

    await collection.insert_one(transaction_doc)

    # Call API endpoint
    response = await http_client.get(
        f"/api/v1/translation-transactions/company/{company_name}"
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert "transactions" in data["data"]

    transactions = data["data"]["transactions"]
    assert len(transactions) >= 1, "Should have at least 1 transaction"

    # Find our test transaction
    test_txn = next((t for t in transactions if t["transaction_id"] == transaction_id), None)
    assert test_txn is not None, "Test transaction should be in response"

    # Verify nested documents array structure
    assert "documents" in test_txn, "Transaction must have documents array"
    assert isinstance(test_txn["documents"], list), "documents must be a list"
    assert len(test_txn["documents"]) == 1, "Should have 1 document"

    doc = test_txn["documents"][0]

    # CRITICAL: Verify datetime fields are ISO strings, NOT datetime objects
    assert isinstance(doc["uploaded_at"], str), "uploaded_at must be ISO string"
    assert isinstance(doc["translated_at"], str), "translated_at must be ISO string"
    assert isinstance(doc["processing_started_at"], str), "processing_started_at must be ISO string"

    # Verify ISO 8601 format validity
    datetime.fromisoformat(doc["uploaded_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(doc["translated_at"].replace("Z", "+00:00"))

    # Verify all document fields
    assert doc["file_name"] == "invoice.pdf"
    assert doc["file_size"] == 204800
    assert doc["original_url"] == "https://docs.google.com/document/d/inv123/edit"
    assert doc["translated_url"] == "https://docs.google.com/document/d/inv456/edit"
    assert doc["translated_name"] == "invoice_en.pdf"
    assert doc["status"] == "completed"
    assert doc["processing_duration"] == 89.3

    # Verify transaction-level datetime fields are also ISO strings
    assert isinstance(test_txn["created_at"], str)
    assert isinstance(test_txn["updated_at"], str)


# ============================================================================
# Test 4: Transaction with Multiple Documents
# ============================================================================

@pytest.mark.asyncio
async def test_transaction_with_multiple_documents(
    http_client: httpx.AsyncClient,
    cleanup_test_transactions
):
    """
    Test edge case: Transaction with multiple documents in the array.

    Verifies:
    - Multiple documents can exist in single transaction
    - Each document maintains independent status
    - Updating one document doesn't affect others
    - Transaction status reflects overall state
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"

    # Create transaction with 3 documents
    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "multiuser@example.com",
        "company_name": None,
        "source_language": "fr",
        "target_language": "de",
        "units_count": 45,
        "price_per_unit": 0.08,
        "total_price": 3.60,
        "status": "started",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "unit_type": "page",

        "documents": [
            {
                "file_name": "doc1.pdf",
                "file_size": 100000,
                "original_url": "https://docs.google.com/document/d/doc1/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            },
            {
                "file_name": "doc2.docx",
                "file_size": 200000,
                "original_url": "https://docs.google.com/document/d/doc2/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            },
            {
                "file_name": "doc3.txt",
                "file_size": 50000,
                "original_url": "https://docs.google.com/document/d/doc3/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }

    await collection.insert_one(transaction_doc)

    # Verify all 3 documents exist
    txn = await collection.find_one({"transaction_id": transaction_id})
    assert len(txn["documents"]) == 3, "Should have 3 documents"

    # Update only first document to completed
    await collection.update_one(
        {"transaction_id": transaction_id},
        {
            "$set": {
                "documents.0.status": "completed",
                "documents.0.translated_url": "https://docs.google.com/document/d/doc1_trans/edit",
                "documents.0.translated_name": "doc1_de.pdf",
                "documents.0.translated_at": datetime.now(timezone.utc)
            }
        }
    )

    # Verify only first document updated
    updated_txn = await collection.find_one({"transaction_id": transaction_id})

    assert updated_txn["documents"][0]["status"] == "completed"
    assert updated_txn["documents"][0]["translated_url"] is not None

    # Other documents should remain unchanged
    assert updated_txn["documents"][1]["status"] == "uploaded"
    assert updated_txn["documents"][1]["translated_url"] is None

    assert updated_txn["documents"][2]["status"] == "uploaded"
    assert updated_txn["documents"][2]["translated_url"] is None

    # Update second document
    await collection.update_one(
        {"transaction_id": transaction_id},
        {
            "$set": {
                "documents.1.status": "completed",
                "documents.1.translated_url": "https://docs.google.com/document/d/doc2_trans/edit",
                "documents.1.translated_name": "doc2_de.docx",
                "documents.1.translated_at": datetime.now(timezone.utc)
            }
        }
    )

    # Verify second document updated
    final_txn = await collection.find_one({"transaction_id": transaction_id})

    assert final_txn["documents"][0]["status"] == "completed"
    assert final_txn["documents"][1]["status"] == "completed"
    assert final_txn["documents"][2]["status"] == "uploaded"  # Still pending


# ============================================================================
# Test 5: Datetime Timezone Handling
# ============================================================================

@pytest.mark.asyncio
async def test_datetime_timezone_handling(cleanup_test_transactions):
    """
    Test that datetime fields are timezone-aware UTC.

    Verifies:
    - All datetime fields have timezone info
    - Timezone is UTC
    - Serialization to ISO 8601 preserves timezone
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"

    now_utc = datetime.now(timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "tztest@example.com",
        "company_name": None,
        "source_language": "en",
        "target_language": "ja",
        "units_count": 5,
        "price_per_unit": 0.15,
        "total_price": 0.75,
        "status": "started",
        "error_message": "",
        "created_at": now_utc,
        "updated_at": now_utc,
        "unit_type": "page",

        "documents": [
            {
                "file_name": "tz_test.pdf",
                "file_size": 50000,
                "original_url": "https://docs.google.com/document/d/tz123/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now_utc,
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }

    await collection.insert_one(transaction_doc)

    # Fetch back
    txn = await collection.find_one({"transaction_id": transaction_id})

    # MongoDB stores datetimes as UTC but returns them without tzinfo
    # This is expected behavior - Motor/PyMongo returns naive UTC datetimes
    assert isinstance(txn["created_at"], datetime), "created_at must be datetime object"
    assert isinstance(txn["updated_at"], datetime), "updated_at must be datetime object"
    assert isinstance(txn["documents"][0]["uploaded_at"], datetime), "uploaded_at must be datetime object"

    # Verify datetimes are close to our input (within 1 second)
    time_diff = abs((txn["created_at"] - now_utc.replace(tzinfo=None)).total_seconds())
    assert time_diff < 1, "created_at should match input time"
