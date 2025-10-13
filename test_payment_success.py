#!/usr/bin/env python3
"""
Test script for payment success endpoint
"""
import requests
import json

# Test 1: camelCase format (recommended for frontend)
test_camelcase = {
    'customerEmail': 'test@example.com',
    'paymentIntentId': 'payment_sq_1760060540428_wq00qen6d',
    'amount': 10.50,
    'currency': 'USD',
    'paymentMethod': 'square'
}

# Test 2: snake_case format (also accepted)
test_snakecase = {
    'customer_email': 'test@example.com',
    'payment_intent_id': 'pi_1234567890',
    'amount': 10.50
}

def test_payment_endpoint(payload, test_name):
    """Test the payment success endpoint"""
    url = 'http://localhost:8000/api/payment/success'

    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"{'='*80}")
    print(f"Payload:\n{json.dumps(payload, indent=2)}")

    try:
        response = requests.post(url, json=payload, timeout=10)

        print(f"\nStatus Code: {response.status_code}")
        print(f"Response:\n{json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            print(f"✅ SUCCESS: {test_name}")
        else:
            print(f"❌ FAILED: {test_name}")

    except requests.exceptions.ConnectionError:
        print(f"❌ ERROR: Cannot connect to server. Make sure it's running on http://localhost:8000")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    print("Payment Success Endpoint Test")
    print("="*80)

    # Test 1: camelCase format
    test_payment_endpoint(test_camelcase, "Test 1: camelCase format (recommended)")

    # Test 2: snake_case format
    test_payment_endpoint(test_snakecase, "Test 2: snake_case format")

    print(f"\n{'='*80}")
    print("Test complete!")
    print(f"{'='*80}")
