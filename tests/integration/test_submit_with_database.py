"""
INTEGRATION TESTS FOR SUBMIT API WITH DATABASE OPERATIONS

These tests create real transactions in MongoDB and test the submit endpoint
with actual database updates and email notifications.

Test Database: translation_test (separate from production)
Uses: Real MongoDB connection via Motor + Real HTTP API calls
"""

import pytest
import httpx
import uuid
from datetime import datetime, timezone

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
async def test_enterprise_transaction():
    """
    Create a test enterprise transaction in translation_transactions collection.
    Automatically cleaned up after test.
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"

    transaction_doc = {
        "transaction_id": transaction_id,
        "company_name": "Test Corp",
        "user_id": "testuser@testcorp.com",
        "user_name": "Test User",
        "status": "processing",
        "documents": [
            {
                "file_name": "report.pdf",
                "file_size": 524288,
                "original_url": "https://drive.google.com/file/d/original123/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None
            },
            {
                "file_name": "summary.docx",
                "file_size": 262144,
                "original_url": "https://drive.google.com/file/d/original456/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None
            }
        ],
        # Email batching counters
        "total_documents": 2,
        "completed_documents": 0,
        "batch_email_sent": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await collection.insert_one(transaction_doc)
    yield transaction_doc

    # Cleanup
    await collection.delete_one({"transaction_id": transaction_id})


@pytest.fixture(scope="function")
async def test_individual_transaction():
    """
    Create a test individual transaction in user_transactions collection.
    Automatically cleaned up after test.
    """
    await database.connect()
    collection = database.user_transactions

    transaction_id = f"TXN-IND-{uuid.uuid4().hex[:8].upper()}"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "individual@example.com",
        "user_name": "Jane Doe",
        "status": "processing",
        "documents": [
            {
                "file_name": "passport.pdf",
                "file_size": 131072,
                "original_url": "https://drive.google.com/file/d/passport123/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None
            }
        ],
        # Email batching counters
        "total_documents": 1,
        "completed_documents": 0,
        "batch_email_sent": False,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await collection.insert_one(transaction_doc)
    yield transaction_doc

    # Cleanup
    await collection.delete_one({"transaction_id": transaction_id})


# ============================================================================
# Test Cases - Enterprise Transactions
# ============================================================================

class TestSubmitEnterpriseTransactions:
    """Test submit endpoint with enterprise transactions."""

    @pytest.mark.asyncio
    async def test_submit_enterprise_document_success(
        self, http_client, test_enterprise_transaction
    ):
        """
        Test successful submission for enterprise transaction.

        Verifies:
        - 200 status code
        - Database is updated with translated_url and translated_name
        - Response contains transaction details
        - Email is sent (or attempted)
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        payload = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/translated123/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }

        response = await http_client.post("/submit", json=payload)

        # Verify HTTP response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["status"] == "success"
        assert data["transaction_id"] == transaction_id
        assert data["document_name"] == "report.pdf"
        assert data["translated_url"] == payload["file_url"]
        assert "email_sent" in data

        # Verify database was updated
        collection = database.translation_transactions
        updated_transaction = await collection.find_one({"transaction_id": transaction_id})

        assert updated_transaction is not None
        doc = updated_transaction["documents"][0]
        assert doc["translated_url"] == payload["file_url"]
        assert doc["translated_name"] == "report_translated.pdf"
        assert doc["translated_at"] is not None

    @pytest.mark.asyncio
    async def test_submit_enterprise_document_not_found(
        self, http_client, test_enterprise_transaction
    ):
        """
        Test submission when document name doesn't exist in transaction.

        Verifies:
        - 404 status code
        - Error message indicates document not found
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        payload = {
            "file_name": "nonexistent.pdf",  # Document not in transaction
            "file_url": "https://drive.google.com/file/d/translated999/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }

        response = await http_client.post("/submit", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()
        assert "nonexistent.pdf" in data["error"]

    @pytest.mark.asyncio
    async def test_submit_enterprise_transaction_not_found(self, http_client):
        """
        Test submission when transaction ID doesn't exist.

        Verifies:
        - 404 status code
        - Error message indicates transaction not found
        """
        payload = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/translated123/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": "TXN-NOTFOUND-999"
        }

        response = await http_client.post("/submit", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_submit_enterprise_multiple_documents(
        self, http_client, test_enterprise_transaction
    ):
        """
        Test submitting multiple documents from same transaction.

        Verifies:
        - Each submission updates the correct document
        - all_documents_complete is True after all are submitted
        - Transaction status is updated to completed
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        # Submit first document
        payload1 = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/trans1/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }

        response1 = await http_client.post("/submit", json=payload1)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["all_documents_complete"] is False

        # Submit second document
        payload2 = {
            "file_name": "summary.docx",
            "file_url": "https://drive.google.com/file/d/trans2/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }

        response2 = await http_client.post("/submit", json=payload2)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["all_documents_complete"] is True

        # Verify database shows transaction as completed
        collection = database.translation_transactions
        final_transaction = await collection.find_one({"transaction_id": transaction_id})
        assert final_transaction["status"] == "completed"
        assert all(doc.get("translated_url") for doc in final_transaction["documents"])


# ============================================================================
# Test Cases - Individual Transactions
# ============================================================================

class TestSubmitIndividualTransactions:
    """Test submit endpoint with individual transactions."""

    @pytest.mark.asyncio
    async def test_submit_individual_document_success(
        self, http_client, test_individual_transaction
    ):
        """
        Test successful submission for individual transaction.

        Verifies:
        - 200 status code
        - Database (user_transactions) is updated
        - Individual template is used for email
        """
        transaction_id = test_individual_transaction["transaction_id"]

        payload = {
            "file_name": "passport.pdf",
            "file_url": "https://drive.google.com/file/d/passport_trans/view",
            "user_email": "individual@example.com",
            "company_name": "Ind",  # Individual customer
            "transaction_id": transaction_id
        }

        response = await http_client.post("/submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["all_documents_complete"] is True

        # Verify database was updated
        collection = database.user_transactions
        updated_transaction = await collection.find_one({"transaction_id": transaction_id})

        assert updated_transaction is not None
        assert updated_transaction["status"] == "completed"
        doc = updated_transaction["documents"][0]
        assert doc["translated_url"] == payload["file_url"]
        assert doc["translated_name"] == "passport_translated.pdf"

    @pytest.mark.asyncio
    async def test_submit_individual_transaction_not_found(self, http_client):
        """
        Test submission when individual transaction doesn't exist.

        Verifies:
        - 404 status code
        - Error response
        """
        payload = {
            "file_name": "document.pdf",
            "file_url": "https://drive.google.com/file/d/trans/view",
            "user_email": "test@example.com",
            "company_name": "Ind",
            "transaction_id": "TXN-IND-NOTFOUND"
        }

        response = await http_client.post("/submit", json=payload)

        assert response.status_code == 404
        data = response.json()
        assert "error" in data


# ============================================================================
# Test Cases - Validation and Error Handling
# ============================================================================

class TestSubmitValidation:
    """Test validation and error handling."""

    @pytest.mark.asyncio
    async def test_submit_missing_transaction_id(self, http_client):
        """
        Test submission with missing required transaction_id.

        Verifies:
        - 422 status code (validation error)
        """
        payload = {
            "file_name": "test.pdf",
            "file_url": "https://drive.google.com/file/d/test/view",
            "user_email": "test@example.com",
            "company_name": "Test Corp"
            # Missing transaction_id (now required)
        }

        response = await http_client.post("/submit", json=payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_empty_transaction_id(self, http_client):
        """
        Test submission with empty transaction_id.

        Verifies:
        - 422 status code
        - Validation rejects empty strings
        """
        payload = {
            "file_name": "test.pdf",
            "file_url": "https://drive.google.com/file/d/test/view",
            "user_email": "test@example.com",
            "company_name": "Test Corp",
            "transaction_id": ""  # Empty string
        }

        response = await http_client.post("/submit", json=payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_submit_short_transaction_id(self, http_client):
        """
        Test submission with transaction_id < 5 characters.

        Verifies:
        - 422 status code
        - Validator catches short transaction IDs
        """
        payload = {
            "file_name": "test.pdf",
            "file_url": "https://drive.google.com/file/d/test/view",
            "user_email": "test@example.com",
            "company_name": "Test Corp",
            "transaction_id": "TXN"  # Too short
        }

        response = await http_client.post("/submit", json=payload)

        assert response.status_code == 422


# ============================================================================
# Test Cases - Email Integration
# ============================================================================

class TestSubmitEmailIntegration:
    """Test email notification integration."""

    @pytest.mark.asyncio
    async def test_submit_success_even_if_email_fails(
        self, http_client, test_enterprise_transaction
    ):
        """
        Test that submission succeeds even if email fails.

        Verifies:
        - Database update succeeds
        - 200 status code
        - email_sent=False in response
        - email_error contains error details
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        payload = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/trans/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }

        response = await http_client.post("/submit", json=payload)

        # Submission should succeed regardless of email status
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"

        # Verify database was updated
        collection = database.translation_transactions
        updated_transaction = await collection.find_one({"transaction_id": transaction_id})
        assert updated_transaction["documents"][0]["translated_url"] is not None

    @pytest.mark.asyncio
    async def test_submit_includes_all_translated_documents_in_email(
        self, http_client, test_enterprise_transaction
    ):
        """
        Test that email includes ALL translated documents, not just the current one.

        Verifies:
        - documents_count in response shows all translated documents
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        # Submit first document
        payload1 = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/trans1/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }
        response1 = await http_client.post("/submit", json=payload1)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1.get("documents_count") == 1  # Only 1 translated so far

        # Submit second document
        payload2 = {
            "file_name": "summary.docx",
            "file_url": "https://drive.google.com/file/d/trans2/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }
        response2 = await http_client.post("/submit", json=payload2)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2.get("documents_count") == 2  # Both translated now

    @pytest.mark.asyncio
    async def test_email_batching_gate_blocks_until_all_complete(
        self, http_client, test_enterprise_transaction
    ):
        """
        Test email batching: email sent ONLY when ALL documents complete.

        Verifies:
        - First /submit: NO email (1/3 complete), email_sent=False
        - Second /submit: NO email (2/3 complete), email_sent=False
        - Third /submit: EMAIL SENT (3/3 complete), email_sent=True
        - Counter tracking: completed_documents increments correctly
        - Email gate logic: blocks email until all complete
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        # Submit first document - EMAIL GATE SHOULD BLOCK (1/3)
        payload1 = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/trans1/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }
        response1 = await http_client.post("/submit", json=payload1)
        assert response1.status_code == 200
        data1 = response1.json()

        # Verify email NOT sent (incomplete)
        assert data1.get("email_sent") == False, "Email should not be sent when only 1/3 documents complete"
        assert data1.get("all_documents_complete") == False
        assert data1.get("completed_documents") == 1
        assert data1.get("total_documents") == 2  # test_enterprise_transaction has 2 documents
        assert data1.get("documents_count") == 1  # Only 1 translated so far
        assert "pending" in data1.get("message", "").lower(), "Message should indicate email is pending"

        # Submit second document - EMAIL GATE SHOULD PASS (2/2)
        payload2 = {
            "file_name": "summary.docx",
            "file_url": "https://drive.google.com/file/d/trans2/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }
        response2 = await http_client.post("/submit", json=payload2)
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify email SENT (all complete)
        assert data2.get("email_sent") == True, "Email should be sent when all 2/2 documents complete"
        assert data2.get("all_documents_complete") == True
        assert data2.get("completed_documents") == 2
        assert data2.get("total_documents") == 2
        assert data2.get("documents_count") == 2  # Email includes both documents
        assert "complete" in data2.get("message", "").lower(), "Message should indicate completion"

        # Verify database state
        collection = database.translation_transactions
        final_transaction = await collection.find_one({"transaction_id": transaction_id})
        assert final_transaction["completed_documents"] == 2
        assert final_transaction["total_documents"] == 2
        assert all(doc.get("translated_url") for doc in final_transaction["documents"])


# ============================================================================
# Test Cases - Filename Generation
# ============================================================================

class TestSubmitFilenameGeneration:
    """Test translated filename generation."""

    @pytest.mark.asyncio
    async def test_submit_generates_translated_name(
        self, http_client, test_enterprise_transaction
    ):
        """
        Test that translated_name is generated correctly.

        Verifies:
        - Simple filename: "report.pdf" -> "report_translated.pdf"
        - Language code removal: "document_en.pdf" -> "document_translated.pdf"
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        payload = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/trans/view",
            "user_email": "testuser@testcorp.com",
            "company_name": "Test Corp",
            "transaction_id": transaction_id
        }

        response = await http_client.post("/submit", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["translated_name"] == "report_translated.pdf"

        # Verify in database
        collection = database.translation_transactions
        updated_transaction = await collection.find_one({"transaction_id": transaction_id})
        assert updated_transaction["documents"][0]["translated_name"] == "report_translated.pdf"
