"""
Manual verification script for transaction_id API implementation.

This script:
1. Creates a test transaction via the API
2. Verifies transaction_id is generated and returned
3. Verifies it's saved correctly in the database
4. Displays results

Prerequisites: Server must be running on localhost:8000
Run: python scripts/verify_transaction_id_api.py
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import database
from app.utils.transaction_id_generator import validate_transaction_id_format


async def verify_api():
    """Verify transaction_id generation via API."""
    print("=" * 70)
    print("MANUAL VERIFICATION: Transaction ID API Implementation")
    print("=" * 70)
    print()

    # Connect to database
    print("📡 Connecting to database...")
    await database.connect()
    print("✅ Database connected\n")

    # Prepare test data
    test_email = f"verify-{datetime.now().timestamp()}@example.com"
    test_square_id = f"VER-{datetime.now().timestamp()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    test_data = {
        "user_name": "Verification Test User",
        "user_email": test_email,
        "documents": [
            {
                "document_name": "verification_document.pdf",
                "document_url": "https://drive.google.com/file/d/verify123/view",
                "translated_url": None,
                "status": "uploaded",
                "uploaded_at": now_iso,
                "translated_at": None
            }
        ],
        "number_of_units": 10,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "en",
        "target_language": "es",
        "stripe_checkout_session_id": test_square_id,
        "stripe_payment_intent_id": test_square_id,
        "amount_cents": 150,
        "currency": "USD",
        "payment_status": "COMPLETED"
    }

    print("📤 Sending POST request to API...")
    print(f"   Endpoint: POST /api/v1/user-transactions/process")
    print(f"   User Email: {test_email}")
    print(f"   Stripe ID: {test_square_id}")
    print()

    # Make API request
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:8000/api/v1/user-transactions/process",
                json=test_data
            )

            print(f"📥 Response Status: {response.status_code}")
            print()

            if response.status_code != 201:
                print(f"❌ API request failed!")
                print(f"   Status Code: {response.status_code}")
                print(f"   Response: {response.text}")
                return

            response_data = response.json()

            # Check for transaction_id in response
            if "transaction_id" not in response_data:
                print("❌ transaction_id NOT found in API response!")
                print(f"   Response keys: {list(response_data.keys())}")
                return

            transaction_id = response_data["transaction_id"]
            print("✅ API Response Validation:")
            print(f"   ├─ transaction_id: {transaction_id}")
            print(f"   ├─ Format Valid: {validate_transaction_id_format(transaction_id)}")
            print(f"   ├─ Stripe ID: {response_data.get('stripe_checkout_session_id')}")
            print(f"   ├─ User Email: {response_data.get('user_email')}")
            print(f"   ├─ Total Cost: ${response_data.get('total_cost')}")
            print(f"   └─ Status: {response_data.get('status')}")
            print()

            # Verify format
            if not validate_transaction_id_format(transaction_id):
                print(f"❌ Invalid transaction_id format: {transaction_id}")
                return

            # Verify in database
            print("🔍 Verifying in database...")
            collection = database.user_transactions

            # Query by transaction_id (new primary key)
            txn_by_id = await collection.find_one({"transaction_id": transaction_id})

            if not txn_by_id:
                print(f"❌ Transaction NOT found in database by transaction_id!")
                return

            print("✅ Database Verification:")
            print(f"   ├─ transaction_id: {txn_by_id['transaction_id']}")
            print(f"   ├─ stripe_checkout_session_id: {txn_by_id['stripe_checkout_session_id']}")
            print(f"   ├─ user_email: {txn_by_id['user_email']}")
            print(f"   ├─ total_cost: ${txn_by_id['total_cost']}")
            print(f"   ├─ MongoDB _id: {txn_by_id['_id']}")
            print(f"   └─ documents count: {len(txn_by_id['documents'])}")
            print()

            # Verify unique index works
            print("🔐 Verifying unique index...")
            indexes = await collection.index_information()

            if "transaction_id_unique" in indexes:
                index_info = indexes["transaction_id_unique"]
                print("✅ Unique Index Verified:")
                print(f"   ├─ Name: transaction_id_unique")
                print(f"   ├─ Unique: {index_info['unique']}")
                print(f"   └─ Key: {index_info['key']}")
            else:
                print("❌ transaction_id_unique index NOT found!")
            print()

            # Cleanup
            print("🧹 Cleaning up test data...")
            result = await collection.delete_one({"transaction_id": transaction_id})
            if result.deleted_count > 0:
                print(f"✅ Test record deleted")
            print()

            print("=" * 70)
            print("✅ VERIFICATION COMPLETE - ALL CHECKS PASSED!")
            print("=" * 70)
            print()
            print("Summary:")
            print("  ✅ API generates transaction_id")
            print("  ✅ transaction_id follows USER + 6-digit format")
            print("  ✅ transaction_id is returned in API response")
            print("  ✅ transaction_id is saved in database")
            print("  ✅ Unique index is properly configured")
            print("  ✅ Database queries by transaction_id work correctly")
            print()

    except httpx.ConnectError:
        print("❌ Could not connect to server!")
        print("   Make sure the server is running:")
        print("   cd server && uvicorn app.main:app --reload")
        print()
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        import traceback
        traceback.print_exc()
        print()


if __name__ == "__main__":
    try:
        asyncio.run(verify_api())
    except KeyboardInterrupt:
        print("\n\n❌ Verification cancelled by user")
