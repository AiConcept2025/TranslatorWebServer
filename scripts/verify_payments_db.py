#!/usr/bin/env python3
"""
Verify what's actually in the payments collection in MongoDB.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database
import json
from datetime import datetime


async def verify_database():
    """Check what's actually in the payments collection."""
    print("=" * 80)
    print("VERIFYING PAYMENTS COLLECTION IN MONGODB")
    print("=" * 80)

    # Connect
    print("\nConnecting to MongoDB...")
    await database.connect()
    print("✓ Connected")

    # Count total documents
    total = await database.payments.count_documents({})
    print(f"\nTotal payment records: {total}")

    # Get all payments
    print("\n" + "=" * 80)
    print("ALL PAYMENT RECORDS:")
    print("=" * 80)

    cursor = database.payments.find({}).sort("created_at", -1)  # Most recent first
    payments = await cursor.to_list(length=100)

    if not payments:
        print("\n⚠️  NO RECORDS FOUND IN PAYMENTS COLLECTION")
        await database.disconnect()
        return

    for idx, payment in enumerate(payments, 1):
        print(f"\n--- Record #{idx} ---")
        print(f"_id: {payment['_id']}")

        # Print all fields
        for key, value in payment.items():
            if key == '_id':
                continue
            if isinstance(value, datetime):
                print(f"{key}: {value.isoformat()}")
            elif isinstance(value, list):
                print(f"{key}: {value} (array with {len(value)} items)")
            else:
                print(f"{key}: {value}")
        print("-" * 80)

    # Show the most recent record in detail
    print("\n" + "=" * 80)
    print("MOST RECENT RECORD (DETAILED):")
    print("=" * 80)

    latest = payments[0]
    print("\nField-by-field analysis:")
    print("-" * 80)

    expected_fields = [
        "_id",
        "company_id",
        "company_name",
        "user_email",
        "square_payment_id",
        "amount",
        "currency",
        "payment_status",
        "refunds",
        "created_at",
        "updated_at",
        "payment_date"
    ]

    print("\nExpected fields:")
    for field in expected_fields:
        if field in latest:
            value = latest[field]
            if isinstance(value, datetime):
                print(f"  ✓ {field}: {value.isoformat()}")
            elif isinstance(value, list):
                print(f"  ✓ {field}: [] (empty array)" if len(value) == 0 else f"  ✓ {field}: [array with {len(value)} items]")
            else:
                print(f"  ✓ {field}: {value}")
        else:
            print(f"  ✗ {field}: MISSING")

    print("\nExtra/unexpected fields:")
    for field in latest.keys():
        if field not in expected_fields:
            print(f"  ⚠️  {field}: {latest[field]}")

    # Disconnect
    print("\n" + "=" * 80)
    await database.disconnect()
    print("✓ Disconnected")


if __name__ == "__main__":
    asyncio.run(verify_database())
