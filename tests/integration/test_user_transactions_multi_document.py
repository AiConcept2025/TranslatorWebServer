"""
Integration tests for multi-document user transactions functionality.

This test module validates:
1. Pydantic model validation for DocumentSchema and UserTransactionCreate
2. CRUD helper functions for creating/retrieving transactions with multiple documents
3. API endpoints for processing transactions with documents array
4. Database serialization/deserialization of documents array

Tests use real MongoDB connection and test data created by setup_test_user_transactions.py
"""

import pytest
from datetime import datetime, timezone
from typing import List, Dict, Any
import uuid

from httpx import AsyncClient
from pydantic import ValidationError

from app.models.payment import (
    DocumentSchema,
    UserTransactionCreate,
    UserTransactionResponse,
)
from app.utils.user_transaction_helper import (
    create_user_transaction,
    get_user_transaction,
    get_user_transactions_by_email,
)
from app.database.mongodb import database


# ============================================================================
# Test Fixtures
# ============================================================================

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
        "square_transaction_id": f"TEST-{uuid.uuid4().hex[:16].upper()}",
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
        "square_transaction_id": f"TEST-{uuid.uuid4().hex[:16].upper()}",
        "square_payment_id": f"TESTPAY-{uuid.uuid4().hex[:16].upper()}",
        "amount_cents": 450,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "status": "processing",
    }


# ============================================================================
# 1. Model Validation Tests (Pydantic)
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
        # Note: uploaded_at and translated_at are ISO strings in fixture, datetime in model
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
        assert "at least 1" in error_msg or "min_length" in error_msg

    def test_user_transaction_create_no_documents_field(self, valid_transaction_data_single_document):
        """Missing documents field should fail."""
        data = valid_transaction_data_single_document.copy()
        del data["documents"]

        with pytest.raises(ValidationError) as exc_info:
            UserTransactionCreate(**data)

        assert "documents" in str(exc_info.value).lower()


# ============================================================================
# 2. CRUD Helper Function Tests
# ============================================================================

class TestCRUDHelperFunctions:
    """Test CRUD helper functions with multiple documents support."""

    @pytest.mark.asyncio
    async def test_create_user_transaction_with_multiple_documents(
        self, valid_transaction_data_multiple_documents
    ):
        """Create transaction with 2 documents and verify in DB."""
        # Connect to database
        await database.connect()

        # Prepare data (use only 2 documents)
        data = valid_transaction_data_multiple_documents.copy()
        data["documents"] = data["documents"][:2]
        transaction_id = data["square_transaction_id"]

        # Create transaction
        result = await create_user_transaction(
            user_name=data["user_name"],
            user_email=data["user_email"],
            documents=data["documents"],
            number_of_units=data["number_of_units"],
            unit_type=data["unit_type"],
            cost_per_unit=data["cost_per_unit"],
            source_language=data["source_language"],
            target_language=data["target_language"],
            square_transaction_id=transaction_id,
            date=datetime.now(timezone.utc),
            status=data["status"],
            square_payment_id=data["square_payment_id"],
            amount_cents=data["amount_cents"],
            currency=data["currency"],
            payment_status=data["payment_status"],
        )

        assert result == transaction_id

        # Verify in database
        collection = database.user_transactions
        db_transaction = await collection.find_one({"square_transaction_id": transaction_id})

        assert db_transaction is not None
        assert db_transaction["user_email"] == data["user_email"]
        assert len(db_transaction["documents"]) == 2
        assert db_transaction["documents"][0]["document_name"] == "contract.pdf"
        assert db_transaction["documents"][1]["document_name"] == "invoice.docx"

        # Cleanup
        await collection.delete_one({"square_transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_create_user_transaction_documents_array_validation(self):
        """Empty documents array should return None."""
        await database.connect()

        transaction_id = f"TEST-INVALID-{uuid.uuid4().hex[:8].upper()}"

        result = await create_user_transaction(
            user_name="Invalid User",
            user_email="invalid@example.com",
            documents=[],  # Empty array
            number_of_units=10,
            unit_type="page",
            cost_per_unit=0.15,
            source_language="en",
            target_language="es",
            square_transaction_id=transaction_id,
            date=datetime.now(timezone.utc),
            status="processing",
            square_payment_id="INVALID-PAY",
            amount_cents=150,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_transaction_returns_documents_array(
        self, valid_transaction_data_single_document
    ):
        """Retrieved transaction has documents field."""
        await database.connect()

        data = valid_transaction_data_single_document
        transaction_id = data["square_transaction_id"]

        # Create transaction
        await create_user_transaction(
            user_name=data["user_name"],
            user_email=data["user_email"],
            documents=data["documents"],
            number_of_units=data["number_of_units"],
            unit_type=data["unit_type"],
            cost_per_unit=data["cost_per_unit"],
            source_language=data["source_language"],
            target_language=data["target_language"],
            square_transaction_id=transaction_id,
            date=datetime.now(timezone.utc),
            status=data["status"],
            square_payment_id=data["square_payment_id"],
            amount_cents=data["amount_cents"],
        )

        # Retrieve transaction
        transaction = await get_user_transaction(transaction_id)

        assert transaction is not None
        assert "documents" in transaction
        assert isinstance(transaction["documents"], list)
        assert len(transaction["documents"]) == 1
        assert transaction["documents"][0]["document_name"] == "test_contract.pdf"

        # Cleanup
        await database.user_transactions.delete_one({"square_transaction_id": transaction_id})


# ============================================================================
# 3. API Endpoint Tests (Most Critical)
# ============================================================================

class TestAPIEndpoints:
    """Test API endpoints for multi-document transactions."""

    @pytest.mark.asyncio
    async def test_post_process_transaction_single_document(
        self, valid_transaction_data_single_document
    ):
        """POST with 1 document should return 201 response."""
        from app.main import app
        from fastapi.testclient import TestClient

        # Use sync TestClient for these tests (FastAPI best practice)
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/user-transactions/process",
                json=valid_transaction_data_single_document,
            )

        assert response.status_code == 201
        data = response.json()

        assert data["user_email"] == valid_transaction_data_single_document["user_email"]
        assert len(data["documents"]) == 1
        assert data["documents"][0]["document_name"] == "test_contract.pdf"

        # Cleanup
        await database.user_transactions.delete_one(
            {"square_transaction_id": valid_transaction_data_single_document["square_transaction_id"]}
        )

    @pytest.mark.asyncio
    async def test_post_process_transaction_multiple_documents(
        self, valid_transaction_data_multiple_documents
    ):
        """POST with 3 documents should verify response structure."""
        from app.main import app
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/user-transactions/process",
                json=valid_transaction_data_multiple_documents,
            )

        assert response.status_code == 201
        data = response.json()

        assert len(data["documents"]) == 3
        assert data["documents"][0]["document_name"] == "contract.pdf"
        assert data["documents"][1]["document_name"] == "invoice.docx"
        assert data["documents"][2]["document_name"] == "terms.txt"
        assert data["total_cost"] == 4.5

        # Cleanup
        await database.user_transactions.delete_one(
            {"square_transaction_id": valid_transaction_data_multiple_documents["square_transaction_id"]}
        )

    @pytest.mark.asyncio
    async def test_post_process_transaction_empty_documents_fails(
        self, valid_transaction_data_single_document
    ):
        """POST with empty documents array should fail (422)."""
        from app.main import app
        from fastapi.testclient import TestClient

        data = valid_transaction_data_single_document.copy()
        data["documents"] = []

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/user-transactions/process",
                json=data,
            )

        # Should fail validation (422 Unprocessable Entity)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_post_process_transaction_response_contains_documents(
        self, valid_transaction_data_single_document
    ):
        """Response has documents array with correct structure."""
        from app.main import app
        from fastapi.testclient import TestClient

        with TestClient(app) as client:
            response = client.post(
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
        assert "translated_url" in doc
        assert "status" in doc
        assert "uploaded_at" in doc

        # Cleanup
        await database.user_transactions.delete_one(
            {"square_transaction_id": valid_transaction_data_single_document["square_transaction_id"]}
        )

    @pytest.mark.asyncio
    async def test_get_transaction_by_id_returns_documents(
        self, valid_transaction_data_single_document
    ):
        """GET by square_transaction_id returns documents array."""
        from app.main import app
        from fastapi.testclient import TestClient

        # First create a transaction
        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/user-transactions/process",
                json=valid_transaction_data_single_document,
            )
            assert create_response.status_code == 201

            # Then retrieve it by ID
            transaction_id = valid_transaction_data_single_document["square_transaction_id"]
            get_response = client.get(
                f"/api/v1/user-transactions/{transaction_id}"
            )

        assert get_response.status_code == 200
        response_data = get_response.json()

        assert response_data["success"] is True
        assert "data" in response_data

        transaction = response_data["data"]
        assert "documents" in transaction
        assert isinstance(transaction["documents"], list)
        assert len(transaction["documents"]) == 1

        # Cleanup
        await database.user_transactions.delete_one(
            {"square_transaction_id": transaction_id}
        )

    @pytest.mark.asyncio
    async def test_get_all_transactions_returns_documents(
        self, valid_transaction_data_single_document
    ):
        """GET /user-transactions returns documents for all transactions."""
        from app.main import app
        from fastapi.testclient import TestClient

        # Create a test transaction
        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/user-transactions/process",
                json=valid_transaction_data_single_document,
            )
            assert create_response.status_code == 201

            # Get all transactions
            list_response = client.get("/api/v1/user-transactions")

        assert list_response.status_code == 200
        response_data = list_response.json()

        assert response_data["success"] is True
        assert "data" in response_data
        assert "transactions" in response_data["data"]

        transactions = response_data["data"]["transactions"]

        # Find our test transaction
        test_txn = next(
            (t for t in transactions if t["square_transaction_id"] ==
             valid_transaction_data_single_document["square_transaction_id"]),
            None
        )

        assert test_txn is not None
        assert "documents" in test_txn
        assert isinstance(test_txn["documents"], list)

        # Cleanup
        await database.user_transactions.delete_one(
            {"square_transaction_id": valid_transaction_data_single_document["square_transaction_id"]}
        )


# ============================================================================
# 4. Database Serialization Tests
# ============================================================================

class TestDatabaseSerialization:
    """Test documents array serialization to/from MongoDB."""

    @pytest.mark.asyncio
    async def test_documents_serialized_correctly_to_mongodb(
        self, valid_transaction_data_multiple_documents
    ):
        """Documents array properly stored in MongoDB."""
        await database.connect()

        data = valid_transaction_data_multiple_documents
        transaction_id = data["square_transaction_id"]

        # Create transaction
        await create_user_transaction(
            user_name=data["user_name"],
            user_email=data["user_email"],
            documents=data["documents"],
            number_of_units=data["number_of_units"],
            unit_type=data["unit_type"],
            cost_per_unit=data["cost_per_unit"],
            source_language=data["source_language"],
            target_language=data["target_language"],
            square_transaction_id=transaction_id,
            date=datetime.now(timezone.utc),
            status=data["status"],
            square_payment_id=data["square_payment_id"],
            amount_cents=data["amount_cents"],
        )

        # Retrieve directly from MongoDB
        collection = database.user_transactions
        db_doc = await collection.find_one({"square_transaction_id": transaction_id})

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
            # translated_url and translated_at can be None

        # Cleanup
        await collection.delete_one({"square_transaction_id": transaction_id})

    @pytest.mark.asyncio
    async def test_documents_deserialized_correctly_from_mongodb(
        self, valid_transaction_data_multiple_documents
    ):
        """Documents array properly retrieved with all fields."""
        await database.connect()

        data = valid_transaction_data_multiple_documents
        transaction_id = data["square_transaction_id"]

        # Create transaction
        await create_user_transaction(
            user_name=data["user_name"],
            user_email=data["user_email"],
            documents=data["documents"],
            number_of_units=data["number_of_units"],
            unit_type=data["unit_type"],
            cost_per_unit=data["cost_per_unit"],
            source_language=data["source_language"],
            target_language=data["target_language"],
            square_transaction_id=transaction_id,
            date=datetime.now(timezone.utc),
            status=data["status"],
            square_payment_id=data["square_payment_id"],
            amount_cents=data["amount_cents"],
        )

        # Retrieve using helper function
        transaction = await get_user_transaction(transaction_id)

        assert transaction is not None
        assert "documents" in transaction

        documents = transaction["documents"]
        assert len(documents) == 3

        # Verify first document (completed)
        doc1 = documents[0]
        assert doc1["document_name"] == "contract.pdf"
        assert doc1["document_url"] == "https://drive.google.com/file/d/1TEST_001/view"
        assert doc1["translated_url"] == "https://drive.google.com/file/d/1TEST_001_es/view"
        assert doc1["status"] == "completed"
        assert doc1["uploaded_at"] is not None
        assert doc1["translated_at"] is not None

        # Verify third document (in progress, no translation yet)
        doc3 = documents[2]
        assert doc3["document_name"] == "terms.txt"
        assert doc3["status"] == "translating"
        assert doc3["translated_url"] is None
        assert doc3["translated_at"] is None

        # Cleanup
        await database.user_transactions.delete_one({"square_transaction_id": transaction_id})


# ============================================================================
# Test Summary
# ============================================================================

"""
Test Coverage Summary:

1. Model Validation (4 tests)
   - DocumentSchema valid creation
   - DocumentSchema missing required fields
   - UserTransactionCreate with single document
   - UserTransactionCreate with multiple documents
   - Empty documents array validation
   - Missing documents field validation

2. CRUD Helper Functions (3 tests)
   - Create with multiple documents
   - Empty documents array returns None
   - Get transaction returns documents array

3. API Endpoints (6 tests)
   - POST with single document (201)
   - POST with multiple documents (201)
   - POST with empty array (422)
   - Response contains documents array
   - GET by ID returns documents
   - GET all returns documents

4. Database Serialization (2 tests)
   - Documents serialized to MongoDB
   - Documents deserialized from MongoDB

Total: 15 comprehensive integration tests
All tests use real MongoDB and test data cleanup
"""
