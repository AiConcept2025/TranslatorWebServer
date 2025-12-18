#!/usr/bin/env python3
"""
Script to update all subscriptions with 12 monthly usage periods.

This script:
1. Fetches all subscriptions from the database
2. For each subscription, generates 12 consecutive monthly periods
3. Preserves existing usage data (units_used) for current periods
4. Sets appropriate status for each period (completed/active)
5. Updates the subscription document with the new usage_periods array

Usage:
    python scripts/add_12_monthly_periods.py [--database DATABASE_NAME] [--dry-run]

Options:
    --database    Database name (default: from settings)
    --dry-run     Show what would be updated without making changes
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from calendar import monthrange
from typing import List, Dict, Any
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_month_end(year: int, month: int) -> tuple:
    """Get the last day of a given month."""
    last_day = monthrange(year, month)[1]
    return (year, month, last_day)


def generate_12_monthly_periods(
    start_date: datetime,
    units_per_subscription: int,
    promotional_units: int,
    price_per_unit: float,
    existing_usage: Dict[str, int] = None
) -> List[Dict[str, Any]]:
    """
    Generate 12 consecutive monthly periods starting from the subscription start_date.

    Args:
        start_date: Subscription start date
        units_per_subscription: Units allocated per period
        promotional_units: Promotional units per period
        price_per_unit: Price per unit
        existing_usage: Dict with {period_number: units_used} for preserving existing usage

    Returns:
        List of 12 usage period dictionaries
    """
    usage_periods = []
    now = datetime.now(timezone.utc)

    # Start from the subscription's start_date
    current_year = start_date.year
    current_month = start_date.month

    if existing_usage is None:
        existing_usage = {}

    for period_number in range(1, 13):
        # Calculate period_start (first day of the month)
        period_start = datetime(current_year, current_month, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Calculate period_end (last day of the month at 23:59:59)
        year_end, month_end, last_day = get_month_end(current_year, current_month)
        period_end = datetime(year_end, month_end, last_day, 23, 59, 59, tzinfo=timezone.utc)

        # Determine status based on period_end relative to now
        if period_end < now:
            status = "completed"
        else:
            status = "active"

        # Get existing units_used for this period, default to 0
        units_used = existing_usage.get(period_number, 0)

        # Calculate units_remaining
        units_remaining = units_per_subscription + promotional_units - units_used

        period = {
            "period_number": period_number,
            "period_start": period_start,
            "period_end": period_end,
            "units_allocated": units_per_subscription,
            "promotional_units": promotional_units,
            "units_used": units_used,
            "units_remaining": units_remaining,
            "price_per_unit": price_per_unit,
            "status": status,
            "last_updated": datetime.now(timezone.utc)
        }

        usage_periods.append(period)

        # Move to next month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    return usage_periods


async def update_subscriptions_with_12_periods(database_name: str = None, dry_run: bool = False):
    """
    Update all subscriptions to have 12 monthly usage periods.

    Args:
        database_name: Database name (uses settings.mongodb_database if None)
        dry_run: If True, show what would be updated without making changes
    """
    db_name = database_name or settings.mongodb_database

    logger.info(f"{'='*80}")
    logger.info(f"Updating Subscriptions to 12 Monthly Periods")
    logger.info(f"{'='*80}")
    logger.info(f"Database: {db_name}")
    logger.info(f"Mode: {'DRY RUN (no changes will be made)' if dry_run else 'LIVE (will update database)'}")
    logger.info(f"{'='*80}\n")

    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[db_name]

    try:
        # Get all subscriptions
        subscriptions = await db.subscriptions.find({}).to_list(length=None)
        logger.info(f"Found {len(subscriptions)} subscriptions\n")

        if not subscriptions:
            logger.warning("No subscriptions found in database")
            return

        updated_count = 0
        skipped_count = 0

        for idx, subscription in enumerate(subscriptions, 1):
            sub_id = subscription["_id"]
            company_name = subscription.get("company_name", "Unknown")
            start_date = subscription.get("start_date")
            units_per_subscription = subscription.get("units_per_subscription", 1000)
            promotional_units = subscription.get("promotional_units", 0)
            price_per_unit = subscription.get("price_per_unit", 0.01)
            existing_periods = subscription.get("usage_periods", [])

            logger.info(f"[{idx}/{len(subscriptions)}] Processing: {company_name}")
            logger.info(f"  Subscription ID: {sub_id}")
            logger.info(f"  Start Date: {start_date}")
            logger.info(f"  Units per Period: {units_per_subscription}")
            logger.info(f"  Promotional Units: {promotional_units}")
            logger.info(f"  Current Periods: {len(existing_periods)}")

            # Extract existing usage data (preserve units_used)
            existing_usage = {}
            if existing_periods:
                for period in existing_periods:
                    period_num = period.get("period_number")
                    units_used = period.get("units_used", 0)
                    if period_num is not None and units_used > 0:
                        existing_usage[period_num] = units_used
                        logger.info(f"  Preserving usage: Period {period_num} has {units_used} units used")

            # Generate 12 monthly periods
            new_usage_periods = generate_12_monthly_periods(
                start_date=start_date,
                units_per_subscription=units_per_subscription,
                promotional_units=promotional_units,
                price_per_unit=float(price_per_unit),
                existing_usage=existing_usage
            )

            logger.info(f"  Generated {len(new_usage_periods)} monthly periods")

            # Show summary of periods
            logger.info(f"  Period Summary:")
            for period in new_usage_periods:
                logger.info(
                    f"    Period {period['period_number']}: "
                    f"{period['period_start'].strftime('%Y-%m-%d')} to {period['period_end'].strftime('%Y-%m-%d')} "
                    f"| Allocated: {period['units_allocated']} | Used: {period['units_used']} | "
                    f"Remaining: {period['units_remaining']} | Status: {period['status']}"
                )

            if dry_run:
                logger.info(f"  [DRY RUN] Would update subscription with {len(new_usage_periods)} periods")
            else:
                # Update the subscription
                result = await db.subscriptions.update_one(
                    {"_id": sub_id},
                    {
                        "$set": {
                            "usage_periods": new_usage_periods,
                            "updated_at": datetime.now(timezone.utc)
                        }
                    }
                )

                if result.modified_count > 0:
                    logger.info(f"  ✅ Updated subscription with {len(new_usage_periods)} monthly periods")
                    updated_count += 1
                else:
                    logger.warning(f"  ⚠️  No changes made")
                    skipped_count += 1

            logger.info("")  # Blank line between subscriptions

        # Summary
        logger.info(f"\n{'='*80}")
        logger.info(f"Summary:")
        logger.info(f"{'='*80}")
        logger.info(f"Total Subscriptions: {len(subscriptions)}")

        if dry_run:
            logger.info(f"Mode: DRY RUN - No changes were made")
            logger.info(f"Would Update: {len(subscriptions)} subscriptions")
        else:
            logger.info(f"Updated: {updated_count}")
            logger.info(f"Skipped: {skipped_count}")

        logger.info(f"{'='*80}\n")

        # Verification - show period count for each company
        logger.info("Verification - Period Count by Company:")
        logger.info(f"{'='*80}")

        for subscription in subscriptions:
            company_name = subscription.get("company_name", "Unknown")
            sub_id = subscription["_id"]

            # Re-fetch to get updated data (unless dry run)
            if not dry_run:
                updated_sub = await db.subscriptions.find_one({"_id": sub_id})
                period_count = len(updated_sub.get("usage_periods", []))
            else:
                period_count = 12  # Would have 12 periods

            logger.info(f"  {company_name}: {period_count} periods")

        logger.info(f"{'='*80}\n")

    except Exception as e:
        logger.error(f"Error updating subscriptions: {e}", exc_info=True)
        raise
    finally:
        client.close()
        logger.info("MongoDB connection closed")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Update all subscriptions with 12 monthly usage periods"
    )
    parser.add_argument(
        "--database",
        type=str,
        default=None,
        help="Database name (default: from settings)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes"
    )

    args = parser.parse_args()

    # Run the update
    asyncio.run(update_subscriptions_with_12_periods(
        database_name=args.database,
        dry_run=args.dry_run
    ))


if __name__ == "__main__":
    main()
