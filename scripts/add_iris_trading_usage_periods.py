#!/usr/bin/env python3
"""
Add 12 monthly usage periods for Iris Trading subscription.

This script creates usage periods for subscription ID: 692f27dcbccdb965bbf42fcc
Annual subscription: 1000 pages + 100 promotional units
Period: January 1 - December 31, 2025

Business Logic:
- Each period has access to FULL pool (1000 pages)
- Promotional units distributed across all 12 months (8-9 per month)
- Users can use units from any month's allocation
- Monthly tracking for reporting/analytics purposes

Usage:
    python3 scripts/add_iris_trading_usage_periods.py --confirm
"""

import asyncio
import argparse
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import calendar


async def create_usage_periods(auto_confirm: bool = False):
    """Create 12 monthly usage periods for Iris Trading subscription."""

    # Connect to MongoDB
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['translation']

    subscription_id = ObjectId("692f27dcbccdb965bbf42fcc")

    # Verify subscription exists
    subscription = await db.subscriptions.find_one({"_id": subscription_id})
    if not subscription:
        print(f"❌ Subscription {subscription_id} not found")
        client.close()
        return

    print(f"✅ Found subscription for: {subscription['company_name']}")
    print(f"   Units per subscription: {subscription['units_per_subscription']}")
    print(f"   Promotional units: {subscription['promotional_units']}")
    print(f"   Start date: {subscription['start_date']}")
    print(f"   End date: {subscription['end_date']}")

    # Annual allocation
    total_units = subscription['units_per_subscription']  # 1000
    total_promotional = subscription['promotional_units']  # 100

    # Calculate promotional units per month (distribute evenly)
    promo_per_month_base = total_promotional // 12  # 8
    promo_remainder = total_promotional % 12  # 4 (first 4 months get 9, rest get 8)

    print(f"\n📊 Allocation Strategy:")
    print(f"   - Each period: {total_units} pages (full pool access)")
    print(f"   - Promotional: {promo_per_month_base}-{promo_per_month_base + 1} per month")
    print(f"   - First {promo_remainder} months get extra promotional unit")

    # Create 12 monthly periods for 2025
    usage_periods = []
    year = 2025

    for month_num in range(1, 13):
        # Calculate period boundaries
        period_start = datetime(year, month_num, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Last day of month
        last_day = calendar.monthrange(year, month_num)[1]
        period_end = datetime(year, month_num, last_day, 23, 59, 59, 999999, tzinfo=timezone.utc)

        # Promotional units (first N months get +1)
        promotional_units = promo_per_month_base + (1 if month_num <= promo_remainder else 0)

        # Create period
        period = {
            "period_start": period_start,
            "period_end": period_end,
            "units_allocated": total_units,  # Full pool access
            "units_used": 0,
            "units_remaining": total_units + promotional_units,  # Initial = allocated + promotional
            "promotional_units": promotional_units,
            "last_updated": datetime.now(timezone.utc),
            "period_number": month_num
        }

        usage_periods.append(period)

        # Print period details
        month_name = calendar.month_name[month_num]
        print(f"\n   {month_num:2d}. {month_name:10s} {period_start.date()} → {period_end.date()}")
        print(f"       Units: {period['units_allocated']:4d} | Promo: {promotional_units:2d} | Total: {period['units_remaining']:4d}")

    # Confirmation prompt
    print(f"\n⚠️  About to insert {len(usage_periods)} usage periods")
    print(f"   Subscription ID: {subscription_id}")
    print(f"   Company: {subscription['company_name']}")

    if not auto_confirm:
        confirm = input("\n   Proceed with insert? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("❌ Insert cancelled")
            client.close()
            return
    else:
        print("\n   Auto-confirm enabled, proceeding with insert...")

    # Update subscription with usage periods
    result = await db.subscriptions.update_one(
        {"_id": subscription_id},
        {
            "$set": {
                "usage_periods": usage_periods,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    if result.modified_count == 1:
        print(f"\n✅ Successfully inserted {len(usage_periods)} usage periods")

        # Verify
        updated_sub = await db.subscriptions.find_one({"_id": subscription_id})
        print(f"\n📋 Verification:")
        print(f"   Usage periods count: {len(updated_sub['usage_periods'])}")
        print(f"   First period start: {updated_sub['usage_periods'][0]['period_start']}")
        print(f"   Last period end: {updated_sub['usage_periods'][-1]['period_end']}")

        # Calculate totals
        total_promo_distributed = sum(p['promotional_units'] for p in updated_sub['usage_periods'])
        print(f"   Total promotional units distributed: {total_promo_distributed}")
        print(f"   Expected: {total_promotional}")

        if total_promo_distributed == total_promotional:
            print("\n✅ Promotional units distribution verified!")
        else:
            print(f"\n⚠️  Warning: Promotional units mismatch!")
    else:
        print(f"\n❌ Update failed")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Add 12 monthly usage periods for Iris Trading subscription"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Auto-confirm insert without prompting"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  Add Usage Periods for Iris Trading Subscription")
    print("=" * 70)
    asyncio.run(create_usage_periods(auto_confirm=args.confirm))
