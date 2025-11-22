#!/usr/bin/env python3
"""
Usage Periods Restoration Script

CRITICAL DATA RESTORATION - DO NOT RUN WITHOUT UNDERSTANDING

This script restores usage_periods data that was accidentally deleted by the
/api/test/seed-subscriptions endpoint. It regenerates usage_periods based on
subscription start_date, end_date, and billing cycle.

SAFETY FEATURES:
- Dry-run mode by default (--dry-run flag)
- Preserves existing usage_periods if they already exist
- Detailed logging of all operations
- Safe to run multiple times (idempotent)
- Environment check (won't run in production without --force)

USAGE:
    # Preview changes (safe, no modifications)
    python restore_usage_periods.py --dry-run

    # Apply changes to development/test database
    python restore_usage_periods.py

    # Force run in any environment (USE WITH CAUTION)
    python restore_usage_periods.py --force

    # Restore only specific company
    python restore_usage_periods.py --company "Acme Corporation"

    # Restore with custom billing cycle
    python restore_usage_periods.py --billing-cycle quarterly
"""

import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from decimal import Decimal
from dateutil.relativedelta import relativedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class UsagePeriodRestorer:
    """Handles the restoration of usage_periods for subscriptions."""

    def __init__(self, db, dry_run: bool = True, billing_cycle: str = "monthly"):
        self.db = db
        self.dry_run = dry_run
        self.billing_cycle = billing_cycle
        self.stats = {
            "total_subscriptions": 0,
            "with_empty_periods": 0,
            "with_existing_periods": 0,
            "without_dates": 0,
            "expired_subscriptions": 0,
            "restored": 0,
            "errors": 0
        }

    def calculate_billing_months(self) -> int:
        """Calculate number of months per billing cycle."""
        cycles = {
            "monthly": 1,
            "quarterly": 3,
            "semi-annual": 6,
            "annual": 12
        }
        return cycles.get(self.billing_cycle.lower(), 1)

    def generate_usage_periods(
        self,
        subscription: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate usage_periods for a subscription based on billing cycle.

        Args:
            subscription: The subscription document from MongoDB

        Returns:
            List of usage period dictionaries
        """
        start_date = subscription.get("start_date")
        end_date = subscription.get("end_date")
        units_per_subscription = subscription.get("units_per_subscription", 0)
        promotional_units = subscription.get("promotional_units", 0)
        price_per_unit = subscription.get("price_per_unit", 0.0)

        if not start_date:
            logger.warning(f"  No start_date for subscription {subscription.get('_id')}")
            return []

        # Use end_date if provided, otherwise assume 1 year from start
        if not end_date:
            end_date = start_date + relativedelta(years=1)
            logger.info(f"  No end_date, assuming 1 year: {end_date.date()}")

        # Ensure timezone-aware UTC datetimes
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        # Calculate billing period length
        months_per_period = self.calculate_billing_months()

        usage_periods = []
        current_period_start = start_date
        period_number = 0

        while current_period_start < end_date:
            period_number += 1

            # Calculate period end (either next billing cycle or subscription end)
            current_period_end = current_period_start + relativedelta(months=months_per_period)

            # Don't exceed subscription end_date
            if current_period_end > end_date:
                current_period_end = end_date

            # Calculate units for this period
            # For monthly billing, distribute evenly
            # For longer cycles, allocate full amount per period
            if self.billing_cycle.lower() == "monthly":
                # Distribute total subscription units across all months
                total_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                total_months = max(1, total_months)  # At least 1 month
                units_allocated = units_per_subscription // total_months

                # Add remainder to first period
                if period_number == 1:
                    remainder = units_per_subscription % total_months
                    units_allocated += remainder
            else:
                # For quarterly/semi-annual/annual, allocate full subscription amount
                units_allocated = units_per_subscription

            # Promotional units only in first period
            period_promotional_units = promotional_units if period_number == 1 else 0

            # Calculate units_remaining
            units_remaining = units_allocated + period_promotional_units

            period = {
                "period_start": current_period_start,
                "period_end": current_period_end,
                "units_allocated": units_allocated,
                "units_used": 0,  # No historical usage data available
                "units_remaining": units_remaining,
                "promotional_units": period_promotional_units,
                "last_updated": datetime.now(timezone.utc)
            }

            usage_periods.append(period)

            # Move to next period
            current_period_start = current_period_end

            # Safety check: prevent infinite loops
            if len(usage_periods) > 50:
                logger.warning(f"  Generated {len(usage_periods)} periods, stopping to prevent infinite loop")
                break

        return usage_periods

    async def restore_subscription(self, subscription: Dict[str, Any]) -> bool:
        """
        Restore usage_periods for a single subscription.

        Args:
            subscription: The subscription document from MongoDB

        Returns:
            True if restored successfully, False otherwise
        """
        sub_id = subscription["_id"]
        company_name = subscription.get("company_name", "Unknown")

        # Generate usage periods
        usage_periods = self.generate_usage_periods(subscription)

        if not usage_periods:
            logger.warning(f"  Could not generate usage_periods for {company_name}")
            self.stats["errors"] += 1
            return False

        logger.info(f"  Generated {len(usage_periods)} usage periods:")
        for idx, period in enumerate(usage_periods, 1):
            logger.info(
                f"    Period {idx}: {period['period_start'].date()} to {period['period_end'].date()} "
                f"(allocated: {period['units_allocated']}, promotional: {period['promotional_units']}, "
                f"remaining: {period['units_remaining']})"
            )

        if self.dry_run:
            logger.info(f"  [DRY-RUN] Would update subscription with {len(usage_periods)} periods")
            self.stats["restored"] += 1
            return True

        # Apply the update
        try:
            result = await self.db.subscriptions.update_one(
                {"_id": sub_id},
                {
                    "$set": {
                        "usage_periods": usage_periods,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"  ✅ Successfully restored {len(usage_periods)} usage periods")
                self.stats["restored"] += 1
                return True
            else:
                logger.warning(f"  ⚠️  Update did not modify the document")
                self.stats["errors"] += 1
                return False

        except Exception as e:
            logger.error(f"  ❌ Error updating subscription: {e}", exc_info=True)
            self.stats["errors"] += 1
            return False

    async def restore_all(self, company_filter: Optional[str] = None):
        """
        Restore usage_periods for all subscriptions with empty/missing periods.

        Args:
            company_filter: Optional company name to filter by
        """
        logger.info("="*80)
        logger.info("USAGE PERIODS RESTORATION")
        logger.info("="*80)
        logger.info(f"Mode: {'DRY-RUN (no changes)' if self.dry_run else 'LIVE (will modify database)'}")
        logger.info(f"Billing Cycle: {self.billing_cycle}")
        logger.info(f"Database: {self.db.name}")
        if company_filter:
            logger.info(f"Company Filter: {company_filter}")
        logger.info("="*80)

        # Build query
        query = {}
        if company_filter:
            query["company_name"] = company_filter

        # Get all subscriptions
        subscriptions = await self.db.subscriptions.find(query).to_list(length=None)
        self.stats["total_subscriptions"] = len(subscriptions)

        logger.info(f"\nFound {len(subscriptions)} subscription(s)")
        logger.info("-"*80)

        # Process each subscription
        for idx, subscription in enumerate(subscriptions, 1):
            company_name = subscription.get("company_name", "Unknown")
            sub_id = subscription.get("_id")
            status = subscription.get("status", "unknown")
            start_date = subscription.get("start_date")
            end_date = subscription.get("end_date")

            logger.info(f"\n[{idx}/{len(subscriptions)}] Processing: {company_name}")
            logger.info(f"  ID: {sub_id}")
            logger.info(f"  Status: {status}")
            logger.info(f"  Start: {start_date.date() if start_date else 'N/A'}")
            logger.info(f"  End: {end_date.date() if end_date else 'N/A'}")

            # Check if usage_periods already exists and has data
            existing_periods = subscription.get("usage_periods", [])

            if existing_periods and len(existing_periods) > 0:
                logger.info(f"  ✓ Already has {len(existing_periods)} usage periods - SKIPPING")
                self.stats["with_existing_periods"] += 1
                continue

            logger.info(f"  ⚠️  Missing usage_periods - RESTORING")
            self.stats["with_empty_periods"] += 1

            # Check if we have required date fields
            if not start_date:
                logger.warning(f"  ❌ Missing start_date - SKIPPING")
                self.stats["without_dates"] += 1
                continue

            # Check if subscription is expired
            now = datetime.now(timezone.utc)
            if end_date and end_date < now:
                logger.info(f"  ℹ️  Subscription expired on {end_date.date()}")
                self.stats["expired_subscriptions"] += 1

            # Restore the subscription
            await self.restore_subscription(subscription)

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print summary of restoration operation."""
        logger.info("\n" + "="*80)
        logger.info("RESTORATION SUMMARY")
        logger.info("="*80)
        logger.info(f"Total subscriptions found:      {self.stats['total_subscriptions']}")
        logger.info(f"With existing periods (skipped): {self.stats['with_existing_periods']}")
        logger.info(f"With empty periods (candidates): {self.stats['with_empty_periods']}")
        logger.info(f"Without dates (skipped):        {self.stats['without_dates']}")
        logger.info(f"Expired subscriptions:          {self.stats['expired_subscriptions']}")
        logger.info(f"Successfully restored:          {self.stats['restored']}")
        logger.info(f"Errors encountered:             {self.stats['errors']}")
        logger.info("="*80)

        if self.dry_run:
            logger.info("\n⚠️  DRY-RUN MODE - NO CHANGES WERE MADE")
            logger.info("Run without --dry-run to apply changes")
        else:
            logger.info(f"\n✅ RESTORATION COMPLETE - {self.stats['restored']} subscription(s) updated")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Restore usage_periods data for subscriptions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview changes without modifying database (default: True)"
    )

    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Apply changes to database (disables dry-run)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force execution in production environment (USE WITH EXTREME CAUTION)"
    )

    parser.add_argument(
        "--company",
        type=str,
        help="Restore only for specific company name"
    )

    parser.add_argument(
        "--billing-cycle",
        type=str,
        choices=["monthly", "quarterly", "semi-annual", "annual"],
        default="monthly",
        help="Billing cycle for usage period generation (default: monthly)"
    )

    args = parser.parse_args()

    # Determine dry-run mode
    dry_run = not args.live  # By default, dry-run unless --live is specified
    if args.dry_run:
        dry_run = True  # Explicit --dry-run overrides --live

    # Environment check
    if settings.environment.lower() == "production" and not args.force:
        logger.error("="*80)
        logger.error("❌ PRODUCTION ENVIRONMENT DETECTED")
        logger.error("="*80)
        logger.error("This script is about to modify production data.")
        logger.error("If you are ABSOLUTELY SURE you want to proceed, use --force flag.")
        logger.error("Otherwise, please switch to development/test environment.")
        logger.error("="*80)
        sys.exit(1)

    if args.force and settings.environment.lower() == "production":
        logger.warning("="*80)
        logger.warning("⚠️  RUNNING IN PRODUCTION WITH --force FLAG")
        logger.warning("="*80)
        logger.warning("You are about to modify PRODUCTION data.")
        logger.warning("Press Ctrl+C within 5 seconds to cancel...")
        logger.warning("="*80)
        await asyncio.sleep(5)

    # Connect to MongoDB
    logger.info(f"Connecting to MongoDB: {settings.mongodb_database}")
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    try:
        # Verify connection
        await db.command("ping")
        logger.info("✅ MongoDB connection successful")

        # Create restorer instance
        restorer = UsagePeriodRestorer(
            db=db,
            dry_run=dry_run,
            billing_cycle=args.billing_cycle
        )

        # Run restoration
        await restorer.restore_all(company_filter=args.company)

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        client.close()
        logger.info("MongoDB connection closed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n⚠️  Operation cancelled by user")
        sys.exit(0)
