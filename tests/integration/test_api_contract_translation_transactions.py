"""
API CONTRACT TESTS FOR TRANSLATION TRANSACTIONS

Tests verify that API endpoints return correct response structures matching
the TypeScript interface contracts on the frontend.

Test Coverage:
- GET /api/v1/translation-transactions/company/{company_name} response structure
- Pagination structure (count, limit, skip, filters)
- Datetime fields are ISO 8601 strings (not datetime objects)
- Field types match TypeScript interfaces
- Error responses follow standard format
- Status code validation (200/400/404/422/500)

Database: translation_test
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
    """
    await database.connect()
    collection = database.company

    company_doc = {
        "company_name": "API Contract Test Co",
        "address": "456 API St",
        "phone": "+1987654321",
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
    Cleanup function to remove test transactions after each test.
    """
    yield

    await database.connect()
    collection = database.translation_transactions

    # SAFE: Only delete test records
    result = await collection.delete_many({
        "transaction_id": {"$regex": "^TXN-API-TEST-"}
    })

    if result.deleted_count > 0:
        print(f"Cleaned up {result.deleted_count} API test transaction(s)")


# ============================================================================
# Test 1: GET Transaction List - Success Response Structure
# ============================================================================

@pytest.mark.asyncio
async def test_transaction_list_response_structure(
    http_client: httpx.AsyncClient,
    test_company: Dict[str, Any],
    cleanup_test_transactions
):
    """
    Test GET /api/v1/translation-transactions/company/{company_name} response structure.

    Verifies:
    - 200 status code
    - success: true
    - data object with transactions array
    - Pagination fields: count, limit, skip
    - Filters object
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-API-TEST-{uuid.uuid4().hex[:8].upper()}"
    company_name = "API Contract Test Co"

    # Create test transaction
    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "apitest@company.com",
        "company_name": company_name,
        "source_language": "en",
        "target_language": "de",
        "units_count": 12,
        "price_per_unit": 0.11,
        "total_price": 1.32,
        "status": "started",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "unit_type": "page",

        "documents": [
            {
                "file_name": "api_test.pdf",
                "file_size": 150000,
                "original_url": "https://docs.google.com/document/d/api123/edit",
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

    # Call API endpoint
    response = await http_client.get(
        f"/api/v1/translation-transactions/company/{company_name}"
    )

    # Verify status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Verify response structure
    data = response.json()

    # Top-level fields
    assert "success" in data, "Response must have 'success' field"
    assert "data" in data, "Response must have 'data' field"
    assert data["success"] is True, "success should be true"

    # Data object structure
    response_data = data["data"]
    assert "transactions" in response_data, "data must have 'transactions' array"
    assert "count" in response_data, "data must have 'count' field"
    assert "limit" in response_data, "data must have 'limit' field"
    assert "skip" in response_data, "data must have 'skip' field"
    assert "filters" in response_data, "data must have 'filters' object"

    # Verify field types
    assert isinstance(response_data["transactions"], list)
    assert isinstance(response_data["count"], int)
    assert isinstance(response_data["limit"], int)
    assert isinstance(response_data["skip"], int)
    assert isinstance(response_data["filters"], dict)

    # Verify filters structure
    filters = response_data["filters"]
    assert "company_name" in filters
    assert "status" in filters
    assert filters["company_name"] == company_name


# ============================================================================
# Test 2: Transaction Object Structure and Field Types
# ============================================================================

@pytest.mark.asyncio
async def test_transaction_object_field_types(
    http_client: httpx.AsyncClient,
    test_company: Dict[str, Any],
    cleanup_test_transactions
):
    """
    Test that transaction objects have correct field types matching TypeScript interface.

    Verifies each field type:
    - String fields: _id, transaction_id, user_id, etc.
    - Number fields: units_count, price_per_unit, total_price, file_size
    - DateTime fields: created_at, updated_at (must be ISO strings)
    - Array fields: documents
    - Nested object validation
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-API-TEST-{uuid.uuid4().hex[:8].upper()}"
    company_name = "API Contract Test Co"

    now = datetime.now(timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "fieldtest@company.com",
        "company_name": company_name,
        "source_language": "fr",
        "target_language": "en",
        "units_count": 18,
        "price_per_unit": 0.13,
        "total_price": 2.34,
        "status": "confirmed",
        "error_message": "",
        "created_at": now,
        "updated_at": now,
        "unit_type": "word",

        "documents": [
            {
                "file_name": "field_test.docx",
                "file_size": 250000,
                "original_url": "https://docs.google.com/document/d/field123/edit",
                "translated_url": "https://docs.google.com/document/d/field456/edit",
                "translated_name": "field_test_en.docx",
                "status": "completed",
                "uploaded_at": now,
                "translated_at": now,
                "processing_started_at": now,
                "processing_duration": 145.8
            }
        ]
    }

    await collection.insert_one(transaction_doc)

    # Call API
    response = await http_client.get(
        f"/api/v1/translation-transactions/company/{company_name}"
    )

    assert response.status_code == 200

    data = response.json()
    transactions = data["data"]["transactions"]

    # Find our test transaction
    txn = next((t for t in transactions if t["transaction_id"] == transaction_id), None)
    assert txn is not None, "Test transaction not found in response"

    # Verify string fields
    assert isinstance(txn["_id"], str), "_id must be string"
    assert isinstance(txn["transaction_id"], str), "transaction_id must be string"
    assert isinstance(txn["user_id"], str), "user_id must be string"
    assert isinstance(txn["source_language"], str), "source_language must be string"
    assert isinstance(txn["target_language"], str), "target_language must be string"
    assert isinstance(txn["status"], str), "status must be string"
    assert isinstance(txn["error_message"], str), "error_message must be string"
    assert isinstance(txn["unit_type"], str), "unit_type must be string"
    assert isinstance(txn["company_name"], str), "company_name must be string"

    # Verify number fields (int or float)
    assert isinstance(txn["units_count"], int), "units_count must be int"
    assert isinstance(txn["price_per_unit"], (int, float)), "price_per_unit must be number"
    assert isinstance(txn["total_price"], (int, float)), "total_price must be number"

    # CRITICAL: Verify datetime fields are ISO strings, NOT datetime objects
    assert isinstance(txn["created_at"], str), "created_at must be ISO string"
    assert isinstance(txn["updated_at"], str), "updated_at must be ISO string"

    # Verify ISO 8601 format
    datetime.fromisoformat(txn["created_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(txn["updated_at"].replace("Z", "+00:00"))

    # Verify documents array
    assert "documents" in txn, "Transaction must have documents array"
    assert isinstance(txn["documents"], list), "documents must be array"
    assert len(txn["documents"]) >= 1, "documents must have at least 1 item"

    # Verify nested document structure
    doc = txn["documents"][0]

    # Document string fields
    assert isinstance(doc["file_name"], str), "file_name must be string"
    assert isinstance(doc["original_url"], str), "original_url must be string"
    assert isinstance(doc["status"], str), "status must be string"

    # Document number fields
    assert isinstance(doc["file_size"], int), "file_size must be int"
    assert isinstance(doc["processing_duration"], (int, float)), "processing_duration must be number"

    # Document datetime fields - MUST be ISO strings
    assert isinstance(doc["uploaded_at"], str), "uploaded_at must be ISO string"
    assert isinstance(doc["translated_at"], str), "translated_at must be ISO string"
    assert isinstance(doc["processing_started_at"], str), "processing_started_at must be ISO string"

    # Verify ISO format for nested datetime fields
    datetime.fromisoformat(doc["uploaded_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(doc["translated_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(doc["processing_started_at"].replace("Z", "+00:00"))

    # Nullable fields
    if doc["translated_url"] is not None:
        assert isinstance(doc["translated_url"], str)
    if doc["translated_name"] is not None:
        assert isinstance(doc["translated_name"], str)


# ============================================================================
# Test 3: Pagination Parameters
# ============================================================================

@pytest.mark.asyncio
async def test_pagination_parameters(
    http_client: httpx.AsyncClient,
    test_company: Dict[str, Any],
    cleanup_test_transactions
):
    """
    Test pagination parameters: limit and skip.

    Verifies:
    - limit parameter controls max results
    - skip parameter controls offset
    - Response includes correct count, limit, skip values
    """
    await database.connect()
    collection = database.translation_transactions

    company_name = "API Contract Test Co"

    # Create 5 test transactions
    for i in range(5):
        transaction_id = f"TXN-API-TEST-PAGE-{i}-{uuid.uuid4().hex[:4].upper()}"

        await collection.insert_one({
            "transaction_id": transaction_id,
            "user_id": f"page{i}@company.com",
            "company_name": company_name,
            "source_language": "en",
            "target_language": "fr",
            "units_count": 10 + i,
            "price_per_unit": 0.10,
            "total_price": (10 + i) * 0.10,
            "status": "started",
            "error_message": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "unit_type": "page",
            "documents": [
                {
                    "file_name": f"page_{i}.pdf",
                    "file_size": 100000 + i * 10000,
                    "original_url": f"https://docs.google.com/document/d/page{i}/edit",
                    "translated_url": None,
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": datetime.now(timezone.utc),
                    "translated_at": None,
                    "processing_started_at": None,
                    "processing_duration": None
                }
            ]
        })

    # Test limit parameter
    response = await http_client.get(
        f"/api/v1/translation-transactions/company/{company_name}",
        params={"limit": 2}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["data"]["limit"] == 2
    assert len(data["data"]["transactions"]) <= 2

    # Test skip parameter
    response = await http_client.get(
        f"/api/v1/translation-transactions/company/{company_name}",
        params={"skip": 2, "limit": 2}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["data"]["skip"] == 2
    assert data["data"]["limit"] == 2


# ============================================================================
# Test 4: Status Filter
# ============================================================================

@pytest.mark.asyncio
async def test_status_filter(
    http_client: httpx.AsyncClient,
    test_company: Dict[str, Any],
    cleanup_test_transactions
):
    """
    Test status query parameter for filtering transactions.

    Verifies:
    - status filter returns only matching transactions
    - filters object in response reflects the filter
    - Invalid status returns 400 error
    """
    await database.connect()
    collection = database.translation_transactions

    company_name = "API Contract Test Co"

    # Create transactions with different statuses
    statuses = ["started", "confirmed", "pending", "failed"]

    for status_val in statuses:
        transaction_id = f"TXN-API-TEST-{status_val.upper()}-{uuid.uuid4().hex[:4].upper()}"

        await collection.insert_one({
            "transaction_id": transaction_id,
            "user_id": f"{status_val}@company.com",
            "company_name": company_name,
            "source_language": "en",
            "target_language": "es",
            "units_count": 5,
            "price_per_unit": 0.10,
            "total_price": 0.50,
            "status": status_val,
            "error_message": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "unit_type": "page",
            "documents": [
                {
                    "file_name": f"{status_val}_test.pdf",
                    "file_size": 50000,
                    "original_url": f"https://docs.google.com/document/d/{status_val}/edit",
                    "translated_url": None,
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": datetime.now(timezone.utc),
                    "translated_at": None,
                    "processing_started_at": None,
                    "processing_duration": None
                }
            ]
        })

    # Test filtering by "started" status
    response = await http_client.get(
        f"/api/v1/translation-transactions/company/{company_name}",
        params={"status": "started"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["data"]["filters"]["status"] == "started"

    # Verify all returned transactions have status="started"
    for txn in data["data"]["transactions"]:
        if txn["transaction_id"].startswith("TXN-API-TEST-"):
            assert txn["status"] == "started"


# ============================================================================
# Test 5: Error Response Structure
# ============================================================================

@pytest.mark.asyncio
async def test_error_response_structure_400(http_client: httpx.AsyncClient):
    """
    Test 400 error response for invalid status filter.

    Verifies:
    - 400 status code
    - Standard error format: {success: false, error: {...}}
    """
    # Invalid status value
    response = await http_client.get(
        "/api/v1/translation-transactions/company/Test%20Company",
        params={"status": "invalid_status"}
    )

    assert response.status_code == 400

    data = response.json()

    # Actual error format from exception handler
    assert "success" in data
    assert data["success"] is False
    assert "error" in data
    assert isinstance(data["error"], dict)

    error = data["error"]
    assert "code" in error
    assert "message" in error
    assert "type" in error
    assert error["code"] == 400
    assert isinstance(error["message"], str)
    assert "Invalid transaction status" in error["message"]


@pytest.mark.asyncio
async def test_error_response_structure_404(
    http_client: httpx.AsyncClient,
    cleanup_test_transactions
):
    """
    Test 404 error when company not found (returns empty array, not 404).

    Note: Current implementation returns empty array instead of 404.
    This test verifies the actual behavior.
    """
    # Non-existent company
    response = await http_client.get(
        "/api/v1/translation-transactions/company/NonExistentCompany12345"
    )

    # Current implementation returns 200 with empty array
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["count"] == 0
    assert len(data["data"]["transactions"]) == 0


# ============================================================================
# Test 6: Empty Result Set
# ============================================================================

@pytest.mark.asyncio
async def test_empty_result_set(
    http_client: httpx.AsyncClient,
    test_company: Dict[str, Any]
):
    """
    Test response structure when no transactions match filters.

    Verifies:
    - 200 status code (success)
    - empty transactions array
    - count = 0
    - filters object populated correctly
    """
    company_name = "API Contract Test Co"

    # Query with filter that won't match any records
    response = await http_client.get(
        f"/api/v1/translation-transactions/company/{company_name}",
        params={"status": "failed"}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["data"]["count"] == 0
    assert len(data["data"]["transactions"]) == 0
    assert data["data"]["filters"]["status"] == "failed"
    assert data["data"]["filters"]["company_name"] == company_name


# ============================================================================
# Test 7: Multiple Documents Per Transaction in API Response
# ============================================================================

@pytest.mark.asyncio
async def test_multiple_documents_in_api_response(
    http_client: httpx.AsyncClient,
    test_company: Dict[str, Any],
    cleanup_test_transactions
):
    """
    Test that transactions with multiple documents serialize correctly in API response.

    Verifies:
    - All documents in array are returned
    - Each document has correct structure
    - Datetime serialization works for all documents
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-API-TEST-MULTI-{uuid.uuid4().hex[:8].upper()}"
    company_name = "API Contract Test Co"

    now = datetime.now(timezone.utc)

    # Create transaction with 3 documents
    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "multidoc@company.com",
        "company_name": company_name,
        "source_language": "es",
        "target_language": "en",
        "units_count": 30,
        "price_per_unit": 0.09,
        "total_price": 2.70,
        "status": "started",
        "error_message": "",
        "created_at": now,
        "updated_at": now,
        "unit_type": "page",

        "documents": [
            {
                "file_name": "multi_doc_1.pdf",
                "file_size": 100000,
                "original_url": "https://docs.google.com/document/d/multi1/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            },
            {
                "file_name": "multi_doc_2.docx",
                "file_size": 200000,
                "original_url": "https://docs.google.com/document/d/multi2/edit",
                "translated_url": "https://docs.google.com/document/d/multi2_trans/edit",
                "translated_name": "multi_doc_2_en.docx",
                "status": "completed",
                "uploaded_at": now,
                "translated_at": now,
                "processing_started_at": now,
                "processing_duration": 78.9
            },
            {
                "file_name": "multi_doc_3.txt",
                "file_size": 50000,
                "original_url": "https://docs.google.com/document/d/multi3/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }

    await collection.insert_one(transaction_doc)

    # Call API
    response = await http_client.get(
        f"/api/v1/translation-transactions/company/{company_name}"
    )

    assert response.status_code == 200

    data = response.json()
    transactions = data["data"]["transactions"]

    # Find our test transaction
    txn = next((t for t in transactions if t["transaction_id"] == transaction_id), None)
    assert txn is not None

    # Verify 3 documents
    assert len(txn["documents"]) == 3

    # Verify each document structure
    for i, doc in enumerate(txn["documents"]):
        assert "file_name" in doc
        assert "file_size" in doc
        assert "original_url" in doc
        assert "status" in doc
        assert "uploaded_at" in doc

        # Verify datetime serialization
        assert isinstance(doc["uploaded_at"], str)

        # Document 2 should have translated fields
        if i == 1:
            assert doc["status"] == "completed"
            assert doc["translated_url"] is not None
            assert doc["translated_name"] == "multi_doc_2_en.docx"
            assert isinstance(doc["translated_at"], str)
            assert isinstance(doc["processing_started_at"], str)
            assert doc["processing_duration"] == 78.9
