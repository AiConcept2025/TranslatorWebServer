#!/usr/bin/env python3
"""
Create 2 additional invoices for Iris Trading company.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def create_invoices():
    """Create 2 invoices for Iris Trading."""
    print("=" * 80)
    print("CREATING INVOICES FOR IRIS TRADING")
    print("=" * 80)

    # Connect to database
    print("\nConnecting to MongoDB...")
    await database.connect()
    print("✓ Connected")

    # Iris Trading company_id (from existing invoice)
    company_id = "68ec42a48ca6a1781d9fe5c2"
    subscription_id = "68ec42a48ca6a1781d9fe5c4"

    # Invoice 2: Paid invoice from September
    invoice_2 = {
        "company_id": company_id,
        "subscription_id": subscription_id,
        "invoice_number": "INV-2025-68EC42A5",
        "invoice_date": datetime(2025, 9, 8, 0, 7, 0),
        "due_date": datetime(2025, 10, 8, 0, 7, 0),
        "total_amount": 106.00,
        "tax_amount": 6.00,
        "status": "paid",
        "pdf_url": "https://storage.example.com/invoices/inv-68ec42a5.pdf",
        "payment_applications": [
            {
                "payment_id": "68fad3c2a0f41c24037c4810",
                "amount_applied": 106.00,
                "applied_date": datetime(2025, 9, 15, 10, 30, 0)
            }
        ],
        "created_at": datetime(2025, 9, 8, 0, 7, 0)
    }

    # Invoice 3: Overdue invoice from August
    invoice_3 = {
        "company_id": company_id,
        "subscription_id": subscription_id,
        "invoice_number": "INV-2025-68EC42A6",
        "invoice_date": datetime(2025, 8, 8, 0, 7, 0),
        "due_date": datetime(2025, 9, 8, 0, 7, 0),
        "total_amount": 106.00,
        "tax_amount": 6.00,
        "status": "overdue",
        "pdf_url": "https://storage.example.com/invoices/inv-68ec42a6.pdf",
        "payment_applications": [],
        "created_at": datetime(2025, 8, 8, 0, 7, 0)
    }

    print(f"\nInserting invoices for company: {company_id}")
    print(f"Subscription ID: {subscription_id}")

    # Insert invoice 2
    print("\n1. Inserting paid invoice (September)...")
    result_2 = await database.invoices.insert_one(invoice_2)
    print(f"   ✓ Inserted invoice: {result_2.inserted_id}")
    print(f"   - Invoice Number: {invoice_2['invoice_number']}")
    print(f"   - Status: {invoice_2['status']}")
    print(f"   - Amount: ${invoice_2['total_amount']}")

    # Insert invoice 3
    print("\n2. Inserting overdue invoice (August)...")
    result_3 = await database.invoices.insert_one(invoice_3)
    print(f"   ✓ Inserted invoice: {result_3.inserted_id}")
    print(f"   - Invoice Number: {invoice_3['invoice_number']}")
    print(f"   - Status: {invoice_3['status']}")
    print(f"   - Amount: ${invoice_3['total_amount']}")

    # Verify all invoices for company
    print(f"\n\nVerifying all invoices for company {company_id}...")
    all_invoices = await database.invoices.find({"company_id": company_id}).to_list(length=100)

    print(f"\n✅ Total invoices found: {len(all_invoices)}")
    print("\nInvoice Summary:")
    print("-" * 80)
    for invoice in all_invoices:
        print(f"  • {invoice['invoice_number']} - ${invoice['total_amount']:.2f} - Status: {invoice['status']}")
        print(f"    Invoice Date: {invoice['invoice_date'].strftime('%Y-%m-%d')}")
        print(f"    Due Date: {invoice['due_date'].strftime('%Y-%m-%d')}")
        print()

    # Disconnect
    print("=" * 80)
    await database.disconnect()
    print("✓ Disconnected")
    print("\n✅ SUCCESS: Invoices created and verified!")


if __name__ == "__main__":
    asyncio.run(create_invoices())
