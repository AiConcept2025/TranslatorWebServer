#!/usr/bin/env python3
"""
Test script for /api/transactions/confirm endpoint
Tests Pydantic validation and endpoint behavior
"""

import requests
import json
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/transactions/confirm"

# Test JWT token (replace with a valid token for your test user)
# You can get this by logging in through the UI or using the login endpoint
TEST_TOKEN = "your_jwt_token_here"


def test_endpoint(test_name: str, payload: Dict[str, Any], headers: Dict[str, str]) -> None:
    """Test the endpoint with a given payload"""
    print("\n" + "=" * 80)
    print(f"TEST: {test_name}")
    print("=" * 80)
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print(f"Headers: {json.dumps(headers, indent=2)}")

    try:
        response = requests.post(ENDPOINT, json=payload, headers=headers)

        print(f"\n📡 Response Status: {response.status_code}")
        print(f"📦 Response Body:")
        try:
            print(json.dumps(response.json(), indent=2))
        except Exception:
            print(response.text)

        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Request Failed: {e}")
        print("=" * 80 + "\n")


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("TESTING /api/transactions/confirm ENDPOINT")
    print("=" * 80)

    # Test 1: Valid request - Payment Success
    print("\n### Test 1: Valid Request - Payment Success")
    test_endpoint(
        test_name="Valid Payment Success",
        payload={
            "square_transaction_id": "sqt_test_123456789",
            "status": True
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_TOKEN}"
        }
    )

    # Test 2: Valid request - Payment Failure
    print("\n### Test 2: Valid Request - Payment Failure")
    test_endpoint(
        test_name="Valid Payment Failure",
        payload={
            "square_transaction_id": "sqt_test_987654321",
            "status": False
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_TOKEN}"
        }
    )

    # Test 3: Invalid request - Missing square_transaction_id
    print("\n### Test 3: Invalid Request - Missing square_transaction_id")
    test_endpoint(
        test_name="Missing square_transaction_id",
        payload={
            "status": True
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_TOKEN}"
        }
    )

    # Test 4: Invalid request - Missing status
    print("\n### Test 4: Invalid Request - Missing status")
    test_endpoint(
        test_name="Missing status",
        payload={
            "square_transaction_id": "sqt_test_123456789"
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_TOKEN}"
        }
    )

    # Test 5: Invalid request - Wrong type for status
    print("\n### Test 5: Invalid Request - Wrong type for status")
    test_endpoint(
        test_name="Wrong type for status",
        payload={
            "square_transaction_id": "sqt_test_123456789",
            "status": "true"  # String instead of boolean
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_TOKEN}"
        }
    )

    # Test 6: Empty request body
    print("\n### Test 6: Invalid Request - Empty Body")
    test_endpoint(
        test_name="Empty Body",
        payload={},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_TOKEN}"
        }
    )

    # Test 7: Missing Authorization header
    print("\n### Test 7: Invalid Request - Missing Auth")
    test_endpoint(
        test_name="Missing Authorization",
        payload={
            "square_transaction_id": "sqt_test_123456789",
            "status": True
        },
        headers={
            "Content-Type": "application/json"
        }
    )

    # Test 8: Wrong Content-Type
    print("\n### Test 8: Invalid Request - Wrong Content-Type")
    response = requests.post(
        ENDPOINT,
        data="square_transaction_id=sqt_test&status=true",  # URL-encoded instead of JSON
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Bearer {TEST_TOKEN}"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Update TEST_TOKEN with a valid JWT token before running!")
    print("You can get a token by logging in through the UI or /api/auth/login endpoint\n")

    # Uncomment to run tests
    # main()

    print("📝 Instructions:")
    print("1. Start the FastAPI server: uvicorn app.main:app --reload")
    print("2. Get a valid JWT token (login through UI or API)")
    print("3. Update TEST_TOKEN in this script")
    print("4. Uncomment main() and run: python test_confirm_endpoint.py")
    print("\n✅ The server logs will show detailed validation and processing steps!")
