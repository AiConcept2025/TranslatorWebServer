"""
INTEGRATION TESTS FOR TABLE UPDATE OPERATIONS - USING REAL HTTP API ENDPOINTS

Tests UPDATE operations via HTTP API on:
- Subscriptions (POST, GET, PATCH)
- Company Users (POST, GET)
- Companies (GET)

Using REAL web server HTTP endpoints instead of direct database operations.
Tests make actual HTTP requests to the running FastAPI server.
Uses the REAL TEST database (translation_test) for all operations.

NO MOCKS - Real API + Real Database testing as per requirements.
"""

import pytest
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone
import uuid

# Configuration - CRITICAL: Use test database, not production
API_BASE_URL = "http://localhost:8000"
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation"
DATABASE_NAME = "translation_test"

# Test data prefixes to identify test records
TEST_PREFIX = "TEST_API_"
TEST_COMPANY = f"{TEST_PREFIX}TestCorp"
TEST_USER_EMAIL = f"{TEST_PREFIX}user@testcorp.com"

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls to running server."""
    async_client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0)
    yield async_client
    await async_client.aclose()


@pytest.fixture(scope="function")
async def db(test_db):
    """
    Connect to REAL test database for verification and cleanup.

    Uses test_db fixture from conftest.py to ensure we use translation_test.
    """
    yield test_db


@pytest.fixture(scope="function")
async def cleanup_test_data(test_db):
    """
    Cleanup test data before and after tests.

    Uses test_db fixture from conftest.py to ensure we clean translation_test.
    """
    # Cleanup before test
    await test_db.subscriptions.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})
    await test_db.company_users.delete_many({"email": {"$regex": f"^{TEST_PREFIX}"}})
    await test_db.companies.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})
    await test_db.company.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})

    yield

    # Cleanup after test
    await test_db.subscriptions.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})
    await test_db.company_users.delete_many({"email": {"$regex": f"^{TEST_PREFIX}"}})
    await test_db.companies.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})
    await test_db.company.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})


@pytest.fixture(scope="function")
async def test_company(db, cleanup_test_data):
    """Create test company via database (no POST /companies endpoint)."""
    company_doc = {
        "company_name": TEST_COMPANY,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "description": "Test company for API integration tests",
        "address": {
            "address0": "123 Test Street",
            "city": "Test City",
            "state": "NY",
            "postal_code": "10001",
            "country": "USA"
        }
    }

    # Insert into both collections (system uses both)
    await db.company.insert_one(company_doc.copy())
    await db.companies.insert_one(company_doc.copy())
    print(f"✅ Created test company via database: {TEST_COMPANY}")

    return TEST_COMPANY


@pytest.fixture(scope="function")
async def admin_token(http_client, db, test_company):
    """
    Create admin user and get authentication token.

    This fixture:
    1. Creates admin user via database (auth required for API)
    2. Authenticates and returns JWT token
    """
    import bcrypt

    admin_email = f"{TEST_PREFIX}admin@testcorp.com"

    # Check if admin already exists
    existing_admin = await db.company_users.find_one({"email": admin_email})

    if not existing_admin:
        password = "AdminPass123"
        salt = bcrypt.gensalt(12)
        password_hash = bcrypt.hashpw(password.encode('utf-8')[:72], salt).decode('utf-8')

        admin_doc = {
            "user_id": f"user_{uuid.uuid4().hex[:16]}",
            "company_name": TEST_COMPANY,
            "user_name": "Test Admin",
            "email": admin_email,
            "phone_number": "+1234567890",
            "permission_level": "admin",
            "status": "active",
            "password_hash": password_hash,
            "last_login": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        await db.company_users.insert_one(admin_doc)
        print(f"✅ Created admin user via database: {admin_email}")

    # Login to get token
    # Note: Use /login/corporate for enterprise users in company_users collection
    # The endpoint expects camelCase field names due to Pydantic aliases
    login_response = await http_client.post(
        "/login/corporate",
        json={
            "companyName": TEST_COMPANY,
            "password": "AdminPass123",
            "userFullName": "Test Admin",
            "userEmail": admin_email,
            "loginDateTime": datetime.now(timezone.utc).isoformat()
        }
    )

    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code} - {login_response.text}")
        pytest.skip(f"Login failed: {login_response.status_code}")

    login_data = login_response.json()
    # Corporate login returns token in data.authToken
    token = login_data.get("data", {}).get("authToken")

    if not token:
        print(f"❌ No token in response: {login_data}")
        pytest.skip("No access token in login response")

    print(f"✅ Admin authenticated, got token")
    return token


# ============================================================================
# SUBSCRIPTION UPDATE TESTS (VIA HTTP API)
# ============================================================================

@pytest.mark.asyncio
class TestSubscriptionAPIUpdates:
    """Test UPDATE operations on subscriptions via HTTP API endpoints."""

    async def test_update_subscription_status(self, http_client, db, test_company, admin_token):
        """Test updating subscription status from active to inactive via PATCH API."""

        # 1. CREATE test subscription via API (POST request)
        print("\n" + "=" * 80)
        print("STEP 1: CREATE subscription via POST API")
        print("=" * 80)

        create_data = {
            "company_name": TEST_COMPANY,
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.05,
            "promotional_units": 100,
            "discount": 1.0,
            "subscription_price": 50.0,
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-12-31T23:59:59Z",
            "status": "active"
        }

        create_response = await http_client.post(
            "/api/subscriptions/",
            json=create_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        print(f"📤 POST /api/subscriptions/ - Status: {create_response.status_code}")
        assert create_response.status_code in [200, 201], \
            f"Failed to create subscription: {create_response.status_code} - {create_response.text}"

        created_data = create_response.json()
        print(f"📥 Response: {created_data}")

        # Extract subscription_id from response
        subscription_id = created_data.get("data", {}).get("subscription_id") or \
                         created_data.get("subscription_id") or \
                         created_data.get("_id") or \
                         created_data.get("id")

        assert subscription_id, f"No subscription_id in response: {created_data}"
        print(f"✅ Created subscription via API: {subscription_id}")

        # 2. GET original state via API
        print("\n" + "=" * 80)
        print("STEP 2: GET original state via GET API")
        print("=" * 80)

        get_response = await http_client.get(
            f"/api/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        print(f"📤 GET /api/subscriptions/{subscription_id} - Status: {get_response.status_code}")
        assert get_response.status_code == 200, \
            f"Failed to get subscription: {get_response.status_code} - {get_response.text}"

        get_data = get_response.json()
        before = get_data.get("data", get_data)
        print(f"📥 Original status: {before.get('status')}")

        assert before["status"] == "active", f"Expected status=active, got {before['status']}"
        print(f"✅ Verified initial status via API: {before['status']}")

        # 3. UPDATE via API (PATCH request)
        print("\n" + "=" * 80)
        print("STEP 3: UPDATE subscription via PATCH API")
        print("=" * 80)

        update_data = {"status": "inactive"}

        update_response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        print(f"📤 PATCH /api/subscriptions/{subscription_id}")
        print(f"📦 Update Data: {update_data}")
        print(f"📥 Response Status: {update_response.status_code}")
        assert update_response.status_code == 200, \
            f"Failed to update subscription: {update_response.status_code} - {update_response.text}"

        update_result = update_response.json()
        print(f"✅ Updated subscription via API")

        # 4. GET updated state via API
        print("\n" + "=" * 80)
        print("STEP 4: VERIFY update via GET API")
        print("=" * 80)

        get_after_response = await http_client.get(
            f"/api/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        print(f"📤 GET /api/subscriptions/{subscription_id} - Status: {get_after_response.status_code}")
        assert get_after_response.status_code == 200, \
            f"Failed to get updated subscription: {get_after_response.status_code} - {get_after_response.text}"

        get_after_data = get_after_response.json()
        after = get_after_data.get("data", get_after_data)
        print(f"📥 Updated status: {after.get('status')}")

        assert after["status"] == "inactive", f"Expected status=inactive, got {after['status']}"
        assert after["status"] != before["status"], \
            f"Status did not change: {before['status']} == {after['status']}"
        print(f"✅ Verified status changed via API: {before['status']} → {after['status']}")

        # 5. Verify in database (optional but recommended)
        print("\n" + "=" * 80)
        print("STEP 5: VERIFY in database")
        print("=" * 80)

        db_record = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert db_record is not None, f"Subscription not found in database: {subscription_id}"
        assert db_record["status"] == "inactive", \
            f"Database status mismatch: expected inactive, got {db_record['status']}"
        print(f"✅ Database confirmed: status = {db_record['status']}")
        print("=" * 80 + "\n")

    async def test_update_subscription_units_and_price(self, http_client, db, test_company, admin_token):
        """Test updating units_per_subscription and price_per_unit via PATCH API."""

        # CREATE test subscription via API
        print("\n" + "=" * 80)
        print("TEST: Update subscription units and price")
        print("=" * 80)

        create_data = {
            "company_name": f"{TEST_PREFIX}UpdateTest",
            "subscription_unit": "word",
            "units_per_subscription": 5000,
            "price_per_unit": 0.03,
            "promotional_units": 0,
            "discount": 1.0,
            "subscription_price": 150.0,
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-06-30T23:59:59Z",
            "status": "active"
        }

        # Create company for this subscription
        company_doc = {
            "company_name": f"{TEST_PREFIX}UpdateTest",
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "description": "Test company for update test"
        }
        await db.company.insert_one(company_doc.copy())
        await db.companies.insert_one(company_doc.copy())

        create_response = await http_client.post(
            "/api/subscriptions/",
            json=create_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert create_response.status_code in [200, 201], \
            f"Failed to create: {create_response.status_code} - {create_response.text}"

        created_data = create_response.json()
        subscription_id = created_data.get("data", {}).get("subscription_id") or \
                         created_data.get("subscription_id")

        print(f"✅ Created subscription: {subscription_id}")

        # Get original values via API
        get_response = await http_client.get(
            f"/api/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_response.status_code == 200

        before_data = get_response.json()
        before = before_data.get("data", before_data)

        original_units = before["units_per_subscription"]
        original_price = before["price_per_unit"]
        print(f"📊 Original: units={original_units}, price=${original_price}")

        # UPDATE via API (PATCH request)
        update_data = {
            "units_per_subscription": 10000,
            "price_per_unit": 0.04
        }

        update_response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert update_response.status_code == 200, \
            f"Update failed: {update_response.status_code} - {update_response.text}"
        print(f"✅ Updated via API")

        # VERIFY update via API
        get_after_response = await http_client.get(
            f"/api/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert get_after_response.status_code == 200

        after_data = get_after_response.json()
        after = after_data.get("data", after_data)

        assert after["units_per_subscription"] == 10000, \
            f"Units not updated: {after['units_per_subscription']}"
        assert after["price_per_unit"] == 0.04, \
            f"Price not updated: {after['price_per_unit']}"
        assert after["units_per_subscription"] != original_units
        assert after["price_per_unit"] != original_price

        print(f"✅ Updated: units={after['units_per_subscription']}, price=${after['price_per_unit']}")

        # Verify in database
        db_record = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert db_record["units_per_subscription"] == 10000
        assert db_record["price_per_unit"] == 0.04
        print(f"✅ Database confirmed: units={db_record['units_per_subscription']}, price={db_record['price_per_unit']}")
        print("=" * 80 + "\n")


# ============================================================================
# COMPANY USER UPDATE TESTS (VIA HTTP API)
# ============================================================================

@pytest.mark.asyncio
class TestCompanyUserAPIUpdates:
    """Test CREATE and GET operations on company_users via HTTP API."""

    async def test_create_and_verify_company_user(self, http_client, db, test_company):
        """Test creating and verifying a company user via POST and GET APIs."""

        print("\n" + "=" * 80)
        print("TEST: Create and verify company user")
        print("=" * 80)

        # CREATE user via API
        print("STEP 1: Create user via POST API")
        user_data = {
            "user_name": "Test User",
            "email": TEST_USER_EMAIL,
            "phone_number": "+1234567890",
            "password": "TestPass123",
            "permission_level": "user",
            "status": "active"
        }

        create_response = await http_client.post(
            f"/api/company-users?company_name={TEST_COMPANY}",
            json=user_data
        )

        print(f"📤 POST /api/company-users?company_name={TEST_COMPANY}")
        print(f"📦 Request Data: {user_data}")
        print(f"📥 Response Status: {create_response.status_code}")

        assert create_response.status_code in [200, 201], \
            f"Failed to create user: {create_response.status_code} - {create_response.text}"

        create_result = create_response.json()
        print(f"📥 Response: {create_result}")
        print(f"✅ Created user via API")

        # GET user via API to verify creation
        print("\nSTEP 2: Verify user via GET API")
        get_users_response = await http_client.get(
            f"/api/company-users?company_name={TEST_COMPANY}"
        )

        print(f"📤 GET /api/company-users?company_name={TEST_COMPANY}")
        print(f"📥 Response Status: {get_users_response.status_code}")

        assert get_users_response.status_code == 200, \
            f"Failed to get users: {get_users_response.status_code} - {get_users_response.text}"

        users = get_users_response.json()
        print(f"📥 Response: {users}")
        print(f"📊 Found {len(users)} user(s)")

        # Find our test user
        test_user = next((u for u in users if u["email"] == TEST_USER_EMAIL.lower()), None)
        assert test_user is not None, f"Test user not found in response: {TEST_USER_EMAIL}"
        assert test_user["status"] == "active", f"Expected status=active, got {test_user['status']}"
        assert test_user["user_name"] == "Test User"
        assert test_user["company_name"] == TEST_COMPANY

        print(f"✅ Verified user creation via API:")
        print(f"   - user_id: {test_user['user_id']}")
        print(f"   - email: {test_user['email']}")
        print(f"   - status: {test_user['status']}")
        print(f"   - company: {test_user['company_name']}")

        # Verify in database
        print("\nSTEP 3: Verify in database")
        db_user = await db.company_users.find_one({"email": TEST_USER_EMAIL.lower()})
        assert db_user is not None, "User not found in database"
        assert db_user["status"] == "active"
        assert db_user["user_name"] == "Test User"

        print(f"✅ Database confirmed:")
        print(f"   - email: {db_user['email']}")
        print(f"   - status: {db_user['status']}")
        print(f"   - company: {db_user['company_name']}")
        print("=" * 80 + "\n")


# ============================================================================
# COMPANY UPDATE TESTS (VIA HTTP API)
# ============================================================================

@pytest.mark.asyncio
class TestCompanyAPIUpdates:
    """Test GET operations on companies via HTTP API."""

    async def test_query_companies_via_api(self, http_client, db, cleanup_test_data):
        """Test querying companies via GET API endpoint."""

        print("\n" + "=" * 80)
        print("TEST: Query companies via API")
        print("=" * 80)

        # CREATE test companies via database (no POST endpoint)
        print("STEP 1: Create test companies via database")
        test_companies = [
            {
                "company_name": f"{TEST_PREFIX}Alpha",
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "description": "Alpha company"
            },
            {
                "company_name": f"{TEST_PREFIX}Beta",
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "description": "Beta company"
            }
        ]

        await db.companies.insert_many([c.copy() for c in test_companies])
        await db.company.insert_many([c.copy() for c in test_companies])
        print(f"✅ Created {len(test_companies)} test companies via database")

        # QUERY companies via API
        print("\nSTEP 2: Query companies via GET API")
        get_response = await http_client.get("/api/v1/companies")

        print(f"📤 GET /api/v1/companies")
        print(f"📥 Response Status: {get_response.status_code}")

        assert get_response.status_code == 200, \
            f"Failed to get companies: {get_response.status_code} - {get_response.text}"

        response_data = get_response.json()
        print(f"📥 Response structure: {list(response_data.keys())}")

        companies = response_data.get("data", {}).get("companies", [])

        # Filter for our test companies
        test_company_names = {f"{TEST_PREFIX}Alpha", f"{TEST_PREFIX}Beta"}
        found_companies = [c for c in companies if c["company_name"] in test_company_names]

        print(f"📊 Total companies returned: {len(companies)}")
        print(f"📊 Test companies found: {len(found_companies)}")

        # VERIFY query results
        assert len(found_companies) >= 2, \
            f"Expected at least 2 test companies, found {len(found_companies)}"

        company_names = [c["company_name"] for c in found_companies]
        assert f"{TEST_PREFIX}Alpha" in company_names, "Alpha company not found"
        assert f"{TEST_PREFIX}Beta" in company_names, "Beta company not found"

        print(f"✅ Found test companies via API:")
        for company in found_companies:
            print(f"   - {company['company_name']}: {company.get('description', 'N/A')}")

        # Verify database consistency
        print("\nSTEP 3: Verify database consistency")
        db_companies = await db.companies.find(
            {"company_name": {"$regex": f"^{TEST_PREFIX}"}}
        ).to_list(length=100)

        assert len(db_companies) >= 2, "Companies not in database"
        print(f"✅ Database confirmed: {len(db_companies)} test companies")
        print("=" * 80 + "\n")


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("INTEGRATION TESTS - HTTP API ENDPOINT UPDATES")
    print("=" * 80)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Database: {MONGODB_URI}/{DATABASE_NAME}")
    print("Tests UPDATE operations via real HTTP API endpoints")
    print("=" * 80)
    print()

    # Run pytest programmatically
    pytest.main([__file__, "-v", "-s", "--tb=short"])
