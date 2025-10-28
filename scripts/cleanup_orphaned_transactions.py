"""
Cleanup script to delete orphaned translation_transactions
where company_id does not exist in companies collection.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings


async def cleanup_orphaned_transactions():
    """Delete translation_transactions with invalid company_ids"""

    print("🔌 Connecting to MongoDB...")
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    print("📋 Fetching valid company IDs...")
    # Get all valid company IDs from companies collection
    valid_company_ids = await db.companies.distinct("_id")
    print(f"✅ Found {len(valid_company_ids)} valid companies: {valid_company_ids}")

    # Count orphaned records before deletion
    print("\n🔍 Checking for orphaned translation_transactions...")
    orphaned_count = await db.translation_transactions.count_documents({
        "company_id": {"$nin": valid_company_ids}
    })
    print(f"⚠️  Found {orphaned_count} orphaned translation_transactions")

    if orphaned_count == 0:
        print("✅ No orphaned records to delete!")
        client.close()
        return

    # Get some examples before deletion
    print("\n📄 Examples of orphaned records:")
    orphaned_examples = await db.translation_transactions.find(
        {"company_id": {"$nin": valid_company_ids}}
    ).limit(5).to_list(length=5)

    for example in orphaned_examples:
        print(f"  - Transaction ID: {example.get('transaction_id')}, Company ID: {example.get('company_id')}")

    # Delete orphaned translation_transactions
    print(f"\n🗑️  Deleting {orphaned_count} orphaned translation_transactions...")
    result = await db.translation_transactions.delete_many({
        "company_id": {"$nin": valid_company_ids}
    })

    print(f"✅ Successfully deleted {result.deleted_count} orphaned translation_transactions")

    # Verify deletion
    remaining_orphaned = await db.translation_transactions.count_documents({
        "company_id": {"$nin": valid_company_ids}
    })
    print(f"✅ Remaining orphaned records: {remaining_orphaned}")

    # Count total remaining records
    total_remaining = await db.translation_transactions.count_documents({})
    print(f"📊 Total translation_transactions remaining: {total_remaining}")

    client.close()
    print("\n✅ Cleanup complete!")


if __name__ == "__main__":
    asyncio.run(cleanup_orphaned_transactions())
