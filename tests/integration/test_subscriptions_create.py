"""
INTEGRATION TESTS FOR SUBSCRIPTION CREATION - COMPANY VALIDATION

These tests verify application-level validation that enforces company existence
before creating subscriptions. Tests use REAL MongoDB database (translation_test).

NO MOCKS - Real API + Real Database testing.

Test Coverage:
- POST /api/subscriptions/ - Create subscription with valid company (SUCCESS)
- POST /api/subscriptions/ - Create subscription with non-existent company (FAIL)
- POST /api/subscriptions/ - Verify error message format for missing company

All tests verify changes in the database after API calls.
"""

import pytest
import httpx
import uuid
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta

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
async def test_company(db):
    """
    Create a test company in the database.

    Returns the created company document.
    Automatically cleaned up after test.
    """
    collection = db.company

    now = datetime.now(timezone.utc)
    company_name = f"TEST-COMPANY-{uuid.uuid4().hex[:8].upper()}"

    company_doc = {
        "company_name": company_name,
        "description": "Test company for subscription tests",
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


# ============================================================================
# Test Class: Company Validation
# ============================================================================

@pytest.mark.asyncio
class TestSubscriptionCompanyValidation:
    """Test company validation when creating subscriptions."""

    async def test_create_subscription_with_existing_company_success(
        self, http_client, db, admin_headers, test_company
    ):
        """
        Test 1.1: Create subscription for existing company - SUCCESS.

        Scenario:
        - Company exists in database
        - Create subscription with valid data
        - Expected: 201 Created, subscription saved to database
        """
        company_name = test_company["company_name"]

        # Verify company exists
        company_in_db = await db.company.find_one({"company_name": company_name})
        assert company_in_db is not None, f"Test company {company_name} should exist"
        print(f"📊 Company exists in DB: {company_name}")

        # Debug: Print headers
        print(f"DEBUG: Headers being sent: {admin_headers}")

        # Prepare subscription data
        now = datetime.now(timezone.utc)
        subscription_data = {
            "company_name": company_name,
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.10,
            "promotional_units": 100,
            "discount": 0.9,
            "subscription_price": 90.00,
            "start_date": now.isoformat(),
            "end_date": (now + timedelta(days=365)).isoformat(),
            "status": "active"
        }

        # Make request
        response = await http_client.post(
            "/api/subscriptions/",
            json=subscription_data,
            headers=admin_headers
        )

        # Assert response
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "subscription_id" in data["data"]
        assert data["data"]["company_name"] == company_name

        subscription_id = data["data"]["subscription_id"]
        print(f"✅ Subscription created: {subscription_id}")

        # Verify subscription in database
        subscription_in_db = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert subscription_in_db is not None
        assert subscription_in_db["company_name"] == company_name
        assert subscription_in_db["status"] == "active"
        assert subscription_in_db["units_per_subscription"] == 1000

        # Cleanup: Delete test subscription
        await db.subscriptions.delete_one({"_id": ObjectId(subscription_id)})
        print(f"🗑️ Cleaned up test subscription: {subscription_id}")

        print(f"✅ Test passed: Subscription created successfully for existing company")


    async def test_create_subscription_with_nonexistent_company_fails(
        self, http_client, db, admin_headers
    ):
        """
        Test 1.2: Create subscription for non-existent company - FAIL.

        Scenario:
        - Company does NOT exist in database
        - Attempt to create subscription
        - Expected: 400 Bad Request with clear error message
        """
        # Generate non-existent company name
        nonexistent_company = f"NONEXISTENT-COMPANY-{uuid.uuid4().hex[:8].upper()}"

        # Verify company does NOT exist
        company_in_db = await db.company.find_one({"company_name": nonexistent_company})
        assert company_in_db is None, f"Company {nonexistent_company} should NOT exist"
        print(f"📊 Company does NOT exist in DB: {nonexistent_company}")

        # Prepare subscription data
        now = datetime.now(timezone.utc)
        subscription_data = {
            "company_name": nonexistent_company,
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.10,
            "promotional_units": 100,
            "discount": 0.9,
            "subscription_price": 90.00,
            "start_date": now.isoformat(),
            "end_date": (now + timedelta(days=365)).isoformat(),
            "status": "active"
        }

        # Make request
        response = await http_client.post(
            "/api/subscriptions/",
            json=subscription_data,
            headers=admin_headers
        )

        # Assert response - should be 400 Bad Request
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify error message contains company name
        error_detail = data.get("detail", "")
        assert nonexistent_company in error_detail, f"Error message should contain company name: {error_detail}"
        assert "does not exist" in error_detail.lower(), f"Error should mention company doesn't exist: {error_detail}"

        print(f"✅ Error message: {error_detail}")

        # Verify subscription was NOT created in database
        subscription_in_db = await db.subscriptions.find_one({"company_name": nonexistent_company})
        assert subscription_in_db is None, "Subscription should NOT be created for non-existent company"

        print(f"✅ Test passed: Subscription creation blocked for non-existent company")


    async def test_create_subscription_error_message_format(
        self, http_client, db, admin_headers
    ):
        """
        Test 1.3: Verify error message format for non-existent company.

        Scenario:
        - Create subscription for non-existent company
        - Expected: HTTP 400 with detailed error message

        Error Format:
        {
            "detail": "Cannot create subscription: Company 'XYZ' does not exist in database"
        }
        """
        nonexistent_company = f"NONEXISTENT-{uuid.uuid4().hex[:8].upper()}"

        # Prepare subscription data
        now = datetime.now(timezone.utc)
        subscription_data = {
            "company_name": nonexistent_company,
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.10,
            "promotional_units": 100,
            "discount": 0.9,
            "subscription_price": 90.00,
            "start_date": now.isoformat(),
            "end_date": (now + timedelta(days=365)).isoformat(),
            "status": "active"
        }

        # Make request
        response = await http_client.post(
            "/api/subscriptions/",
            json=subscription_data,
            headers=admin_headers
        )

        # Verify status code
        assert response.status_code == 400

        # Verify error structure
        data = response.json()
        assert "detail" in data, "Response should contain 'detail' field"

        error_detail = data["detail"]

        # Verify error message contains:
        # 1. The phrase "Cannot create subscription"
        # 2. The company name
        # 3. The phrase "does not exist"
        assert "cannot create subscription" in error_detail.lower(), \
            f"Error should mention subscription creation: {error_detail}"
        assert nonexistent_company in error_detail, \
            f"Error should contain company name '{nonexistent_company}': {error_detail}"
        assert "does not exist" in error_detail.lower(), \
            f"Error should mention company doesn't exist: {error_detail}"

        print(f"✅ Error format verified:")
        print(f"   Status: 400")
        print(f"   Detail: {error_detail}")

        print(f"✅ Test passed: Error message format is correct")


    async def test_create_subscription_case_sensitive_company_name(
        self, http_client, db, admin_headers, test_company
    ):
        """
        Test 1.4: Company name matching is case-sensitive.

        Scenario:
        - Company exists as "TEST-COMPANY-ABC123"
        - Try to create subscription with "test-company-abc123" (lowercase)
        - Expected: 400 (case-sensitive matching)

        NOTE: If company name matching should be case-INsensitive,
        this test will fail and the service needs to be updated.
        """
        company_name = test_company["company_name"]  # e.g., "TEST-COMPANY-ABC123"
        lowercase_name = company_name.lower()  # e.g., "test-company-abc123"

        print(f"📊 Actual company: {company_name}")
        print(f"📊 Lowercase attempt: {lowercase_name}")

        # Verify lowercase version does NOT exist
        lowercase_company_in_db = await db.company.find_one({"company_name": lowercase_name})
        assert lowercase_company_in_db is None, "Lowercase company should NOT exist"

        # Prepare subscription data with lowercase company name
        now = datetime.now(timezone.utc)
        subscription_data = {
            "company_name": lowercase_name,
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.10,
            "promotional_units": 100,
            "discount": 0.9,
            "subscription_price": 90.00,
            "start_date": now.isoformat(),
            "end_date": (now + timedelta(days=365)).isoformat(),
            "status": "active"
        }

        # Make request
        response = await http_client.post(
            "/api/subscriptions/",
            json=subscription_data,
            headers=admin_headers
        )

        # Should fail with 400 (case-sensitive matching)
        assert response.status_code == 400, \
            f"Expected 400 for case-mismatch, got {response.status_code}: {response.text}"

        data = response.json()
        error_detail = data.get("detail", "")
        assert lowercase_name in error_detail, f"Error should contain attempted company name: {error_detail}"

        print(f"✅ Test passed: Company name matching is case-sensitive")


    async def test_create_multiple_subscriptions_same_company(
        self, http_client, db, admin_headers, test_company
    ):
        """
        Test 1.5: Can create multiple subscriptions for same company.

        Scenario:
        - Company exists
        - Create first subscription - SUCCESS
        - Create second subscription for same company - SUCCESS
        - Expected: Both subscriptions exist in database
        """
        company_name = test_company["company_name"]
        subscription_ids = []

        try:
            # Create first subscription
            now = datetime.now(timezone.utc)
            subscription_data_1 = {
                "company_name": company_name,
                "subscription_unit": "page",
                "units_per_subscription": 1000,
                "price_per_unit": 0.10,
                "promotional_units": 100,
                "discount": 0.9,
                "subscription_price": 90.00,
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=365)).isoformat(),
                "status": "active"
            }

            response_1 = await http_client.post(
                "/api/subscriptions/",
                json=subscription_data_1,
                headers=admin_headers
            )

            assert response_1.status_code == 201
            subscription_id_1 = response_1.json()["data"]["subscription_id"]
            subscription_ids.append(subscription_id_1)
            print(f"✅ Created subscription 1: {subscription_id_1}")

            # Create second subscription for same company
            subscription_data_2 = {
                "company_name": company_name,
                "subscription_unit": "word",  # Different unit
                "units_per_subscription": 5000,
                "price_per_unit": 0.02,
                "promotional_units": 500,
                "discount": 0.8,
                "subscription_price": 80.00,
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=365)).isoformat(),
                "status": "active"
            }

            response_2 = await http_client.post(
                "/api/subscriptions/",
                json=subscription_data_2,
                headers=admin_headers
            )

            assert response_2.status_code == 201
            subscription_id_2 = response_2.json()["data"]["subscription_id"]
            subscription_ids.append(subscription_id_2)
            print(f"✅ Created subscription 2: {subscription_id_2}")

            # Verify both subscriptions exist in database
            count = await db.subscriptions.count_documents({"company_name": company_name})
            assert count >= 2, f"Should have at least 2 subscriptions for {company_name}"

            print(f"✅ Test passed: Multiple subscriptions created for same company")

        finally:
            # Cleanup: Delete test subscriptions
            for sub_id in subscription_ids:
                await db.subscriptions.delete_one({"_id": ObjectId(sub_id)})
                print(f"🗑️ Cleaned up subscription: {sub_id}")


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SUBSCRIPTION CREATION - COMPANY VALIDATION TESTS")
    print("=" * 80)
    print("\nRunning tests against:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Database: {MONGODB_URI}/{DATABASE_NAME}")
    print("\nNOTE: Tests use test database and clean up after themselves")
    print("=" * 80)
    print("\n")
