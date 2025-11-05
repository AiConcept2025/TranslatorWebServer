"""
Verify subscriptions exist for translation transactions and create missing ones.

This script:
1. Checks all translation_transactions for unique company_name and subscription_id combinations
2. Verifies if corresponding subscriptions exist in the subscriptions collection
3. Creates missing subscription records with proper company_name and _id
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
from bson import ObjectId

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def verify_and_create_subscriptions():
    """Verify and create subscriptions for translation transactions."""
    print("=" * 60)
    print("🔍 Verifying Subscriptions for Translation Transactions")
    print("=" * 60)

    try:
        # Connect to database
        print("\n🔌 Connecting to MongoDB...")
        await database.connect()
        print("✅ Connected to database")

        # Step 1: Get all unique company_name + subscription_id combinations from translation_transactions
        print("\n📊 Fetching translation transactions...")
        transactions = await database.translation_transactions.find({}).to_list(length=None)
        print(f"✅ Found {len(transactions)} translation transactions")

        # Extract unique combinations
        subscription_refs = set()
        for txn in transactions:
            company_name = txn.get('company_name')
            subscription_id = txn.get('subscription_id')
            if company_name and subscription_id:
                subscription_refs.add((company_name, subscription_id))

        print(f"\n📋 Found {len(subscription_refs)} unique company/subscription combinations:")
        for company_name, sub_id in subscription_refs:
            print(f"  - {company_name}: {sub_id}")

        # Step 2: Check which subscriptions exist
        print("\n🔍 Checking existing subscriptions...")
        existing_count = 0
        missing_subscriptions = []

        for company_name, sub_id in subscription_refs:
            # Check if subscription exists
            subscription = await database.subscriptions.find_one({"_id": ObjectId(sub_id)})

            if subscription:
                print(f"  ✅ Found subscription for {company_name} ({sub_id})")
                existing_count += 1
            else:
                print(f"  ❌ Missing subscription for {company_name} ({sub_id})")
                missing_subscriptions.append((company_name, sub_id))

        print(f"\n📊 Summary: {existing_count} exist, {len(missing_subscriptions)} missing")

        # Step 3: Create missing subscriptions
        if missing_subscriptions:
            print(f"\n🔨 Creating {len(missing_subscriptions)} missing subscriptions...")

            for company_name, sub_id in missing_subscriptions:
                # Create subscription document
                now = datetime.now(timezone.utc)
                subscription_doc = {
                    "_id": ObjectId(sub_id),
                    "company_name": company_name,
                    "subscription_unit": "page",
                    "units_per_subscription": 1000,
                    "price_per_unit": 0.01,
                    "promotional_units": 0,
                    "discount": 0,
                    "subscription_price": 10.0,
                    "start_date": now,
                    "end_date": datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
                    "status": "active",
                    "usage_periods": [
                        {
                            "period_start": now,
                            "period_end": datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
                            "units_allocated": 1000,
                            "units_used": 0,
                            "units_remaining": 1000,
                            "last_updated": now,
                            "promotional_units": 0
                        }
                    ],
                    "created_at": now,
                    "updated_at": now
                }

                try:
                    await database.subscriptions.insert_one(subscription_doc)
                    print(f"  ✅ Created subscription for {company_name} ({sub_id})")
                except Exception as e:
                    print(f"  ❌ Failed to create subscription for {company_name}: {e}")

        # Step 4: Verify final state
        print("\n🔍 Final verification...")
        final_count = await database.subscriptions.count_documents({})
        print(f"✅ Total subscriptions in database: {final_count}")

        # List all subscriptions
        all_subs = await database.subscriptions.find({}, {"company_name": 1, "_id": 1, "status": 1}).to_list(length=None)
        print(f"\n📋 All subscriptions:")
        for sub in all_subs:
            print(f"  - {sub['company_name']}: {sub['_id']} (status: {sub['status']})")

        print("\n" + "=" * 60)
        print("✅ Verification and creation complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(verify_and_create_subscriptions())
