"""
Focused integration test for company user creation endpoint.

Tests creating a new user for the existing 'Iris Trading' company.

FOCUS: Only tests creating a new user for an existing company.
SAFE: Only modifies company_users collection for cleanup.

Test Database: translation_test (if running against test database)
Collections: company_users (for cleanup only)
"""

import pytest
from httpx import AsyncClient

from app.main import app
from app.database.mongodb import database


@pytest.fixture
async def client():
    """Provide an AsyncClient for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_create_company_user_for_iris_trading(client: AsyncClient):
    """
    Test creating a new user for the existing company 'Iris Trading'.

    This test:
    1. Sends POST request to create a user for 'Iris Trading'
    2. Verifies 201 Created response
    3. Verifies response contains correct user data
    4. Cleans up the created user from company_users collection

    SAFE: Only touches company_users collection for cleanup.
    Does NOT create or modify companies collection.

    Assertions:
    - Response status is 201 Created
    - Response contains user_id with correct format (user_*)
    - Response contains all required user fields
    - Response does NOT contain password or password_hash
    - created_at timestamp is present
    """
    # Test data - create user for existing company "Iris Trading"
    company_name = "Iris Trading"
    user_data = {
        "user_name": "Test User",
        "email": "testuser@iristrading.com",
        "phone_number": "+1-555-9999",
        "password": "TestPass123",
        "permission_level": "user",
        "status": "active"
    }

    # Send request to create user
    response = await client.post(
        f"/api/company-users?company_name={company_name}",
        json=user_data
    )

    # Verify response status
    assert response.status_code == 201, (
        f"Expected 201 Created, got {response.status_code}: {response.text}"
    )

    data = response.json()

    # Verify user_id format
    assert "user_id" in data
    assert data["user_id"].startswith("user_")
    user_id = data["user_id"]

    # Verify company_name matches
    assert data["company_name"] == company_name

    # Verify all user fields are present and correct
    assert data["user_name"] == user_data["user_name"]
    assert data["email"] == user_data["email"].lower()
    assert data["phone_number"] == user_data["phone_number"]
    assert data["permission_level"] == user_data["permission_level"]
    assert data["status"] == user_data["status"]

    # Verify timestamp
    assert "created_at" in data
    assert data["created_at"] is not None

    # CRITICAL: Verify password is NOT in response
    assert "password" not in data, "Password must not be in response"
    assert "password_hash" not in data, "Password hash must not be in response"

    # Cleanup: Delete the test user from company_users collection ONLY
    try:
        await database.connect()
        delete_result = await database.company_users.delete_one(
            {"user_id": user_id}
        )
        await database.disconnect()

        assert delete_result.deleted_count == 1, (
            f"Expected to delete 1 user, deleted {delete_result.deleted_count}"
        )
    except Exception as e:
        # Attempt cleanup even if assertion fails
        try:
            await database.disconnect()
        except:
            pass
        raise AssertionError(f"Cleanup failed: {str(e)}") from e


# Export for pytest collection
__all__ = ["test_create_company_user_for_iris_trading"]
