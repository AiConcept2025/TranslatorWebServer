"""
TDD RED STATE - Failing Integration Tests for Payment-Invoice Linkage

These tests WILL FAIL because the implementation is incomplete.
This is Phase 1 (RED) of TDD - write failing tests first.

EXPECTED FAILURES:
- GET /api/v1/payments/ may not return invoice_id, subscription_id fields
- POST /api/v1/payments/{id}/apply-to-invoice may fail (endpoint exists but logic incomplete)
- Invoice amount_paid/amount_due may not update when payment applied
- Payment status may not update when linked to invoice

Test Coverage:
- GET /api/v1/payments/ - Return invoice_id, subscription_id fields
- POST /api/v1/payments/{id}/apply-to-invoice - Link payment to invoice (ALREADY IMPLEMENTED)
- Verify invoice.amount_paid updated when payment applied
- Verify invoice.amount_due recalculated
- Verify invoice.status changes to 'paid' when fully paid
- Verify payment.invoice_id set correctly
- Test partial payments and overpayments

CRITICAL: Uses REAL running server + REAL test database
Terminal 1: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
Terminal 2: pytest tests/integration/test_payments_billing_integration.py -v
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
    company_name = f"TEST-PAYMENT-CO-{uuid.uuid4().hex[:8].upper()}"
    company_data = {
        "company_name": company_name,
        "description": "Test company for payment-invoice tests",
        "address": {
            "address0": "789 Payment Blvd",
            "address1": "",
            "postal_code": "98765",
            "state": "CA",
            "city": "Payment City",
            "country": "USA"
        },
        "contact_person": {
            "name": "Payment Contact",
            "type": "Primary Contact"
        },
        "phone_number": ["555-PAY1"],
        "company_url": [],
        "line_of_business": "Testing Payments",
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
    """Create a test subscription."""
    subscription_id = f"SUB-TEST-{uuid.uuid4().hex[:8].upper()}"
    subscription_doc = {
        "subscription_id": subscription_id,
        "company_name": test_company["company_name"],
        "subscription_unit": "page",
        "units_per_subscription": 5000,
        "price_per_unit": 0.05,
        "subscription_price": 250.0,
        "start_date": datetime.now(timezone.utc),
        "end_date": datetime.now(timezone.utc) + timedelta(days=365),
        "status": "active",
        "billing_frequency": "quarterly",
        "payment_terms_days": 30,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.subscriptions.insert_one(subscription_doc)
    print(f"✅ Created test subscription: {subscription_id}")

    yield subscription_doc

    # Cleanup
    await test_db.subscriptions.delete_one({"subscription_id": subscription_id})


@pytest.fixture(scope="function")
async def test_invoice(test_db, test_company, test_subscription):
    """Create a test invoice."""
    invoice_number = f"TEST-INV-{uuid.uuid4().hex[:8].upper()}"
    invoice_doc = {
        "invoice_number": invoice_number,
        "company_name": test_company["company_name"],
        "subscription_id": test_subscription["subscription_id"],
        "issue_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc) + timedelta(days=30),
        "billing_period": {
            "start_date": "2025-01-01",
            "end_date": "2025-03-31"
        },
        "line_items": [
            {"description": "Translation Services", "quantity": 1000, "unit_price": 0.05, "amount": 50.0}
        ],
        "subtotal": 50.0,
        "tax_rate": 0.08,
        "tax_amount": 4.0,
        "total_amount": 54.0,
        "amount_paid": 0.0,
        "amount_due": 54.0,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.invoices.insert_one(invoice_doc)
    print(f"✅ Created test invoice: {invoice_number}, total=${invoice_doc['total_amount']}")

    yield invoice_doc

    # Cleanup
    await test_db.invoices.delete_one({"invoice_number": invoice_number})


@pytest.fixture(scope="function")
async def test_company_user(test_db, test_company):
    """Create a test company user for authentication."""
    user_email = f"test_payment_{uuid.uuid4().hex[:8]}@test.com"
    user_data = {
        "email": user_email,
        "user_id": f"USER-{uuid.uuid4().hex[:8]}",
        "user_name": f"Payment Test User",
        "company_name": test_company["company_name"],
        "permission_level": "user",
        "status": "active",
        "password_hash": "hashed_test_password",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.company_users.insert_one(user_data)
    yield user_data

    # Cleanup
    await test_db.company_users.delete_one({"email": user_email})


@pytest.fixture(scope="function")
async def admin_headers(http_client):
    """Get admin authentication headers for API requests."""
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
async def test_get_payments_returns_invoice_and_subscription_ids(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_subscription,
    test_invoice,
    test_company_user,
    admin_headers
):
    """
    TEST: GET /api/v1/payments/ returns invoice_id and subscription_id

    EXPECTED FAILURE:
    - Response missing invoice_id and/or subscription_id fields
    - Serialization error if fields exist in DB but not in response model

    SUCCESS CRITERIA:
    - Payment records include invoice_id and subscription_id fields
    - Fields serialized correctly (can be null)
    """
    # Create a payment directly in database with invoice/subscription links
    payment_id = f"PAY-TEST-{uuid.uuid4().hex[:8].upper()}"
    payment_doc = {
        "payment_id": payment_id,
        "company_name": test_company["company_name"],
        "user_email": test_company_user["email"],
        "invoice_id": test_invoice["invoice_number"],  # NEW FIELD
        "subscription_id": test_subscription["subscription_id"],  # NEW FIELD
        "amount": 54.0,
        "payment_method": "credit_card",
        "payment_date": datetime.now(timezone.utc),
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.payments.insert_one(payment_doc)
    print(f"✅ Created payment {payment_id} linked to invoice {test_invoice['invoice_number']}")

    # GET payments
    print(f"\n📤 GET /api/v1/payments/")
    response = await http_client.get(
        "/api/v1/payments/",
        headers=admin_headers
    )

    print(f"📥 Response: {response.status_code}")
    if response.status_code != 200:
        print(f"❌ ERROR: {response.text}")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    response_data = response.json()
    assert response_data.get("success") is True, "Expected success=True"
    assert "data" in response_data, "Response missing 'data' field"
    assert "payments" in response_data["data"], "Response data missing 'payments' field"

    payments = response_data["data"]["payments"]
    assert isinstance(payments, list), "Expected list of payments"

    # Find our test payment
    test_payment = next((p for p in payments if p.get("payment_id") == payment_id), None)
    assert test_payment is not None, f"Payment {payment_id} not in response"

    # VERIFY: invoice_id and subscription_id fields present
    assert "invoice_id" in test_payment, "Payment response missing invoice_id field"
    assert test_payment["invoice_id"] == test_invoice["invoice_number"]

    assert "subscription_id" in test_payment, "Payment response missing subscription_id field"
    assert test_payment["subscription_id"] == test_subscription["subscription_id"]

    print(f"✅ Payment includes invoice_id={test_payment['invoice_id']}, subscription_id={test_payment['subscription_id']}")

    # Cleanup
    await test_db.payments.delete_one({"payment_id": payment_id})


@pytest.mark.asyncio
async def test_apply_payment_to_invoice_updates_invoice_amount_paid(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_subscription,
    test_invoice,
    test_company_user,
    admin_headers
):
    """
    TEST: POST /api/v1/payments/{id}/apply-to-invoice updates invoice.amount_paid

    NOTE: This endpoint is ALREADY IMPLEMENTED but may not update amount_paid correctly

    EXPECTED FAILURE:
    - Invoice.amount_paid not updated
    - Invoice.amount_due not recalculated
    - Payment.invoice_id not set

    SUCCESS CRITERIA:
    - Invoice.amount_paid increases by payment amount
    - Invoice.amount_due = total_amount - amount_paid
    - Payment.invoice_id set to invoice_number
    """
    # Create a payment
    payment_id = f"PAY-TEST-{uuid.uuid4().hex[:8].upper()}"
    payment_doc = {
        "payment_id": payment_id,
        "company_name": test_company["company_name"],
        "user_email": test_company_user["email"],
        "invoice_id": None,  # Not yet linked
        "subscription_id": test_subscription["subscription_id"],
        "amount": 30.0,
        "payment_method": "credit_card",
        "payment_date": datetime.now(timezone.utc),
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.payments.insert_one(payment_doc)
    print(f"✅ Created payment {payment_id} for ${payment_doc['amount']}")

    # Verify invoice initial state
    invoice_before = await test_db.invoices.find_one({"invoice_number": test_invoice["invoice_number"]})
    print(f"📊 Invoice before: amount_paid=${invoice_before['amount_paid']}, amount_due=${invoice_before['amount_due']}")

    # Apply payment to invoice
    apply_data = {
        "invoice_id": test_invoice["invoice_number"]
    }

    print(f"\n📤 POST /api/v1/payments/{payment_id}/apply-to-invoice")
    response = await http_client.post(
        f"/api/v1/payments/{payment_id}/apply-to-invoice",
        json=apply_data,
        headers=admin_headers
    )

    print(f"📥 Response: {response.status_code}")
    if response.status_code not in [200, 201]:
        print(f"❌ ERROR: {response.text}")

    assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"

    # VERIFY: Invoice updated in database
    invoice_after = await test_db.invoices.find_one({"invoice_number": test_invoice["invoice_number"]})

    expected_amount_paid = invoice_before["amount_paid"] + payment_doc["amount"]  # 0 + 30 = 30
    expected_amount_due = test_invoice["total_amount"] - expected_amount_paid  # 54 - 30 = 24

    assert invoice_after["amount_paid"] == expected_amount_paid, \
        f"Expected amount_paid={expected_amount_paid}, got {invoice_after['amount_paid']}"

    assert invoice_after["amount_due"] == expected_amount_due, \
        f"Expected amount_due={expected_amount_due}, got {invoice_after['amount_due']}"

    assert invoice_after["status"] == "partial", \
        f"Expected status='partial' (partial payment), got {invoice_after['status']}"

    print(f"📊 Invoice after: amount_paid=${invoice_after['amount_paid']}, amount_due=${invoice_after['amount_due']}, status={invoice_after['status']}")

    # VERIFY: Payment linked to invoice
    payment_after = await test_db.payments.find_one({"payment_id": payment_id})
    assert payment_after["invoice_id"] == test_invoice["invoice_number"], \
        f"Expected payment.invoice_id={test_invoice['invoice_number']}, got {payment_after.get('invoice_id')}"

    print(f"✅ Payment applied: invoice.amount_paid updated, payment.invoice_id set")

    # Cleanup
    await test_db.payments.delete_one({"payment_id": payment_id})
    # Restore invoice state
    await test_db.invoices.update_one(
        {"invoice_number": test_invoice["invoice_number"]},
        {"$set": {"amount_paid": 0.0, "amount_due": test_invoice["total_amount"], "status": "pending"}}
    )


@pytest.mark.asyncio
async def test_apply_full_payment_changes_invoice_status_to_paid(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_subscription,
    test_invoice,
    test_company_user,
    admin_headers
):
    """
    TEST: Apply full payment to invoice → status changes to 'paid'

    EXPECTED FAILURE: Status may not update to 'paid'

    SUCCESS CRITERIA:
    - amount_paid = total_amount
    - amount_due = 0
    - status = 'paid'
    """
    # Create payment for full invoice amount
    payment_id = f"PAY-TEST-{uuid.uuid4().hex[:8].upper()}"
    payment_doc = {
        "payment_id": payment_id,
        "company_name": test_company["company_name"],
        "user_email": test_company_user["email"],
        "invoice_id": None,
        "subscription_id": test_subscription["subscription_id"],
        "amount": test_invoice["total_amount"],  # Full amount: 54.0
        "payment_method": "credit_card",
        "payment_date": datetime.now(timezone.utc),
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.payments.insert_one(payment_doc)
    print(f"✅ Created FULL payment {payment_id} for ${payment_doc['amount']}")

    # Apply payment
    apply_data = {"invoice_id": test_invoice["invoice_number"]}

    print(f"\n📤 POST /api/v1/payments/{payment_id}/apply-to-invoice (FULL PAYMENT)")
    response = await http_client.post(
        f"/api/v1/payments/{payment_id}/apply-to-invoice",
        json=apply_data,
        headers=admin_headers
    )

    assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"

    # VERIFY: Invoice fully paid
    invoice_after = await test_db.invoices.find_one({"invoice_number": test_invoice["invoice_number"]})

    assert invoice_after["amount_paid"] == test_invoice["total_amount"], \
        f"Expected amount_paid={test_invoice['total_amount']}, got {invoice_after['amount_paid']}"

    assert invoice_after["amount_due"] == 0.0, \
        f"Expected amount_due=0.0, got {invoice_after['amount_due']}"

    assert invoice_after["status"] == "paid", \
        f"Expected status='paid', got {invoice_after['status']}"

    print(f"✅ Invoice FULLY PAID: amount_paid=${invoice_after['amount_paid']}, amount_due=$0, status=paid")

    # Cleanup
    await test_db.payments.delete_one({"payment_id": payment_id})
    await test_db.invoices.update_one(
        {"invoice_number": test_invoice["invoice_number"]},
        {"$set": {"amount_paid": 0.0, "amount_due": test_invoice["total_amount"], "status": "pending"}}
    )


@pytest.mark.asyncio
async def test_apply_multiple_payments_to_same_invoice(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_subscription,
    test_invoice,
    test_company_user,
    admin_headers
):
    """
    TEST: Apply multiple payments to same invoice - amounts accumulate

    EXPECTED FAILURE: amount_paid may not accumulate correctly

    SUCCESS CRITERIA:
    - First payment: amount_paid = payment1_amount
    - Second payment: amount_paid = payment1_amount + payment2_amount
    - amount_due recalculated each time
    """
    # Payment 1
    payment1_id = f"PAY-TEST-{uuid.uuid4().hex[:8].upper()}"
    payment1_doc = {
        "payment_id": payment1_id,
        "company_name": test_company["company_name"],
        "user_email": test_company_user["email"],
        "invoice_id": None,
        "subscription_id": test_subscription["subscription_id"],
        "amount": 20.0,
        "payment_method": "credit_card",
        "payment_date": datetime.now(timezone.utc),
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.payments.insert_one(payment1_doc)
    print(f"✅ Created payment 1: ${payment1_doc['amount']}")

    # Payment 2
    payment2_id = f"PAY-TEST-{uuid.uuid4().hex[:8].upper()}"
    payment2_doc = {
        "payment_id": payment2_id,
        "company_name": test_company["company_name"],
        "user_email": test_company_user["email"],
        "invoice_id": None,
        "subscription_id": test_subscription["subscription_id"],
        "amount": 34.0,
        "payment_method": "bank_transfer",
        "payment_date": datetime.now(timezone.utc),
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.payments.insert_one(payment2_doc)
    print(f"✅ Created payment 2: ${payment2_doc['amount']}")

    # Apply payment 1
    print(f"\n📤 Apply payment 1 (${payment1_doc['amount']})")
    response1 = await http_client.post(
        f"/api/v1/payments/{payment1_id}/apply-to-invoice",
        json={"invoice_id": test_invoice["invoice_number"]},
        headers=admin_headers
    )
    assert response1.status_code in [200, 201]

    invoice_after_1 = await test_db.invoices.find_one({"invoice_number": test_invoice["invoice_number"]})
    assert invoice_after_1["amount_paid"] == 20.0
    assert invoice_after_1["amount_due"] == 34.0  # 54 - 20
    print(f"📊 After payment 1: amount_paid=$20, amount_due=$34")

    # Apply payment 2
    print(f"\n📤 Apply payment 2 (${payment2_doc['amount']})")
    response2 = await http_client.post(
        f"/api/v1/payments/{payment2_id}/apply-to-invoice",
        json={"invoice_id": test_invoice["invoice_number"]},
        headers=admin_headers
    )
    assert response2.status_code in [200, 201]

    invoice_after_2 = await test_db.invoices.find_one({"invoice_number": test_invoice["invoice_number"]})
    assert invoice_after_2["amount_paid"] == 54.0, f"Expected 54.0, got {invoice_after_2['amount_paid']}"
    assert invoice_after_2["amount_due"] == 0.0
    assert invoice_after_2["status"] == "paid"
    print(f"📊 After payment 2: amount_paid=$54, amount_due=$0, status=paid")

    print(f"✅ Multiple payments accumulated correctly")

    # Cleanup
    await test_db.payments.delete_many({"payment_id": {"$in": [payment1_id, payment2_id]}})
    await test_db.invoices.update_one(
        {"invoice_number": test_invoice["invoice_number"]},
        {"$set": {"amount_paid": 0.0, "amount_due": test_invoice["total_amount"], "status": "pending"}}
    )


@pytest.mark.asyncio
async def test_overpayment_handling(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_subscription,
    test_invoice,
    test_company_user,
    admin_headers
):
    """
    TEST: Apply payment larger than invoice amount - handle overpayment

    EXPECTED FAILURE: Overpayment logic may not be implemented

    SUCCESS CRITERIA:
    - Either: Reject overpayment with error
    - Or: Accept overpayment, amount_paid = payment amount, amount_due = negative (credit)
    """
    # Create overpayment (invoice is $54, payment is $100)
    payment_id = f"PAY-TEST-{uuid.uuid4().hex[:8].upper()}"
    payment_doc = {
        "payment_id": payment_id,
        "company_name": test_company["company_name"],
        "user_email": test_company_user["email"],
        "invoice_id": None,
        "subscription_id": test_subscription["subscription_id"],
        "amount": 100.0,  # More than invoice total
        "payment_method": "credit_card",
        "payment_date": datetime.now(timezone.utc),
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.payments.insert_one(payment_doc)
    print(f"✅ Created OVERPAYMENT {payment_id} for $100 (invoice is only $54)")

    # Try to apply overpayment
    print(f"\n📤 POST /api/v1/payments/{payment_id}/apply-to-invoice (OVERPAYMENT)")
    response = await http_client.post(
        f"/api/v1/payments/{payment_id}/apply-to-invoice",
        json={"invoice_id": test_invoice["invoice_number"]},
        headers=admin_headers
    )

    print(f"📥 Response: {response.status_code}")

    # VERIFY: Either rejected or handled gracefully
    if response.status_code == 400:
        # Option 1: Rejected overpayment
        print(f"✅ Overpayment rejected (as expected): {response.json()}")
    elif response.status_code in [200, 201]:
        # Option 2: Accepted overpayment
        invoice_after = await test_db.invoices.find_one({"invoice_number": test_invoice["invoice_number"]})

        # Check if credit applied
        assert invoice_after["amount_paid"] >= test_invoice["total_amount"]
        assert invoice_after["status"] in ["paid", "overpaid", "credit"]

        print(f"✅ Overpayment accepted: amount_paid=${invoice_after['amount_paid']}, status={invoice_after['status']}")
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")

    # Cleanup
    await test_db.payments.delete_one({"payment_id": payment_id})
    await test_db.invoices.update_one(
        {"invoice_number": test_invoice["invoice_number"]},
        {"$set": {"amount_paid": 0.0, "amount_due": test_invoice["total_amount"], "status": "pending"}}
    )


@pytest.mark.asyncio
async def test_payment_without_invoice_has_null_invoice_id(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_subscription,
    test_company_user,
    admin_headers
):
    """
    TEST: Payment created without invoice_id should have invoice_id=null

    EXPECTED FAILURE: Field may not exist in response

    SUCCESS CRITERIA:
    - Payment response includes invoice_id field
    - invoice_id is null for unlinked payments
    """
    # Create payment without invoice
    payment_id = f"PAY-TEST-{uuid.uuid4().hex[:8].upper()}"
    payment_doc = {
        "payment_id": payment_id,
        "company_name": test_company["company_name"],
        "user_email": test_company_user["email"],
        "invoice_id": None,  # No invoice
        "subscription_id": test_subscription["subscription_id"],
        "amount": 25.0,
        "payment_method": "credit_card",
        "payment_date": datetime.now(timezone.utc),
        "status": "completed",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await test_db.payments.insert_one(payment_doc)
    print(f"✅ Created payment {payment_id} WITHOUT invoice link")

    # GET payments
    print(f"\n📤 GET /api/v1/payments/")
    response = await http_client.get("/api/v1/payments/", headers=admin_headers)

    assert response.status_code == 200
    response_data = response.json()
    assert response_data.get("success") is True
    payments = response_data["data"]["payments"]

    test_payment = next((p for p in payments if p.get("payment_id") == payment_id), None)
    assert test_payment is not None

    # VERIFY: invoice_id field exists and is null
    assert "invoice_id" in test_payment, "Payment missing invoice_id field"
    assert test_payment["invoice_id"] is None, f"Expected invoice_id=null, got {test_payment['invoice_id']}"

    print(f"✅ Unlinked payment has invoice_id=null (as expected)")

    # Cleanup
    await test_db.payments.delete_one({"payment_id": payment_id})


# ============================================================================
# End of Tests
# ============================================================================
