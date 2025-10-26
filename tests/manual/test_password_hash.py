#!/usr/bin/env python3
"""Test password hashing and verification."""

import bcrypt
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def test_password():
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation")
    db = client.translation

    # Get user
    user = await db.users.find_one({
        "email": "danishevsky@gmail.com",
        "user_name": "Vladimir L Danishevsky"
    })

    if not user:
        print("❌ User not found!")
        return

    print(f"✅ User found: {user.get('user_name')}")
    print(f"📧 Email: {user.get('email')}")
    print(f"🔑 Permission: {user.get('permission_level')}")
    print(f"✅ Status: {user.get('status')}")
    print(f"🏢 Company ID: {user.get('company_id')}")

    # Check password hash
    password_hash = user.get('password_hash')
    if not password_hash:
        print("❌ No password_hash field found!")
        return

    print(f"\n🔐 Password hash exists: {password_hash[:30]}...")

    # Test password
    test_password = "Sveta87201120!"
    password_bytes = test_password.encode('utf-8')[:72]

    try:
        is_valid = bcrypt.checkpw(password_bytes, password_hash.encode('utf-8'))
        if is_valid:
            print(f"✅ Password verification SUCCESS!")
        else:
            print(f"❌ Password verification FAILED!")

            # Try re-hashing to compare
            new_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
            print(f"\n🔄 New hash would be: {new_hash[:30]}...")
            print(f"📋 Current hash is: {password_hash[:30]}...")

    except Exception as e:
        print(f"💥 Error during verification: {e}")

    client.close()

if __name__ == "__main__":
    asyncio.run(test_password())
