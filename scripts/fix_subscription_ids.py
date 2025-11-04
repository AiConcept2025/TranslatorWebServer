"""
Fix subscription_id references in translation_transactions to match actual subscriptions.
"""

import asyncio
import sys
from pathlib import Path
from bson import ObjectId

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def fix_subscription_ids():
    """Update translation_transactions to use correct subscription_ids."""
    print("=" * 60)
    print("🔧 Fixing Subscription IDs in Translation Transactions")
    print("=" * 60)

    try:
        # Connect to database
        print("\n🔌 Connecting to MongoDB...")
        await database.connect()
        print("✅ Connected to database")

        # Get all subscriptions
        print("\n📊 Fetching all subscriptions...")
        subscriptions = await database.subscriptions.find({}, {"company_name": 1, "_id": 1}).to_list(length=None)

        # Create company_name -> subscription_id mapping
        company_to_sub_id = {sub['company_name']: str(sub['_id']) for sub in subscriptions}

        print(f"✅ Found {len(company_to_sub_id)} subscriptions:")
        for company, sub_id in company_to_sub_id.items():
            print(f"  - {company}: {sub_id}")

        # Update translation_transactions
        print("\n🔧 Updating translation_transactions...")
        update_count = 0

        for company_name, correct_sub_id in company_to_sub_id.items():
            result = await database.translation_transactions.update_many(
                {"company_name": company_name},
                {"$set": {"subscription_id": correct_sub_id}}
            )

            if result.modified_count > 0:
                print(f"  ✅ Updated {result.modified_count} transactions for {company_name} to use {correct_sub_id}")
                update_count += result.modified_count
            else:
                print(f"  ℹ️  No updates needed for {company_name}")

        print(f"\n✅ Total transactions updated: {update_count}")

        # Verify final state
        print("\n🔍 Verifying updates...")
        transactions = await database.translation_transactions.find({}, {"company_name": 1, "subscription_id": 1}).to_list(length=None)

        print(f"\n📋 Transaction -> Subscription mapping:")
        for txn in transactions:
            company = txn.get('company_name', 'N/A')
            sub_id = txn.get('subscription_id', 'N/A')
            print(f"  - {company}: {sub_id}")

        print("\n" + "=" * 60)
        print("✅ Fix complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(fix_subscription_ids())
