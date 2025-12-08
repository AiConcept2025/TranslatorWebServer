"""
TDD RED STATE - Failing Integration Tests for Enhanced Subscription Billing Schema

These tests WILL FAIL because the implementation is incomplete.
This is Phase 1 (RED) of TDD - write failing tests first.

EXPECTED FAILURES:
- GET endpoints may not serialize new billing fields → 500 or missing keys
- POST endpoint may reject billing_frequency/payment_terms_days → 422 validation error
- Database queries may fail if schema not updated → KeyError

Test Coverage:
- POST /api/subscriptions - Create with billing_frequency, payment_terms_days
- GET /api/subscriptions/{id} - Return billing fields
- GET /api/subscriptions/company/{name} - Return billing fields in list
- PATCH /api/subscriptions/{id} - Update billing fields

CRITICAL: Uses REAL running server + REAL test database
Terminal 1: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
Terminal 2: pytest tests/integration/test_subscriptions_billing_integration.py -v
"""

import pytest
import httpx
import uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from decimal import Decimal

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
    company_name = f"TEST-BILLING-CO-{uuid.uuid4().hex[:8].upper()}"
    company_data = {
        "company_name": company_name,
        "description": "Test company for billing integration tests",
        "address": {
            "address0": "123 Billing Street",
            "address1": "",
            "postal_code": "12345",
            "state": "NJ",
            "city": "Billing City",
            "country": "USA"
        },
        "contact_person": {
            "name": "Billing Contact",
            "type": "Primary Contact"
        },
        "phone_number": ["555-BILL"],
        "company_url": [],
        "line_of_business": "Testing Billing",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.company.insert_one(company_data)
    print(f"✅ Created test company: {company_name}")

    yield company_data

    # Cleanup
    await test_db.company.delete_one({"company_name": company_name})
    print(f"🧹 Cleaned up test company: {company_name}")


@pytest.fixture(scope="function")
async def admin_headers(http_client):
    """
    Get admin authentication headers for API requests.
    Uses corporate login endpoint.
    """
    login_response = await http_client.post(
        "/login/corporate",
        json={
            "companyName": "Iris Trading",
            "userEmail": "danishevsky@gmail.com",
            "password": "Sveta87201120!",
            "userFullName": "Manager User",
            "loginDateTime": datetime.now(timezone.utc).isoformat()
        }
    )

    if login_response.status_code != 200:
        pytest.skip(f"Failed to authenticate admin user: {login_response.status_code}")

    auth_data = login_response.json()
    token = auth_data.get("data", {}).get("authToken")

    if not token:
        pytest.skip("No authToken in login response")

    return {"Authorization": f"Bearer {token}"}


# ============================================================================
# TDD RED STATE TESTS - These WILL FAIL
# ============================================================================

@pytest.mark.asyncio
async def test_create_subscription_with_billing_frequency_quarterly(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    admin_headers
):
    """
    TEST: Create subscription with billing_frequency='quarterly'

    EXPECTED FAILURE:
    - 422 validation error (field not in model)
    - OR 500 error (field not handled)
    - OR billing_frequency not saved to database

    SUCCESS CRITERIA:
    - Status 201
    - Response contains billing_frequency='quarterly'
    - Database record contains billing_frequency='quarterly'
    """
    subscription_data = {
        "company_name": test_company["company_name"],
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        "price_per_unit": 0.05,
        "subscription_price": 50.0,
        "start_date": (datetime.now(timezone.utc)).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "status": "active",
        "billing_frequency": "quarterly",  # NEW FIELD - will cause failure
        "payment_terms_days": 30  # NEW FIELD - will cause failure
    }

    print(f"\n📤 POST /api/subscriptions with billing_frequency={subscription_data['billing_frequency']}")
    response = await http_client.post(
        "/api/subscriptions",
        json=subscription_data,
        headers=admin_headers
    )

    print(f"📥 Response: {response.status_code}")
    if response.status_code != 201:
        print(f"❌ ERROR: {response.text}")

    # ASSERT: Should succeed (but will fail in RED state)
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

    result = response.json()
    data = result.get("data", {})
    subscription_id = data.get("subscription_id")

    # VERIFY: Response contains new billing fields
    assert "billing_frequency" in data, "Response missing billing_frequency field"
    assert data["billing_frequency"] == "quarterly", f"Expected quarterly, got {data.get('billing_frequency')}"
    assert "payment_terms_days" in data, "Response missing payment_terms_days field"
    assert data["payment_terms_days"] == 30, f"Expected 30, got {data.get('payment_terms_days')}"

    # VERIFY: Database contains new billing fields
    db_subscription = await test_db.subscriptions.find_one({"subscription_id": subscription_id})
    assert db_subscription is not None, "Subscription not found in database"
    assert "billing_frequency" in db_subscription, "Database record missing billing_frequency"
    assert db_subscription["billing_frequency"] == "quarterly"
    assert "payment_terms_days" in db_subscription, "Database record missing payment_terms_days"
    assert db_subscription["payment_terms_days"] == 30

    print(f"✅ Subscription {subscription_id} created with billing_frequency=quarterly, payment_terms_days=30")

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": subscription_id})


@pytest.mark.asyncio
async def test_create_subscription_with_billing_frequency_monthly(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    admin_headers
):
    """
    TEST: Create subscription with billing_frequency='monthly'

    EXPECTED FAILURE: Same as quarterly test
    """
    subscription_data = {
        "company_name": test_company["company_name"],
        "subscription_unit": "word",
        "units_per_subscription": 5000,
        "price_per_unit": 0.02,
        "subscription_price": 100.0,
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "status": "active",
        "billing_frequency": "monthly",
        "payment_terms_days": 15
    }

    print(f"\n📤 POST /api/subscriptions with billing_frequency=monthly")
    response = await http_client.post(
        "/api/subscriptions",
        json=subscription_data,
        headers=admin_headers
    )

    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    result = response.json()
    data = result.get("data", {})

    assert data["billing_frequency"] == "monthly"
    assert data["payment_terms_days"] == 15

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": result["subscription_id"]})


@pytest.mark.asyncio
async def test_create_subscription_with_billing_frequency_annual(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    admin_headers
):
    """
    TEST: Create subscription with billing_frequency='annual'

    EXPECTED FAILURE: Same as quarterly test
    """
    subscription_data = {
        "company_name": test_company["company_name"],
        "subscription_unit": "page",
        "units_per_subscription": 10000,
        "price_per_unit": 0.04,
        "subscription_price": 400.0,
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "status": "active",
        "billing_frequency": "annual",
        "payment_terms_days": 60
    }

    print(f"\n📤 POST /api/subscriptions with billing_frequency=annual")
    response = await http_client.post(
        "/api/subscriptions",
        json=subscription_data,
        headers=admin_headers
    )

    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    result = response.json()
    data = result.get("data", {})

    assert data["billing_frequency"] == "annual"
    assert data["payment_terms_days"] == 60

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": data["subscription_id"]})


@pytest.mark.asyncio
async def test_get_subscription_returns_billing_fields(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    admin_headers
):
    """
    TEST: GET /api/subscriptions/{id} returns billing_frequency and payment_terms_days

    EXPECTED FAILURE:
    - 500 error (serialization fails)
    - OR response missing billing_frequency/payment_terms_days fields
    - OR KeyError in backend code
    """
    # First create a subscription directly in database with billing fields
    subscription_id = f"SUB-TEST-{uuid.uuid4().hex[:8].upper()}"
    subscription_doc = {
        "subscription_id": subscription_id,
        "company_name": test_company["company_name"],
        "subscription_unit": "page",
        "units_per_subscription": 2000,
        "price_per_unit": 0.06,
        "subscription_price": 120.0,
        "start_date": datetime.now(timezone.utc),
        "end_date": datetime.now(timezone.utc) + timedelta(days=365),
        "status": "active",
        "billing_frequency": "quarterly",  # Direct DB insert
        "payment_terms_days": 45,  # Direct DB insert
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.subscriptions.insert_one(subscription_doc)
    print(f"✅ Created subscription {subscription_id} in database with billing fields")

    # Now try to GET it via API
    print(f"\n📤 GET /api/subscriptions/{subscription_id}")
    response = await http_client.get(
        f"/api/subscriptions/{subscription_id}",
        headers=admin_headers
    )

    print(f"📥 Response: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ ERROR: {response.text}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    result = response.json()
    data = result.get("data", {})

    # VERIFY: Response serialized billing fields correctly
    assert "billing_frequency" in data, "Response missing billing_frequency"
    assert data["billing_frequency"] == "quarterly"
    assert "payment_terms_days" in data, "Response missing payment_terms_days"
    assert data["payment_terms_days"] == 45

    print(f"✅ GET subscription returned billing_frequency={data['billing_frequency']}, payment_terms_days={data['payment_terms_days']}")

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": subscription_id})


@pytest.mark.asyncio
async def test_get_subscriptions_by_company_returns_billing_fields(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    admin_headers
):
    """
    TEST: GET /api/subscriptions/company/{name} returns billing fields in list

    EXPECTED FAILURE: Same as single GET test, but for list endpoint
    """
    # Create subscription with billing fields
    subscription_id = f"SUB-TEST-{uuid.uuid4().hex[:8].upper()}"
    subscription_doc = {
        "subscription_id": subscription_id,
        "company_name": test_company["company_name"],
        "subscription_unit": "word",
        "units_per_subscription": 3000,
        "price_per_unit": 0.03,
        "subscription_price": 90.0,
        "start_date": datetime.now(timezone.utc),
        "end_date": datetime.now(timezone.utc) + timedelta(days=365),
        "status": "active",
        "billing_frequency": "monthly",
        "payment_terms_days": 20,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.subscriptions.insert_one(subscription_doc)
    print(f"✅ Created subscription {subscription_id} for company {test_company['company_name']}")

    # GET subscriptions by company
    print(f"\n📤 GET /api/subscriptions/company/{test_company['company_name']}")
    response = await http_client.get(
        f"/api/subscriptions/company/{test_company['company_name']}",
        headers=admin_headers
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    subscriptions = response.json()
    assert isinstance(subscriptions, list), "Expected list of subscriptions"
    assert len(subscriptions) > 0, "Expected at least 1 subscription"

    # Find our test subscription
    test_sub = next((s for s in subscriptions if s["subscription_id"] == subscription_id), None)
    assert test_sub is not None, f"Subscription {subscription_id} not in response"

    # VERIFY: Billing fields present
    assert "billing_frequency" in test_sub, "Subscription missing billing_frequency"
    assert test_sub["billing_frequency"] == "monthly"
    assert "payment_terms_days" in test_sub, "Subscription missing payment_terms_days"
    assert test_sub["payment_terms_days"] == 20

    print(f"✅ Company subscriptions list includes billing fields")

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": subscription_id})


@pytest.mark.asyncio
async def test_update_subscription_billing_fields(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    admin_headers
):
    """
    TEST: PATCH /api/subscriptions/{id} - Update billing_frequency and payment_terms_days

    EXPECTED FAILURE:
    - 422 validation error (fields not in update model)
    - OR fields not updated in database
    """
    # Create subscription
    subscription_id = f"SUB-TEST-{uuid.uuid4().hex[:8].upper()}"
    subscription_doc = {
        "subscription_id": subscription_id,
        "company_name": test_company["company_name"],
        "subscription_unit": "page",
        "units_per_subscription": 1500,
        "price_per_unit": 0.05,
        "subscription_price": 75.0,
        "start_date": datetime.now(timezone.utc),
        "end_date": datetime.now(timezone.utc) + timedelta(days=365),
        "status": "active",
        "billing_frequency": "quarterly",
        "payment_terms_days": 30,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.subscriptions.insert_one(subscription_doc)
    print(f"✅ Created subscription {subscription_id} with quarterly billing")

    # Update billing fields
    update_data = {
        "billing_frequency": "monthly",
        "payment_terms_days": 15
    }

    print(f"\n📤 PATCH /api/subscriptions/{subscription_id} - Change to monthly billing")
    response = await http_client.patch(
        f"/api/subscriptions/{subscription_id}",
        json=update_data,
        headers=admin_headers
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    result = response.json()
    data = result.get("data", {})
    assert data["billing_frequency"] == "monthly"
    assert data["payment_terms_days"] == 15

    # Verify database updated
    db_subscription = await test_db.subscriptions.find_one({"subscription_id": subscription_id})
    assert db_subscription["billing_frequency"] == "monthly"
    assert db_subscription["payment_terms_days"] == 15

    print(f"✅ Billing fields updated: quarterly→monthly, 30 days→15 days")

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": subscription_id})


@pytest.mark.asyncio
async def test_create_subscription_without_billing_fields_uses_defaults(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    admin_headers
):
    """
    TEST: Create subscription WITHOUT billing fields - should use defaults

    EXPECTED FAILURE: Will fail if default values not configured

    SUCCESS CRITERIA:
    - Status 201
    - billing_frequency defaults to 'quarterly'
    - payment_terms_days defaults to 30
    """
    subscription_data = {
        "company_name": test_company["company_name"],
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        "price_per_unit": 0.05,
        "subscription_price": 50.0,
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "status": "active"
        # NO billing_frequency or payment_terms_days
    }

    print(f"\n📤 POST /api/subscriptions WITHOUT billing fields (test defaults)")
    response = await http_client.post(
        "/api/subscriptions",
        json=subscription_data,
        headers=admin_headers
    )

    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    result = response.json()
    data = result.get("data", {})

    # VERIFY: Defaults applied
    assert "billing_frequency" in data, "Response missing billing_frequency (should have default)"
    assert data["billing_frequency"] == "quarterly", f"Default billing_frequency should be 'quarterly', got {data.get('billing_frequency')}"
    assert "payment_terms_days" in data, "Response missing payment_terms_days (should have default)"
    assert data["payment_terms_days"] == 30, f"Default payment_terms_days should be 30, got {data.get('payment_terms_days')}"

    print(f"✅ Defaults applied: billing_frequency=quarterly, payment_terms_days=30")

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": data["subscription_id"]})


@pytest.mark.asyncio
async def test_billing_frequency_validation_rejects_invalid_value(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    admin_headers
):
    """
    TEST: Create subscription with INVALID billing_frequency

    EXPECTED FAILURE: Will fail if validation not implemented

    SUCCESS CRITERIA:
    - Status 422 (validation error)
    - Error message indicates invalid billing_frequency
    """
    subscription_data = {
        "company_name": test_company["company_name"],
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        "price_per_unit": 0.05,
        "subscription_price": 50.0,
        "start_date": datetime.now(timezone.utc).isoformat(),
        "end_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
        "status": "active",
        "billing_frequency": "weekly",  # INVALID - should only allow monthly/quarterly/annual
        "payment_terms_days": 30
    }

    print(f"\n📤 POST /api/subscriptions with INVALID billing_frequency=weekly")
    response = await http_client.post(
        "/api/subscriptions",
        json=subscription_data,
        headers=admin_headers
    )

    # VERIFY: Validation rejected it
    assert response.status_code == 422, f"Expected 422 validation error, got {response.status_code}"

    error_detail = response.json()
    print(f"✅ Validation error (as expected): {error_detail}")

    # VERIFY: Error message mentions billing_frequency
    error_text = str(error_detail).lower()
    assert "billing_frequency" in error_text or "billing" in error_text, "Error should mention billing_frequency"


# ============================================================================
# End of Tests
# ============================================================================
