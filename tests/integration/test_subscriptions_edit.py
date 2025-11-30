"""
INTEGRATION TESTS FOR SUBSCRIPTIONS EDIT OPERATIONS - USING REAL DATABASE

These tests make actual HTTP requests to the running server and verify
responses against the REAL MongoDB database (translation_test).

NO MOCKS - Real API + Real Database testing.

Test Coverage:
- PATCH /api/subscriptions/{subscription_id} - Update subscription
- POST /api/subscriptions/{subscription_id}/usage-periods - Add usage period
- POST /api/subscriptions/{subscription_id}/record-usage - Record usage

All tests verify changes in the database after API calls.
"""

import pytest
import httpx
import uuid
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# ============================================================================
# Test Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8000"
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation"
DATABASE_NAME = "translation_test"

# NOTE: These tests require a running server configured for test database
# Server must use translation_test database and valid admin credentials

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def db(test_db):
    """
    Connect to test MongoDB database.

    CRITICAL: Uses test database 'translation_test', NOT production 'translation'.
    Uses test_db fixture from conftest.py to ensure translation_test is used.
    """
    yield test_db


@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls to running server."""
    async_client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0)
    yield async_client
    await async_client.aclose()


@pytest.fixture(scope="function")
async def subscription_auth():
    """
    Get authentication headers for subscription tests.
    Uses admin login endpoint with existing admin credentials.
    """
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        try:
            response = await client.post(
                "/login/admin",
                json={
                    "email": "danishevsky@gmail.com",
                    "password": "Sveta87201120!"
                }
            )
            if response.status_code != 200:
                pytest.skip(f"Auth failed: {response.status_code}")

            data = response.json()
            # Admin login returns token in data.authToken
            token = (
                data.get("data", {}).get("authToken") or
                data.get("access_token") or
                data.get("token")
            )
            if not token:
                pytest.skip("No token in auth response")

            yield {"Authorization": f"Bearer {token}"}
        except httpx.ConnectError:
            pytest.skip("Server not running")


@pytest.fixture(scope="function")
async def test_subscription(db, test_company):
    """
    Create a test subscription in the database for testing.

    Returns the created subscription document.
    Automatically cleaned up after test.

    Uses test_company fixture for referential integrity.
    """
    collection = db.subscriptions

    now = datetime.now(timezone.utc)

    subscription_doc = {
        "company_name": test_company["company_name"],  # Valid company reference
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        "price_per_unit": 0.10,
        "promotional_units": 100,
        "discount": 0.9,
        "subscription_price": 90.00,
        "start_date": now,
        "end_date": now + timedelta(days=365),
        "status": "active",
        "usage_periods": [],
        "created_at": now,
        "updated_at": now
    }

    result = await collection.insert_one(subscription_doc)
    subscription_doc["_id"] = result.inserted_id

    print(f"✅ Created test subscription: {result.inserted_id} (company: {test_company['company_name']})")

    yield subscription_doc

    # Cleanup: Delete test subscription
    await collection.delete_one({"_id": result.inserted_id})
    print(f"🗑️ Cleaned up test subscription: {result.inserted_id}")


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
# Test Class: Update Subscription
# ============================================================================

@pytest.mark.asyncio
class TestUpdateSubscription:
    """Test PATCH /api/subscriptions/{subscription_id} endpoint."""

    async def test_update_subscription_status(self, http_client, db, subscription_auth, test_subscription):
        """Test 1.1: Update subscription status from active to inactive."""
        subscription_id = str(test_subscription["_id"])
        original_status = test_subscription["status"]

        # Step 1: Get existing record from database
        record_before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_before is not None
        assert record_before["status"] == original_status
        print(f"📊 Before: status={record_before['status']}")

        # Step 2: Prepare update data
        update_data = {"status": "inactive"}

        # Step 3: Make PATCH request
        response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers=subscription_auth
        )

        # Step 4: Assert response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["status"] == "inactive"

        # Step 5: Verify database was updated
        record_after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_after["status"] == "inactive"
        assert record_after["status"] != original_status
        assert record_after["updated_at"] > record_before["updated_at"]

        # Step 6: Log results
        print(f"✅ Test passed: Status updated from '{original_status}' to '{record_after['status']}'")


    async def test_update_subscription_units(self, http_client, db, subscription_auth, test_subscription):
        """Test 1.2: Update units_per_subscription."""
        subscription_id = str(test_subscription["_id"])
        original_units = test_subscription["units_per_subscription"]
        new_units = 2000

        # Get record before
        record_before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_before["units_per_subscription"] == original_units
        print(f"📊 Before: units_per_subscription={record_before['units_per_subscription']}")

        # Update data
        update_data = {"units_per_subscription": new_units}

        # Make request
        response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers=subscription_auth
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database
        record_after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_after["units_per_subscription"] == new_units
        assert record_after["units_per_subscription"] != original_units

        print(f"✅ Test passed: Units updated from {original_units} to {record_after['units_per_subscription']}")


    async def test_update_subscription_price(self, http_client, db, subscription_auth, test_subscription):
        """Test 1.3: Update price_per_unit."""
        subscription_id = str(test_subscription["_id"])
        original_price = test_subscription["price_per_unit"]
        new_price = 0.15

        # Get record before
        record_before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_before["price_per_unit"] == original_price
        print(f"📊 Before: price_per_unit={record_before['price_per_unit']}")

        # Update data
        update_data = {"price_per_unit": new_price}

        # Make request
        response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers=subscription_auth
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database
        record_after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_after["price_per_unit"] == new_price
        assert record_after["price_per_unit"] != original_price

        print(f"✅ Test passed: Price updated from {original_price} to {record_after['price_per_unit']}")


    async def test_update_subscription_promotional_units(self, http_client, db, subscription_auth, test_subscription):
        """Test 1.4: Update promotional_units."""
        subscription_id = str(test_subscription["_id"])
        original_promotional = test_subscription["promotional_units"]
        new_promotional = 200

        # Get record before
        record_before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_before["promotional_units"] == original_promotional
        print(f"📊 Before: promotional_units={record_before['promotional_units']}")

        # Update data
        update_data = {"promotional_units": new_promotional}

        # Make request
        response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers=subscription_auth
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database
        record_after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_after["promotional_units"] == new_promotional
        assert record_after["promotional_units"] != original_promotional

        print(f"✅ Test passed: Promotional units updated from {original_promotional} to {record_after['promotional_units']}")


    async def test_update_subscription_dates(self, http_client, db, subscription_auth, test_subscription):
        """Test 1.5: Update start_date and end_date."""
        subscription_id = str(test_subscription["_id"])
        original_start = test_subscription["start_date"]
        original_end = test_subscription["end_date"]

        new_start = datetime.now(timezone.utc) + timedelta(days=30)
        new_end = datetime.now(timezone.utc) + timedelta(days=395)

        # Get record before
        record_before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        print(f"📊 Before: start_date={record_before['start_date']}, end_date={record_before['end_date']}")

        # Update data
        update_data = {
            "start_date": new_start.isoformat(),
            "end_date": new_end.isoformat()
        }

        # Make request
        response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers=subscription_auth
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database
        record_after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        # Compare timestamps (allow small tolerance for serialization)
        # MongoDB may store naive or aware datetimes, so convert both to naive for comparison
        db_start = record_after["start_date"]
        db_end = record_after["end_date"]
        if db_start.tzinfo is None:
            new_start_naive = new_start.replace(tzinfo=None)
            new_end_naive = new_end.replace(tzinfo=None)
        else:
            new_start_naive = new_start
            new_end_naive = new_end
            db_start = db_start
            db_end = db_end
        assert abs((db_start - new_start_naive).total_seconds()) < 2
        assert abs((db_end - new_end_naive).total_seconds()) < 2

        print(f"✅ Test passed: Dates updated successfully")


    async def test_update_subscription_multiple_fields(self, http_client, db, subscription_auth, test_subscription):
        """Test 1.6: Update multiple fields at once."""
        subscription_id = str(test_subscription["_id"])

        # Get record before
        record_before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        print(f"📊 Before: status={record_before['status']}, units={record_before['units_per_subscription']}, price={record_before['price_per_unit']}")

        # Update multiple fields
        update_data = {
            "status": "inactive",
            "units_per_subscription": 3000,
            "price_per_unit": 0.12,
            "promotional_units": 300
        }

        # Make request
        response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers=subscription_auth
        )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database - all fields updated
        record_after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        assert record_after["status"] == "inactive"
        assert record_after["units_per_subscription"] == 3000
        assert record_after["price_per_unit"] == 0.12
        assert record_after["promotional_units"] == 300

        print(f"✅ Test passed: Multiple fields updated successfully")


    async def test_update_nonexistent_subscription(self, http_client, subscription_auth):
        """Test 1.7: Update non-existent subscription returns 404."""
        fake_id = str(ObjectId())

        update_data = {"status": "inactive"}

        # Make request
        response = await http_client.patch(
            f"/api/subscriptions/{fake_id}",
            json=update_data,
            headers=subscription_auth
        )

        # Verify 404 error
        assert response.status_code == 404

        print(f"✅ Test passed: 404 returned for non-existent subscription")


    async def test_update_subscription_invalid_data(self, http_client, subscription_auth, test_subscription):
        """Test 1.8: Invalid data returns 422 validation error."""
        subscription_id = str(test_subscription["_id"])

        # Invalid status value
        update_data = {"status": "invalid_status"}

        # Make request
        response = await http_client.patch(
            f"/api/subscriptions/{subscription_id}",
            json=update_data,
            headers=subscription_auth
        )

        # Verify 422 validation error
        assert response.status_code == 422

        print(f"✅ Test passed: 422 returned for invalid data")


# ============================================================================
# Test Class: Usage Periods
# ============================================================================

@pytest.mark.asyncio
class TestUsagePeriods:
    """Test usage period operations."""

    async def test_add_usage_period(self, http_client, db, subscription_auth, test_subscription):
        """Test 2.1: Add new usage period successfully."""
        subscription_id = str(test_subscription["_id"])

        # Get record before
        record_before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        original_periods_count = len(record_before.get("usage_periods", []))
        print(f"📊 Before: usage_periods count={original_periods_count}")

        # Prepare usage period data
        now = datetime.now(timezone.utc)
        period_data = {
            "period_start": now.isoformat(),
            "period_end": (now + timedelta(days=30)).isoformat(),
            "units_allocated": 1000
        }

        # Make request
        response = await http_client.post(
            f"/api/subscriptions/{subscription_id}/usage-periods",
            json=period_data,
            headers=subscription_auth
        )

        # Verify response
        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True

        # Verify database
        record_after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        new_periods_count = len(record_after.get("usage_periods", []))
        assert new_periods_count == original_periods_count + 1

        # Verify last period has correct data
        last_period = record_after["usage_periods"][-1]
        assert last_period["units_allocated"] == 1000
        assert last_period["units_used"] == 0

        print(f"✅ Test passed: Usage period added successfully (count: {original_periods_count} → {new_periods_count})")


    async def test_add_usage_period_invalid_dates(self, http_client, subscription_auth, test_subscription):
        """Test 2.2: Invalid period dates return validation error."""
        subscription_id = str(test_subscription["_id"])

        now = datetime.now(timezone.utc)
        # period_end BEFORE period_start (invalid)
        period_data = {
            "period_start": now.isoformat(),
            "period_end": (now - timedelta(days=30)).isoformat(),
            "units_allocated": 1000
        }

        # Make request
        response = await http_client.post(
            f"/api/subscriptions/{subscription_id}/usage-periods",
            json=period_data,
            headers=subscription_auth
        )

        # Verify error (should be 400 or 422)
        assert response.status_code in [400, 422]

        print(f"✅ Test passed: Invalid dates rejected with {response.status_code}")


    async def test_record_usage(self, http_client, db, subscription_auth, test_subscription):
        """Test 2.3: Record usage successfully."""
        subscription_id = str(test_subscription["_id"])

        # First, add a usage period (requires auth)
        now = datetime.now(timezone.utc)
        period_data = {
            "period_start": now.isoformat(),
            "period_end": (now + timedelta(days=30)).isoformat(),
            "units_allocated": 1000
        }

        period_response = await http_client.post(
            f"/api/subscriptions/{subscription_id}/usage-periods",
            json=period_data,
            headers=subscription_auth
        )

        if period_response.status_code != 201:
            print(f"⚠️ Test skipped: Could not create usage period ({period_response.status_code})")
            pytest.skip("Could not create usage period")

        # Get subscription with usage period
        record_before = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        last_period_before = record_before["usage_periods"][-1]
        original_used_units = last_period_before["units_used"]
        print(f"📊 Before: units_used={original_used_units}")

        # Record usage
        usage_data = {
            "units_to_add": 50,
            "use_promotional_units": False
        }

        # Make request
        response = await http_client.post(
            f"/api/subscriptions/{subscription_id}/record-usage",
            json=usage_data,
            headers=subscription_auth
        )

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True

        # Verify database
        record_after = await db.subscriptions.find_one({"_id": ObjectId(subscription_id)})
        last_period_after = record_after["usage_periods"][-1]
        assert last_period_after["units_used"] == original_used_units + 50

        print(f"✅ Test passed: Usage recorded (units_used: {original_used_units} → {last_period_after['units_used']})")


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("SUBSCRIPTIONS EDIT OPERATIONS - INTEGRATION TESTS")
    print("=" * 80)
    print("\nRunning tests against:")
    print(f"  API: {API_BASE_URL}")
    print(f"  Database: {MONGODB_URI}/{DATABASE_NAME}")
    print("\nNOTE: Tests use test database and clean up after themselves")
    print("=" * 80)
    print("\n")
