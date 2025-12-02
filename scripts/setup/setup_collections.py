#!/usr/bin/env python3
"""
MongoDB Collections Setup Script
Reads schema.ts and creates collections with validation and indexes.
"""

import re
import json
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid
from bson.decimal128 import Decimal128
import sys

# MongoDB Configuration
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"
SCHEMA_FILE = "schema.ts"

# Collections to create (in order)
COLLECTIONS_TO_CREATE = [
    "system_config",
    "schema_versions",
    "system_admins",
    "system_activity_log",
    "company",
    "company_users",
    "subscriptions",
    "invoices",
    "payments",
    "translation_transactions",
    "audit_logs",
    "notification_logs",
    "api_keys"
]


def print_status(message, status="info"):
    """Print colored status messages."""
    colors = {
        "info": "\033[94m",
        "success": "\033[92m",
        "warning": "\033[93m",
        "error": "\033[91m",
        "reset": "\033[0m"
    }

    symbols = {
        "info": "ℹ",
        "success": "✓",
        "warning": "⚠",
        "error": "✗"
    }

    color = colors.get(status, colors["info"])
    symbol = symbols.get(status, "•")
    print(f"{color}{symbol} {message}{colors['reset']}")


def js_type_to_bson(js_type):
    """Convert JavaScript/TypeScript types to BSON types."""
    type_map = {
        "String": "string",
        "Integer": "int",
        "Long": "long",
        "Decimal": ["double", "decimal"],  # Accept both double and Decimal128
        "Boolean": "bool",
        "Date": "date",
        "ObjectId": "objectId",
        "Object": "object",
        "Array": "array"
    }
    return type_map.get(js_type, "string")


def parse_schema_file(file_path):
    """Parse the schema.ts file and extract collection definitions."""
    print_status(f"Reading schema file: {file_path}", "info")

    with open(file_path, 'r') as f:
        content = f.read()

    # Parse collections object from JavaScript
    collections_match = re.search(
        r'collections:\s*\{(.*?)\n\s*\},\s*\n\s*//\s*=+',
        content,
        re.DOTALL
    )

    if not collections_match:
        raise ValueError("Could not find collections definition in schema file")

    print_status("Schema file parsed successfully", "success")
    return content


def create_json_schema(collection_name, field_def):
    """Create MongoDB JSON Schema validation."""
    properties = {}
    required = []

    # Handle different field definition formats
    fields = field_def.get('fields', field_def)

    for field_name, field_spec in fields.items():
        if field_name == '_id' or field_name == 'fields':
            continue

        if not isinstance(field_spec, dict):
            continue

        field_type = field_spec.get('type')
        if not field_type:
            continue

        # Skip embedded arrays and objects for now
        if field_type in ['Array', 'Object']:
            continue

        bson_type = js_type_to_bson(field_type)
        is_required = field_spec.get('required', False)

        # Build field schema
        if is_required:
            # Handle types that are already lists (like Decimal)
            if isinstance(bson_type, list):
                field_schema = {"bsonType": bson_type}
            else:
                field_schema = {"bsonType": bson_type}
            required.append(field_name)
        else:
            # For optional fields, add null to the list
            if isinstance(bson_type, list):
                field_schema = {"bsonType": bson_type + ["null"]}
            else:
                field_schema = {"bsonType": [bson_type, "null"]}

        # Add enum validation
        if 'enum' in field_spec:
            if is_required:
                field_schema['enum'] = field_spec['enum']
            else:
                field_schema = {
                    "anyOf": [
                        {"bsonType": "null"},
                        {"bsonType": bson_type, "enum": field_spec['enum']}
                    ]
                }

        # Add pattern validation
        elif 'pattern' in field_spec and bson_type == 'string':
            if is_required:
                field_schema['pattern'] = field_spec['pattern']
            else:
                field_schema = {
                    "anyOf": [
                        {"bsonType": "null"},
                        {"bsonType": "string", "pattern": field_spec['pattern']}
                    ]
                }

        # Add maxLength for strings
        elif 'maxLength' in field_spec and bson_type == 'string':
            if is_required:
                field_schema['maxLength'] = field_spec['maxLength']
            else:
                field_schema = {
                    "anyOf": [
                        {"bsonType": "null"},
                        {"bsonType": "string", "maxLength": field_spec['maxLength']}
                    ]
                }

        properties[field_name] = field_schema

    schema = {
        "bsonType": "object",
        "properties": properties
    }

    if required:
        schema["required"] = required

    return {"$jsonSchema": schema}


def get_collection_schema(collection_name):
    """Get the schema definition for a specific collection."""
    schemas = {
        "system_config": {
            "fields": {
                "config_key": {"type": "String", "required": True, "unique": True, "maxLength": 100},
                "config_value": {"type": "String", "required": True},
                "config_type": {"type": "String", "enum": ["string", "integer", "boolean", "json"]},
                "description": {"type": "String"},
                "is_sensitive": {"type": "Boolean"},
                "updated_by": {"type": "String"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"config_key": 1}, "unique": True}
            ]
        },
        "schema_versions": {
            "fields": {
                "version_number": {"type": "String", "required": True},
                "description": {"type": "String"},
                "applied_at": {"type": "Date", "required": True},
                "applied_by": {"type": "String"}
            },
            "indexes": [
                {"fields": {"version_number": 1}},
                {"fields": {"applied_at": -1}}
            ]
        },
        "system_admins": {
            "fields": {
                "username": {"type": "String", "required": True, "unique": True, "maxLength": 100},
                "email": {"type": "String", "required": True, "unique": True, "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"},
                "password_hash": {"type": "String", "required": True},
                "full_name": {"type": "String"},
                "role": {"type": "String", "enum": ["super_admin", "admin", "support"]},
                "status": {"type": "String", "enum": ["active", "inactive", "suspended"]},
                "last_login": {"type": "Date"},
                "created_at": {"type": "Date"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"username": 1}, "unique": True},
                {"fields": {"email": 1}, "unique": True},
                {"fields": {"status": 1}}
            ]
        },
        "system_activity_log": {
            "fields": {
                "admin_id": {"type": "ObjectId"},
                "activity_type": {"type": "String", "required": True},
                "description": {"type": "String"},
                "ip_address": {"type": "String"},
                "user_agent": {"type": "String"},
                "created_at": {"type": "Date", "required": True}
            },
            "indexes": [
                {"fields": {"admin_id": 1}},
                {"fields": {"created_at": -1}},
                {"fields": {"activity_type": 1}}
            ]
        },
        "company": {
            "fields": {
                "company_id": {"type": "String"},
                "description": {"type": "String"},
                "company_name": {"type": "String", "required": True},
                "contact_person": {"type": "String"},
                "phone_number": {"type": "String"},
                "company_url": {"type": "String"},
                "line_of_business": {"type": "String"},
                "created_at": {"type": "Date"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"company_name": 1}},
                {"fields": {"line_of_business": 1}}
            ]
        },
        "company_users": {
            "fields": {
                "user_id": {"type": "String", "required": True, "unique": True, "maxLength": 255},
                "company_id": {"type": "ObjectId", "required": True},
                "user_name": {"type": "String", "required": True, "maxLength": 255},
                "email": {"type": "String", "required": True, "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"},
                "phone_number": {"type": "String", "maxLength": 50},
                "permission_level": {"type": "String", "enum": ["admin", "user"]},
                "status": {"type": "String", "enum": ["active", "inactive", "suspended"]},
                "password_hash": {"type": "String"},
                "last_login": {"type": "Date"},
                "created_at": {"type": "Date"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"user_id": 1}, "unique": True},
                {"fields": {"company_id": 1}},
                {"fields": {"email": 1}},
                {"fields": {"company_id": 1, "email": 1}, "unique": True}
            ]
        },
        "subscriptions": {
            "fields": {
                "company_id": {"type": "ObjectId", "required": True},
                "subscription_unit": {"type": "String", "required": True, "enum": ["page", "word", "character"]},
                "units_per_subscription": {"type": "Integer", "required": True},
                "price_per_unit": {"type": "Decimal", "required": True},
                "promotional_units": {"type": "Integer"},
                "discount": {"type": "Decimal"},
                "subscription_price": {"type": "Decimal", "required": True},
                "start_date": {"type": "Date", "required": True},
                "end_date": {"type": "Date"},
                "status": {"type": "String", "enum": ["active", "inactive", "expired"]},
                "created_at": {"type": "Date"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"company_id": 1}},
                {"fields": {"company_id": 1, "status": 1}},
                {"fields": {"start_date": 1}},
                {"fields": {"status": 1}}
            ]
        },
        "invoices": {
            "fields": {
                "customer_id": {"type": "ObjectId", "required": True},
                "subscription_id": {"type": "ObjectId"},
                "invoice_number": {"type": "String", "required": True, "unique": True, "maxLength": 50},
                "invoice_date": {"type": "Date", "required": True},
                "due_date": {"type": "Date", "required": True},
                "total_amount": {"type": "Decimal", "required": True},
                "tax_amount": {"type": "Decimal"},
                "status": {"type": "String", "enum": ["draft", "sent", "paid", "overdue", "cancelled"]},
                "pdf_url": {"type": "String"},
                "created_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"invoice_number": 1}, "unique": True},
                {"fields": {"customer_id": 1}},
                {"fields": {"status": 1}},
                {"fields": {"invoice_date": -1}}
            ]
        },
        "payments": {
            "fields": {
                "company_id": {"type": "ObjectId", "required": True},
                "subscription_id": {"type": "ObjectId"},
                "stripe_payment_intent_id": {"type": "String", "required": True, "unique": True, "maxLength": 255},
                "stripe_invoice_id": {"type": "String"},
                "square_receipt_url": {"type": "String"},
                "amount": {"type": "Decimal", "required": True},
                "currency": {"type": "String", "maxLength": 3},
                "payment_status": {"type": "String", "required": True, "enum": ["completed", "pending", "failed", "refunded", "partially_refunded"]},
                "payment_method": {"type": "String"},
                "card_brand": {"type": "String"},
                "last_4_digits": {"type": "String", "maxLength": 4},
                "processing_fee": {"type": "Decimal"},
                "net_amount": {"type": "Decimal"},
                "refunded_amount": {"type": "Decimal"},
                "payment_date": {"type": "Date", "required": True},
                "notes": {"type": "String"},
                "created_at": {"type": "Date"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"stripe_payment_intent_id": 1}, "unique": True},
                {"fields": {"company_id": 1}},
                {"fields": {"payment_date": -1}},
                {"fields": {"payment_status": 1}}
            ]
        },
        "translation_transactions": {
            "fields": {
                "company_id": {"type": "ObjectId", "required": True},
                "subscription_id": {"type": "ObjectId"},
                "requester_id": {"type": "String", "required": True},
                "user_name": {"type": "String", "required": True},
                "transaction_date": {"type": "Date", "required": True},
                "units_consumed": {"type": "Integer", "required": True},
                "original_file_url": {"type": "String", "required": True},
                "translated_file_url": {"type": "String"},
                "source_language": {"type": "String", "required": True, "maxLength": 10},
                "target_language": {"type": "String", "required": True, "maxLength": 10},
                "status": {"type": "String", "enum": ["pending", "completed", "failed"]},
                "error_message": {"type": "String"},
                "created_at": {"type": "Date"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"company_id": 1}},
                {"fields": {"subscription_id": 1}},
                {"fields": {"transaction_date": -1}},
                {"fields": {"status": 1}}
            ]
        },
        "audit_logs": {
            "fields": {
                "user_id": {"type": "String"},
                "customer_id": {"type": "ObjectId"},
                "action": {"type": "String", "required": True},
                "collection_name": {"type": "String"},
                "record_id": {"type": "String"},
                "ip_address": {"type": "String"},
                "timestamp": {"type": "Date", "required": True}
            },
            "indexes": [
                {"fields": {"user_id": 1}},
                {"fields": {"customer_id": 1}},
                {"fields": {"timestamp": -1}},
                {"fields": {"action": 1}}
            ]
        },
        "notification_logs": {
            "fields": {
                "customer_id": {"type": "ObjectId"},
                "user_id": {"type": "String"},
                "notification_type": {"type": "String", "required": True},
                "subject": {"type": "String"},
                "status": {"type": "String"},
                "sent_at": {"type": "Date", "required": True}
            },
            "indexes": [
                {"fields": {"customer_id": 1}},
                {"fields": {"user_id": 1}},
                {"fields": {"sent_at": -1}},
                {"fields": {"notification_type": 1}}
            ]
        },
        "api_keys": {
            "fields": {
                "customer_id": {"type": "ObjectId", "required": True},
                "key_hash": {"type": "String", "required": True, "unique": True},
                "key_name": {"type": "String"},
                "status": {"type": "String", "enum": ["active", "inactive", "revoked"]},
                "created_by": {"type": "String"},
                "last_used": {"type": "Date"},
                "expires_at": {"type": "Date"},
                "created_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"key_hash": 1}, "unique": True},
                {"fields": {"customer_id": 1}},
                {"fields": {"status": 1}}
            ]
        }
    }

    return schemas.get(collection_name)


def create_collection(db, collection_name):
    """Create a single collection with validation and indexes."""
    print_status(f"Creating collection: {collection_name}", "info")

    # Check if collection already exists
    if collection_name in db.list_collection_names():
        print_status(f"Collection '{collection_name}' already exists, dropping...", "warning")
        db.drop_collection(collection_name)

    # Get schema definition
    schema_def = get_collection_schema(collection_name)
    if not schema_def:
        print_status(f"No schema definition found for '{collection_name}'", "error")
        return False

    try:
        # Create JSON Schema validation
        validation_schema = create_json_schema(collection_name, schema_def)

        # Create collection with validation
        db.create_collection(
            collection_name,
            validator=validation_schema,
            validationLevel='moderate',
            validationAction='error'
        )

        print_status(f"Created collection: {collection_name}", "success")

        # Create indexes
        if 'indexes' in schema_def:
            create_indexes(db, collection_name, schema_def['indexes'])

        return True

    except Exception as e:
        print_status(f"Error creating collection '{collection_name}': {e}", "error")
        return False


def create_indexes(db, collection_name, indexes_def):
    """Create indexes for a collection."""
    collection = db[collection_name]

    for index_def in indexes_def:
        try:
            fields = index_def['fields']
            unique = index_def.get('unique', False)

            # Convert fields dict to list of tuples
            index_fields = []
            for field, direction in fields.items():
                if direction == 1:
                    index_fields.append((field, ASCENDING))
                elif direction == -1:
                    index_fields.append((field, DESCENDING))

            # Create index
            collection.create_index(index_fields, unique=unique)
            index_name = "_".join([f"{k}_{v}" for k, v in fields.items()])
            print_status(f"  Created index: {index_name}", "success")

        except Exception as e:
            print_status(f"  Error creating index: {e}", "warning")


def insert_initial_data(db):
    """Insert initial configuration data."""
    print_status("Inserting initial data...", "info")

    # System config entries
    system_configs = [
        {
            "config_key": "app_version",
            "config_value": "1.0.0",
            "config_type": "string",
            "description": "Application version",
            "is_sensitive": False,
            "updated_at": datetime.now(timezone.utc)
        },
        {
            "config_key": "max_upload_size_mb",
            "config_value": "100",
            "config_type": "integer",
            "description": "Maximum file upload size in MB",
            "is_sensitive": False,
            "updated_at": datetime.now(timezone.utc)
        }
    ]

    try:
        result = db.system_config.insert_many(system_configs)
        print_status(f"Inserted {len(result.inserted_ids)} system config entries", "success")
    except Exception as e:
        print_status(f"Error inserting system config: {e}", "warning")

    # Schema version
    schema_version = {
        "version_number": "1.0.0",
        "description": "Initial database schema from schema.ts",
        "applied_at": datetime.now(timezone.utc),
        "applied_by": "setup_collections.py"
    }

    try:
        result = db.schema_versions.insert_one(schema_version)
        print_status(f"Inserted schema version: 1.0.0", "success")
    except Exception as e:
        print_status(f"Error inserting schema version: {e}", "warning")


def main():
    """Main setup function."""
    print("\n" + "="*70)
    print("MongoDB Collections Setup from schema.ts")
    print("="*70 + "\n")

    # Connect to MongoDB
    print_status(f"Connecting to MongoDB...", "info")
    print_status(f"Database: {DATABASE_NAME}", "info")

    try:
        client = MongoClient(MONGODB_URI)
        db = client[DATABASE_NAME]
        client.server_info()
        print_status("Connected to MongoDB successfully", "success")
        print()
    except Exception as e:
        print_status(f"Failed to connect to MongoDB: {e}", "error")
        sys.exit(1)

    # Parse schema file
    try:
        parse_schema_file(SCHEMA_FILE)
        print()
    except Exception as e:
        print_status(f"Failed to parse schema file: {e}", "error")
        sys.exit(1)

    # Create collections
    print_status(f"Creating {len(COLLECTIONS_TO_CREATE)} collections...", "info")
    print()

    created_count = 0
    for collection_name in COLLECTIONS_TO_CREATE:
        if create_collection(db, collection_name):
            created_count += 1
        print()

    # Insert initial data
    insert_initial_data(db)
    print()

    # Summary
    print("="*70)
    print_status("Setup Complete!", "success")
    print("="*70)
    print(f"Collections created: {created_count}/{len(COLLECTIONS_TO_CREATE)}")
    print(f"Total collections in database: {len(db.list_collection_names())}")
    print()

    # List all collections
    print("Collections:")
    for name in sorted(db.list_collection_names()):
        count = db[name].count_documents({})
        print(f"  ✓ {name:35} ({count} documents)")
    print()


if __name__ == "__main__":
    main()
