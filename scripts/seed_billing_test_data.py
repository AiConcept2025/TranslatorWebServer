#!/usr/bin/env python3
"""
Seed Enhanced Billing Schema Test Data

Creates test data for E2E tests with billing fields:
- Companies with subscriptions (billing_frequency, payment_terms_days)
- Invoices with billing_period and line_items
- Payments linked to invoices and subscriptions

Usage:
    python scripts/seed_billing_test_data.py
"""

import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import os
from typing import List, Dict, Any

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = "translation_test"  # Use test database

async def seed_billing_test_data():
    """Seed test database with billing schema data"""

    print("=" * 80)
    print("Enhanced Billing Schema - Test Data Seeding")
    print("=" * 80)

    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DATABASE_NAME]

    print(f"\n📊 Database: {DATABASE_NAME}")
    print(f"🔗 MongoDB URI: {MONGODB_URI}")

    # 1. Create Test Companies
    print("\n1️⃣  Creating test companies...")

    companies_data = [
        {
            "company_name": "Acme Corporation",
            "email": "admin@acme.example.com",
            "phone": "+1-555-0100",
            "address": "123 Business St, San Francisco, CA 94105",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "company_name": "Global Translation Inc",
            "email": "admin@globaltrans.example.com",
            "phone": "+1-555-0200",
            "address": "456 Translation Ave, New York, NY 10001",
            "created_at": datetime.now(timezone.utc),
        },
        {
            "company_name": "TechDocs Ltd",
            "email": "admin@techdocs.example.com",
            "phone": "+44-20-5550-0300",
            "address": "789 Document Lane, London, UK",
            "created_at": datetime.now(timezone.utc),
        }
    ]

    for company_data in companies_data:
        await db.companies.update_one(
            {"company_name": company_data["company_name"]},
            {"$set": company_data},
            upsert=True
        )

    print(f"   ✅ Created {len(companies_data)} companies")

    # 2. Create Test Subscriptions with Billing Fields
    print("\n2️⃣  Creating test subscriptions with billing fields...")

    start_date = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=365)

    subscriptions_data = [
        {
            "company_name": "Acme Corporation",
            "subscription_unit": "page",
            "units_per_subscription": 10000,
            "price_per_unit": 0.05,
            "promotional_units": 2000,
            "discount": 0.1,
            "subscription_price": 450.0,
            "start_date": start_date,
            "end_date": end_date,
            "status": "active",
            "billing_frequency": "quarterly",  # NEW FIELD
            "payment_terms_days": 30,          # NEW FIELD
            "usage_periods": [
                {
                    "period_start": start_date + timedelta(days=i*30),
                    "period_end": start_date + timedelta(days=(i+1)*30),
                    "units_allocated": 10000,
                    "units_used": 3000 + (i * 500),
                    "units_remaining": 7000 - (i * 500),
                    "promotional_units": 2000,
                    "last_updated": datetime.now(timezone.utc),
                    "period_number": i + 1  # 1-12
                }
                for i in range(12)
            ],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "company_name": "Global Translation Inc",
            "subscription_unit": "word",
            "units_per_subscription": 100000,
            "price_per_unit": 0.01,
            "promotional_units": 5000,
            "discount": 0.15,
            "subscription_price": 850.0,
            "start_date": start_date,
            "end_date": end_date,
            "status": "active",
            "billing_frequency": "monthly",    # NEW FIELD
            "payment_terms_days": 15,          # NEW FIELD
            "usage_periods": [
                {
                    "period_start": start_date + timedelta(days=i*30),
                    "period_end": start_date + timedelta(days=(i+1)*30),
                    "units_allocated": 100000,
                    "units_used": 45000 + (i * 2000),
                    "units_remaining": 55000 - (i * 2000),
                    "promotional_units": 5000,
                    "last_updated": datetime.now(timezone.utc),
                    "period_number": i + 1
                }
                for i in range(12)
            ],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        },
        {
            "company_name": "TechDocs Ltd",
            "subscription_unit": "character",
            "units_per_subscription": 500000,
            "price_per_unit": 0.001,
            "promotional_units": 10000,
            "discount": 0.2,
            "subscription_price": 400.0,
            "start_date": start_date,
            "end_date": end_date,
            "status": "active",
            "billing_frequency": "yearly",     # NEW FIELD
            "payment_terms_days": 60,          # NEW FIELD
            "usage_periods": [
                {
                    "period_start": start_date + timedelta(days=i*30),
                    "period_end": start_date + timedelta(days=(i+1)*30),
                    "units_allocated": 500000,
                    "units_used": 150000 + (i * 10000),
                    "units_remaining": 350000 - (i * 10000),
                    "promotional_units": 10000,
                    "last_updated": datetime.now(timezone.utc),
                    "period_number": i + 1
                }
                for i in range(12)
            ],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]

    subscription_ids = []
    for sub_data in subscriptions_data:
        result = await db.subscriptions.update_one(
            {"company_name": sub_data["company_name"]},
            {"$set": sub_data},
            upsert=True
        )
        if result.upserted_id:
            subscription_ids.append(result.upserted_id)
        else:
            existing = await db.subscriptions.find_one({"company_name": sub_data["company_name"]})
            subscription_ids.append(existing["_id"])

    print(f"   ✅ Created {len(subscriptions_data)} subscriptions with billing fields")

    # 3. Create Test Invoices with Billing Period and Line Items
    print("\n3️⃣  Creating test invoices with billing_period and line_items...")

    invoices_data = []
    invoice_counter = 1000

    for i, (sub_data, sub_id) in enumerate(zip(subscriptions_data, subscription_ids)):
        # Create Q1 invoice (periods 1-3)
        quarter_start = start_date
        quarter_end = start_date + timedelta(days=90)

        line_items = [
            {
                "description": f"Base subscription charge - {sub_data['subscription_unit']} (Q1)",
                "period_numbers": [1, 2, 3],
                "quantity": sub_data["units_per_subscription"] * 3,
                "unit_price": sub_data["price_per_unit"],
                "amount": sub_data["units_per_subscription"] * 3 * sub_data["price_per_unit"]
            },
            {
                "description": "Overage charges (Q1)",
                "period_numbers": [1, 2, 3],
                "quantity": 5000,
                "unit_price": sub_data["price_per_unit"] * 1.5,
                "amount": 5000 * sub_data["price_per_unit"] * 1.5
            }
        ]

        subtotal = sum(item["amount"] for item in line_items)
        tax_rate = 0.08
        tax_amount = subtotal * tax_rate
        total_amount = subtotal + tax_amount
        amount_paid = total_amount * 0.5 if i % 2 == 0 else 0.0  # Some partially paid

        invoice_data = {
            "company_name": sub_data["company_name"],
            "subscription_id": sub_id,
            "invoice_number": f"INV-{invoice_counter + i}",
            "invoice_date": quarter_start,
            "due_date": quarter_start + timedelta(days=sub_data["payment_terms_days"]),
            "subtotal": subtotal,            # NEW FIELD
            "tax_amount": tax_amount,
            "total_amount": total_amount,
            "amount_paid": amount_paid,      # NEW FIELD
            "status": "partially_paid" if amount_paid > 0 else "sent",
            "billing_period": {              # NEW FIELD
                "period_numbers": [1, 2, 3],
                "period_start": quarter_start.isoformat(),
                "period_end": quarter_end.isoformat()
            },
            "line_items": line_items,        # NEW FIELD
            "stripe_invoice_id": f"in_test_{invoice_counter + i}",  # NEW FIELD
            "payment_applications": [],
            "pdf_url": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        invoices_data.append(invoice_data)

    invoice_ids = []
    for invoice_data in invoices_data:
        result = await db.invoices.insert_one(invoice_data)
        invoice_ids.append(result.inserted_id)

    print(f"   ✅ Created {len(invoices_data)} invoices with billing_period and line_items")

    # 4. Create Test Payments Linked to Invoices
    print("\n4️⃣  Creating test payments linked to invoices...")

    payments_data = []

    for i, (invoice_data, invoice_id, sub_id) in enumerate(zip(invoices_data, invoice_ids, subscription_ids)):
        if invoice_data["amount_paid"] > 0:  # Only create payment if partially paid
            payment_data = {
                "company_name": invoice_data["company_name"],
                "user_email": f"admin@{invoice_data['company_name'].lower().replace(' ', '')}.example.com",
                "stripe_payment_intent_id": f"pi_test_{1000 + i}",
                "stripe_invoice_id": invoice_data.get("stripe_invoice_id"),
                "stripe_customer_id": f"cus_test_{i}",
                "amount": invoice_data["amount_paid"],
                "currency": "usd",
                "payment_status": "COMPLETED",
                "payment_method": "card",
                "card_brand": "visa",
                "last_4_digits": "4242",
                "processing_fee": invoice_data["amount_paid"] * 0.029,
                "net_amount": invoice_data["amount_paid"] * 0.971,
                "refunded_amount": 0.0,
                "total_refunded": 0.0,        # NEW FIELD
                "invoice_id": invoice_id,     # NEW FIELD
                "subscription_id": sub_id,    # NEW FIELD
                "payment_date": datetime.now(timezone.utc),
                "notes": f"Partial payment for Q1 invoice {invoice_data['invoice_number']}",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            payments_data.append(payment_data)

    for payment_data in payments_data:
        await db.payments.insert_one(payment_data)

    print(f"   ✅ Created {len(payments_data)} payments linked to invoices")

    # Summary
    print("\n" + "=" * 80)
    print("✅ Test Data Seeding Complete!")
    print("=" * 80)
    print(f"\n📊 Summary:")
    print(f"   Companies: {len(companies_data)}")
    print(f"   Subscriptions: {len(subscriptions_data)} (with billing_frequency, payment_terms_days)")
    print(f"   Invoices: {len(invoices_data)} (with billing_period, line_items)")
    print(f"   Payments: {len(payments_data)} (with invoice_id, subscription_id)")
    print(f"\n🗄️  Database: {DATABASE_NAME}")
    print(f"🔍 Verify with: mongosh {MONGODB_URI}/{DATABASE_NAME}")
    print("\n" + "=" * 80)

    client.close()

if __name__ == "__main__":
    asyncio.run(seed_billing_test_data())
