#!/usr/bin/env python3
"""
Create the first invoice for Iris Trading (the one referenced by the user).
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from bson import ObjectId

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def create_first_invoice():
    """Create the first invoice that the user referenced."""
    print("=" * 80)
    print("CREATING FIRST INVOICE FOR IRIS TRADING")
    print("=" * 80)

    # Connect to database
    print("\nConnecting to MongoDB...")
    await database.connect()
    print("✓ Connected")

    # The invoice data from user's schema
    invoice_1 = {
        "_id": ObjectId("68ec42a48ca6a1781d9fe5c5"),
        "company_id": "68ec42a48ca6a1781d9fe5c2",
        "subscription_id": "68ec42a48ca6a1781d9fe5c4",
        "invoice_number": "INV-2025-68EC42A4",
        "invoice_date": datetime(2025, 10, 8, 0, 7, 0, 396000),
        "due_date": datetime(2025, 11, 7, 0, 7, 0, 396000),
        "total_amount": 106.00,
        "tax_amount": 6.00,
        "status": "sent",
        "pdf_url": "https://storage.example.com/invoices/inv-123456.pdf",
        "payment_applications": [],
        "created_at": datetime(2025, 10, 8, 0, 7, 0, 396000)
    }

    print(f"\nChecking if invoice {invoice_1['_id']} already exists...")
    existing = await database.invoices.find_one({"_id": invoice_1["_id"]})

    if existing:
        print(f"✓ Invoice already exists: {invoice_1['invoice_number']}")
    else:
        print(f"Creating invoice {invoice_1['invoice_number']}...")
        await database.invoices.insert_one(invoice_1)
        print(f"✓ Invoice created: {invoice_1['invoice_number']}")

    # Verify all invoices
    print(f"\n\nVerifying all invoices for company {invoice_1['company_id']}...")
    all_invoices = await database.invoices.find({"company_id": invoice_1["company_id"]}).sort("invoice_date", -1).to_list(length=100)

    print(f"\n✅ Total invoices found: {len(all_invoices)}")
    print("\nInvoice Summary (sorted by date, newest first):")
    print("-" * 80)
    for invoice in all_invoices:
        print(f"  • {invoice['invoice_number']} - ${invoice['total_amount']:.2f} - Status: {invoice['status']}")
        print(f"    Invoice Date: {invoice['invoice_date'].strftime('%Y-%m-%d')}")
        print(f"    Due Date: {invoice['due_date'].strftime('%Y-%m-%d')}")
        print(f"    ID: {invoice['_id']}")
        print()

    # Disconnect
    print("=" * 80)
    await database.disconnect()
    print("✓ Disconnected")
    print("\n✅ SUCCESS: All invoices verified!")


if __name__ == "__main__":
    asyncio.run(create_first_invoice())
