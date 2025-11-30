"""
Integration tests for multi-document user transactions functionality.

This test module validates:
1. Pydantic model validation for DocumentSchema and UserTransactionCreate
2. CRUD helper functions for creating/retrieving transactions with multiple documents
3. API endpoints for processing transactions with documents array
4. Database serialization/deserialization of documents array

Tests use real MongoDB test database via test_db fixture from conftest.py.
"""

import pytest
import httpx
from datetime import datetime, timezone
from typing import Dict, Any
import uuid

from pydantic import ValidationError

from app.models.payment import (
    DocumentSchema,
    UserTransactionCreate,
)

# Base URL for the running server
BASE_URL = "http://localhost:8000"


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def db(test_db):
    """Get test database via conftest fixture."""
    yield test_db


@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls."""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
def valid_document_data() -> Dict[str, Any]:
    """Valid document data for testing."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "document_name": "test_contract.pdf",
        "document_url": "https://drive.google.com/file/d/1TEST_ABC/view",
        "translated_url": "https://drive.google.com/file/d/1TEST_ABC_es/view",
        "status": "completed",
        "uploaded_at": now_iso,
        "translated_at": now_iso,
    }


@pytest.fixture
def valid_transaction_data_single_document(valid_document_data) -> Dict[str, Any]:
    """Valid transaction data with single document."""
    return {
        "user_name": "Test User Single",
        "user_email": "test.single@example.com",
        "documents": [valid_document_data],
        "number_of_units": 10,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "en",
        "target_language": "es",
        "square_transaction_id": f"TEST-MULTI-{uuid.uuid4().hex[:16].upper()}",
        "square_payment_id": f"TESTPAY-{uuid.uuid4().hex[:16].upper()}",
        "amount_cents": 150,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "status": "processing",
    }


@pytest.fixture
def valid_transaction_data_multiple_documents() -> Dict[str, Any]:
    """Valid transaction data with multiple documents."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "user_name": "Test User Multiple",
        "user_email": "test.multiple@example.com",
        "documents": [
            {
                "document_name": "contract.pdf",
                "document_url": "https://drive.google.com/file/d/1TEST_001/view",
                "translated_url": "https://drive.google.com/file/d/1TEST_001_es/view",
                "status": "completed",
                "uploaded_at": now_iso,
                "translated_at": now_iso,
            },
            {
                "document_name": "invoice.docx",
                "document_url": "https://drive.google.com/file/d/1TEST_002/view",
                "translated_url": "https://drive.google.com/file/d/1TEST_002_es/view",
                "status": "completed",
                "uploaded_at": now_iso,
                "translated_at": now_iso,
            },
            {
                "document_name": "terms.txt",
                "document_url": "https://drive.google.com/file/d/1TEST_003/view",
                "translated_url": None,
                "status": "translating",
                "uploaded_at": now_iso,
                "translated_at": None,
            },
        ],
        "number_of_units": 30,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "en",
        "target_language": "es",
        "square_transaction_id": f"TEST-MULTI-{uuid.uuid4().hex[:16].upper()}",
        "square_payment_id": f"TESTPAY-{uuid.uuid4().hex[:16].upper()}",
        "amount_cents": 450,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "status": "processing",
    }


@pytest.fixture(scope="function")
async def cleanup_multi_doc_test_data(db):
    """Cleanup test data after each test."""
    yield
    # Clean up test transactions (only those with TEST-MULTI- prefix)
    try:
        await db.user_transactions.delete_many({
            "square_transaction_id": {"$regex": "^TEST-MULTI-"}
        })
    except Exception as e:
        print(f"Cleanup warning: {e}")


# ============================================================================
# 1. Model Validation Tests (Pydantic) - No DB required
# ============================================================================

class TestDocumentSchemaValidation:
    """Test DocumentSchema Pydantic validation."""

    def test_document_schema_valid(self, valid_document_data):
        """Valid DocumentSchema creation should succeed."""
        document = DocumentSchema(**valid_document_data)

        assert document.document_name == valid_document_data["document_name"]
        assert document.document_url == valid_document_data["document_url"]
        assert document.translated_url == valid_document_data["translated_url"]
        assert document.status == valid_document_data["status"]
        assert document.uploaded_at is not None
        assert document.translated_at is not None

    def test_document_schema_missing_required_fields(self):
        """Missing document_name or document_url should fail."""
        # Missing document_name
        with pytest.raises(ValidationError) as exc_info:
            DocumentSchema(
                document_url="https://drive.google.com/file/d/1ABC/view",
                status="uploaded",
            )
        assert "document_name" in str(exc_info.value)

        # Missing document_url
        with pytest.raises(ValidationError) as exc_info:
            DocumentSchema(
                document_name="test.pdf",
                status="uploaded",
            )
        assert "document_url" in str(exc_info.value)

    def test_document_schema_defaults(self):
        """DocumentSchema should have correct default values."""
        document = DocumentSchema(
            document_name="test.pdf",
            document_url="https://drive.google.com/file/d/1ABC/view",
        )

        assert document.status == "uploaded"
        assert document.translated_url is None
        assert document.translated_at is None
        assert document.uploaded_at is not None


class TestUserTransactionCreateValidation:
    """Test UserTransactionCreate Pydantic validation."""

    def test_user_transaction_create_valid_single_document(self, valid_transaction_data_single_document):
        """Single document in array should be valid."""
        transaction = UserTransactionCreate(**valid_transaction_data_single_document)

        assert len(transaction.documents) == 1
        assert transaction.documents[0].document_name == "test_contract.pdf"
        assert transaction.user_name == "Test User Single"
        assert transaction.user_email == "test.single@example.com"

    def test_user_transaction_create_valid_multiple_documents(self, valid_transaction_data_multiple_documents):
        """Multiple documents (2-3) should be valid."""
        transaction = UserTransactionCreate(**valid_transaction_data_multiple_documents)

        assert len(transaction.documents) == 3
        assert transaction.documents[0].document_name == "contract.pdf"
        assert transaction.documents[1].document_name == "invoice.docx"
        assert transaction.documents[2].document_name == "terms.txt"

    def test_user_transaction_create_empty_documents_array(self, valid_transaction_data_single_document):
        """Empty documents array should fail (min_length=1)."""
        data = valid_transaction_data_single_document.copy()
        data["documents"] = []

        with pytest.raises(ValidationError) as exc_info:
            UserTransactionCreate(**data)

        error_msg = str(exc_info.value).lower()
        assert "documents" in error_msg

    def test_user_transaction_create_no_documents_field(self, valid_transaction_data_single_document):
        """Missing documents field should fail."""
        data = valid_transaction_data_single_document.copy()
        del data["documents"]

        with pytest.raises(ValidationError) as exc_info:
            UserTransactionCreate(**data)

        assert "documents" in str(exc_info.value).lower()


# ============================================================================
# 2. API Endpoint Tests (Primary Integration Tests)
# ============================================================================

class TestAPIEndpoints:
    """Test API endpoints for multi-document transactions."""

    @pytest.mark.asyncio
    async def test_post_process_transaction_single_document(
        self, http_client, db, valid_transaction_data_single_document, cleanup_multi_doc_test_data
    ):
        """POST with 1 document should return 201 response."""
        response = await http_client.post(
            "/api/v1/user-transactions/process",
            json=valid_transaction_data_single_document,
        )

        assert response.status_code == 201
        data = response.json()

        assert data["user_email"] == valid_transaction_data_single_document["user_email"]
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "test_contract.pdf"

    @pytest.mark.asyncio
    async def test_post_process_transaction_multiple_documents(
        self, http_client, db, valid_transaction_data_multiple_documents, cleanup_multi_doc_test_data
    ):
        """POST with 3 documents should verify response structure."""
        response = await http_client.post(
            "/api/v1/user-transactions/process",
            json=valid_transaction_data_multiple_documents,
        )

        assert response.status_code == 201
        data = response.json()

        assert len(data["documents"]) == 3
        assert data["documents"][0]["document_name"] == "contract.pdf"
        assert data["documents"][1]["document_name"] == "invoice.docx"
        assert data["documents"][2]["document_name"] == "terms.txt"

    @pytest.mark.asyncio
    async def test_post_process_transaction_empty_documents_fails(
        self, http_client, valid_transaction_data_single_document
    ):
        """POST with empty documents array should fail (422)."""
        data = valid_transaction_data_single_document.copy()
        data["documents"] = []

        response = await http_client.post(
            "/api/v1/user-transactions/process",
            json=data,
        )

        # Should fail validation (422 Unprocessable Entity)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_post_process_transaction_response_contains_documents(
        self, http_client, db, valid_transaction_data_single_document, cleanup_multi_doc_test_data
    ):
        """Response has documents array with correct structure."""
        response = await http_client.post(
            "/api/v1/user-transactions/process",
            json=valid_transaction_data_single_document,
        )

        assert response.status_code == 201
        data = response.json()

        # Verify documents array structure
        assert "documents" in data
        assert isinstance(data["documents"], list)
        assert len(data["documents"]) > 0

        # Verify document structure
        doc = data["documents"][0]
        assert "document_name" in doc
        assert "document_url" in doc
        assert "status" in doc
        assert "uploaded_at" in doc

    @pytest.mark.asyncio
    async def test_get_transaction_by_id_returns_documents(
        self, http_client, db, valid_transaction_data_single_document, cleanup_multi_doc_test_data
    ):
        """GET by square_transaction_id returns documents array."""
        # First create a transaction
        create_response = await http_client.post(
            "/api/v1/user-transactions/process",
            json=valid_transaction_data_single_document,
        )
        assert create_response.status_code == 201

        # Use square_transaction_id (the endpoint path param is named square_transaction_id)
        square_transaction_id = valid_transaction_data_single_document["square_transaction_id"]

        # Then retrieve it by square_transaction_id
        get_response = await http_client.get(
            f"/api/v1/user-transactions/{square_transaction_id}"
        )

        assert get_response.status_code == 200
        response_data = get_response.json()

        assert response_data["success"] is True
        assert "data" in response_data

        transaction = response_data["data"]
        assert "documents" in transaction
        assert isinstance(transaction["documents"], list)
        assert len(transaction["documents"]) == 1

    @pytest.mark.asyncio
    async def test_get_all_transactions_returns_documents(
        self, http_client, db, valid_transaction_data_single_document, cleanup_multi_doc_test_data
    ):
        """GET /user-transactions returns documents for all transactions."""
        # Create a test transaction
        create_response = await http_client.post(
            "/api/v1/user-transactions/process",
            json=valid_transaction_data_single_document,
        )
        assert create_response.status_code == 201

        # Get all transactions
        list_response = await http_client.get("/api/v1/user-transactions")

        assert list_response.status_code == 200
        response_data = list_response.json()

        assert response_data["success"] is True
        assert "data" in response_data
        assert "transactions" in response_data["data"]

        transactions = response_data["data"]["transactions"]

        # Find our test transaction
        test_txn = next(
            (t for t in transactions if t.get("square_transaction_id") ==
             valid_transaction_data_single_document["square_transaction_id"]),
            None
        )

        assert test_txn is not None
        assert "documents" in test_txn
        assert isinstance(test_txn["documents"], list)


# ============================================================================
# 3. Database Verification Tests (via API)
# ============================================================================

class TestDatabaseVerificationViaAPI:
    """Test documents array is stored correctly via API."""

    @pytest.mark.asyncio
    async def test_documents_stored_and_retrieved_via_api(
        self, http_client, db, valid_transaction_data_multiple_documents, cleanup_multi_doc_test_data
    ):
        """Documents array properly stored and retrieved via API."""
        data = valid_transaction_data_multiple_documents
        square_txn_id = data["square_transaction_id"]

        # Create transaction via API
        response = await http_client.post(
            "/api/v1/user-transactions/process",
            json=data,
        )

        assert response.status_code == 201
        response_data = response.json()

        # Verify response has documents
        assert "documents" in response_data
        assert len(response_data["documents"]) == 3

        # Verify in database using test_db
        db_doc = await db.user_transactions.find_one({"square_transaction_id": square_txn_id})

        assert db_doc is not None
        assert "documents" in db_doc
        assert isinstance(db_doc["documents"], list)
        assert len(db_doc["documents"]) == 3

        # Verify all document fields are present
        for doc in db_doc["documents"]:
            assert "document_name" in doc
            assert "document_url" in doc
            assert "status" in doc
            assert "uploaded_at" in doc
