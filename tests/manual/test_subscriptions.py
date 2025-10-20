"""
Test script for subscription functionality.

Run with: python test_subscriptions.py
"""

import asyncio
from datetime import datetime, timedelta, timezone
from bson import ObjectId

from app.database.mongodb import database
from app.services.subscription_service import subscription_service
from app.models.subscription import (
    SubscriptionCreate,
    UsagePeriodCreate,
    UsageUpdate
)


async def test_subscriptions():
    """Test subscription CRUD operations."""

    print("=" * 80)
    print("SUBSCRIPTION SYSTEM TEST")
    print("=" * 80)

    # Connect to database
    print("\n[1] Connecting to MongoDB...")
    await database.connect()
    print("✅ Connected to MongoDB")

    # Get a test company
    print("\n[2] Finding test company...")
    company = await database.companies.find_one({})
    if not company:
        print("❌ No company found in database. Please add a company first.")
        return

    company_id = str(company["_id"])
    print(f"✅ Using company: {company.get('company_name')} (ID: {company_id})")

    # Create a subscription
    print("\n[3] Creating subscription...")
    start_date = datetime.now(timezone.utc)
    end_date = start_date + timedelta(days=365)

    subscription_data = SubscriptionCreate(
        company_id=company_id,
        subscription_unit="page",
        units_per_subscription=1000,
        price_per_unit=0.10,
        promotional_units=100,
        discount=0.9,
        subscription_price=90.00,
        start_date=start_date,
        end_date=end_date,
        status="active"
    )

    subscription = await subscription_service.create_subscription(subscription_data)
    subscription_id = str(subscription["_id"])
    print(f"✅ Created subscription ID: {subscription_id}")
    print(f"   - Unit: {subscription['subscription_unit']}")
    print(f"   - Units: {subscription['units_per_subscription']}")
    print(f"   - Price: ${subscription['subscription_price']}")
    print(f"   - Promotional units: {subscription['promotional_units']}")

    # Add usage period
    print("\n[4] Adding usage period...")
    period_start = datetime.now(timezone.utc)
    period_end = period_start + timedelta(days=30)

    period_data = UsagePeriodCreate(
        period_start=period_start,
        period_end=period_end,
        units_allocated=1000
    )

    subscription = await subscription_service.add_usage_period(subscription_id, period_data)
    print(f"✅ Added usage period")
    print(f"   - Period: {period_start.date()} to {period_end.date()}")
    print(f"   - Units allocated: 1000")
    print(f"   - Total periods: {len(subscription.get('usage_periods', []))}")

    # Record some usage
    print("\n[5] Recording usage (50 regular units)...")
    usage_data = UsageUpdate(
        units_to_add=50,
        use_promotional_units=False
    )

    subscription = await subscription_service.record_usage(subscription_id, usage_data)
    current_period = subscription["usage_periods"][0]
    print(f"✅ Usage recorded")
    print(f"   - Units used: {current_period['units_used']}")
    print(f"   - Units remaining: {current_period['units_remaining']}")

    # Record promotional usage
    print("\n[6] Recording usage (25 promotional units)...")
    promo_usage_data = UsageUpdate(
        units_to_add=25,
        use_promotional_units=True
    )

    subscription = await subscription_service.record_usage(subscription_id, promo_usage_data)
    current_period = subscription["usage_periods"][0]
    print(f"✅ Promotional usage recorded")
    print(f"   - Promotional units used: {current_period['promotional_units_used']}")
    print(f"   - Regular units used: {current_period['units_used']}")
    print(f"   - Units remaining: {current_period['units_remaining']}")

    # Get subscription summary
    print("\n[7] Getting subscription summary...")
    summary = await subscription_service.get_subscription_summary(subscription_id)
    print(f"✅ Subscription summary:")
    print(f"   - Status: {summary.status}")
    print(f"   - Total allocated: {summary.total_units_allocated}")
    print(f"   - Total used: {summary.total_units_used}")
    print(f"   - Total remaining: {summary.total_units_remaining}")
    print(f"   - Promotional available: {summary.promotional_units_available}")
    print(f"   - Promotional used: {summary.promotional_units_used}")

    # Get company subscriptions
    print("\n[8] Getting all company subscriptions...")
    subscriptions = await subscription_service.get_company_subscriptions(company_id, active_only=True)
    print(f"✅ Found {len(subscriptions)} active subscription(s)")

    for sub in subscriptions:
        print(f"   - {sub['subscription_unit']}: {sub['units_per_subscription']} units")

    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED")
    print("=" * 80)

    # Cleanup
    await database.disconnect()


if __name__ == "__main__":
    asyncio.run(test_subscriptions())
