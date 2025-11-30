"""
Pytest configuration for integration tests.

All tests use real HTTP requests to the server and output human-readable logs.
Uses the real test database (translation_test) for all integration tests.
"""

import pytest
import uuid
import httpx
from datetime import datetime, timezone
from typing import Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

# CRITICAL: Do NOT import database from app.database.mongodb here!
# That singleton uses settings.mongodb_database which points to PRODUCTION.
# All tests MUST use the test_db fixture instead.

from tests.test_logger import TestLogger, get_test_headers

# Test database configuration
TEST_MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation"
TEST_DATABASE_NAME = "translation_test"


# Cache for admin token to avoid recreating for each test
_admin_token_cache: Dict[str, str] = {}


# Configure pytest to use asyncio
def pytest_configure(config):
    """
    Configure pytest with custom settings.

    CRITICAL: Verify DATABASE_MODE is set to "test" before running tests.
    This prevents accidentally running tests against production database.
    """
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )

    # CRITICAL: Check database mode BEFORE running any tests
    from app.config import settings

    if not settings.is_test_mode():
        pytest.exit(
            f"\n\n"
            f"{'='*80}\n"
            f"FATAL ERROR: Tests cannot run in {settings.database_mode.upper()} mode!\n"
            f"{'='*80}\n\n"
            f"Current DATABASE_MODE: {settings.database_mode}\n"
            f"Current database: {settings.active_mongodb_database}\n\n"
            f"REQUIRED ACTION:\n"
            f"  1. Open your .env file: {settings.Config.env_file}\n"
            f"  2. Set: DATABASE_MODE=test\n"
            f"  3. Save and run pytest again\n\n"
            f"This safety check prevents accidentally running tests against production data.\n"
            f"{'='*80}\n",
            returncode=1
        )

    # Log successful database mode verification
    print(f"\n{'='*80}")
    print(f"Database Mode Verification: PASSED")
    print(f"  DATABASE_MODE: {settings.database_mode}")
    print(f"  Active Database: {settings.active_mongodb_database}")
    print(f"  Expected Database: {TEST_DATABASE_NAME}")
    print(f"{'='*80}\n")

    # Clear token caches at start of session
    global _admin_token_cache
    _admin_token_cache.clear()

    # Restore Golden Source database before running tests
    import subprocess
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).parent.parent / "scripts"
    restore_script = scripts_dir / "restore_test_db.py"

    if restore_script.exists():
        print(f"\n{'='*80}")
        print("Restoring Golden Source to translation_test...")
        print(f"{'='*80}")

        result = subprocess.run(
            [sys.executable, str(restore_script)],
            capture_output=True,
            text=True,
            cwd=str(scripts_dir.parent)
        )

        if result.returncode != 0:
            print(f"❌ Failed to restore Golden Source:")
            print(result.stderr)
            pytest.exit("Golden Source restoration failed", returncode=1)

        # Print summary (last few lines of output)
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines[-5:]:
            print(f"  {line}")

        print(f"{'='*80}\n")
    else:
        print(f"\n⚠️  Warning: restore_test_db.py not found at {restore_script}")
        print("    Tests will run against existing test database state.\n")


# ============================================================================
# Shared Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def admin_session_token():
    """
    Get a valid session token for testing using the real enterprise user.

    Uses the login API endpoint to get a token valid for the running server.

    Returns:
        dict: {"Authorization": "Bearer {token}"}
    """
    global _admin_token_cache

    # Return cached token if available
    if "token" in _admin_token_cache:
        return {"Authorization": f"Bearer {_admin_token_cache['token']}"}

    # Use the login endpoint to get a real token from the running server
    # This ensures the token is valid for the server's database state
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        login_response = await client.post(
            "/login/corporate",
            json={
                "companyName": "Iris Trading",
                "userEmail": "danishevsky@gmail.com",
                "password": "Sveta87201120!",
                "userFullName": "Manager User",  # Must match user_name in company_users Golden Source
                "loginDateTime": datetime.now(timezone.utc).isoformat()
            }
        )

        if login_response.status_code != 200:
            raise ValueError(f"Failed to login: {login_response.status_code} - {login_response.text}")

        login_data = login_response.json()
        # Token is in data.authToken for corporate login
        session_token = login_data.get("data", {}).get("authToken")

        if not session_token:
            raise ValueError(f"No authToken in login response: {login_data}")

        # Cache the token
        _admin_token_cache["token"] = session_token

        return {"Authorization": f"Bearer {session_token}"}


@pytest.fixture(scope="function")
async def admin_headers(admin_session_token):
    """
    Get admin authentication headers for a test.

    Uses the admin_session_token fixture.

    Returns:
        dict: {"Authorization": "Bearer {token}"}
    """
    return admin_session_token


@pytest.fixture(scope="function")
async def test_transaction_with_nested_docs(test_db):
    """
    Create test transaction with nested documents structure.

    Returns a complete transaction document matching the new nested structure.
    Automatically cleaned up after test.

    Structure:
    - transaction_id: TXN-TEST-{uuid}
    - documents: array with 1 document
    - All required transaction fields

    CRITICAL: Uses test_db fixture to ensure writes go to translation_test, NOT production.
    """
    collection = test_db.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "testuser@example.com",
        "source_language": "en",
        "target_language": "fr",
        "units_count": 15,
        "price_per_unit": 0.10,
        "total_price": 1.50,
        "status": "started",
        "error_message": "",
        "created_at": now,
        "updated_at": now,
        "unit_type": "page",

        # Nested documents array (NEW STRUCTURE)
        "documents": [
            {
                "file_name": "test_document.pdf",
                "file_size": 204800,
                "original_url": "https://docs.google.com/document/d/test123/edit",
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

    result = await collection.insert_one(transaction_doc)
    transaction_doc["_id"] = result.inserted_id

    yield transaction_doc

    # Cleanup
    await collection.delete_one({"transaction_id": transaction_id})


@pytest.fixture(scope="function")
async def sample_nested_transaction_data() -> Dict[str, Any]:
    """
    Sample nested transaction data for testing without database insertion.

    Returns a dict with complete transaction structure including nested documents.
    Useful for model validation tests that don't require database.

    NOTE: company_name is set to None (valid for individual users).
    For enterprise tests requiring valid company_name, use test_company fixture.
    """
    now = datetime.now(timezone.utc)

    return {
        "transaction_id": f"TXN-SAMPLE-{uuid.uuid4().hex[:8].upper()}",
        "user_id": "sample@example.com",
        "company_name": None,  # None is valid for individual users
        "source_language": "de",
        "target_language": "en",
        "units_count": 20,
        "price_per_unit": 0.12,
        "total_price": 2.40,
        "status": "confirmed",
        "error_message": "",
        "created_at": now,
        "updated_at": now,
        "unit_type": "word",

        "documents": [
            {
                "file_name": "sample_doc_1.pdf",
                "file_size": 150000,
                "original_url": "https://docs.google.com/document/d/sample1/edit",
                "translated_url": "https://docs.google.com/document/d/sample1_trans/edit",
                "translated_name": "sample_doc_1_en.pdf",
                "status": "completed",
                "uploaded_at": now,
                "translated_at": now,
                "processing_started_at": now,
                "processing_duration": 95.3
            },
            {
                "file_name": "sample_doc_2.docx",
                "file_size": 250000,
                "original_url": "https://docs.google.com/document/d/sample2/edit",
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


# ============================================================================
# Referential Integrity Fixtures (for database consistency)
# ============================================================================

@pytest.fixture(scope="function")
async def test_company(test_db):
    """
    Create a valid test company for referential integrity.

    Use this fixture whenever creating records that require a valid company_name
    reference (subscriptions, invoices, translation_transactions, etc.).

    Automatically cleaned up after test.
    """
    company_name = f"TEST-Company-{uuid.uuid4().hex[:8]}"
    company_data = {
        "company_name": company_name,
        "description": "Test company for integration tests",
        "address": {
            "street": "123 Test Street",
            "city": "Test City",
            "state": "TS",
            "zip": "12345",
            "country": "USA"
        },
        "contact_email": f"contact_{uuid.uuid4().hex[:6]}@testcompany.com",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.company.insert_one(company_data)
    yield company_data

    # Cleanup
    await test_db.company.delete_one({"company_name": company_name})


@pytest.fixture(scope="function")
async def test_user(test_db):
    """
    Create a valid test user in users_login for referential integrity.

    Use this fixture whenever creating payments or records that require
    a valid user_email reference.

    Automatically cleaned up after test.
    """
    user_email = f"test_{uuid.uuid4().hex[:8]}@test.com"
    user_data = {
        "user_email": user_email,
        "user_name": f"Test User {uuid.uuid4().hex[:4]}",
        "password": "hashed_test_password_12345",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "last_login": None
    }

    await test_db.users_login.insert_one(user_data)
    yield user_data

    # Cleanup
    await test_db.users_login.delete_one({"user_email": user_email})


@pytest.fixture(scope="function")
async def test_company_user(test_db, test_company):
    """
    Create a valid company user for referential integrity.

    Use this fixture whenever creating payments or records that require
    a valid user_email reference from a company user.

    Depends on test_company fixture.
    Automatically cleaned up after test.
    """
    user_email = f"company_user_{uuid.uuid4().hex[:8]}@test.com"
    user_data = {
        "email": user_email,
        "user_id": f"USER-{uuid.uuid4().hex[:8]}",
        "user_name": f"Test Company User {uuid.uuid4().hex[:4]}",
        "company_name": test_company["company_name"],
        "permission_level": "user",
        "status": "active",
        "password_hash": "hashed_test_password_12345",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "last_login": None
    }

    await test_db.company_users.insert_one(user_data)
    yield user_data

    # Cleanup
    await test_db.company_users.delete_one({"email": user_email})


# ============================================================================
# Real User Authentication Fixtures
# ============================================================================

# Cache for enterprise token
_enterprise_token_cache: Dict[str, str] = {}


@pytest.fixture(scope="function")
async def enterprise_auth_token(test_db):
    """
    Get authentication token for enterprise user (danishevsky@gmail.com).
    Uses real credentials for integration testing.

    CRITICAL: Uses test_db fixture to read from translation_test, NOT production.
    """
    global _enterprise_token_cache

    if "token" in _enterprise_token_cache:
        return {"Authorization": f"Bearer {_enterprise_token_cache['token']}"}

    from app.services.auth_service import auth_service

    # Find the company for this user from TEST database
    user = await test_db.company_users.find_one({"email": "danishevsky@gmail.com"})
    if not user:
        pytest.skip("Enterprise user danishevsky@gmail.com not found in database")

    company_name = user.get("company_name", "Iris Trading")
    user_name = user.get("user_name", "Vladimir Danishevsky")

    auth_result = await auth_service.authenticate_user(
        company_name=company_name,
        password="Sveta87201120!",
        user_name=user_name,
        email="danishevsky@gmail.com"
    )

    session_token = auth_result.get("session_token")
    if not session_token:
        pytest.skip("Failed to authenticate enterprise user")

    _enterprise_token_cache["token"] = session_token
    return {"Authorization": f"Bearer {session_token}"}


@pytest.fixture(scope="function")
async def enterprise_headers(enterprise_auth_token):
    """Get enterprise authentication headers for a test."""
    return enterprise_auth_token


# Cache for individual token
_individual_token_cache: Dict[str, str] = {}


@pytest.fixture(scope="function")
async def individual_auth_token(test_db):
    """
    Get authentication token for individual user (danishevsky@yahoo.com).
    Uses real credentials for integration testing.

    CRITICAL: Uses test_db fixture to read from translation_test, NOT production.
    """
    global _individual_token_cache

    if "token" in _individual_token_cache:
        return {"Authorization": f"Bearer {_individual_token_cache['token']}"}

    from app.services.auth_service import auth_service

    # Individual users may be in users_login collection - from TEST database
    user = await test_db.users_login.find_one({"email": "danishevsky@yahoo.com"})
    if not user:
        # Try company_users as fallback
        user = await test_db.company_users.find_one({"email": "danishevsky@yahoo.com"})

    if not user:
        pytest.skip("Individual user danishevsky@yahoo.com not found in database")

    # For individual users, authenticate differently
    try:
        auth_result = await auth_service.authenticate_user(
            company_name=user.get("company_name", ""),
            password="Sveta87201120!",
            user_name=user.get("user_name", "Vladimir Danishevsky"),
            email="danishevsky@yahoo.com"
        )

        session_token = auth_result.get("session_token")
        if not session_token:
            pytest.skip("Failed to authenticate individual user")

        _individual_token_cache["token"] = session_token
        return {"Authorization": f"Bearer {session_token}"}
    except Exception as e:
        pytest.skip(f"Individual user auth failed: {e}")


@pytest.fixture(scope="function")
async def individual_headers(individual_auth_token):
    """Get individual user authentication headers for a test."""
    return individual_auth_token


# ============================================================================
# Test Logging Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def test_logger(request) -> TestLogger:
    """
    Provides a TestLogger instance for the current test.

    The logger is pre-configured with the test function name.
    Use it to log test purpose, requests, responses, and results.

    Example:
        def test_my_feature(test_logger):
            test_logger.start("Verify user creation via POST /api/users")
            test_logger.request("POST", "/api/users", {"name": "test"})
            # ... test code ...
            test_logger.passed("User created with ID: 123")
    """
    return TestLogger(request.node.name)


@pytest.fixture(scope="function")
def test_headers(request) -> Dict[str, str]:
    """
    Provides HTTP headers that identify test requests in server logs.

    These headers are logged by the server, making it easy to trace
    which requests came from which tests.

    Example:
        async def test_my_feature(http_client, test_headers):
            response = await http_client.get("/api/resource", headers=test_headers)
    """
    return get_test_headers(request.node.name)


# ============================================================================
# Test Database Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def test_db() -> AsyncIOMotorDatabase:
    """
    Provide a connection to the test database (translation_test).

    CRITICAL: All integration tests MUST use this fixture to ensure they
    connect to translation_test, NOT the production database.

    The fixture provides proper async connection management and cleanup.

    Returns:
        AsyncIOMotorDatabase: Motor database instance for translation_test
    """
    mongo_client = AsyncIOMotorClient(TEST_MONGODB_URI, serverSelectionTimeoutMS=5000)
    test_database = mongo_client[TEST_DATABASE_NAME]

    # Verify connection
    try:
        await mongo_client.admin.command('ping')
    except Exception as e:
        pytest.skip(f"Cannot connect to test database: {e}")

    yield test_database

    # Cleanup: Close connection
    mongo_client.close()


@pytest.fixture(scope="function")
async def test_db_cleanup():
    """
    Fixture that ensures test database cleanup after each test.

    This fixture:
    1. Provides a database connection
    2. Yields control to the test
    3. Automatically cleans up test data after the test completes

    Usage:
        async def test_something(test_db_cleanup):
            db = test_db_cleanup  # This is the connected database
            # Run test
            # Data is automatically cleaned up afterward
    """
    mongo_client = AsyncIOMotorClient(TEST_MONGODB_URI, serverSelectionTimeoutMS=5000)
    test_database = mongo_client[TEST_DATABASE_NAME]

    # Verify connection
    try:
        await mongo_client.admin.command('ping')
    except Exception as e:
        pytest.skip(f"Cannot connect to test database: {e}")

    yield test_database

    # Cleanup: Delete only test-created data (with TEST- prefix)
    try:
        collections_to_clean = [
            "translation_transactions",
            "user_transactions",
            "company",
            "company_users",
            "subscriptions",
            "payments",
            "invoices"
        ]

        for collection_name in collections_to_clean:
            collection = test_database[collection_name]
            # Delete records with TEST prefix in their ID/name fields
            await collection.delete_many({
                "$or": [
                    {"transaction_id": {"$regex": "^TXN-TEST-"}},
                    {"company_name": {"$regex": "^TEST-"}},
                    {"invoice_number": {"$regex": "^TEST-"}},
                ]
            })
    except Exception as e:
        # Log cleanup errors but don't fail the test
        print(f"Warning: Cleanup error in {collection_name}: {e}")

    # Close connection
    mongo_client.close()
