#!/usr/bin/env python3
"""
Quick test script to verify /submit endpoint validation logging.
This simulates what GoogleTranslator service would send.
"""

import requests
import json

# Test Case 1: Valid request (should work)
print("=" * 80)
print("TEST 1: Valid /submit request")
print("=" * 80)

valid_payload = {
    "file_name": "test_document.docx",
    "file_url": "https://docs.google.com/document/d/abc123/edit",
    "user_email": "test@example.com",
    "company_name": "Test Company",
    "transaction_id": "TXN-TEST-123456"
}

print(f"Payload: {json.dumps(valid_payload, indent=2)}")

try:
    response = requests.post(
        "http://localhost:8000/submit",
        json=valid_payload,
        timeout=10
    )
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.text[:500]}")
except Exception as e:
    print(f"Request failed: {e}")

print("\n" + "=" * 80)
print("TEST 2: Invalid request - MISSING transaction_id (reproduces the bug)")
print("=" * 80)

# Test Case 2: Missing transaction_id (reproduces the validation error)
invalid_payload = {
    "file_name": "test_document.docx",
    "file_url": "https://docs.google.com/document/d/abc123/edit",
    "user_email": "test@example.com",
    "company_name": "Test Company"
    # transaction_id intentionally missing
}

print(f"Payload: {json.dumps(invalid_payload, indent=2)}")

try:
    response = requests.post(
        "http://localhost:8000/submit",
        json=invalid_payload,
        timeout=10
    )
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.text[:500]}")
except Exception as e:
    print(f"Request failed: {e}")

print("\n" + "=" * 80)
print("TEST 3: Invalid request - transaction_id is null (reproduces the exact bug)")
print("=" * 80)

# Test Case 3: transaction_id is null (exact bug reproduction)
null_payload = {
    "file_name": "test_document.docx",
    "file_url": "https://docs.google.com/document/d/abc123/edit",
    "user_email": "test@example.com",
    "company_name": "Test Company",
    "transaction_id": None  # Explicitly null
}

print(f"Payload: {json.dumps(null_payload, indent=2)}")

try:
    response = requests.post(
        "http://localhost:8000/submit",
        json=null_payload,
        timeout=10
    )
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.text[:500]}")
except Exception as e:
    print(f"Request failed: {e}")

print("\n" + "=" * 80)
print("INSTRUCTIONS:")
print("1. Start the server: uvicorn app.main:app --reload")
print("2. Run this script: python3 test_submit_logging.py")
print("3. Check server logs for enhanced debugging output")
print("=" * 80)
