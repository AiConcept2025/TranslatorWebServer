#!/usr/bin/env python3
"""Insert one realistic record per collection with referential integrity."""

from pymongo import MongoClient
from bson import ObjectId
from bson.decimal128 import Decimal128
from datetime import datetime, timezone

MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"

def seed():
    client = MongoClient(MONGODB_URI)
    db = client.translation

    print("\nSeeding database with sample data\n")

    company = {
        "company_name": "Acme Translation Corp",
        "address": "123 Business St, New York, NY 10001",
        "contact_person": "John Smith",
        "phone_number": "+1-555-0100",
        "company_url": "https://acmetranslation.com",
        "line_of_business": "Legal Translation Services",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    company_id = db.company.insert_one(company).inserted_id
    print(f"✓ Company: {company['company_name']} (ID: {company_id})")

    user = {
        "user_id": "jane.smith@acme.com",
        "company_id": company_id,  # Fixed: was 'customer_id', now 'company_id' for consistency
        "user_name": "Jane Smith",
        "email": "jane.smith@acme.com",
        "phone_number": "+1-555-0101",
        "permission_level": "admin",
        "status": "active",
        "password_hash": "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIx.T7jK3i",
        "last_login": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    user_id = db.company_users.insert_one(user).inserted_id
    print(f"✓ User: {user['user_name']} ({user['email']})")

    subscription = {
        "customer_id": company_id,
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        "price_per_unit": Decimal128("0.10"),
        "promotional_units": 100,
        "subscription_price": Decimal128("100.00"),
        "start_date": datetime.now(timezone.utc),
        "end_date": None,
        "status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    subscription_id = db.subscriptions.insert_one(subscription).inserted_id
    print(f"✓ Subscription: 1000 pages @ $0.10/page (ID: {subscription_id})")

    invoice = {
        "customer_id": company_id,
        "subscription_id": subscription_id,
        "invoice_number": f"INV-2025-{str(company_id)[-6:]}",
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc),
        "total_amount": Decimal128("106.00"),
        "tax_amount": Decimal128("6.00"),
        "status": "paid",
        "pdf_url": f"https://invoices.acme.com/{str(company_id)[-6:]}.pdf",
        "created_at": datetime.now(timezone.utc)
    }
    invoice_id = db.invoices.insert_one(invoice).inserted_id
    print(f"✓ Invoice: {invoice['invoice_number']} - $106.00 (paid)")

    payment = {
        "customer_id": company_id,
        "subscription_id": subscription_id,
        "square_payment_id": f"sq_pay_{ObjectId()}",
        "square_order_id": f"sq_ord_{ObjectId()}",
        "square_receipt_url": "https://square.com/receipt/123",
        "amount": Decimal128("106.00"),
        "currency": "USD",
        "payment_status": "completed",
        "payment_method": "card",
        "card_brand": "Visa",
        "last_4_digits": "4242",
        "processing_fee": Decimal128("3.37"),
        "net_amount": Decimal128("102.63"),
        "refunded_amount": Decimal128("0.00"),
        "payment_date": datetime.now(timezone.utc),
        "notes": "Monthly subscription payment",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    payment_id = db.payments.insert_one(payment).inserted_id
    print(f"✓ Payment: ${payment['amount'].to_decimal()} via {payment['card_brand']} ****{payment['last_4_digits']}")

    transaction = {
        "customer_id": company_id,
        "subscription_id": subscription_id,
        "requester_id": user["user_id"],
        "user_name": user["user_name"],
        "transaction_date": datetime.now(timezone.utc),
        "units_consumed": 15,
        "original_file_url": "https://drive.google.com/file/d/abc123/view",
        "translated_file_url": "https://drive.google.com/file/d/xyz789/view",
        "source_language": "en",
        "target_language": "es",
        "status": "completed",
        "error_message": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    transaction_id = db.translation_transactions.insert_one(transaction).inserted_id
    print(f"✓ Transaction: 15 pages translated (en → es)")

    print(f"\n✓ Seeding complete: 6 records inserted with referential integrity")

    client.close()

if __name__ == "__main__":
    seed()
