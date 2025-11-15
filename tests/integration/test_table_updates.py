"""
INTEGRATION TESTS FOR TABLE UPDATE OPERATIONS - REAL DATABASE + REAL API

Tests UPDATE operations on:
- Subscriptions
- Company Users
- Companies

Using REAL FastAPI server and REAL MongoDB database.
NO MOCKS - Full end-to-end testing.
"""

import pytest
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta
import asyncio

# Configuration
API_BASE_URL = "http://localhost:8000"
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation"
DATABASE_NAME = "translation_test"

# Admin users are stored in production database
MONGODB_URI_PROD = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME_PROD = "translation"

# Test data prefixes to identify test records
TEST_PREFIX = "TEST_UPDATE_"
TEST_COMPANY = f"{TEST_PREFIX}TestCorp"
TEST_USER_EMAIL = f"{TEST_PREFIX}user@testcorp.com"

@pytest.fixture(scope="function")
async def db():
    """Connect to REAL test database."""
    client = AsyncIOMotorClient(MONGODB_URI)
    database = client[DATABASE_NAME]
    yield database
    client.close()

@pytest.fixture(scope="function")
async def http_client(db):
    """HTTP client for REAL API calls with authentication."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        # Create a test admin user with known password
        # Note: Admins are stored in PRODUCTION database, not test database
        import bcrypt
        test_admin_email = f"{TEST_PREFIX}admin@test.com"
        test_password = "TestAdmin123"

        # Hash password
        password_bytes = test_password.encode('utf-8')
        salt = bcrypt.gensalt(12)
        password_hash = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

        # Connect to production database for admin creation
        prod_client = AsyncIOMotorClient(MONGODB_URI_PROD)
        prod_db = prod_client[DATABASE_NAME_PROD]

        # Create admin in PRODUCTION database (where auth service looks)
        await prod_db['iris-admins'].delete_many({"user_email": test_admin_email})
        await prod_db['iris-admins'].insert_one({
            "user_name": "Test Admin",
            "user_email": test_admin_email,
            "password": password_hash,
            "permission_level": "admin",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })
        print(f"✅ Created test admin in PRODUCTION db: {test_admin_email}")

        # Login with test admin
        login_response = await client.post(
            "/login/admin",
            json={
                "email": test_admin_email,
                "password": test_password
            }
        )

        if login_response.status_code == 200:
            data = login_response.json()
            if data.get("success") and "data" in data:
                token = data["data"]["authToken"]
                # Add Authorization header to all subsequent requests
                client.headers["Authorization"] = f"Bearer {token}"
                print(f"✅ Authenticated successfully with admin token")
        else:
            print(f"❌ Login failed: {login_response.status_code} - {login_response.text}")

        yield client

        # Cleanup test admin from production database
        await prod_db['iris-admins'].delete_many({"user_email": test_admin_email})
        prod_client.close()

@pytest.fixture(scope="function")
async def cleanup_test_data(db):
    """Cleanup test data before and after tests."""
    # Cleanup before test
    await db.subscriptions.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})
    await db.company_users.delete_many({"email": {"$regex": f"^{TEST_PREFIX}"}})
    await db.companies.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})
    await db.company.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})

    yield

    # Cleanup after test
    await db.subscriptions.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})
    await db.company_users.delete_many({"email": {"$regex": f"^{TEST_PREFIX}"}})
    await db.companies.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})
    await db.company.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}"}})

# ============================================================================
# SUBSCRIPTION UPDATE TESTS
# ============================================================================

@pytest.mark.asyncio
class TestSubscriptionUpdates:
    """Test UPDATE operations on subscriptions table."""

    async def test_update_subscription_status(self, http_client, db, cleanup_test_data):
        """Test updating subscription status from active to inactive."""

        # 1. CREATE test subscription in database
        test_subscription = {
            "company_name": TEST_COMPANY,
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.05,
            "promotional_units": 100,
            "discount": 1.0,
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc) + timedelta(days=365),
            "status": "active",
            "usage_periods": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await db.subscriptions.insert_one(test_subscription)
        subscription_id = str(result.inserted_id)
        print(f"✅ Created test subscription: {subscription_id}")

        # 2. VERIFY subscription exists with status=active
        before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert before is not None
        assert before["status"] == "active"
        print(f"✅ Verified initial status: {before['status']}")

        # 3. UPDATE via API - change status to inactive
        update_data = {"status": "inactive"}
        response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data
        )

        # 4. VERIFY API response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("success") is True
        print(f"✅ API update successful: {data}")

        # 5. VERIFY database was updated
        after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert after is not None
        assert after["status"] == "inactive"
        assert after["status"] != before["status"]
        print(f"✅ Database verified: status changed from '{before['status']}' to '{after['status']}'")

    async def test_update_subscription_units_and_price(self, http_client, db, cleanup_test_data):
        """Test updating units_per_subscription and price_per_unit."""

        # CREATE test subscription
        test_sub = {
            "company_name": f"{TEST_PREFIX}UpdateTest",
            "subscription_unit": "word",
            "units_per_subscription": 5000,
            "price_per_unit": 0.03,
            "promotional_units": 0,
            "discount": 1.0,
            "start_date": datetime.now(timezone.utc),
            "end_date": datetime.now(timezone.utc) + timedelta(days=180),
            "status": "active",
            "usage_periods": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await db.subscriptions.insert_one(test_sub)
        sub_id = str(result.inserted_id)

        # Get original values
        before = await db.subscriptions.find_one({"_id": ObjectId(sub_id)})
        original_units = before["units_per_subscription"]
        original_price = before["price_per_unit"]
        print(f"Original: units={original_units}, price=${original_price}")

        # UPDATE via API
        update_data = {
            "units_per_subscription": 10000,
            "price_per_unit": 0.04
        }
        response = await http_client.patch(f"/api/subscriptions/{sub_id}", json=update_data)

        # VERIFY response
        assert response.status_code == 200

        # VERIFY database
        after = await db.subscriptions.find_one({"_id": ObjectId(sub_id)})
        assert after["units_per_subscription"] == 10000
        assert after["price_per_unit"] == 0.04
        assert after["units_per_subscription"] != original_units
        assert after["price_per_unit"] != original_price
        print(f"✅ Updated: units={after['units_per_subscription']}, price=${after['price_per_unit']}")

# ============================================================================
# COMPANY USER UPDATE TESTS
# ============================================================================

@pytest.mark.asyncio
class TestCompanyUserUpdates:
    """Test UPDATE operations on company_users table."""

    async def test_create_company_user(self, http_client, db, cleanup_test_data):
        """Test creating a new company user via API."""

        # 1. CREATE company first in BOTH collections (the API checks 'company' collection)
        test_company = {
            "company_name": TEST_COMPANY,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "description": "Test company for integration tests",
            "address": {
                "address0": "123 Test St",
                "city": "Test City",
                "state": "NY",
                "postal_code": "10001",
                "country": "USA"
            }
        }
        # Insert into 'company' collection (what the API checks)
        await db.company.insert_one(test_company.copy())
        # Also insert into 'companies' collection for consistency
        await db.companies.insert_one(test_company.copy())
        print(f"✅ Created test company: {TEST_COMPANY}")

        # 2. CREATE user via API
        user_data = {
            "user_name": "Test User",
            "email": TEST_USER_EMAIL,
            "phone_number": "+1234567890",
            "password": "TestPass123",
            "permission_level": "user",
            "status": "active"
        }

        response = await http_client.post(
            f"/api/company-users?company_name={TEST_COMPANY}",
            json=user_data
        )

        # 3. VERIFY API response
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        print(f"✅ API response: {data}")

        # 4. VERIFY database
        user = await db.company_users.find_one({"email": TEST_USER_EMAIL})
        assert user is not None
        assert user["user_name"] == "Test User"
        assert user["company_name"] == TEST_COMPANY
        assert user["permission_level"] == "user"
        assert user["status"] == "active"
        print(f"✅ Database verified: User created with email {user['email']}")

# ============================================================================
# COMPANY UPDATE TESTS
# ============================================================================

@pytest.mark.asyncio
class TestCompanyUpdates:
    """Test UPDATE operations on companies table."""

    async def test_get_companies(self, http_client, db, cleanup_test_data):
        """Test getting companies list (GET endpoint exists)."""

        # CREATE test companies
        test_companies = [
            {"company_name": f"{TEST_PREFIX}Alpha", "status": "active", "created_at": datetime.now(timezone.utc)},
            {"company_name": f"{TEST_PREFIX}Beta", "status": "active", "created_at": datetime.now(timezone.utc)}
        ]
        await db.companies.insert_many(test_companies)
        print(f"✅ Created {len(test_companies)} test companies")

        # GET via API
        response = await http_client.get("/api/v1/companies")

        # VERIFY response
        assert response.status_code == 200
        response_data = response.json()

        # Response structure: {"success": true, "data": {"companies": [...]}}
        assert response_data.get("success") is True
        assert "data" in response_data
        assert "companies" in response_data["data"]

        companies = response_data["data"]["companies"]

        # VERIFY test companies are in response
        company_names = [c["company_name"] for c in companies]
        assert f"{TEST_PREFIX}Alpha" in company_names
        assert f"{TEST_PREFIX}Beta" in company_names
        print(f"✅ API returned {len(companies)} companies including our test companies")

# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("INTEGRATION TESTS FOR TABLE UPDATES - REAL DATABASE + REAL API")
    print("=" * 80)
    print(f"API: {API_BASE_URL}")
    print(f"Database: {MONGODB_URI}/{DATABASE_NAME}")
    print("=" * 80)
    print()

    # Run pytest programmatically
    pytest.main([__file__, "-v", "-s", "--tb=short"])
