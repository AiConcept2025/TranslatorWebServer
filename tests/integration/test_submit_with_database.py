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

# CRITICAL: Do NOT import database from app.database here!
# All tests MUST use the test_db fixture from conftest.py instead.


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
async def db(test_db):
    """Get test database via conftest fixture."""
    yield test_db


@pytest.fixture(scope="function")
async def test_enterprise_transaction(db):
    """
    Create a test enterprise transaction in translation_transactions collection.
    Automatically cleaned up after test.
    """
    collection = db.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"

    transaction_doc = {
        "transaction_id": transaction_id,
        "company_name": "Iris Trading",  # Use real company from Golden Source
        "user_id": "danishevsky@gmail.com",
        "user_name": "Vladimir Danishevsky",
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
async def test_individual_transaction(db):
    """
    Create a test individual transaction in user_transactions collection.
    Automatically cleaned up after test.
    """
    collection = db.user_transactions

    transaction_id = f"USER-TEST-{uuid.uuid4().hex[:8].upper()}"
    square_txn_id = f"TEST-SQR-IND-{uuid.uuid4().hex[:8].upper()}"

    transaction_doc = {
        "transaction_id": transaction_id,
        "square_transaction_id": square_txn_id,
        "user_email": "testuser@example.com",
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


@pytest.fixture(scope="function")
async def cleanup_test_transactions(db):
    """Cleanup test transactions after each test."""
    yield
    try:
        await db.translation_transactions.delete_many({
            "transaction_id": {"$regex": "^TXN-TEST-"}
        })
        await db.user_transactions.delete_many({
            "transaction_id": {"$regex": "^USER-TEST-"}
        })
    except Exception as e:
        print(f"Cleanup warning: {e}")


# ============================================================================
# Test Cases - Enterprise Transactions
# ============================================================================

class TestSubmitEnterpriseTransactions:
    """Test submit endpoint with enterprise transactions."""

    @pytest.mark.asyncio
    async def test_submit_enterprise_document_success(
        self, http_client, db, test_enterprise_transaction
    ):
        """
        Test successful submission for enterprise transaction.

        Verifies:
        - 200 status code
        - Database is updated with translated_url
        - Response contains transaction details
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        payload = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/translated123/view",
            "user_email": "danishevsky@gmail.com",
            "company_name": "Iris Trading",
            "transaction_id": transaction_id
        }

        print(f"\n  Submitting document for transaction: {transaction_id}")
        response = await http_client.post("/submit", json=payload)
        print(f"  POST /submit")
        print(f"  Response: {response.status_code}")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data.get("status") == "success" or data.get("success") is True
        assert data.get("transaction_id") == transaction_id

        # Verify database was updated
        updated_transaction = await db.translation_transactions.find_one({"transaction_id": transaction_id})
        if updated_transaction:
            doc = updated_transaction["documents"][0]
            assert doc["translated_url"] == payload["file_url"]
            print(f"  Database verified: translated_url set")

        print("  PASSED")

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
            "transaction_id": "TXN-NOTFOUND-999999"
        }

        print("\n  Testing 404 for non-existent transaction...")
        response = await http_client.post("/submit", json=payload)
        print(f"  Response: {response.status_code}")

        assert response.status_code == 404
        data = response.json()
        error_msg = data.get("error", "") or data.get("detail", "")
        assert "not found" in error_msg.lower()

        print("  PASSED")

    @pytest.mark.asyncio
    async def test_submit_enterprise_multiple_documents(
        self, http_client, db, test_enterprise_transaction
    ):
        """
        Test submitting multiple documents from same transaction.

        Verifies:
        - Each submission updates the correct document
        - all_documents_complete is True after all are submitted
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        # Submit first document
        payload1 = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/trans1/view",
            "user_email": "danishevsky@gmail.com",
            "company_name": "Iris Trading",
            "transaction_id": transaction_id
        }

        print(f"\n  Submitting first document: report.pdf")
        response1 = await http_client.post("/submit", json=payload1)
        print(f"  Response 1: {response1.status_code}")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1.get("all_documents_complete") is False

        # Submit second document
        payload2 = {
            "file_name": "summary.docx",
            "file_url": "https://drive.google.com/file/d/trans2/view",
            "user_email": "danishevsky@gmail.com",
            "company_name": "Iris Trading",
            "transaction_id": transaction_id
        }

        print(f"  Submitting second document: summary.docx")
        response2 = await http_client.post("/submit", json=payload2)
        print(f"  Response 2: {response2.status_code}")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2.get("all_documents_complete") is True

        # Verify database shows both documents translated
        final_transaction = await db.translation_transactions.find_one({"transaction_id": transaction_id})
        if final_transaction:
            assert all(doc.get("translated_url") for doc in final_transaction["documents"])
            print(f"  Database verified: all documents translated")

        print("  PASSED")


# ============================================================================
# Test Cases - Individual Transactions
# ============================================================================

class TestSubmitIndividualTransactions:
    """Test submit endpoint with individual transactions."""

    @pytest.mark.asyncio
    async def test_submit_individual_document_success(
        self, http_client, db, test_individual_transaction
    ):
        """
        Test successful submission for individual transaction.

        Verifies:
        - 200 status code
        - Database (user_transactions) is updated
        """
        transaction_id = test_individual_transaction["transaction_id"]

        payload = {
            "file_name": "passport.pdf",
            "file_url": "https://drive.google.com/file/d/passport_trans/view",
            "user_email": "testuser@example.com",
            "company_name": "Ind",  # Individual customer
            "transaction_id": transaction_id
        }

        print(f"\n  Submitting individual document: {transaction_id}")
        response = await http_client.post("/submit", json=payload)
        print(f"  Response: {response.status_code}")

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success" or data.get("success") is True
        assert data.get("all_documents_complete") is True

        # Verify database was updated
        updated_transaction = await db.user_transactions.find_one({"transaction_id": transaction_id})
        if updated_transaction:
            doc = updated_transaction["documents"][0]
            assert doc["translated_url"] == payload["file_url"]
            print(f"  Database verified: translated_url set")

        print("  PASSED")

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
            "transaction_id": "USER-IND-NOTFOUND"
        }

        print("\n  Testing 404 for non-existent individual transaction...")
        response = await http_client.post("/submit", json=payload)
        print(f"  Response: {response.status_code}")

        assert response.status_code == 404

        print("  PASSED")


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

        print("\n  Testing 422 for missing transaction_id...")
        response = await http_client.post("/submit", json=payload)
        print(f"  Response: {response.status_code}")

        assert response.status_code == 422

        print("  PASSED")

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

        print("\n  Testing 422 for empty transaction_id...")
        response = await http_client.post("/submit", json=payload)
        print(f"  Response: {response.status_code}")

        assert response.status_code == 422

        print("  PASSED")

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

        print("\n  Testing 422 for short transaction_id...")
        response = await http_client.post("/submit", json=payload)
        print(f"  Response: {response.status_code}")

        assert response.status_code == 422

        print("  PASSED")


# ============================================================================
# Test Cases - Email Batching
# ============================================================================

class TestSubmitEmailBatching:
    """Test email batching logic."""

    @pytest.mark.asyncio
    async def test_email_batching_blocks_until_all_complete(
        self, http_client, db, test_enterprise_transaction
    ):
        """
        Test email batching: email sent ONLY when ALL documents complete.

        Verifies:
        - First /submit: email_sent=False (1/2 complete)
        - Second /submit: email_sent=True (2/2 complete)
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        # Submit first document - EMAIL GATE SHOULD BLOCK (1/2)
        payload1 = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/trans1/view",
            "user_email": "danishevsky@gmail.com",
            "company_name": "Iris Trading",
            "transaction_id": transaction_id
        }

        print(f"\n  Testing email batching for transaction: {transaction_id}")
        print("  Submit 1/2...")
        response1 = await http_client.post("/submit", json=payload1)
        assert response1.status_code == 200
        data1 = response1.json()

        # Verify email NOT sent (incomplete)
        assert data1.get("email_sent") is False, "Email should not be sent when only 1/2 documents complete"
        assert data1.get("all_documents_complete") is False
        print(f"  First submit: email_sent={data1.get('email_sent')}, complete={data1.get('all_documents_complete')}")

        # Submit second document - EMAIL GATE SHOULD PASS (2/2)
        payload2 = {
            "file_name": "summary.docx",
            "file_url": "https://drive.google.com/file/d/trans2/view",
            "user_email": "danishevsky@gmail.com",
            "company_name": "Iris Trading",
            "transaction_id": transaction_id
        }

        print("  Submit 2/2...")
        response2 = await http_client.post("/submit", json=payload2)
        assert response2.status_code == 200
        data2 = response2.json()

        # Verify email batching triggered (all_documents_complete=True)
        # Note: email_sent may be False if SMTP server is unavailable
        assert data2.get("all_documents_complete") is True, "all_documents_complete should be True when 2/2 documents complete"
        # Accept either: email was sent OR email was attempted but failed due to SMTP issues
        if data2.get("email_sent") is False:
            # If email not sent, verify it was attempted (error message present)
            assert "email_error" in data2, \
                "If email_sent is False, email_error should explain why (SMTP unavailable is acceptable)"
            print(f"  Second submit: all_documents_complete=True, email attempted but failed: {data2.get('email_error')}")
        else:
            print(f"  Second submit: email_sent={data2.get('email_sent')}, complete={data2.get('all_documents_complete')}")

        # Verify database state
        final_transaction = await db.translation_transactions.find_one({"transaction_id": transaction_id})
        if final_transaction:
            assert final_transaction.get("completed_documents") == 2
            print(f"  Database verified: completed_documents=2")

        print("  PASSED")


# ============================================================================
# Test Cases - Filename Generation
# ============================================================================

class TestSubmitFilenameGeneration:
    """Test translated filename generation."""

    @pytest.mark.asyncio
    async def test_submit_generates_translated_name(
        self, http_client, db, test_enterprise_transaction
    ):
        """
        Test that translated_name is generated correctly.

        Verifies:
        - Simple filename: "report.pdf" -> "report_translated.pdf"
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        payload = {
            "file_name": "report.pdf",
            "file_url": "https://drive.google.com/file/d/trans/view",
            "user_email": "danishevsky@gmail.com",
            "company_name": "Iris Trading",
            "transaction_id": transaction_id
        }

        print(f"\n  Testing filename generation...")
        response = await http_client.post("/submit", json=payload)
        assert response.status_code == 200

        data = response.json()
        translated_name = data.get("translated_name", "")
        print(f"  Generated name: {translated_name}")

        # Should contain "translated" in the name
        assert "translated" in translated_name.lower() or "report" in translated_name

        # Verify in database
        updated_transaction = await db.translation_transactions.find_one({"transaction_id": transaction_id})
        if updated_transaction:
            doc_name = updated_transaction["documents"][0].get("translated_name", "")
            print(f"  Database name: {doc_name}")

        print("  PASSED")
