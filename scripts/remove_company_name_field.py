#!/usr/bin/env python3
"""
Remove company_name Field from Users Collection

This script completely removes the company_name field from all users
in the 'users' collection (individual users don't need this field).
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

async def remove_company_name_field():
    """Remove company_name field from all users."""
    client = AsyncIOMotorClient(MONGODB_URI)

    # Extract database name from URI
    db_name = MONGODB_URI.split("/")[-1] if "/" in MONGODB_URI else "translation"
    db = client[db_name]

    print(f"🔧 Removing company_name field from users in database '{db_name}'...")

    # Remove company_name field from all users
    result = await db.users.update_many(
        {},  # All users
        {
            "$unset": {
                "company_name": ""  # Remove the field entirely
            },
            "$set": {
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    print(f"✅ Updated {result.modified_count} users")
    print(f"   Total users matched: {result.matched_count}")

    # Verify
    users_with_company = await db.users.count_documents({"company_name": {"$exists": True}})
    total_users = await db.users.count_documents({})

    print(f"\n📊 Verification:")
    print(f"   Total users: {total_users}")
    print(f"   Users with company_name field: {users_with_company}")
    print(f"   Users without company_name field: {total_users - users_with_company}")

    if users_with_company == 0:
        print("\n🎉 SUCCESS! company_name field removed from all individual users")
    else:
        print(f"\n⚠️  WARNING: {users_with_company} users still have company_name field")

    # Show a sample user
    sample_user = await db.users.find_one({})
    if sample_user:
        print(f"\n📋 Sample user fields: {list(sample_user.keys())}")

    client.close()

if __name__ == "__main__":
    asyncio.run(remove_company_name_field())
