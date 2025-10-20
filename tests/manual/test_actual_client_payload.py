#!/usr/bin/env python3
"""
Test with actual client payload that was failing
"""
import requests
import json

# Actual payload from client error log
actual_client_payload = {
    'paymentIntentId': 'payment_sq_1760060540428_wq00qen6d',
    'amount': 0.1,
    'currency': 'USD',
    'paymentMethod': 'square',
    'metadata': {
        'status': 'COMPLETED',
        'cardBrand': 'VISA',
        'last4': '5220',
        'receiptNumber': 'PAYMENT_SQ_1760060540428_WQ00QEN6D',
        'created': '2025-10-10T01:42:20.429Z',
        'simulated': True,
        'customer_email': 'test@example.com'  # Email in metadata
    },
    'timestamp': '2025-10-10T01:42:20.430Z'
}

url = 'http://localhost:8000/api/payment/success'

print("="*80)
print("Testing Actual Client Payload")
print("="*80)
print(f"\nPayload:\n{json.dumps(actual_client_payload, indent=2)}")

try:
    response = requests.post(url, json=actual_client_payload, timeout=10)

    print(f"\n{'='*80}")
    print(f"Status Code: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
    print(f"{'='*80}")

    if response.status_code == 200:
        print("\n✅ SUCCESS: Actual client payload works!")
    else:
        print("\n❌ FAILED: Endpoint returned error")

except requests.exceptions.ConnectionError:
    print("\n❌ ERROR: Cannot connect to server at http://localhost:8000")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
