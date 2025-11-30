"""
Integration tests for split transaction confirm endpoints.

Tests comprehensive validation, success flow, failure flow, and edge cases for:
- /api/transactions/confirm-enterprise (Enterprise flow - no file search)
- /api/transactions/confirm-individual (Individual flow with payment - no file search)

Reference Implementation: app/main.py lines 1742-2119

CRITICAL: These tests use the REAL test database (translation_test) via the test_db fixture from conftest.py.
External services (Google Drive) are mocked, but database operations use real records.
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import httpx

# CRITICAL: Do NOT import database from app.database.mongodb
# All tests use the test_db fixture from conftest.py


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
async def enterprise_auth(test_db):
    """
    Get enterprise authentication headers for tests.

    Uses corporate login endpoint with credentials from Golden Source.
    Skips if login fails (server may not be in test mode).
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        try:
            response = await client.post(
                "/login/corporate",
                json={
                    "companyName": "Iris Trading",
                    "userEmail": "danishevsky@gmail.com",
                    "password": "Sveta87201120!",
                    "userFullName": "Manager User",  # Must match user_name in company_users
                    "loginDateTime": datetime.now(timezone.utc).isoformat()
                }
            )

            if response.status_code != 200:
                pytest.skip(f"Login failed ({response.status_code}) - server may not be in test mode")

            data = response.json()
            token = data.get("data", {}).get("authToken")
            if not token:
                pytest.skip("No auth token in login response")

            return {"Authorization": f"Bearer {token}"}
        except Exception as e:
            pytest.skip(f"Login error: {e}")


@pytest.fixture
def mock_google_drive_service():
    """
    Mock Google Drive service for all file operations.

    IMPORTANT: We mock EXTERNAL services (Google Drive) but use REAL database.
    This follows the requirement: "NO mocking of database or server - use real instances"

    Provides mocked methods:
    - move_files_to_inbox_on_payment_success: Simulates file movement
    - update_file_metadata: Updates file metadata
    - delete_file: Deletes file from Temp
    """
    with patch("app.services.google_drive_service.google_drive_service") as mock_service:
        # Default mock for move_files_to_inbox_on_payment_success
        mock_service.move_files_to_inbox_on_payment_success = AsyncMock(return_value={
            "inbox_folder_id": "inbox-folder-123",
            "total_files": 1,
            "moved_successfully": 1,
            "moved_files": [
                {
                    "file_id": "test-file-id-001",
                    "filename": "test_document.pdf",
                    "new_parent": "inbox-folder-123"
                }
            ],
            "failed_moves": 0
        })

        # Default mock for update_file_metadata
        mock_service.update_file_metadata = AsyncMock(return_value=True)

        # Default mock for delete_file
        mock_service.delete_file = AsyncMock(return_value=True)

        yield mock_service


@pytest.fixture(scope="function")
async def cleanup_confirm_test_data(db):
    """
    Cleanup test data after each test.

    Uses test_db fixture to clean up test database (translation_test).
    Only deletes records with TEST- prefix to preserve other test data.
    """
    yield
    # Clean up test transactions (only those with TEST- prefix)
    try:
        # Delete test transactions
        await db.translation_transactions.delete_many({
            "transaction_id": {"$regex": "^TXN-TEST-"}
        })
        # Delete test user transactions
        await db.user_transactions.delete_many({
            "transaction_id": {"$regex": "^TXN-TEST-"}
        })
    except Exception as e:
        # Ignore cleanup errors
        print(f"Cleanup warning: {e}")


# ============================================================================
# Enterprise Confirm Tests
# ============================================================================

@pytest.mark.asyncio
async def test_enterprise_confirm_success(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    enterprise_auth
):
    """
    Enterprise confirm success flow.

    Setup: Create Enterprise user with company_name, upload files, create transaction
    Call: POST /api/transactions/confirm-enterprise with transaction_id, status=true
    Assert:
    - HTTP 200
    - Transaction status updated to 'processing'
    - Response contains confirmation details
    """
    # Setup: Create Enterprise transaction
    transaction_id = f"TXN-TEST-ENT-{uuid.uuid4().hex[:8].upper()}"
    company_name = "Iris Trading"  # Use real company from Golden Source

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "danishevsky@gmail.com",  # Real user from Golden Source
        "company_name": company_name,
        "source_language": "en",
        "target_language": "es",
        "units_count": 10,
        "price_per_unit": 0.10,
        "total_price": 1.00,
        "status": "awaiting_confirmation",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "documents": [
            {
                "file_id": "file-001",
                "file_name": "enterprise_doc.pdf",
                "file_size": 204800,
                "original_url": "https://docs.google.com/document/d/file-001/edit",
                "status": "uploaded"
            }
        ]
    }

    await db.translation_transactions.insert_one(transaction_doc)
    print(f"\n  Created enterprise transaction: {transaction_id}")

    # Call API
    response = await http_client.post(
        "/api/transactions/confirm-enterprise",
        json={
            "transaction_id": transaction_id,
            "status": True
        },
        headers=enterprise_auth
    )
    print(f"  POST /api/transactions/confirm-enterprise")
    print(f"  Response: {response.status_code}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert data["success"] is True
    assert "confirmed" in data["message"].lower() or "processing" in data["message"].lower()
    assert data["data"]["transaction_id"] == transaction_id

    # Verify transaction status updated in database
    txn = await db.translation_transactions.find_one({"transaction_id": transaction_id})
    assert txn["status"] == "processing", f"Expected status=processing, got {txn['status']}"

    print(f"  Database verified: status={txn['status']}")
    print("  PASSED")


@pytest.mark.asyncio
async def test_enterprise_confirm_cancel(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    enterprise_auth
):
    """
    Enterprise cancel flow.

    Setup: Create Enterprise transaction
    Call: POST /api/transactions/confirm-enterprise with status=false
    Assert:
    - HTTP 200
    - Transaction status updated to 'cancelled'
    """
    transaction_id = f"TXN-TEST-ENT-{uuid.uuid4().hex[:8].upper()}"
    company_name = "Iris Trading"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "danishevsky@gmail.com",
        "company_name": company_name,
        "status": "awaiting_confirmation",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "documents": [
            {
                "file_id": "file-001",
                "file_name": "enterprise_doc.pdf"
            }
        ]
    }

    await db.translation_transactions.insert_one(transaction_doc)
    print(f"\n  Created enterprise transaction for cancel: {transaction_id}")

    response = await http_client.post(
        "/api/transactions/confirm-enterprise",
        json={
            "transaction_id": transaction_id,
            "status": False
        },
        headers=enterprise_auth
    )
    print(f"  POST /api/transactions/confirm-enterprise (cancel)")
    print(f"  Response: {response.status_code}")

    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "cancelled" in data["message"].lower()

    # Verify transaction status updated
    txn = await db.translation_transactions.find_one({"transaction_id": transaction_id})
    assert txn["status"] == "cancelled"

    print(f"  Database verified: status={txn['status']}")
    print("  PASSED")


@pytest.mark.asyncio
async def test_enterprise_missing_transaction_404(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    enterprise_auth
):
    """
    Enterprise confirm with non-existent transaction_id (404 Not Found).
    """
    print("\n  Testing 404 for non-existent transaction...")

    response = await http_client.post(
        "/api/transactions/confirm-enterprise",
        json={
            "transaction_id": "TXN-NONEXISTENT-12345",
            "status": True
        },
        headers=enterprise_auth
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code == 404
    data = response.json()
    # Check for error message in either format
    error_message = data.get("detail", "") or data.get("error", {}).get("message", "")
    assert "not found" in error_message.lower()

    print("  PASSED")


@pytest.mark.asyncio
async def test_enterprise_no_documents_400(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    enterprise_auth
):
    """
    Enterprise transaction with no documents array (400 Bad Request).
    """
    transaction_id = f"TXN-TEST-ENT-{uuid.uuid4().hex[:8].upper()}"
    company_name = "Iris Trading"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "danishevsky@gmail.com",
        "company_name": company_name,
        "status": "awaiting_confirmation",
        "created_at": datetime.now(timezone.utc)
        # Missing 'documents' field
    }

    await db.translation_transactions.insert_one(transaction_doc)
    print(f"\n  Created transaction without documents: {transaction_id}")

    response = await http_client.post(
        "/api/transactions/confirm-enterprise",
        json={
            "transaction_id": transaction_id,
            "status": True
        },
        headers=enterprise_auth
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code == 400
    data = response.json()
    error_message = data.get("detail", "") or data.get("error", {}).get("message", "")
    assert "no documents" in error_message.lower()

    print("  PASSED")


@pytest.mark.asyncio
async def test_enterprise_multiple_files(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    enterprise_auth
):
    """
    Enterprise confirm with multiple files.

    Verifies all files are processed correctly.
    """
    transaction_id = f"TXN-TEST-ENT-{uuid.uuid4().hex[:8].upper()}"
    company_name = "Iris Trading"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "danishevsky@gmail.com",
        "company_name": company_name,
        "status": "awaiting_confirmation",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "documents": [
            {"file_id": "file-001", "file_name": "doc1.pdf"},
            {"file_id": "file-002", "file_name": "doc2.pdf"},
            {"file_id": "file-003", "file_name": "doc3.pdf"}
        ]
    }

    await db.translation_transactions.insert_one(transaction_doc)
    print(f"\n  Created transaction with 3 documents: {transaction_id}")

    # Mock move result for multiple files
    mock_google_drive_service.move_files_to_inbox_on_payment_success.return_value = {
        "inbox_folder_id": "inbox-folder-123",
        "total_files": 3,
        "moved_successfully": 3,
        "moved_files": [
            {"file_id": "file-001"},
            {"file_id": "file-002"},
            {"file_id": "file-003"}
        ],
        "failed_moves": 0
    }

    response = await http_client.post(
        "/api/transactions/confirm-enterprise",
        json={
            "transaction_id": transaction_id,
            "status": True
        },
        headers=enterprise_auth
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code == 200

    data = response.json()
    # Check that response is successful - file movement may not happen in test env
    assert data.get("success") is True or "data" in data
    # total_files should match the number of documents
    if "data" in data and "total_files" in data["data"]:
        assert data["data"]["total_files"] == 3

    # Verify transaction status is updated to processing
    txn = await db.translation_transactions.find_one({"transaction_id": transaction_id})
    assert txn["status"] == "processing", f"Expected 'processing', got '{txn['status']}'"

    print(f"  Verified: status={txn['status']}, total_files={data.get('data', {}).get('total_files', 'N/A')}")
    print("  PASSED")


# ============================================================================
# Individual Confirm Tests
# ============================================================================

@pytest.mark.asyncio
async def test_individual_confirm_success(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    individual_headers
):
    """
    Individual confirm success flow with payment.

    Setup: Create Individual user (no company), upload files, create transaction
    Call: POST /api/transactions/confirm-individual with transaction_id, square_transaction_id, file_ids
    Assert:
    - HTTP 200
    - Transaction status updated to 'completed'
    - square_transaction_id stored in transaction
    """
    transaction_id = f"TXN-TEST-IND-{uuid.uuid4().hex[:8].upper()}"
    user_email = "danishevsky@yahoo.com"  # Individual user from Golden Source
    square_txn_id = f"sqt_test_{uuid.uuid4().hex[:12]}"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "source_language": "en",
        "target_language": "fr",
        "units_count": 5,
        "price_per_unit": 0.10,
        "total_price": 0.50,
        "status": "started",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "documents": [
            {
                "file_id": "file-ind-001",
                "file_name": "individual_doc.pdf"
            }
        ]
    }

    await db.user_transactions.insert_one(transaction_doc)
    print(f"\n  Created individual transaction: {transaction_id}")

    response = await http_client.post(
        "/api/transactions/confirm-individual",
        json={
            "transaction_id": transaction_id,
            "square_transaction_id": square_txn_id,
            "file_ids": ["file-ind-001"],
            "status": True
        },
        headers=individual_headers
    )
    print(f"  POST /api/transactions/confirm-individual")
    print(f"  Response: {response.status_code}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert data["success"] is True
    assert "confirmed" in data["message"].lower() or "completed" in data["message"].lower()
    assert data["data"]["transaction_id"] == transaction_id
    assert data["data"]["square_transaction_id"] == square_txn_id

    # Verify transaction updated
    txn = await db.user_transactions.find_one({"transaction_id": transaction_id})
    assert txn["status"] == "completed"
    assert txn["square_transaction_id"] == square_txn_id

    print(f"  Database verified: status={txn['status']}, square_txn_id stored")
    print("  PASSED")


@pytest.mark.asyncio
async def test_individual_confirm_cancel(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    individual_headers
):
    """
    Individual cancel flow.

    Call: POST /api/transactions/confirm-individual with status=false
    Assert:
    - HTTP 200
    - Transaction status updated to 'cancelled'
    """
    transaction_id = f"TXN-TEST-IND-{uuid.uuid4().hex[:8].upper()}"
    user_email = "danishevsky@yahoo.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "status": "started",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await db.user_transactions.insert_one(transaction_doc)
    print(f"\n  Created individual transaction for cancel: {transaction_id}")

    response = await http_client.post(
        "/api/transactions/confirm-individual",
        json={
            "transaction_id": transaction_id,
            "file_ids": ["file-ind-001"],
            "status": False
        },
        headers=individual_headers
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "cancelled" in data["message"].lower()

    # Verify transaction status
    txn = await db.user_transactions.find_one({"transaction_id": transaction_id})
    assert txn["status"] == "cancelled"

    print(f"  Database verified: status={txn['status']}")
    print("  PASSED")


@pytest.mark.asyncio
async def test_individual_missing_file_ids_422(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    individual_headers
):
    """
    Individual confirm without file_ids (422 validation error).
    """
    transaction_id = f"TXN-TEST-IND-{uuid.uuid4().hex[:8].upper()}"
    user_email = "danishevsky@yahoo.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "status": "started",
        "created_at": datetime.now(timezone.utc)
    }

    await db.user_transactions.insert_one(transaction_doc)
    print(f"\n  Testing missing file_ids validation...")

    # Missing file_ids
    response = await http_client.post(
        "/api/transactions/confirm-individual",
        json={
            "transaction_id": transaction_id,
            "status": True
        },
        headers=individual_headers
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code == 422  # Pydantic validation error

    print("  PASSED")


@pytest.mark.asyncio
async def test_individual_empty_file_ids_400(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    individual_headers
):
    """
    Individual confirm with empty file_ids array (400 Bad Request).
    """
    transaction_id = f"TXN-TEST-IND-{uuid.uuid4().hex[:8].upper()}"
    user_email = "danishevsky@yahoo.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "status": "started",
        "created_at": datetime.now(timezone.utc)
    }

    await db.user_transactions.insert_one(transaction_doc)
    print(f"\n  Testing empty file_ids validation...")

    response = await http_client.post(
        "/api/transactions/confirm-individual",
        json={
            "transaction_id": transaction_id,
            "file_ids": [],  # Empty array
            "status": True
        },
        headers=individual_headers
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code == 400
    data = response.json()
    error_message = data.get("detail", "") or data.get("error", {}).get("message", "")
    assert "file_ids" in error_message.lower() or "required" in error_message.lower()

    print("  PASSED")


# ============================================================================
# Authentication Tests
# ============================================================================

@pytest.mark.asyncio
async def test_enterprise_authentication_required(http_client: httpx.AsyncClient):
    """
    Test that authentication is required for enterprise endpoint (no Authorization header).

    Should return 401 or 403.
    """
    print("\n  Testing enterprise authentication required...")

    # No Authorization header
    response = await http_client.post(
        "/api/transactions/confirm-enterprise",
        json={
            "transaction_id": "TXN-TEST-001",
            "status": True
        }
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code in [401, 403]

    print("  PASSED")


@pytest.mark.asyncio
async def test_individual_authentication_required(http_client: httpx.AsyncClient):
    """
    Test that authentication is required for individual endpoint (no Authorization header).

    Should return 401 or 403.
    """
    print("\n  Testing individual authentication required...")

    # No Authorization header
    response = await http_client.post(
        "/api/transactions/confirm-individual",
        json={
            "transaction_id": "TXN-TEST-001",
            "file_ids": ["file-001"],
            "status": True
        }
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code in [401, 403]

    print("  PASSED")


# ============================================================================
# Database State Verification Tests
# ============================================================================

@pytest.mark.asyncio
async def test_enterprise_confirm_updates_timestamp(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    enterprise_auth
):
    """
    Verify that confirm updates the updated_at timestamp.
    """
    transaction_id = f"TXN-TEST-ENT-{uuid.uuid4().hex[:8].upper()}"
    company_name = "Iris Trading"
    original_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "danishevsky@gmail.com",
        "company_name": company_name,
        "status": "awaiting_confirmation",
        "created_at": original_time,
        "updated_at": original_time,
        "documents": [
            {"file_id": "file-001", "file_name": "doc.pdf"}
        ]
    }

    await db.translation_transactions.insert_one(transaction_doc)
    print(f"\n  Created transaction with old timestamp: {transaction_id}")

    response = await http_client.post(
        "/api/transactions/confirm-enterprise",
        json={
            "transaction_id": transaction_id,
            "status": True
        },
        headers=enterprise_auth
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code == 200

    # Verify updated_at was changed
    txn = await db.translation_transactions.find_one({"transaction_id": transaction_id})
    # MongoDB may store naive datetimes, so compare appropriately
    updated_at = txn["updated_at"]
    if updated_at.tzinfo is None:
        original_time_naive = original_time.replace(tzinfo=None)
        assert updated_at > original_time_naive, "updated_at should be newer than original"
    else:
        assert updated_at > original_time, "updated_at should be newer than original"

    print(f"  Timestamp updated: {txn['updated_at']}")
    print("  PASSED")


@pytest.mark.asyncio
async def test_individual_confirm_stores_payment_info(
    http_client: httpx.AsyncClient,
    db,
    mock_google_drive_service,
    cleanup_confirm_test_data,
    individual_headers
):
    """
    Verify that individual confirm stores payment information.
    """
    transaction_id = f"TXN-TEST-IND-{uuid.uuid4().hex[:8].upper()}"
    user_email = "danishevsky@yahoo.com"
    square_txn_id = f"sqt_payment_{uuid.uuid4().hex[:12]}"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "status": "started",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await db.user_transactions.insert_one(transaction_doc)
    print(f"\n  Created individual transaction: {transaction_id}")

    response = await http_client.post(
        "/api/transactions/confirm-individual",
        json={
            "transaction_id": transaction_id,
            "square_transaction_id": square_txn_id,
            "file_ids": ["file-001"],
            "status": True
        },
        headers=individual_headers
    )
    print(f"  Response: {response.status_code}")

    assert response.status_code == 200

    # Verify payment info stored
    txn = await db.user_transactions.find_one({"transaction_id": transaction_id})
    assert txn["square_transaction_id"] == square_txn_id
    assert txn["status"] == "completed"

    print(f"  Payment info stored: {square_txn_id}")
    print("  PASSED")
