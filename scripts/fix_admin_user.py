#!/usr/bin/env python3
"""
Fix Admin User Authentication - danishevsky@gmail.com

This script:
1. Analyzes the authentication schema requirements
2. Shows current user records
3. Creates/updates the correct admin record
4. Tests password verification

Based on analysis of:
- app/routers/auth.py (admin login endpoint)
- app/services/auth_service.py (authentication logic)
- app/models/auth_models.py (request/response models)
"""

import asyncio
import bcrypt
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import uuid
from functools import partial

# MongoDB connection
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"

# Admin credentials to create
ADMIN_EMAIL = "danishevsky@gmail.com"
ADMIN_PASSWORD = "Sveta87201120!"
ADMIN_NAME = "Vladimir Danishevsky"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def analyze_auth_schema():
    """Analyze the authentication code to determine exact schema."""
    print_section("STEP 1: Authentication Schema Analysis")

    print("\n📋 Based on code analysis:")
    print()
    print("ADMIN LOGIN ENDPOINT: POST /login/admin")
    print("  - Handler: app/routers/auth.py::admin_login()")
    print("  - Service: app/services/auth_service.py::authenticate_admin()")
    print()
    print("AUTHENTICATION FLOW:")
    print("  1. Lookup admin in 'iris-admins' collection")
    print("  2. Query: {'user_email': email}")
    print("  3. Verify password with bcrypt.checkpw()")
    print("  4. Create JWT token with admin permission level")
    print("  5. Update login_date timestamp")
    print()
    print("REQUIRED SCHEMA for 'iris-admins' collection:")
    print("  {")
    print("    '_id': ObjectId,                    # Auto-generated")
    print("    'user_email': str,                  # Required - lookup key")
    print("    'user_name': str,                   # Required - full name")
    print("    'password': str,                    # Required - bcrypt hash")
    print("    'user_id': str,                     # Optional - will be generated if missing")
    print("    'login_date': datetime,             # Updated on each login")
    print("    'updated_at': datetime,             # Updated on each login")
    print("    'created_at': datetime              # Optional - record creation")
    print("  }")
    print()
    print("PASSWORD HASHING:")
    print("  - Algorithm: bcrypt")
    print("  - Verification: bcrypt.checkpw(password_bytes, password_hash)")
    print("  - Field name: 'password' (NOT 'password_hash')")
    print("  - Format: UTF-8 encoded bcrypt hash string")


async def check_current_records(client):
    """Check existing records in the database."""
    print_section("STEP 2: Current Database Records")

    db = client.translation

    # Check iris-admins collection
    print("\n🔍 Checking 'iris-admins' collection...")
    admin_count = await db["iris-admins"].count_documents({})
    print(f"  Total records: {admin_count}")

    admin = await db["iris-admins"].find_one({"user_email": ADMIN_EMAIL})
    if admin:
        print(f"\n  ✅ Admin record FOUND for {ADMIN_EMAIL}:")
        print(f"     _id: {admin.get('_id')}")
        print(f"     user_email: {admin.get('user_email')}")
        print(f"     user_name: {admin.get('user_name')}")
        print(f"     password: {'SET' if admin.get('password') else 'MISSING'}")
        print(f"     user_id: {admin.get('user_id', 'NOT SET')}")
        print(f"     login_date: {admin.get('login_date', 'NOT SET')}")
        print(f"     created_at: {admin.get('created_at', 'NOT SET')}")
    else:
        print(f"\n  ❌ No admin record found for {ADMIN_EMAIL}")

    # Check other collections (for reference)
    print("\n🔍 Checking other collections (for reference)...")

    company_user = await db.company_users.find_one({"email": ADMIN_EMAIL})
    if company_user:
        print(f"\n  Found in 'company_users':")
        print(f"     company_name: {company_user.get('company_name')}")
        print(f"     user_name: {company_user.get('user_name')}")
        print(f"     email: {company_user.get('email')}")
    else:
        print(f"\n  Not in 'company_users'")

    user = await db.users.find_one({"email": ADMIN_EMAIL})
    if user:
        print(f"\n  Found in 'users':")
        print(f"     user_name: {user.get('user_name')}")
        print(f"     email: {user.get('email')}")
        print(f"     company_name: {user.get('company_name', 'NOT SET')}")
    else:
        print(f"\n  Not in 'users'")

    return admin


async def create_admin_record(client):
    """Create or update admin record with correct schema."""
    print_section("STEP 3: Create/Update Admin Record")

    db = client.translation
    collection = db["iris-admins"]

    # Hash password with bcrypt
    print(f"\n🔐 Hashing password with bcrypt (12 rounds)...")
    password_bytes = ADMIN_PASSWORD.encode('utf-8')[:72]  # bcrypt 72-byte limit

    loop = asyncio.get_event_loop()
    salt = await loop.run_in_executor(None, bcrypt.gensalt, 12)
    password_hash = await loop.run_in_executor(
        None,
        partial(bcrypt.hashpw, password_bytes, salt)
    )
    password_hash_str = password_hash.decode('utf-8')
    print(f"  ✅ Password hashed successfully")
    print(f"     Hash preview: {password_hash_str[:29]}...")

    # Generate user_id
    user_id = f"admin_{uuid.uuid4().hex[:16]}"
    print(f"\n📝 Generated user_id: {user_id}")

    # Check if record exists
    existing = await collection.find_one({"user_email": ADMIN_EMAIL})

    now = datetime.now(timezone.utc)

    if existing:
        # Update existing record
        print(f"\n🔄 Updating existing admin record...")

        update_doc = {
            "$set": {
                "user_name": ADMIN_NAME,
                "password": password_hash_str,
                "updated_at": now
            }
        }

        # Only set user_id if not already present
        if not existing.get('user_id'):
            update_doc["$set"]["user_id"] = user_id

        # Only set created_at if not already present
        if not existing.get('created_at'):
            update_doc["$set"]["created_at"] = now

        result = await collection.update_one(
            {"user_email": ADMIN_EMAIL},
            update_doc
        )

        print(f"  ✅ Admin record updated")
        print(f"     Matched: {result.matched_count}")
        print(f"     Modified: {result.modified_count}")

        # Fetch updated record
        admin = await collection.find_one({"user_email": ADMIN_EMAIL})
    else:
        # Create new record
        print(f"\n➕ Creating new admin record...")

        admin_doc = {
            "user_email": ADMIN_EMAIL,
            "user_name": ADMIN_NAME,
            "password": password_hash_str,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
            "login_date": None  # Will be set on first login
        }

        result = await collection.insert_one(admin_doc)
        print(f"  ✅ Admin record created")
        print(f"     Inserted ID: {result.inserted_id}")

        # Fetch created record
        admin = await collection.find_one({"_id": result.inserted_id})

    # Display final record
    print(f"\n📋 Final admin record in 'iris-admins':")
    print("   {")
    print(f"     '_id': {admin['_id']},")
    print(f"     'user_email': '{admin['user_email']}',")
    print(f"     'user_name': '{admin['user_name']}',")
    print(f"     'password': '{admin['password'][:29]}...',")
    print(f"     'user_id': '{admin.get('user_id')}',")
    print(f"     'created_at': {admin.get('created_at')},")
    print(f"     'updated_at': {admin.get('updated_at')},")
    print(f"     'login_date': {admin.get('login_date')}")
    print("   }")

    return admin


async def test_password_verification(admin_record):
    """Test password verification like the authentication code does."""
    print_section("STEP 4: Test Password Verification")

    print(f"\n🧪 Testing bcrypt password verification...")
    print(f"   Password: {ADMIN_PASSWORD}")
    print(f"   Hash: {admin_record['password'][:29]}...")

    # Simulate what auth_service.authenticate_admin() does
    password_bytes = ADMIN_PASSWORD.encode('utf-8')[:72]
    password_hash_bytes = admin_record['password'].encode('utf-8')

    loop = asyncio.get_event_loop()
    password_valid = await loop.run_in_executor(
        None,
        partial(bcrypt.checkpw, password_bytes, password_hash_bytes)
    )

    if password_valid:
        print(f"\n  ✅ PASSWORD VERIFICATION SUCCESSFUL!")
        print(f"     bcrypt.checkpw() returned True")
        print(f"     This password will work for admin login")
    else:
        print(f"\n  ❌ PASSWORD VERIFICATION FAILED!")
        print(f"     bcrypt.checkpw() returned False")
        print(f"     Something is wrong with the hash")

    return password_valid


async def test_wrong_password(admin_record):
    """Test that wrong password fails verification."""
    print_section("STEP 5: Test Wrong Password (Negative Test)")

    wrong_password = "WrongPassword123!"
    print(f"\n🧪 Testing with WRONG password: {wrong_password}")

    password_bytes = wrong_password.encode('utf-8')[:72]
    password_hash_bytes = admin_record['password'].encode('utf-8')

    loop = asyncio.get_event_loop()
    password_valid = await loop.run_in_executor(
        None,
        partial(bcrypt.checkpw, password_bytes, password_hash_bytes)
    )

    if password_valid:
        print(f"\n  ❌ WRONG PASSWORD ACCEPTED - SECURITY ISSUE!")
    else:
        print(f"\n  ✅ Wrong password correctly REJECTED")
        print(f"     bcrypt.checkpw() returned False as expected")

    return not password_valid  # Should return True (test passed)


async def main():
    """Main execution flow."""
    print_section("Admin User Fix Tool - danishevsky@gmail.com")

    print(f"\nTarget Admin:")
    print(f"  Email: {ADMIN_EMAIL}")
    print(f"  Password: {ADMIN_PASSWORD}")
    print(f"  Name: {ADMIN_NAME}")
    print(f"\nMongoDB URI: {MONGODB_URI}")

    # Connect to MongoDB
    print(f"\n📡 Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGODB_URI)

    try:
        # Test connection
        await client.admin.command('ping')
        print(f"  ✅ Connected successfully")

        # Step 1: Analyze schema
        await analyze_auth_schema()

        # Step 2: Check current records
        existing_admin = await check_current_records(client)

        # Step 3: Create/update admin record
        admin_record = await create_admin_record(client)

        # Step 4: Test password verification
        correct_password_works = await test_password_verification(admin_record)

        # Step 5: Test wrong password
        wrong_password_fails = await test_wrong_password(admin_record)

        # Final summary
        print_section("SUMMARY")

        if correct_password_works and wrong_password_fails:
            print("\n✅ ALL TESTS PASSED!")
            print()
            print("Admin user is correctly configured:")
            print(f"  - Email: {ADMIN_EMAIL}")
            print(f"  - Name: {ADMIN_NAME}")
            print(f"  - Password: {ADMIN_PASSWORD}")
            print(f"  - Collection: iris-admins")
            print(f"  - Password hash: Correct bcrypt format")
            print(f"  - Verification: Working")
            print()
            print("You can now login via:")
            print(f"  POST http://localhost:8000/login/admin")
            print(f"  Body: {'{\"email\": \"' + ADMIN_EMAIL + '\", \"password\": \"' + ADMIN_PASSWORD + '\"}'}")
        else:
            print("\n❌ TESTS FAILED!")
            if not correct_password_works:
                print("  - Correct password verification failed")
            if not wrong_password_fails:
                print("  - Wrong password was accepted (security issue)")

    finally:
        # Close connection
        client.close()
        print("\n📡 MongoDB connection closed")


if __name__ == "__main__":
    asyncio.run(main())
