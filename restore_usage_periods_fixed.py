#!/usr/bin/env python3
"""
USAGE PERIODS RESTORATION SCRIPT
=================================

This script restores the usage_periods field for all subscriptions that have empty or missing data.

WHAT IT DOES:
1. Connects to MongoDB
2. Finds all subscriptions with empty/missing usage_periods
3. Regenerates usage_periods based on subscription start_date and end_date
4. Creates monthly periods with proper dummy data following the correct schema

SCHEMA (from app/mongodb_models.py UsagePeriod):
- period_start: datetime
- period_end: datetime
- units_allocated: int
- units_used: int = 0
- units_remaining: int
- promotional_units: int = 0
- last_updated: datetime

SAFETY FEATURES:
- Dry-run mode by default (use --apply to actually update)
- Only processes subscriptions with empty usage_periods
- Preserves existing data
- Detailed logging of all operations
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/translation")

async def get_database():
    """Connect to MongoDB and return database."""
    client = AsyncIOMotorClient(MONGODB_URI)
    db_name = MONGODB_URI.split("/")[-1] if "/" in MONGODB_URI else "translation"
    return client[db_name]

def generate_usage_periods(subscription: dict) -> list:
    """
    Generate monthly usage periods for a subscription.

    Args:
        subscription: Subscription document from MongoDB

    Returns:
        List of usage period dictionaries
    """
    periods = []

    start_date = subscription.get("start_date")
    end_date = subscription.get("end_date")
    units_per_subscription = subscription.get("units_per_subscription", 0)
    promotional_units = subscription.get("promotional_units", 0)

    if not start_date or not end_date:
        print(f"  ⚠️  Subscription {subscription.get('_id')} missing start_date or end_date")
        return []

    # Ensure datetime objects
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

    # Make timezone-aware if needed
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    # Generate monthly periods
    current_period_start = start_date
    period_number = 0

    while current_period_start < end_date:
        period_number += 1

        # Calculate period end (end of month or subscription end_date, whichever is earlier)
        next_month = current_period_start + relativedelta(months=1)
        period_end = min(next_month, end_date)

        # First period gets promotional units
        period_promotional_units = promotional_units if period_number == 1 else 0

        # Calculate units_remaining
        units_remaining = units_per_subscription + period_promotional_units

        period = {
            "period_start": current_period_start,
            "period_end": period_end,
            "units_allocated": units_per_subscription,
            "units_used": 0,  # Dummy data - no historical usage
            "units_remaining": units_remaining,
            "promotional_units": period_promotional_units,
            "last_updated": datetime.now(timezone.utc)
        }

        periods.append(period)

        # Move to next period
        current_period_start = period_end

    return periods

async def restore_usage_periods(dry_run: bool = True):
    """
    Main restoration function.

    Args:
        dry_run: If True, only preview changes without applying them
    """
    print("=" * 80)
    print("USAGE PERIODS RESTORATION SCRIPT")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'APPLY CHANGES'}")
    print(f"MongoDB URI: {MONGODB_URI}")
    print()

    # Connect to database
    db = await get_database()
    subscriptions_collection = db.subscriptions

    # Find subscriptions with empty or missing usage_periods
    query = {
        "$or": [
            {"usage_periods": {"$exists": False}},
            {"usage_periods": []},
            {"usage_periods": None}
        ]
    }

    subscriptions = await subscriptions_collection.find(query).to_list(length=1000)

    print(f"Found {len(subscriptions)} subscriptions with empty/missing usage_periods")
    print()

    if len(subscriptions) == 0:
        print("✅ All subscriptions already have usage_periods. Nothing to restore.")
        return

    # Process each subscription
    updated_count = 0
    error_count = 0

    for sub in subscriptions:
        sub_id = sub.get("_id")
        company_name = sub.get("company_name", "Unknown")

        print(f"📋 Processing Subscription:")
        print(f"   ID: {sub_id}")
        print(f"   Company: {company_name}")
        print(f"   Start: {sub.get('start_date')}")
        print(f"   End: {sub.get('end_date')}")
        print(f"   Units: {sub.get('units_per_subscription')}")
        print(f"   Promotional: {sub.get('promotional_units')}")

        # Generate usage periods
        try:
            usage_periods = generate_usage_periods(sub)

            if not usage_periods:
                print("   ⚠️  Could not generate periods (missing dates)")
                error_count += 1
                print()
                continue

            print(f"   ✅ Generated {len(usage_periods)} periods")

            # Show first and last period
            if usage_periods:
                first = usage_periods[0]
                last = usage_periods[-1]
                print(f"   📅 First period: {first['period_start']} → {first['period_end']}")
                print(f"   📅 Last period: {last['period_start']} → {last['period_end']}")

            # Apply update if not dry run
            if not dry_run:
                result = await subscriptions_collection.update_one(
                    {"_id": sub_id},
                    {
                        "$set": {
                            "usage_periods": usage_periods,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

                if result.modified_count > 0:
                    print("   💾 Updated in database")
                    updated_count += 1
                else:
                    print("   ⚠️  Update failed")
                    error_count += 1
            else:
                print("   🔍 Would update (dry run mode)")
                updated_count += 1

        except Exception as e:
            print(f"   ❌ Error: {e}")
            error_count += 1

        print()

    # Summary
    print("=" * 80)
    print("RESTORATION SUMMARY")
    print("=" * 80)
    print(f"Total subscriptions found: {len(subscriptions)}")
    print(f"Successfully {'updated' if not dry_run else 'would update'}: {updated_count}")
    print(f"Errors: {error_count}")
    print()

    if dry_run:
        print("⚠️  This was a DRY RUN. No changes were made to the database.")
        print("   To apply changes, run with --apply flag:")
        print("   python restore_usage_periods_fixed.py --apply")
    else:
        print("✅ Restoration complete!")

    print("=" * 80)

async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Restore usage_periods for subscriptions")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    args = parser.parse_args()

    dry_run = not args.apply

    await restore_usage_periods(dry_run=dry_run)

if __name__ == "__main__":
    asyncio.run(main())
