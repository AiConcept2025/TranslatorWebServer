#!/usr/bin/env python3
"""
Delete old payment records with incorrect schema.

Deletes records that are missing company_id and company_name fields.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def delete_old_records():
    """Delete payment records with old/incorrect schema."""
    print("=" * 80)
    print("DELETING OLD PAYMENT RECORDS")
    print("=" * 80)

    # Connect
    print("\nConnecting to MongoDB...")
    await database.connect()
    print("✓ Connected")

    # Find records missing company_id (old schema)
    print("\nSearching for old records (missing company_id)...")
    old_records = await database.payments.find(
        {"company_id": {"$exists": False}}
    ).to_list(length=100)

    if not old_records:
        print("✓ No old records found - database is clean!")
        await database.disconnect()
        return

    print(f"\nFound {len(old_records)} old record(s) to delete:")
    print("-" * 80)
    for idx, record in enumerate(old_records, 1):
        print(f"\nRecord #{idx}:")
        print(f"  _id: {record['_id']}")
        print(f"  stripe_payment_intent_id: {record.get('stripe_payment_intent_id', 'N/A')}")
        print(f"  user_email: {record.get('user_email', 'N/A')}")
        print(f"  amount: {record.get('amount', 0)} cents")
        print(f"  created_at: {record.get('created_at', 'N/A')}")

        # Show what fields are present
        extra_fields = [k for k in record.keys() if k not in [
            '_id', 'company_id', 'company_name', 'user_email',
            'stripe_payment_intent_id', 'amount', 'currency', 'payment_status',
            'refunds', 'created_at', 'updated_at', 'payment_date'
        ]]
        if extra_fields:
            print(f"  Extra fields: {', '.join(extra_fields)}")

    # Confirm deletion
    print("\n" + "-" * 80)
    print(f"⚠️  About to DELETE {len(old_records)} record(s)")
    print("These records have the OLD schema (missing company_id/company_name)")

    # Delete
    print("\nDeleting old records...")
    result = await database.payments.delete_many(
        {"company_id": {"$exists": False}}
    )

    print(f"✓ Deleted {result.deleted_count} record(s)")

    # Verify remaining records
    print("\n" + "=" * 80)
    print("VERIFYING REMAINING RECORDS")
    print("=" * 80)

    remaining = await database.payments.find({}).to_list(length=100)
    print(f"\nRemaining payment records: {len(remaining)}")

    if remaining:
        print("\nAll remaining records have correct schema:")
        print("-" * 80)
        for idx, record in enumerate(remaining, 1):
            print(f"\nRecord #{idx}:")
            print(f"  _id: {record['_id']}")
            print(f"  company_id: {record.get('company_id', '❌ MISSING')}")
            print(f"  company_name: {record.get('company_name', '❌ MISSING')}")
            print(f"  user_email: {record['user_email']}")
            print(f"  stripe_payment_intent_id: {record['stripe_payment_intent_id']}")
            print(f"  amount: ${record['amount'] / 100:.2f}")
            print(f"  payment_status: {record['payment_status']}")
            print(f"  refunds: {len(record.get('refunds', []))} refund(s)")
            print(f"  created_at: {record['created_at']}")

    print("\n" + "=" * 80)
    print("✓ DATABASE CLEANED - Only correct schema records remain")
    print("=" * 80)

    # Disconnect
    await database.disconnect()
    print("\n✓ Disconnected")


if __name__ == "__main__":
    asyncio.run(delete_old_records())
