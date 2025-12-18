#!/usr/bin/env python3
"""
Verification script to confirm all subscriptions have 12 monthly periods.
Shows detailed information about each subscription's usage periods.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def verify_subscriptions():
    """Verify all subscriptions have 12 periods and show details."""

    # Connect to MongoDB
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    try:
        # Get all subscriptions
        subscriptions = await db.subscriptions.find({}).to_list(length=None)

        logger.info("=" * 100)
        logger.info("SUBSCRIPTION VERIFICATION REPORT")
        logger.info("=" * 100)
        logger.info(f"Database: {settings.mongodb_database}")
        logger.info(f"Total Subscriptions: {len(subscriptions)}")
        logger.info("=" * 100)
        logger.info("")

        for idx, subscription in enumerate(subscriptions, 1):
            company_name = subscription.get("company_name", "Unknown")
            sub_id = subscription["_id"]
            usage_periods = subscription.get("usage_periods", [])
            units_per_subscription = subscription.get("units_per_subscription", 0)
            promotional_units = subscription.get("promotional_units", 0)

            logger.info(f"{idx}. {company_name}")
            logger.info(f"   Subscription ID: {sub_id}")
            logger.info(f"   Units per Period: {units_per_subscription}")
            logger.info(f"   Promotional Units: {promotional_units}")
            logger.info(f"   Total Periods: {len(usage_periods)}")
            logger.info("")

            if len(usage_periods) == 12:
                logger.info("   ✅ HAS 12 MONTHLY PERIODS")
            else:
                logger.info(f"   ❌ INCORRECT - Has {len(usage_periods)} periods (expected 12)")

            logger.info("")
            logger.info("   Period Details:")
            logger.info("   " + "-" * 90)
            logger.info(f"   {'#':<4} {'Start':<12} {'End':<12} {'Allocated':<10} {'Promo':<6} {'Used':<6} {'Remaining':<10} {'Status':<10}")
            logger.info("   " + "-" * 90)

            for period in usage_periods:
                period_num = period.get("period_number", "?")
                start = period.get("period_start", "").strftime("%Y-%m-%d") if period.get("period_start") else "N/A"
                end = period.get("period_end", "").strftime("%Y-%m-%d") if period.get("period_end") else "N/A"
                allocated = period.get("units_allocated", 0)
                promo = period.get("promotional_units", 0)
                used = period.get("units_used", 0)
                remaining = period.get("units_remaining", 0)
                status = period.get("status", "N/A")

                logger.info(f"   {period_num:<4} {start:<12} {end:<12} {allocated:<10} {promo:<6} {used:<6} {remaining:<10} {status:<10}")

            logger.info("")
            logger.info("=" * 100)
            logger.info("")

        # Summary
        all_have_12 = all(len(sub.get("usage_periods", [])) == 12 for sub in subscriptions)

        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 100)
        logger.info(f"Total Subscriptions Checked: {len(subscriptions)}")
        logger.info(f"All have 12 periods: {'✅ YES' if all_have_12 else '❌ NO'}")
        logger.info("=" * 100)

    except Exception as e:
        logger.error(f"Error during verification: {e}", exc_info=True)
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(verify_subscriptions())
