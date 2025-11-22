#!/usr/bin/env python3
"""
Remove Duplicate Users

This script:
1. Finds users with duplicate emails
2. Keeps the oldest user (first created_at)
3. Deletes newer duplicates
"""

import asyncio
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
import os

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/translation")

async def remove_duplicate_users():
    """Remove duplicate users."""
    client = AsyncIOMotorClient(MONGODB_URI)

    # Extract database name from URI
    db_name = MONGODB_URI.split("/")[-1] if "/" in MONGODB_URI else "translation"
    db = client[db_name]

    print(f"🔍 Analyzing users in database '{db_name}'...")

    # Find duplicate emails
    pipeline = [
        {'$group': {'_id': '$email', 'count': {'$sum': 1}, 'docs': {'$push': '$$ROOT'}}},
        {'$match': {'count': {'$gt': 1}}}
    ]

    duplicates = await db.users.aggregate(pipeline).to_list(length=None)

    if not duplicates:
        print("\n✅ No duplicate emails found")
        client.close()
        return

    print(f"\n⚠️  Found {len(duplicates)} emails with duplicates:")

    total_to_delete = 0

    for dup in duplicates:
        email = dup['_id']
        docs = dup['docs']
        count = len(docs)

        print(f"\n   Email: {email} ({count} duplicates)")

        # Sort by created_at (oldest first)
        docs_sorted = sorted(docs, key=lambda x: x.get('created_at', 0))

        # Keep the oldest
        keep = docs_sorted[0]
        delete = docs_sorted[1:]

        print(f"      Keeping: ID {keep['_id']} (created: {keep.get('created_at', 'N/A')})")
        print(f"      Deleting {len(delete)} duplicates:")

        for doc in delete:
            print(f"        - ID {doc['_id']} (created: {doc.get('created_at', 'N/A')})")
            total_to_delete += 1

    print(f"\n⚠️  Total users to delete: {total_to_delete}")

    # Confirm deletion
    response = input("\nProceed with deletion? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Deletion cancelled by user")
        client.close()
        return

    # Delete duplicates
    print("\n🗑️  Deleting duplicate users...")

    deleted_count = 0

    for dup in duplicates:
        docs = dup['docs']
        docs_sorted = sorted(docs, key=lambda x: x.get('created_at', 0))
        delete_ids = [doc['_id'] for doc in docs_sorted[1:]]

        result = await db.users.delete_many({'_id': {'$in': delete_ids}})
        deleted_count += result.deleted_count
        print(f"   ✓ Deleted {result.deleted_count} users for email {dup['_id']}")

    # Verify
    print(f"\n✅ Verification:")
    print(f"   Total deleted: {deleted_count}")

    # Check for remaining duplicates
    duplicates_after = await db.users.aggregate(pipeline).to_list(length=None)

    if not duplicates_after:
        print("   No duplicate emails remaining")
        print("\n🎉 SUCCESS! All duplicates removed")
    else:
        print(f"   ⚠️  WARNING: {len(duplicates_after)} duplicate emails still exist")

    client.close()

if __name__ == "__main__":
    asyncio.run(remove_duplicate_users())
