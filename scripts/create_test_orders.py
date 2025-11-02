"""
Create test translation transactions for Iris Trading and Acme Company.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import uuid


async def create_test_transactions():
    """Create test transactions for both companies in November 2025."""

    # Connect to database
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["translation"]

    print("=" * 80)
    print("CREATING TEST TRANSLATION TRANSACTIONS")
    print("=" * 80)

    # Check existing transactions
    print("\n📊 Checking existing transactions...")
    iris_count = await db.translation_transactions.count_documents({"company_name": "Iris Trading"})
    acme_count = await db.translation_transactions.count_documents({"company_name": "Acme Company"})

    print(f"   Iris Trading: {iris_count} existing transactions")
    print(f"   Acme Company: {acme_count} existing transactions")

    # Clear existing transactions
    if iris_count > 0 or acme_count > 0:
        print(f"\n🗑️  Clearing existing transactions...")
        result = await db.translation_transactions.delete_many({
            "company_name": {"$in": ["Iris Trading", "Acme Company"]}
        })
        print(f"   Deleted {result.deleted_count} transactions")

    # Define test transactions
    now = datetime.now(timezone.utc)

    # Calculate dates for November 2025
    nov_2025 = datetime(2025, 11, 1, tzinfo=timezone.utc)

    test_transactions = [
        # Iris Trading - November 2025 (Current month)
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Iris Trading",
            "user_id": "john.doe@iristrading.com",
            "original_file_url": "https://drive.google.com/file/d/1ABC123/view",
            "translated_file_url": "https://drive.google.com/file/d/1ABC124/view",
            "translated_file_name": "contract_fr.pdf",
            "source_language": "en",
            "target_language": "fr",
            "file_name": "contract.pdf",
            "file_size": 524288,
            "units_count": 15,
            "price_per_unit": 0.10,
            "total_price": 1.50,
            "status": "confirmed",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=5, hours=10),
            "updated_at": nov_2025 + timedelta(days=5, hours=11),
            "subscription_id": None,
            "unit_type": "page"
        },
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Iris Trading",
            "user_id": "sarah.chen@iristrading.com",
            "original_file_url": "https://drive.google.com/file/d/2DEF456/view",
            "translated_file_url": "https://drive.google.com/file/d/2DEF457/view",
            "translated_file_name": "proposal_es.pdf",
            "source_language": "en",
            "target_language": "es",
            "file_name": "proposal.pdf",
            "file_size": 1048576,
            "units_count": 25,
            "price_per_unit": 0.10,
            "total_price": 2.50,
            "status": "confirmed",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=10, hours=14),
            "updated_at": nov_2025 + timedelta(days=10, hours=15),
            "subscription_id": None,
            "unit_type": "page"
        },
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Iris Trading",
            "user_id": "mike.wilson@iristrading.com",
            "original_file_url": "https://drive.google.com/file/d/3GHI789/view",
            "translated_file_url": "",
            "translated_file_name": "",
            "source_language": "en",
            "target_language": "de",
            "file_name": "report.docx",
            "file_size": 2097152,
            "units_count": 40,
            "price_per_unit": 0.10,
            "total_price": 4.00,
            "status": "started",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=15, hours=9),
            "updated_at": nov_2025 + timedelta(days=15, hours=9),
            "subscription_id": None,
            "unit_type": "page"
        },

        # Acme Company - November 2025
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Acme Company",
            "user_id": "alice.brown@acme.com",
            "original_file_url": "https://drive.google.com/file/d/4JKL012/view",
            "translated_file_url": "https://drive.google.com/file/d/4JKL013/view",
            "translated_file_name": "manual_ja.pdf",
            "source_language": "en",
            "target_language": "ja",
            "file_name": "manual.pdf",
            "file_size": 3145728,
            "units_count": 50,
            "price_per_unit": 0.12,
            "total_price": 6.00,
            "status": "confirmed",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=8, hours=11),
            "updated_at": nov_2025 + timedelta(days=8, hours=13),
            "subscription_id": None,
            "unit_type": "page"
        },
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Acme Company",
            "user_id": "bob.smith@acme.com",
            "original_file_url": "https://drive.google.com/file/d/5MNO345/view",
            "translated_file_url": "https://drive.google.com/file/d/5MNO346/view",
            "translated_file_name": "agreement_zh.pdf",
            "source_language": "en",
            "target_language": "zh",
            "file_name": "agreement.pdf",
            "file_size": 786432,
            "units_count": 20,
            "price_per_unit": 0.12,
            "total_price": 2.40,
            "status": "confirmed",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=12, hours=16),
            "updated_at": nov_2025 + timedelta(days=12, hours=17),
            "subscription_id": None,
            "unit_type": "page"
        },
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Acme Company",
            "user_id": "carol.davis@acme.com",
            "original_file_url": "https://drive.google.com/file/d/6PQR678/view",
            "translated_file_url": "",
            "translated_file_name": "",
            "source_language": "en",
            "target_language": "ko",
            "file_name": "presentation.pptx",
            "file_size": 4194304,
            "units_count": 60,
            "price_per_unit": 0.12,
            "total_price": 7.20,
            "status": "pending",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=18, hours=10),
            "updated_at": nov_2025 + timedelta(days=18, hours=10),
            "subscription_id": None,
            "unit_type": "page"
        },
    ]

    # Insert transactions
    print(f"\n📥 Creating {len(test_transactions)} test transactions...")
    result = await db.translation_transactions.insert_many(test_transactions)
    print(f"   ✅ Created {len(result.inserted_ids)} transactions")

    # Verify by company
    print(f"\n✅ Verification:")
    iris_count = await db.translation_transactions.count_documents({"company_name": "Iris Trading"})
    acme_count = await db.translation_transactions.count_documents({"company_name": "Acme Company"})
    print(f"   Iris Trading: {iris_count} transactions")
    print(f"   Acme Company: {acme_count} transactions")

    # Show sample
    print(f"\n📄 Sample transactions:")
    async for txn in db.translation_transactions.find({"company_name": "Iris Trading"}).limit(3):
        print(f"   {txn['transaction_id']} | {txn['user_id']} | {txn['file_name']} | {txn['status']} | {txn['created_at']}")

    print("\n" + "=" * 80)
    print("✅ TEST DATA CREATED SUCCESSFULLY")
    print("=" * 80)

    # Close connection
    client.close()


if __name__ == "__main__":
    asyncio.run(create_test_transactions())
