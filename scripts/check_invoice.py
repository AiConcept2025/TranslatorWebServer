#!/usr/bin/env python3
"""
Check the specific invoice the user mentioned.
"""
import asyncio
import sys
from pathlib import Path
from bson import ObjectId

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def check_invoice():
    """Check the specific invoice."""
    print("=" * 80)
    print("CHECKING INVOICE 68ec42a48ca6a1781d9fe5c5")
    print("=" * 80)

    # Connect to database
    print("\nConnecting to MongoDB...")
    await database.connect()
    print("✓ Connected")

    # Check the specific invoice
    invoice_id = ObjectId("68ec42a48ca6a1781d9fe5c5")
    print(f"\nLooking for invoice with _id: {invoice_id}...")

    invoice = await database.invoices.find_one({"_id": invoice_id})

    if invoice:
        print(f"\n✅ Invoice found!")
        print("\nInvoice Details:")
        print("-" * 80)
        for key, value in invoice.items():
            print(f"  {key}: {value}")
    else:
        print(f"\n❌ Invoice not found!")
        print("\nLet me check all invoices in the collection...")

        all_invoices = await database.invoices.find().to_list(length=100)
        print(f"\nTotal invoices in database: {len(all_invoices)}")

        if all_invoices:
            print("\nAll invoice IDs and company_ids:")
            print("-" * 80)
            for inv in all_invoices:
                print(f"  _id: {inv['_id']}")
                print(f"  company_id: {inv.get('company_id', 'N/A')}")
                print(f"  invoice_number: {inv.get('invoice_number', 'N/A')}")
                print(f"  status: {inv.get('status', 'N/A')}")
                print()

    # Disconnect
    print("=" * 80)
    await database.disconnect()
    print("✓ Disconnected")


if __name__ == "__main__":
    asyncio.run(check_invoice())
