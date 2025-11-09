"""
Create test translation transactions using app's database connection.
Run this from the server directory.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from datetime import datetime, timezone, timedelta
import uuid

# Import from app
from app.database import database


async def main():
    """Create test transactions."""
    print("=" * 80)
    print("CREATING TEST TRANSLATION TRANSACTIONS")
    print("=" * 80)

    # Connect to database
    print("\n🔌 Connecting to database...")
    connected = await database.connect()
    if not connected:
        print("❌ Failed to connect to database")
        return

    print("✅ Connected to database")

    # Check existing
    print("\n📊 Checking existing transactions...")
    iris_count = await database.translation_transactions.count_documents({"company_name": "Iris Trading"})
    acme_count = await database.translation_transactions.count_documents({"company_name": "Acme Company"})
    print(f"   Iris Trading: {iris_count} existing")
    print(f"   Acme Company: {acme_count} existing")

    # Clear existing
    if iris_count > 0 or acme_count > 0:
        print(f"\n🗑️  Clearing existing transactions...")
        result = await database.translation_transactions.delete_many({
            "company_name": {"$in": ["Iris Trading", "Acme Company"]}
        })
        print(f"   Deleted {result.deleted_count} transactions")

    # November 2025 date
    nov_2025 = datetime(2025, 11, 1, tzinfo=timezone.utc)

    # Create test transactions with NESTED structure
    transactions = [
        # Iris Trading - Transaction 1 (NESTED)
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Iris Trading",
            "user_id": "john.doe@iristrading.com",
            "user_name": "John Doe",
            "source_language": "en",
            "target_language": "fr",
            "units_count": 15,
            "price_per_unit": 0.10,
            "total_price": 1.50,
            "status": "confirmed",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=5, hours=10),
            "updated_at": nov_2025 + timedelta(days=5, hours=11),
            "subscription_id": None,
            "unit_type": "page",
            "documents": [
                {
                    "file_name": "contract.pdf",
                    "file_size": 524288,
                    "original_url": "https://drive.google.com/file/d/1ABC123/view",
                    "translated_url": "https://drive.google.com/file/d/1ABC124/view",
                    "translated_name": "contract_fr.pdf",
                    "status": "translated",
                    "uploaded_at": nov_2025 + timedelta(days=5, hours=10),
                    "translated_at": nov_2025 + timedelta(days=5, hours=11),
                    "processing_started_at": nov_2025 + timedelta(days=5, hours=10, minutes=5),
                    "processing_duration": 55.2
                }
            ]
        },
        # Iris Trading - Transaction 2 (NESTED)
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Iris Trading",
            "user_id": "sarah.chen@iristrading.com",
            "user_name": "Sarah Chen",
            "source_language": "en",
            "target_language": "es",
            "units_count": 25,
            "price_per_unit": 0.10,
            "total_price": 2.50,
            "status": "confirmed",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=10, hours=14),
            "updated_at": nov_2025 + timedelta(days=10, hours=15),
            "subscription_id": None,
            "unit_type": "page",
            "documents": [
                {
                    "file_name": "proposal.pdf",
                    "file_size": 1048576,
                    "original_url": "https://drive.google.com/file/d/2DEF456/view",
                    "translated_url": "https://drive.google.com/file/d/2DEF457/view",
                    "translated_name": "proposal_es.pdf",
                    "status": "translated",
                    "uploaded_at": nov_2025 + timedelta(days=10, hours=14),
                    "translated_at": nov_2025 + timedelta(days=10, hours=15),
                    "processing_started_at": nov_2025 + timedelta(days=10, hours=14, minutes=10),
                    "processing_duration": 48.7
                }
            ]
        },
        # Iris Trading - Transaction 3 (NESTED)
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Iris Trading",
            "user_id": "mike.wilson@iristrading.com",
            "user_name": "Mike Wilson",
            "source_language": "en",
            "target_language": "de",
            "units_count": 40,
            "price_per_unit": 0.10,
            "total_price": 4.00,
            "status": "started",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=15, hours=9),
            "updated_at": nov_2025 + timedelta(days=15, hours=9),
            "subscription_id": None,
            "unit_type": "page",
            "documents": [
                {
                    "file_name": "report.docx",
                    "file_size": 2097152,
                    "original_url": "https://drive.google.com/file/d/3GHI789/view",
                    "translated_url": None,
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": nov_2025 + timedelta(days=15, hours=9),
                    "translated_at": None,
                    "processing_started_at": None,
                    "processing_duration": None
                }
            ]
        },
        # Acme Company - Transaction 1 (NESTED)
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Acme Company",
            "user_id": "alice.brown@acme.com",
            "user_name": "Alice Brown",
            "source_language": "en",
            "target_language": "ja",
            "units_count": 50,
            "price_per_unit": 0.12,
            "total_price": 6.00,
            "status": "confirmed",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=8, hours=11),
            "updated_at": nov_2025 + timedelta(days=8, hours=13),
            "subscription_id": None,
            "unit_type": "page",
            "documents": [
                {
                    "file_name": "manual.pdf",
                    "file_size": 3145728,
                    "original_url": "https://drive.google.com/file/d/4JKL012/view",
                    "translated_url": "https://drive.google.com/file/d/4JKL013/view",
                    "translated_name": "manual_ja.pdf",
                    "status": "translated",
                    "uploaded_at": nov_2025 + timedelta(days=8, hours=11),
                    "translated_at": nov_2025 + timedelta(days=8, hours=13),
                    "processing_started_at": nov_2025 + timedelta(days=8, hours=11, minutes=15),
                    "processing_duration": 112.3
                }
            ]
        },
        # Acme Company - Transaction 2 (NESTED)
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Acme Company",
            "user_id": "bob.smith@acme.com",
            "user_name": "Bob Smith",
            "source_language": "en",
            "target_language": "zh",
            "units_count": 20,
            "price_per_unit": 0.12,
            "total_price": 2.40,
            "status": "confirmed",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=12, hours=16),
            "updated_at": nov_2025 + timedelta(days=12, hours=17),
            "subscription_id": None,
            "unit_type": "page",
            "documents": [
                {
                    "file_name": "agreement.pdf",
                    "file_size": 786432,
                    "original_url": "https://drive.google.com/file/d/5MNO345/view",
                    "translated_url": "https://drive.google.com/file/d/5MNO346/view",
                    "translated_name": "agreement_zh.pdf",
                    "status": "translated",
                    "uploaded_at": nov_2025 + timedelta(days=12, hours=16),
                    "translated_at": nov_2025 + timedelta(days=12, hours=17),
                    "processing_started_at": nov_2025 + timedelta(days=12, hours=16, minutes=8),
                    "processing_duration": 52.1
                }
            ]
        },
        # Acme Company - Transaction 3 (NESTED)
        {
            "transaction_id": f"TXN-{uuid.uuid4().hex[:10].upper()}",
            "company_name": "Acme Company",
            "user_id": "carol.davis@acme.com",
            "user_name": "Carol Davis",
            "source_language": "en",
            "target_language": "ko",
            "units_count": 60,
            "price_per_unit": 0.12,
            "total_price": 7.20,
            "status": "pending",
            "error_message": "",
            "created_at": nov_2025 + timedelta(days=18, hours=10),
            "updated_at": nov_2025 + timedelta(days=18, hours=10),
            "subscription_id": None,
            "unit_type": "page",
            "documents": [
                {
                    "file_name": "presentation.pptx",
                    "file_size": 4194304,
                    "original_url": "https://drive.google.com/file/d/6PQR678/view",
                    "translated_url": None,
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": nov_2025 + timedelta(days=18, hours=10),
                    "translated_at": None,
                    "processing_started_at": None,
                    "processing_duration": None
                }
            ]
        },
    ]

    print(f"\n📥 Creating {len(transactions)} test transactions...")
    result = await database.translation_transactions.insert_many(transactions)
    print(f"   ✅ Created {len(result.inserted_ids)} transactions")

    # Verify
    print(f"\n✅ Verification:")
    iris_count = await database.translation_transactions.count_documents({"company_name": "Iris Trading"})
    acme_count = await database.translation_transactions.count_documents({"company_name": "Acme Company"})
    print(f"   Iris Trading: {iris_count} transactions")
    print(f"   Acme Company: {acme_count} transactions")

    # Show samples
    print(f"\n📄 Sample Iris Trading transactions:")
    async for txn in database.translation_transactions.find({"company_name": "Iris Trading"}).limit(3):
        print(f"   {txn['transaction_id']} | {txn['file_name']} | {txn['status']} | {txn['created_at']}")

    print("\n" + "=" * 80)
    print("✅ TEST DATA CREATED SUCCESSFULLY")
    print("=" * 80)

    await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
