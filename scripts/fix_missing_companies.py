"""
Fix Missing Companies in Master Collection

This script adds missing company records (Tech Solutions, Global Corp) to the company
collection to match what exists in the subscriptions and translation_transactions collections.

SAFETY NOTE: This script ONLY ADDS records, does not delete anything.

Root Cause: setup_test_translation_transactions.py and verify_and_create_subscriptions.py
created companies in transaction/subscription data, but populate_test_data.py only created
2 of the 3 companies in the master company collection.

Fix Strategy: Add missing entries to company collection with minimal placeholder data.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database

async def fix_missing_companies():
    """Add missing companies to the company collection."""

    print("\n" + "=" * 80)
    print("FIXING MISSING COMPANIES IN MASTER COLLECTION")
    print("=" * 80)

    try:
        # Connect to database
        print("\n🔌 Connecting to MongoDB...")
        await database.connect()
        print("✅ Connected to database")

        # 1. Get all unique companies from translation_transactions
        print("\n1. Fetching unique companies from translation_transactions...")
        tt_companies = await database.translation_transactions.distinct(
            'company_name',
            {'company_name': {'$ne': None}}
        )
        tt_companies.sort()
        print(f"   Found {len(tt_companies)} companies in translation_transactions:")
        for company in tt_companies:
            print(f"     - {company}")

        # 2. Get all companies from company collection
        print("\n2. Fetching existing companies from company collection...")
        existing_companies = await database.company.find({}).to_list(length=None)
        existing_names = [c.get('company_name') for c in existing_companies]
        existing_names.sort()
        print(f"   Found {len(existing_companies)} companies in company collection:")
        for company in existing_names:
            print(f"     - {company}")

        # 3. Identify missing companies
        print("\n3. Identifying missing companies...")
        existing_set = set(existing_names)
        tt_set = set(tt_companies)

        missing = tt_set - existing_set
        extra = existing_set - tt_set
        overlap = existing_set & tt_set

        print(f"\n   Missing from company collection (exist in transactions):")
        if missing:
            for company in sorted(missing):
                print(f"     - {company}")
        else:
            print("     (none)")

        print(f"\n   Extra in company collection (no transactions):")
        if extra:
            for company in sorted(extra):
                print(f"     - {company}")
        else:
            print("     (none)")

        print(f"\n   Overlap (in both):")
        for company in sorted(overlap):
            print(f"     - {company}")

        # 4. Add missing companies to company collection
        if missing:
            print(f"\n4. Adding {len(missing)} missing companies to company collection...")

            now = datetime.now(timezone.utc)

            for company_name in sorted(missing):
                # Create minimal company record
                company_doc = {
                    "company_name": company_name,
                    "description": f"{company_name} - Auto-created from transaction data",
                    "address": {
                        "address0": "TBD",
                        "address1": "",
                        "postal_code": "TBD",
                        "state": "TBD",
                        "city": "TBD",
                        "country": "USA"
                    },
                    "contact_person": {
                        "name": "Contact Name",
                        "type": "Primary Contact"
                    },
                    "phone_number": [],
                    "company_url": [],
                    "line_of_business": "General",
                    "created_at": now,
                    "updated_at": now
                }

                # Insert the record
                result = await database.company.insert_one(company_doc)
                print(f"   ✅ Added: {company_name} (ID: {result.inserted_id})")
        else:
            print("\n4. ✅ No missing companies found - all companies already in collection!")

        # 5. Final verification
        print("\n5. Final Verification...")
        final_companies = await database.company.find({}).to_list(length=None)
        final_names = [c.get('company_name') for c in final_companies]
        final_names.sort()

        print(f"   Company collection now has {len(final_companies)} companies:")
        for company in final_names:
            print(f"     - {company}")

        # Check if all are accounted for
        final_set = set(final_names)
        still_missing = tt_set - final_set

        if still_missing:
            print(f"\n   ❌ ERROR: Still missing companies: {still_missing}")
            return False
        else:
            print(f"\n   ✅ SUCCESS: All companies from transactions are now in company collection!")

        print("\n" + "=" * 80)
        print("FIX COMPLETE")
        print("=" * 80)

        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main entry point."""
    success = await fix_missing_companies()
    exit(0 if success else 1)

if __name__ == '__main__':
    asyncio.run(main())
