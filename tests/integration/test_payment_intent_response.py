"""
Integration test for payment intent API response structure.

This test verifies the actual API response format from the backend
and identifies the mismatch with frontend expectations.

ISSUE: Frontend expects response.data.data.clientSecret
ACTUAL: Backend returns response.data.clientSecret

Backend Response (from payment_simplified.py lines 368-374, 395-401):
{
    "clientSecret": "pi_xxx_secret_yyy",
    "paymentIntentId": "pi_xxx"
}

Axios wraps this in response.data:
{
    data: {
        clientSecret: "...",
        paymentIntentId: "..."
    }
}

Frontend Bug (api.ts line 415):
    return response.data.data!;  // ❌ WRONG - response.data.data is undefined

Frontend Fix:
    return response.data;  // ✅ CORRECT - access clientSecret directly
"""

import pytest
import httpx
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_payment_intent_response_structure():
    """
    Test the payment intent creation endpoint response structure.

    This test verifies:
    1. Backend returns { clientSecret, paymentIntentId } directly
    2. Response does NOT have nested .data.data structure
    3. Frontend should access response.data (not response.data.data)
    """

    # ARRANGE: Prepare request data
    request_data = {
        "amount": 1000,  # $10.00 in cents
        "currency": "usd",
        "metadata": {
            "timestamp": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
            "test": "true"
        },
        "description": "Test payment intent",
        "receipt_email": "test@example.com"
    }

    # ACT: Make real HTTP request to running server
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        try:
            response = await client.post(
                "/api/payment/create-intent",
                json=request_data,
                timeout=10.0
            )
        except httpx.ConnectError:
            pytest.skip("Server not running. Start with: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000")

    # ASSERT: Verify response structure
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    response_json = response.json()

    # VERIFY: Backend returns flat structure (not nested in .data)
    assert "clientSecret" in response_json, f"Missing 'clientSecret' in response: {response_json.keys()}"
    assert "paymentIntentId" in response_json, f"Missing 'paymentIntentId' in response: {response_json.keys()}"

    # VERIFY: No nested .data field
    assert "data" not in response_json, f"Response should NOT have nested 'data' field. Got: {response_json.keys()}"

    # VERIFY: Field values are correct type
    client_secret = response_json["clientSecret"]
    payment_intent_id = response_json["paymentIntentId"]

    assert isinstance(client_secret, str), f"clientSecret should be string, got {type(client_secret)}"
    assert isinstance(payment_intent_id, str), f"paymentIntentId should be string, got {type(payment_intent_id)}"
    assert len(client_secret) > 0, "clientSecret should not be empty"
    assert len(payment_intent_id) > 0, "paymentIntentId should not be empty"

    # VERIFY: Test mode response format (mock payment intent)
    # In test mode, backend returns mock values (lines 368-374)
    assert client_secret.startswith("pi_"), f"clientSecret should start with 'pi_', got: {client_secret[:10]}"
    assert payment_intent_id.startswith("pi_"), f"paymentIntentId should start with 'pi_', got: {payment_intent_id[:10]}"

    print("\n" + "=" * 80)
    print("✅ BACKEND RESPONSE STRUCTURE (CORRECT):")
    print("=" * 80)
    print(f"response.data = {{")
    print(f"    'clientSecret': '{client_secret}',")
    print(f"    'paymentIntentId': '{payment_intent_id}'")
    print(f"}}")
    print("\n" + "=" * 80)
    print("❌ FRONTEND BUG (api.ts line 415):")
    print("=" * 80)
    print("return response.data.data!;  // ❌ WRONG - .data.data is undefined")
    print("\n" + "=" * 80)
    print("✅ FRONTEND FIX:")
    print("=" * 80)
    print("return response.data;  // ✅ CORRECT - access clientSecret directly")
    print("=" * 80 + "\n")


@pytest.mark.asyncio
async def test_frontend_axios_response_wrapping():
    """
    Demonstrate how Axios wraps the backend response.

    Backend returns: { clientSecret, paymentIntentId }
    Axios wraps as:   { data: { clientSecret, paymentIntentId } }

    So frontend should access: response.data.clientSecret
    NOT: response.data.data.clientSecret (which is undefined)
    """

    # ARRANGE
    request_data = {
        "amount": 500,  # $5.00
        "currency": "usd",
        "metadata": {"test": "axios_wrapping"},
        "description": "Axios wrapper test"
    }

    # ACT
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        try:
            response = await client.post("/api/payment/create-intent", json=request_data)
        except httpx.ConnectError:
            pytest.skip("Server not running")

    # ASSERT
    assert response.status_code == 200
    backend_response = response.json()

    # SIMULATE: How Axios wraps the response
    axios_response = {
        "data": backend_response,  # Axios wraps backend response in .data
        "status": response.status_code,
        "statusText": "OK",
        "headers": dict(response.headers)
    }

    # VERIFY: Axios response structure
    assert "data" in axios_response
    assert "clientSecret" in axios_response["data"]
    assert "paymentIntentId" in axios_response["data"]

    # VERIFY: .data.data does NOT exist (this is the bug)
    assert "data" not in axios_response["data"], "Axios response should NOT have nested .data.data"

    print("\n" + "=" * 80)
    print("🔍 AXIOS RESPONSE STRUCTURE:")
    print("=" * 80)
    print("axios_response = {")
    print(f"    'data': {{")
    print(f"        'clientSecret': '{axios_response['data']['clientSecret']}',")
    print(f"        'paymentIntentId': '{axios_response['data']['paymentIntentId']}'")
    print(f"    }},")
    print(f"    'status': {axios_response['status']},")
    print(f"    'statusText': '{axios_response['statusText']}'")
    print("}")
    print("\n" + "=" * 80)
    print("✅ CORRECT ACCESS:")
    print("=" * 80)
    print(f"response.data.clientSecret = '{axios_response['data']['clientSecret']}'")
    print(f"response.data.paymentIntentId = '{axios_response['data']['paymentIntentId']}'")
    print("\n" + "=" * 80)
    print("❌ BUG (what frontend currently does):")
    print("=" * 80)
    print("response.data.data.clientSecret  // ❌ TypeError: Cannot destructure...")
    print("response.data.data is undefined!")
    print("=" * 80 + "\n")


@pytest.mark.asyncio
async def test_payment_intent_with_different_amounts():
    """
    Test multiple payment amounts to ensure consistent response structure.
    """
    test_amounts = [
        (100, "$1.00"),
        (1000, "$10.00"),
        (5000, "$50.00"),
        (10000, "$100.00")
    ]

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        for amount, display in test_amounts:
            # ACT
            try:
                response = await client.post(
                    "/api/payment/create-intent",
                    json={
                        "amount": amount,
                        "currency": "usd",
                        "metadata": {"test_amount": display}
                    }
                )
            except httpx.ConnectError:
                pytest.skip("Server not running")

            # ASSERT
            assert response.status_code == 200
            data = response.json()

            # VERIFY: Same structure for all amounts
            assert "clientSecret" in data
            assert "paymentIntentId" in data
            assert "data" not in data  # Should NOT have nested .data

            print(f"✅ {display}: clientSecret={data['clientSecret'][:20]}...")
