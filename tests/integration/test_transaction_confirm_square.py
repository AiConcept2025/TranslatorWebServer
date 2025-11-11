"""
Integration tests for /api/transactions/confirm endpoint (Square payment confirmation).

Tests comprehensive validation, success flow, failure flow, and edge cases for the Square payment
confirmation endpoint that processes payments and manages files in Google Drive.

Reference Implementation: app/main.py lines 1166-1567
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from app.main import app
from app.database import database


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
async def init_database():
    """Initialize database connection for tests."""
    await database.connect()
    yield
    # Database disconnect is handled by pytest cleanup


@pytest.fixture(autouse=True)
async def mock_auth_service():
    """Mock authentication service to return test user for all tests."""
    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "test@example.com",
            "sub": "test-user-id-123",
            "user_name": "Test User",
            "user_id": "test-user-id-123"
        }
        yield mock_verify


@pytest.fixture
async def mock_google_drive_service():
    """
    Mock Google Drive service for all file operations.

    Provides mocked methods:
    - find_files_by_customer_email: Returns list of files in Temp folder
    - move_files_to_inbox_on_payment_success: Simulates file movement
    - update_file_metadata: Updates file metadata
    - delete_file: Deletes file from Temp
    """
    with patch("app.services.google_drive_service.google_drive_service") as mock_service:
        # Default mock for find_files_by_customer_email
        mock_service.find_files_by_customer_email = AsyncMock(return_value=[
            {
                "file_id": "test-file-id-001",
                "filename": "test_document.pdf",
                "size": 204800,
                "google_drive_url": "https://docs.google.com/document/d/test-file-id-001/edit",
                "metadata": {
                    "customer_email": "test@example.com",
                    "status": "awaiting_payment",
                    "source_language": "en",
                    "target_language": "es",
                    "total_units": 10,
                    "total_price": 0.10
                }
            }
        ])

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
            "failed_moves": []
        })

        # Default mock for update_file_metadata
        mock_service.update_file_metadata = AsyncMock(return_value=True)

        # Default mock for delete_file
        mock_service.delete_file = AsyncMock(return_value=True)

        yield mock_service


@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Cleanup test data after each test."""
    yield
    # Clean up test transactions (only those with TEST- prefix)
    try:
        if database.user_transactions is not None:
            await database.user_transactions.delete_many({
                "square_transaction_id": {"$regex": "^TEST-"}
            })
    except Exception as e:
        # Ignore cleanup errors (database might not be connected in some tests)
        pass


# ============================================================================
# Request Validation Tests (422 Errors)
# ============================================================================

@pytest.mark.asyncio
async def test_confirm_valid_success_request(mock_google_drive_service):
    """
    ✅ Valid success request (status=True with square_transaction_id).

    Should return 200 and create transaction.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_3030c9a6c8c94a5180e2",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["success"] is True
        assert "transaction_id" in data["data"]
        assert data["data"]["square_transaction_id"] == "TEST-sqt_3030c9a6c8c94a5180e2"
        assert data["data"]["status"] == "processing"


@pytest.mark.asyncio
async def test_confirm_valid_failure_request(mock_google_drive_service):
    """
    ✅ Valid failure request (status=False with square_transaction_id="NONE").

    Should return 200 and delete files.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["success"] is False
        assert "Payment failed" in data["message"]
        assert data["data"]["files_deleted"] == 1


@pytest.mark.asyncio
async def test_confirm_missing_square_transaction_id(mock_google_drive_service):
    """
    ❌ Missing square_transaction_id field (422 error).

    Pydantic validation should reject request.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "status": True
                # Missing square_transaction_id
            },
            headers=headers
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

        data = response.json()
        assert "detail" in data
        # Verify error mentions missing field
        error_fields = [err["loc"][-1] for err in data["detail"]]
        assert "square_transaction_id" in error_fields


@pytest.mark.asyncio
async def test_confirm_missing_status_field(mock_google_drive_service):
    """
    ❌ Missing status field (422 error).

    Pydantic validation should reject request.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_123"
                # Missing status
            },
            headers=headers
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

        data = response.json()
        assert "detail" in data
        error_fields = [err["loc"][-1] for err in data["detail"]]
        assert "status" in error_fields


@pytest.mark.asyncio
async def test_confirm_wrong_type_for_status(mock_google_drive_service):
    """
    ❌ Wrong type for status (string instead of boolean) (422 error).

    Pydantic validation should reject non-boolean status.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_123",
                "status": "true"  # String instead of boolean
            },
            headers=headers
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

        data = response.json()
        assert "detail" in data


@pytest.mark.asyncio
async def test_confirm_empty_request_body(mock_google_drive_service):
    """
    ❌ Empty request body (422 error).

    Pydantic validation should reject empty body.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={},  # Empty body
            headers=headers
        )

        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

        data = response.json()
        assert "detail" in data
        # Should complain about missing required fields
        error_fields = [err["loc"][-1] for err in data["detail"]]
        assert "square_transaction_id" in error_fields or "status" in error_fields


# ============================================================================
# Success Flow Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_success_flow_creates_transaction(mock_google_drive_service):
    """
    Test success flow creates transaction in user_transactions collection.

    Verifies:
    - Transaction created with correct square_transaction_id
    - Transaction has generated transaction_id (TXN- format)
    - Transaction status is 'started'
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_success_001",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        transaction_id = data["data"]["transaction_id"]

        # Verify transaction exists in database
        txn = await database.user_transactions.find_one({"transaction_id": transaction_id})
        assert txn is not None, "Transaction should exist in database"
        assert txn["square_transaction_id"] == "TEST-sqt_success_001"
        assert txn["transaction_id"].startswith("TXN-")
        assert txn["status"] == "started"
        assert txn["user_id"] == "test@example.com"


@pytest.mark.asyncio
async def test_success_flow_updates_file_metadata(mock_google_drive_service):
    """
    Test success flow updates file metadata with transaction_id.

    Verifies:
    - update_file_metadata called for each file
    - Metadata includes transaction_id, status='processing', payment_date
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_metadata_001",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        transaction_id = data["data"]["transaction_id"]

        # Verify update_file_metadata was called
        mock_google_drive_service.update_file_metadata.assert_called_once()

        # Verify metadata includes transaction_id
        call_args = mock_google_drive_service.update_file_metadata.call_args
        assert call_args[1]["file_id"] == "test-file-id-001"
        metadata = call_args[1]["metadata"]
        assert metadata["transaction_id"] == transaction_id
        assert metadata["status"] == "processing"
        assert "payment_date" in metadata


@pytest.mark.asyncio
async def test_success_flow_moves_files_to_inbox(mock_google_drive_service):
    """
    Test success flow moves files from Temp to Inbox.

    Verifies:
    - move_files_to_inbox_on_payment_success called with correct params
    - Files moved successfully
    - Response includes files_moved count
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_move_001",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify move_files_to_inbox_on_payment_success was called
        mock_google_drive_service.move_files_to_inbox_on_payment_success.assert_called_once()

        call_args = mock_google_drive_service.move_files_to_inbox_on_payment_success.call_args
        assert call_args[1]["customer_email"] == "test@example.com"
        assert call_args[1]["file_ids"] == ["test-file-id-001"]
        assert call_args[1]["company_name"] is None  # Individual user

        # Verify response
        assert data["data"]["files_moved"] == 1
        assert data["data"]["files_processed"] == 1


@pytest.mark.asyncio
async def test_success_flow_response_structure(mock_google_drive_service):
    """
    Test success flow returns correct response structure.

    Verifies:
    - success: True
    - message contains confirmation text
    - data contains transaction_id, square_transaction_id, files_processed, files_moved, total_price, status
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_response_001",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert isinstance(data["success"], bool), "success must be boolean"
        assert "Payment confirmed" in data["message"]

        # Verify data object
        assert "data" in data
        assert isinstance(data["data"]["transaction_id"], str)
        assert data["data"]["transaction_id"].startswith("TXN-")
        assert data["data"]["square_transaction_id"] == "TEST-sqt_response_001"
        assert isinstance(data["data"]["files_processed"], int)
        assert isinstance(data["data"]["files_moved"], int)
        assert isinstance(data["data"]["total_price"], float)
        assert data["data"]["status"] == "processing"


@pytest.mark.asyncio
async def test_success_flow_multiple_files(mock_google_drive_service):
    """
    Test success flow with multiple files.

    Verifies:
    - All files processed
    - Metadata updated for all files
    - All files moved to Inbox
    """
    # Mock multiple files
    mock_google_drive_service.find_files_by_customer_email.return_value = [
        {
            "file_id": "file-001",
            "filename": "doc1.pdf",
            "size": 100000,
            "google_drive_url": "https://docs.google.com/document/d/file-001/edit",
            "metadata": {
                "customer_email": "test@example.com",
                "status": "awaiting_payment",
                "source_language": "en",
                "target_language": "es",
                "total_units": 5,
                "total_price": 0.05
            }
        },
        {
            "file_id": "file-002",
            "filename": "doc2.pdf",
            "size": 200000,
            "google_drive_url": "https://docs.google.com/document/d/file-002/edit",
            "metadata": {
                "customer_email": "test@example.com",
                "status": "awaiting_payment",
                "source_language": "en",
                "target_language": "es",
                "total_units": 5,
                "total_price": 0.05
            }
        }
    ]

    mock_google_drive_service.move_files_to_inbox_on_payment_success.return_value = {
        "inbox_folder_id": "inbox-folder-123",
        "total_files": 2,
        "moved_successfully": 2,
        "moved_files": [
            {"file_id": "file-001", "filename": "doc1.pdf"},
            {"file_id": "file-002", "filename": "doc2.pdf"}
        ],
        "failed_moves": []
    }

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_multi_001",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all files processed
        assert data["data"]["files_processed"] == 2
        assert data["data"]["files_moved"] == 2

        # Verify metadata updated twice
        assert mock_google_drive_service.update_file_metadata.call_count == 2


# ============================================================================
# Failure Flow Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_failure_flow_no_transaction_created(mock_google_drive_service):
    """
    Test failure flow does NOT create transaction.

    Verifies:
    - No transaction created in database
    - Files deleted instead
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify no transaction created
        assert "transaction_id" not in data.get("data", {})

        # Verify no transactions with this square_transaction_id
        txn = await database.user_transactions.find_one({"square_transaction_id": "NONE"})
        assert txn is None, "No transaction should be created for failed payment"


@pytest.mark.asyncio
async def test_failure_flow_deletes_files(mock_google_drive_service):
    """
    Test failure flow deletes files from Temp folder.

    Verifies:
    - delete_file called for each file
    - Response includes files_deleted count
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify delete_file was called
        mock_google_drive_service.delete_file.assert_called_once_with("test-file-id-001")

        # Verify response
        assert data["data"]["files_deleted"] == 1


@pytest.mark.asyncio
async def test_failure_flow_response_structure(mock_google_drive_service):
    """
    Test failure flow returns correct response structure.

    Verifies:
    - success: False
    - message contains failure text
    - data contains square_transaction_id and files_deleted
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is False
        assert isinstance(data["success"], bool), "success must be boolean"
        assert "Payment failed" in data["message"]

        # Verify data object
        assert "data" in data
        assert data["data"]["square_transaction_id"] == "NONE"
        assert isinstance(data["data"]["files_deleted"], int)


@pytest.mark.asyncio
async def test_failure_flow_multiple_files(mock_google_drive_service):
    """
    Test failure flow with multiple files - all should be deleted.

    Verifies:
    - delete_file called for each file
    - All files deleted
    """
    # Mock multiple files
    mock_google_drive_service.find_files_by_customer_email.return_value = [
        {
            "file_id": "file-001",
            "filename": "doc1.pdf",
            "size": 100000,
            "google_drive_url": "https://docs.google.com/document/d/file-001/edit",
            "metadata": {"customer_email": "test@example.com", "status": "awaiting_payment"}
        },
        {
            "file_id": "file-002",
            "filename": "doc2.pdf",
            "size": 200000,
            "google_drive_url": "https://docs.google.com/document/d/file-002/edit",
            "metadata": {"customer_email": "test@example.com", "status": "awaiting_payment"}
        },
        {
            "file_id": "file-003",
            "filename": "doc3.pdf",
            "size": 300000,
            "google_drive_url": "https://docs.google.com/document/d/file-003/edit",
            "metadata": {"customer_email": "test@example.com", "status": "awaiting_payment"}
        }
    ]

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all files deleted
        assert data["data"]["files_deleted"] == 3
        assert mock_google_drive_service.delete_file.call_count == 3


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_no_files_found_in_temp_for_success_flow(mock_google_drive_service):
    """
    Test success flow when no files found in Temp folder (404 error expected).

    Should return 404 with appropriate error message.
    """
    # Mock empty file list
    mock_google_drive_service.find_files_by_customer_email.return_value = []

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_no_files",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"

        data = response.json()
        # Check both possible error formats
        if "detail" in data:
            assert "No files found" in data["detail"]
        elif "error" in data:
            assert "No files found" in data["error"]["message"]


@pytest.mark.asyncio
async def test_no_files_found_in_temp_for_failure_flow(mock_google_drive_service):
    """
    Test failure flow when no files found in Temp folder (graceful handling).

    Should return 200 with files_deleted=0.
    """
    # Mock empty file list
    mock_google_drive_service.find_files_by_customer_email.return_value = []

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should succeed but with 0 files deleted
        assert data["success"] is False
        assert data["data"]["files_deleted"] == 0
        assert "No files found" in data["message"]


@pytest.mark.asyncio
async def test_empty_files_list(mock_google_drive_service):
    """
    Test graceful handling when find_files_by_customer_email returns empty list.

    Same as test_no_files_found_in_temp_for_success_flow but explicit.
    """
    mock_google_drive_service.find_files_by_customer_email.return_value = []

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_empty",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 404


@pytest.mark.asyncio
async def test_google_drive_service_error_on_find_files(mock_google_drive_service):
    """
    Test proper error response when Google Drive service errors during file search.

    Should return 500 with error details.
    """
    # Mock Google Drive error
    mock_google_drive_service.find_files_by_customer_email.side_effect = Exception("Google Drive API error")

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_gd_error",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 500, f"Expected 500, got {response.status_code}: {response.text}"

        data = response.json()
        # Check both possible error formats
        if "detail" in data:
            assert "Failed to process payment confirmation" in data["detail"]
        elif "error" in data:
            assert "Failed to process payment confirmation" in data["error"]["message"]


@pytest.mark.asyncio
async def test_google_drive_service_error_on_move_files(mock_google_drive_service):
    """
    Test proper error response when Google Drive service errors during file move.

    Should return 500 with error details.
    """
    # Mock Google Drive error on move
    mock_google_drive_service.move_files_to_inbox_on_payment_success.side_effect = Exception("Move failed")

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_move_error",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 500
        data = response.json()
        # Check both possible error formats
        if "detail" in data:
            assert "Failed to process payment confirmation" in data["detail"]
        elif "error" in data:
            assert "Failed to process payment confirmation" in data["error"]["message"]


@pytest.mark.asyncio
async def test_google_drive_service_error_on_delete(mock_google_drive_service):
    """
    Test graceful handling when Google Drive service errors during file deletion.

    Should still return 200 but with partial deletion count.
    """
    # Mock multiple files with delete failure on second file
    mock_google_drive_service.find_files_by_customer_email.return_value = [
        {
            "file_id": "file-001",
            "filename": "doc1.pdf",
            "size": 100000,
            "google_drive_url": "https://docs.google.com/document/d/file-001/edit",
            "metadata": {"customer_email": "test@example.com", "status": "awaiting_payment"}
        },
        {
            "file_id": "file-002",
            "filename": "doc2.pdf",
            "size": 200000,
            "google_drive_url": "https://docs.google.com/document/d/file-002/edit",
            "metadata": {"customer_email": "test@example.com", "status": "awaiting_payment"}
        }
    ]

    # Mock delete to succeed first time, fail second time
    mock_google_drive_service.delete_file.side_effect = [None, Exception("Delete failed")]

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should report partial success (1 deleted, 1 failed)
        assert data["data"]["files_deleted"] == 1


@pytest.mark.asyncio
async def test_file_missing_file_id(mock_google_drive_service):
    """
    Test graceful handling when file object missing file_id.

    Should skip the file and continue processing others.
    """
    # Mock files with one missing file_id
    mock_google_drive_service.find_files_by_customer_email.return_value = [
        {
            "file_id": "file-001",
            "filename": "doc1.pdf",
            "size": 100000,
            "google_drive_url": "https://docs.google.com/document/d/file-001/edit",
            "metadata": {
                "customer_email": "test@example.com",
                "status": "awaiting_payment",
                "source_language": "en",
                "target_language": "es",
                "total_units": 5,
                "total_price": 0.05
            }
        },
        {
            # Missing file_id
            "filename": "doc2.pdf",
            "size": 200000,
            "google_drive_url": "https://docs.google.com/document/d/file-002/edit",
            "metadata": {
                "customer_email": "test@example.com",
                "status": "awaiting_payment",
                "source_language": "en",
                "target_language": "es",
                "total_units": 5,
                "total_price": 0.05
            }
        }
    ]

    mock_google_drive_service.move_files_to_inbox_on_payment_success.return_value = {
        "inbox_folder_id": "inbox-folder-123",
        "total_files": 1,
        "moved_successfully": 1,
        "moved_files": [{"file_id": "file-001", "filename": "doc1.pdf"}],
        "failed_moves": []
    }

    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_missing_id",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should process 2 files but only move 1 (one missing file_id)
        assert data["data"]["files_processed"] == 2
        assert data["data"]["files_moved"] == 1


@pytest.mark.asyncio
async def test_authentication_required(mock_google_drive_service):
    """
    Test that authentication is required (no Authorization header).

    Should return 401 or 403 (depending on auth implementation).
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        # No Authorization header
        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_auth",
                "status": True
            }
        )

        # Expect authentication error (401 or 403)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


# ============================================================================
# Transaction Database Validation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_transaction_has_correct_square_transaction_id(mock_google_drive_service):
    """
    Test transaction created with correct square_transaction_id.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_check_id_123",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        transaction_id = data["data"]["transaction_id"]

        # Verify square_transaction_id in database
        txn = await database.user_transactions.find_one({"transaction_id": transaction_id})
        assert txn["square_transaction_id"] == "TEST-sqt_check_id_123"


@pytest.mark.asyncio
async def test_transaction_id_is_string(mock_google_drive_service):
    """
    Test that transaction_id is returned as string (not other type).
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_type_check",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify transaction_id is string
        assert isinstance(data["data"]["transaction_id"], str)
        assert data["data"]["transaction_id"].startswith("TXN-")


@pytest.mark.asyncio
async def test_status_is_boolean_in_response(mock_google_drive_service):
    """
    Test that status field in response data is correct type.

    Note: The 'status' field in response is actually a string ('processing'),
    but the input status should be boolean.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_status_type",
                "status": True  # Boolean input
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()

        # success field should be boolean
        assert isinstance(data["success"], bool)
        # status field in data is string ('processing')
        assert isinstance(data["data"]["status"], str)
        assert data["data"]["status"] == "processing"


@pytest.mark.asyncio
async def test_transaction_documents_array_created(mock_google_drive_service):
    """
    Test that transaction has documents array with file information.
    """
    async with AsyncClient(app=app, base_url="http://test", timeout=5.0) as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_documents",
                "status": True
            },
            headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        transaction_id = data["data"]["transaction_id"]

        # Verify documents array in database
        txn = await database.user_transactions.find_one({"transaction_id": transaction_id})
        assert "documents" in txn
        assert isinstance(txn["documents"], list)
        assert len(txn["documents"]) == 1

        # Verify document structure
        doc = txn["documents"][0]
        assert "file_name" in doc
        assert "file_size" in doc
        assert "original_url" in doc
        assert doc["status"] == "processing"
