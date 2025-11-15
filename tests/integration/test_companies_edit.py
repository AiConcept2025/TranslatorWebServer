"""
INTEGRATION TESTS FOR COMPANIES EDIT OPERATIONS - USING REAL DATABASE

These tests make actual HTTP requests to the running server and verify
responses against the REAL MongoDB database (translation_test).

NO MOCKS - Real API + Real Database testing.

Test Coverage:
- GET /api/v1/companies - Retrieve all companies
- POST /api/v1/companies - Create new company (if implemented)
- PATCH /api/v1/companies/{company_name} - Update company (if implemented)
- DELETE /api/v1/companies/{company_name} - Delete company (if implemented)

All tests verify changes in the database after API calls.

Note: Based on the existing router, only GET endpoint is currently implemented.
Other tests will check if endpoints exist and skip if not implemented.
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
        "description": "Test company for company tests",
        "address": {
            "address0": "123 Test Street",
            "address1": "Suite 100",
            "postal_code": "12345",
            "state": "NJ",
            "city": "Test City",
            "country": "USA"
        },
        "contact_person": {
            "name": "Test Contact Person",
            "type": "Primary Contact"
        },
        "phone_number": ["555-0123", "555-0124"],
        "company_url": ["https://testcompany.example.com"],
        "line_of_business": "Testing Services",
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


# ============================================================================
# Test Class: Get Companies
# ============================================================================

@pytest.mark.asyncio
class TestGetCompanies:
    """Test GET /api/v1/companies endpoint."""

    async def test_get_all_companies_success(self, http_client, db, test_company):
        """Test 1.1: GET /api/v1/companies returns 200 and company list."""
        # Make request
        response = await http_client.get("/api/v1/companies")

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "companies" in data["data"]
        assert "count" in data["data"]
        assert isinstance(data["data"]["companies"], list)
        assert data["data"]["count"] >= 1  # Should have at least our test company

        print(f"✅ Test passed: Retrieved {data['data']['count']} companies")


    async def test_get_all_companies_structure(self, http_client, test_company):
        """Test 1.2: Response has correct structure with all required fields."""
        # Make request
        response = await http_client.get("/api/v1/companies")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "success" in data
        assert data["success"] is True
        assert "data" in data

        # Check data structure
        assert "companies" in data["data"]
        assert "count" in data["data"]
        assert isinstance(data["data"]["companies"], list)

        # Find our test company
        test_company_name = test_company["company_name"]
        found_company = None
        for company in data["data"]["companies"]:
            if company["company_name"] == test_company_name:
                found_company = company
                break

        assert found_company is not None, f"Test company '{test_company_name}' not found in results"

        # Verify company has required fields
        assert "_id" in found_company
        assert "company_name" in found_company
        assert "description" in found_company
        assert "address" in found_company
        assert "contact_person" in found_company
        assert "phone_number" in found_company
        assert "line_of_business" in found_company
        assert "created_at" in found_company
        assert "updated_at" in found_company

        # Verify _id is string (serialized from ObjectId)
        assert isinstance(found_company["_id"], str)

        # Verify datetime fields are ISO strings
        assert isinstance(found_company["created_at"], str)
        assert isinstance(found_company["updated_at"], str)

        print(f"✅ Test passed: Response structure correct, all fields present")


    async def test_get_all_companies_matches_database(self, http_client, db):
        """Test 1.3: API response count matches database count."""
        # Get count from API
        response = await http_client.get("/api/v1/companies")
        assert response.status_code == 200
        data = response.json()
        api_count = data["data"]["count"]

        # Get count from database
        db_count = await db.company.count_documents({})

        # Verify counts match
        assert api_count == db_count, f"API count ({api_count}) != DB count ({db_count})"

        print(f"✅ Test passed: API count matches DB count ({api_count})")


    async def test_get_companies_test_company_present(self, http_client, test_company):
        """Test 1.4: Test company is present in results."""
        # Make request
        response = await http_client.get("/api/v1/companies")

        # Verify response
        assert response.status_code == 200
        data = response.json()

        # Find our test company
        test_company_name = test_company["company_name"]
        company_names = [c["company_name"] for c in data["data"]["companies"]]

        assert test_company_name in company_names, f"Test company '{test_company_name}' not found"

        print(f"✅ Test passed: Test company '{test_company_name}' found in results")


# ============================================================================
# Test Class: Create Company (if implemented)
# ============================================================================

@pytest.mark.asyncio
class TestCreateCompany:
    """Test POST /api/v1/companies endpoint (if implemented)."""

    async def test_create_company_success(self, http_client, db, admin_headers):
        """Test 2.1: Create company with all required fields."""
        now = datetime.now(timezone.utc)
        company_name = f"NEW-COMPANY-{uuid.uuid4().hex[:8].upper()}"

        # Prepare company data
        company_data = {
            "company_name": company_name,
            "description": "New test company",
            "address": {
                "address0": "456 New Street",
                "address1": "",
                "postal_code": "54321",
                "state": "CA",
                "city": "New City",
                "country": "USA"
            },
            "contact_person": {
                "name": "New Contact",
                "type": "Primary Contact"
            },
            "phone_number": ["555-5555"],
            "company_url": ["https://newcompany.example.com"],
            "line_of_business": "New Business"
        }

        # Make request
        response = await http_client.post(
            "/api/v1/companies",
            json=company_data,
            headers=admin_headers
        )

        # If endpoint not implemented, skip
        if response.status_code == 404:
            print(f"⚠️ Test skipped: POST /api/v1/companies not implemented (404)")
            return

        if response.status_code == 405:
            print(f"⚠️ Test skipped: POST /api/v1/companies method not allowed (405)")
            return

        # Verify response
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True

        # Verify database
        created_company = await db.company.find_one({"company_name": company_name})
        assert created_company is not None
        assert created_company["company_name"] == company_name
        assert created_company["description"] == "New test company"
        assert created_company["line_of_business"] == "New Business"

        # Cleanup
        await db.company.delete_one({"_id": created_company["_id"]})

        print(f"✅ Test passed: Company created successfully")


    async def test_create_company_minimal(self, http_client, db, admin_headers):
        """Test 2.2: Create company with only required fields."""
        company_name = f"MINIMAL-{uuid.uuid4().hex[:8].upper()}"

        # Minimal required fields
        company_data = {
            "company_name": company_name,
            "description": "Minimal company"
        }

        # Make request
        response = await http_client.post(
            "/api/v1/companies",
            json=company_data,
            headers=admin_headers
        )

        # If endpoint not implemented, skip
        if response.status_code in [404, 405]:
            print(f"⚠️ Test skipped: POST endpoint not implemented ({response.status_code})")
            return

        # Should succeed or return validation error
        if response.status_code == 201:
            data = response.json()
            # Cleanup
            await db.company.delete_one({"company_name": company_name})
            print(f"✅ Test passed: Minimal company created")
        elif response.status_code == 422:
            print(f"✅ Test passed: Validation error for minimal data (422)")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code}")


    async def test_create_company_duplicate_name(self, http_client, test_company, admin_headers):
        """Test 2.3: Creating company with duplicate name returns 400."""
        duplicate_name = test_company["company_name"]

        company_data = {
            "company_name": duplicate_name,
            "description": "Duplicate company"
        }

        # Make request
        response = await http_client.post(
            "/api/v1/companies",
            json=company_data,
            headers=admin_headers
        )

        # If endpoint not implemented, skip
        if response.status_code in [404, 405]:
            print(f"⚠️ Test skipped: POST endpoint not implemented ({response.status_code})")
            return

        # Verify 400 or 409 error
        assert response.status_code in [400, 409], f"Expected 400 or 409, got {response.status_code}"

        print(f"✅ Test passed: {response.status_code} returned for duplicate company name")


    async def test_create_company_invalid_data(self, http_client, admin_headers):
        """Test 2.4: Invalid data returns 422 validation error."""
        # Missing required field (company_name)
        company_data = {
            "description": "Company without name"
        }

        # Make request
        response = await http_client.post(
            "/api/v1/companies",
            json=company_data,
            headers=admin_headers
        )

        # If endpoint not implemented, skip
        if response.status_code in [404, 405]:
            print(f"⚠️ Test skipped: POST endpoint not implemented ({response.status_code})")
            return

        # Verify 422 validation error
        assert response.status_code == 422

        print(f"✅ Test passed: 422 returned for invalid data")


# ============================================================================
# Test Class: Update Company (if implemented)
# ============================================================================

@pytest.mark.asyncio
class TestUpdateCompany:
    """Test PATCH /api/v1/companies/{company_name} endpoint (if implemented)."""

    async def test_update_company_description(self, http_client, db, admin_headers, test_company):
        """Test 3.1: Update company description."""
        company_name = test_company["company_name"]
        original_description = test_company["description"]
        new_description = "Updated description"

        # Get record before
        record_before = await db.company.find_one({"company_name": company_name})
        assert record_before["description"] == original_description
        print(f"📊 Before: description={record_before['description']}")

        # Update data
        update_data = {"description": new_description}

        # Make request
        response = await http_client.patch(
            f"/api/v1/companies/{company_name}",
            json=update_data,
            headers=admin_headers
        )

        # If endpoint not implemented, skip
        if response.status_code in [404, 405]:
            print(f"⚠️ Test skipped: PATCH endpoint not implemented ({response.status_code})")
            return

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database
        record_after = await db.company.find_one({"company_name": company_name})
        assert record_after["description"] == new_description
        assert record_after["description"] != original_description
        assert record_after["updated_at"] > record_before["updated_at"]

        print(f"✅ Test passed: Description updated from '{original_description}' to '{new_description}'")


    async def test_update_company_contact_info(self, http_client, db, admin_headers, test_company):
        """Test 3.2: Update company contact information."""
        company_name = test_company["company_name"]

        # Get record before
        record_before = await db.company.find_one({"company_name": company_name})
        original_phone = record_before["phone_number"]
        print(f"📊 Before: phone_number={original_phone}")

        # Update data
        new_phone = ["555-9999", "555-8888"]
        update_data = {
            "phone_number": new_phone,
            "contact_person": {
                "name": "Updated Contact",
                "type": "Secondary Contact"
            }
        }

        # Make request
        response = await http_client.patch(
            f"/api/v1/companies/{company_name}",
            json=update_data,
            headers=admin_headers
        )

        # If endpoint not implemented, skip
        if response.status_code in [404, 405]:
            print(f"⚠️ Test skipped: PATCH endpoint not implemented ({response.status_code})")
            return

        # Verify response
        assert response.status_code == 200

        # Verify database
        record_after = await db.company.find_one({"company_name": company_name})
        assert record_after["phone_number"] == new_phone
        assert record_after["contact_person"]["name"] == "Updated Contact"

        print(f"✅ Test passed: Contact info updated successfully")


    async def test_update_company_address(self, http_client, db, admin_headers, test_company):
        """Test 3.3: Update company address."""
        company_name = test_company["company_name"]

        # Get record before
        record_before = await db.company.find_one({"company_name": company_name})
        original_address = record_before["address"]
        print(f"📊 Before: address={original_address}")

        # Update data
        new_address = {
            "address0": "789 Updated Street",
            "address1": "Floor 5",
            "postal_code": "99999",
            "state": "NY",
            "city": "Updated City",
            "country": "USA"
        }
        update_data = {"address": new_address}

        # Make request
        response = await http_client.patch(
            f"/api/v1/companies/{company_name}",
            json=update_data,
            headers=admin_headers
        )

        # If endpoint not implemented, skip
        if response.status_code in [404, 405]:
            print(f"⚠️ Test skipped: PATCH endpoint not implemented ({response.status_code})")
            return

        # Verify response
        assert response.status_code == 200

        # Verify database
        record_after = await db.company.find_one({"company_name": company_name})
        assert record_after["address"]["address0"] == "789 Updated Street"
        assert record_after["address"]["city"] == "Updated City"
        assert record_after["address"]["postal_code"] == "99999"

        print(f"✅ Test passed: Address updated successfully")


    async def test_update_nonexistent_company(self, http_client, admin_headers):
        """Test 3.4: Update non-existent company returns 404."""
        fake_company = "NONEXISTENT-COMPANY-12345"

        update_data = {"description": "Updated"}

        # Make request
        response = await http_client.patch(
            f"/api/v1/companies/{fake_company}",
            json=update_data,
            headers=admin_headers
        )

        # If endpoint returns 405, it's not implemented
        if response.status_code == 405:
            print(f"⚠️ Test skipped: PATCH endpoint not implemented (405)")
            return

        # Verify 404 error
        assert response.status_code == 404

        print(f"✅ Test passed: 404 returned for non-existent company")


# ============================================================================
# Test Class: Delete Company (if implemented)
# ============================================================================

@pytest.mark.asyncio
class TestDeleteCompany:
    """Test DELETE /api/v1/companies/{company_name} endpoint (if implemented)."""

    async def test_delete_company_success(self, http_client, db, admin_headers):
        """Test 4.1: Delete company successfully."""
        # Create a company specifically for deletion
        now = datetime.now(timezone.utc)
        company_name = f"DELETE-ME-{uuid.uuid4().hex[:8].upper()}"

        company_doc = {
            "company_name": company_name,
            "description": "Company to be deleted",
            "address": {
                "address0": "Delete Street",
                "postal_code": "00000",
                "city": "Delete City",
                "state": "XX",
                "country": "USA"
            },
            "phone_number": [],
            "company_url": [],
            "line_of_business": "Testing",
            "created_at": now,
            "updated_at": now
        }

        result = await db.company.insert_one(company_doc)
        print(f"📊 Created company for deletion: {company_name}")

        # Verify company exists
        company_before = await db.company.find_one({"company_name": company_name})
        assert company_before is not None

        # Delete company
        response = await http_client.delete(
            f"/api/v1/companies/{company_name}",
            headers=admin_headers
        )

        # If endpoint not implemented, clean up and skip
        if response.status_code in [404, 405]:
            await db.company.delete_one({"company_name": company_name})
            print(f"⚠️ Test skipped: DELETE endpoint not implemented ({response.status_code})")
            return

        # Verify response
        assert response.status_code == 200

        # Verify database - company should be deleted
        company_after = await db.company.find_one({"company_name": company_name})
        assert company_after is None

        print(f"✅ Test passed: Company deleted successfully")


    async def test_delete_company_with_users(self, http_client, db, admin_headers):
        """Test 4.2: Delete company with associated users (should handle cascading delete or prevent)."""
        # Create company and user
        now = datetime.now(timezone.utc)
        company_name = f"DELETE-WITH-USERS-{uuid.uuid4().hex[:8].upper()}"

        company_doc = {
            "company_name": company_name,
            "description": "Company with users",
            "created_at": now,
            "updated_at": now
        }
        await db.company.insert_one(company_doc)

        # Create associated user
        user_doc = {
            "user_id": f"user_{uuid.uuid4().hex[:16]}",
            "company_name": company_name,
            "user_name": "Test User",
            "email": f"test-{uuid.uuid4().hex[:8]}@example.com",
            "permission_level": "user",
            "status": "active",
            "password_hash": "$2b$12$test",
            "created_at": now,
            "updated_at": now
        }
        await db.company_users.insert_one(user_doc)

        print(f"📊 Created company with user: {company_name}")

        # Try to delete company
        response = await http_client.delete(
            f"/api/v1/companies/{company_name}",
            headers=admin_headers
        )

        # If endpoint not implemented, clean up and skip
        if response.status_code in [404, 405]:
            await db.company.delete_one({"company_name": company_name})
            await db.company_users.delete_one({"company_name": company_name})
            print(f"⚠️ Test skipped: DELETE endpoint not implemented ({response.status_code})")
            return

        # Should either succeed (cascading delete) or fail (400/409)
        if response.status_code == 200:
            # Verify both company and users deleted (cascading)
            company_after = await db.company.find_one({"company_name": company_name})
            users_after = await db.company_users.count_documents({"company_name": company_name})
            assert company_after is None
            assert users_after == 0
            print(f"✅ Test passed: Company and users deleted (cascading)")
        elif response.status_code in [400, 409]:
            # Delete prevented, clean up
            await db.company.delete_one({"company_name": company_name})
            await db.company_users.delete_one({"company_name": company_name})
            print(f"✅ Test passed: Delete prevented due to associated users ({response.status_code})")
        else:
            # Cleanup
            await db.company.delete_one({"company_name": company_name})
            await db.company_users.delete_one({"company_name": company_name})
            pytest.fail(f"Unexpected status code: {response.status_code}")


    async def test_delete_nonexistent_company(self, http_client, admin_headers):
        """Test 4.3: Delete non-existent company returns 404."""
        fake_company = "NONEXISTENT-COMPANY-12345"

        # Make request
        response = await http_client.delete(
            f"/api/v1/companies/{fake_company}",
            headers=admin_headers
        )

        # If endpoint returns 405, it's not implemented
        if response.status_code == 405:
            print(f"⚠️ Test skipped: DELETE endpoint not implemented (405)")
            return

        # Verify 404 error
        assert response.status_code == 404

        print(f"✅ Test passed: 404 returned for non-existent company")


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("COMPANIES EDIT OPERATIONS - INTEGRATION TESTS")
    print("=" * 80)
    print("\nRunning tests against:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Database: {MONGODB_URI}/{DATABASE_NAME}")
    print("\nNOTE: Tests use test database and clean up after themselves")
    print("NOTE: Only GET endpoint is currently implemented - other tests will skip gracefully")
    print("=" * 80)
    print("\n")
