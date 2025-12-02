#!/usr/bin/env python3
"""
MongoDB Test Database Restore Script
=====================================

Restores the Golden Source from tests/fixtures/golden_db/ to the 'translation_test' database.
Drops all existing collections in translation_test and recreates them from the golden source.

Usage:
    python scripts/restore_test_db.py
    python scripts/restore_test_db.py --verbose
    python scripts/restore_test_db.py --skip-indexes  # Skip index recreation
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId, Decimal128, json_util
import argparse

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings

# Golden source directory (legacy - now using daily backups)
GOLDEN_DB_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "golden_db"

# Daily backups directory (preferred source)
BACKUPS_DIR = Path(__file__).parent.parent / "backups"


class TestDatabaseRestorer:
    """Restore MongoDB test database from Golden Source JSON files."""

    def __init__(self, verbose: bool = False, skip_indexes: bool = False):
        """Initialize restorer."""
        settings = get_settings()
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db_name = settings.mongodb_database_test  # Use test DB name
        self.db = self.client[self.db_name]
        self.verbose = verbose
        self.skip_indexes = skip_indexes

        # Verify we're targeting test database
        if "test" not in self.db_name.lower():
            raise ValueError(
                f"Safety check failed: Database name '{self.db_name}' does not contain 'test'. "
                "This script only operates on test databases."
            )

        if self.verbose:
            print(f"📊 Configuration:")
            print(f"   MongoDB URI: {settings.mongodb_uri[:30]}...")
            print(f"   Target database: {self.db_name}")
            print(f"   Golden source dir: {GOLDEN_DB_DIR}")
            print(f"   Skip indexes: {skip_indexes}")
            print()

    async def drop_all_collections(self):
        """Drop all collections in the test database."""
        print(f"🗑️  Dropping all collections in '{self.db_name}'...")

        collections = await self.db.list_collection_names()
        system_collections = [c for c in collections if c.startswith("system.")]
        user_collections = [c for c in collections if not c.startswith("system.")]

        if not user_collections:
            print("   ℹ️  No collections to drop")
            return

        dropped_count = 0
        for collection_name in user_collections:
            await self.db.drop_collection(collection_name)
            dropped_count += 1
            if self.verbose:
                print(f"   ❌ Dropped: {collection_name}")

        print(f"   Dropped {dropped_count} collections")
        print()

    async def restore_collection(self, json_file: Path) -> tuple[str, int]:
        """
        Restore a single collection from JSON file.

        Args:
            json_file: Path to the JSON file containing collection data

        Returns:
            Tuple of (collection_name, document_count)
        """
        collection_name = json_file.stem  # Filename without .json extension

        # Read JSON file
        with open(json_file, 'r') as f:
            json_data = json.load(f)

        if not json_data:
            if self.verbose:
                print(f"   ℹ️  {collection_name}: empty (skipping)")
            return collection_name, 0

        # Convert from JSON back to MongoDB format using json_util
        # This properly restores ObjectId, datetime, Decimal128, etc.
        documents = json_util.loads(json.dumps(json_data))

        # Insert documents
        collection = self.db[collection_name]
        await collection.insert_many(documents)

        print(f"   ✅ {collection_name}: {len(documents)} documents restored")

        return collection_name, len(documents)

    async def get_collection_indexes(self, collection_name: str) -> list:
        """
        Get indexes for a collection from the production database.

        Args:
            collection_name: Name of the collection

        Returns:
            List of index information dictionaries
        """
        settings = get_settings()
        prod_db = self.client[settings.mongodb_database]
        collection = prod_db[collection_name]

        try:
            indexes = await collection.index_information()
            # Filter out default _id index
            return {name: info for name, info in indexes.items() if name != "_id_"}
        except Exception as e:
            if self.verbose:
                print(f"   ⚠️  Could not get indexes for {collection_name}: {e}")
            return {}

    async def recreate_indexes(self, collection_name: str):
        """
        Recreate indexes for a collection based on production database.

        Args:
            collection_name: Name of the collection
        """
        if self.skip_indexes:
            return

        indexes = await self.get_collection_indexes(collection_name)

        if not indexes:
            if self.verbose:
                print(f"      No indexes to create for {collection_name}")
            return

        collection = self.db[collection_name]

        for index_name, index_info in indexes.items():
            try:
                # Extract index key (list of tuples)
                keys = index_info.get("key", [])

                if not keys:
                    continue

                # Extract index options
                options = {}
                if index_info.get("unique"):
                    options["unique"] = True
                if index_info.get("sparse"):
                    options["sparse"] = True
                if "expireAfterSeconds" in index_info:
                    options["expireAfterSeconds"] = index_info["expireAfterSeconds"]
                if index_name != "_".join([k for k, _ in keys]):
                    options["name"] = index_name

                # Create index
                await collection.create_index(keys, **options)

                if self.verbose:
                    print(f"      📌 Created index: {index_name}")

            except Exception as e:
                print(f"      ⚠️  Failed to create index {index_name}: {e}")

    async def restore_from_daily_backup(self):
        """Restore all collections from latest daily backup file."""
        print(f"🔄 Restoring from latest daily backup to '{self.db_name}'...")
        print(f"📁 Backups location: {BACKUPS_DIR}")
        print()

        # Verify backups directory exists
        if not BACKUPS_DIR.exists():
            print(f"❌ Backups directory not found: {BACKUPS_DIR}")
            print("   Create backups first or use old restore_all() method.")
            return

        # Get all backup files and find the latest
        backup_files = sorted(BACKUPS_DIR.glob("backup_translation_*.json"), reverse=True)

        if not backup_files:
            print(f"❌ No backup files found in {BACKUPS_DIR}")
            print("   Create a backup first.")
            return

        latest_backup = backup_files[0]
        print(f"📦 Using latest backup: {latest_backup.name}")
        print(f"   Timestamp: {latest_backup.stat().st_mtime}")
        print()

        # Load backup file
        with open(latest_backup, 'r') as f:
            backup_data = json.load(f, object_hook=json_util.object_hook)

        collections_data = backup_data.get("collections", {})
        print(f"📦 Found {len(collections_data)} collections in backup")
        if self.verbose:
            for coll_name in sorted(collections_data.keys()):
                doc_count = len(collections_data[coll_name])
                print(f"   - {coll_name}: {doc_count} documents")
            print()

        # Drop existing collections
        await self.drop_all_collections()

        # Restore each collection from backup
        print("📝 Restoring collections...")
        total_docs = 0
        restored_collections = []

        for collection_name, documents in sorted(collections_data.items()):
            if not documents:
                if self.verbose:
                    print(f"   ℹ️  {collection_name}: empty")
                continue

            try:
                # Insert documents
                collection = self.db[collection_name]
                if documents:
                    await collection.insert_many(documents)

                doc_count = len(documents)
                total_docs += doc_count
                restored_collections.append(collection_name)
                print(f"   ✅ {collection_name}: {doc_count} documents")

                # Recreate indexes
                if not self.skip_indexes:
                    await self.recreate_indexes(collection_name)

            except Exception as e:
                print(f"   ❌ {collection_name}: ERROR - {e}")
                if self.verbose:
                    import traceback
                    traceback.print_exc()

        # Summary
        print()
        print("=" * 80)
        print("✅ Restoration completed successfully!")
        print(f"   Collections restored: {len(restored_collections)}/{len(collections_data)}")
        print(f"   Total documents: {total_docs}")
        print(f"   Database: {self.db_name}")
        print(f"   Source: {latest_backup.name}")
        if not self.skip_indexes:
            print("   Indexes recreated: ✅")
        print("=" * 80)

    async def restore_all(self):
        """Restore all collections - now uses daily backups instead of golden source."""
        # Use daily backup restoration
        await self.restore_from_daily_backup()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Restore MongoDB test database from Golden Source"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Skip index recreation"
    )

    args = parser.parse_args()

    restorer = TestDatabaseRestorer(
        verbose=args.verbose,
        skip_indexes=args.skip_indexes
    )

    try:
        await restorer.restore_all()
    except Exception as e:
        print(f"\n❌ Error during restore: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)
    finally:
        restorer.client.close()


if __name__ == "__main__":
    asyncio.run(main())
