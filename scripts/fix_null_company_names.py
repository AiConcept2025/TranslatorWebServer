#!/usr/bin/env python3
"""
Fix null company_name values in users collection.

This script:
1. Identifies users with null company_name
2. Assigns appropriate company_name based on email/user type
3. Creates companies if needed
4. Updates user records
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/translation")

async def fix_null_company_names():
    """Fix null company_name values in users."""
    client = AsyncIOMotorClient(MONGODB_URI)

    # Extract database name from URI
    db_name = MONGODB_URI.split("/")[-1] if "/" in MONGODB_URI else "translation"
    db = client[db_name]

    print(f"🔍 Analyzing users in database '{db_name}'...")

    # Find users with null company_name
    null_company_users = await db.users.find({"company_name": None}).to_list(length=None)

    if not null_company_users:
        print("✅ No users with null company_name found")
        client.close()
        return

    print(f"\n⚠️  Found {len(null_company_users)} users with null company_name:")
    for user in null_company_users:
        print(f"   - {user.get('email')} ({user.get('full_name', 'Unknown')})")

    print("\n🔧 Assigning company_name based on email patterns...")

    updates = []

    for user in null_company_users:
        email = user.get('email', '')
        full_name = user.get('full_name', '')

        # Determine company_name based on email/name pattern
        if 'testcorp' in email.lower():
            company_name = 'TestCorp'
        elif 'individual' in email.lower() or 'individual' in full_name.lower():
            company_name = 'Individual Users'
        elif 'example.com' in email:
            company_name = 'Example Company'
        else:
            # Default fallback
            company_name = 'General Users'

        updates.append({
            'email': email,
            'old_company_name': None,
            'new_company_name': company_name
        })

        print(f"   ✓ {email} → {company_name}")

    # Create companies if they don't exist
    print("\n🏢 Ensuring companies exist...")
    unique_companies = set(u['new_company_name'] for u in updates)

    for company_name in unique_companies:
        existing = await db.companies.find_one({"company_name": company_name})
        if not existing:
            await db.companies.insert_one({
                "company_name": company_name,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            })
            print(f"   ✓ Created company: {company_name}")
        else:
            print(f"   ℹ️  Company already exists: {company_name}")

    # Update user records
    print("\n📝 Updating user records...")

    for update in updates:
        result = await db.users.update_one(
            {"email": update['email']},
            {
                "$set": {
                    "company_name": update['new_company_name'],
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.modified_count > 0:
            print(f"   ✓ Updated {update['email']}")
        else:
            print(f"   ⚠️  No update for {update['email']}")

    # Verify all users now have company_name
    print("\n✅ Verification:")
    remaining_null = await db.users.count_documents({"company_name": None})
    total_users = await db.users.count_documents({})

    print(f"   Total users: {total_users}")
    print(f"   Users with null company_name: {remaining_null}")

    if remaining_null == 0:
        print("\n🎉 SUCCESS! All users now have company_name assigned")
    else:
        print(f"\n⚠️  WARNING: {remaining_null} users still have null company_name")

    client.close()

if __name__ == "__main__":
    asyncio.run(fix_null_company_names())
