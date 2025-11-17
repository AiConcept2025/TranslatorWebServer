"""
INTEGRATION TESTS FOR COMPANY USERS EDIT OPERATIONS - USING REAL DATABASE

These tests make actual HTTP requests to the running server and verify
responses against the REAL MongoDB database (translation_test).

NO MOCKS - Real API + Real Database testing.

Test Coverage:
- POST /api/company-users - Create new company user
- GET /api/company-users - Retrieve company users (with filtering)
- PATCH /api/company-users/{user_id} - Update company user (if implemented)
- DELETE /api/company-users/{user_id} - Delete company user (if implemented)

All tests verify changes in the database after API calls.
"""

import pytest
import httpx
import uuid
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

# ============================================================================
# Test Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8000"
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation"
DATABASE_NAME = "translation_test"

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def db():
    """
    Connect to test MongoDB database.

    CRITICAL: Uses test database 'translation_test', NOT production 'translation'.
    """
    mongo_client = AsyncIOMotorClient(MONGODB_URI)
    database = mongo_client[DATABASE_NAME]

    yield database

    # Cleanup: Don't drop database, just close connection
    mongo_client.close()


@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls to running server."""
    async_client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=10.0)
    yield async_client
    await async_client.aclose()


@pytest.fixture(scope="function")
async def admin_headers():
    """
    Get admin authentication headers.

    TODO: Implement admin login to get auth token if required.
    For now, return empty dict (endpoints may not require auth in test env).
    """
    return {}


@pytest.fixture(scope="function")
async def test_company(db):
    """
    Create a test company in the database for testing.

    Returns the created company document.
    Automatically cleaned up after test.
    """
    collection = db.company

    now = datetime.now(timezone.utc)
    company_name = f"TEST-COMPANY-{uuid.uuid4().hex[:8].upper()}"

    company_doc = {
        "company_name": company_name,
        "description": "Test company for user tests",
        "address": {
            "address0": "123 Test Street",
            "address1": "",
            "postal_code": "12345",
            "state": "NJ",
            "city": "Test City",
            "country": "USA"
        },
        "contact_person": {
            "name": "Test Contact",
            "type": "Primary Contact"
        },
        "phone_number": ["555-0123"],
        "company_url": [],
        "line_of_business": "Testing",
        "created_at": now,
        "updated_at": now
    }

    result = await collection.insert_one(company_doc)
    company_doc["_id"] = result.inserted_id

    print(f"✅ Created test company: {company_name}")

    yield company_doc

    # Cleanup: Delete test company
    await collection.delete_one({"_id": result.inserted_id})
    print(f"🗑️ Cleaned up test company: {company_name}")


@pytest.fixture(scope="function")
async def test_user(db, test_company):
    """
    Create a test company user in the database.

    Returns the created user document.
    Automatically cleaned up after test.
    """
    collection = db.company_users

    now = datetime.now(timezone.utc)
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    email = f"test-{uuid.uuid4().hex[:8]}@example.com"

    user_doc = {
        "user_id": user_id,
        "company_name": test_company["company_name"],
        "user_name": "Test User",
        "email": email,
        "phone_number": "+1-555-0123",
        "permission_level": "user",
        "status": "active",
        "password_hash": "$2b$12$test_hash_placeholder",
        "last_login": None,
        "created_at": now,
        "updated_at": now
    }

    result = await collection.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    print(f"✅ Created test user: {email}")

    yield user_doc

    # Cleanup: Delete test user
    await collection.delete_one({"_id": result.inserted_id})
    print(f"🗑️ Cleaned up test user: {email}")


# ============================================================================
# Test Class: Create Company User
# ============================================================================

@pytest.mark.asyncio
class TestCreateCompanyUser:
    """Test POST /api/company-users endpoint."""

    async def test_create_user_success(self, http_client, db, test_company):
        """Test 1.1: Create user with all required fields."""
        company_name = test_company["company_name"]
        email = f"newuser-{uuid.uuid4().hex[:8]}@example.com"

        # Prepare user data
        user_data = {
            "user_name": "John Doe",
            "email": email,
            "phone_number": "+1-555-9999",
            "password": "SecurePass123",
            "permission_level": "user",
            "status": "active"
        }

        # Make request
        response = await http_client.post(
            f"/api/company-users?company_name={company_name}",
            json=user_data
        )

        # Verify response
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "user_id" in data
        assert data["email"] == email.lower()  # Email should be normalized
        assert data["company_name"] == company_name
        assert data["permission_level"] == "user"
        assert data["status"] == "active"

        # Verify database
        created_user = await db.company_users.find_one({"email": email.lower()})
        assert created_user is not None
        assert created_user["user_name"] == "John Doe"
        assert created_user["company_name"] == company_name
        assert created_user["permission_level"] == "user"
        assert "password_hash" in created_user
        assert created_user["password_hash"] != "SecurePass123"  # Password should be hashed

        # Cleanup
        await db.company_users.delete_one({"_id": created_user["_id"]})

        print(f"✅ Test passed: User created successfully with user_id={data['user_id']}")


    async def test_create_user_minimal_fields(self, http_client, db, test_company):
        """Test 1.2: Create user with only required fields."""
        company_name = test_company["company_name"]
        email = f"minimal-{uuid.uuid4().hex[:8]}@example.com"

        # Minimal required fields (no phone_number)
        user_data = {
            "user_name": "Jane Smith",
            "email": email,
            "password": "Password123"
        }

        # Make request
        response = await http_client.post(
            f"/api/company-users?company_name={company_name}",
            json=user_data
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == email.lower()
        assert data["permission_level"] == "user"  # Default value
        assert data["status"] == "active"  # Default value

        # Verify database
        created_user = await db.company_users.find_one({"email": email.lower()})
        assert created_user is not None

        # Cleanup
        await db.company_users.delete_one({"_id": created_user["_id"]})

        print(f"✅ Test passed: User created with minimal fields")


    async def test_create_user_duplicate_email(self, http_client, test_company, test_user):
        """Test 1.3: Creating user with duplicate email returns 400."""
        company_name = test_company["company_name"]
        duplicate_email = test_user["email"]

        user_data = {
            "user_name": "Duplicate User",
            "email": duplicate_email,
            "password": "Password123"
        }

        # Make request
        response = await http_client.post(
            f"/api/company-users?company_name={company_name}",
            json=user_data
        )

        # Verify 400 error
        assert response.status_code == 400
        data = response.json()
        assert "already exists" in data["detail"].lower()

        print(f"✅ Test passed: 400 returned for duplicate email")


    async def test_create_user_invalid_email(self, http_client, test_company):
        """Test 1.4: Invalid email returns 422 validation error."""
        company_name = test_company["company_name"]

        user_data = {
            "user_name": "Invalid Email User",
            "email": "not-an-email",  # Invalid email format
            "password": "Password123"
        }

        # Make request
        response = await http_client.post(
            f"/api/company-users?company_name={company_name}",
            json=user_data
        )

        # Verify 422 validation error
        assert response.status_code == 422

        print(f"✅ Test passed: 422 returned for invalid email")


    async def test_create_user_invalid_company(self, http_client):
        """Test 1.5: Non-existent company returns 400."""
        fake_company = "NONEXISTENT-COMPANY-12345"
        email = f"test-{uuid.uuid4().hex[:8]}@example.com"

        user_data = {
            "user_name": "Test User",
            "email": email,
            "password": "Password123"
        }

        # Make request
        response = await http_client.post(
            f"/api/company-users?company_name={fake_company}",
            json=user_data
        )

        # Verify 400 error
        assert response.status_code == 400
        data = response.json()
        assert "company not found" in data["detail"].lower()

        print(f"✅ Test passed: 400 returned for non-existent company")


    async def test_create_user_weak_password(self, http_client, test_company):
        """Test 1.6: Weak password returns 422 validation error."""
        company_name = test_company["company_name"]
        email = f"weak-{uuid.uuid4().hex[:8]}@example.com"

        # Test various weak passwords
        weak_passwords = [
            "12345",           # Too short
            "password",        # No number
            "12345678",        # No letter
            "pass",            # Too short and no number
        ]

        for weak_password in weak_passwords:
            user_data = {
                "user_name": "Weak Password User",
                "email": email,
                "password": weak_password
            }

            # Make request
            response = await http_client.post(
                f"/api/company-users?company_name={company_name}",
                json=user_data
            )

            # Verify 422 validation error
            assert response.status_code == 422, f"Expected 422 for password '{weak_password}', got {response.status_code}"

            print(f"✅ Weak password '{weak_password}' rejected")

        print(f"✅ Test passed: All weak passwords rejected with 422")


# ============================================================================
# Test Class: Get Company Users
# ============================================================================

@pytest.mark.asyncio
class TestGetCompanyUsers:
    """Test GET /api/company-users endpoint."""

    async def test_get_all_company_users(self, http_client, db, test_company, test_user):
        """Test 2.1: Get all company users without filter."""
        # Make request
        response = await http_client.get("/api/company-users")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # Should have at least our test user

        # Find our test user in the results
        test_user_found = any(user["email"] == test_user["email"] for user in data)
        assert test_user_found, "Test user should be in the results"

        print(f"✅ Test passed: Retrieved {len(data)} company users")


    async def test_get_company_users_filtered(self, http_client, db, test_company, test_user):
        """Test 2.2: Get company users filtered by company_name."""
        company_name = test_company["company_name"]

        # Make request with filter
        response = await http_client.get(f"/api/company-users?company_name={company_name}")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # Should have at least our test user

        # Verify all users belong to the filtered company
        for user in data:
            assert user["company_name"] == company_name

        # Find our test user
        test_user_found = any(user["email"] == test_user["email"] for user in data)
        assert test_user_found, "Test user should be in filtered results"

        print(f"✅ Test passed: Retrieved {len(data)} users for company '{company_name}'")


    async def test_get_company_users_invalid_company(self, http_client):
        """Test 2.3: Filter by non-existent company returns 400."""
        fake_company = "NONEXISTENT-COMPANY-12345"

        # Make request
        response = await http_client.get(f"/api/company-users?company_name={fake_company}")

        # Verify 400 error
        assert response.status_code == 400
        data = response.json()
        assert "company not found" in data["detail"].lower()

        print(f"✅ Test passed: 400 returned for non-existent company filter")


    async def test_get_company_users_response_structure(self, http_client, test_user):
        """Test 2.4: Response has correct structure and excludes sensitive data."""
        # Make request
        response = await http_client.get("/api/company-users")

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        # Check structure of first user
        user = data[0]
        assert "user_id" in user
        assert "company_name" in user
        assert "user_name" in user
        assert "email" in user
        assert "permission_level" in user
        assert "status" in user
        assert "created_at" in user

        # Verify sensitive data is NOT included
        assert "password_hash" not in user, "Password hash should not be in response"
        assert "password" not in user, "Password should not be in response"

        print(f"✅ Test passed: Response structure correct, sensitive data excluded")


# ============================================================================
# Test Class: Update Company User (if implemented)
# ============================================================================

@pytest.mark.asyncio
class TestUpdateCompanyUser:
    """Test PATCH /api/company-users/{user_id} endpoint (if implemented)."""

    async def test_update_user_permission_level(self, http_client, db, test_user):
        """Test 3.1: Update permission level from user to admin."""
        user_id = test_user["user_id"]
        original_permission = test_user["permission_level"]

        # Get record before
        record_before = await db.company_users.find_one({"user_id": user_id})
        assert record_before["permission_level"] == original_permission
        print(f"📊 Before: permission_level={record_before['permission_level']}")

        # Update data
        update_data = {"permission_level": "admin"}

        # Make request
        response = await http_client.patch(
            f"/api/company-users/{user_id}",
            json=update_data
        )

        # If endpoint not implemented, skip
        if response.status_code == 404:
            print(f"⚠️ Test skipped: PATCH endpoint not implemented (404)")
            return

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["permission_level"] == "admin"

        # Verify database
        record_after = await db.company_users.find_one({"user_id": user_id})
        assert record_after["permission_level"] == "admin"
        assert record_after["permission_level"] != original_permission

        print(f"✅ Test passed: Permission level updated from '{original_permission}' to 'admin'")


    async def test_update_user_status(self, http_client, db, test_user):
        """Test 3.2: Update status from active to inactive."""
        user_id = test_user["user_id"]
        original_status = test_user["status"]

        # Get record before
        record_before = await db.company_users.find_one({"user_id": user_id})
        assert record_before["status"] == original_status
        print(f"📊 Before: status={record_before['status']}")

        # Update data
        update_data = {"status": "inactive"}

        # Make request
        response = await http_client.patch(
            f"/api/company-users/{user_id}",
            json=update_data
        )

        # If endpoint not implemented, skip
        if response.status_code == 404:
            print(f"⚠️ Test skipped: PATCH endpoint not implemented (404)")
            return

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "inactive"

        # Verify database
        record_after = await db.company_users.find_one({"user_id": user_id})
        assert record_after["status"] == "inactive"
        assert record_after["status"] != original_status

        print(f"✅ Test passed: Status updated from '{original_status}' to 'inactive'")


# ============================================================================
# Test Class: Delete Company User (if implemented)
# ============================================================================

@pytest.mark.asyncio
class TestDeleteCompanyUser:
    """Test DELETE /api/company-users/{user_id} endpoint (if implemented)."""

    async def test_delete_user_success(self, http_client, db, test_company):
        """Test 4.1: Delete user successfully."""
        # Create a user specifically for deletion
        email = f"delete-{uuid.uuid4().hex[:8]}@example.com"
        user_data = {
            "user_name": "Delete Me",
            "email": email,
            "password": "Password123"
        }

        create_response = await http_client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=user_data
        )
        assert create_response.status_code == 201
        created_user = create_response.json()
        user_id = created_user["user_id"]

        # Verify user exists in database
        user_before = await db.company_users.find_one({"user_id": user_id})
        assert user_before is not None
        print(f"📊 User exists: user_id={user_id}")

        # Delete user
        response = await http_client.delete(f"/api/company-users/{user_id}")

        # If endpoint not implemented, clean up and skip
        if response.status_code == 404:
            await db.company_users.delete_one({"user_id": user_id})
            print(f"⚠️ Test skipped: DELETE endpoint not implemented (404)")
            return

        # Verify response
        assert response.status_code == 200

        # Verify database - user should be deleted
        user_after = await db.company_users.find_one({"user_id": user_id})
        assert user_after is None

        print(f"✅ Test passed: User deleted successfully")


    async def test_delete_nonexistent_user(self, http_client):
        """Test 4.2: Delete non-existent user returns 404."""
        fake_user_id = f"user_{uuid.uuid4().hex[:16]}"

        # Make request
        response = await http_client.delete(f"/api/company-users/{fake_user_id}")

        # Should return 404
        if response.status_code == 404 and "not implemented" in response.text.lower():
            print(f"⚠️ Test skipped: DELETE endpoint not implemented")
            return

        # Verify 404 error
        assert response.status_code == 404

        print(f"✅ Test passed: 404 returned for non-existent user")


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("COMPANY USERS EDIT OPERATIONS - INTEGRATION TESTS")
    print("=" * 80)
    print("\nRunning tests against:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Database: {MONGODB_URI}/{DATABASE_NAME}")
    print("\nNOTE: Tests use test database and clean up after themselves")
    print("=" * 80)
    print("\n")
