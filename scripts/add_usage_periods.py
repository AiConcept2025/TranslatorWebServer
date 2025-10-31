#!/usr/bin/env python3
"""
Script to add usage_periods to existing subscription records.
Each subscription will get 2 usage periods with all required fields.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from decimal import Decimal

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_usage_periods_to_subscriptions():
    """Add 2 usage periods to each subscription record."""

    # Connect to MongoDB
    logger.info(f"Connecting to MongoDB: {settings.mongodb_database}")
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    try:
        # Get all subscriptions
        subscriptions = await db.subscriptions.find({}).to_list(length=None)
        logger.info(f"Found {len(subscriptions)} subscription records")

        updated_count = 0

        for subscription in subscriptions:
            sub_id = subscription["_id"]
            company_name = subscription.get("company_name", "Unknown")
            start_date = subscription.get("start_date")
            end_date = subscription.get("end_date")

            logger.info(f"\nProcessing subscription for: {company_name}")
            logger.info(f"  ID: {sub_id}")
            logger.info(f"  Start: {start_date}")
            logger.info(f"  End: {end_date}")

            # Check if usage_periods already exists and has data
            existing_periods = subscription.get("usage_periods", [])
            if existing_periods:
                logger.info(f"  ⚠️  Already has {len(existing_periods)} usage periods, skipping")
                continue

            # Get subscription details for usage periods
            units_per_subscription = subscription.get("units_per_subscription", 1000)
            promotional_units = subscription.get("promotional_units", 0)
            price_per_unit = subscription.get("price_per_unit", 0.01)

            # Create 2 usage periods
            # Period 1: First month (or half the subscription period)
            # Period 2: Second month (or second half)

            if start_date and end_date:
                # Calculate midpoint
                total_days = (end_date - start_date).days
                mid_date = start_date + timedelta(days=total_days // 2)

                period_1_start = start_date
                period_1_end = mid_date
                period_2_start = mid_date
                period_2_end = end_date
            else:
                # Default to monthly periods starting now
                now = datetime.now(timezone.utc)
                period_1_start = now
                period_1_end = now + timedelta(days=30)
                period_2_start = period_1_end
                period_2_end = period_2_start + timedelta(days=30)

            # Allocate units between periods
            # Give promotional units to first period, split subscription units
            period_1_subscription_units = units_per_subscription // 2
            period_2_subscription_units = units_per_subscription - period_1_subscription_units

            # Create usage periods
            usage_periods = [
                {
                    "subscription_units": period_1_subscription_units,
                    "used_units": 0,
                    "promotional_units": promotional_units,
                    "price_per_unit": float(price_per_unit),
                    "period_start": period_1_start,
                    "period_end": period_1_end
                },
                {
                    "subscription_units": period_2_subscription_units,
                    "used_units": 0,
                    "promotional_units": 0,  # No promotional units in second period
                    "price_per_unit": float(price_per_unit),
                    "period_start": period_2_start,
                    "period_end": period_2_end
                }
            ]

            logger.info(f"  Creating 2 usage periods:")
            logger.info(f"    Period 1: {period_1_start.date()} to {period_1_end.date()}")
            logger.info(f"      - Subscription units: {period_1_subscription_units}")
            logger.info(f"      - Promotional units: {promotional_units}")
            logger.info(f"      - Price per unit: ${price_per_unit}")
            logger.info(f"    Period 2: {period_2_start.date()} to {period_2_end.date()}")
            logger.info(f"      - Subscription units: {period_2_subscription_units}")
            logger.info(f"      - Promotional units: 0")
            logger.info(f"      - Price per unit: ${price_per_unit}")

            # Update the subscription
            result = await db.subscriptions.update_one(
                {"_id": sub_id},
                {
                    "$set": {
                        "usage_periods": usage_periods,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"  ✅ Updated subscription with 2 usage periods")
                updated_count += 1
            else:
                logger.warning(f"  ⚠️  No changes made")

        logger.info(f"\n{'='*60}")
        logger.info(f"Summary:")
        logger.info(f"  Total subscriptions: {len(subscriptions)}")
        logger.info(f"  Updated: {updated_count}")
        logger.info(f"  Skipped (already had periods): {len(subscriptions) - updated_count}")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f"Error updating subscriptions: {e}", exc_info=True)
        raise
    finally:
        client.close()
        logger.info("MongoDB connection closed")


if __name__ == "__main__":
    asyncio.run(add_usage_periods_to_subscriptions())
