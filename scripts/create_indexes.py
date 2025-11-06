#!/usr/bin/env python3
"""
Database indexes creation script.

Creates necessary indexes for optimal query performance in MongoDB collections:
- translation_transactions (enterprise)
- user_transactions (individual)
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database.mongodb import database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_transaction_indexes():
    """
    Create indexes for translation_transactions collection (Enterprise).

    Indexes:
    1. transaction_id (unique) - Primary lookup key
    2. company_name + status - For filtering by company and status
    3. documents.document_name - For document lookups within transaction
    4. user_id + status - For user-specific queries
    """
    try:
        collection = database.translation_transactions

        if collection is None:
            logger.error("translation_transactions collection not available")
            return False

        logger.info("Creating indexes for translation_transactions collection...")

        # 1. Unique index on transaction_id
        await collection.create_index("transaction_id", unique=True, name="idx_transaction_id")
        logger.info("✓ Created unique index on transaction_id")

        # 2. Compound index on company_name + status for filtering
        await collection.create_index(
            [("company_name", 1), ("status", 1)],
            name="idx_company_status"
        )
        logger.info("✓ Created compound index on company_name + status")

        # 3. Index on documents.document_name for document lookups
        await collection.create_index("documents.document_name", name="idx_documents_name")
        logger.info("✓ Created index on documents.document_name")

        # 4. Compound index on user_id + status
        await collection.create_index(
            [("user_id", 1), ("status", 1)],
            name="idx_user_status"
        )
        logger.info("✓ Created compound index on user_id + status")

        # 5. Index on created_at for sorting
        await collection.create_index("created_at", name="idx_created_at")
        logger.info("✓ Created index on created_at")

        # List all indexes
        indexes = await collection.list_indexes().to_list(length=None)
        logger.info(f"\nTotal indexes for translation_transactions: {len(indexes)}")
        for idx in indexes:
            logger.info(f"  - {idx['name']}: {idx['key']}")

        return True

    except Exception as e:
        logger.error(f"Error creating indexes for translation_transactions: {e}", exc_info=True)
        return False


async def create_user_transaction_indexes():
    """
    Create indexes for user_transactions collection (Individual).

    Indexes:
    1. transaction_id (unique) - Primary lookup key
    2. user_id + status - For user-specific queries
    3. documents.document_name - For document lookups within transaction
    4. status - For filtering by status
    """
    try:
        collection = database.user_transactions

        if collection is None:
            logger.error("user_transactions collection not available")
            return False

        logger.info("\nCreating indexes for user_transactions collection...")

        # 1. Unique index on transaction_id
        await collection.create_index("transaction_id", unique=True, name="idx_transaction_id")
        logger.info("✓ Created unique index on transaction_id")

        # 2. Compound index on user_id + status
        await collection.create_index(
            [("user_id", 1), ("status", 1)],
            name="idx_user_status"
        )
        logger.info("✓ Created compound index on user_id + status")

        # 3. Index on documents.document_name for document lookups
        await collection.create_index("documents.document_name", name="idx_documents_name")
        logger.info("✓ Created index on documents.document_name")

        # 4. Index on status for filtering
        await collection.create_index("status", name="idx_status")
        logger.info("✓ Created index on status")

        # 5. Index on created_at for sorting
        await collection.create_index("created_at", name="idx_created_at")
        logger.info("✓ Created index on created_at")

        # List all indexes
        indexes = await collection.list_indexes().to_list(length=None)
        logger.info(f"\nTotal indexes for user_transactions: {len(indexes)}")
        for idx in indexes:
            logger.info(f"  - {idx['name']}: {idx['key']}")

        return True

    except Exception as e:
        logger.error(f"Error creating indexes for user_transactions: {e}", exc_info=True)
        return False


async def main():
    """Main function to create all indexes."""
    logger.info("Starting database index creation...\n")

    try:
        # Connect to database
        await database.connect()
        logger.info("✓ Connected to MongoDB\n")

        # Create indexes for both collections
        success_translation = await create_transaction_indexes()
        success_user = await create_user_transaction_indexes()

        if success_translation and success_user:
            logger.info("\n✅ All indexes created successfully!")
            return 0
        else:
            logger.error("\n❌ Failed to create some indexes")
            return 1

    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        return 1

    finally:
        # Disconnect from database
        await database.disconnect()
        logger.info("\n✓ Disconnected from MongoDB")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
