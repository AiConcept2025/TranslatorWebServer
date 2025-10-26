"""
Test script to demonstrate the transaction confirm timeout issue.

ISSUE: /api/transactions/confirm blocks for 60+ seconds while moving files,
causing 30-second timeout middleware to fire.

Expected: Endpoint should return immediately (< 1s) and move files in background.
Actual: Endpoint blocks for 60+ seconds, times out at 30s.
"""
import httpx
import asyncio
import time
import json

API_BASE = "http://localhost:8000"

# Valid JWT token for authentication (expires in the far future)
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZGFuaXNoZXZza3lAZ21haWwuY29tIiwiZW1haWwiOiJkYW5pc2hldnNreUBnbWFpbC5jb20iLCJmaXJzdF9uYW1lIjoiVmxhZGltaXIiLCJsYXN0X25hbWUiOiJEYW5pc2hldnNreSIsImNvbXBhbnlfaWQiOiI2NzgyYzVmZjhhYTk0OGZlZjZlNzQ0ZmEiLCJwZXJtaXNzaW9uX2xldmVsIjoidXNlciIsImV4cCI6MjA0OTE3MjQzOCwiaWF0IjoxNzM0MzcyNDM4fQ.hJ8FdMfsFQ0Zz5jW83WCHq2tUcAg9ozvGDleCa3NVYn5EAE"

async def test_confirm_timeout():
    """
    Test current behavior: Endpoint times out at 30s while files are still moving.
    """
    print("="*80)
    print("TEST: Transaction Confirm - Current Behavior (BLOCKING)")
    print("="*80)

    # Payload with 3 real transaction IDs
    payload = {
        "transaction_ids": [
            "TXN-6C21AD7D97",
            "TXN-A0CD070C4D",
            "TXN-60B9A347F8"
        ]
    }

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }

    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:  # Slightly longer than server timeout
            print(f"\n⏱️  [{0:.2f}s] Sending POST /api/transactions/confirm...")
            print(f"📋 Transaction IDs: {payload['transaction_ids']}")

            response = await client.post(
                f"{API_BASE}/api/transactions/confirm",
                json=payload,
                headers=headers
            )

            elapsed = time.time() - start_time

            print(f"\n⏱️  [{elapsed:.2f}s] Response received")
            print(f"📊 Status Code: {response.status_code}")
            print(f"📊 Response Time: {elapsed:.2f}s")

            if response.status_code == 408:
                print("\n❌ ISSUE CONFIRMED: Request timed out at 30s")
                print("   The endpoint is blocking while moving files")
                print("   This should return immediately with background processing")
            elif response.status_code == 200:
                print("\n✅ Response successful")
                data = response.json()
                print(f"📋 Moved files: {data['data'].get('moved_files', 0)}")
                print(f"📋 Verified in Inbox: {data['data'].get('verified_in_inbox', 0)}")
            else:
                print(f"\n⚠️  Unexpected status: {response.status_code}")
                print(f"Response: {response.text[:200]}")

    except httpx.TimeoutException:
        elapsed = time.time() - start_time
        print(f"\n❌ CLIENT TIMEOUT: Request timed out after {elapsed:.2f}s")
        print("   This confirms the endpoint is taking too long")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ERROR after {elapsed:.2f}s: {e}")

    print("\n" + "="*80)
    print("ANALYSIS:")
    print("="*80)
    print("Current implementation (main.py:733):")
    print("  move_result = await google_drive_service.move_files_to_inbox_on_payment_success(...)")
    print("  ^--- This BLOCKS the HTTP response")
    print()
    print("Expected behavior:")
    print("  1. Return HTTP 200 immediately (< 1s)")
    print("  2. Move files in background task")
    print("  3. Frontend polls for status or receives webhook")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_confirm_timeout())
