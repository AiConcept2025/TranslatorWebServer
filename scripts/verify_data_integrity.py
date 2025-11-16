#!/usr/bin/env python3
"""
Verify Data Integrity Between Companies and Subscriptions

This script checks referential integrity and reports any violations:
1. Orphaned subscriptions (company_name references non-existent company)
2. Missing companies referenced by subscriptions
3. Schema validation violations

Usage:
    # Check integrity only
    python scripts/verify_data_integrity.py

    # Check and fix issues
    python scripts/verify_data_integrity.py --fix

    # Check specific database
    python scripts/verify_data_integrity.py --database translation_test

    # Verbose output
    python scripts/verify_data_integrity.py --verbose

    # Export report to JSON
    python scripts/verify_data_integrity.py --export report.json

SAFETY:
- Read-only by default
- --fix flag only ADDS missing companies (never deletes subscriptions)
- Never modifies existing data
"""

import asyncio
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING
import os


class DataIntegrityVerifier:
    """Verifies and optionally fixes data integrity issues."""

    def __init__(
        self,
        database_name: str = "translation",
        fix: bool = False,
        verbose: bool = False
    ):
        self.database_name = database_name
        self.fix = fix
        self.verbose = verbose
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

        # Results storage
        self.orphaned_subscriptions: List[Dict] = []
        self.missing_companies: Set[str] = set()
        self.total_subscriptions: int = 0
        self.total_companies: int = 0
        self.validation_errors: List[Dict] = []

    async def connect(self):
        """Connect to MongoDB."""
        mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[self.database_name]

        # Test connection
        try:
            await self.client.admin.command('ping')
            if self.verbose:
                print(f"✅ Connected to MongoDB: {self.database_name}")
        except Exception as e:
            print(f"❌ Failed to connect to MongoDB: {e}")
            raise

    async def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            if self.verbose:
                print("✅ Disconnected from MongoDB")

    async def check_referential_integrity(self) -> bool:
        """
        Check referential integrity between companies and subscriptions.

        Returns:
            bool: True if integrity is valid, False if violations found
        """
        print("\n" + "="*80)
        print("REFERENTIAL INTEGRITY CHECK")
        print("="*80)

        companies_collection = self.db.companies
        subscriptions_collection = self.db.subscriptions

        # Count total records
        self.total_companies = await companies_collection.count_documents({})
        self.total_subscriptions = await subscriptions_collection.count_documents({})

        print(f"📊 Total companies: {self.total_companies}")
        print(f"📊 Total subscriptions: {self.total_subscriptions}")

        # Get all company names from companies collection
        existing_companies = set(await companies_collection.distinct("company_name"))
        if self.verbose:
            print(f"\n📋 Companies in database:")
            for company in sorted(existing_companies):
                print(f"   - {company}")

        # Get all unique company names referenced in subscriptions
        subscription_companies = set(await subscriptions_collection.distinct("company_name"))
        if self.verbose:
            print(f"\n📋 Companies referenced by subscriptions:")
            for company in sorted(subscription_companies):
                print(f"   - {company}")

        # Find missing companies
        self.missing_companies = subscription_companies - existing_companies

        if self.missing_companies:
            print(f"\n⚠️  Found {len(self.missing_companies)} missing companies:")

            for company in sorted(self.missing_companies):
                # Get all orphaned subscriptions for this company
                orphaned = []
                async for sub in subscriptions_collection.find({"company_name": company}):
                    orphaned.append(sub)
                    self.orphaned_subscriptions.append(sub)

                print(f"\n   Company: '{company}'")
                print(f"   Orphaned subscriptions: {len(orphaned)}")

                if self.verbose:
                    for sub in orphaned:
                        print(f"      - Subscription ID: {sub['_id']}")
                        print(f"        Status: {sub.get('status', 'N/A')}")
                        print(f"        Start: {sub.get('start_date', 'N/A')}")
                        print(f"        Units: {sub.get('units_per_subscription', 'N/A')}")

            print(f"\n❌ Referential integrity check FAILED")
            print(f"   Total orphaned subscriptions: {len(self.orphaned_subscriptions)}")
            return False

        print("\n✅ Referential integrity check PASSED")
        print("   All subscriptions reference existing companies")
        return True

    async def check_schema_validation(self) -> bool:
        """
        Check if schema validation is enabled and working.

        Returns:
            bool: True if validation is properly configured
        """
        print("\n" + "="*80)
        print("SCHEMA VALIDATION CHECK")
        print("="*80)

        # Check companies collection validation
        print("\n📋 Checking 'companies' collection validation...")
        try:
            companies_info = await self.db.command({"listCollections": 1, "filter": {"name": "companies"}})
            companies_config = list(companies_info.get("cursor", {}).get("firstBatch", []))

            if companies_config and "options" in companies_config[0]:
                validator = companies_config[0]["options"].get("validator")
                if validator:
                    print("✅ Schema validation enabled for 'companies'")
                    if self.verbose:
                        print(f"   Validator: {json.dumps(validator, indent=2)}")
                else:
                    print("⚠️  No schema validation found for 'companies'")
                    self.validation_errors.append({
                        "collection": "companies",
                        "issue": "No schema validation configured"
                    })
            else:
                print("⚠️  Could not retrieve validation config for 'companies'")
        except Exception as e:
            print(f"❌ Error checking companies validation: {e}")
            self.validation_errors.append({
                "collection": "companies",
                "issue": f"Error checking validation: {e}"
            })

        # Check subscriptions collection validation
        print("\n📋 Checking 'subscriptions' collection validation...")
        try:
            subscriptions_info = await self.db.command({"listCollections": 1, "filter": {"name": "subscriptions"}})
            subscriptions_config = list(subscriptions_info.get("cursor", {}).get("firstBatch", []))

            if subscriptions_config and "options" in subscriptions_config[0]:
                validator = subscriptions_config[0]["options"].get("validator")
                if validator:
                    print("✅ Schema validation enabled for 'subscriptions'")
                    if self.verbose:
                        print(f"   Validator: {json.dumps(validator, indent=2)}")
                else:
                    print("⚠️  No schema validation found for 'subscriptions'")
                    self.validation_errors.append({
                        "collection": "subscriptions",
                        "issue": "No schema validation configured"
                    })
            else:
                print("⚠️  Could not retrieve validation config for 'subscriptions'")
        except Exception as e:
            print(f"❌ Error checking subscriptions validation: {e}")
            self.validation_errors.append({
                "collection": "subscriptions",
                "issue": f"Error checking validation: {e}"
            })

        return len(self.validation_errors) == 0

    async def check_indexes(self) -> bool:
        """
        Check if required indexes exist and are properly configured.

        Returns:
            bool: True if all indexes are correct
        """
        print("\n" + "="*80)
        print("INDEX VERIFICATION")
        print("="*80)

        issues_found = False

        # Check companies indexes
        print("\n📊 Checking 'companies' collection indexes...")
        companies_indexes = await self.db.companies.index_information()

        required_company_indexes = {
            "company_name_unique": {
                "key": [("company_name", ASCENDING)],
                "unique": True
            }
        }

        for idx_name, idx_spec in required_company_indexes.items():
            if idx_name in companies_indexes:
                actual = companies_indexes[idx_name]
                is_unique = actual.get("unique", False)

                if idx_spec["unique"] != is_unique:
                    print(f"⚠️  Index '{idx_name}': unique={is_unique}, expected={idx_spec['unique']}")
                    issues_found = True
                else:
                    print(f"✅ Index '{idx_name}': properly configured")
            else:
                print(f"❌ Missing required index: '{idx_name}'")
                issues_found = True

        # Check subscriptions indexes
        print("\n📊 Checking 'subscriptions' collection indexes...")
        subscriptions_indexes = await self.db.subscriptions.index_information()

        required_subscription_indexes = {
            "company_name_idx": {
                "key": [("company_name", ASCENDING)],
                "unique": False  # Must NOT be unique
            }
        }

        # Check for problematic unique index
        if "company_name_unique" in subscriptions_indexes:
            print("❌ CRITICAL: Found incorrect unique index 'company_name_unique'")
            print("   This prevents multiple subscriptions per company!")
            print("   Fix: Run migration script to drop and recreate as non-unique")
            issues_found = True

        for idx_name, idx_spec in required_subscription_indexes.items():
            if idx_name in subscriptions_indexes:
                actual = subscriptions_indexes[idx_name]
                is_unique = actual.get("unique", False)

                if idx_spec["unique"] != is_unique:
                    print(f"⚠️  Index '{idx_name}': unique={is_unique}, expected={idx_spec['unique']}")
                    issues_found = True
                else:
                    print(f"✅ Index '{idx_name}': properly configured")
            else:
                print(f"⚠️  Missing recommended index: '{idx_name}'")
                issues_found = True

        if self.verbose:
            print("\n📋 All indexes on 'companies':")
            for idx_name, idx_info in companies_indexes.items():
                print(f"   - {idx_name}: {idx_info}")

            print("\n📋 All indexes on 'subscriptions':")
            for idx_name, idx_info in subscriptions_indexes.items():
                print(f"   - {idx_name}: {idx_info}")

        return not issues_found

    async def fix_missing_companies(self) -> bool:
        """
        Create missing companies referenced by orphaned subscriptions.

        Returns:
            bool: True if fixes applied successfully
        """
        if not self.missing_companies:
            print("\nℹ️  No missing companies to fix")
            return True

        print("\n" + "="*80)
        print("FIXING MISSING COMPANIES")
        print("="*80)

        companies_collection = self.db.companies

        for company_name in sorted(self.missing_companies):
            print(f"\n📝 Creating company: '{company_name}'")

            try:
                # Create company document
                now = datetime.utcnow()
                company_doc = {
                    "company_name": company_name,
                    "created_at": now,
                    "updated_at": now
                }

                result = await companies_collection.insert_one(company_doc)
                print(f"✅ Created company with ID: {result.inserted_id}")

            except Exception as e:
                print(f"❌ Error creating company '{company_name}': {e}")
                return False

        print(f"\n✅ Successfully created {len(self.missing_companies)} companies")
        return True

    async def generate_report(self) -> Dict:
        """
        Generate integrity report.

        Returns:
            dict: Report with all findings
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "database": self.database_name,
            "summary": {
                "total_companies": self.total_companies,
                "total_subscriptions": self.total_subscriptions,
                "missing_companies": len(self.missing_companies),
                "orphaned_subscriptions": len(self.orphaned_subscriptions),
                "validation_errors": len(self.validation_errors)
            },
            "missing_companies": sorted(list(self.missing_companies)),
            "orphaned_subscriptions": [
                {
                    "id": str(sub["_id"]),
                    "company_name": sub.get("company_name"),
                    "status": sub.get("status"),
                    "start_date": sub.get("start_date").isoformat() if sub.get("start_date") else None,
                    "units": sub.get("units_per_subscription")
                }
                for sub in self.orphaned_subscriptions
            ],
            "validation_errors": self.validation_errors,
            "passed": (
                len(self.missing_companies) == 0 and
                len(self.orphaned_subscriptions) == 0 and
                len(self.validation_errors) == 0
            )
        }

    async def run_verification(self) -> Tuple[bool, Dict]:
        """
        Execute full verification process.

        Returns:
            Tuple[bool, dict]: (passed, report)
        """
        print("\n" + "="*80)
        print("MONGODB DATA INTEGRITY VERIFICATION")
        print("="*80)
        print(f"Database: {self.database_name}")
        print(f"Mode: {'FIX ISSUES' if self.fix else 'CHECK ONLY'}")
        print(f"Time: {datetime.now().isoformat()}")
        print("="*80)

        # Check referential integrity
        referential_ok = await self.check_referential_integrity()

        # Check schema validation
        validation_ok = await self.check_schema_validation()

        # Check indexes
        indexes_ok = await self.check_indexes()

        # Fix issues if requested
        if self.fix and not referential_ok:
            print("\n⚠️  Attempting to fix missing companies...")
            if await self.fix_missing_companies():
                print("✅ Fixes applied successfully")
                # Re-check integrity
                referential_ok = await self.check_referential_integrity()
            else:
                print("❌ Failed to apply fixes")

        # Generate report
        report = await self.generate_report()

        # Print summary
        print("\n" + "="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        print(f"Total companies: {report['summary']['total_companies']}")
        print(f"Total subscriptions: {report['summary']['total_subscriptions']}")
        print(f"Missing companies: {report['summary']['missing_companies']}")
        print(f"Orphaned subscriptions: {report['summary']['orphaned_subscriptions']}")
        print(f"Validation errors: {report['summary']['validation_errors']}")

        passed = report['passed']

        if passed:
            print("\n✅ ALL CHECKS PASSED")
            print("   Data integrity is valid")
        else:
            print("\n❌ ISSUES FOUND")
            if not referential_ok:
                print("   - Referential integrity violations")
            if not validation_ok:
                print("   - Schema validation issues")
            if not indexes_ok:
                print("   - Index configuration issues")

            if not self.fix:
                print("\nℹ️  Run with --fix flag to automatically create missing companies")
                print("   python scripts/verify_data_integrity.py --fix")

        return passed, report


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify data integrity between companies and subscriptions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check integrity only
  python scripts/verify_data_integrity.py

  # Check and fix issues
  python scripts/verify_data_integrity.py --fix

  # Check specific database
  python scripts/verify_data_integrity.py --database translation_test

  # Verbose output
  python scripts/verify_data_integrity.py --verbose

  # Export report to JSON
  python scripts/verify_data_integrity.py --export report.json
        """
    )

    parser.add_argument(
        "--database",
        default="translation",
        help="Database name (default: translation)"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix issues by creating missing companies"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output with detailed information"
    )
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="Export report to JSON file"
    )

    args = parser.parse_args()

    # Run verification
    verifier = DataIntegrityVerifier(
        database_name=args.database,
        fix=args.fix,
        verbose=args.verbose
    )

    try:
        await verifier.connect()
        passed, report = await verifier.run_verification()
        await verifier.disconnect()

        # Export report if requested
        if args.export:
            with open(args.export, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📄 Report exported to: {args.export}")

        sys.exit(0 if passed else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Verification interrupted by user")
        await verifier.disconnect()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        await verifier.disconnect()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
