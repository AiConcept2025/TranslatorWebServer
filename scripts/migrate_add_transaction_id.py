"""
Migration script to add transaction_id to existing user_transactions records.

This script:
1. Finds all records without transaction_id field
2. Generates unique USER + 6-digit transaction IDs for them
3. Updates the records
4. Allows the unique index to be created

Run: python scripts/migrate_add_transaction_id.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import database
from app.utils.transaction_id_generator import generate_unique_transaction_id


async def migrate_transaction_ids():
    """Add transaction_id to existing records that don't have it."""
    print("=== Transaction ID Migration ===\n")

    # Connect to database
    print("Connecting to database...")
    await database.connect()

    collection = database.user_transactions

    # Count records without transaction_id
    count_without = await collection.count_documents({
        "transaction_id": {"$exists": False}
    })

    print(f"Found {count_without} records without transaction_id\n")

    if count_without == 0:
        print("✅ No migration needed - all records have transaction_id")
        return

    # Get all records without transaction_id
    cursor = collection.find({"transaction_id": {"$exists": False}})
    records = await cursor.to_list(length=None)

    print(f"Migrating {len(records)} records...\n")

    updated = 0
    failed = 0

    for record in records:
        try:
            # Generate unique transaction_id
            transaction_id = await generate_unique_transaction_id(collection)

            # Update the record
            result = await collection.update_one(
                {"_id": record["_id"]},
                {"$set": {"transaction_id": transaction_id}}
            )

            if result.modified_count > 0:
                updated += 1
                square_id = record.get("stripe_checkout_session_id", "N/A")
                print(f"✅ {updated}/{len(records)}: {transaction_id} (Square: {square_id})")
            else:
                failed += 1
                print(f"❌ Failed to update record {record['_id']}")

        except Exception as e:
            failed += 1
            print(f"❌ Error updating record {record['_id']}: {e}")

    print(f"\n=== Migration Complete ===")
    print(f"✅ Successfully updated: {updated}")
    print(f"❌ Failed: {failed}")
    print(f"Total: {len(records)}")

    # Verify all records now have transaction_id
    remaining = await collection.count_documents({
        "transaction_id": {"$exists": False}
    })

    if remaining == 0:
        print(f"\n✅ All records now have transaction_id field")
    else:
        print(f"\n⚠️  Warning: {remaining} records still missing transaction_id")


if __name__ == "__main__":
    asyncio.run(migrate_transaction_ids())
