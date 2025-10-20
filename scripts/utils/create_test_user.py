#!/usr/bin/env python3
"""
Create test user for E2E tests.

Company: Iris Trading
User: Vladimir Danishevsky
Email: danishevsky@gmail.com
Password: Sveta87201120!
Subscription: 233 pages remaining (out of 1000 allocated)
"""

import asyncio
import bcrypt
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def create_test_data():
    """Create test company, user, and subscription."""

    # Connect to MongoDB with authentication
    mongodb_uri = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
    client = AsyncIOMotorClient(mongodb_uri)
    db = client.translation

    print("=" * 80)
    print("Creating test data for E2E tests")
    print("=" * 80)

    # 1. Create or update company
    print("\n1. Setting up company...")
    company_name = "Iris Trading"
    # NOTE: Backend uses 'company' (singular) collection, not 'companies' (plural)
    company = await db.company.find_one({"company_name": company_name})

    if company:
        company_id = company["_id"]
        print(f"   ✅ Company exists: {company_id}")
    else:
        company_doc = {
            "company_name": company_name,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        result = await db.company.insert_one(company_doc)
        company_id = result.inserted_id
        print(f"   ✅ Company created: {company_id}")

    # 2. Create or update user with hashed password
    print("\n2. Setting up user...")
    email = "danishevsky@gmail.com"
    user_name = "Vladimir L Danishevsky"  # Must match test expectations
    password = "Sveta87201120!"

    # Hash password with bcrypt
    password_bytes = password.encode('utf-8')[:72]  # Truncate to 72 bytes (bcrypt limit)
    password_hash = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')

    # Check if user exists
    user = await db.users.find_one({
        "email": email,
        "company_id": company_id
    })

    if user:
        # Update existing user
        await db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "user_name": user_name,
                    "password_hash": password_hash,
                    "status": "active",
                    "permission_level": "admin",
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        user_id = user.get("user_id")
        print(f"   ✅ User updated: {user['_id']}")
    else:
        # Create new user
        # Generate user_id (8 random hex chars)
        import secrets
        user_id = f"user_{secrets.token_hex(4)}"

        user_doc = {
            "user_id": user_id,
            "email": email,
            "user_name": user_name,
            "company_id": company_id,
            "password_hash": password_hash,
            "status": "active",
            "permission_level": "admin",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        result = await db.users.insert_one(user_doc)
        print(f"   ✅ User created: {result.inserted_id}")

    print(f"   📧 Email: {email}")
    print(f"   👤 User Name: {user_name}")
    print(f"   🔐 Password: {password}")
    print(f"   🔑 Permission: admin")
    print(f"   ✅ Status: active")

    # 3. Create or update subscription
    print("\n3. Setting up subscription...")
    subscription = await db.subscriptions.find_one({"company_id": company_id})

    subscription_doc = {
        "company_id": company_id,
        "status": "active",
        "subscription_unit": "page",
        "price_per_unit": 0.10,
        "usage_periods": [{
            "period_start": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "period_end": datetime(2025, 2, 1, tzinfo=timezone.utc),
            "units_allocated": 1000,
            "units_used": 767,
            "units_remaining": 233  # This is what E2E tests expect
        }],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    if subscription:
        await db.subscriptions.update_one(
            {"_id": subscription["_id"]},
            {"$set": subscription_doc}
        )
        print(f"   ✅ Subscription updated: {subscription['_id']}")
    else:
        result = await db.subscriptions.insert_one(subscription_doc)
        print(f"   ✅ Subscription created: {result.inserted_id}")

    print(f"   📊 Units allocated: 1000 pages")
    print(f"   📊 Units used: 767 pages")
    print(f"   📊 Units remaining: 233 pages")
    print(f"   💵 Price per page: $0.10")

    # 4. Verify data
    print("\n4. Verifying setup...")

    # Verify company
    company_check = await db.company.find_one({"_id": company_id})
    assert company_check is not None, "Company not found"
    print(f"   ✅ Company verified: {company_check['company_name']}")

    # Verify user
    user_check = await db.users.find_one({
        "email": email,
        "company_id": company_id,
        "user_name": user_name
    })
    assert user_check is not None, "User not found"
    assert user_check["status"] == "active", "User not active"
    assert user_check["permission_level"] == "admin", "User not admin"
    print(f"   ✅ User verified: {user_check['email']}")

    # Verify password hash
    password_valid = bcrypt.checkpw(password_bytes, user_check["password_hash"].encode('utf-8'))
    assert password_valid, "Password hash verification failed"
    print(f"   ✅ Password hash verified")

    # Verify subscription
    subscription_check = await db.subscriptions.find_one({"company_id": company_id})
    assert subscription_check is not None, "Subscription not found"
    assert subscription_check["usage_periods"][0]["units_remaining"] == 233
    print(f"   ✅ Subscription verified: {subscription_check['usage_periods'][0]['units_remaining']} pages remaining")

    print("\n" + "=" * 80)
    print("✅ TEST DATA SETUP COMPLETE")
    print("=" * 80)
    print("\nYou can now run E2E tests with these credentials:")
    print(f"  Company: {company_name}")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print(f"  Expected behavior: 233 pages remaining < 432 pages required = INSUFFICIENT FUNDS")
    print("=" * 80)

    # Close connection
    client.close()


if __name__ == "__main__":
    asyncio.run(create_test_data())
