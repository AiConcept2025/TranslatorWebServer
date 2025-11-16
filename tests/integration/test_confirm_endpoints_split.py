"""
Integration tests for split transaction confirm endpoints.

Tests comprehensive validation, success flow, failure flow, and edge cases for:
- /api/transactions/confirm-enterprise (Enterprise flow - no file search)
- /api/transactions/confirm-individual (Individual flow with payment - no file search)

Reference Implementation: app/main.py lines 1742-2119
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
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


@pytest.fixture
async def mock_google_drive_service():
    """
    Mock Google Drive service for all file operations.

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


@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Cleanup test data after each test."""
    yield
    # Clean up test transactions (only those with TEST- prefix)
    try:
        if database.translation_transactions is not None:
            await database.translation_transactions.delete_many({
                "transaction_id": {"$regex": "^TXN-TEST-"}
            })
        if database.user_transactions is not None:
            await database.user_transactions.delete_many({
                "transaction_id": {"$regex": "^TXN-TEST-"}
            })
    except Exception as e:
        # Ignore cleanup errors (database might not be connected in some tests)
        pass


# ============================================================================
# Enterprise Confirm Tests
# ============================================================================

@pytest.mark.asyncio
async def test_enterprise_confirm_success(mock_google_drive_service):
    """
    ✅ Enterprise confirm success flow.

    Setup: Create Enterprise user with company_name, upload files, create transaction
    Call: POST /api/transactions/confirm-enterprise with transaction_id, status=true
    Assert:
    - HTTP 200
    - Transaction status updated to 'processing'
    - Files moved from Temp to Inbox
    - Response contains: moved_files, total_files, company_name
    - NO file search occurred
    """
    # Setup: Create Enterprise transaction
    transaction_id = "TXN-TEST-ENT-001"
    company_name = "Acme Corp"
    customer_email = "enterprise@acme.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": customer_email,  # Production uses user_id field to store email
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

    await database.translation_transactions.insert_one(transaction_doc)

    # Mock auth to return Enterprise user
    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": customer_email,
            "sub": "enterprise-user-id",
            "user_name": "Enterprise User",
            "company_name": company_name
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-enterprise",
                json={
                    "transaction_id": transaction_id,
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Enterprise transaction confirmed successfully"
            assert data["data"]["transaction_id"] == transaction_id
            assert data["data"]["moved_files"] == 1
            assert data["data"]["total_files"] == 1
            assert data["data"]["company_name"] == company_name

            # Verify transaction status updated
            txn = await database.translation_transactions.find_one({"transaction_id": transaction_id})
            assert txn["status"] == "processing"

            # Verify files moved (mock called)
            mock_google_drive_service.move_files_to_inbox_on_payment_success.assert_called_once()
            call_args = mock_google_drive_service.move_files_to_inbox_on_payment_success.call_args
            assert call_args[1]["customer_email"] == customer_email
            assert call_args[1]["file_ids"] == ["file-001"]
            assert call_args[1]["company_name"] == company_name


@pytest.mark.asyncio
async def test_enterprise_confirm_cancel(mock_google_drive_service):
    """
    ✅ Enterprise cancel flow.

    Setup: Create Enterprise transaction
    Call: POST /api/transactions/confirm-enterprise with status=false
    Assert:
    - HTTP 200
    - Transaction status updated to 'cancelled'
    - Files deleted from Temp
    - Response contains: deleted_files, total_files
    """
    transaction_id = "TXN-TEST-ENT-002"
    company_name = "Acme Corp"
    customer_email = "enterprise@acme.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": customer_email,  # Production uses user_id field to store email
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

    await database.translation_transactions.insert_one(transaction_doc)

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": customer_email,
            "company_name": company_name
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-enterprise",
                json={
                    "transaction_id": transaction_id,
                    "status": False
                },
                headers=headers
            )

            assert response.status_code == 200

            data = response.json()
            assert data["success"] is True
            assert "cancelled" in data["message"]
            assert data["data"]["deleted_files"] == 1
            assert data["data"]["total_files"] == 1

            # Verify transaction status updated
            txn = await database.translation_transactions.find_one({"transaction_id": transaction_id})
            assert txn["status"] == "cancelled"

            # Verify delete_file called
            mock_google_drive_service.delete_file.assert_called_once_with("file-001")


@pytest.mark.asyncio
async def test_enterprise_wrong_company_403(mock_google_drive_service):
    """
    ❌ Enterprise user tries to confirm another company's transaction (403 Forbidden).
    """
    transaction_id = "TXN-TEST-ENT-003"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "user@companyA.com",  # Production uses user_id field
        "company_name": "Company A",
        "status": "awaiting_confirmation",
        "created_at": datetime.now(timezone.utc),
        "documents": [{"file_id": "file-001"}]
    }

    await database.translation_transactions.insert_one(transaction_doc)

    # User from Company B trying to access Company A's transaction
    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "user@companyB.com",
            "company_name": "Company B"
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-enterprise",
                json={
                    "transaction_id": transaction_id,
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 403
            data = response.json()
            error_message = data.get("detail") or data.get("error", {}).get("message", "")
            assert "does not belong to your company" in error_message


@pytest.mark.asyncio
async def test_enterprise_missing_transaction_404(mock_google_drive_service):
    """
    ❌ Enterprise confirm with non-existent transaction_id (404 Not Found).
    """
    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "enterprise@acme.com",
            "company_name": "Acme Corp"
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-enterprise",
                json={
                    "transaction_id": "TXN-NONEXISTENT",
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 404
            data = response.json()
            error_message = data.get("detail") or data.get("error", {}).get("message", "")
            assert "not found" in error_message


@pytest.mark.asyncio
async def test_enterprise_individual_user_403(mock_google_drive_service):
    """
    ❌ Individual user (no company_name) tries to use Enterprise endpoint (403 Forbidden).
    """
    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "individual@example.com",        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-enterprise",
                json={
                    "transaction_id": "TXN-TEST-001",
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 403
            data = response.json()
            error_message = data.get("detail") or data.get("error", {}).get("message", "")
            assert "only for Enterprise users" in error_message


# ============================================================================
# Individual Confirm Tests
# ============================================================================

@pytest.mark.asyncio
async def test_individual_confirm_success(mock_google_drive_service):
    """
    ✅ Individual confirm success flow with payment.

    Setup: Create Individual user (no company), upload files, create transaction
    Call: POST /api/transactions/confirm-individual with transaction_id, square_transaction_id, file_ids
    Assert:
    - HTTP 200
    - Transaction status updated to 'completed'
    - square_transaction_id stored in transaction
    - Files moved from Temp to Inbox
    - Response contains: transaction_id, square_transaction_id, moved_files, total_files
    - NO file search occurred
    """
    transaction_id = "TXN-TEST-IND-001"
    user_email = "individual@example.com"
    square_txn_id = "sqt_test_123456"

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

    await database.user_transactions.insert_one(transaction_doc)

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": user_email,        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-individual",
                json={
                    "transaction_id": transaction_id,
                    "square_transaction_id": square_txn_id,
                    "file_ids": ["file-ind-001"],
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Individual transaction confirmed successfully"
            assert data["data"]["transaction_id"] == transaction_id
            assert data["data"]["square_transaction_id"] == square_txn_id
            assert data["data"]["moved_files"] == 1
            assert data["data"]["total_files"] == 1

            # Verify transaction updated
            txn = await database.user_transactions.find_one({"transaction_id": transaction_id})
            assert txn["status"] == "completed"
            assert txn["square_transaction_id"] == square_txn_id

            # Verify files moved
            mock_google_drive_service.move_files_to_inbox_on_payment_success.assert_called_once()
            call_args = mock_google_drive_service.move_files_to_inbox_on_payment_success.call_args
            assert call_args[1]["customer_email"] == user_email
            assert call_args[1]["file_ids"] == ["file-ind-001"]

@pytest.mark.asyncio
async def test_individual_confirm_cancel(mock_google_drive_service):
    """
    ✅ Individual cancel flow.

    Call: POST /api/transactions/confirm-individual with status=false
    Assert:
    - HTTP 200
    - Transaction status updated to 'cancelled'
    - Files deleted from Temp
    """
    transaction_id = "TXN-TEST-IND-002"
    user_email = "individual@example.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "status": "started",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await database.user_transactions.insert_one(transaction_doc)

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": user_email, }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-individual",
                json={
                    "transaction_id": transaction_id,
                    "file_ids": ["file-ind-001"],
                    "status": False
                },
                headers=headers
            )

            assert response.status_code == 200

            data = response.json()
            assert data["success"] is True
            assert "cancelled" in data["message"]
            assert data["data"]["deleted_files"] == 1

            # Verify transaction status
            txn = await database.user_transactions.find_one({"transaction_id": transaction_id})
            assert txn["status"] == "cancelled"


@pytest.mark.asyncio
async def test_individual_wrong_user_403(mock_google_drive_service):
    """
    ❌ Individual user tries to confirm another user's transaction (403 Forbidden).
    """
    transaction_id = "TXN-TEST-IND-003"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": "userA@example.com",
        "status": "started",
        "created_at": datetime.now(timezone.utc)
    }

    await database.user_transactions.insert_one(transaction_doc)

    # User B trying to access User A's transaction
    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "userB@example.com", }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-individual",
                json={
                    "transaction_id": transaction_id,
                    "file_ids": ["file-001"],
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 403
            data = response.json()
            error_message = data.get("detail") or data.get("error", {}).get("message", "")
            assert "does not belong to your account" in error_message


@pytest.mark.asyncio
async def test_individual_missing_file_ids_400(mock_google_drive_service):
    """
    ❌ Individual confirm without file_ids (400 Bad Request).
    """
    transaction_id = "TXN-TEST-IND-004"
    user_email = "individual@example.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "status": "started",
        "created_at": datetime.now(timezone.utc)
    }

    await database.user_transactions.insert_one(transaction_doc)

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": user_email, }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            # Missing file_ids
            response = await client.post(
                "/api/transactions/confirm-individual",
                json={
                    "transaction_id": transaction_id,
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 422  # Pydantic validation error


@pytest.mark.asyncio
async def test_individual_empty_file_ids_400(mock_google_drive_service):
    """
    ❌ Individual confirm with empty file_ids array (400 Bad Request).
    """
    transaction_id = "TXN-TEST-IND-005"
    user_email = "individual@example.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "status": "started",
        "created_at": datetime.now(timezone.utc)
    }

    await database.user_transactions.insert_one(transaction_doc)

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": user_email, }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-individual",
                json={
                    "transaction_id": transaction_id,
                    "file_ids": [],  # Empty array
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 400
            data = response.json()
            error_message = data.get("detail") or data.get("error", {}).get("message", "")
            assert "file_ids are required" in error_message


@pytest.mark.asyncio
async def test_individual_enterprise_user_403(mock_google_drive_service):
    """
    ❌ Enterprise user (has company_name) tries to use Individual endpoint (403 Forbidden).
    """
    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "enterprise@acme.com",
            "company_name": "Acme Corp"  # Enterprise user
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-individual",
                json={
                    "transaction_id": "TXN-TEST-001",
                    "file_ids": ["file-001"],
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 403
            data = response.json()
            error_message = data.get("detail") or data.get("error", {}).get("message", "")
            assert "only for Individual users" in error_message


# ============================================================================
# No File Search Verification Tests
# ============================================================================

@pytest.mark.asyncio
async def test_enterprise_no_file_search_called(mock_google_drive_service):
    """
    ✅ Verify Enterprise endpoint does NOT call find_files_by_customer_email.

    File IDs come from transaction.documents, NOT from Google Drive search.
    """
    transaction_id = "TXN-TEST-ENT-SEARCH"
    company_name = "Acme Corp"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "enterprise@acme.com",  # Production uses user_id field
        "company_name": company_name,
        "status": "awaiting_confirmation",
        "created_at": datetime.now(timezone.utc),
        "documents": [{"file_id": "file-001"}]
    }

    await database.translation_transactions.insert_one(transaction_doc)

    # Add find_files_by_customer_email mock to verify it's NOT called
    mock_google_drive_service.find_files_by_customer_email = AsyncMock()

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "enterprise@acme.com",
            "company_name": company_name
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            await client.post(
                "/api/transactions/confirm-enterprise",
                json={
                    "transaction_id": transaction_id,
                    "status": True
                },
                headers=headers
            )

            # ✅ CRITICAL: Verify NO file search occurred
            mock_google_drive_service.find_files_by_customer_email.assert_not_called()


@pytest.mark.asyncio
async def test_individual_no_file_search_called(mock_google_drive_service):
    """
    ✅ Verify Individual endpoint does NOT call find_files_by_customer_email.

    File IDs come from request body, NOT from Google Drive search.
    """
    transaction_id = "TXN-TEST-IND-SEARCH"
    user_email = "individual@example.com"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_email": user_email,
        "status": "started",
        "created_at": datetime.now(timezone.utc)
    }

    await database.user_transactions.insert_one(transaction_doc)

    # Add find_files_by_customer_email mock to verify it's NOT called
    mock_google_drive_service.find_files_by_customer_email = AsyncMock()

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": user_email, }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            await client.post(
                "/api/transactions/confirm-individual",
                json={
                    "transaction_id": transaction_id,
                    "file_ids": ["file-001", "file-002"],
                    "status": True
                },
                headers=headers
            )

            # ✅ CRITICAL: Verify NO file search occurred
            mock_google_drive_service.find_files_by_customer_email.assert_not_called()


# ============================================================================
# Edge Cases
# ============================================================================

@pytest.mark.asyncio
async def test_enterprise_no_documents_in_transaction_400(mock_google_drive_service):
    """
    ❌ Enterprise transaction with no documents array (400 Bad Request).
    """
    transaction_id = "TXN-TEST-ENT-NODOCS"
    company_name = "Acme Corp"

    transaction_doc = {
        "transaction_id": transaction_id,
        "company_name": company_name,
        "status": "awaiting_confirmation",
        "created_at": datetime.now(timezone.utc)
        # Missing 'documents' field
    }

    await database.translation_transactions.insert_one(transaction_doc)

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "enterprise@acme.com",
            "company_name": company_name
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-enterprise",
                json={
                    "transaction_id": transaction_id,
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 400
            data = response.json()
            error_message = data.get("detail") or data.get("error", {}).get("message", "")
            assert "no documents" in error_message


@pytest.mark.asyncio
async def test_individual_authentication_required(mock_google_drive_service):
    """
    ❌ Test that authentication is required (no Authorization header).

    Should return 401 or 403.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No Authorization header
        response = await client.post(
            "/api/transactions/confirm-individual",
            json={
                "transaction_id": "TXN-TEST-001",
                "file_ids": ["file-001"],
                "status": True
            }
        )

        assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_enterprise_multiple_files(mock_google_drive_service):
    """
    ✅ Enterprise confirm with multiple files.

    Verifies all files are processed correctly.
    """
    transaction_id = "TXN-TEST-ENT-MULTI"
    company_name = "Acme Corp"

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "enterprise@acme.com",  # Production uses user_id field
        "company_name": company_name,
        "status": "awaiting_confirmation",
        "created_at": datetime.now(timezone.utc),
        "documents": [
            {"file_id": "file-001", "file_name": "doc1.pdf"},
            {"file_id": "file-002", "file_name": "doc2.pdf"},
            {"file_id": "file-003", "file_name": "doc3.pdf"}
        ]
    }

    await database.translation_transactions.insert_one(transaction_doc)

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

    with patch("app.services.auth_service.auth_service.verify_session") as mock_verify:
        mock_verify.return_value = {
            "email": "enterprise@acme.com",
            "company_name": company_name
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm-enterprise",
                json={
                    "transaction_id": transaction_id,
                    "status": True
                },
                headers=headers
            )

            assert response.status_code == 200

            data = response.json()
            assert data["data"]["moved_files"] == 3
            assert data["data"]["total_files"] == 3

            # Verify metadata updated for all files
            assert mock_google_drive_service.update_file_metadata.call_count == 3
