#!/usr/bin/env python3
"""
Reset Individual Users to Have NULL company_name

This script updates users in the 'users' collection to have NULL company_name
for individual users (users not associated with a company).
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

async def reset_individual_users():
    """Reset individual users to have NULL company_name."""
    client = AsyncIOMotorClient(MONGODB_URI)

    # Extract database name from URI
    db_name = MONGODB_URI.split("/")[-1] if "/" in MONGODB_URI else "translation"
    db = client[db_name]

    print(f"🔧 Resetting individual users in database '{db_name}'...")

    # Update all users in 'users' collection to have NULL company_name
    # (These are individual users, not company users)
    result = await db.users.update_many(
        {},  # All users in this collection
        {
            "$set": {
                "company_name": None,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )

    print(f"✅ Updated {result.modified_count} users to have NULL company_name")
    print(f"   Total users matched: {result.matched_count}")

    # Verify
    users_with_company = await db.users.count_documents({"company_name": {"$ne": None}})
    total_users = await db.users.count_documents({})

    print(f"\n📊 Verification:")
    print(f"   Total users: {total_users}")
    print(f"   Users with company_name: {users_with_company}")
    print(f"   Users with NULL company_name: {total_users - users_with_company}")

    if users_with_company == 0:
        print("\n🎉 SUCCESS! All individual users now have NULL company_name")
    else:
        print(f"\n⚠️  WARNING: {users_with_company} users still have non-NULL company_name")

    client.close()

if __name__ == "__main__":
    asyncio.run(reset_individual_users())
