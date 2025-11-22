#!/usr/bin/env python3
"""
MongoDB Database Backup Script
===============================

Creates a timestamped backup of the MongoDB database before running tests.

Usage:
    python scripts/backup_database.py                    # Backup 'translation' database
    python scripts/backup_database.py --db translation_test  # Backup specific database
    python scripts/backup_database.py --list             # List available backups
    python scripts/backup_database.py --restore latest   # Restore from latest backup
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId, json_util
import argparse

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/translation")
BACKUP_DIR = Path(__file__).parent.parent / "backups"

# Collections to backup (all important collections)
COLLECTIONS = [
    "subscriptions",
    "companies",
    "users",
    "invoices",
    "payments",
    "translation_transactions",
    "user_transactions",
]

class DatabaseBackup:
    """Handle database backup and restore operations."""

    def __init__(self, db_name: str = None):
        """Initialize backup handler."""
        self.client = AsyncIOMotorClient(MONGODB_URI)

        # Extract database name from URI or use provided
        if db_name:
            self.db_name = db_name
        else:
            self.db_name = MONGODB_URI.split("/")[-1] if "/" in MONGODB_URI else "translation"

        self.db = self.client[self.db_name]

        # Create backup directory if it doesn't exist
        BACKUP_DIR.mkdir(exist_ok=True)

    async def create_backup(self) -> Path:
        """
        Create a timestamped backup of the database.

        Returns:
            Path to the backup file
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"backup_{self.db_name}_{timestamp}.json"

        print(f"🔄 Creating backup of database '{self.db_name}'...")
        print(f"📁 Backup location: {backup_file}")

        backup_data = {
            "database": self.db_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "collections": {}
        }

        total_docs = 0

        for collection_name in COLLECTIONS:
            collection = self.db[collection_name]

            # Get all documents from collection
            documents = await collection.find({}).to_list(length=None)

            if documents:
                # Convert to JSON-serializable format
                serialized_docs = json.loads(json_util.dumps(documents))
                backup_data["collections"][collection_name] = serialized_docs
                total_docs += len(documents)
                print(f"   ✅ {collection_name}: {len(documents)} documents")
            else:
                print(f"   ℹ️  {collection_name}: empty")

        # Write backup to file
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)

        file_size = backup_file.stat().st_size / 1024  # Size in KB

        print(f"\n✅ Backup created successfully!")
        print(f"   Total documents: {total_docs}")
        print(f"   File size: {file_size:.2f} KB")
        print(f"   Location: {backup_file}")

        return backup_file

    async def list_backups(self):
        """List all available backups."""
        backups = sorted(BACKUP_DIR.glob("backup_*.json"), reverse=True)

        if not backups:
            print("📂 No backups found")
            return

        print(f"📂 Available backups in {BACKUP_DIR}:\n")

        for i, backup_file in enumerate(backups, 1):
            file_size = backup_file.stat().st_size / 1024

            # Try to read backup metadata
            try:
                with open(backup_file, 'r') as f:
                    data = json.load(f)
                    timestamp = data.get("timestamp", "unknown")
                    db_name = data.get("database", "unknown")
                    total_docs = sum(len(docs) for docs in data.get("collections", {}).values())

                print(f"{i}. {backup_file.name}")
                print(f"   Database: {db_name}")
                print(f"   Created: {timestamp}")
                print(f"   Documents: {total_docs}")
                print(f"   Size: {file_size:.2f} KB")

                if i == 1:
                    print("   ⭐ LATEST")

                print()

            except Exception as e:
                print(f"{i}. {backup_file.name} (corrupted: {e})")
                print()

    async def restore_backup(self, backup_identifier: str):
        """
        Restore database from a backup.

        Args:
            backup_identifier: 'latest' or backup filename
        """
        # Find backup file
        if backup_identifier == "latest":
            backups = sorted(BACKUP_DIR.glob("backup_*.json"), reverse=True)
            if not backups:
                print("❌ No backups found to restore")
                return
            backup_file = backups[0]
        else:
            backup_file = BACKUP_DIR / backup_identifier
            if not backup_file.exists():
                print(f"❌ Backup file not found: {backup_file}")
                return

        print(f"🔄 Restoring from backup: {backup_file.name}")

        # Read backup data
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)

        restored_db = backup_data.get("database")
        backup_timestamp = backup_data.get("timestamp")
        collections_data = backup_data.get("collections", {})

        print(f"   Database: {restored_db}")
        print(f"   Created: {backup_timestamp}")
        print(f"   Collections: {len(collections_data)}")
        print()

        # Confirm restore
        print("⚠️  WARNING: This will DELETE existing data and restore from backup!")
        response = input("   Type 'YES' to confirm restore: ")

        if response != "YES":
            print("❌ Restore cancelled")
            return

        print("\n🔄 Restoring collections...")

        total_restored = 0

        for collection_name, documents in collections_data.items():
            collection = self.db[collection_name]

            # Clear existing data
            delete_result = await collection.delete_many({})
            print(f"   🗑️  {collection_name}: deleted {delete_result.deleted_count} existing documents")

            if documents:
                # Convert from JSON back to MongoDB format
                mongo_docs = json_util.loads(json.dumps(documents))

                # Insert restored documents
                await collection.insert_many(mongo_docs)
                total_restored += len(documents)
                print(f"   ✅ {collection_name}: restored {len(documents)} documents")
            else:
                print(f"   ℹ️  {collection_name}: no documents to restore")

        print(f"\n✅ Restore complete!")
        print(f"   Total documents restored: {total_restored}")

    async def cleanup_old_backups(self, keep_count: int = 10):
        """
        Remove old backups, keeping only the most recent N backups.

        Args:
            keep_count: Number of recent backups to keep
        """
        backups = sorted(BACKUP_DIR.glob("backup_*.json"), reverse=True)

        if len(backups) <= keep_count:
            print(f"📦 {len(backups)} backups found (keeping all)")
            return

        to_delete = backups[keep_count:]

        print(f"🗑️  Cleaning up old backups (keeping {keep_count} most recent)...")

        for backup_file in to_delete:
            backup_file.unlink()
            print(f"   ❌ Deleted: {backup_file.name}")

        print(f"✅ Cleanup complete! Deleted {len(to_delete)} old backups")

async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="MongoDB database backup utility")
    parser.add_argument("--db", help="Database name to backup (default: from MONGODB_URI)")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--restore", help="Restore from backup ('latest' or filename)")
    parser.add_argument("--cleanup", type=int, metavar="N", help="Keep only N most recent backups")

    args = parser.parse_args()

    backup_handler = DatabaseBackup(db_name=args.db)

    try:
        if args.list:
            await backup_handler.list_backups()
        elif args.restore:
            await backup_handler.restore_backup(args.restore)
        elif args.cleanup is not None:
            await backup_handler.cleanup_old_backups(keep_count=args.cleanup)
        else:
            # Default: create backup
            await backup_handler.create_backup()

    finally:
        backup_handler.client.close()

if __name__ == "__main__":
    asyncio.run(main())
