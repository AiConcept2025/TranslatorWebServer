#!/usr/bin/env python3
"""
Migration Script: Fix square_transaction_id Index to be Sparse

PROBLEM:
- The square_transaction_id index on user_transactions is unique but NOT sparse
- This prevents multiple documents with null square_transaction_id
- Tests fail when trying to create multiple transactions before payment

SOLUTION:
- Drop the old index
- Recreate as unique + sparse
- Sparse allows multiple null values while enforcing uniqueness on non-null values

SAFETY:
- Read-only check before modifying
- Backup verification recommended before running
- Can run on both test and production databases

Usage:
    python scripts/fix_sparse_index_migration.py --database translation_test
    python scripts/fix_sparse_index_migration.py --database translation --confirm
"""

import argparse
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING


async def fix_sparse_index(database_name: str, dry_run: bool = True):
    """
    Fix square_transaction_id index to be sparse.

    Args:
        database_name: Name of the database (translation or translation_test)
        dry_run: If True, only show what would be done without making changes
    """
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client[database_name]
    collection = db.user_transactions

    print(f"\n{'='*80}")
    print(f"Database: {database_name}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will modify database)'}")
    print(f"{'='*80}\n")

    # Check current index configuration
    print("📊 Current Index Configuration:")
    indexes = await collection.list_indexes().to_list(length=100)

    current_index = None
    for idx in indexes:
        if idx['name'] == 'square_transaction_id_unique':
            current_index = idx
            print(f"  Index Name: {idx['name']}")
            print(f"  Keys: {idx['key']}")
            print(f"  Unique: {idx.get('unique', False)}")
            print(f"  Sparse: {idx.get('sparse', False)}")

            if not idx.get('sparse', False):
                print(f"  ⚠️  Issue: Index is NOT sparse (blocks multiple null values)")
            else:
                print(f"  ✅ Index is already sparse")

    if not current_index:
        print("  ❌ Index 'square_transaction_id_unique' not found!")
        client.close()
        return False

    # Check if fix is needed
    if current_index.get('sparse', False):
        print("\n✅ Index is already sparse. No migration needed.")
        client.close()
        return True

    # Count documents with null square_transaction_id
    null_count = await collection.count_documents({"square_transaction_id": None})
    print(f"\n📈 Statistics:")
    print(f"  Documents with square_transaction_id=null: {null_count}")

    if null_count > 1:
        print(f"  ⚠️  Multiple null values exist (would fail with current index)")

    # Show migration plan
    print(f"\n📋 Migration Plan:")
    print(f"  1. Drop index: square_transaction_id_unique")
    print(f"  2. Create new index with sparse=True")
    print(f"  3. Verify new index configuration")

    if dry_run:
        print(f"\n⚠️  DRY RUN MODE - No changes made")
        print(f"  To apply changes, run with --confirm flag")
        client.close()
        return True

    # Execute migration
    print(f"\n🔧 Executing Migration...")

    try:
        # Step 1: Drop old index
        print(f"  Step 1: Dropping old index...")
        await collection.drop_index("square_transaction_id_unique")
        print(f"  ✅ Old index dropped")

        # Step 2: Create new sparse unique index
        print(f"  Step 2: Creating new sparse unique index...")
        await collection.create_index(
            [("square_transaction_id", ASCENDING)],
            unique=True,
            sparse=True,
            name="square_transaction_id_unique"
        )
        print(f"  ✅ New sparse unique index created")

        # Step 3: Verify
        print(f"  Step 3: Verifying new index...")
        indexes = await collection.list_indexes().to_list(length=100)
        for idx in indexes:
            if idx['name'] == 'square_transaction_id_unique':
                print(f"\n  ✅ Verified Index Configuration:")
                print(f"     Name: {idx['name']}")
                print(f"     Keys: {idx['key']}")
                print(f"     Unique: {idx.get('unique', False)}")
                print(f"     Sparse: {idx.get('sparse', False)}")

                if idx.get('sparse', False) and idx.get('unique', False):
                    print(f"\n✅ Migration completed successfully!")
                    client.close()
                    return True
                else:
                    print(f"\n❌ Migration verification failed!")
                    client.close()
                    return False

        print(f"\n❌ Could not verify new index")
        client.close()
        return False

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        client.close()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Fix square_transaction_id index to be sparse"
    )
    parser.add_argument(
        '--database',
        choices=['translation', 'translation_test'],
        required=True,
        help='Database to migrate'
    )
    parser.add_argument(
        '--confirm',
        action='store_true',
        help='Confirm execution (without this flag, runs in dry-run mode)'
    )

    args = parser.parse_args()

    # Determine if this is a dry run
    dry_run = not args.confirm

    # Run migration
    success = asyncio.run(fix_sparse_index(args.database, dry_run))

    if success:
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    main()
