#!/usr/bin/env python3
"""
MongoDB Golden Source Dump Script
===================================

Dumps the production 'translation' database to JSON files as the Golden Source for tests.
All collections are saved to tests/fixtures/golden_db/ directory.

Usage:
    python scripts/dump_golden_db.py
    python scripts/dump_golden_db.py --verbose
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

# Output directory for golden source
GOLDEN_DB_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "golden_db"


class GoldenSourceDumper:
    """Dump MongoDB database to JSON files for test fixtures."""

    def __init__(self, verbose: bool = False):
        """Initialize dumper."""
        settings = get_settings()
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db_name = settings.mongodb_database  # Use production DB name
        self.db = self.client[self.db_name]
        self.verbose = verbose

        # Create output directory if it doesn't exist
        GOLDEN_DB_DIR.mkdir(parents=True, exist_ok=True)

        if self.verbose:
            print(f"📊 Configuration:")
            print(f"   MongoDB URI: {settings.mongodb_uri[:30]}...")
            print(f"   Database: {self.db_name}")
            print(f"   Output dir: {GOLDEN_DB_DIR}")
            print()

    async def get_all_collections(self) -> list:
        """
        Get all collection names from the database.

        Returns:
            List of collection names
        """
        collections = await self.db.list_collection_names()
        # Filter out system collections
        return [c for c in collections if not c.startswith("system.")]

    async def dump_collection(self, collection_name: str) -> int:
        """
        Dump a single collection to JSON file.

        Args:
            collection_name: Name of the collection to dump

        Returns:
            Number of documents dumped
        """
        collection = self.db[collection_name]

        # Get all documents
        documents = await collection.find({}).to_list(length=None)

        if not documents:
            if self.verbose:
                print(f"   ℹ️  {collection_name}: empty (skipping)")
            return 0

        # Convert to JSON-serializable format using BSON json_util
        # This properly handles ObjectId, datetime, Decimal128, etc.
        serialized_docs = json.loads(json_util.dumps(documents))

        # Write to file
        output_file = GOLDEN_DB_DIR / f"{collection_name}.json"
        with open(output_file, 'w') as f:
            json.dump(serialized_docs, f, indent=2)

        file_size = output_file.stat().st_size / 1024  # Size in KB

        print(f"   ✅ {collection_name}: {len(documents)} documents ({file_size:.2f} KB)")

        return len(documents)

    async def dump_all(self):
        """Dump all collections to golden source directory."""
        print(f"🔄 Dumping database '{self.db_name}' to Golden Source...")
        print(f"📁 Output location: {GOLDEN_DB_DIR}")
        print()

        # Get all collections
        collections = await self.get_all_collections()

        if not collections:
            print("❌ No collections found in database!")
            return

        print(f"📦 Found {len(collections)} collections:")
        if self.verbose:
            for coll in collections:
                print(f"   - {coll}")
            print()

        # Dump each collection
        print("📝 Dumping collections...")
        total_docs = 0
        dumped_collections = 0

        for collection_name in sorted(collections):
            try:
                doc_count = await self.dump_collection(collection_name)
                total_docs += doc_count
                if doc_count > 0:
                    dumped_collections += 1
            except Exception as e:
                print(f"   ❌ {collection_name}: ERROR - {e}")

        # Summary
        print()
        print(f"✅ Golden Source dump completed!")
        print(f"   Collections dumped: {dumped_collections}/{len(collections)}")
        print(f"   Total documents: {total_docs}")
        print(f"   Location: {GOLDEN_DB_DIR}")

        # List generated files
        if self.verbose:
            print()
            print("📄 Generated files:")
            for json_file in sorted(GOLDEN_DB_DIR.glob("*.json")):
                file_size = json_file.stat().st_size / 1024
                print(f"   - {json_file.name} ({file_size:.2f} KB)")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Dump MongoDB database to Golden Source for tests"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    dumper = GoldenSourceDumper(verbose=args.verbose)

    try:
        await dumper.dump_all()
    except Exception as e:
        print(f"\n❌ Error during dump: {e}")
        import traceback
        if args.verbose:
            traceback.print_exc()
        sys.exit(1)
    finally:
        dumper.client.close()


if __name__ == "__main__":
    asyncio.run(main())
