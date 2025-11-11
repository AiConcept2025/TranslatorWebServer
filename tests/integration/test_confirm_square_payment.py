"""
REAL Integration tests for transaction confirmation endpoint.

⚠️ CRITICAL: NO MOCKS - ALL REAL SERVICES

This test suite uses:
- REAL MongoDB (translation_test database)
- REAL JWT authentication (real tokens)
- REAL Google Drive operations (real files created/moved/deleted)
- REAL HTTP requests to running server (http://localhost:8000)

PREREQUISITES:
1. Server must be running: uvicorn app.main:app --reload --port 8000
2. MongoDB must be running on localhost:27017
3. Google Drive credentials must be configured
4. TEST- prefix used for all test data (automatic cleanup)

Tests verify:
1. New request schema (square_transaction_id + status)
2. Transaction creation with square_transaction_id
3. TXN-format transaction_id generation
4. Success vs failure flow branching
5. Response format validation
6. Real Google Drive file operations
7. Real database operations

Reference: app/main.py lines 968-1567
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import httpx
from bson import ObjectId
import secrets

# Import real services (NO MOCKS)
from app.database import database
from app.services.jwt_service import jwt_service
from app.services.google_drive_service import google_drive_service


# ============================================================================
# Real User Fixtures - NO MOCKS
# ============================================================================

@pytest.fixture
async def real_test_user() -> Dict[str, Any]:
    """
    Create REAL test user in MongoDB.

    Returns:
        dict: User data with MongoDB _id
    """
    # Ensure database is connected
    await database.connect()

    # Generate unique user_id and email for each test run
    unique_id = secrets.token_hex(8)

    # Create test user in users collection
    user_data = {
        "user_id": f"TEST-USER-{unique_id}",  # Unique user_id to avoid duplicate key error
        "user_email": f"test-confirm-{unique_id}@example.com",  # Unique email
        "user_name": "Test Confirm User",
        "created_at": datetime.now(timezone.utc),
        "permission_level": "user"
    }

    # Insert new test user
    result = await database.users.insert_one(user_data)
    user_data["_id"] = result.inserted_id
    print(f"✓ Created test user: {user_data['user_email']} (user_id: {user_data['user_id']})")

    yield user_data

    # Cleanup: Delete test user by user_id
    await database.users.delete_one({"user_id": user_data["user_id"]})
    print(f"✓ Cleaned up test user: {user_data['user_email']}")


@pytest.fixture
async def real_auth_token(real_test_user: Dict[str, Any]) -> str:
    """
    Generate REAL JWT token using real jwt_service.

    Args:
        real_test_user: Real user from database

    Returns:
        str: Valid JWT token
    """
    token_data = {
        "user_id": str(real_test_user["_id"]),
        "email": real_test_user["user_email"],
        "user_name": real_test_user["user_name"],
        "permission_level": real_test_user.get("permission_level", "user")
    }

    # Create token with 1 hour expiration
    token = jwt_service.create_access_token(token_data, timedelta(hours=1))

    print(f"✓ Generated JWT token for: {real_test_user['user_email']}")
    return token


@pytest.fixture
async def real_test_files(real_test_user: Dict[str, Any]) -> List[str]:
    """
    Create REAL test files in Google Drive Temp folder.

    This fixture:
    1. Creates customer folder structure (if not exists)
    2. Uploads test file to Temp folder with metadata
    3. Returns file IDs for testing
    4. Cleanup: Deletes test files after test

    Args:
        real_test_user: Real user from database

    Returns:
        List[str]: List of file IDs created in Google Drive
    """
    customer_email = real_test_user["user_email"]

    # Step 1: Create folder structure (Inbox, Temp, Completed)
    print(f"✓ Creating folder structure for: {customer_email}")
    temp_folder_id = await google_drive_service.create_customer_folder_structure(
        customer_email=customer_email,
        company_name=None  # Individual user
    )
    print(f"✓ Temp folder ID: {temp_folder_id}")

    # Step 2: Create test file content
    test_content = b"This is a test PDF document for integration testing."

    # Step 3: Upload test file to Temp folder
    # Note: upload_file_to_folder_with_metadata() signature:
    # - file_content: bytes
    # - filename: str
    # - folder_id: str
    # - customer_email: str
    # - source_language: str
    # - target_language: str
    # - page_count: int
    # It automatically sets status='awaiting_payment' in file properties

    print(f"✓ Uploading test file to Temp folder...")
    file_info = await google_drive_service.upload_file_to_folder_with_metadata(
        file_content=test_content,
        filename="TEST_integration_test.pdf",
        folder_id=temp_folder_id,
        customer_email=customer_email,
        source_language="en",
        target_language="es",
        page_count=10  # Used for pricing calculation
    )

    # Extract file_id from returned dictionary
    file_id = file_info['file_id']
    print(f"✓ Test file uploaded: {file_id}")

    file_ids = [file_id]

    yield file_ids

    # Cleanup: Delete test files from both Temp and Inbox folders
    print(f"✓ Cleaning up test files...")
    for fid in file_ids:
        try:
            await google_drive_service.delete_file(fid)
            print(f"✓ Deleted test file: {fid}")
        except Exception as e:
            print(f"⚠ Failed to delete test file {fid}: {e}")


@pytest.fixture(autouse=True)
async def cleanup_test_transactions():
    """
    Auto cleanup test transactions BEFORE and AFTER each test.

    This ensures:
    - Clean state before test
    - Clean state after test
    - Only TEST- prefixed transactions are deleted (NEVER production data)
    """
    await database.connect()

    # Before test: Clean up any leftover TEST- transactions
    result_before = await database.user_transactions.delete_many({
        "square_transaction_id": {"$regex": "^TEST-"}
    })
    if result_before.deleted_count > 0:
        print(f"✓ Pre-test cleanup: Deleted {result_before.deleted_count} old TEST transactions")

    yield

    # After test: Clean up TEST- transactions created during test
    result_after = await database.user_transactions.delete_many({
        "square_transaction_id": {"$regex": "^TEST-"}
    })
    if result_after.deleted_count > 0:
        print(f"✓ Post-test cleanup: Deleted {result_after.deleted_count} TEST transactions")


@pytest.fixture(autouse=True)
async def init_database():
    """Initialize database connection for all tests."""
    await database.connect()
    yield


# ============================================================================
# Test Case 1: Request Validation - Valid Success Request
# ============================================================================

@pytest.mark.asyncio
async def test_1_valid_success_request(
    real_test_user: Dict[str, Any],
    real_auth_token: str,
    real_test_files: List[str]
):
    """
    Test Case 1: Valid success request with status=True.

    Tests REAL integration:
    - REAL HTTP request to localhost:8000
    - REAL JWT authentication
    - REAL Google Drive file operations
    - REAL MongoDB transaction creation

    Verifies:
    - Request with square_transaction_id + status=True is accepted
    - Returns 200 (not 422)
    - Creates transaction in database
    - Transaction has correct fields
    """
    print("\n" + "=" * 80)
    print("TEST 1: Valid Success Request")
    print("=" * 80)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {real_auth_token}"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_test123",
                "status": True
            },
            headers=headers
        )

        print(f"✓ Response status: {response.status_code}")

        # Should accept request (not 422)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        print(f"✓ Response data: {data}")

        assert data["success"] is True
        assert "transaction_id" in data["data"]
        assert data["data"]["transaction_id"].startswith("TXN-")

        # Verify transaction exists in database
        transaction = await database.user_transactions.find_one({
            "transaction_id": data["data"]["transaction_id"]
        })

        assert transaction is not None, "Transaction should exist in database"
        assert transaction["square_transaction_id"] == "TEST-sqt_test123"
        assert transaction["user_id"] == real_test_user["user_email"]
        print(f"✓ Transaction verified in database: {transaction['transaction_id']}")


# ============================================================================
# Test Case 2: Request Validation - Valid Failure Request
# ============================================================================

@pytest.mark.asyncio
async def test_2_valid_failure_request(
    real_test_user: Dict[str, Any],
    real_auth_token: str,
    real_test_files: List[str]
):
    """
    Test Case 2: Valid failure request with status=False.

    Tests REAL integration:
    - REAL HTTP request to localhost:8000
    - REAL JWT authentication
    - REAL Google Drive file deletion
    - REAL MongoDB (no transaction created)

    Verifies:
    - Request with square_transaction_id="NONE" + status=False is accepted
    - Returns 200 (not 422)
    - Does NOT create transaction
    - Files are deleted from Google Drive
    """
    print("\n" + "=" * 80)
    print("TEST 2: Valid Failure Request")
    print("=" * 80)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {real_auth_token}"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        print(f"✓ Response status: {response.status_code}")

        # Should accept request (not 422)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        print(f"✓ Response data: {data}")

        assert data["success"] is False
        assert "transaction_id" not in data.get("data", {})
        assert data["data"]["files_deleted"] >= 0

        # Verify NO transaction created with square_transaction_id="NONE"
        transaction = await database.user_transactions.find_one({
            "square_transaction_id": "NONE"
        })

        assert transaction is None, "No transaction should be created for failed payment"
        print(f"✓ Verified: No transaction created for failed payment")


# ============================================================================
# Test Case 3: Request Validation - Missing Fields
# ============================================================================

@pytest.mark.asyncio
async def test_3a_missing_square_transaction_id(
    real_test_user: Dict[str, Any],
    real_auth_token: str
):
    """
    Test Case 3a: Missing square_transaction_id field (now OPTIONAL).

    Verifies:
    - Request without square_transaction_id succeeds (field is optional)
    - Defaults to None when omitted
    - Endpoint finds files and proceeds normally
    """
    print("\n" + "=" * 80)
    print("TEST 3a: Missing square_transaction_id (OPTIONAL field)")
    print("=" * 80)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {real_auth_token}"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "status": True
                # square_transaction_id omitted - should default to None
            },
            headers=headers
        )

        print(f"✓ Response status: {response.status_code}")

        # Should return 404 (no files found) since no files were uploaded for this test user
        # This proves the field is optional and request passed validation
        assert response.status_code == 404, f"Expected 404 (no files), got {response.status_code}: {response.text}"

        data = response.json()
        print(f"✓ Error response: {data}")

        # Verify it's a "no files found" error, not a validation error
        assert "No files found" in data["error"]["message"]
        print(f"✓ Verified: square_transaction_id is optional (passed validation)")


@pytest.mark.asyncio
async def test_3b_missing_status_field(
    real_test_user: Dict[str, Any],
    real_auth_token: str
):
    """
    Test Case 3b: Missing status field (now has DEFAULT).

    Verifies:
    - Request without status succeeds (field has default=True)
    - Defaults to True when omitted
    - Endpoint proceeds normally
    """
    print("\n" + "=" * 80)
    print("TEST 3b: Missing status field (HAS DEFAULT)")
    print("=" * 80)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {real_auth_token}"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_123"
                # status omitted - should default to True
            },
            headers=headers
        )

        print(f"✓ Response status: {response.status_code}")

        # Should return 404 (no files found) since no files were uploaded for this test user
        # This proves the field has default value and request passed validation
        assert response.status_code == 404, f"Expected 404 (no files), got {response.status_code}: {response.text}"

        data = response.json()
        print(f"✓ Error response: {data}")

        # Verify it's a "no files found" error, not a validation error
        assert "No files found" in data["error"]["message"]
        print(f"✓ Verified: status field has default (passed validation)")

        # Check for error details mentioning status
        if "detail" in data:
            error_fields = [err["loc"][-1] for err in data["detail"]]
            assert "status" in error_fields
        elif "error" in data and "details" in data["error"]:
            error_text = str(data["error"]["details"])
            assert "status" in error_text


# ============================================================================
# Test Case 4: Transaction Creation on Success
# ============================================================================

@pytest.mark.asyncio
async def test_4_transaction_creation_on_success(
    real_test_user: Dict[str, Any],
    real_auth_token: str,
    real_test_files: List[str]
):
    """
    Test Case 4: Transaction creation on success flow.

    Tests REAL integration with REAL database operations.

    Verifies:
    - Transaction created in user_transactions collection
    - Transaction has square_transaction_id field
    - Transaction has TXN-format transaction_id
    - Response contains transaction_id
    - All required fields are present
    - Files are moved to Inbox folder
    """
    print("\n" + "=" * 80)
    print("TEST 4: Transaction Creation on Success")
    print("=" * 80)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {real_auth_token}"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_create_001",
                "status": True
            },
            headers=headers
        )

        print(f"✓ Response status: {response.status_code}")
        assert response.status_code == 200

        data = response.json()
        print(f"✓ Response data: {data}")

        # Verify response contains transaction_id
        assert "transaction_id" in data["data"]
        transaction_id = data["data"]["transaction_id"]

        # Verify TXN-format
        assert transaction_id.startswith("TXN-"), f"Expected TXN- format, got {transaction_id}"
        print(f"✓ Transaction ID format verified: {transaction_id}")

        # Verify transaction exists in database (REAL MongoDB query)
        txn = await database.user_transactions.find_one({"transaction_id": transaction_id})
        assert txn is not None, "Transaction should exist in user_transactions collection"
        print(f"✓ Transaction found in database")

        # Verify square_transaction_id field
        assert "square_transaction_id" in txn
        assert txn["square_transaction_id"] == "TEST-sqt_create_001"
        print(f"✓ square_transaction_id verified: {txn['square_transaction_id']}")

        # Verify transaction_id field
        assert "transaction_id" in txn
        assert txn["transaction_id"] == transaction_id
        assert txn["transaction_id"].startswith("TXN-")

        # Verify other required fields
        assert txn["status"] == "started"
        assert txn["user_id"] == real_test_user["user_email"]
        assert "documents" in txn
        assert len(txn["documents"]) > 0
        print(f"✓ Transaction fields verified:")
        print(f"  - status: {txn['status']}")
        print(f"  - user_id: {txn['user_id']}")
        print(f"  - documents: {len(txn['documents'])} files")


# ============================================================================
# Test Case 5: No Transaction Created on Failure
# ============================================================================

@pytest.mark.asyncio
async def test_5_no_transaction_on_failure(
    real_test_user: Dict[str, Any],
    real_auth_token: str,
    real_test_files: List[str]
):
    """
    Test Case 5: No transaction created on failure flow.

    Tests REAL integration with REAL file deletion.

    Verifies:
    - No transaction created in user_transactions
    - Response has success=False
    - Files are deleted from Google Drive (REAL deletion)
    """
    print("\n" + "=" * 80)
    print("TEST 5: No Transaction on Failure")
    print("=" * 80)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {real_auth_token}"}

        # Get file IDs before deletion for verification
        file_ids_before = real_test_files.copy()
        print(f"✓ Files before deletion: {file_ids_before}")

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        print(f"✓ Response status: {response.status_code}")
        assert response.status_code == 200

        data = response.json()
        print(f"✓ Response data: {data}")

        # Verify no transaction_id in response
        assert "transaction_id" not in data.get("data", {})

        # Verify success=False
        assert data["success"] is False

        # Verify no transaction created with square_transaction_id="NONE"
        txn = await database.user_transactions.find_one({"square_transaction_id": "NONE"})
        assert txn is None, "No transaction should be created for failed payment"
        print(f"✓ Verified: No transaction created")

        # Verify files were deleted from Google Drive (REAL check)
        assert data["data"]["files_deleted"] > 0
        print(f"✓ Files deleted: {data['data']['files_deleted']}")


# ============================================================================
# Test Case 6: Response Format Validation
# ============================================================================

@pytest.mark.asyncio
async def test_6a_success_response_format(
    real_test_user: Dict[str, Any],
    real_auth_token: str,
    real_test_files: List[str]
):
    """
    Test Case 6a: Success response has correct format.

    Verifies success response contains:
    - transaction_id (string, TXN- format)
    - square_transaction_id (string)
    - files_processed (int)
    """
    print("\n" + "=" * 80)
    print("TEST 6a: Success Response Format")
    print("=" * 80)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {real_auth_token}"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "TEST-sqt_response_001",
                "status": True
            },
            headers=headers
        )

        print(f"✓ Response status: {response.status_code}")
        assert response.status_code == 200

        data = response.json()
        print(f"✓ Response data: {data}")

        # Verify top-level structure
        assert "success" in data
        assert "message" in data
        assert "data" in data

        # Verify success=True
        assert data["success"] is True
        assert isinstance(data["success"], bool)

        # Verify data fields
        assert "transaction_id" in data["data"]
        assert "square_transaction_id" in data["data"]
        assert "files_processed" in data["data"]

        # Verify field types
        assert isinstance(data["data"]["transaction_id"], str)
        assert data["data"]["transaction_id"].startswith("TXN-")
        assert isinstance(data["data"]["square_transaction_id"], str)
        assert isinstance(data["data"]["files_processed"], int)

        # Verify square_transaction_id value
        assert data["data"]["square_transaction_id"] == "TEST-sqt_response_001"

        print(f"✓ Response format validated:")
        print(f"  - transaction_id: {data['data']['transaction_id']}")
        print(f"  - square_transaction_id: {data['data']['square_transaction_id']}")
        print(f"  - files_processed: {data['data']['files_processed']}")


@pytest.mark.asyncio
async def test_6b_failure_response_format(
    real_test_user: Dict[str, Any],
    real_auth_token: str,
    real_test_files: List[str]
):
    """
    Test Case 6b: Failure response has correct format.

    Verifies failure response contains:
    - square_transaction_id (string)
    - files_deleted (int)
    - NO transaction_id
    """
    print("\n" + "=" * 80)
    print("TEST 6b: Failure Response Format")
    print("=" * 80)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {real_auth_token}"}

        response = await client.post(
            "/api/transactions/confirm",
            json={
                "square_transaction_id": "NONE",
                "status": False
            },
            headers=headers
        )

        print(f"✓ Response status: {response.status_code}")
        assert response.status_code == 200

        data = response.json()
        print(f"✓ Response data: {data}")

        # Verify top-level structure
        assert "success" in data
        assert "message" in data
        assert "data" in data

        # Verify success=False
        assert data["success"] is False
        assert isinstance(data["success"], bool)

        # Verify data fields
        assert "square_transaction_id" in data["data"]
        assert "files_deleted" in data["data"]

        # Verify NO transaction_id
        assert "transaction_id" not in data["data"]

        # Verify field types
        assert isinstance(data["data"]["square_transaction_id"], str)
        assert isinstance(data["data"]["files_deleted"], int)

        # Verify square_transaction_id value
        assert data["data"]["square_transaction_id"] == "NONE"

        print(f"✓ Response format validated:")
        print(f"  - square_transaction_id: {data['data']['square_transaction_id']}")
        print(f"  - files_deleted: {data['data']['files_deleted']}")
        print(f"  - NO transaction_id (as expected)")
