"""
Minimal Integration Test: Complete Stripe Payment Flow

CRITICAL: Uses REAL running server + REAL test database
Terminal 1: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
Terminal 2: pytest tests/integration/test_stripe_basic_flow.py -v

Test Coverage:
1. Create payment intent via POST /api/payment/create-intent
2. Simulate Stripe webhook (payment_intent.succeeded)
3. Verify invoice created in database
4. Verify invoice has correct amount and status

IMPORTANT: All tests use HTTP requests to real server (NO direct function calls)
"""

import pytest
import httpx
import json
import time
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

# Import Stripe signature generator
from tests.utils.stripe_test_utils import generate_stripe_webhook_signature

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
async def settings():
    """Get application settings for webhook secret."""
    from app.config import settings
    return settings


# ============================================================================
# Integration Test - Complete Stripe Payment Flow
# ============================================================================

@pytest.mark.asyncio
async def test_complete_stripe_payment_flow(http_client, test_db, settings):
    """
    TEST: Create payment intent → webhook → invoice created

    ARRANGE:
    - Server in test mode (mocks Stripe API calls automatically)
    - Create payment intent via HTTP POST

    ACT:
    - Simulate Stripe webhook (payment_intent.succeeded)

    ASSERT:
    - Webhook returns 200
    - Invoice created in database
    - Invoice has correct amount ($50.00 from 5000 cents)
    - Invoice status is "paid"

    VERIFY:
    - Database state confirms invoice exists
    - Invoice linked to payment_intent_id
    """
    test_email = f"test_{uuid.uuid4().hex[:8]}@example.com"

    print("\n" + "=" * 80)
    print("STEP 1: Create Payment Intent")
    print("=" * 80)

    # STEP 1: Create payment intent
    create_response = await http_client.post(
        "/api/payment/create-intent",
        json={
            "amount": 5000,  # $50.00 in cents
            "currency": "usd",
            "metadata": {"email": test_email}
        }
    )

    print(f"📥 Response: {create_response.status_code}")
    assert create_response.status_code == 200, f"Expected 200, got {create_response.status_code}: {create_response.text}"

    data = create_response.json()
    assert "paymentIntentId" in data, "Response missing paymentIntentId"
    assert "clientSecret" in data, "Response missing clientSecret"

    payment_intent_id = data["paymentIntentId"]
    print(f"✅ Payment Intent Created: {payment_intent_id}")
    print(f"   Amount: $50.00 (5000 cents)")
    print(f"   Currency: USD")
    print(f"   Customer: {test_email}")

    print("\n" + "=" * 80)
    print("STEP 2: Simulate Stripe Webhook (payment_intent.succeeded)")
    print("=" * 80)

    # STEP 2: Simulate Stripe webhook
    webhook_payload = {
        "id": f"evt_test_{uuid.uuid4().hex[:12]}",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": 5000,
                "currency": "usd",
                "customer_email": test_email,
                "metadata": {"email": test_email}
            }
        }
    }

    # Generate valid Stripe signature
    payload_bytes = json.dumps(webhook_payload).encode('utf-8')
    timestamp = int(time.time())
    sig_header = generate_stripe_webhook_signature(
        payload_bytes,
        settings.stripe_webhook_secret,
        timestamp
    )

    print(f"📤 POST /api/webhooks/stripe")
    print(f"   Event ID: {webhook_payload['id']}")
    print(f"   Event Type: {webhook_payload['type']}")
    print(f"   Payment Intent: {payment_intent_id}")

    webhook_response = await http_client.post(
        "/api/webhooks/stripe",
        content=payload_bytes,
        headers={"stripe-signature": sig_header}
    )

    # ASSERT: Webhook accepted
    print(f"📥 Webhook Response: {webhook_response.status_code}")
    assert webhook_response.status_code == 200, f"Expected 200, got {webhook_response.status_code}: {webhook_response.text}"

    webhook_data = webhook_response.json()
    assert webhook_data.get("received") == True, "Webhook not acknowledged"
    print(f"✅ Webhook Accepted: {webhook_data.get('event_id')}")

    print("\n" + "=" * 80)
    print("STEP 3: Verify Invoice Created in Database")
    print("=" * 80)

    # STEP 3: Wait for background processing (webhook uses background tasks)
    # Give the background task time to process
    import asyncio
    await asyncio.sleep(2)  # 2 seconds should be enough for background processing

    # VERIFY: Invoice created in database
    invoice = await test_db.invoices.find_one({"payment_intent_id": payment_intent_id})

    print(f"🔍 Looking for invoice with payment_intent_id: {payment_intent_id}")

    assert invoice is not None, f"Invoice not found for payment_intent_id: {payment_intent_id}"

    print(f"✅ Invoice Found:")
    print(f"   Invoice ID: {invoice['invoice_id']}")
    print(f"   Payment Intent: {invoice['payment_intent_id']}")
    print(f"   Status: {invoice['status']}")
    print(f"   Amount: ${float(invoice['amount'].to_decimal()):.2f}")
    print(f"   Currency: {invoice['currency']}")
    print(f"   Customer: {invoice.get('customer_email')}")

    # ASSERT: Invoice has correct data
    assert invoice["status"] == "paid", f"Expected status 'paid', got '{invoice['status']}'"
    assert float(invoice["amount"].to_decimal()) == 50.00, f"Expected amount $50.00, got ${float(invoice['amount'].to_decimal()):.2f}"
    assert invoice["currency"] == "usd", f"Expected currency 'usd', got '{invoice['currency']}'"
    assert invoice.get("customer_email") == test_email, f"Expected customer_email '{test_email}', got '{invoice.get('customer_email')}'"

    print("\n" + "=" * 80)
    print("TEST PASSED: Complete Stripe Payment Flow")
    print("=" * 80)
    print("✅ Payment intent created successfully")
    print("✅ Webhook processed successfully")
    print("✅ Invoice created with correct data")
    print("✅ Amount converted correctly: 5000 cents → $50.00")
    print("✅ Invoice status set to 'paid'")
    print("=" * 80 + "\n")

    # Cleanup: Delete test invoice
    await test_db.invoices.delete_one({"payment_intent_id": payment_intent_id})
    print(f"🧹 Cleaned up test invoice: {invoice['invoice_id']}")


# ============================================================================
# End of Tests
# ============================================================================
