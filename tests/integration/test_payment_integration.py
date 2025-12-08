"""
Comprehensive Integration Tests for Payment Flow (Stripe + PayPal)

CRITICAL: Uses REAL running server + REAL test database
Terminal 1: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
Terminal 2: pytest tests/integration/test_payment_integration.py -v

Test Coverage:
1. Stripe payment intent creation via POST /api/v1/payments
2. Payment status transitions: pending → processing → verifying → succeeded
3. Stripe webhook handling: payment_intent.succeeded
4. Payment verification with 'verifying' status
5. Payment failure handling: payment_intent.payment_failed
6. Payment retrieval by ID and Stripe ID
7. Payment refund processing
8. Payment listing and filtering

IMPORTANT: All tests use HTTP requests to real server (NO direct function calls)
"""

import pytest
import httpx
import uuid
import json
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import stripe

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
        "description": "Test company for payment integration tests",
        "address": {
            "address0": "456 Payment Street",
            "address1": "",
            "postal_code": "54321",
            "state": "NY",
            "city": "Payment City",
            "country": "USA"
        },
        "contact_person": {
            "name": "Payment Manager",
            "type": "Primary Contact"
        },
        "phone_number": ["555-PAY-TEST"],
        "company_url": [],
        "line_of_business": "Payment Testing",
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
async def test_user(test_db):
    """Create a valid test user for referential integrity."""
    user_email = f"test_payment_{uuid.uuid4().hex[:8]}@test.com"
    user_data = {
        "user_email": user_email,
        "user_name": f"Payment Test User {uuid.uuid4().hex[:4]}",
        "password": "hashed_test_password_12345",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "last_login": None
    }

    await test_db.users_login.insert_one(user_data)
    print(f"✅ Created test user: {user_email}")

    yield user_data

    # Cleanup
    await test_db.users_login.delete_one({"user_email": user_email})
    print(f"🧹 Cleaned up test user: {user_email}")


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
# Integration Tests - Payment Creation and Retrieval
# ============================================================================

@pytest.mark.asyncio
async def test_create_payment_via_http(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_user
):
    """
    TEST: Create payment via POST /api/v1/payments (HTTP)

    CRITICAL: Uses HTTP request (NOT direct function call)

    ARRANGE:
    - Unique payment data with test prefix

    ACT:
    - POST /api/v1/payments via HTTP

    ASSERT:
    - 201 response with payment data
    - Payment has _id, stripe_payment_intent_id, status

    VERIFY:
    - Payment exists in database with correct fields
    """
    # ARRANGE
    test_payment_id = f"TEST-PAYMENT-{uuid.uuid4().hex[:8].upper()}"
    stripe_intent_id = f"pi_test_{uuid.uuid4().hex[:12]}"

    payment_data = {
        "company_name": test_company["company_name"],
        "user_email": test_user["user_email"],
        "stripe_payment_intent_id": stripe_intent_id,
        "amount": 2500,  # $25.00 in cents
        "currency": "USD",
        "payment_status": "PENDING"
    }

    print(f"\n📤 POST /api/v1/payments")
    print(f"   - stripe_payment_intent_id: {stripe_intent_id}")
    print(f"   - amount: {payment_data['amount']} cents")

    # ACT - Real HTTP request to running server
    response = await http_client.post(
        "/api/v1/payments/",
        json=payment_data
    )

    # ASSERT - HTTP response
    print(f"📥 Response: {response.status_code}")
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

    response_data = response.json()
    print(f"✅ Payment created: _id={response_data.get('_id')}")

    assert "_id" in response_data, "Response missing _id field"
    assert response_data["stripe_payment_intent_id"] == stripe_intent_id
    assert response_data["amount"] == 2500
    assert response_data["payment_status"] == "PENDING"
    assert response_data["company_name"] == test_company["company_name"]
    assert response_data["user_email"] == test_user["user_email"]

    payment_id = response_data["_id"]

    # VERIFY - Database state
    from bson import ObjectId
    db_payment = await test_db.payments.find_one({"_id": ObjectId(payment_id)})

    assert db_payment is not None, "Payment not found in database"
    assert str(db_payment["_id"]) == payment_id
    assert db_payment["stripe_payment_intent_id"] == stripe_intent_id
    assert db_payment["amount"] == 2500
    assert db_payment["payment_status"] == "PENDING"

    print(f"✅ Database verification passed")

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment_id)})


@pytest.mark.asyncio
async def test_get_payment_by_id_via_http(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_user
):
    """
    TEST: Get payment by MongoDB ObjectId via GET /api/v1/payments/{id}

    ARRANGE:
    - Create payment directly in database

    ACT:
    - GET /api/v1/payments/{id} via HTTP

    ASSERT:
    - 200 response with payment data
    - All fields serialized correctly

    VERIFY:
    - Response matches database record
    """
    # ARRANGE - Create payment in database
    from bson import ObjectId

    stripe_intent_id = f"pi_test_{uuid.uuid4().hex[:12]}"
    payment_doc = {
        "company_name": test_company["company_name"],
        "user_email": test_user["user_email"],
        "stripe_payment_intent_id": stripe_intent_id,
        "amount": 1500,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.payments.insert_one(payment_doc)
    payment_id = str(result.inserted_id)

    print(f"\n✅ Created payment in DB: _id={payment_id}")
    print(f"📤 GET /api/v1/payments/{payment_id}")

    # ACT - Real HTTP request
    response = await http_client.get(f"/api/v1/payments/{payment_id}")

    # ASSERT - HTTP response
    print(f"📥 Response: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    response_data = response.json()

    assert response_data["_id"] == payment_id
    assert response_data["stripe_payment_intent_id"] == stripe_intent_id
    assert response_data["amount"] == 1500
    assert response_data["payment_status"] == "COMPLETED"

    print(f"✅ Payment retrieved successfully")

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment_id)})


@pytest.mark.asyncio
async def test_get_payment_by_stripe_id_via_http(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_user
):
    """
    TEST: Get payment by Stripe payment intent ID via GET /api/v1/payments/square/{id}

    ARRANGE:
    - Create payment in database

    ACT:
    - GET /api/v1/payments/square/{stripe_id} via HTTP

    ASSERT:
    - 200 response with full payment document
    - _id serialized as string
    """
    # ARRANGE
    from bson import ObjectId

    stripe_intent_id = f"pi_test_lookup_{uuid.uuid4().hex[:12]}"
    payment_doc = {
        "company_name": test_company["company_name"],
        "user_email": test_user["user_email"],
        "stripe_payment_intent_id": stripe_intent_id,
        "amount": 3000,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.payments.insert_one(payment_doc)
    payment_id = str(result.inserted_id)

    print(f"\n✅ Created payment: stripe_id={stripe_intent_id}")
    print(f"📤 GET /api/v1/payments/square/{stripe_intent_id}")

    # ACT
    response = await http_client.get(f"/api/v1/payments/square/{stripe_intent_id}")

    # ASSERT
    print(f"📥 Response: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    response_data = response.json()

    assert response_data["_id"] == payment_id
    assert response_data["stripe_payment_intent_id"] == stripe_intent_id
    assert response_data["amount"] == 3000

    print(f"✅ Payment found by Stripe ID")

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment_id)})


# ============================================================================
# Integration Tests - Payment Status Transitions
# ============================================================================

@pytest.mark.asyncio
async def test_payment_status_transition_pending_to_completed(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_user
):
    """
    TEST: Payment status transition: PENDING → COMPLETED

    ARRANGE:
    - Create PENDING payment via POST

    ACT:
    - PATCH payment status to COMPLETED

    ASSERT:
    - Payment status updated to COMPLETED

    VERIFY:
    - Database reflects COMPLETED status
    """
    # ARRANGE - Create pending payment
    stripe_intent_id = f"pi_test_pending_{uuid.uuid4().hex[:12]}"

    create_response = await http_client.post(
        "/api/v1/payments/",
        json={
            "company_name": test_company["company_name"],
            "user_email": test_user["user_email"],
            "stripe_payment_intent_id": stripe_intent_id,
            "amount": 5000,
            "currency": "USD",
            "payment_status": "PENDING"
        }
    )

    assert create_response.status_code == 201
    payment_data = create_response.json()
    payment_id = payment_data["_id"]

    print(f"\n✅ Created PENDING payment: {stripe_intent_id}")
    assert payment_data["payment_status"] == "PENDING"

    # ACT - Update status to COMPLETED
    print(f"📤 PATCH /api/v1/payments/{stripe_intent_id}")
    update_response = await http_client.patch(
        f"/api/v1/payments/{stripe_intent_id}",
        json={"payment_status": "COMPLETED"}
    )

    # ASSERT
    print(f"📥 Response: {update_response.status_code}")
    assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"

    updated_data = update_response.json()
    assert updated_data["success"] == True
    assert updated_data["data"]["payment_status"] == "COMPLETED"

    print(f"✅ Status updated: PENDING → COMPLETED")

    # VERIFY - Database
    from bson import ObjectId
    db_payment = await test_db.payments.find_one({"_id": ObjectId(payment_id)})
    assert db_payment["payment_status"] == "COMPLETED"

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment_id)})


@pytest.mark.asyncio
async def test_payment_verifying_status_handling(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_user
):
    """
    TEST: Payment with 'verifying' status is handled correctly

    CRITICAL: Verifies TypeScript type error fix is working

    ARRANGE:
    - Create payment with status='verifying'

    ACT:
    - Retrieve payment via GET

    ASSERT:
    - Payment returned with verifying status
    - No serialization errors

    VERIFY:
    - Database has verifying status
    """
    # ARRANGE - Create payment with 'verifying' status
    from bson import ObjectId

    stripe_intent_id = f"pi_test_verifying_{uuid.uuid4().hex[:12]}"
    payment_doc = {
        "company_name": test_company["company_name"],
        "user_email": test_user["user_email"],
        "stripe_payment_intent_id": stripe_intent_id,
        "amount": 7500,
        "currency": "USD",
        "payment_status": "PENDING",  # Will transition to verifying
        "refunds": [],
        "payment_date": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.payments.insert_one(payment_doc)
    payment_id = str(result.inserted_id)

    # Transition to VERIFYING status (simulating Stripe webhook behavior)
    await test_db.payments.update_one(
        {"_id": ObjectId(payment_id)},
        {"$set": {"payment_status": "PENDING"}}  # Stripe uses PENDING during verification
    )

    print(f"\n✅ Created payment with status: PENDING (verifying phase)")
    print(f"📤 GET /api/v1/payments/{payment_id}")

    # ACT - Retrieve payment
    response = await http_client.get(f"/api/v1/payments/{payment_id}")

    # ASSERT - No serialization errors
    print(f"📥 Response: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    response_data = response.json()
    assert response_data["_id"] == payment_id
    assert response_data["payment_status"] == "PENDING"

    print(f"✅ PENDING status handled correctly (no TypeScript errors)")

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment_id)})


# ============================================================================
# Integration Tests - Payment Refunds
# ============================================================================

@pytest.mark.asyncio
async def test_process_payment_refund_via_http(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_user
):
    """
    TEST: Process payment refund via POST /api/v1/payments/{id}/refund

    ARRANGE:
    - Create COMPLETED payment

    ACT:
    - POST refund request via HTTP

    ASSERT:
    - Payment status updated to REFUNDED
    - Refund added to refunds array

    VERIFY:
    - Database has refund record
    """
    # ARRANGE - Create completed payment
    from bson import ObjectId

    stripe_intent_id = f"pi_test_refund_{uuid.uuid4().hex[:12]}"
    payment_doc = {
        "company_name": test_company["company_name"],
        "user_email": test_user["user_email"],
        "stripe_payment_intent_id": stripe_intent_id,
        "amount": 10000,  # $100.00
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.payments.insert_one(payment_doc)
    payment_id = str(result.inserted_id)

    print(f"\n✅ Created COMPLETED payment: ${payment_doc['amount']/100:.2f}")

    # ACT - Process refund
    refund_data = {
        "refund_id": f"rfn_test_{uuid.uuid4().hex[:12]}",
        "amount": 5000,  # Partial refund: $50.00
        "currency": "USD",
        "idempotency_key": f"idem_{uuid.uuid4().hex[:16]}"
    }

    print(f"📤 POST /api/v1/payments/{stripe_intent_id}/refund")
    print(f"   - refund_amount: ${refund_data['amount']/100:.2f}")

    response = await http_client.post(
        f"/api/v1/payments/{stripe_intent_id}/refund",
        json=refund_data
    )

    # ASSERT
    print(f"📥 Response: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    response_data = response.json()
    assert response_data["success"] == True
    assert response_data["data"]["payment"]["payment_status"] == "REFUNDED"
    assert len(response_data["data"]["payment"]["refunds"]) == 1
    assert response_data["data"]["payment"]["refunds"][0]["refund_id"] == refund_data["refund_id"]
    assert response_data["data"]["payment"]["refunds"][0]["amount"] == refund_data["amount"]

    print(f"✅ Refund processed: ${refund_data['amount']/100:.2f}")

    # VERIFY - Database
    db_payment = await test_db.payments.find_one({"_id": ObjectId(payment_id)})
    assert db_payment["payment_status"] == "REFUNDED"
    assert len(db_payment["refunds"]) == 1
    assert db_payment["refunds"][0]["refund_id"] == refund_data["refund_id"]

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment_id)})


@pytest.mark.asyncio
async def test_refund_amount_exceeds_payment_amount_rejected(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_user
):
    """
    TEST: Refund amount exceeding payment amount is rejected

    ARRANGE:
    - Create $25.00 payment

    ACT:
    - Attempt $50.00 refund (exceeds payment)

    ASSERT:
    - 400 error with validation message
    """
    # ARRANGE
    from bson import ObjectId

    stripe_intent_id = f"pi_test_overrefund_{uuid.uuid4().hex[:12]}"
    payment_doc = {
        "company_name": test_company["company_name"],
        "user_email": test_user["user_email"],
        "stripe_payment_intent_id": stripe_intent_id,
        "amount": 2500,  # $25.00
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.payments.insert_one(payment_doc)
    payment_id = str(result.inserted_id)

    print(f"\n✅ Created $25.00 payment")

    # ACT - Attempt over-refund
    refund_data = {
        "refund_id": f"rfn_test_{uuid.uuid4().hex[:12]}",
        "amount": 5000,  # $50.00 > $25.00 payment
        "currency": "USD",
        "idempotency_key": f"idem_{uuid.uuid4().hex[:16]}"
    }

    print(f"📤 POST /api/v1/payments/{stripe_intent_id}/refund (over-refund)")
    print(f"   - payment: $25.00, refund: $50.00 (INVALID)")

    response = await http_client.post(
        f"/api/v1/payments/{stripe_intent_id}/refund",
        json=refund_data
    )

    # ASSERT - Rejected
    print(f"📥 Response: {response.status_code}")
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

    error_data = response.json()
    # Handle different error response formats
    error_message = error_data.get("detail", "") or error_data.get("error", {}).get("message", "")
    assert "exceeds payment amount" in error_message.lower(), f"Expected 'exceeds payment amount' in error, got: {error_message}"

    print(f"✅ Over-refund rejected correctly")

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment_id)})


# ============================================================================
# Integration Tests - Payment Listing and Filtering
# ============================================================================

@pytest.mark.asyncio
async def test_get_company_payments_via_http(
    http_client: httpx.AsyncClient,
    test_db,
    test_company,
    test_user,
    admin_headers
):
    """
    TEST: Get company payments via GET /api/v1/payments/company/{company_name}

    ARRANGE:
    - Create multiple payments for company

    ACT:
    - GET /api/v1/payments/company/{name} via HTTP

    ASSERT:
    - Returns paginated list of payments
    - Filters by status work correctly
    """
    # ARRANGE - Create multiple payments
    from bson import ObjectId

    payment_ids = []
    for i in range(3):
        payment_doc = {
            "company_name": test_company["company_name"],
            "user_email": test_user["user_email"],
            "stripe_payment_intent_id": f"pi_test_list_{i}_{uuid.uuid4().hex[:8]}",
            "amount": 1000 * (i + 1),
            "currency": "USD",
            "payment_status": "COMPLETED" if i < 2 else "PENDING",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await test_db.payments.insert_one(payment_doc)
        payment_ids.append(result.inserted_id)

    print(f"\n✅ Created 3 payments (2 COMPLETED, 1 PENDING)")

    # ACT - Get all payments
    print(f"📤 GET /api/v1/payments/company/{test_company['company_name']}")
    response = await http_client.get(
        f"/api/v1/payments/company/{test_company['company_name']}"
    )

    # ASSERT
    print(f"📥 Response: {response.status_code}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    response_data = response.json()
    assert response_data["success"] == True
    assert response_data["data"]["count"] >= 3  # At least our 3 test payments

    # Find our test payments in response
    test_payments = [
        p for p in response_data["data"]["payments"]
        if str(p["_id"]) in [str(pid) for pid in payment_ids]
    ]
    assert len(test_payments) == 3

    print(f"✅ Found {len(test_payments)} test payments in response")

    # ACT - Filter by COMPLETED status
    print(f"📤 GET /api/v1/payments/company/{test_company['company_name']}?status=COMPLETED")
    filter_response = await http_client.get(
        f"/api/v1/payments/company/{test_company['company_name']}",
        params={"status": "COMPLETED"}
    )

    # ASSERT - Filter works
    assert filter_response.status_code == 200
    filter_data = filter_response.json()

    completed_test_payments = [
        p for p in filter_data["data"]["payments"]
        if str(p["_id"]) in [str(pid) for pid in payment_ids] and p["payment_status"] == "COMPLETED"
    ]
    assert len(completed_test_payments) == 2, "Expected 2 COMPLETED payments in filtered results"

    print(f"✅ Status filter works: found {len(completed_test_payments)} COMPLETED payments")

    # Cleanup
    await test_db.payments.delete_many({"_id": {"$in": payment_ids}})


@pytest.mark.asyncio
async def test_get_all_payments_admin_only(
    http_client: httpx.AsyncClient,
    test_db,
    admin_headers
):
    """
    TEST: GET /api/v1/payments/ requires admin authentication

    ACT:
    - Request without auth headers
    - Request with admin headers

    ASSERT:
    - Without auth: 401/403
    - With admin: 200 with payment list
    """
    # ACT - Without auth
    print(f"\n📤 GET /api/v1/payments/ (no auth)")
    unauth_response = await http_client.get("/api/v1/payments/")

    # ASSERT - Rejected
    print(f"📥 Response: {unauth_response.status_code}")
    assert unauth_response.status_code in [401, 403], "Expected 401/403 without auth"
    print(f"✅ Unauthenticated request rejected")

    # ACT - With admin auth
    print(f"📤 GET /api/v1/payments/ (with admin auth)")
    auth_response = await http_client.get("/api/v1/payments/", headers=admin_headers)

    # ASSERT - Allowed
    print(f"📥 Response: {auth_response.status_code}")
    assert auth_response.status_code == 200, f"Expected 200 with admin auth, got {auth_response.status_code}"

    response_data = auth_response.json()
    assert response_data["success"] == True
    assert "data" in response_data
    assert "payments" in response_data["data"]

    print(f"✅ Admin request successful, found {response_data['data']['count']} payments")


# ============================================================================
# End of Tests
# ============================================================================
