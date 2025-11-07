#!/usr/bin/env python3
"""
Cleanup Script: Delete Old Flat Translation Transaction Records

PURPOSE:
    Safely delete old flat transaction records after migration verification.
    This script should be run 24-48 hours AFTER running migrate_translation_transactions.py
    to ensure the migration was successful.

WHAT IT DOES:
    1. Reads old record IDs from migration output file
    2. Verifies records are flat (no documents array)
    3. Counts records to be deleted
    4. DRY RUN by default (shows what would be deleted)
    5. Requires explicit --confirm flag for actual deletion
    6. Manual confirmation prompt ("type DELETE to confirm")
    7. Deletes old records
    8. Verifies no flat records remain

SAFETY FEATURES:
    - Dry run mode by default
    - Requires --confirm flag
    - Manual confirmation prompt
    - Verifies records are flat before deletion
    - Only deletes records by ID from file (no bulk deletes)
    - Comprehensive logging

Usage:
    # Dry run (default) - shows what would be deleted
    python3 cleanup_old_transaction_records.py /tmp/translation_transactions_old_ids_20241106_120000.txt

    # Actual deletion (requires confirmation)
    python3 cleanup_old_transaction_records.py /tmp/translation_transactions_old_ids_20241106_120000.txt --confirm

    # With custom MongoDB URI
    MONGODB_URI="mongodb://localhost:27017/translation" python3 cleanup_old_transaction_records.py <ids_file> --confirm
"""
import asyncio
import sys
import os
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class OldRecordCleaner:
    """Handles safe deletion of old flat transaction records after migration."""

    def __init__(self, mongodb_uri: str, database_name: str, ids_file: str, confirm: bool):
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self.ids_file = ids_file
        self.confirm = confirm
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.old_ids: List[ObjectId] = []

    async def connect(self) -> bool:
        """Establish MongoDB connection."""
        try:
            logger.info(f"Connecting to MongoDB database: {self.database_name}")
            self.client = AsyncIOMotorClient(
                self.mongodb_uri,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.client[self.database_name]

            # Test connection
            await self.client.admin.command('ping')
            logger.info("✓ Successfully connected to MongoDB")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to connect to MongoDB: {e}")
            return False

    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("✓ Database connection closed")

    def load_old_ids(self) -> bool:
        """Load old record IDs from file."""
        try:
            if not os.path.exists(self.ids_file):
                logger.error(f"✗ IDs file not found: {self.ids_file}")
                return False

            logger.info(f"Reading old record IDs from: {self.ids_file}")

            with open(self.ids_file, 'r') as f:
                lines = f.readlines()

            # Parse IDs (skip comments)
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                try:
                    self.old_ids.append(ObjectId(line))
                except Exception as e:
                    logger.warning(f"⚠ Invalid ObjectId: {line}")

            logger.info(f"✓ Loaded {len(self.old_ids)} record IDs")
            return len(self.old_ids) > 0

        except Exception as e:
            logger.error(f"✗ Failed to load IDs file: {e}")
            return False

    async def verify_flat_records(self) -> tuple[int, int]:
        """
        Verify that records are flat (no documents field).

        Returns:
            Tuple of (flat_count, nested_count)
        """
        try:
            logger.info("Verifying records are flat (no documents field)...")

            flat_count = 0
            nested_count = 0

            # Check first 5 records as samples
            sample_size = min(5, len(self.old_ids))
            samples = self.old_ids[:sample_size]

            for record_id in samples:
                record = await self.db.translation_transactions.find_one({"_id": record_id})

                if not record:
                    logger.warning(f"⚠ Record not found: {record_id}")
                    continue

                if "documents" in record:
                    nested_count += 1
                    logger.warning(f"⚠ Record {record_id} has documents array (nested structure)")
                else:
                    flat_count += 1

            # Count all matching flat records
            total_flat = await self.db.translation_transactions.count_documents({
                "_id": {"$in": self.old_ids},
                "documents": {"$exists": False}
            })

            total_nested = await self.db.translation_transactions.count_documents({
                "_id": {"$in": self.old_ids},
                "documents": {"$exists": True}
            })

            logger.info(f"✓ Verification complete:")
            logger.info(f"  Flat records:   {total_flat}")
            logger.info(f"  Nested records: {total_nested}")

            if total_nested > 0:
                logger.error(f"✗ ERROR: {total_nested} records have nested structure!")
                logger.error("  These records may have already been migrated or are invalid.")
                logger.error("  Aborting to prevent data loss.")
                return total_flat, total_nested

            return total_flat, total_nested

        except Exception as e:
            logger.error(f"✗ Verification failed: {e}")
            return 0, 0

    async def show_sample_records(self, limit: int = 3):
        """Show sample records that would be deleted."""
        try:
            logger.info(f"\nSample records to be deleted (showing {limit}):")
            logger.info("-" * 80)

            samples = self.old_ids[:limit]

            for i, record_id in enumerate(samples, 1):
                record = await self.db.translation_transactions.find_one({"_id": record_id})

                if not record:
                    logger.warning(f"  [{i}] Record not found: {record_id}")
                    continue

                logger.info(f"  [{i}] ID: {record_id}")
                logger.info(f"      Transaction ID: {record.get('transaction_id')}")
                logger.info(f"      User ID:        {record.get('user_id')}")
                logger.info(f"      File Name:      {record.get('file_name')}")
                logger.info(f"      Status:         {record.get('status')}")
                logger.info(f"      Created:        {record.get('created_at')}")
                logger.info(f"      Has documents:  {('documents' in record)}")
                logger.info("")

            logger.info("-" * 80)

        except Exception as e:
            logger.error(f"✗ Failed to show samples: {e}")

    def get_manual_confirmation(self) -> bool:
        """Get manual confirmation from user."""
        try:
            logger.info("\n" + "="*80)
            logger.info("⚠ WARNING: You are about to DELETE records from the database!")
            logger.info("="*80)
            logger.info(f"\nTotal records to delete: {len(self.old_ids)}")
            logger.info("\nThis action CANNOT be undone!")
            logger.info("Please ensure you have:")
            logger.info("  1. Verified the migration was successful")
            logger.info("  2. Tested your application with the new structure")
            logger.info("  3. Confirmed backup exists")
            logger.info("\nType 'DELETE' (all caps) to confirm deletion: ", end="")

            user_input = input().strip()

            if user_input == "DELETE":
                logger.info("\n✓ Confirmation received")
                return True
            else:
                logger.info(f"\n✗ Confirmation failed (got '{user_input}', expected 'DELETE')")
                logger.info("  Aborting deletion")
                return False

        except KeyboardInterrupt:
            logger.info("\n\n✗ Cancelled by user")
            return False
        except Exception as e:
            logger.error(f"✗ Confirmation failed: {e}")
            return False

    async def delete_records(self) -> tuple[int, int]:
        """
        Delete old flat records.

        Returns:
            Tuple of (deleted_count, error_count)
        """
        try:
            logger.info(f"\nDeleting {len(self.old_ids)} old flat records...")

            # Delete records by ID (only flat records)
            result = await self.db.translation_transactions.delete_many({
                "_id": {"$in": self.old_ids},
                "documents": {"$exists": False}  # Safety: only delete flat records
            })

            deleted_count = result.deleted_count
            error_count = len(self.old_ids) - deleted_count

            logger.info(f"✓ Deletion complete:")
            logger.info(f"  Deleted:  {deleted_count}")
            logger.info(f"  Skipped:  {error_count}")

            return deleted_count, error_count

        except Exception as e:
            logger.error(f"✗ Deletion failed: {e}")
            return 0, len(self.old_ids)

    async def verify_cleanup(self) -> bool:
        """Verify that no flat records remain."""
        try:
            logger.info("\nVerifying cleanup...")

            # Count remaining flat records
            remaining_flat = await self.db.translation_transactions.count_documents({
                "documents": {"$exists": False}
            })

            # Count nested records
            nested_count = await self.db.translation_transactions.count_documents({
                "documents": {"$exists": True}
            })

            # Total records
            total_count = await self.db.translation_transactions.count_documents({})

            logger.info(f"✓ Verification complete:")
            logger.info(f"  Flat records remaining: {remaining_flat}")
            logger.info(f"  Nested records:         {nested_count}")
            logger.info(f"  Total records:          {total_count}")

            if remaining_flat > 0:
                logger.warning(f"\n⚠ WARNING: {remaining_flat} flat records still exist!")
                logger.warning("  These may be new records created after migration.")
                return False

            logger.info("\n✓ All flat records have been removed!")
            return True

        except Exception as e:
            logger.error(f"✗ Verification failed: {e}")
            return False

    async def run_dry_run(self):
        """Execute dry run (show what would be deleted)."""
        try:
            logger.info("="*80)
            logger.info("DRY RUN MODE - No records will be deleted")
            logger.info("="*80 + "\n")

            # Step 1: Connect
            if not await self.connect():
                return False

            # Step 2: Load IDs
            logger.info("[Step 1/3] Loading old record IDs...")
            if not self.load_old_ids():
                return False

            # Step 3: Verify
            logger.info("\n[Step 2/3] Verifying records...")
            flat_count, nested_count = await self.verify_flat_records()

            if nested_count > 0:
                logger.error("\n✗ Some records have nested structure - aborting")
                return False

            # Step 4: Show samples
            logger.info("\n[Step 3/3] Showing sample records...")
            await self.show_sample_records()

            logger.info("\n" + "="*80)
            logger.info("DRY RUN COMPLETE")
            logger.info("="*80)
            logger.info(f"\nWould delete {len(self.old_ids)} records")
            logger.info(f"  Flat records: {flat_count}")
            logger.info("\nTo actually delete these records, run:")
            logger.info(f"  python {sys.argv[0]} {self.ids_file} --confirm")
            logger.info("="*80 + "\n")

            return True

        except Exception as e:
            logger.error(f"\n✗ Dry run failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            await self.disconnect()

    async def run_deletion(self):
        """Execute actual deletion."""
        try:
            logger.info("="*80)
            logger.info("DELETION MODE - Records will be permanently deleted")
            logger.info("="*80 + "\n")

            # Step 1: Connect
            if not await self.connect():
                return False

            # Step 2: Load IDs
            logger.info("[Step 1/5] Loading old record IDs...")
            if not self.load_old_ids():
                return False

            # Step 3: Verify
            logger.info("\n[Step 2/5] Verifying records...")
            flat_count, nested_count = await self.verify_flat_records()

            if nested_count > 0:
                logger.error("\n✗ Some records have nested structure - aborting")
                return False

            # Step 4: Show samples
            logger.info("\n[Step 3/5] Showing sample records...")
            await self.show_sample_records()

            # Step 5: Get confirmation
            logger.info("\n[Step 4/5] Requesting confirmation...")
            if not self.get_manual_confirmation():
                logger.info("\n✗ Deletion cancelled")
                return False

            # Step 6: Delete
            logger.info("\n[Step 5/5] Deleting records...")
            deleted_count, error_count = await self.delete_records()

            # Step 7: Verify
            await self.verify_cleanup()

            logger.info("\n" + "="*80)
            logger.info("CLEANUP COMPLETE!")
            logger.info("="*80)
            logger.info(f"\nDeleted:  {deleted_count} records")
            logger.info(f"Errors:   {error_count}")
            logger.info("="*80 + "\n")

            return True

        except Exception as e:
            logger.error(f"\n✗ Deletion failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Delete old flat translation transaction records after migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (default)
  python cleanup_old_transaction_records.py /tmp/translation_transactions_old_ids_20241106.txt

  # Actual deletion
  python cleanup_old_transaction_records.py /tmp/translation_transactions_old_ids_20241106.txt --confirm
        """
    )
    parser.add_argument(
        "ids_file",
        help="Path to file containing old record IDs (from migration script)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually delete records (default is dry run)"
    )

    args = parser.parse_args()

    # Get MongoDB connection details
    mongodb_uri = os.getenv("MONGODB_URI", settings.mongodb_uri)
    database_name = os.getenv("MONGODB_DATABASE", settings.mongodb_database)

    # Create cleaner
    cleaner = OldRecordCleaner(
        mongodb_uri=mongodb_uri,
        database_name=database_name,
        ids_file=args.ids_file,
        confirm=args.confirm
    )

    # Run dry run or deletion
    if args.confirm:
        success = await cleaner.run_deletion()
    else:
        success = await cleaner.run_dry_run()

    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n\n⚠ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
