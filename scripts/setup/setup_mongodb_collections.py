#!/usr/bin/env python3
"""
MongoDB Collections Setup Script
Reads translation-schema.js and creates collections with validation, indexes, and initial data.

Usage:
    python setup_mongodb_collections.py
"""

import json
import re
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import CollectionInvalid, OperationFailure
import sys

# MongoDB Connection URI
MONGODB_URI = "mongodb://iris:Iris87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"
SCHEMA_FILE = "translation-schema.js"


def parse_js_schema(file_path):
    """
    Parse the JavaScript schema file and extract collection definitions.

    Args:
        file_path: Path to translation-schema.js

    Returns:
        Dictionary with collection schemas
    """
    print(f"📖 Reading schema file: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract the collections object from JavaScript
    # This is a simplified parser - assumes the structure in translation-schema.js
    collections_match = re.search(r'collections:\s*\{(.*?)\n\s*\},\s*\n\s*//\s*=+\s*\n\s*//\s*COMMON',
                                   content, re.DOTALL)

    if not collections_match:
        raise ValueError("Could not find collections definition in schema file")

    print("✅ Schema file parsed successfully")
    return content


def js_type_to_bson_type(js_type):
    """Convert JavaScript type to BSON type for JSON Schema validation."""
    type_map = {
        "String": "string",
        "Integer": "int",
        "Long": "long",
        "Decimal": "double",
        "Boolean": "bool",
        "Date": "date",
        "ObjectId": "objectId",
        "Object": "object",
        "Array": "array"
    }
    return type_map.get(js_type, "string")


def create_json_schema_validation(collection_name, fields):
    """
    Create MongoDB JSON Schema validation from field definitions.

    Args:
        collection_name: Name of the collection
        fields: Dictionary of field definitions

    Returns:
        JSON Schema validation object
    """
    properties = {}
    required = []

    for field_name, field_def in fields.items():
        if field_name == '_id':
            continue  # Skip _id as it's auto-generated

        if isinstance(field_def, dict):
            field_type = field_def.get('type')

            # Skip if it's an embedded document or array (we'll handle those separately)
            if field_type in ['Array', 'Object']:
                continue

            bson_type = js_type_to_bson_type(field_type)

            # For optional fields (not required), allow both the type and null
            is_required = field_def.get('required', False)
            if is_required:
                field_schema = {"bsonType": bson_type}
            else:
                # Allow null for optional fields
                field_schema = {"bsonType": [bson_type, "null"]}

            # Add description if present
            if 'description' in field_def:
                field_schema['description'] = field_def['description']

            # Add enum validation (only when value is not null)
            if 'enum' in field_def:
                # For optional fields with enums, we need to handle null separately
                if not is_required:
                    field_schema = {
                        "anyOf": [
                            {"bsonType": "null"},
                            {"bsonType": bson_type, "enum": field_def['enum']}
                        ]
                    }
                else:
                    field_schema['enum'] = field_def['enum']

            # Add pattern validation for strings (only when not null)
            elif 'pattern' in field_def and bson_type == 'string':
                if not is_required:
                    field_schema = {
                        "anyOf": [
                            {"bsonType": "null"},
                            {"bsonType": "string", "pattern": field_def['pattern']}
                        ]
                    }
                else:
                    field_schema['pattern'] = field_def['pattern']

            # Add maxLength for strings
            elif 'maxLength' in field_def and bson_type == 'string':
                if not is_required:
                    field_schema = {
                        "anyOf": [
                            {"bsonType": "null"},
                            {"bsonType": "string", "maxLength": field_def['maxLength']}
                        ]
                    }
                else:
                    field_schema['maxLength'] = field_def['maxLength']

            properties[field_name] = field_schema

            # Track required fields
            if is_required:
                required.append(field_name)

    schema = {
        "bsonType": "object",
        "properties": properties
    }

    if required:
        schema["required"] = required

    return {"$jsonSchema": schema}


def extract_collection_schemas(content):
    """Extract all collection schemas from the JS file content."""
    collections = {}

    # Define the collections we want to create based on translation-schema.js
    collection_definitions = {
        "system_config": {
            "fields": {
                "config_key": {"type": "String", "required": True},
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
                "username": {"type": "String", "required": True, "maxLength": 100},
                "email": {"type": "String", "required": True, "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"},
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
        "customers": {
            "fields": {
                "company_name": {"type": "String", "required": True, "maxLength": 255},
                "address": {"type": "String"},
                "contact_person": {"type": "String"},
                "phone_number": {"type": "String", "maxLength": 50},
                "company_url": {"type": "String", "maxLength": 500},
                "line_of_business": {"type": "String", "maxLength": 255},
                "created_at": {"type": "Date"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"company_name": 1}},
                {"fields": {"line_of_business": 1}},
                {"fields": {"company_name": "text"}}
            ]
        },
        "company_users": {
            "fields": {
                "user_id": {"type": "String", "required": True, "maxLength": 255},
                "customer_id": {"type": "ObjectId", "required": True},
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
                {"fields": {"customer_id": 1}},
                {"fields": {"email": 1}},
                {"fields": {"customer_id": 1, "email": 1}, "unique": True},
                {"fields": {"customer_id": 1, "permission_level": 1}}
            ]
        },
        "subscriptions": {
            "fields": {
                "customer_id": {"type": "ObjectId", "required": True},
                "subscription_unit": {"type": "String", "required": True, "enum": ["page", "word", "character"]},
                "units_per_subscription": {"type": "Integer", "required": True},
                "price_per_unit": {"type": "Decimal", "required": True},
                "promotional_units": {"type": "Integer"},
                "subscription_price": {"type": "Decimal", "required": True},
                "start_date": {"type": "Date", "required": True},
                "end_date": {"type": "Date"},
                "status": {"type": "String", "enum": ["active", "inactive", "expired"]},
                "created_at": {"type": "Date"},
                "updated_at": {"type": "Date"}
            },
            "indexes": [
                {"fields": {"customer_id": 1}},
                {"fields": {"customer_id": 1, "status": 1}},
                {"fields": {"start_date": 1}},
                {"fields": {"end_date": 1}},
                {"fields": {"status": 1}}
            ]
        },
        "invoices": {
            "fields": {
                "customer_id": {"type": "ObjectId", "required": True},
                "subscription_id": {"type": "ObjectId"},
                "invoice_number": {"type": "String", "required": True, "maxLength": 50},
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
                {"fields": {"invoice_date": -1}},
                {"fields": {"due_date": 1}}
            ]
        },
        "payments": {
            "fields": {
                "customer_id": {"type": "ObjectId", "required": True},
                "subscription_id": {"type": "ObjectId"},
                "stripe_payment_intent_id": {"type": "String", "required": True, "maxLength": 255},
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
                {"fields": {"customer_id": 1}},
                {"fields": {"subscription_id": 1}},
                {"fields": {"payment_date": -1}},
                {"fields": {"payment_status": 1}}
            ]
        },
        "translation_transactions": {
            "fields": {
                "customer_id": {"type": "ObjectId", "required": True},
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
                {"fields": {"customer_id": 1}},
                {"fields": {"subscription_id": 1}},
                {"fields": {"transaction_date": -1}},
                {"fields": {"customer_id": 1, "requester_id": 1}},
                {"fields": {"status": 1}},
                {"fields": {"source_language": 1, "target_language": 1}}
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
                {"fields": {"collection_name": 1, "record_id": 1}},
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
                "key_hash": {"type": "String", "required": True},
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
                {"fields": {"status": 1}},
                {"fields": {"expires_at": 1}}
            ]
        }
    }

    return collection_definitions


def create_collection_with_validation(db, collection_name, schema_def):
    """
    Create collection with JSON Schema validation.

    Args:
        db: MongoDB database object
        collection_name: Name of the collection
        schema_def: Schema definition dictionary
    """
    try:
        # Check if collection already exists
        if collection_name in db.list_collection_names():
            print(f"⚠️  Collection '{collection_name}' already exists, skipping creation")
            return False

        # Create JSON Schema validation
        validation_schema = create_json_schema_validation(collection_name, schema_def['fields'])

        # Create collection with validation
        db.create_collection(
            collection_name,
            validator=validation_schema,
            validationLevel='moderate',  # 'strict' or 'moderate'
            validationAction='error'     # 'error' or 'warn'
        )

        print(f"✅ Created collection: {collection_name}")
        return True

    except CollectionInvalid as e:
        print(f"⚠️  Collection '{collection_name}' creation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error creating collection '{collection_name}': {e}")
        return False


def create_indexes(db, collection_name, indexes_def):
    """
    Create indexes for a collection.

    Args:
        db: MongoDB database object
        collection_name: Name of the collection
        indexes_def: List of index definitions
    """
    collection = db[collection_name]

    for index_def in indexes_def:
        try:
            fields = index_def['fields']
            unique = index_def.get('unique', False)

            # Convert fields dict to list of tuples for pymongo
            index_fields = []
            for field, direction in fields.items():
                if field == "text":
                    # Text index
                    index_fields.append((field, TEXT))
                elif direction == 1:
                    index_fields.append((field, ASCENDING))
                elif direction == -1:
                    index_fields.append((field, DESCENDING))
                elif direction == "text":
                    index_fields.append((field, TEXT))

            # Create the index
            collection.create_index(index_fields, unique=unique)
            print(f"  📊 Created index on {collection_name}: {list(fields.keys())}")

        except Exception as e:
            print(f"  ⚠️  Error creating index on {collection_name}: {e}")


def insert_initial_data(db):
    """Insert initial configuration data."""
    print("\n📝 Inserting initial data...")

    # Initial system_config data
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
        },
        {
            "config_key": "default_subscription_units",
            "config_value": "1000",
            "config_type": "integer",
            "description": "Default units for new subscriptions",
            "is_sensitive": False,
            "updated_at": datetime.now(timezone.utc)
        },
        {
            "config_key": "price_per_page",
            "config_value": "0.10",
            "config_type": "string",
            "description": "Price per page for translation",
            "is_sensitive": False,
            "updated_at": datetime.now(timezone.utc)
        }
    ]

    try:
        result = db.system_config.insert_many(system_configs)
        print(f"  ✅ Inserted {len(result.inserted_ids)} system config entries")
    except Exception as e:
        print(f"  ⚠️  Error inserting system config: {e}")

    # Initial schema_versions data
    schema_version = {
        "version_number": "1.0.0",
        "description": "Initial database schema",
        "applied_at": datetime.now(timezone.utc),
        "applied_by": "setup_script"
    }

    try:
        result = db.schema_versions.insert_one(schema_version)
        print(f"  ✅ Inserted schema version: 1.0.0")
    except Exception as e:
        print(f"  ⚠️  Error inserting schema version: {e}")


def main():
    """Main setup function."""
    print("=" * 80)
    print("MongoDB Collections Setup for Translation Software")
    print("=" * 80)
    print()

    # Connect to MongoDB
    print(f"🔌 Connecting to MongoDB...")
    print(f"   URI: {MONGODB_URI.replace('Iris87201120', '***')}")

    try:
        client = MongoClient(MONGODB_URI)
        db = client[DATABASE_NAME]

        # Test connection
        client.server_info()
        print(f"✅ Connected to MongoDB successfully")
        print(f"   Database: {DATABASE_NAME}")
        print()

    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        sys.exit(1)

    # Parse schema file
    try:
        content = parse_js_schema(SCHEMA_FILE)
        collections_def = extract_collection_schemas(content)
        print(f"✅ Found {len(collections_def)} collections to create")
        print()

    except Exception as e:
        print(f"❌ Failed to parse schema file: {e}")
        sys.exit(1)

    # Create collections with validation
    print("📦 Creating collections with validation...")
    created_count = 0

    for collection_name, schema_def in collections_def.items():
        if create_collection_with_validation(db, collection_name, schema_def):
            created_count += 1

            # Create indexes
            if 'indexes' in schema_def:
                create_indexes(db, collection_name, schema_def['indexes'])

    print()
    print(f"✅ Created {created_count} new collections")

    # Insert initial data
    if created_count > 0:
        insert_initial_data(db)

    # Summary
    print()
    print("=" * 80)
    print("✅ Setup Complete!")
    print("=" * 80)
    print(f"Database: {DATABASE_NAME}")
    print(f"Collections created: {created_count}")
    print(f"Total collections: {len(db.list_collection_names())}")
    print()
    print("All collections:")
    for name in sorted(db.list_collection_names()):
        count = db[name].count_documents({})
        print(f"  - {name:30} ({count} documents)")
    print()
    print("🎉 MongoDB setup completed successfully!")
    print()


if __name__ == "__main__":
    main()
