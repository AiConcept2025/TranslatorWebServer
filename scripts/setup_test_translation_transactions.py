"""
Setup test data for translation_transactions collection with multiple documents support.

This script:
1. Clears ALL records from translation_transactions collection
2. Creates 3 test transactions for different companies/users
3. Each transaction has 2-3 documents with mock Google Drive URLs and processing details
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database
from app.services.translation_transaction_service import create_translation_transaction


async def clear_translation_transactions():
    """Clear all records from translation_transactions collection."""
    print("\n🗑️  Clearing translation_transactions collection...")
    collection = database.translation_transactions
    result = await collection.delete_many({})
    print(f"✅ Deleted {result.deleted_count} records from translation_transactions")


async def create_test_transaction_1():
    """Create test transaction for Iris Trading company with 2 documents."""
    print("\n📄 Creating transaction 1 for Iris Trading...")

    # Generate unique transaction ID
    transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"

    documents = [
        {
            "file_name": "Business_Contract_2024.pdf",
            "file_size": 524288,
            "original_url": "https://drive.google.com/file/d/1ABC_contract_2024/view",
            "translated_url": "https://drive.google.com/file/d/1ABC_contract_2024_fr/view",
            "translated_name": "Business_Contract_2024_fr.pdf",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 20, 10, 0, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 20, 10, 15, 0, tzinfo=timezone.utc),
            "processing_started_at": datetime(2025, 10, 20, 10, 0, 5, tzinfo=timezone.utc),
            "processing_duration": 895.5
        },
        {
            "file_name": "Invoice_Q4_2024.docx",
            "file_size": 196608,
            "original_url": "https://drive.google.com/file/d/1DEF_invoice_q4/view",
            "translated_url": "https://drive.google.com/file/d/1DEF_invoice_q4_fr/view",
            "translated_name": "Invoice_Q4_2024_fr.docx",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 20, 10, 5, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 20, 10, 20, 0, tzinfo=timezone.utc),
            "processing_started_at": datetime(2025, 10, 20, 10, 5, 5, tzinfo=timezone.utc),
            "processing_duration": 895.0
        },
    ]

    result = await create_translation_transaction(
        transaction_id=transaction_id,
        user_id="admin@iristrading.com",
        documents=documents,
        source_language="en",
        target_language="fr",
        units_count=25,
        price_per_unit=0.01,
        total_price=0.25,
        status="confirmed",
        error_message="",
        company_name="Iris Trading",
        subscription_id="68fa6add22b0c739f4f4b273",
        unit_type="page"
    )

    if result:
        print(f"✅ Created transaction: {transaction_id} (DB ID: {result})")
    else:
        print(f"❌ Failed to create transaction 1")


async def create_test_transaction_2():
    """Create test transaction for Tech Solutions company with 3 documents."""
    print("\n📄 Creating transaction 2 for Tech Solutions...")

    # Generate unique transaction ID
    transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"

    documents = [
        {
            "file_name": "Legal_Agreement_Draft.pdf",
            "file_size": 1048576,
            "original_url": "https://drive.google.com/file/d/1GHI_legal_draft/view",
            "translated_url": "https://drive.google.com/file/d/1GHI_legal_draft_es/view",
            "translated_name": "Legal_Agreement_Draft_es.pdf",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 21, 14, 0, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 21, 14, 25, 0, tzinfo=timezone.utc),
            "processing_started_at": datetime(2025, 10, 21, 14, 0, 10, tzinfo=timezone.utc),
            "processing_duration": 1490.0
        },
        {
            "file_name": "Technical_Specifications.docx",
            "file_size": 327680,
            "original_url": "https://drive.google.com/file/d/1JKL_tech_specs/view",
            "translated_url": "https://drive.google.com/file/d/1JKL_tech_specs_es/view",
            "translated_name": "Technical_Specifications_es.docx",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 21, 14, 10, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 21, 14, 35, 0, tzinfo=timezone.utc),
            "processing_started_at": datetime(2025, 10, 21, 14, 10, 8, tzinfo=timezone.utc),
            "processing_duration": 1492.0
        },
        {
            "file_name": "User_Manual_v2.txt",
            "file_size": 81920,
            "original_url": "https://drive.google.com/file/d/1MNO_user_manual/view",
            "translated_url": "https://drive.google.com/file/d/1MNO_user_manual_es/view",
            "translated_name": "User_Manual_v2_es.txt",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 21, 14, 15, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 21, 14, 40, 0, tzinfo=timezone.utc),
            "processing_started_at": datetime(2025, 10, 21, 14, 15, 6, tzinfo=timezone.utc),
            "processing_duration": 1494.0
        },
    ]

    result = await create_translation_transaction(
        transaction_id=transaction_id,
        user_id="manager@techsolutions.com",
        documents=documents,
        source_language="en",
        target_language="es",
        units_count=45,
        price_per_unit=0.01,
        total_price=0.45,
        status="confirmed",
        error_message="",
        company_name="Tech Solutions",
        subscription_id="68fa6add22b0c739f4f4b274",
        unit_type="page"
    )

    if result:
        print(f"✅ Created transaction: {transaction_id} (DB ID: {result})")
    else:
        print(f"❌ Failed to create transaction 2")


async def create_test_transaction_3():
    """Create test transaction for Global Corp with 2 documents (one in progress)."""
    print("\n📄 Creating transaction 3 for Global Corp...")

    # Generate unique transaction ID
    transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"

    documents = [
        {
            "file_name": "Marketing_Campaign_2025.pdf",
            "file_size": 2097152,
            "original_url": "https://drive.google.com/file/d/1PQR_marketing/view",
            "translated_url": "https://drive.google.com/file/d/1PQR_marketing_de/view",
            "translated_name": "Marketing_Campaign_2025_de.pdf",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 22, 9, 0, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 22, 9, 18, 0, tzinfo=timezone.utc),
            "processing_started_at": datetime(2025, 10, 22, 9, 0, 12, tzinfo=timezone.utc),
            "processing_duration": 1068.0
        },
        {
            "file_name": "Product_Catalog_2025.docx",
            "file_size": 3145728,
            "original_url": "https://drive.google.com/file/d/1STU_catalog/view",
            "translated_url": None,
            "translated_name": None,
            "status": "translating",
            "uploaded_at": datetime(2025, 10, 22, 9, 5, 0, tzinfo=timezone.utc),
            "translated_at": None,
            "processing_started_at": datetime(2025, 10, 22, 9, 5, 15, tzinfo=timezone.utc),
            "processing_duration": None
        },
    ]

    result = await create_translation_transaction(
        transaction_id=transaction_id,
        user_id="director@globalcorp.com",
        documents=documents,
        source_language="en",
        target_language="de",
        units_count=30,
        price_per_unit=0.01,
        total_price=0.30,
        status="started",
        error_message="",
        company_name="Global Corp",
        subscription_id="68fa6add22b0c739f4f4b275",
        unit_type="page"
    )

    if result:
        print(f"✅ Created transaction: {transaction_id} (DB ID: {result})")
    else:
        print(f"❌ Failed to create transaction 3")


async def verify_test_data():
    """Verify created test data."""
    print("\n🔍 Verifying test data...")
    collection = database.translation_transactions

    transactions = await collection.find({}).to_list(length=10)
    print(f"\n📊 Total transactions: {len(transactions)}")

    for idx, txn in enumerate(transactions, 1):
        print(f"\n  Transaction {idx}:")
        print(f"    Transaction ID: {txn['transaction_id']}")
        print(f"    User: {txn['user_id']}")
        print(f"    Company: {txn['company_name']}")
        print(f"    Status: {txn['status']}")
        print(f"    Documents: {len(txn['documents'])}")
        for doc_idx, doc in enumerate(txn['documents'], 1):
            print(f"      {doc_idx}. {doc['file_name']} - Status: {doc['status']}")
            if doc.get('processing_duration'):
                print(f"         Processing Duration: {doc['processing_duration']:.1f}s")
        print(f"    Total Price: ${txn['total_price']:.2f}")
        print(f"    Languages: {txn['source_language']} → {txn['target_language']}")


async def main():
    """Main execution function."""
    print("=" * 60)
    print("🚀 Setup Test Translation Transactions (Multi-Document Support)")
    print("=" * 60)

    try:
        # Connect to database
        print("\n🔌 Connecting to MongoDB...")
        await database.connect()
        print("✅ Connected to database")

        # Step 1: Clear existing data
        await clear_translation_transactions()

        # Step 2: Create test transactions
        await create_test_transaction_1()
        await create_test_transaction_2()
        await create_test_transaction_3()

        # Step 3: Verify
        await verify_test_data()

        print("\n" + "=" * 60)
        print("✅ Test data setup complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
