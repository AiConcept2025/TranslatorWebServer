"""
Integration Tests for Subscription Overdraft Feature

Tests the new overdraft functionality that allows enterprise subscriptions
to go negative when units are insufficient.

Test Coverage:
- Overdraft detection when available units < requested units
- Soft limit warning when balance < -100
- Overdraft fields returned in API response
- Negative balance correctly saved to database
- Individual users NOT affected (still require payment)

CRITICAL: Uses REAL running server + REAL test database
Terminal 1: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
Terminal 2: pytest tests/integration/test_subscription_overdraft.py -v
"""

import pytest
import httpx
import uuid
import base64
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

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
async def test_db():
    """Connect to test MongoDB database."""
    mongo_client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    database = mongo_client[DATABASE_NAME]

    # Verify connection
    try:
        await mongo_client.admin.command('ping')
    except Exception as e:
        pytest.skip(f"Cannot connect to test database: {e}")

    yield database
    mongo_client.close()


@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls to running server."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        # Verify server is running
        try:
            response = await client.get("/health")
            if response.status_code != 200:
                pytest.skip(f"Server not responding: {response.status_code}")
        except httpx.ConnectError:
            pytest.skip("Server not running at http://localhost:8000")

        yield client


@pytest.fixture(scope="function")
async def test_company(test_db):
    """Create a valid test company for referential integrity."""
    company_name = f"TEST-OVERDRAFT-CO-{uuid.uuid4().hex[:8].upper()}"
    company_data = {
        "company_name": company_name,
        "description": "Test company for overdraft integration tests",
        "address": {
            "address0": "123 Overdraft Street",
            "address1": "",
            "postal_code": "12345",
            "state": "NJ",
            "city": "Overdraft City",
            "country": "USA"
        },
        "contact_person": {
            "name": "Overdraft Contact",
            "type": "Primary Contact"
        },
        "phone_number": ["555-OVERDRAFT"],
        "company_url": [],
        "line_of_business": "Testing Overdraft",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.company.insert_one(company_data)
    print(f"✅ Created test company: {company_name}")

    yield company_name

    # Cleanup
    await test_db.company.delete_one({"company_name": company_name})
    print(f"🗑️  Deleted test company: {company_name}")


@pytest.fixture(scope="function")
async def test_subscription_low_balance(test_db, test_company):
    """Create a subscription with only 10 units remaining."""
    subscription_data = {
        "company_name": test_company,
        "subscription_unit": "page",
        "units_per_subscription": 100,
        "price_per_unit": 0.20,
        "promotional_units": 0,
        "discount": 0,
        "subscription_price": 20.0,
        "start_date": datetime.now(timezone.utc),
        "end_date": datetime.now(timezone.utc) + timedelta(days=365),
        "status": "active",
        "usage_periods": [
            {
                "period_start": datetime.now(timezone.utc) - timedelta(days=1),
                "period_end": datetime.now(timezone.utc) + timedelta(days=30),
                "units_allocated": 100,
                "units_used": 90,  # 90 units already used
                "units_remaining": 10,  # Only 10 left
                "promotional_units": 0,
                "last_updated": datetime.now(timezone.utc),
                "period_number": 1
            }
        ],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.subscriptions.insert_one(subscription_data)
    subscription_id = str(result.inserted_id)
    print(f"✅ Created test subscription with 10 units remaining: {subscription_id}")

    yield subscription_id

    # Cleanup
    await test_db.subscriptions.delete_one({"_id": result.inserted_id})
    print(f"🗑️  Deleted test subscription: {subscription_id}")


@pytest.fixture(scope="function")
async def test_user(test_db, test_company):
    """Create a test user for authentication."""
    user_id = f"TEST-USER-{uuid.uuid4().hex[:8]}"
    user_data = {
        "user_id": user_id,
        "company_name": test_company,
        "user_name": "Test Overdraft User",
        "email": f"test-{uuid.uuid4().hex[:8]}@overdraft-test.com",
        "password": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqgKkx.yQu",  # hashed "password"
        "permission_level": "user",
        "status": "active",
        "phone_number": "555-TEST",
        "last_login": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.company_users.insert_one(user_data)
    print(f"✅ Created test user: {user_data['email']}")

    yield user_data

    # Cleanup
    await test_db.company_users.delete_one({"user_id": user_id})
    print(f"🗑️  Deleted test user: {user_data['email']}")


@pytest.fixture(scope="function")
async def auth_headers(http_client, test_user, test_company):
    """Get authentication headers for enterprise requests."""
    login_response = await http_client.post(
        "/api/login/corporate",
        json={
            "companyName": test_company,
            "password": "password",
            "userFullName": test_user["user_name"],
            "userEmail": test_user["email"],
            "loginDateTime": datetime.now(timezone.utc).isoformat()
        }
    )

    if login_response.status_code != 200:
        pytest.skip(f"Cannot authenticate test user: {login_response.status_code}")

    token = login_response.json()["data"]["authToken"]
    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# Test Cases
# ============================================================================

@pytest.mark.asyncio
async def test_overdraft_detected_when_insufficient_units(
    http_client,
    test_db,
    test_subscription_low_balance,
    auth_headers
):
    """
    Test that overdraft is detected when requested units > available units.

    Setup: Subscription with 10 units remaining
    Action: Request 50 pages translation
    Expected: overdraft=True, overdraft_amount=40
    """
    print("\n" + "="*80)
    print("TEST: Overdraft detection with insufficient units")
    print("="*80)

    # Create a small test file (will be counted as 1 page, but we'll request 50 via translation mode)
    file_content = b"Test content for overdraft scenario" * 100
    file_data = base64.b64encode(file_content).decode('utf-8')

    # Make translation request
    response = await http_client.post(
        "/api/translate-user",
        json={
            "files": [
                {
                    "name": "test-overdraft.txt",
                    "content": file_data,
                    "size": len(file_content),
                    "type": "text/plain"
                }
            ] * 50,  # 50 files to simulate 50 pages
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "test@overdraft.com",
            "userName": "Test Overdraft User"
        },
        headers=auth_headers
    )

    print(f"Response status: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    data = response.json()
    assert data["success"] is True

    # Check overdraft fields in pricing info
    pricing = data["data"]["pricing"]
    print(f"Pricing info: {pricing}")

    assert "overdraft" in pricing, "overdraft field missing from pricing"
    assert pricing["overdraft"] is True, "overdraft should be True"
    assert "overdraft_amount" in pricing, "overdraft_amount field missing"
    assert pricing["overdraft_amount"] == 40, f"Expected overdraft_amount=40, got {pricing['overdraft_amount']}"
    assert pricing["available_units"] == 10, f"Expected available_units=10, got {pricing['available_units']}"
    assert pricing["requested_units"] == 50, f"Expected requested_units=50, got {pricing['requested_units']}"

    print("✅ Overdraft correctly detected: 40 units")


@pytest.mark.asyncio
async def test_soft_limit_warning_when_balance_exceeds_threshold(
    http_client,
    test_db,
    test_subscription_low_balance,
    auth_headers
):
    """
    Test that soft limit warning is shown when new balance < -100.

    Setup: Subscription with 10 units remaining
    Action: Request 150 pages translation (balance will be -140)
    Expected: exceeds_soft_limit=True
    """
    print("\n" + "="*80)
    print("TEST: Soft limit warning")
    print("="*80)

    # Create test files for 150 pages
    file_content = b"Test content" * 100
    file_data = base64.b64encode(file_content).decode('utf-8')

    response = await http_client.post(
        "/api/translate-user",
        json={
            "files": [
                {
                    "name": f"test-{i}.txt",
                    "content": file_data,
                    "size": len(file_content),
                    "type": "text/plain"
                }
                for i in range(150)
            ],
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "test@overdraft.com",
            "userName": "Test User"
        },
        headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()
    pricing = data["data"]["pricing"]

    print(f"Overdraft amount: {pricing.get('overdraft_amount')}")
    print(f"Exceeds soft limit: {pricing.get('exceeds_soft_limit')}")

    assert pricing["overdraft"] is True
    assert pricing["exceeds_soft_limit"] is True, "Should exceed soft limit (-100)"
    assert pricing["overdraft_amount"] == 140, f"Expected overdraft_amount=140"

    print("✅ Soft limit warning correctly triggered")


@pytest.mark.asyncio
async def test_negative_balance_saved_to_database(
    http_client,
    test_db,
    test_subscription_low_balance,
    auth_headers
):
    """
    Test that negative balance is correctly saved to the database.

    Setup: Subscription with 10 units remaining
    Action: Request 50 pages translation
    Expected: Database shows units_used=140, units_remaining=-40
    """
    print("\n" + "="*80)
    print("TEST: Negative balance persisted in database")
    print("="*80)

    file_content = b"Test" * 100
    file_data = base64.b64encode(file_content).decode('utf-8')

    # Make request
    response = await http_client.post(
        "/api/translate-user",
        json={
            "files": [{"name": f"test-{i}.txt", "content": file_data, "size": len(file_content), "type": "text/plain"} for i in range(50)],
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "test@overdraft.com",
            "userName": "Test User"
        },
        headers=auth_headers
    )

    assert response.status_code == 200

    # Verify database state
    from bson import ObjectId
    subscription = await test_db.subscriptions.find_one({"_id": ObjectId(test_subscription_low_balance)})

    assert subscription is not None
    current_period = subscription["usage_periods"][0]

    print(f"Units used: {current_period['units_used']}")
    print(f"Units remaining: {current_period['units_remaining']}")

    assert current_period["units_used"] == 140, f"Expected units_used=140, got {current_period['units_used']}"
    assert current_period["units_remaining"] == -40, f"Expected units_remaining=-40, got {current_period['units_remaining']}"

    print("✅ Negative balance correctly saved to database")


@pytest.mark.asyncio
async def test_individual_users_still_require_payment(http_client):
    """
    Test that individual users (non-enterprise) still get payment requirement.
    Overdraft feature should ONLY work for enterprise users with subscriptions.
    """
    print("\n" + "="*80)
    print("TEST: Individual users unaffected (still require payment)")
    print("="*80)

    file_content = b"Test" * 100
    file_data = base64.b64encode(file_content).decode('utf-8')

    # Make request WITHOUT authentication (individual user)
    response = await http_client.post(
        "/api/translate-user",
        json={
            "files": [{"name": "test.txt", "content": file_data, "size": len(file_content), "type": "text/plain"}],
            "sourceLanguage": "en",
            "targetLanguage": "es",
            "email": "individual@test.com",
            "userName": "Individual User"
        }
        # NO auth_headers - simulates individual user
    )

    assert response.status_code == 200
    data = response.json()
    pricing = data["data"]["pricing"]
    payment = data["data"]["payment"]

    print(f"Customer type: {pricing.get('customer_type')}")
    print(f"Payment required: {payment.get('required')}")
    print(f"Overdraft detected: {pricing.get('overdraft', False)}")

    assert pricing["customer_type"] == "individual", "Should be individual user"
    assert payment["required"] is True, "Individual users must pay"
    assert pricing.get("overdraft", False) is False, "Individual users should NOT have overdraft"

    print("✅ Individual users still require payment (overdraft not applied)")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
