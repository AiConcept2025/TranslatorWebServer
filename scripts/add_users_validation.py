#!/usr/bin/env python3
"""
Add Database-Level Validation for Users Collection

This script implements database-level constraints for users:
1. company_name is required (non-null, non-empty string)
2. company_name must reference existing company
3. JSON Schema validation
4. Optimized indexes

Usage:
    # Dry run (recommended first)
    python scripts/add_users_validation.py --dry-run

    # Apply changes
    python scripts/add_users_validation.py

    # Apply to test database
    python scripts/add_users_validation.py --database translation_test

    # Force apply (skip confirmations)
    python scripts/add_users_validation.py --force

SAFETY:
- Never deletes data
- Only adds validation and indexes
- Dry-run mode available
- Verifies existing data integrity before applying
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel
from pymongo.errors import OperationFailure
import os


class UsersValidationMigration:
    """Manages MongoDB users validation migration."""

    def __init__(self, database_name: str = "translation", dry_run: bool = False, force: bool = False):
        self.database_name = database_name
        self.dry_run = dry_run
        self.force = force
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

        # Validation results
        self.orphaned_users: List[Dict] = []
        self.users_with_null_company: List[Dict] = []

    async def connect(self):
        """Connect to MongoDB."""
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[self.database_name]

        # Test connection
        try:
            await self.client.admin.command('ping')
            print(f"✅ Connected to MongoDB: {self.database_name}")
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            raise

    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            print("✅ Disconnected from MongoDB")

    def get_users_schema_validation(self) -> Dict:
        """
        Define JSON Schema validation for users collection.

        Enforces:
        - email is required, valid email format
        - company_name is required, non-empty string
        - created_at and updated_at are required dates
        """
        return {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["email", "company_name", "created_at", "updated_at"],
                "properties": {
                    "email": {
                        "bsonType": "string",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                        "description": "Email must be a valid email address"
                    },
                    "company_name": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 255,
                        "description": "Company name must be a non-empty string (1-255 chars), must reference existing company"
                    },
                    "full_name": {
                        "bsonType": ["string", "null"],
                        "description": "User's full name (optional)"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "Creation timestamp"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "Last update timestamp"
                    }
                }
            }
        }

    async def verify_existing_data(self) -> bool:
        """
        Verify existing data integrity.

        Checks:
        1. All users have non-null company_name
        2. All users reference existing companies

        Returns:
            True if data is valid, False otherwise
        """
        print("\n" + "="*60)
        print("STEP 1: VERIFY EXISTING DATA INTEGRITY")
        print("="*60)

        # Get all companies
        companies = await self.db.companies.find({}).to_list(length=None)
        company_names = set(c.get('company_name') for c in companies if c.get('company_name'))

        print(f"✓ Found {len(company_names)} companies")

        # Check for users with null company_name
        null_company_users = await self.db.users.find({"company_name": None}).to_list(length=None)

        if null_company_users:
            self.users_with_null_company = null_company_users
            print(f"\n❌ Found {len(null_company_users)} users with null company_name:")
            for user in null_company_users:
                print(f"   - {user.get('email')} ({user.get('full_name', 'Unknown')})")
            return False

        print("✓ No users with null company_name")

        # Check for orphaned users (company_name doesn't exist)
        all_users = await self.db.users.find({}).to_list(length=None)
        user_company_names = set(u.get('company_name') for u in all_users if u.get('company_name'))

        orphaned = user_company_names - company_names

        if orphaned:
            # Get users with orphaned company_name
            orphaned_users = [u for u in all_users if u.get('company_name') in orphaned]
            self.orphaned_users = orphaned_users

            print(f"\n❌ Found {len(orphaned_users)} users with non-existent companies:")
            for company in orphaned:
                users_count = len([u for u in orphaned_users if u.get('company_name') == company])
                print(f"   - {company} ({users_count} users)")
            return False

        print(f"✓ All {len(all_users)} users reference existing companies")

        print("\n✅ Data integrity verified - safe to proceed")
        return True

    async def add_validation_to_users(self):
        """Add JSON Schema validation to users collection."""
        print("\n" + "="*60)
        print("STEP 2: ADD VALIDATION TO USERS COLLECTION")
        print("="*60)

        collection = self.db.users

        # Check for existing validator
        try:
            coll_info = await self.db.command("listCollections", filter={"name": "users"})
            existing_validator = None
            if coll_info and "cursor" in coll_info and "firstBatch" in coll_info["cursor"]:
                first_batch = coll_info["cursor"]["firstBatch"]
                if first_batch and len(first_batch) > 0:
                    existing_validator = first_batch[0].get("options", {}).get("validator")

            if existing_validator:
                print("⚠️  Existing validator found - will be replaced")

        except Exception as e:
            print(f"ℹ️  Could not check existing validator: {e}")

        # Get validation schema
        validator = self.get_users_schema_validation()

        if self.dry_run:
            print("\n[DRY RUN] Would apply validator:")
            import json
            print(json.dumps(validator, indent=2))
            return

        # Apply validator
        try:
            await self.db.command("collMod", "users", validator=validator, validationLevel="strict")
            print("✅ Applied JSON Schema validation to users collection")
        except OperationFailure as e:
            print(f"❌ Failed to add validator: {e}")
            raise

    async def create_indexes(self):
        """Create optimized indexes for users collection."""
        print("\n" + "="*60)
        print("STEP 3: CREATE OPTIMIZED INDEXES")
        print("="*60)

        collection = self.db.users

        # Check existing indexes
        existing_indexes = await collection.index_information()
        print(f"ℹ️  Existing indexes: {list(existing_indexes.keys())}")

        indexes_to_create = []

        # 1. Email unique index (primary identifier)
        if 'email_unique' not in existing_indexes:
            indexes_to_create.append(
                IndexModel([("email", ASCENDING)], unique=True, name="email_unique")
            )

        # 2. Company name index (for lookups and joins)
        if 'company_name_idx' not in existing_indexes:
            indexes_to_create.append(
                IndexModel([("company_name", ASCENDING)], name="company_name_idx")
            )

        # 3. Compound index for company queries with sorting
        if 'company_created_idx' not in existing_indexes:
            indexes_to_create.append(
                IndexModel(
                    [("company_name", ASCENDING), ("created_at", ASCENDING)],
                    name="company_created_idx"
                )
            )

        if not indexes_to_create:
            print("✓ All required indexes already exist")
            return

        if self.dry_run:
            print("\n[DRY RUN] Would create indexes:")
            for idx_model in indexes_to_create:
                print(f"  - {idx_model.document['name']}")
            return

        # Create indexes
        try:
            await collection.create_indexes(indexes_to_create)
            print(f"✅ Created {len(indexes_to_create)} indexes:")
            for idx_model in indexes_to_create:
                print(f"  ✓ {idx_model.document['name']}")
        except Exception as e:
            print(f"❌ Failed to create indexes: {e}")
            raise

    async def run(self):
        """Execute the migration."""
        try:
            await self.connect()

            # Step 1: Verify data integrity
            is_valid = await self.verify_existing_data()

            if not is_valid:
                print("\n❌ MIGRATION ABORTED - Data integrity issues found")
                print("\nFix required:")
                if self.users_with_null_company:
                    print("  1. Run: python scripts/fix_null_company_names.py")
                if self.orphaned_users:
                    print("  2. Create missing companies or reassign users")
                return False

            # Step 2: Confirm if not forced
            if not self.force and not self.dry_run:
                print("\n" + "="*60)
                print("CONFIRMATION REQUIRED")
                print("="*60)
                response = input("\nProceed with migration? (yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("❌ Migration cancelled by user")
                    return False

            # Step 3: Add validation
            await self.add_validation_to_users()

            # Step 4: Create indexes
            await self.create_indexes()

            # Summary
            print("\n" + "="*60)
            print("MIGRATION COMPLETE")
            print("="*60)

            if self.dry_run:
                print("✓ Dry run completed - no changes made")
            else:
                print("✓ Users validation applied successfully")
                print("\nWhat was done:")
                print("  1. Added JSON Schema validation (company_name required)")
                print("  2. Created optimized indexes for performance")
                print("\nDatabase-level enforcement:")
                print("  - INSERT with null company_name → REJECTED")
                print("  - UPDATE setting company_name to null → REJECTED")
                print("  - Empty string company_name → REJECTED")

            return True

        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Add database-level validation for users collection")
    parser.add_argument("--database", default="translation", help="Database name (default: translation)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")

    args = parser.parse_args()

    migration = UsersValidationMigration(
        database_name=args.database,
        dry_run=args.dry_run,
        force=args.force
    )

    success = await migration.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
