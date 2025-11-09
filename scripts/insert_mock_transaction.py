#!/usr/bin/env python3
"""
Insert Mock Translation Transaction
Creates a realistic test entry in the translation_transactions collection.

Usage:
    python3 scripts/insert_mock_transaction.py
"""
import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


async def insert_mock_transaction():
    """Insert a realistic mock translation transaction."""
    print("=" * 80)
    print("Inserting Mock Translation Transaction")
    print("=" * 80)

    # MongoDB connection (from .env)
    uri = 'mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation'
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client.translation

    try:
        # Test connection
        await client.admin.command('ping')
        print("\n✓ Connected to MongoDB")

        # Generate unique transaction ID
        transaction_id = f"TXN-MOCK-{uuid.uuid4().hex[:12].upper()}"

        # Create mock transaction document with NESTED structure
        # Based on schema from test_transaction_insert.py and actual usage
        mock_transaction = {
            # Core identifiers
            "transaction_id": transaction_id,
            "company_name": "test-company-123",
            "user_id": "test@example.com",
            "user_name": "Test User",
            "subscription_id": None,  # Individual transaction, not subscription

            # Translation details
            "source_language": "en",
            "target_language": "es",
            "status": "pending",  # pending, processing, completed, failed

            # Pricing and units
            "unit_type": "page",  # page, word, character
            "units_count": 12,  # 12 pages
            "price_per_unit": 0.10,  # $0.10 per page
            "total_price": 1.20,  # 12 pages * $0.10

            # Error handling
            "error_message": "",

            # Timestamps
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),

            # NESTED documents array - NEW STRUCTURE
            "documents": [
                {
                    "file_name": "business_proposal_2024.pdf",
                    "file_size": 2457600,  # ~2.4 MB
                    "original_url": "https://drive.google.com/file/d/1ABC_mock_original_file/view",
                    "translated_url": None,  # None until translation complete
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": datetime.now(timezone.utc),
                    "translated_at": None,
                    "processing_started_at": None,
                    "processing_duration": None
                }
            ]
        }

        print(f"\n✓ Generated transaction ID: {transaction_id}")
        print("\nMock Transaction Document:")
        print("-" * 80)
        for key, value in mock_transaction.items():
            if key == "metadata":
                print(f"  {key}:")
                for mk, mv in value.items():
                    print(f"    - {mk}: {mv}")
            else:
                value_str = str(value)[:60] if not isinstance(value, (datetime, type(None))) else str(value)
                print(f"  {key}: {value_str}")

        # Insert the document
        print("\n" + "-" * 80)
        print("Inserting document...")
        result = await db.translation_transactions.insert_one(mock_transaction)
        print(f"✓ Insert successful!")
        print(f"  Inserted ID: {result.inserted_id}")

        # Verify insertion
        print("\nVerifying insertion...")
        found_doc = await db.translation_transactions.find_one(
            {"transaction_id": transaction_id}
        )

        if found_doc:
            print("✓ Transaction verified in database")
            print(f"  Transaction ID: {found_doc['transaction_id']}")
            print(f"  Company Name: {found_doc.get('company_name', 'N/A')}")
            print(f"  User ID: {found_doc.get('user_id', 'N/A')}")
            print(f"  Documents: {len(found_doc.get('documents', []))} file(s)")
            if found_doc.get('documents'):
                doc = found_doc['documents'][0]
                print(f"  First Document: {doc.get('file_name', 'N/A')}")
                print(f"  Document Status: {doc.get('status', 'N/A')}")
            print(f"  Status: {found_doc['status']}")
            print(f"  Language: {found_doc['source_language']} → {found_doc['target_language']}")
            print(f"  Cost: ${found_doc['total_price']:.2f}")
            print(f"  Created: {found_doc['created_at']}")
        else:
            print("✗ Transaction NOT found in database")
            return False

        # Show collection stats
        total_count = await db.translation_transactions.count_documents({})
        print(f"\n✓ Total transactions in collection: {total_count}")

        print("\n" + "=" * 80)
        print("SUCCESS: Mock transaction inserted successfully!")
        print("=" * 80)

        # Show query examples
        print("\nQuery Examples:")
        print("-" * 80)
        print("1. Find by transaction_id:")
        print(f"   db.translation_transactions.find_one({{'transaction_id': '{transaction_id}'}})")
        print("\n2. Find by company_id:")
        print(f"   db.translation_transactions.find({{'company_id': 'test-company-123'}})")
        print("\n3. Find by status:")
        print(f"   db.translation_transactions.find({{'status': 'pending'}})")
        print("-" * 80)

        return True

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = asyncio.run(insert_mock_transaction())
    sys.exit(0 if success else 1)
