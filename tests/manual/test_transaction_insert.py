#!/usr/bin/env python3
"""
Test script to verify MongoDB transaction insertion.
"""
import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid

async def test_transaction_insert():
    """Test inserting a transaction record."""
    print("=" * 80)
    print("Testing MongoDB Transaction Insert")
    print("=" * 80)

    # Connect to MongoDB
    uri = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
    print(f"\n1. Connecting to MongoDB...")
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client.translation

    try:
        # Test connection
        await client.admin.command('ping')
        print("   ✓ Connection successful")

        # Check if collection exists
        collections = await db.list_collection_names()
        print(f"\n2. Available collections: {collections}")

        if "translation_transactions" in collections:
            print("   ✓ translation_transactions collection exists")
        else:
            print("   ⚠ translation_transactions collection does NOT exist")

        # Count existing transactions
        count_before = await db.translation_transactions.count_documents({})
        print(f"\n3. Existing transactions: {count_before}")

        # Create test transaction
        transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:10].upper()}"
        transaction_doc = {
            "transaction_id": transaction_id,
            "user_id": "test_user",
            "original_file_url": "https://drive.google.com/test",
            "translated_file_url": "",
            "source_language": "en",
            "target_language": "es",
            "file_name": "test_file.docx",
            "file_size": 1024,
            "units_count": 5,
            "price_per_unit": 0.10,
            "total_price": 0.50,
            "status": "started",
            "error_message": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "company_id": None,
            "subscription_id": None,
            "unit_type": "page"
        }

        print(f"\n4. Inserting test transaction: {transaction_id}")
        print(f"   Document: {transaction_doc}")

        # Insert the transaction
        result = await db.translation_transactions.insert_one(transaction_doc)
        print(f"   ✓ Insert successful, inserted_id: {result.inserted_id}")

        # Verify insertion
        count_after = await db.translation_transactions.count_documents({})
        print(f"\n5. Transactions after insert: {count_after}")

        # Find the inserted document
        found_doc = await db.translation_transactions.find_one({"transaction_id": transaction_id})
        if found_doc:
            print(f"   ✓ Transaction found in database")
            print(f"   Transaction ID: {found_doc['transaction_id']}")
            print(f"   File: {found_doc['file_name']}")
            print(f"   Status: {found_doc['status']}")
        else:
            print(f"   ✗ Transaction NOT found in database")

        print("\n" + "=" * 80)
        print("SUCCESS: MongoDB transaction insert works correctly")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_transaction_insert())
