#!/usr/bin/env python3
"""
Quick status check for iris-admins collection.
Shows current state before/after migration.
"""

import sys
from pathlib import Path
from pymongo import MongoClient
from bson import ObjectId

# MongoDB connection details
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"
COLLECTION_NAME = "iris-admins"

def main():
    print("=" * 80)
    print("IRIS-ADMINS COLLECTION STATUS CHECK")
    print("=" * 80)

    try:
        # Connect to MongoDB
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[DATABASE_NAME]
        collection = db[COLLECTION_NAME]

        # Check if collection exists
        if COLLECTION_NAME not in db.list_collection_names():
            print(f"❌ Collection '{COLLECTION_NAME}' does not exist!")
            sys.exit(1)

        print(f"✓ Collection '{COLLECTION_NAME}' exists\n")

        # Count total documents
        total_docs = collection.count_documents({})
        print(f"Total admin users: {total_docs}\n")

        # List all admin users
        print("Admin Users:")
        print("-" * 80)

        for doc in collection.find():
            print(f"User: {doc.get('user_name')}")
            print(f"  - _id: {doc.get('_id')}")
            print(f"  - user_email: {doc.get('user_email', 'NOT SET')}")
            print(f"  - has password: {'Yes' if doc.get('password') else 'No'}")
            print(f"  - password hash: {doc.get('password', '')[:30]}...")
            print(f"  - created_at: {doc.get('created_at')}")
            print(f"  - login_date: {doc.get('login_date')}")
            print()

        # List indexes
        print("Indexes:")
        print("-" * 80)

        for idx in collection.list_indexes():
            unique = " (UNIQUE)" if idx.get('unique') else ""
            print(f"  - {idx.get('name')}: {idx.get('key')}{unique}")

        print()

        # Check migration status
        print("Migration Status:")
        print("-" * 80)

        # Check if existing admin has user_email
        existing_admin = collection.find_one({
            "_id": ObjectId("68f3a1c1e44710d091e002e5")
        })

        if existing_admin:
            has_email = 'user_email' in existing_admin
            print(f"  ✓ Existing admin (iris-admin) found")
            print(f"  {'✓' if has_email else '❌'} user_email field: {existing_admin.get('user_email', 'NOT SET')}")
        else:
            print(f"  ❌ Existing admin (iris-admin) not found")

        # Check if new admin exists
        new_admin = collection.find_one({
            "user_email": "danishevsky@gmail.com"
        })

        if new_admin:
            print(f"  ✓ New admin (Vladimir Danishevsky) exists")
        else:
            print(f"  ❌ New admin (Vladimir Danishevsky) not found")

        # Check if unique index exists
        index_names = [idx.get('name') for idx in collection.list_indexes()]
        has_unique_index = 'user_email_unique' in index_names
        print(f"  {'✓' if has_unique_index else '❌'} user_email_unique index exists")

        print()

        # Determine if migration needed
        migration_needed = not (existing_admin and 'user_email' in existing_admin and new_admin and has_unique_index)

        if migration_needed:
            print("🔴 MIGRATION NEEDED - Run: python scripts/migrations/migrate_iris_admins_add_email.py")
        else:
            print("🟢 MIGRATION COMPLETE - All changes applied successfully")

        print("=" * 80)

        client.close()
        sys.exit(0 if not migration_needed else 1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
