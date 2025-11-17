#!/usr/bin/env python3
"""
Add Referential Integrity to MongoDB Collections

This script implements database-level referential integrity between
companies and subscriptions collections using:
1. JSON Schema validation
2. Optimized indexes
3. Data integrity verification

Usage:
    # Dry run (recommended first)
    python scripts/add_referential_integrity.py --dry-run

    # Apply changes
    python scripts/add_referential_integrity.py

    # Apply to test database
    python scripts/add_referential_integrity.py --database translation_test

    # Force apply (skip confirmations)
    python scripts/add_referential_integrity.py --force

SAFETY:
- Never deletes data
- Only adds validation and indexes
- Dry-run mode available
- Verifies existing data integrity before applying
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel
from pymongo.errors import OperationFailure, DuplicateKeyError
import os


class ReferentialIntegrityMigration:
    """Manages MongoDB referential integrity migration."""

    def __init__(self, database_name: str = "translation", dry_run: bool = False, force: bool = False):
        self.database_name = database_name
        self.dry_run = dry_run
        self.force = force
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

        # Validation results
        self.orphaned_subscriptions: List[Dict] = []
        self.missing_companies: List[str] = []

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

    def get_company_schema_validation(self) -> Dict:
        """
        Define JSON Schema validation for companies collection.

        Enforces:
        - company_name is required, non-empty string
        - created_at and updated_at are required dates
        """
        return {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["company_name", "created_at", "updated_at"],
                "properties": {
                    "company_name": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 255,
                        "description": "Company name must be a non-empty string (1-255 chars)"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "Creation timestamp must be a date"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "Update timestamp must be a date"
                    }
                },
                "additionalProperties": True
            }
        }

    def get_subscription_schema_validation(self) -> Dict:
        """
        Define JSON Schema validation for subscriptions collection.

        Enforces:
        - company_name is required and non-empty
        - All required subscription fields
        - Valid enum values for status and subscription_unit
        - Business rules (units > 0, dates, etc.)

        Note: MongoDB JSON Schema cannot directly enforce foreign key constraints.
        This is validated via application logic and verification scripts.
        """
        return {
            "$jsonSchema": {
                "bsonType": "object",
                "required": [
                    "company_name",
                    "subscription_unit",
                    "units_per_subscription",
                    "price_per_unit",
                    "subscription_price",
                    "start_date",
                    "status",
                    "usage_periods",
                    "created_at",
                    "updated_at"
                ],
                "properties": {
                    "company_name": {
                        "bsonType": "string",
                        "minLength": 1,
                        "maxLength": 255,
                        "description": "Company name must reference an existing company in companies collection"
                    },
                    "subscription_unit": {
                        "enum": ["page", "word", "character"],
                        "description": "Subscription unit must be one of: page, word, character"
                    },
                    "units_per_subscription": {
                        "bsonType": "int",
                        "minimum": 1,
                        "description": "Units per subscription must be a positive integer"
                    },
                    "price_per_unit": {
                        "bsonType": ["double", "decimal"],
                        "minimum": 0,
                        "description": "Price per unit must be non-negative"
                    },
                    "promotional_units": {
                        "bsonType": "int",
                        "minimum": 0,
                        "description": "Promotional units must be non-negative"
                    },
                    "discount": {
                        "bsonType": ["double", "decimal"],
                        "minimum": 0,
                        "maximum": 1,
                        "description": "Discount must be between 0 and 1"
                    },
                    "subscription_price": {
                        "bsonType": ["double", "decimal"],
                        "minimum": 0,
                        "description": "Subscription price must be non-negative"
                    },
                    "start_date": {
                        "bsonType": "date",
                        "description": "Start date must be a date"
                    },
                    "end_date": {
                        "bsonType": ["date", "null"],
                        "description": "End date must be a date or null"
                    },
                    "status": {
                        "enum": ["active", "inactive", "expired"],
                        "description": "Status must be one of: active, inactive, expired"
                    },
                    "usage_periods": {
                        "bsonType": "array",
                        "description": "Usage periods must be an array of usage period objects"
                    },
                    "created_at": {
                        "bsonType": "date",
                        "description": "Creation timestamp must be a date"
                    },
                    "updated_at": {
                        "bsonType": "date",
                        "description": "Update timestamp must be a date"
                    }
                },
                "additionalProperties": True
            }
        }

    def get_company_indexes(self) -> List[IndexModel]:
        """
        Define indexes for companies collection.

        Indexes:
        1. company_name (unique) - Already exists, ensures no duplicate companies
        2. created_at (ascending) - Already exists, for sorting/filtering
        """
        return [
            IndexModel(
                [("company_name", ASCENDING)],
                name="company_name_unique",
                unique=True
            ),
            IndexModel(
                [("created_at", ASCENDING)],
                name="created_at_asc"
            )
        ]

    def get_subscription_indexes(self) -> List[IndexModel]:
        """
        Define indexes for subscriptions collection.

        Indexes:
        1. company_name (non-unique) - For foreign key lookups (CRITICAL: must be non-unique)
        2. status - Already exists, for filtering active/inactive
        3. (company_name, status) - Already exists, compound for common queries
        4. start_date, end_date - Already exist, for date range queries
        5. created_at - Already exists, for sorting
        """
        return [
            IndexModel(
                [("company_name", ASCENDING)],
                name="company_name_idx",
                unique=False  # CRITICAL: Multiple subscriptions per company allowed
            ),
            IndexModel(
                [("status", ASCENDING)],
                name="status_idx"
            ),
            IndexModel(
                [("company_name", ASCENDING), ("status", ASCENDING)],
                name="company_status_idx"
            ),
            IndexModel(
                [("start_date", ASCENDING)],
                name="start_date_idx"
            ),
            IndexModel(
                [("end_date", ASCENDING)],
                name="end_date_idx"
            ),
            IndexModel(
                [("created_at", ASCENDING)],
                name="created_at_asc"
            )
        ]

    async def verify_data_integrity(self) -> bool:
        """
        Verify existing data integrity before applying validation.

        Checks:
        1. All subscriptions have valid company_name references
        2. No orphaned subscriptions

        Returns:
            bool: True if data is valid, False otherwise
        """
        print("\n" + "="*80)
        print("STEP 1: DATA INTEGRITY VERIFICATION")
        print("="*80)

        companies_collection = self.db.companies
        subscriptions_collection = self.db.subscriptions

        # Get all unique company names from subscriptions
        subscription_companies = await subscriptions_collection.distinct("company_name")
        print(f"📊 Found {len(subscription_companies)} unique companies in subscriptions")

        # Get all company names from companies collection
        existing_companies = await companies_collection.distinct("company_name")
        print(f"📊 Found {len(existing_companies)} companies in companies collection")

        # Find orphaned subscriptions
        self.missing_companies = [
            company for company in subscription_companies
            if company not in existing_companies
        ]

        if self.missing_companies:
            print(f"\n⚠️  WARNING: Found {len(self.missing_companies)} missing companies:")
            for company in self.missing_companies:
                # Get count of orphaned subscriptions
                count = await subscriptions_collection.count_documents({"company_name": company})
                print(f"   - '{company}': {count} subscription(s)")

                # Store orphaned subscriptions
                async for sub in subscriptions_collection.find({"company_name": company}):
                    self.orphaned_subscriptions.append(sub)

            print("\n❌ Data integrity check FAILED")
            print("   Action required: Fix orphaned subscriptions before applying validation")
            print("   Use: python scripts/verify_data_integrity.py --fix")
            return False

        print("\n✅ Data integrity check PASSED")
        print("   All subscriptions reference existing companies")
        return True

    async def fix_unique_constraint_issue(self) -> bool:
        """
        Fix the incorrect unique constraint on subscriptions.company_name.

        The current setup has:
        - subscriptions.company_name with unique=True (WRONG)

        Should be:
        - subscriptions.company_name with unique=False (multiple subscriptions per company)

        Returns:
            bool: True if fixed successfully
        """
        print("\n" + "="*80)
        print("STEP 2: FIX UNIQUE CONSTRAINT ISSUE")
        print("="*80)

        subscriptions_collection = self.db.subscriptions

        # Check if the problematic index exists
        indexes = await subscriptions_collection.index_information()

        if "company_name_unique" in indexes:
            print("⚠️  Found incorrect unique constraint on subscriptions.company_name")

            if self.dry_run:
                print("   [DRY RUN] Would drop index: company_name_unique")
                print("   [DRY RUN] Would create non-unique index: company_name_idx")
            else:
                try:
                    # Drop the incorrect unique index
                    await subscriptions_collection.drop_index("company_name_unique")
                    print("✅ Dropped incorrect unique index: company_name_unique")

                    # Create non-unique index
                    await subscriptions_collection.create_index(
                        [("company_name", ASCENDING)],
                        name="company_name_idx",
                        unique=False
                    )
                    print("✅ Created non-unique index: company_name_idx")
                except Exception as e:
                    print(f"❌ Error fixing unique constraint: {e}")
                    return False
        else:
            print("✅ No unique constraint issue found (already fixed or doesn't exist)")

        return True

    async def apply_schema_validation(self) -> bool:
        """
        Apply JSON Schema validation to collections.

        Returns:
            bool: True if successful
        """
        print("\n" + "="*80)
        print("STEP 3: APPLY SCHEMA VALIDATION")
        print("="*80)

        # Apply validation to companies
        print("\n📋 Applying schema validation to 'companies' collection...")
        company_validator = self.get_company_schema_validation()

        if self.dry_run:
            print("   [DRY RUN] Would apply validation:")
            print(f"   {company_validator}")
        else:
            try:
                await self.db.command({
                    "collMod": "companies",
                    "validator": company_validator,
                    "validationLevel": "strict",
                    "validationAction": "error"
                })
                print("✅ Applied schema validation to 'companies'")
            except OperationFailure as e:
                if "collection validation failed" in str(e).lower():
                    print(f"❌ Validation failed - existing data violates schema: {e}")
                    return False
                else:
                    print(f"❌ Error applying validation to companies: {e}")
                    return False

        # Apply validation to subscriptions
        print("\n📋 Applying schema validation to 'subscriptions' collection...")
        subscription_validator = self.get_subscription_schema_validation()

        if self.dry_run:
            print("   [DRY RUN] Would apply validation:")
            print(f"   {subscription_validator}")
        else:
            try:
                await self.db.command({
                    "collMod": "subscriptions",
                    "validator": subscription_validator,
                    "validationLevel": "strict",
                    "validationAction": "error"
                })
                print("✅ Applied schema validation to 'subscriptions'")
            except OperationFailure as e:
                if "collection validation failed" in str(e).lower():
                    print(f"❌ Validation failed - existing data violates schema: {e}")
                    return False
                else:
                    print(f"❌ Error applying validation to subscriptions: {e}")
                    return False

        return True

    async def create_indexes(self) -> bool:
        """
        Create or update indexes on collections.

        Returns:
            bool: True if successful
        """
        print("\n" + "="*80)
        print("STEP 4: CREATE/UPDATE INDEXES")
        print("="*80)

        # Companies indexes
        print("\n📊 Creating indexes for 'companies' collection...")
        company_indexes = self.get_company_indexes()

        if self.dry_run:
            print("   [DRY RUN] Would create/update indexes:")
            for idx in company_indexes:
                print(f"   - {idx.document['name']}: {idx.document['key']}")
        else:
            try:
                existing_indexes = await self.db.companies.index_information()
                for idx in company_indexes:
                    idx_name = idx.document['name']
                    if idx_name in existing_indexes:
                        print(f"   ℹ️  Index already exists: {idx_name}")
                    else:
                        await self.db.companies.create_indexes([idx])
                        print(f"   ✅ Created index: {idx_name}")
            except Exception as e:
                print(f"❌ Error creating companies indexes: {e}")
                return False

        # Subscriptions indexes
        print("\n📊 Creating indexes for 'subscriptions' collection...")
        subscription_indexes = self.get_subscription_indexes()

        if self.dry_run:
            print("   [DRY RUN] Would create/update indexes:")
            for idx in subscription_indexes:
                print(f"   - {idx.document['name']}: {idx.document['key']}")
        else:
            try:
                existing_indexes = await self.db.subscriptions.index_information()
                for idx in subscription_indexes:
                    idx_name = idx.document['name']
                    if idx_name in existing_indexes:
                        print(f"   ℹ️  Index already exists: {idx_name}")
                    else:
                        await self.db.subscriptions.create_indexes([idx])
                        print(f"   ✅ Created index: {idx_name}")
            except Exception as e:
                print(f"❌ Error creating subscriptions indexes: {e}")
                return False

        return True

    async def run_migration(self) -> bool:
        """
        Execute the full migration process.

        Steps:
        1. Verify data integrity
        2. Fix unique constraint issue
        3. Apply schema validation
        4. Create/update indexes

        Returns:
            bool: True if migration successful
        """
        print("\n" + "="*80)
        print("MONGODB REFERENTIAL INTEGRITY MIGRATION")
        print("="*80)
        print(f"Database: {self.database_name}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'APPLY CHANGES'}")
        print(f"Time: {datetime.now().isoformat()}")
        print("="*80)

        # Step 1: Verify data integrity
        if not await self.verify_data_integrity():
            print("\n❌ Migration aborted - data integrity issues found")
            print("   Fix data integrity issues first, then re-run migration")
            return False

        # Confirmation prompt (unless force flag set)
        if not self.dry_run and not self.force:
            print("\n⚠️  About to apply database changes:")
            print("   - Fix unique constraint on subscriptions.company_name")
            print("   - Add JSON Schema validation to companies and subscriptions")
            print("   - Create/update indexes")
            print("\nThis operation is SAFE (no data deletion), but will:")
            print("   - Prevent invalid data from being inserted")
            print("   - May impact write performance slightly")

            response = input("\nProceed with migration? [y/N]: ")
            if response.lower() != 'y':
                print("❌ Migration cancelled by user")
                return False

        # Step 2: Fix unique constraint
        if not await self.fix_unique_constraint_issue():
            print("\n❌ Migration failed at unique constraint fix step")
            return False

        # Step 3: Apply schema validation
        if not await self.apply_schema_validation():
            print("\n❌ Migration failed at schema validation step")
            return False

        # Step 4: Create indexes
        if not await self.create_indexes():
            print("\n❌ Migration failed at index creation step")
            return False

        # Success
        print("\n" + "="*80)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY")
        print("="*80)

        if self.dry_run:
            print("\nℹ️  This was a DRY RUN - no changes were applied")
            print("   Run without --dry-run to apply changes")
        else:
            print("\nNext steps:")
            print("   1. Run verification script to ensure integrity:")
            print("      python scripts/verify_data_integrity.py")
            print("   2. Test application functionality")
            print("   3. Monitor logs for validation errors")

        return True


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add referential integrity to MongoDB collections",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (recommended first)
  python scripts/add_referential_integrity.py --dry-run

  # Apply changes
  python scripts/add_referential_integrity.py

  # Apply to test database
  python scripts/add_referential_integrity.py --database translation_test

  # Force apply (skip confirmations)
  python scripts/add_referential_integrity.py --force
        """
    )

    parser.add_argument(
        "--database",
        default="translation",
        help="Database name (default: translation)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without applying changes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    # Run migration
    migration = ReferentialIntegrityMigration(
        database_name=args.database,
        dry_run=args.dry_run,
        force=args.force
    )

    try:
        await migration.connect()
        success = await migration.run_migration()
        await migration.disconnect()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        await migration.disconnect()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        await migration.disconnect()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
