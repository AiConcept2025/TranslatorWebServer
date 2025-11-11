"""
Fix transaction_id index by dropping and recreating it.

Run: python scripts/fix_transaction_id_index.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
from app.config import settings


async def fix_index():
    """Drop and recreate transaction_id unique index."""
    print("=== Fix transaction_id Index ===\n")

    # Connect directly without auto-creating indexes
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]
    collection = db.user_transactions

    print("Dropping existing transaction_id_unique index (if exists)...")
    try:
        await collection.drop_index("transaction_id_unique")
        print("✅ Dropped transaction_id_unique index\n")
    except Exception as e:
        print(f"ℹ️  Index doesn't exist or couldn't be dropped: {e}\n")

    # Verify all records have transaction_id
    count_without = await collection.count_documents({
        "transaction_id": {"$exists": False}
    })

    if count_without > 0:
        print(f"⚠️  Warning: {count_without} records still missing transaction_id!")
        print("Run migrate_add_transaction_id.py first\n")
        return

    print("✅ All records have transaction_id field\n")

    # Create the unique index
    print("Creating transaction_id_unique index...")
    try:
        await collection.create_index(
            [("transaction_id", ASCENDING)],
            unique=True,
            name="transaction_id_unique"
        )
        print("✅ Created transaction_id_unique index\n")
    except Exception as e:
        print(f"❌ Failed to create index: {e}\n")
        return

    # Verify index exists
    indexes = await collection.index_information()
    if "transaction_id_unique" in indexes:
        print("✅ Index verified:")
        print(f"   Name: transaction_id_unique")
        print(f"   Unique: {indexes['transaction_id_unique']['unique']}")
        print(f"   Key: {indexes['transaction_id_unique']['key']}")
    else:
        print("❌ Index not found after creation")

    print("\n=== Complete ===")


if __name__ == "__main__":
    asyncio.run(fix_index())
