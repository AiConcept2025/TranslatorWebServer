#!/usr/bin/env python3
"""
Fix payment company_id to match the actual company MongoDB ObjectId.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def fix_payment_company_id():
    """Update payment company_id from string to MongoDB ObjectId."""
    print("=" * 80)
    print("FIXING PAYMENT COMPANY_ID")
    print("=" * 80)

    # Connect to database
    print("\nConnecting to MongoDB...")
    await database.connect()
    print("✓ Connected")

    # Find payment with old company_id
    old_company_id = "cmp_00123"
    new_company_id = "68ec42a48ca6a1781d9fe5c9"

    print(f"\nSearching for payment with company_id: '{old_company_id}'...")
    payment = await database.payments.find_one({"company_id": old_company_id})

    if not payment:
        print(f"❌ No payment found with company_id: '{old_company_id}'")

        # Check what payments exist
        all_payments = await database.payments.find().to_list(length=10)
        print(f"\nFound {len(all_payments)} total payments:")
        for p in all_payments:
            print(f"  - Payment {p['_id']}: company_id = '{p.get('company_id')}'")

        await database.disconnect()
        return

    print(f"✓ Found payment: {payment['_id']}")
    print(f"  Current company_id: '{payment['company_id']}'")
    print(f"  User email: {payment.get('user_email')}")
    print(f"  Amount: ${payment.get('amount', 0) / 100:.2f}")

    # Update the payment
    print(f"\nUpdating company_id to: '{new_company_id}'...")
    result = await database.payments.update_one(
        {"_id": payment["_id"]},
        {"$set": {"company_id": new_company_id}}
    )

    if result.modified_count > 0:
        print("✅ Payment updated successfully!")

        # Verify the update
        updated_payment = await database.payments.find_one({"_id": payment["_id"]})
        print(f"\nVerification:")
        print(f"  Payment ID: {updated_payment['_id']}")
        print(f"  New company_id: '{updated_payment['company_id']}'")
        print(f"  Company name: {updated_payment.get('company_name')}")
    else:
        print("❌ No changes made")

    # Disconnect
    print("\n" + "=" * 80)
    await database.disconnect()
    print("✓ Disconnected")


if __name__ == "__main__":
    asyncio.run(fix_payment_company_id())
