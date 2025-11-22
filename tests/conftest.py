"""
Pytest configuration for integration tests.
"""

import pytest
import uuid
import httpx
from datetime import datetime, timezone
from typing import Dict, Any

from app.database.mongodb import database


# Configure pytest to use asyncio
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )


# ============================================================================
# Shared Test Fixtures
# ============================================================================

@pytest.fixture(scope="session")
async def admin_session_token():
    """
    Create an admin user and get a valid session token for testing.

    This is a session-scoped fixture that creates an admin user once
    and returns a valid Bearer token for all tests.

    Returns:
        dict: {"Authorization": "Bearer {token}"}
    """
    import bcrypt
    from app.services.auth_service import auth_service

    await database.connect()

    # Create test admin user
    admin_email = "test-admin@example.com"
    admin_password = "TestAdmin123!"

    # Delete existing admin user if exists (for clean test state)
    await database.company_users.delete_one({"email": admin_email})

    # Always create fresh admin user for tests
    if True:
        # Create admin user directly in company_users collection
        # Hash password with bcrypt (same method as auth_service)
        password_bytes = admin_password.encode('utf-8')[:72]  # Truncate to 72 bytes (bcrypt limit)
        password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')

        admin_doc = {
            "email": admin_email,
            "password_hash": password_hash,
            "user_name": "Test Admin",
            "company_name": "TEST-ADMIN-COMPANY",  # Admin needs a company
            "permission_level": "admin",
            "status": "active",  # User must be active to authenticate
            "failed_login_attempts": 0,
            "account_locked": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        # Also create the company
        company_doc = {
            "company_name": "TEST-ADMIN-COMPANY",
            "description": "Test company for admin user",
            "address": {
                "address0": "123 Admin St",
                "address1": "",
                "postal_code": "00000",
                "state": "TS",
                "city": "Test City",
                "country": "USA"
            },
            "contact_person": {
                "name": "Test Admin",
                "type": "Admin"
            },
            "phone_number": ["000-000-0000"],
            "company_url": [],
            "line_of_business": "Testing",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        # Check if company exists
        existing_company = await database.company.find_one({"company_name": "TEST-ADMIN-COMPANY"})
        if not existing_company:
            await database.company.insert_one(company_doc)

        await database.company_users.insert_one(admin_doc)

    # Authenticate to get session token
    auth_result = await auth_service.authenticate_user(
        company_name="TEST-ADMIN-COMPANY",
        password=admin_password,
        user_name="Test Admin",
        email=admin_email
    )

    session_token = auth_result.get("session_token")
    if not session_token:
        raise ValueError("Failed to create admin session token")

    return {"Authorization": f"Bearer {session_token}"}


@pytest.fixture(scope="function")
async def admin_headers(admin_session_token):
    """
    Get admin authentication headers for a test.

    Uses the session-scoped admin_session_token fixture.

    Returns:
        dict: {"Authorization": "Bearer {token}"}
    """
    return admin_session_token


@pytest.fixture(scope="function")
async def test_transaction_with_nested_docs():
    """
    Create test transaction with nested documents structure.

    Returns a complete transaction document matching the new nested structure.
    Automatically cleaned up after test.

    Structure:
    - transaction_id: TXN-TEST-{uuid}
    - documents: array with 1 document
    - All required transaction fields
    """
    await database.connect()
    collection = database.translation_transactions

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
    """
    now = datetime.now(timezone.utc)

    return {
        "transaction_id": f"TXN-SAMPLE-{uuid.uuid4().hex[:8].upper()}",
        "user_id": "sample@example.com",
        "company_name": "Sample Company",
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
