#!/usr/bin/env python3
"""Create 6 core MongoDB collections with validation and indexes."""

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime, timezone

MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"

COLLECTIONS = {
    "company": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["company_name"],
                "properties": {
                    "company_name": {"bsonType": "string"},
                    "address": {"bsonType": ["string", "null"]},
                    "contact_person": {"bsonType": ["string", "null"]},
                    "phone_number": {"bsonType": ["string", "null"]},
                    "company_url": {"bsonType": ["string", "null"]},
                    "line_of_business": {"bsonType": ["string", "null"]},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"}
                }
            }
        },
        "indexes": [
            ([("company_name", ASCENDING)], {}),
            ([("line_of_business", ASCENDING)], {})
        ]
    },
    "company_users": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["user_id", "customer_id", "user_name", "email"],
                "properties": {
                    "user_id": {"bsonType": "string"},
                    "customer_id": {"bsonType": "objectId"},
                    "user_name": {"bsonType": "string"},
                    "email": {"bsonType": "string"},
                    "phone_number": {"bsonType": ["string", "null"]},
                    "permission_level": {"enum": ["admin", "user"]},
                    "status": {"enum": ["active", "inactive", "suspended"]},
                    "password_hash": {"bsonType": ["string", "null"]},
                    "last_login": {"bsonType": ["date", "null"]},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"}
                }
            }
        },
        "indexes": [
            ([("user_id", ASCENDING)], {"unique": True}),
            ([("customer_id", ASCENDING)], {}),
            ([("email", ASCENDING)], {}),
            ([("customer_id", ASCENDING), ("email", ASCENDING)], {"unique": True})
        ]
    },
    "subscriptions": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["customer_id", "subscription_unit", "units_per_subscription",
                            "price_per_unit", "subscription_price", "start_date"],
                "properties": {
                    "customer_id": {"bsonType": "objectId"},
                    "subscription_unit": {"enum": ["page", "word", "character"]},
                    "units_per_subscription": {"bsonType": "int"},
                    "price_per_unit": {"bsonType": ["double", "decimal"]},
                    "promotional_units": {"bsonType": ["int", "null"]},
                    "subscription_price": {"bsonType": ["double", "decimal"]},
                    "start_date": {"bsonType": "date"},
                    "end_date": {"bsonType": ["date", "null"]},
                    "status": {"enum": ["active", "inactive", "expired"]},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"}
                }
            }
        },
        "indexes": [
            ([("customer_id", ASCENDING)], {}),
            ([("customer_id", ASCENDING), ("status", ASCENDING)], {}),
            ([("start_date", ASCENDING)], {}),
            ([("status", ASCENDING)], {})
        ]
    },
    "invoices": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["customer_id", "invoice_number", "invoice_date",
                            "due_date", "total_amount"],
                "properties": {
                    "customer_id": {"bsonType": "objectId"},
                    "subscription_id": {"bsonType": ["objectId", "null"]},
                    "invoice_number": {"bsonType": "string"},
                    "invoice_date": {"bsonType": "date"},
                    "due_date": {"bsonType": "date"},
                    "total_amount": {"bsonType": ["double", "decimal"]},
                    "tax_amount": {"bsonType": ["double", "decimal", "null"]},
                    "status": {"enum": ["draft", "sent", "paid", "overdue", "cancelled"]},
                    "pdf_url": {"bsonType": ["string", "null"]},
                    "created_at": {"bsonType": "date"}
                }
            }
        },
        "indexes": [
            ([("invoice_number", ASCENDING)], {"unique": True}),
            ([("customer_id", ASCENDING)], {}),
            ([("status", ASCENDING)], {}),
            ([("invoice_date", DESCENDING)], {})
        ]
    },
    "payments": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["customer_id", "stripe_payment_intent_id", "amount", "payment_status", "payment_date"],
                "properties": {
                    "customer_id": {"bsonType": "objectId"},
                    "subscription_id": {"bsonType": ["objectId", "null"]},
                    "stripe_payment_intent_id": {"bsonType": "string"},
                    "stripe_invoice_id": {"bsonType": ["string", "null"]},
                    "square_receipt_url": {"bsonType": ["string", "null"]},
                    "amount": {"bsonType": ["double", "decimal"]},
                    "currency": {"bsonType": "string"},
                    "payment_status": {"enum": ["completed", "pending", "failed", "refunded", "partially_refunded"]},
                    "payment_method": {"bsonType": ["string", "null"]},
                    "card_brand": {"bsonType": ["string", "null"]},
                    "last_4_digits": {"bsonType": ["string", "null"]},
                    "processing_fee": {"bsonType": ["double", "decimal", "null"]},
                    "net_amount": {"bsonType": ["double", "decimal", "null"]},
                    "refunded_amount": {"bsonType": ["double", "decimal", "null"]},
                    "payment_date": {"bsonType": "date"},
                    "notes": {"bsonType": ["string", "null"]},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"}
                }
            }
        },
        "indexes": [
            ([("stripe_payment_intent_id", ASCENDING)], {"unique": True}),
            ([("customer_id", ASCENDING)], {}),
            ([("payment_date", DESCENDING)], {}),
            ([("payment_status", ASCENDING)], {})
        ]
    },
    "translation_transactions": {
        "validator": {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["customer_id", "requester_id", "user_name", "transaction_date",
                            "units_consumed", "original_file_url", "source_language", "target_language"],
                "properties": {
                    "customer_id": {"bsonType": "objectId"},
                    "subscription_id": {"bsonType": ["objectId", "null"]},
                    "requester_id": {"bsonType": "string"},
                    "user_name": {"bsonType": "string"},
                    "transaction_date": {"bsonType": "date"},
                    "units_consumed": {"bsonType": "int"},
                    "original_file_url": {"bsonType": "string"},
                    "translated_file_url": {"bsonType": ["string", "null"]},
                    "source_language": {"bsonType": "string"},
                    "target_language": {"bsonType": "string"},
                    "status": {"enum": ["pending", "completed", "failed"]},
                    "error_message": {"bsonType": ["string", "null"]},
                    "created_at": {"bsonType": "date"},
                    "updated_at": {"bsonType": "date"}
                }
            }
        },
        "indexes": [
            ([("customer_id", ASCENDING)], {}),
            ([("subscription_id", ASCENDING)], {}),
            ([("transaction_date", DESCENDING)], {}),
            ([("status", ASCENDING)], {})
        ]
    }
}

def setup():
    client = MongoClient(MONGODB_URI)
    db = client.translation

    print(f"\nCreating {len(COLLECTIONS)} collections with validation and indexes\n")

    for name, config in COLLECTIONS.items():
        if name in db.list_collection_names():
            db[name].drop()

        db.create_collection(
            name,
            validator=config["validator"],
            validationLevel="moderate"
        )

        for index_spec, options in config["indexes"]:
            db[name].create_index(index_spec, **options)

        index_count = len(config["indexes"])
        print(f"✓ {name:30} ({index_count} indexes)")

    print(f"\n✓ Setup complete: {len(COLLECTIONS)} collections ready")

    client.close()

if __name__ == "__main__":
    setup()
