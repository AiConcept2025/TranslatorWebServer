#!/usr/bin/env python3
"""
Cleanup orphaned records from MongoDB collections.

This script removes records from translation_transactions and subscriptions
where company_id does not exist in the companies collection.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from app.config import settings


async def get_valid_company_ids(client: AsyncIOMotorClient) -> list:
    """
    Get all valid company IDs from the companies collection.

    Args:
        client: MongoDB client

    Returns:
        List of valid company IDs
    """
    db = client[settings.mongodb_database]

    # The actual collection name is 'company' (singular), not 'companies'
    collection = db.company

    # Get all unique _id values (these are the company_ids)
    valid_ids = await collection.distinct("_id")

    print(f"[INFO] Found {len(valid_ids)} valid company IDs in 'company' collection")
    return valid_ids


async def cleanup_translation_transactions(
    client: AsyncIOMotorClient,
    valid_company_ids: list
) -> Dict[str, Any]:
    """
    Delete orphaned translation_transactions records.

    Args:
        client: MongoDB client
        valid_company_ids: List of valid company IDs

    Returns:
        Dictionary with deletion results
    """
    db = client[settings.mongodb_database]
    collection = db.translation_transactions

    # Count orphaned records before deletion
    orphaned_count = await collection.count_documents({
        "company_id": {"$nin": valid_company_ids}
    })

    if orphaned_count == 0:
        print("[INFO] No orphaned translation_transactions found")
        return {"collection": "translation_transactions", "deleted": 0, "orphaned_before": 0}

    print(f"[WARNING] Found {orphaned_count} orphaned translation_transactions")

    # Delete orphaned records
    result = await collection.delete_many({
        "company_id": {"$nin": valid_company_ids}
    })

    return {
        "collection": "translation_transactions",
        "deleted": result.deleted_count,
        "orphaned_before": orphaned_count
    }


async def cleanup_subscriptions(
    client: AsyncIOMotorClient,
    valid_company_ids: list
) -> Dict[str, Any]:
    """
    Delete orphaned subscriptions records.

    Args:
        client: MongoDB client
        valid_company_ids: List of valid company IDs

    Returns:
        Dictionary with deletion results
    """
    db = client[settings.mongodb_database]
    collection = db.subscriptions

    # Count orphaned records before deletion
    orphaned_count = await collection.count_documents({
        "company_id": {"$nin": valid_company_ids}
    })

    if orphaned_count == 0:
        print("[INFO] No orphaned subscriptions found")
        return {"collection": "subscriptions", "deleted": 0, "orphaned_before": 0}

    print(f"[WARNING] Found {orphaned_count} orphaned subscriptions")

    # Delete orphaned records
    result = await collection.delete_many({
        "company_id": {"$nin": valid_company_ids}
    })

    return {
        "collection": "subscriptions",
        "deleted": result.deleted_count,
        "orphaned_before": orphaned_count
    }


async def verify_cleanup(client: AsyncIOMotorClient, valid_company_ids: list) -> Dict[str, int]:
    """
    Verify that cleanup was successful by counting remaining orphaned records.

    Args:
        client: MongoDB client
        valid_company_ids: List of valid company IDs

    Returns:
        Dictionary with remaining orphaned record counts
    """
    db = client[settings.mongodb_database]

    translation_orphans = await db.translation_transactions.count_documents({
        "company_id": {"$nin": valid_company_ids}
    })

    subscription_orphans = await db.subscriptions.count_documents({
        "company_id": {"$nin": valid_company_ids}
    })

    return {
        "translation_transactions": translation_orphans,
        "subscriptions": subscription_orphans
    }


async def main():
    """Main cleanup function."""
    print("=" * 80)
    print("MongoDB Orphaned Data Cleanup")
    print("=" * 80)
    print(f"Database: {settings.mongodb_database}")
    print(f"URI: {settings.mongodb_uri.split('@')[1] if '@' in settings.mongodb_uri else settings.mongodb_uri}")
    print("=" * 80)

    client = None

    try:
        # Connect to MongoDB
        print("\n[INFO] Connecting to MongoDB...")
        client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000
        )

        # Test connection
        await client.admin.command('ping')
        print("[SUCCESS] Connected to MongoDB")

        # Get valid company IDs
        print("\n[STEP 1] Fetching valid company IDs...")
        valid_company_ids = await get_valid_company_ids(client)

        if not valid_company_ids:
            print("[WARNING] No companies found in database! Aborting cleanup to prevent data loss.")
            return

        # Cleanup translation_transactions
        print("\n[STEP 2] Cleaning up translation_transactions...")
        trans_result = await cleanup_translation_transactions(client, valid_company_ids)

        # Cleanup subscriptions
        print("\n[STEP 3] Cleaning up subscriptions...")
        subs_result = await cleanup_subscriptions(client, valid_company_ids)

        # Verify cleanup
        print("\n[STEP 4] Verifying cleanup...")
        remaining = await verify_cleanup(client, valid_company_ids)

        # Print summary
        print("\n" + "=" * 80)
        print("CLEANUP SUMMARY")
        print("=" * 80)
        print(f"\nTranslation Transactions:")
        print(f"  - Orphaned records found: {trans_result['orphaned_before']}")
        print(f"  - Records deleted: {trans_result['deleted']}")
        print(f"  - Remaining orphaned: {remaining['translation_transactions']}")

        print(f"\nSubscriptions:")
        print(f"  - Orphaned records found: {subs_result['orphaned_before']}")
        print(f"  - Records deleted: {subs_result['deleted']}")
        print(f"  - Remaining orphaned: {remaining['subscriptions']}")

        print(f"\nTotal records deleted: {trans_result['deleted'] + subs_result['deleted']}")

        if remaining['translation_transactions'] > 0 or remaining['subscriptions'] > 0:
            print("\n[WARNING] Some orphaned records remain! Manual investigation needed.")
        else:
            print("\n[SUCCESS] All orphaned records successfully removed!")

        print("=" * 80)

    except ConnectionFailure as e:
        print(f"\n[ERROR] Failed to connect to MongoDB: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] Unexpected error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        if client:
            client.close()
            print("\n[INFO] MongoDB connection closed")


if __name__ == "__main__":
    asyncio.run(main())
