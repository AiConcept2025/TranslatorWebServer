"""
Add usage period to Iris Trading subscription.

This script adds a usage period to the existing subscription for Iris Trading company.
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import database


async def add_usage_period():
    """Add usage period to Iris Trading subscription."""
    # Connect to database
    await database.connect()
    db = database.db
    subscriptions = db.subscriptions

    # Find Iris Trading subscription
    subscription = await subscriptions.find_one({"company_name": "Iris Trading"})

    if not subscription:
        print("❌ ERROR: No subscription found for 'Iris Trading'")
        return False

    print(f"✅ Found subscription: {subscription['_id']}")
    print(f"   Company: {subscription['company_name']}")
    print(f"   Status: {subscription.get('status', 'N/A')}")
    print(f"   Current usage_periods count: {len(subscription.get('usage_periods', []))}")

    # Check if usage period already exists
    if subscription.get('usage_periods'):
        print("⚠️  WARNING: Subscription already has usage periods:")
        for idx, period in enumerate(subscription['usage_periods']):
            print(f"   Period {idx + 1}:")
            print(f"      Start: {period.get('period_start')}")
            print(f"      End: {period.get('period_end')}")
            print(f"      Allocated: {period.get('units_allocated')}")
            print(f"      Used: {period.get('units_used')}")
            print(f"      Remaining: {period.get('units_remaining')}")

        response = input("\n Do you want to ADD ANOTHER period? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Aborted - no changes made")
            return False

    # Create usage period
    now = datetime.now(timezone.utc)

    # Current month period: Dec 1 - Dec 31, 2025
    period_start = datetime(2025, 12, 1, 0, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    usage_period = {
        "period_start": period_start,
        "period_end": period_end,
        "units_allocated": 1000,  # Full allocation for the month
        "units_used": 998,  # Already used from previous tests
        "units_remaining": 2,  # 1000 - 998
        "promotional_units": 0,
        "last_updated": now
    }

    print("\n📋 Usage period to be added:")
    print(f"   Period: {period_start.isoformat()} to {period_end.isoformat()}")
    print(f"   Units Allocated: {usage_period['units_allocated']}")
    print(f"   Units Used: {usage_period['units_used']}")
    print(f"   Units Remaining: {usage_period['units_remaining']}")
    print(f"   Promotional Units: {usage_period['promotional_units']}")

    confirm = input("\n✋ Confirm update? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Aborted - no changes made")
        return False

    # Add usage period to subscription
    result = await subscriptions.update_one(
        {"_id": subscription["_id"]},
        {"$push": {"usage_periods": usage_period}}
    )

    if result.modified_count == 1:
        print("\n✅ SUCCESS: Usage period added to subscription")

        # Verify the update
        updated_subscription = await subscriptions.find_one({"_id": subscription["_id"]})
        print(f"\n📊 Updated subscription:")
        print(f"   Total usage_periods: {len(updated_subscription.get('usage_periods', []))}")

        for idx, period in enumerate(updated_subscription['usage_periods']):
            print(f"\n   Period {idx + 1}:")
            print(f"      Start: {period['period_start']}")
            print(f"      End: {period['period_end']}")
            print(f"      Allocated: {period['units_allocated']}")
            print(f"      Used: {period['units_used']}")
            print(f"      Remaining: {period['units_remaining']}")
            print(f"      Promotional: {period['promotional_units']}")

        return True
    else:
        print("❌ ERROR: Failed to update subscription")
        return False


if __name__ == "__main__":
    print("🔧 Adding usage period to Iris Trading subscription...\n")
    success = asyncio.run(add_usage_period())
    sys.exit(0 if success else 1)
