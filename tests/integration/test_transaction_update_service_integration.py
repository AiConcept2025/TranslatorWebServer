"""
INTEGRATION TESTS FOR TRANSACTION UPDATE VIA REAL HTTP ENDPOINTS

These tests make REAL HTTP requests to the running server's /submit endpoint
and verify responses against the REAL MongoDB database (translation_test).

NO MOCKS - Real API + Real Database testing.

Test Database: translation_test (separate from production)
Endpoint: POST /submit (handles webhook callbacks from GoogleTranslator)

REQUIREMENTS:
- Server must be running: cd server && uvicorn app.main:app --reload
- MongoDB must be running with translation_test database
"""

import pytest
import httpx
import uuid
from datetime import datetime, timezone

# ============================================================================
# Test Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8000"


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def db(test_db):
    """
    Get the test database via conftest fixture.
    Uses test_db fixture from conftest.py to ensure translation_test is used.
    """
    yield test_db


@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls to running server."""
    async_client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0)
    yield async_client
    await async_client.aclose()


@pytest.fixture(scope="function")
async def test_enterprise_transaction(db):
    """
    Create a test enterprise transaction in translation_transactions collection.
    Automatically cleaned up after test.
    """
    collection = db.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "company_name": "Test Integration Corp",
        "user_id": "integration@testcorp.com",
        "user_name": "Integration Test User",
        "status": "processing",
        "source_language": "en",
        "target_language": "es",
        "documents": [
            {
                "file_name": "test_report.pdf",
                "file_size": 524288,
                "original_url": "https://drive.google.com/file/d/original_test_1/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None
            },
            {
                "file_name": "test_summary.docx",
                "file_size": 262144,
                "original_url": "https://drive.google.com/file/d/original_test_2/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None
            }
        ],
        "total_documents": 2,
        "completed_documents": 0,
        "batch_email_sent": False,
        "created_at": now,
        "updated_at": now
    }

    await collection.insert_one(transaction_doc)
    print(f"\n  Created test enterprise transaction: {transaction_id}")

    yield transaction_doc

    # Cleanup
    await collection.delete_one({"transaction_id": transaction_id})
    print(f"  Cleaned up test enterprise transaction: {transaction_id}")


@pytest.fixture(scope="function")
async def test_individual_transaction(db):
    """
    Create a test individual transaction in user_transactions collection.
    Automatically cleaned up after test.
    """
    collection = db.user_transactions

    transaction_id = f"TXN-IND-TEST-{uuid.uuid4().hex[:8].upper()}"
    square_txn_id = f"SQR-TEST-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "square_transaction_id": square_txn_id,
        "user_email": "individual_integration@example.com",
        "user_name": "Jane Integration Test",
        "status": "processing",
        "source_language": "fr",
        "target_language": "en",
        "documents": [
            {
                "file_name": "passport_test.pdf",
                "file_size": 131072,
                "original_url": "https://drive.google.com/file/d/passport_orig/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None
            }
        ],
        "total_documents": 1,
        "completed_documents": 0,
        "batch_email_sent": False,
        "created_at": now,
        "updated_at": now
    }

    await collection.insert_one(transaction_doc)
    print(f"\n  Created test individual transaction: {transaction_id}")

    yield transaction_doc

    # Cleanup
    await collection.delete_one({"transaction_id": transaction_id})
    print(f"  Cleaned up test individual transaction: {transaction_id}")


# ============================================================================
# Test Class: Server Health Check
# ============================================================================

@pytest.mark.asyncio
class TestServerConnection:
    """Verify that the real server is running and accessible."""

    async def test_server_health_check(self, http_client):
        """Test that the server is running."""
        response = await http_client.get("/health")
        assert response.status_code == 200, \
            f"Server not running! Start with: uvicorn app.main:app --reload. Got: {response.status_code}"
        print("\n  Server health check passed")


# ============================================================================
# Test Class: Enterprise Transaction Updates via /submit endpoint
# ============================================================================

@pytest.mark.asyncio
class TestEnterpriseTransactionUpdatesIntegration:
    """Integration tests for enterprise transaction updates via real HTTP endpoint."""

    async def test_update_enterprise_transaction_success(
        self, http_client, db, test_enterprise_transaction
    ):
        """
        Test successful update of enterprise transaction via POST /submit.

        Verifies:
        - HTTP endpoint returns 200
        - Document is found and updated in real database
        - translated_url is set correctly
        - completed_documents counter is incremented
        """
        transaction_id = test_enterprise_transaction["transaction_id"]
        file_url = "https://drive.google.com/file/d/translated_test_1/view"

        # Make real HTTP request to /submit endpoint
        submit_data = {
            "file_name": "test_report.pdf",
            "file_url": file_url,
            "user_email": "integration@testcorp.com",
            "company_name": "Test Integration Corp",
            "transaction_id": transaction_id
        }

        response = await http_client.post("/submit", json=submit_data)

        print(f"\n  POST /submit Response Status: {response.status_code}")
        print(f"  Response: {response.text[:500]}")

        # Verify HTTP response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "success"
        assert data["transaction_id"] == transaction_id

        # Verify database state
        collection = db.translation_transactions
        updated = await collection.find_one({"transaction_id": transaction_id})

        assert updated is not None
        assert updated["completed_documents"] == 1
        doc = updated["documents"][0]
        assert doc["translated_url"] == file_url
        assert doc["status"] == "completed"

        print(f"  Database verified: completed_documents={updated['completed_documents']}")

    async def test_update_enterprise_transaction_not_found(self, http_client):
        """
        Test update when transaction doesn't exist.

        Verifies:
        - HTTP endpoint returns 404
        - Error message indicates transaction not found
        """
        submit_data = {
            "file_name": "test.pdf",
            "file_url": "https://drive.google.com/file/d/test/view",
            "user_email": "test@example.com",
            "company_name": "Nonexistent Corp",
            "transaction_id": "TXN-NONEXISTENT-12345"
        }

        response = await http_client.post("/submit", json=submit_data)

        print(f"\n  POST /submit Response Status: {response.status_code}")

        # Should return 404 for not found
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        assert "not found" in data.get("error", "").lower()

        print(f"  Correctly returned 404 for non-existent transaction")

    async def test_update_enterprise_document_not_found(
        self, http_client, test_enterprise_transaction
    ):
        """
        Test update when document name doesn't match any in transaction.

        Verifies:
        - HTTP endpoint returns 404
        - Error message indicates document not found
        """
        transaction_id = test_enterprise_transaction["transaction_id"]

        submit_data = {
            "file_name": "nonexistent_file.pdf",
            "file_url": "https://drive.google.com/file/d/test/view",
            "user_email": "integration@testcorp.com",
            "company_name": "Test Integration Corp",
            "transaction_id": transaction_id
        }

        response = await http_client.post("/submit", json=submit_data)

        print(f"\n  POST /submit Response Status: {response.status_code}")

        # Should return 404 for document not found
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

        print(f"  Correctly returned 404 for non-existent document")

    async def test_update_enterprise_multiple_documents(
        self, http_client, db, test_enterprise_transaction
    ):
        """
        Test updating multiple documents in the same transaction.

        Verifies:
        - Each update via HTTP returns 200
        - Each update increments completed_documents
        - Both documents are correctly updated in database
        """
        transaction_id = test_enterprise_transaction["transaction_id"]
        collection = db.translation_transactions

        # Update first document via HTTP
        submit_data_1 = {
            "file_name": "test_report.pdf",
            "file_url": "https://drive.google.com/file/d/trans1/view",
            "user_email": "integration@testcorp.com",
            "company_name": "Test Integration Corp",
            "transaction_id": transaction_id
        }

        response1 = await http_client.post("/submit", json=submit_data_1)
        assert response1.status_code == 200, f"First update failed: {response1.text}"
        print(f"\n  First document updated successfully")

        # Verify first update in database
        updated1 = await collection.find_one({"transaction_id": transaction_id})
        assert updated1["completed_documents"] == 1
        print(f"  Database: completed_documents={updated1['completed_documents']}")

        # Update second document via HTTP
        submit_data_2 = {
            "file_name": "test_summary.docx",
            "file_url": "https://drive.google.com/file/d/trans2/view",
            "user_email": "integration@testcorp.com",
            "company_name": "Test Integration Corp",
            "transaction_id": transaction_id
        }

        response2 = await http_client.post("/submit", json=submit_data_2)
        assert response2.status_code == 200, f"Second update failed: {response2.text}"
        print(f"  Second document updated successfully")

        # Verify second update in database
        updated2 = await collection.find_one({"transaction_id": transaction_id})
        assert updated2["completed_documents"] == 2
        assert all(doc["translated_url"] for doc in updated2["documents"])
        print(f"  Database: completed_documents={updated2['completed_documents']}, all docs have translated_url")

    async def test_update_enterprise_idempotency(
        self, http_client, db, test_enterprise_transaction
    ):
        """
        Test that duplicate updates are handled correctly (idempotency via cache).

        Verifies:
        - First update via HTTP returns 200
        - Second update with SAME file_url returns cached 200 (deduplication)
        - completed_documents is NOT double-incremented
        """
        transaction_id = test_enterprise_transaction["transaction_id"]
        collection = db.translation_transactions
        file_url = "https://drive.google.com/file/d/trans_idempotent/view"

        submit_data = {
            "file_name": "test_report.pdf",
            "file_url": file_url,
            "user_email": "integration@testcorp.com",
            "company_name": "Test Integration Corp",
            "transaction_id": transaction_id
        }

        # First update - should succeed
        response1 = await http_client.post("/submit", json=submit_data)
        assert response1.status_code == 200, f"First update failed: {response1.text}"
        print(f"\n  First update: status={response1.status_code}")

        # Second update with SAME data - should return cached result (200)
        # The /submit endpoint has webhook deduplication cache
        response2 = await http_client.post("/submit", json=submit_data)
        print(f"  Second update (same data): status={response2.status_code}")

        # Both should return 200 (second from cache)
        assert response2.status_code == 200, f"Second update unexpected: {response2.text}"

        # Verify counter wasn't double-incremented
        updated = await collection.find_one({"transaction_id": transaction_id})
        assert updated["completed_documents"] == 1, \
            f"Counter double-incremented! Expected 1, got {updated['completed_documents']}"
        print(f"  Idempotency verified: completed_documents={updated['completed_documents']}")


# ============================================================================
# Test Class: Individual Transaction Updates via /submit endpoint
# ============================================================================

@pytest.mark.asyncio
class TestIndividualTransactionUpdatesIntegration:
    """Integration tests for individual transaction updates via real HTTP endpoint."""

    async def test_update_individual_transaction_success(
        self, http_client, db, test_individual_transaction
    ):
        """
        Test successful update of individual transaction via POST /submit.

        Verifies:
        - HTTP endpoint returns 200
        - Document is found and updated in user_transactions
        - translated_url is set correctly
        - completed_documents counter is incremented
        """
        transaction_id = test_individual_transaction["transaction_id"]
        file_url = "https://drive.google.com/file/d/passport_trans/view"

        # Individual users have company_name = "Ind"
        submit_data = {
            "file_name": "passport_test.pdf",
            "file_url": file_url,
            "user_email": "individual_integration@example.com",
            "company_name": "Ind",
            "transaction_id": transaction_id
        }

        response = await http_client.post("/submit", json=submit_data)

        print(f"\n  POST /submit Response Status: {response.status_code}")
        print(f"  Response: {response.text[:500]}")

        # Verify HTTP response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["status"] == "success"

        # Verify database state
        collection = db.user_transactions
        updated = await collection.find_one({"transaction_id": transaction_id})

        assert updated is not None
        assert updated["completed_documents"] == 1
        doc = updated["documents"][0]
        assert doc["translated_url"] == file_url
        assert doc["status"] == "completed"

        print(f"  Database verified: completed_documents={updated['completed_documents']}")

    async def test_update_individual_transaction_not_found(self, http_client):
        """
        Test update when individual transaction doesn't exist.
        """
        submit_data = {
            "file_name": "test.pdf",
            "file_url": "https://drive.google.com/file/d/test/view",
            "user_email": "nobody@example.com",
            "company_name": "Ind",
            "transaction_id": "TXN-IND-NONEXISTENT-999"
        }

        response = await http_client.post("/submit", json=submit_data)

        print(f"\n  POST /submit Response Status: {response.status_code}")

        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"  Correctly returned 404 for non-existent individual transaction")


# ============================================================================
# Test Class: Extension-Agnostic Filename Matching via /submit
# ============================================================================

@pytest.mark.asyncio
class TestFilenameMatchingIntegration:
    """Integration tests for extension-agnostic filename matching via HTTP."""

    async def test_match_pdf_to_translated_docx(self, http_client, db):
        """
        Test that PDF original matches DOCX translated (common case).

        GoogleTranslator often converts PDF to DOCX, so webhook filename
        might be "report_translated.docx" for original "report.pdf".
        """
        collection = db.translation_transactions
        transaction_id = f"TXN-TEST-EXT-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        # Create transaction with PDF file
        await collection.insert_one({
            "transaction_id": transaction_id,
            "company_name": "Extension Test Corp",
            "user_id": "ext@test.com",
            "user_name": "Ext Test User",
            "status": "processing",
            "documents": [{
                "file_name": "NuVIZ_Report.pdf",  # Original is PDF
                "original_url": "https://example.com/orig",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now
            }],
            "total_documents": 1,
            "completed_documents": 0,
            "created_at": now,
            "updated_at": now
        })

        try:
            # Webhook sends DOCX with _translated suffix via HTTP
            submit_data = {
                "file_name": "NuVIZ_Report_translated.docx",  # Translated is DOCX
                "file_url": "https://drive.google.com/file/d/trans_ext/view",
                "user_email": "ext@test.com",
                "company_name": "Extension Test Corp",
                "transaction_id": transaction_id
            }

            response = await http_client.post("/submit", json=submit_data)

            print(f"\n  POST /submit Response Status: {response.status_code}")

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            # Verify database update
            updated = await collection.find_one({"transaction_id": transaction_id})
            assert updated["documents"][0]["translated_url"] is not None
            print(f"  PDF->DOCX matching verified in database")

        finally:
            await collection.delete_one({"transaction_id": transaction_id})

    async def test_match_case_insensitive(self, http_client, db):
        """
        Test case-insensitive filename matching via HTTP.
        """
        collection = db.translation_transactions
        transaction_id = f"TXN-TEST-CASE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)

        # Create transaction with mixed-case filename
        await collection.insert_one({
            "transaction_id": transaction_id,
            "company_name": "Case Test Corp",
            "user_id": "case@test.com",
            "user_name": "Case Test User",
            "status": "processing",
            "documents": [{
                "file_name": "MyDocument.PDF",  # Mixed case
                "original_url": "https://example.com/orig",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now
            }],
            "total_documents": 1,
            "completed_documents": 0,
            "created_at": now,
            "updated_at": now
        })

        try:
            # Webhook sends lowercase via HTTP
            submit_data = {
                "file_name": "mydocument_translated.docx",  # Different case
                "file_url": "https://drive.google.com/file/d/trans_case/view",
                "user_email": "case@test.com",
                "company_name": "Case Test Corp",
                "transaction_id": transaction_id
            }

            response = await http_client.post("/submit", json=submit_data)

            print(f"\n  POST /submit Response Status: {response.status_code}")

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            print(f"  Case-insensitive matching verified")

        finally:
            await collection.delete_one({"transaction_id": transaction_id})


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("TRANSACTION UPDATE SERVICE - REAL HTTP INTEGRATION TESTS")
    print("=" * 80)
    print("\nRunning tests against:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Endpoint: POST /submit")
    print("\nNOTE: These tests use REAL HTTP requests to the running server")
    print("NOTE: Server must be running: uvicorn app.main:app --reload")
    print("=" * 80)
    print("\n")
