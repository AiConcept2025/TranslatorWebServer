#!/usr/bin/env python3
"""
Create Missing Companies for Orphaned Users

This script:
1. Identifies users with company_name that doesn't exist in companies collection
2. Creates those missing companies
3. Verifies referential integrity
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

async def create_missing_companies():
    """Create missing companies for orphaned users."""
    client = AsyncIOMotorClient(MONGODB_URI)

    # Extract database name from URI
    db_name = MONGODB_URI.split("/")[-1] if "/" in MONGODB_URI else "translation"
    db = client[db_name]

    print(f"🔍 Analyzing database '{db_name}'...")

    # Get all companies
    companies = await db.companies.find({}).to_list(length=None)
    company_names_set = set(c.get('company_name') for c in companies if c.get('company_name'))
    print(f"   Found {len(company_names_set)} existing companies")

    # Get all users
    users = await db.users.find({}).to_list(length=None)
    user_company_names_set = set(u.get('company_name') for u in users if u.get('company_name'))
    print(f"   Found {len(users)} users referencing {len(user_company_names_set)} unique companies")

    # Find missing companies
    missing_companies = user_company_names_set - company_names_set

    if not missing_companies:
        print("\n✅ No missing companies found - all users have valid company references")
        client.close()
        return

    print(f"\n⚠️  Found {len(missing_companies)} missing companies:")
    for company in missing_companies:
        users_count = len([u for u in users if u.get('company_name') == company])
        print(f"   - {company} (referenced by {users_count} users)")

    # Create missing companies
    print("\n🏢 Creating missing companies...")

    for company_name in missing_companies:
        await db.companies.insert_one({
            "company_name": company_name,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        })
        print(f"   ✓ Created: {company_name}")

    # Verify
    print("\n✅ Verification:")
    companies_after = await db.companies.find({}).to_list(length=None)
    company_names_after = set(c.get('company_name') for c in companies_after if c.get('company_name'))

    remaining_orphaned = user_company_names_set - company_names_after

    print(f"   Total companies: {len(company_names_after)}")
    print(f"   Orphaned users: {len(remaining_orphaned)}")

    if len(remaining_orphaned) == 0:
        print("\n🎉 SUCCESS! All users now have valid company references")
    else:
        print(f"\n⚠️  WARNING: {len(remaining_orphaned)} users still orphaned")

    client.close()

if __name__ == "__main__":
    asyncio.run(create_missing_companies())
