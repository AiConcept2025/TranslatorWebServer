"""
Integration tests for invoice generation fixes.

Tests cover:
1. Monthly invoice line item description (month name, not "Q0")
2. Payment link failure handling for unpaid invoices
3. Payment link failure handling for paid invoices

IMPORTANT: Server must be running at http://localhost:8000
Terminal 1: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
Terminal 2: pytest tests/integration/test_invoice_generation.py -v
"""

import pytest
import httpx
import uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId, Decimal128
from typing import Dict, Any

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
    company_name = f"TEST-INVOICE-GEN-{uuid.uuid4().hex[:8].upper()}"
    company_data = {
        "company_name": company_name,
        "description": "Test company for invoice generation integration tests",
        "address": {
            "address0": "789 Generation Street",
            "address1": "",
            "postal_code": "98765",
            "state": "CA",
            "city": "Test City",
            "country": "USA"
        },
        "contact_person": {
            "name": "Invoice Generator",
            "type": "Billing Contact"
        },
        "contact_email": f"test_{uuid.uuid4().hex[:6]}@testcompany.com",
        "phone_number": ["555-GEN-TEST"],
        "company_url": [],
        "line_of_business": "Testing Invoice Generation",
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
async def test_subscription(test_db, test_company):
    """Create a valid test subscription for invoice creation."""
    subscription_id = f"SUB-TEST-GEN-{uuid.uuid4().hex[:8].upper()}"
    subscription_data = {
        "subscription_id": subscription_id,
        "company_name": test_company["company_name"],
        "subscription_unit": "page",
        "units_per_subscription": 3000,
        "price_per_unit": 0.10,
        "subscription_price": 300.0,
        "start_date": datetime.now(timezone.utc),
        "end_date": datetime.now(timezone.utc) + timedelta(days=365),
        "status": "active",
        "billing_frequency": "monthly",
        "payment_terms_days": 30,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.subscriptions.insert_one(subscription_data)
    subscription_data["_id"] = result.inserted_id
    print(f"✅ Created test subscription: {subscription_id}")

    yield subscription_data

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": subscription_id})
    print(f"🧹 Cleaned up test subscription: {subscription_id}")


@pytest.fixture(scope="function")
async def test_invoice_unpaid(test_db, test_company, test_subscription):
    """Create a test invoice with UNPAID status."""
    invoice_number = f"INV-TEST-UNPAID-{uuid.uuid4().hex[:8].upper()}"
    invoice_data = {
        "invoice_number": invoice_number,
        "company_id": test_company["company_name"],
        "company_name": test_company["company_name"],
        "subscription_id": test_subscription["subscription_id"],
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc) + timedelta(days=30),
        "billing_period": {
            "period_numbers": [3],  # March
            "period_start": datetime(2025, 3, 1, tzinfo=timezone.utc),
            "period_end": datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
        },
        "line_items": [
            {
                "description": "Translation Services - March 2025",
                "period_numbers": [3],
                "quantity": 1000,
                "unit_price": Decimal128("0.10"),
                "amount": Decimal128("100.00")
            }
        ],
        "subtotal": Decimal128("100.00"),
        "tax_amount": Decimal128("6.00"),
        "total_amount": Decimal128("106.00"),
        "amount_paid": Decimal128("0.00"),
        "amount_due": Decimal128("106.00"),
        "status": "sent",  # UNPAID
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.invoices.insert_one(invoice_data)
    invoice_data["_id"] = result.inserted_id
    print(f"✅ Created test UNPAID invoice: {invoice_number}")

    yield invoice_data

    # Cleanup
    await test_db.invoices.delete_one({"invoice_number": invoice_number})
    print(f"🧹 Cleaned up test unpaid invoice: {invoice_number}")


@pytest.fixture(scope="function")
async def test_invoice_paid(test_db, test_company, test_subscription):
    """Create a test invoice with PAID status."""
    invoice_number = f"INV-TEST-PAID-{uuid.uuid4().hex[:8].upper()}"
    invoice_data = {
        "invoice_number": invoice_number,
        "company_id": test_company["company_name"],
        "company_name": test_company["company_name"],
        "subscription_id": test_subscription["subscription_id"],
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc) + timedelta(days=30),
        "billing_period": {
            "period_numbers": [3],  # March
            "period_start": datetime(2025, 3, 1, tzinfo=timezone.utc),
            "period_end": datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
        },
        "line_items": [
            {
                "description": "Translation Services - March 2025",
                "period_numbers": [3],
                "quantity": 1000,
                "unit_price": Decimal128("0.10"),
                "amount": Decimal128("100.00")
            }
        ],
        "subtotal": Decimal128("100.00"),
        "tax_amount": Decimal128("6.00"),
        "total_amount": Decimal128("106.00"),
        "amount_paid": Decimal128("106.00"),  # FULLY PAID
        "amount_due": Decimal128("0.00"),
        "status": "paid",  # PAID
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.invoices.insert_one(invoice_data)
    invoice_data["_id"] = result.inserted_id
    print(f"✅ Created test PAID invoice: {invoice_number}")

    yield invoice_data

    # Cleanup
    await test_db.invoices.delete_one({"invoice_number": invoice_number})
    print(f"🧹 Cleaned up test paid invoice: {invoice_number}")


@pytest.fixture(scope="function")
async def admin_auth_headers(http_client):
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
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_monthly_invoice_line_item_description(
    http_client: httpx.AsyncClient,
    test_subscription: Dict[str, Any],
    admin_auth_headers: Dict[str, str]
):
    """Test monthly invoice shows correct month name in line item description."""

    print(f"\n{'='*80}")
    print("TEST: Monthly invoice line item description")
    print(f"{'='*80}")

    # Test 1: Generate monthly invoice for March (month 3)
    print(f"\n📤 POST /api/v1/invoices/generate-monthly - Month 3 (March)")
    response = await http_client.post(
        "/api/v1/invoices/generate-monthly",
        params={
            "subscription_id": str(test_subscription["_id"]),
            "month": 3
        },
        headers=admin_auth_headers
    )

    print(f"📥 Response: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ ERROR: {response.text}")

    assert response.status_code == 200, \
        f"Expected 200, got {response.status_code}: {response.text}"

    result = response.json()
    data = result.get("data", {})

    # Verify line item description
    assert "line_items" in data, "Response missing line_items"
    line_items = data["line_items"]
    assert len(line_items) > 0, "Expected at least 1 line item"

    base_line_item = line_items[0]  # First line item is base subscription
    description = base_line_item.get("description", "")

    print(f"\n✅ Line item description: {description}")

    assert "March" in description, \
        f"Expected 'March' in description, got: {description}"
    assert "Q0" not in description, \
        f"Should not contain 'Q0', got: {description}"

    # Test 2: Verify for different month (December = 12)
    print(f"\n📤 POST /api/v1/invoices/generate-monthly - Month 12 (December)")
    response2 = await http_client.post(
        "/api/v1/invoices/generate-monthly",
        params={
            "subscription_id": str(test_subscription["_id"]),
            "month": 12
        },
        headers=admin_auth_headers
    )

    assert response2.status_code == 200, \
        f"Expected 200, got {response2.status_code}: {response2.text}"

    result2 = response2.json()
    data2 = result2.get("data", {})
    line_items2 = data2.get("line_items", [])

    assert len(line_items2) > 0, "Expected at least 1 line item"
    description2 = line_items2[0].get("description", "")

    print(f"✅ Line item description: {description2}")

    assert "December" in description2, \
        f"Expected 'December', got: {description2}"
    assert "Q0" not in description2, \
        f"Should not contain 'Q0', got: {description2}"

    print(f"\n{'='*80}")
    print("✅ TEST PASSED: Monthly invoice line items show correct month names")
    print(f"{'='*80}\n")


@pytest.mark.asyncio
async def test_send_invoice_email_fails_when_payment_link_creation_fails_for_unpaid_invoice(
    http_client: httpx.AsyncClient,
    test_db,
    test_company: Dict[str, Any],
    test_subscription: Dict[str, Any],
    admin_auth_headers: Dict[str, str]
):
    """Test email send fails when payment link creation fails for unpaid invoice."""

    print(f"\n{'='*80}")
    print("TEST: Payment link failure for UNPAID invoice")
    print(f"{'='*80}")

    # Create invoice with INVALID total_amount (None) which will naturally cause
    # payment link creation to fail when _convert_to_cents() is called
    invoice_number = f"INV-TEST-UNPAID-INVALID-{uuid.uuid4().hex[:8].upper()}"
    invoice_data = {
        "invoice_number": invoice_number,
        "company_id": test_company["company_name"],
        "company_name": test_company["company_name"],
        "subscription_id": test_subscription["subscription_id"],
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc) + timedelta(days=30),
        "billing_period": {
            "period_numbers": [3],
            "period_start": datetime(2025, 3, 1, tzinfo=timezone.utc),
            "period_end": datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
        },
        "line_items": [
            {
                "description": "Translation Services - March 2025",
                "period_numbers": [3],
                "quantity": 1000,
                "unit_price": Decimal128("0.10"),
                "amount": Decimal128("100.00")
            }
        ],
        "subtotal": Decimal128("100.00"),
        "tax_amount": Decimal128("6.00"),
        "total_amount": None,  # ❌ INVALID - causes payment link creation to fail
        "amount_paid": Decimal128("0.00"),
        "amount_due": Decimal128("106.00"),
        "status": "sent",  # UNPAID
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.invoices.insert_one(invoice_data)
    invoice_id = str(result.inserted_id)
    print(f"✅ Created test invoice with invalid total_amount: {invoice_number}")

    try:
        print(f"\n📤 POST /api/v1/invoices/{invoice_id}/send-email")
        print(f"   Invoice status: {invoice_data['status']} (UNPAID)")
        print(f"   Invoice total_amount: {invoice_data['total_amount']} (INVALID)")
        print(f"   Expected: Payment link creation fails → Email send fails")

        # Attempt to send email for unpaid invoice with invalid total
        response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=admin_auth_headers
        )

        print(f"\n📥 Response: {response.status_code}")
        print(f"   Response body: {response.text}")

        # Should fail with 500 error
        assert response.status_code == 500, \
            f"Expected 500 for payment link failure on unpaid invoice, got {response.status_code}"

        # Extract error message from nested error object
        response_data = response.json()
        error_message = response_data.get("error", {}).get("message", "")

        assert "Payment link creation failed" in error_message, \
            f"Expected error message about payment link failure, got: {error_message}"
        assert "Cannot send invoice" in error_message, \
            f"Expected message about not sending invoice, got: {error_message}"

        print(f"\n✅ Correctly failed with error: {error_message}")
        print(f"\n{'='*80}")
        print("✅ TEST PASSED: Unpaid invoice without payment link fails fast")
        print(f"{'='*80}\n")

    finally:
        # Cleanup
        await test_db.invoices.delete_one({"invoice_number": invoice_number})
        print(f"🧹 Cleaned up test invoice: {invoice_number}")


@pytest.mark.asyncio
async def test_send_invoice_email_succeeds_when_payment_link_fails_for_paid_invoice(
    http_client: httpx.AsyncClient,
    test_db,
    test_company: Dict[str, Any],
    test_subscription: Dict[str, Any],
    admin_auth_headers: Dict[str, str]
):
    """Test email send succeeds when payment link fails for PAID invoice (acceptable)."""

    print(f"\n{'='*80}")
    print("TEST: Payment link failure for PAID invoice")
    print(f"{'='*80}")

    # Create PAID invoice with INVALID total_amount (None)
    # Payment link creation will fail, but email should still succeed (paid invoice doesn't need link)
    invoice_number = f"INV-TEST-PAID-INVALID-{uuid.uuid4().hex[:8].upper()}"
    invoice_data = {
        "invoice_number": invoice_number,
        "company_id": test_company["company_name"],
        "company_name": test_company["company_name"],
        "subscription_id": test_subscription["subscription_id"],
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc) + timedelta(days=30),
        "billing_period": {
            "period_numbers": [3],
            "period_start": datetime(2025, 3, 1, tzinfo=timezone.utc),
            "period_end": datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
        },
        "line_items": [
            {
                "description": "Translation Services - March 2025",
                "period_numbers": [3],
                "quantity": 1000,
                "unit_price": Decimal128("0.10"),
                "amount": Decimal128("100.00")
            }
        ],
        "subtotal": Decimal128("100.00"),
        "tax_amount": Decimal128("6.00"),
        "total_amount": None,  # ❌ INVALID - causes payment link creation to fail
        "amount_paid": Decimal128("106.00"),  # FULLY PAID
        "amount_due": Decimal128("0.00"),
        "status": "paid",  # ✅ PAID - payment link not required
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.invoices.insert_one(invoice_data)
    invoice_id = str(result.inserted_id)
    print(f"✅ Created test PAID invoice with invalid total_amount: {invoice_number}")

    try:
        print(f"\n📤 POST /api/v1/invoices/{invoice_id}/send-email")
        print(f"   Invoice status: {invoice_data['status']} (PAID)")
        print(f"   Invoice total_amount: {invoice_data['total_amount']} (INVALID)")
        print(f"   Expected: Payment link creation fails → Email send SUCCEEDS (paid invoice doesn't need link)")

        # Attempt to send email for PAID invoice
        response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=admin_auth_headers
        )

        print(f"\n📥 Response: {response.status_code}")
        print(f"   Response body: {response.text}")

        # Should succeed (paid invoice doesn't need payment link)
        assert response.status_code == 200, \
            f"Expected 200 for paid invoice (payment link not required), got {response.status_code}: {response.text}"

        data = response.json()
        assert data.get("success") is True, \
            f"Email send should be successful for paid invoice. Response: {data}"

        print(f"\n✅ Successfully sent email for paid invoice (payment link not required)")
        print(f"\n{'='*80}")
        print("✅ TEST PASSED: Paid invoice email succeeds even without payment link")
        print(f"{'='*80}\n")

    finally:
        # Cleanup
        await test_db.invoices.delete_one({"invoice_number": invoice_number})
        print(f"🧹 Cleaned up test invoice: {invoice_number}")


# ============================================================================
# End of Tests
# ============================================================================
