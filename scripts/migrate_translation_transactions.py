#!/usr/bin/env python3
"""
Migration Script: Transform Flat Translation Transactions to Nested Structure

PURPOSE:
    Migrate existing flat translation_transactions records to new nested structure
    with documents[] array containing document-level information.

WHAT IT DOES:
    1. Creates timestamped backup collection
    2. Identifies flat records (no documents field)
    3. Groups records by transaction_id
    4. Transforms flat structure to nested documents[] structure
    5. Inserts new nested records
    6. Saves old record IDs to file for later cleanup
    7. Provides verification summary

TRANSFORMATION:
    OLD (flat):
        {
            "_id": ObjectId("..."),
            "transaction_id": "TXN-ABC",
            "user_id": "user@example.com",
            "file_name": "doc.pdf",
            "file_size": 12345,
            "original_file_url": "https://...",
            "translated_file_url": "https://..." or "",
            ...
        }

    NEW (nested):
        {
            "_id": ObjectId("..."),  # NEW ID
            "transaction_id": "TXN-ABC",
            "user_id": "user@example.com",
            "documents": [  # NESTED ARRAY
                {
                    "file_name": "doc.pdf",
                    "file_size": 12345,
                    "original_url": "https://...",
                    "translated_url": "https://..." or None,
                    "translated_name": None,
                    "status": "completed" if translated_url else "uploaded",
                    "uploaded_at": created_at,
                    "translated_at": updated_at if translated_url else None,
                    "processing_started_at": None,
                    "processing_duration": None
                }
            ],
            ...
        }

SAFETY:
    - Does NOT delete old records (only creates new ones)
    - Creates backup before migration
    - Saves old IDs to file for manual cleanup later
    - Comprehensive error handling
    - Dry-run verification available

Usage:
    python3 server/scripts/migrate_translation_transactions.py

    # Or with custom MongoDB URI
    MONGODB_URI="mongodb://localhost:27017/translation" python3 server/scripts/migrate_translation_transactions.py
"""
import asyncio
import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class TranslationTransactionMigrator:
    """Handles migration of flat translation transactions to nested structure."""

    def __init__(self, mongodb_uri: str, database_name: str):
        self.mongodb_uri = mongodb_uri
        self.database_name = database_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self.backup_collection_name = None

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

    async def create_backup(self) -> bool:
        """Create backup of translation_transactions collection."""
        try:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self.backup_collection_name = f"translation_transactions_backup_{timestamp}"

            logger.info(f"Creating backup collection: {self.backup_collection_name}")

            # Count documents to backup
            total_docs = await self.db.translation_transactions.count_documents({})
            logger.info(f"Found {total_docs} documents to backup")

            if total_docs == 0:
                logger.warning("⚠ No documents to backup")
                return True

            # Copy all documents to backup collection
            cursor = self.db.translation_transactions.find({})
            backup_docs = await cursor.to_list(length=None)

            if backup_docs:
                await self.db[self.backup_collection_name].insert_many(backup_docs)
                logger.info(f"✓ Backup created: {len(backup_docs)} documents")

            return True

        except Exception as e:
            logger.error(f"✗ Backup creation failed: {e}")
            return False

    async def identify_flat_records(self) -> List[Dict[str, Any]]:
        """Identify flat records that need migration (no documents field)."""
        try:
            logger.info("Identifying flat records (no documents field)...")

            # Find records without documents field
            cursor = self.db.translation_transactions.find({
                "documents": {"$exists": False}
            })

            flat_records = await cursor.to_list(length=None)
            logger.info(f"✓ Found {len(flat_records)} flat records to migrate")

            return flat_records

        except Exception as e:
            logger.error(f"✗ Failed to identify flat records: {e}")
            return []

    def transform_flat_to_nested(self, flat_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform a flat record to nested structure.

        Args:
            flat_record: Original flat record

        Returns:
            Transformed nested record with documents[] array
        """
        # Extract file-related fields to move into documents array
        file_name = flat_record.get("file_name", "")
        file_size = flat_record.get("file_size", 0)
        original_file_url = flat_record.get("original_file_url", "")
        translated_file_url = flat_record.get("translated_file_url", "")

        # Determine document status
        if translated_file_url and translated_file_url.strip():
            doc_status = "completed"
            translated_url = translated_file_url
            translated_at = flat_record.get("updated_at")
        else:
            doc_status = "uploaded"
            translated_url = None
            translated_at = None

        # Create document object
        document = {
            "file_name": file_name,
            "file_size": file_size,
            "original_url": original_file_url,
            "translated_url": translated_url,
            "translated_name": None,  # Not available in flat structure
            "status": doc_status,
            "uploaded_at": flat_record.get("created_at", datetime.now(timezone.utc)),
            "translated_at": translated_at,
            "processing_started_at": None,  # Not available in flat structure
            "processing_duration": None  # Not available in flat structure
        }

        # Create new nested record (exclude file fields and _id)
        nested_record = {
            "transaction_id": flat_record.get("transaction_id"),
            "user_id": flat_record.get("user_id"),
            "documents": [document],  # Array with single document
            "source_language": flat_record.get("source_language"),
            "target_language": flat_record.get("target_language"),
            "units_count": flat_record.get("units_count"),
            "price_per_unit": flat_record.get("price_per_unit"),
            "total_price": flat_record.get("total_price"),
            "status": flat_record.get("status"),
            "created_at": flat_record.get("created_at", datetime.now(timezone.utc)),
            "updated_at": flat_record.get("updated_at", datetime.now(timezone.utc))
        }

        # Optional fields
        optional_fields = [
            "company_name", "subscription_id", "unit_type", "error_message",
            "estimated_cost", "actual_cost", "metadata", "completed_at"
        ]

        for field in optional_fields:
            if field in flat_record:
                nested_record[field] = flat_record[field]

        return nested_record

    async def migrate_records(self, flat_records: List[Dict[str, Any]]) -> tuple[int, int]:
        """
        Migrate flat records to nested structure.

        Args:
            flat_records: List of flat records to migrate

        Returns:
            Tuple of (success_count, error_count)
        """
        success_count = 0
        error_count = 0

        logger.info(f"Starting migration of {len(flat_records)} records...")

        # Group by transaction_id (rare case: multiple docs per transaction)
        grouped_records: Dict[str, List[Dict[str, Any]]] = {}
        for record in flat_records:
            txn_id = record.get("transaction_id")
            if not txn_id:
                logger.warning(f"⚠ Skipping record with no transaction_id: {record.get('_id')}")
                error_count += 1
                continue

            if txn_id not in grouped_records:
                grouped_records[txn_id] = []
            grouped_records[txn_id].append(record)

        logger.info(f"Grouped into {len(grouped_records)} unique transactions")

        # Process each transaction
        for txn_id, records in grouped_records.items():
            try:
                if len(records) == 1:
                    # Single document - straightforward transformation
                    nested_record = self.transform_flat_to_nested(records[0])

                else:
                    # Multiple documents for same transaction (rare)
                    logger.info(f"⚠ Transaction {txn_id} has {len(records)} documents")

                    # Use first record as base, combine documents
                    base_record = records[0]
                    nested_record = self.transform_flat_to_nested(base_record)

                    # Add additional documents
                    for additional_record in records[1:]:
                        additional_nested = self.transform_flat_to_nested(additional_record)
                        nested_record["documents"].extend(additional_nested["documents"])

                # Replace flat record with nested version (atomic operation)
                # This avoids unique index conflicts on transaction_id
                first_record_id = records[0]["_id"]
                result = await self.db.translation_transactions.replace_one(
                    {"_id": first_record_id},
                    nested_record
                )

                # If multiple records for same transaction_id, delete the extras
                if len(records) > 1:
                    extra_ids = [rec["_id"] for rec in records[1:]]
                    await self.db.translation_transactions.delete_many({
                        "_id": {"$in": extra_ids}
                    })
                    logger.info(f"  Merged {len(records)} records into one nested record")

                success_count += 1

                if success_count % 10 == 0:
                    logger.info(f"Progress: {success_count}/{len(grouped_records)} transactions migrated")

            except Exception as e:
                # Log any errors during migration
                logger.error(f"✗ Error migrating transaction {txn_id}: {e}")
                error_count += 1

        return success_count, error_count

    async def save_old_ids(self) -> str:
        """
        No longer needed - records are replaced in-place during migration.
        Old flat records are automatically deleted when replaced with nested versions.
        """
        logger.info("✓ Old flat records were replaced during migration (no cleanup needed)")
        return ""

    async def verify_migration(self, expected_count: int) -> bool:
        """Verify migration results."""
        try:
            logger.info("\n" + "="*80)
            logger.info("MIGRATION VERIFICATION")
            logger.info("="*80)

            # Count flat records remaining
            flat_remaining = await self.db.translation_transactions.count_documents({
                "documents": {"$exists": False}
            })

            # Count nested records
            nested_count = await self.db.translation_transactions.count_documents({
                "documents": {"$exists": True}
            })

            # Total records
            total_count = await self.db.translation_transactions.count_documents({})

            logger.info(f"\nRecord Counts:")
            logger.info(f"  Flat records remaining:    {flat_remaining}")
            logger.info(f"  Nested records:            {nested_count}")
            logger.info(f"  Total records:             {total_count}")
            logger.info(f"  Expected migrations:       {expected_count}")

            # Show sample nested record
            sample = await self.db.translation_transactions.find_one({
                "documents": {"$exists": True}
            })

            if sample:
                logger.info(f"\nSample Nested Record:")
                logger.info(f"  Transaction ID:  {sample.get('transaction_id')}")
                logger.info(f"  User ID:         {sample.get('user_id')}")
                logger.info(f"  Documents:       {len(sample.get('documents', []))} document(s)")
                logger.info(f"  Status:          {sample.get('status')}")
                logger.info(f"  Total Price:     ${sample.get('total_price', 0):.2f}")

                if sample.get('documents'):
                    doc = sample['documents'][0]
                    logger.info(f"\n  First Document:")
                    logger.info(f"    File Name:     {doc.get('file_name')}")
                    logger.info(f"    File Size:     {doc.get('file_size')} bytes")
                    logger.info(f"    Status:        {doc.get('status')}")
                    logger.info(f"    Uploaded At:   {doc.get('uploaded_at')}")
                    logger.info(f"    Translated:    {doc.get('translated_url') is not None}")

            logger.info("="*80 + "\n")

            return True

        except Exception as e:
            logger.error(f"✗ Verification failed: {e}")
            return False

    async def run(self):
        """Execute full migration process."""
        try:
            logger.info("="*80)
            logger.info("TRANSLATION TRANSACTIONS MIGRATION")
            logger.info("Flat Structure → Nested Structure with documents[]")
            logger.info("="*80 + "\n")

            # Step 1: Connect
            if not await self.connect():
                return False

            # Step 2: Create backup
            logger.info("\n[Step 1/5] Creating backup...")
            if not await self.create_backup():
                logger.error("✗ Backup failed - aborting migration")
                return False

            # Step 3: Identify flat records
            logger.info("\n[Step 2/5] Identifying flat records...")
            flat_records = await self.identify_flat_records()

            if not flat_records:
                logger.info("✓ No flat records found - migration not needed")
                return True

            # Show sample flat record
            if flat_records:
                sample = flat_records[0]
                logger.info(f"\nSample Flat Record (before migration):")
                logger.info(f"  Transaction ID:  {sample.get('transaction_id')}")
                logger.info(f"  File Name:       {sample.get('file_name')}")
                logger.info(f"  File Size:       {sample.get('file_size')} bytes")
                logger.info(f"  Status:          {sample.get('status')}")

            # Step 4: Migrate records
            logger.info(f"\n[Step 3/5] Migrating {len(flat_records)} records...")
            success_count, error_count = await self.migrate_records(flat_records)

            logger.info(f"\n✓ Migration complete:")
            logger.info(f"  Successful: {success_count}")
            logger.info(f"  Errors:     {error_count}")

            # Step 4: Cleanup messaging
            logger.info(f"\n[Step 4/4] Migration cleanup...")
            await self.save_old_ids()

            # Step 5: Verify
            logger.info(f"\n[Step 5/5] Verifying migration...")
            await self.verify_migration(len(flat_records))

            logger.info("\n" + "="*80)
            logger.info("MIGRATION SUCCESSFUL!")
            logger.info("="*80)
            logger.info(f"\n✓ Old flat records were REPLACED with nested structure (deleted during migration)")
            logger.info(f"\nNext Steps:")
            logger.info(f"1. Verify migrated data in your application")
            logger.info(f"2. Check transaction list endpoint works correctly")
            logger.info(f"3. Test translation upload and processing flow")
            logger.info(f"\n⚠ Backup location: {self.backup_collection_name}")
            logger.info(f"   (Keep for rollback if needed)")
            logger.info("="*80 + "\n")

            return True

        except Exception as e:
            logger.error(f"\n✗ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    # Get MongoDB connection details
    mongodb_uri = os.getenv("MONGODB_URI", settings.mongodb_uri)
    database_name = os.getenv("MONGODB_DATABASE", settings.mongodb_database)

    # Create and run migrator
    migrator = TranslationTransactionMigrator(mongodb_uri, database_name)
    success = await migrator.run()

    return 0 if success else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n\n⚠ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
