#!/usr/bin/env python3
"""
Create Admin User Account for Iris Trading

This script:
1. Checks if company "Iris Trading" exists (creates if not)
2. Checks if user danishevsky@gmail.com exists
3. Creates or updates the user with properly hashed password
4. Verifies creation

CRITICAL: Password is hashed with bcrypt - NEVER store plain text!
"""

import asyncio
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt


# Database connection
MONGO_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DB_NAME = "translation"

# User details
USER_EMAIL = "danishevsky@yahoo.com"
USER_NAME = "Vladimir Danishevsky"
USER_PASSWORD = "Sveta87201120!"
COMPANY_NAME = "Iris Trading"
USER_ROLE = "admin"


async def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


async def create_company_if_not_exists(db):
    """Check if company exists, create if not."""
    companies = db.companies

    existing = await companies.find_one({"company_name": COMPANY_NAME})

    if existing:
        print(f"✓ Company '{COMPANY_NAME}' already exists")
        print(f"  Company ID: {existing['_id']}")
        return existing

    # Create company
    company_doc = {
        "company_name": COMPANY_NAME,
        "description": None,
        "address": None,
        "contact_person": None,
        "contact_email": USER_EMAIL,
        "phone_number": None,
        "company_url": None,
        "line_of_business": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await companies.insert_one(company_doc)
    print(f"✓ Created company '{COMPANY_NAME}'")
    print(f"  Company ID: {result.inserted_id}")

    return await companies.find_one({"_id": result.inserted_id})


async def create_or_update_user(db):
    """Create or update admin user in company_users collection."""
    company_users = db.company_users

    # Check if user exists
    existing_user = await company_users.find_one({"email": USER_EMAIL})

    # Hash password
    print("Hashing password with bcrypt...")
    hashed_password = await hash_password(USER_PASSWORD)
    print(f"✓ Password hashed: {hashed_password[:20]}...")

    now = datetime.now(timezone.utc)

    user_doc = {
        "user_id": USER_EMAIL,  # Using email as user_id
        "company_name": COMPANY_NAME,
        "user_name": USER_NAME,
        "email": USER_EMAIL,
        "phone_number": None,
        "permission_level": USER_ROLE,  # "admin"
        "status": "active",
        "password_hash": hashed_password,
        "last_login": None,
        "updated_at": now
    }

    if existing_user:
        # Update existing user
        print(f"⚠ User {USER_EMAIL} already exists")
        print("  Updating password and role...")

        await company_users.update_one(
            {"email": USER_EMAIL},
            {"$set": user_doc}
        )

        print(f"✓ Updated user: {USER_EMAIL}")
        action = "updated"
    else:
        # Create new user
        user_doc["created_at"] = now
        result = await company_users.insert_one(user_doc)
        print(f"✓ Created user: {USER_EMAIL}")
        print(f"  User ID: {result.inserted_id}")
        action = "created"

    return action


async def verify_user(db):
    """Verify user was created correctly."""
    company_users = db.company_users

    user = await company_users.find_one({"email": USER_EMAIL})

    if not user:
        print("❌ ERROR: User not found after creation!")
        return False

    print("\n" + "="*60)
    print("USER ACCOUNT DETAILS")
    print("="*60)
    print(f"Name:             {user['user_name']}")
    print(f"Email:            {user['email']}")
    print(f"Company:          {user['company_name']}")
    print(f"Role:             {user['permission_level']}")
    print(f"Status:           {user['status']}")
    print(f"Password Hash:    {user['password_hash'][:30]}... (SECURELY HASHED)")
    print(f"Created At:       {user.get('created_at', 'N/A')}")
    print(f"Updated At:       {user['updated_at']}")
    print("="*60)

    # Verify password hash format (bcrypt starts with $2b$)
    if user['password_hash'].startswith('$2b$'):
        print("✓ Password is properly bcrypt hashed")
    else:
        print("❌ WARNING: Password hash format unexpected!")
        return False

    # Test password verification
    if bcrypt.checkpw(USER_PASSWORD.encode('utf-8'), user['password_hash'].encode('utf-8')):
        print("✓ Password verification successful")
    else:
        print("❌ WARNING: Password verification failed!")
        return False

    return True


async def main():
    """Main execution."""
    print("="*60)
    print("ADMIN USER CREATION SCRIPT")
    print("="*60)
    print(f"Database:  {DB_NAME}")
    print(f"User:      {USER_NAME}")
    print(f"Email:     {USER_EMAIL}")
    print(f"Company:   {COMPANY_NAME}")
    print(f"Role:      {USER_ROLE}")
    print("="*60 + "\n")

    # Connect to MongoDB
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    try:
        # Verify connection
        await client.admin.command('ping')
        print("✓ Connected to MongoDB\n")

        # Step 1: Create/verify company
        print("STEP 1: Verify/Create Company")
        print("-" * 60)
        await create_company_if_not_exists(db)
        print()

        # Step 2: Create/update user
        print("STEP 2: Create/Update User")
        print("-" * 60)
        action = await create_or_update_user(db)
        print()

        # Step 3: Verify
        print("STEP 3: Verify User Account")
        print("-" * 60)
        success = await verify_user(db)
        print()

        if success:
            print("="*60)
            print("✓ SUCCESS: Admin user account ready!")
            print("="*60)
            print(f"\nYou can now log in with:")
            print(f"  Email:    {USER_EMAIL}")
            print(f"  Password: {USER_PASSWORD}")
            print()
            return 0
        else:
            print("="*60)
            print("❌ ERROR: Verification failed")
            print("="*60)
            return 1

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        client.close()
        print("\nClosed MongoDB connection")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
