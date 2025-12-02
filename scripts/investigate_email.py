"""
Database Investigation Script for danishevsky@gmail.com
Searches all collections and reports database state.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime
import json


MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
TARGET_EMAIL = "danishevsky@gmail.com"


async def investigate_email():
    """Comprehensive investigation of email across all collections."""

    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.translation

    print("=" * 80)
    print(f"DATABASE INVESTIGATION: {TARGET_EMAIL}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 80)
    print()

    # Step 1: Get all collection names
    collection_names = await db.list_collection_names()
    print(f"📊 Total Collections in Database: {len(collection_names)}")
    print(f"Collections: {', '.join(sorted(collection_names))}")
    print()

    # Step 2: Search each collection for the email
    total_matches = 0
    collections_with_matches = []

    print("=" * 80)
    print("SEARCHING ALL COLLECTIONS FOR EMAIL")
    print("=" * 80)
    print()

    for collection_name in sorted(collection_names):
        collection = db[collection_name]

        # Try different field names where email might be stored
        email_fields = ['email', 'user_email', 'owner_email', 'admin_email', 'contact_email']

        matches = []
        for field in email_fields:
            query = {field: TARGET_EMAIL}
            cursor = collection.find(query)
            async for doc in cursor:
                # Add field name to track which field matched
                doc['_matched_field'] = field
                matches.append(doc)

        if matches:
            total_matches += len(matches)
            collections_with_matches.append(collection_name)

            print(f"🔴 COLLECTION: {collection_name}")
            print(f"   Matches Found: {len(matches)}")
            print()

            for idx, doc in enumerate(matches, 1):
                matched_field = doc.pop('_matched_field')
                print(f"   📄 Document #{idx}")
                print(f"   Matched Field: {matched_field}")
                print(f"   Document ID: {doc.get('_id')}")

                # Show key fields
                key_fields = ['email', 'user_email', 'company_id', 'company_name',
                             'role', 'status', 'created_at', 'updated_at']
                for key in key_fields:
                    if key in doc:
                        value = doc[key]
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        print(f"   {key}: {value}")

                # Show full document (formatted)
                print(f"   Full Document:")
                doc_copy = doc.copy()
                # Convert datetime objects for JSON serialization
                for key, value in doc_copy.items():
                    if isinstance(value, datetime):
                        doc_copy[key] = value.isoformat()
                print(f"   {json.dumps(doc_copy, indent=6, default=str)}")
                print()

    print("=" * 80)
    print(f"SUMMARY: Found {total_matches} total matches across {len(collections_with_matches)} collections")
    if collections_with_matches:
        print(f"Collections with matches: {', '.join(collections_with_matches)}")
    print("=" * 80)
    print()

    # Step 3: Check unique indexes on email fields
    print("=" * 80)
    print("UNIQUE INDEX ANALYSIS")
    print("=" * 80)
    print()

    # Focus on collections that commonly have email fields
    email_collections = ['users', 'company_users', 'iris-admins', 'companies']

    for collection_name in email_collections:
        if collection_name not in collection_names:
            print(f"⚠️  Collection '{collection_name}' does not exist")
            print()
            continue

        collection = db[collection_name]
        indexes = await collection.index_information()

        print(f"📑 Collection: {collection_name}")
        print(f"   Total Indexes: {len(indexes)}")

        # Check for unique indexes on email fields
        email_indexes = []
        for index_name, index_info in indexes.items():
            keys = index_info.get('key', [])
            is_unique = index_info.get('unique', False)

            # Check if any key contains 'email'
            for key_tuple in keys:
                field_name = key_tuple[0] if isinstance(key_tuple, tuple) else key_tuple
                if 'email' in field_name.lower():
                    email_indexes.append({
                        'name': index_name,
                        'field': field_name,
                        'unique': is_unique,
                        'info': index_info
                    })

        if email_indexes:
            print(f"   📧 Email-Related Indexes:")
            for idx_info in email_indexes:
                print(f"      • Index: {idx_info['name']}")
                print(f"        Field: {idx_info['field']}")
                print(f"        Unique: {idx_info['unique']}")
                print(f"        Full Info: {json.dumps(idx_info['info'], indent=10, default=str)}")
        else:
            print(f"   No email-related indexes found")
        print()

    # Step 4: Detailed count per collection
    print("=" * 80)
    print("PER-COLLECTION EMAIL COUNT")
    print("=" * 80)
    print()

    for collection_name in sorted(collection_names):
        collection = db[collection_name]

        # Count for each email field
        email_fields = ['email', 'user_email', 'owner_email', 'admin_email', 'contact_email']

        field_counts = {}
        for field in email_fields:
            count = await collection.count_documents({field: TARGET_EMAIL})
            if count > 0:
                field_counts[field] = count

        if field_counts:
            print(f"📊 {collection_name}:")
            for field, count in field_counts.items():
                print(f"   {field}: {count} document(s)")
            print()

    # Step 5: Root cause hypothesis
    print("=" * 80)
    print("ROOT CAUSE HYPOTHESIS")
    print("=" * 80)
    print()

    if total_matches == 0:
        print("✅ No documents found with this email.")
        print("   Hypothesis: Email was successfully deleted, or error is from cache/session.")
    elif total_matches == 1:
        print(f"⚠️  Exactly 1 document found.")
        print(f"   Location: {collections_with_matches[0]}")
        print("   Hypothesis: Single active record - expected state if user exists.")
    else:
        print(f"🔴 MULTIPLE DOCUMENTS FOUND: {total_matches} total")
        print(f"   Across collections: {', '.join(collections_with_matches)}")
        print()
        print("   Possible Issues:")
        print("   1. Orphaned records in multiple collections")
        print("   2. Duplicate entries violating business logic")
        print("   3. Incomplete deletion (some collections missed)")
        print("   4. Multiple company associations")
        print()
        print("   Recommended Action:")
        print("   - Review each document's company_id")
        print("   - Check if records should be consolidated")
        print("   - Verify deletion logic covers all collections")

    print()
    print("=" * 80)
    print("INVESTIGATION COMPLETE")
    print("=" * 80)

    client.close()


if __name__ == "__main__":
    asyncio.run(investigate_email())
