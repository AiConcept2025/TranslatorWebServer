#!/usr/bin/env python3
"""
Populate MongoDB Test Data
Creates test data for two existing companies: "Acme Translation Corp" and "Iris Trading"

CRITICAL: Uses company_name (String) NOT company_id (ObjectId) - migrated schema

Usage:
    python3 scripts/populate_test_data.py
"""
import asyncio
import sys
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_user_id():
    """Generate unique user ID."""
    return f"user_{uuid.uuid4().hex[:16]}"


def generate_transaction_id():
    """Generate unique transaction ID."""
    return f"TXN-{uuid.uuid4().hex[:10].upper()}"


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


async def populate_test_data():
    """Populate MongoDB with test data for two companies."""
    print("=" * 80)
    print("Populating MongoDB Test Data")
    print("=" * 80)

    # MongoDB connection (from existing scripts pattern)
    uri = 'mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation'
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client.translation

    try:
        # Test connection
        await client.admin.command('ping')
        print("\n✓ Connected to MongoDB")

        # Define company names (CRITICAL: use company_name, not company_id)
        companies = [
            {"company_name": "Acme Translation Corp"},
            {"company_name": "Iris Trading"}
        ]

        print("\n" + "=" * 80)
        print("Step 1: Verify Companies Exist")
        print("=" * 80)

        for company in companies:
            company_name = company["company_name"]
            existing = await db.company.find_one({"company_name": company_name})
            if existing:
                print(f"✓ Company exists: {company_name}")
                company["_id"] = existing["_id"]
                company["company_id"] = existing.get("company_id", "N/A")
            else:
                print(f"✗ ERROR: Company NOT found: {company_name}")
                print(f"  Please ensure '{company_name}' exists in the database first")
                return False

        print("\n" + "=" * 80)
        print("Step 2: Clean Up Existing Test Data")
        print("=" * 80)

        # Delete existing test data for these companies
        company_names = [c["company_name"] for c in companies]

        # Delete subscriptions (uses company_name)
        sub_result = await db.subscriptions.delete_many({"company_name": {"$in": company_names}})
        print(f"✓ Deleted {sub_result.deleted_count} existing subscriptions")

        # Delete company_users (✅ MIGRATED: uses company_name)
        users_result = await db.company_users.delete_many({"company_name": {"$in": company_names}})
        print(f"✓ Deleted {users_result.deleted_count} existing company users")

        # Delete translation_transactions (uses company_name)
        trans_result = await db.translation_transactions.delete_many({"company_name": {"$in": company_names}})
        print(f"✓ Deleted {trans_result.deleted_count} existing translation transactions")

        print("\n" + "=" * 80)
        print("Step 3: Create Subscriptions (MIGRATED SCHEMA: uses company_name)")
        print("=" * 80)

        subscriptions_data = [
            {
                "company_name": "Acme Translation Corp",  # ✅ MIGRATED: String company_name
                "subscription_unit": "page",
                "units_per_subscription": 1000,
                "price_per_unit": 0.10,
                "promotional_units": 100,
                "discount": 0.9,  # 10% discount
                "subscription_price": 90.00,
                "start_date": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "end_date": datetime(2025, 12, 31, tzinfo=timezone.utc),
                "status": "active",
                "usage_periods": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            },
            {
                "company_name": "Iris Trading",  # ✅ MIGRATED: String company_name
                "subscription_unit": "page",
                "units_per_subscription": 2000,
                "price_per_unit": 0.10,
                "promotional_units": 100,
                "discount": 0.9,  # 10% discount
                "subscription_price": 180.00,
                "start_date": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "end_date": datetime(2025, 12, 31, tzinfo=timezone.utc),
                "status": "active",
                "usage_periods": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
        ]

        subscription_ids = {}
        for sub_data in subscriptions_data:
            result = await db.subscriptions.insert_one(sub_data)
            company_name = sub_data["company_name"]
            subscription_ids[company_name] = result.inserted_id
            print(f"✓ Created subscription for {company_name}")
            print(f"  - Units: {sub_data['units_per_subscription']} {sub_data['subscription_unit']}s")
            print(f"  - Price: ${sub_data['subscription_price']:.2f}")
            print(f"  - Promotional units: {sub_data['promotional_units']}")
            print(f"  - Subscription ID: {result.inserted_id}")

        print("\n" + "=" * 80)
        print("Step 4: Create Company Users (MIGRATED SCHEMA: uses company_name)")
        print("=" * 80)

        # ✅ MIGRATED: company_users now uses company_name (String)
        password_hash = hash_password("password123")

        company_users_data = [
            {
                "user_id": generate_user_id(),
                "user_name": "Admin User",
                "email": "admin@acme.com",
                "company_name": "Acme Translation Corp",  # ✅ MIGRATED: String company_name
                "password_hash": password_hash,
                "permission_level": "admin",
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "last_login": datetime.now(timezone.utc)
            },
            {
                "user_id": generate_user_id(),
                "user_name": "Manager User",
                "email": "manager@iris.com",
                "company_name": "Iris Trading",  # ✅ MIGRATED: String company_name
                "password_hash": password_hash,
                "permission_level": "admin",
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "last_login": datetime.now(timezone.utc)
            }
        ]

        for user_data in company_users_data:
            result = await db.company_users.insert_one(user_data)
            print(f"✓ Created user for {user_data['company_name']}")
            print(f"  - User ID: {user_data['user_id']}")
            print(f"  - Email: {user_data['email']}")
            print(f"  - Permission: {user_data['permission_level']}")
            print(f"  - Password: password123")

        print("\n" + "=" * 80)
        print("Step 5: Create Translation Transactions (MIGRATED SCHEMA: uses company_name)")
        print("=" * 80)

        # Create 2-3 transactions per company
        transactions_data = [
            # Acme Translation Corp - Transaction 1
            {
                "transaction_id": generate_transaction_id(),
                "user_id": "admin@acme.com",
                "original_file_url": "https://docs.google.com/document/d/1ACMEtest001/edit",
                "translated_file_url": "",
                "source_language": "en",
                "target_language": "es",
                "file_name": "Contract_Draft.docx",
                "file_size": 524288,
                "units_count": 25,
                "price_per_unit": 0.10,
                "total_price": 2.50,
                "status": "started",
                "error_message": "",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "company_name": "Acme Translation Corp",  # ✅ MIGRATED: String company_name
                "subscription_id": subscription_ids["Acme Translation Corp"],
                "unit_type": "page"
            },
            # Acme Translation Corp - Transaction 2
            {
                "transaction_id": generate_transaction_id(),
                "user_id": "admin@acme.com",
                "original_file_url": "https://docs.google.com/document/d/1ACMEtest002/edit",
                "translated_file_url": "https://docs.google.com/document/d/1ACMEtest002_trans/edit",
                "source_language": "en",
                "target_language": "fr",
                "file_name": "Marketing_Materials.pdf",
                "file_size": 1048576,
                "units_count": 50,
                "price_per_unit": 0.10,
                "total_price": 5.00,
                "status": "confirmed",
                "error_message": "",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "company_name": "Acme Translation Corp",  # ✅ MIGRATED: String company_name
                "subscription_id": subscription_ids["Acme Translation Corp"],
                "unit_type": "page"
            },
            # Iris Trading - Transaction 1
            {
                "transaction_id": generate_transaction_id(),
                "user_id": "manager@iris.com",
                "original_file_url": "https://docs.google.com/document/d/1IRIStest001/edit",
                "translated_file_url": "",
                "source_language": "de",
                "target_language": "en",
                "file_name": "Invoice_2025_Q1.pdf",
                "file_size": 262144,
                "units_count": 15,
                "price_per_unit": 0.10,
                "total_price": 1.50,
                "status": "pending",
                "error_message": "",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "company_name": "Iris Trading",  # ✅ MIGRATED: String company_name
                "subscription_id": subscription_ids["Iris Trading"],
                "unit_type": "page"
            },
            # Iris Trading - Transaction 2
            {
                "transaction_id": generate_transaction_id(),
                "user_id": "manager@iris.com",
                "original_file_url": "https://docs.google.com/document/d/1IRIStest002/edit",
                "translated_file_url": "https://docs.google.com/document/d/1IRIStest002_trans/edit",
                "source_language": "en",
                "target_language": "de",
                "file_name": "Product_Catalog.docx",
                "file_size": 786432,
                "units_count": 35,
                "price_per_unit": 0.10,
                "total_price": 3.50,
                "status": "confirmed",
                "error_message": "",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "company_name": "Iris Trading",  # ✅ MIGRATED: String company_name
                "subscription_id": subscription_ids["Iris Trading"],
                "unit_type": "page"
            },
            # Iris Trading - Transaction 3
            {
                "transaction_id": generate_transaction_id(),
                "user_id": "manager@iris.com",
                "original_file_url": "https://docs.google.com/document/d/1IRIStest003/edit",
                "translated_file_url": "",
                "source_language": "en",
                "target_language": "es",
                "file_name": "Shipping_Documents.pdf",
                "file_size": 409600,
                "units_count": 20,
                "price_per_unit": 0.10,
                "total_price": 2.00,
                "status": "started",
                "error_message": "",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "company_name": "Iris Trading",  # ✅ MIGRATED: String company_name
                "subscription_id": subscription_ids["Iris Trading"],
                "unit_type": "page"
            }
        ]

        transaction_count = 0
        for trans_data in transactions_data:
            result = await db.translation_transactions.insert_one(trans_data)
            transaction_count += 1
            print(f"✓ Created transaction {transaction_count} for {trans_data['company_name']}")
            print(f"  - Transaction ID: {trans_data['transaction_id']}")
            print(f"  - File: {trans_data['file_name']}")
            print(f"  - Language: {trans_data['source_language']} → {trans_data['target_language']}")
            print(f"  - Status: {trans_data['status']}")
            print(f"  - Units: {trans_data['units_count']} pages")
            print(f"  - Total: ${trans_data['total_price']:.2f}")

        print("\n" + "=" * 80)
        print("Step 6: Verification")
        print("=" * 80)

        # Verify data was created
        for company in companies:
            company_name = company["company_name"]
            print(f"\n{company_name}:")

            # Check subscription
            sub = await db.subscriptions.find_one({"company_name": company_name})
            print(f"  ✓ Subscription: {sub['units_per_subscription']} pages at ${sub['subscription_price']:.2f}")

            # Check users (✅ MIGRATED: uses company_name)
            user_count = await db.company_users.count_documents({"company_name": company_name})
            print(f"  ✓ Company users: {user_count}")

            # Check transactions
            trans_count = await db.translation_transactions.count_documents({"company_name": company_name})
            print(f"  ✓ Translation transactions: {trans_count}")

        print("\n" + "=" * 80)
        print("SUCCESS: Test data populated successfully!")
        print("=" * 80)

        print("\n📝 Summary:")
        print(f"  - Companies verified: {len(companies)}")
        print(f"  - Subscriptions created: {len(subscriptions_data)}")
        print(f"  - Company users created: {len(company_users_data)}")
        print(f"  - Translation transactions created: {len(transactions_data)}")

        print("\n🔑 Login Credentials:")
        print("  - Email: admin@acme.com | Password: password123")
        print("  - Email: manager@iris.com | Password: password123")

        print("\n💡 Query Examples:")
        print("  # Get Acme subscription")
        print("  db.subscriptions.findOne({company_name: 'Acme Translation Corp'})")
        print("\n  # Get Iris transactions")
        print("  db.translation_transactions.find({company_name: 'Iris Trading'})")

        print("\n" + "=" * 80)

        return True

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        client.close()


if __name__ == "__main__":
    success = asyncio.run(populate_test_data())
    sys.exit(0 if success else 1)
