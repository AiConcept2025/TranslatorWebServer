"""
Final verification: Check if danishevsky@gmail.com exists in company_users
for Iris Trading (case-insensitive check matching the API logic).
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json
from datetime import datetime


MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
TARGET_EMAIL = "danishevsky@gmail.com"
COMPANY_NAME = "Iris Trading"


async def final_check():
    """Verify exact API validation logic."""

    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.translation

    print("=" * 80)
    print("FINAL VERIFICATION - API VALIDATION LOGIC")
    print("=" * 80)
    print(f"Email: {TARGET_EMAIL}")
    print(f"Company: {COMPANY_NAME}")
    print()

    # Exact query from API code (line 168-171)
    # existing_user = await database.company_users.find_one({
    #     "company_name": company_name,
    #     "email": {"$regex": f"^{request.email}$", "$options": "i"}
    # })

    print("Running EXACT API query:")
    print(f'Query: company_name="{COMPANY_NAME}", email regex="^{TARGET_EMAIL}$" (case-insensitive)')
    print()

    company_users = db.company_users
    existing_user = await company_users.find_one({
        "company_name": COMPANY_NAME,
        "email": {"$regex": f"^{TARGET_EMAIL}$", "$options": "i"}
    })

    if existing_user:
        print("🔴 FOUND - Email DOES exist for this company")
        print()
        print("This is WHY the API returns 'Email already exists for company'")
        print()
        print("Document details:")
        for key, value in existing_user.items():
            if isinstance(value, datetime):
                existing_user[key] = value.isoformat()
        print(json.dumps(existing_user, indent=2, default=str))
    else:
        print("✅ NOT FOUND - Email does NOT exist for this company")
        print()
        print("API should allow user creation")

    print()
    print("=" * 80)
    print("Additional Check: ALL users with this email (any company)")
    print("=" * 80)
    print()

    all_users_cursor = company_users.find({
        "email": {"$regex": f"^{TARGET_EMAIL}$", "$options": "i"}
    })

    count = 0
    async for user in all_users_cursor:
        count += 1
        print(f"User #{count}:")
        print(f"  Company: {user.get('company_name', 'N/A')}")
        print(f"  Email: {user.get('email', 'N/A')}")
        print(f"  User ID: {user.get('user_id', 'N/A')}")
        print(f"  Status: {user.get('status', 'N/A')}")
        print()

    if count == 0:
        print("No users found with this email in company_users collection")

    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)

    if existing_user:
        print("❌ User creation will FAIL")
        print(f"   Reason: Email '{TARGET_EMAIL}' already exists for '{COMPANY_NAME}'")
        print(f"   Solution: Delete the existing user record OR use different email")
    else:
        print("✅ User creation should SUCCEED")
        print(f"   Email '{TARGET_EMAIL}' is available for '{COMPANY_NAME}'")

    client.close()


if __name__ == "__main__":
    asyncio.run(final_check())
