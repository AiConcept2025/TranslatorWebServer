#!/usr/bin/env python3
"""
Script to remove all records created today from all collections in the translation database.

USAGE:
    python scripts/cleanup_today_records.py [--dry-run] [--confirm]

OPTIONS:
    --dry-run    Show what would be deleted without actually deleting (default)
    --confirm    Actually delete the records (requires explicit confirmation)

WARNING: This script deletes data from the PRODUCTION database (translation).
         Use with extreme caution!
"""

import asyncio
import argparse
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

# Database configuration - PRODUCTION database
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"

# Common date field names to check
DATE_FIELDS = [
    "created_at",
    "createdAt",
    "created",
    "date",
    "timestamp",
    "uploaded_at",
    "payment_date",
    "updated_at",
    "updatedAt",
]


def get_today_start_end():
    """Get the start and end of today in UTC."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    return today_start, today_end


def build_today_query(today_start, today_end):
    """Build a MongoDB query to find records created today."""
    # Build OR query for all possible date fields
    or_conditions = []
    for field in DATE_FIELDS:
        or_conditions.append({
            field: {
                "$gte": today_start,
                "$lt": today_end
            }
        })

    return {"$or": or_conditions}


async def get_all_collections(db):
    """Get all collection names in the database."""
    collections = await db.list_collection_names()
    # Filter out system collections
    return [c for c in collections if not c.startswith("system.")]


async def count_today_records(collection, query):
    """Count records matching the query in a collection."""
    try:
        count = await collection.count_documents(query)
        return count
    except Exception as e:
        print(f"  Error counting: {e}")
        return 0


async def delete_today_records(collection, query):
    """Delete records matching the query from a collection."""
    try:
        result = await collection.delete_many(query)
        return result.deleted_count
    except Exception as e:
        print(f"  Error deleting: {e}")
        return 0


async def preview_records(collection, query, limit=3):
    """Preview a few records that would be deleted."""
    try:
        cursor = collection.find(query).limit(limit)
        records = await cursor.to_list(length=limit)
        return records
    except Exception as e:
        print(f"  Error previewing: {e}")
        return []


async def main(dry_run=True, confirm=False):
    """Main function to cleanup today's records."""

    print("=" * 80)
    print("CLEANUP TODAY'S RECORDS FROM TRANSLATION DATABASE")
    print("=" * 80)
    print()

    # Get today's date range
    today_start, today_end = get_today_start_end()
    print(f"Date range: {today_start.isoformat()} to {today_end.isoformat()}")
    print(f"Database: {DATABASE_NAME}")
    print(f"Mode: {'DRY RUN (no deletions)' if dry_run else 'LIVE DELETE'}")
    print()

    if not dry_run and not confirm:
        print("ERROR: To delete records, you must use both --confirm flag")
        print("       and type 'DELETE' when prompted.")
        return

    # Connect to database
    client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[DATABASE_NAME]

    # Verify connection
    try:
        await client.admin.command('ping')
        print("Connected to MongoDB successfully.")
    except Exception as e:
        print(f"ERROR: Cannot connect to MongoDB: {e}")
        return

    print()
    print("-" * 80)

    # Build query for today's records
    query = build_today_query(today_start, today_end)

    # Get all collections
    collections = await get_all_collections(db)
    print(f"Found {len(collections)} collections to scan.")
    print()

    # Summary statistics
    total_to_delete = 0
    collections_with_records = []

    # Scan each collection
    for collection_name in sorted(collections):
        collection = db[collection_name]
        count = await count_today_records(collection, query)

        if count > 0:
            total_to_delete += count
            collections_with_records.append((collection_name, count))
            print(f"  {collection_name}: {count} records from today")

            # Preview a few records
            if dry_run:
                preview = await preview_records(collection, query, limit=2)
                for i, record in enumerate(preview):
                    # Show key identifying fields
                    record_id = record.get("_id", "N/A")
                    txn_id = record.get("transaction_id", record.get("invoice_number", record.get("company_name", "")))
                    created = None
                    for field in DATE_FIELDS:
                        if field in record:
                            created = record[field]
                            break
                    print(f"      Sample {i+1}: _id={record_id}, id={txn_id}, date={created}")

    print()
    print("-" * 80)
    print(f"SUMMARY: {total_to_delete} total records from today across {len(collections_with_records)} collections")
    print()

    if total_to_delete == 0:
        print("No records from today found. Nothing to delete.")
        client.close()
        return

    # If dry run, stop here
    if dry_run:
        print("DRY RUN COMPLETE. No records were deleted.")
        print()
        print("To actually delete these records, run with --confirm flag:")
        print("  python scripts/cleanup_today_records.py --confirm")
        client.close()
        return

    # Confirm deletion
    print("WARNING: You are about to DELETE the above records PERMANENTLY!")
    print()
    confirmation = input("Type 'DELETE' to confirm deletion: ")

    if confirmation != "DELETE":
        print("Aborted. No records were deleted.")
        client.close()
        return

    print()
    print("Deleting records...")
    print()

    # Delete from each collection
    total_deleted = 0
    for collection_name, expected_count in collections_with_records:
        collection = db[collection_name]
        deleted_count = await delete_today_records(collection, query)
        total_deleted += deleted_count
        print(f"  {collection_name}: Deleted {deleted_count} records")

    print()
    print("-" * 80)
    print(f"DELETION COMPLETE: {total_deleted} records deleted from {len(collections_with_records)} collections")
    print()

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Remove all records created today from the translation database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be deleted without actually deleting (default behavior)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete the records (will prompt for confirmation)"
    )

    args = parser.parse_args()

    # If --confirm is passed, disable dry-run
    dry_run = not args.confirm

    asyncio.run(main(dry_run=dry_run, confirm=args.confirm))
