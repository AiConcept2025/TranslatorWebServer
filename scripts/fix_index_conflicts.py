#!/usr/bin/env python3
"""
MongoDB Index Conflict Resolution Script

Purpose: Drop old indexes that reference company_id after schema refactoring to company_name.

This script:
1. Connects to MongoDB
2. Lists all indexes in affected collections
3. Drops old indexes that reference company_id
4. Verifies the drops were successful
5. Allows server startup to recreate correct indexes

Collections affected:
- users: email_company_idx (old: company_id, new: company_name)
- payments: company_status_idx (old: company_id, new: company_name)
- users_login: potential duplicates

Usage:
    python scripts/fix_index_conflicts.py [--dry-run]
"""

import asyncio
import logging
import sys
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection settings
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"

# Index drop configuration
# Format: {collection_name: [list of index names to drop]}
INDEXES_TO_DROP = {
    "users": [
        # Drop old email_company_idx if it has company_id
        # The new one will be created by server startup
    ],
    "payments": [
        # Drop old company_status_idx if it has company_id
        # The new one will be created by server startup
    ],
    "users_login": [
        # Drop duplicate or conflicting indexes
    ]
}


async def list_indexes(collection, collection_name: str) -> List[Dict[str, Any]]:
    """
    List all indexes in a collection.

    Args:
        collection: Motor collection object
        collection_name: Name of the collection

    Returns:
        List of index specifications
    """
    try:
        indexes = []
        async for index in collection.list_indexes():
            indexes.append(index)

        logger.info(f"[{collection_name}] Found {len(indexes)} indexes")
        for idx in indexes:
            logger.info(f"  - {idx['name']}: {idx.get('key', {})}")

        return indexes
    except Exception as e:
        logger.error(f"[{collection_name}] Error listing indexes: {e}")
        return []


async def check_index_has_old_field(collection, index_name: str, old_field: str = "company_id") -> bool:
    """
    Check if an index contains the old field (company_id).

    Args:
        collection: Motor collection object
        index_name: Name of the index to check
        old_field: Old field name to check for (default: company_id)

    Returns:
        True if index contains old field, False otherwise
    """
    try:
        async for index in collection.list_indexes():
            if index['name'] == index_name:
                keys = index.get('key', {})
                if old_field in keys:
                    logger.info(f"  ✓ Index '{index_name}' contains old field '{old_field}'")
                    return True
                else:
                    logger.info(f"  ✗ Index '{index_name}' does NOT contain old field '{old_field}'")
                    return False

        logger.warning(f"  ? Index '{index_name}' not found")
        return False
    except Exception as e:
        logger.error(f"  Error checking index '{index_name}': {e}")
        return False


async def drop_index(collection, collection_name: str, index_name: str, dry_run: bool = False) -> bool:
    """
    Drop an index from a collection.

    Args:
        collection: Motor collection object
        collection_name: Name of the collection
        index_name: Name of the index to drop
        dry_run: If True, only simulate the drop

    Returns:
        True if successful, False otherwise
    """
    try:
        if dry_run:
            logger.info(f"[{collection_name}] DRY RUN: Would drop index '{index_name}'")
            return True

        # Don't drop _id_ index
        if index_name == "_id_":
            logger.warning(f"[{collection_name}] SKIPPED: Cannot drop _id_ index")
            return False

        await collection.drop_index(index_name)
        logger.info(f"[{collection_name}] ✓ Successfully dropped index '{index_name}'")
        return True
    except OperationFailure as e:
        if "index not found" in str(e).lower():
            logger.info(f"[{collection_name}] Index '{index_name}' does not exist (already dropped or never existed)")
            return True
        else:
            logger.error(f"[{collection_name}] ✗ Failed to drop index '{index_name}': {e}")
            return False
    except Exception as e:
        logger.error(f"[{collection_name}] ✗ Unexpected error dropping index '{index_name}': {e}")
        return False


async def fix_collection_indexes(db, collection_name: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Fix indexes for a specific collection.

    Args:
        db: Motor database object
        collection_name: Name of the collection to fix
        dry_run: If True, only simulate the fixes

    Returns:
        Dictionary with results
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing collection: {collection_name}")
    logger.info(f"{'='*80}")

    collection = db[collection_name]

    # Step 1: List all current indexes
    logger.info(f"\n[{collection_name}] Step 1: Listing current indexes...")
    indexes = await list_indexes(collection, collection_name)

    if not indexes:
        logger.warning(f"[{collection_name}] No indexes found or error occurred")
        return {"success": False, "dropped": [], "errors": []}

    # Step 2: Identify and drop problematic indexes
    logger.info(f"\n[{collection_name}] Step 2: Identifying indexes with old fields or naming conflicts...")

    dropped_indexes = []
    errors = []

    # Special handling for users_login: drop old idx_ prefixed indexes
    if collection_name == "users_login":
        old_login_indexes = ["idx_user_email_unique", "idx_user_name_unique", "idx_created_at"]
        for index_name in old_login_indexes:
            # Check if it exists
            exists = any(idx['name'] == index_name for idx in indexes)
            if exists:
                logger.info(f"[{collection_name}] Found old index with prefix: {index_name}")
                if await drop_index(collection, collection_name, index_name, dry_run):
                    dropped_indexes.append(index_name)
                else:
                    errors.append(index_name)

    for index in indexes:
        index_name = index['name']
        keys = index.get('key', {})

        # Skip _id_ index
        if index_name == "_id_":
            continue

        # Skip if already processed (users_login special case)
        if index_name in dropped_indexes:
            continue

        # Check if index contains company_id (old field)
        if "company_id" in keys:
            logger.info(f"[{collection_name}] Found index with old field: {index_name} -> {keys}")

            if await drop_index(collection, collection_name, index_name, dry_run):
                dropped_indexes.append(index_name)
            else:
                errors.append(index_name)

    # Step 3: List indexes after cleanup
    if not dry_run and dropped_indexes:
        logger.info(f"\n[{collection_name}] Step 3: Verifying indexes after cleanup...")
        remaining_indexes = await list_indexes(collection, collection_name)
        logger.info(f"[{collection_name}] Remaining indexes: {len(remaining_indexes)}")

    return {
        "success": len(errors) == 0,
        "dropped": dropped_indexes,
        "errors": errors
    }


async def main(dry_run: bool = False):
    """
    Main function to fix index conflicts.

    Args:
        dry_run: If True, only simulate the fixes without making changes
    """
    logger.info("="*80)
    logger.info("MongoDB Index Conflict Resolution")
    logger.info("="*80)
    logger.info(f"Mode: {'DRY RUN (simulation only)' if dry_run else 'LIVE (making actual changes)'}")
    logger.info(f"Database: {DATABASE_NAME}")
    logger.info("="*80)

    # Connect to MongoDB
    logger.info("\nConnecting to MongoDB...")
    try:
        client = AsyncIOMotorClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000
        )
        db = client[DATABASE_NAME]

        # Test connection
        await client.admin.command('ping')
        logger.info("✓ Successfully connected to MongoDB")
    except Exception as e:
        logger.error(f"✗ Failed to connect to MongoDB: {e}")
        return False

    # Collections to check
    collections_to_fix = ["users", "payments", "users_login", "company_users", "subscriptions", "translation_transactions"]

    results = {}
    total_dropped = 0
    total_errors = 0

    # Process each collection
    for collection_name in collections_to_fix:
        try:
            result = await fix_collection_indexes(db, collection_name, dry_run)
            results[collection_name] = result
            total_dropped += len(result["dropped"])
            total_errors += len(result["errors"])
        except Exception as e:
            logger.error(f"[{collection_name}] Unexpected error: {e}", exc_info=True)
            results[collection_name] = {"success": False, "dropped": [], "errors": ["unexpected_error"]}
            total_errors += 1

    # Summary
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)

    for collection_name, result in results.items():
        status = "✓ SUCCESS" if result["success"] else "✗ ERRORS"
        logger.info(f"[{collection_name}] {status}")

        if result["dropped"]:
            logger.info(f"  Dropped indexes: {', '.join(result['dropped'])}")

        if result["errors"]:
            logger.info(f"  Errors: {', '.join(result['errors'])}")

    logger.info(f"\nTotal indexes dropped: {total_dropped}")
    logger.info(f"Total errors: {total_errors}")

    if dry_run:
        logger.info("\n⚠️  This was a DRY RUN. No changes were made.")
        logger.info("Run without --dry-run to apply changes.")
    else:
        logger.info("\n✓ Index cleanup completed!")
        logger.info("Start the server to recreate correct indexes.")

    # Close connection
    client.close()
    logger.info("\nMongoDB connection closed")

    return total_errors == 0


if __name__ == "__main__":
    # Check for --dry-run flag
    dry_run = "--dry-run" in sys.argv

    # Run async main
    success = asyncio.run(main(dry_run))

    # Exit with appropriate code
    sys.exit(0 if success else 1)
