"""
Setup test data for user_transactions collection with multiple documents support.

This script:
1. Clears ALL records from user_transactions collection
2. Creates 3 test transactions for different users
3. Each transaction has 2-3 documents with mock Google Drive URLs
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
import uuid

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database
from app.utils.user_transaction_helper import create_user_transaction


async def clear_user_transactions():
    """Clear all records from user_transactions collection."""
    print("\n🗑️  Clearing user_transactions collection...")
    collection = database.user_transactions
    result = await collection.delete_many({})
    print(f"✅ Deleted {result.deleted_count} records from user_transactions")


async def create_test_transaction_1():
    """Create test transaction for user 1 with 2 documents."""
    print("\n📄 Creating transaction 1 for John Doe...")

    documents = [
        {
            "document_name": "Business_Contract_2024.pdf",
            "document_url": "https://drive.google.com/file/d/1ABC_contract_2024/view",
            "translated_url": "https://drive.google.com/file/d/1ABC_contract_2024_es/view",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 20, 10, 0, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 20, 10, 15, 0, tzinfo=timezone.utc),
        },
        {
            "document_name": "Invoice_Q4_2024.docx",
            "document_url": "https://drive.google.com/file/d/1DEF_invoice_q4/view",
            "translated_url": "https://drive.google.com/file/d/1DEF_invoice_q4_es/view",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 20, 10, 5, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 20, 10, 20, 0, tzinfo=timezone.utc),
        },
    ]

    result = await create_user_transaction(
        user_name="John Doe",
        user_email="john.doe@example.com",
        documents=documents,
        number_of_units=25,
        unit_type="page",
        cost_per_unit=0.15,
        source_language="en",
        target_language="es",
        square_transaction_id=f"SQR-{uuid.uuid4().hex[:16].upper()}",
        date=datetime(2025, 10, 20, 10, 0, 0, tzinfo=timezone.utc),
        status="completed",
        square_payment_id=f"SQPAY-{uuid.uuid4().hex[:16].upper()}",
        amount_cents=375,
        currency="USD",
        payment_status="COMPLETED",
        payment_date=datetime(2025, 10, 20, 10, 0, 0, tzinfo=timezone.utc),
    )

    if result:
        print(f"✅ Created transaction: {result}")
    else:
        print("❌ Failed to create transaction 1")


async def create_test_transaction_2():
    """Create test transaction for user 2 with 3 documents."""
    print("\n📄 Creating transaction 2 for Jane Smith...")

    documents = [
        {
            "document_name": "Legal_Agreement_Draft.pdf",
            "document_url": "https://drive.google.com/file/d/1GHI_legal_draft/view",
            "translated_url": "https://drive.google.com/file/d/1GHI_legal_draft_fr/view",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 21, 14, 0, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 21, 14, 25, 0, tzinfo=timezone.utc),
        },
        {
            "document_name": "Technical_Specifications.docx",
            "document_url": "https://drive.google.com/file/d/1JKL_tech_specs/view",
            "translated_url": "https://drive.google.com/file/d/1JKL_tech_specs_fr/view",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 21, 14, 10, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 21, 14, 35, 0, tzinfo=timezone.utc),
        },
        {
            "document_name": "User_Manual_v2.txt",
            "document_url": "https://drive.google.com/file/d/1MNO_user_manual/view",
            "translated_url": "https://drive.google.com/file/d/1MNO_user_manual_fr/view",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 21, 14, 15, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 21, 14, 40, 0, tzinfo=timezone.utc),
        },
    ]

    result = await create_user_transaction(
        user_name="Jane Smith",
        user_email="jane.smith@example.com",
        documents=documents,
        number_of_units=45,
        unit_type="page",
        cost_per_unit=0.15,
        source_language="en",
        target_language="fr",
        square_transaction_id=f"SQR-{uuid.uuid4().hex[:16].upper()}",
        date=datetime(2025, 10, 21, 14, 0, 0, tzinfo=timezone.utc),
        status="completed",
        square_payment_id=f"SQPAY-{uuid.uuid4().hex[:16].upper()}",
        amount_cents=675,
        currency="USD",
        payment_status="COMPLETED",
        payment_date=datetime(2025, 10, 21, 14, 0, 0, tzinfo=timezone.utc),
    )

    if result:
        print(f"✅ Created transaction: {result}")
    else:
        print("❌ Failed to create transaction 2")


async def create_test_transaction_3():
    """Create test transaction for user 3 with 2 documents (one in progress)."""
    print("\n📄 Creating transaction 3 for Bob Johnson...")

    documents = [
        {
            "document_name": "Marketing_Campaign_2025.pdf",
            "document_url": "https://drive.google.com/file/d/1PQR_marketing/view",
            "translated_url": "https://drive.google.com/file/d/1PQR_marketing_de/view",
            "status": "completed",
            "uploaded_at": datetime(2025, 10, 22, 9, 0, 0, tzinfo=timezone.utc),
            "translated_at": datetime(2025, 10, 22, 9, 18, 0, tzinfo=timezone.utc),
        },
        {
            "document_name": "Product_Catalog_2025.docx",
            "document_url": "https://drive.google.com/file/d/1STU_catalog/view",
            "translated_url": None,
            "status": "translating",
            "uploaded_at": datetime(2025, 10, 22, 9, 5, 0, tzinfo=timezone.utc),
            "translated_at": None,
        },
    ]

    result = await create_user_transaction(
        user_name="Bob Johnson",
        user_email="bob.johnson@example.com",
        documents=documents,
        number_of_units=30,
        unit_type="page",
        cost_per_unit=0.15,
        source_language="en",
        target_language="de",
        square_transaction_id=f"SQR-{uuid.uuid4().hex[:16].upper()}",
        date=datetime(2025, 10, 22, 9, 0, 0, tzinfo=timezone.utc),
        status="processing",
        square_payment_id=f"SQPAY-{uuid.uuid4().hex[:16].upper()}",
        amount_cents=450,
        currency="USD",
        payment_status="COMPLETED",
        payment_date=datetime(2025, 10, 22, 9, 0, 0, tzinfo=timezone.utc),
    )

    if result:
        print(f"✅ Created transaction: {result}")
    else:
        print("❌ Failed to create transaction 3")


async def verify_test_data():
    """Verify created test data."""
    print("\n🔍 Verifying test data...")
    collection = database.user_transactions

    transactions = await collection.find({}).to_list(length=10)
    print(f"\n📊 Total transactions: {len(transactions)}")

    for idx, txn in enumerate(transactions, 1):
        print(f"\n  Transaction {idx}:")
        print(f"    User: {txn['user_name']} ({txn['user_email']})")
        print(f"    Status: {txn['status']}")
        print(f"    Documents: {len(txn['documents'])}")
        for doc_idx, doc in enumerate(txn['documents'], 1):
            print(f"      {doc_idx}. {doc['document_name']} - Status: {doc['status']}")
        print(f"    Total Cost: ${txn['total_cost']:.2f}")
        print(f"    Square ID: {txn['square_transaction_id']}")


async def main():
    """Main execution function."""
    print("=" * 60)
    print("🚀 Setup Test User Transactions (Multi-Document Support)")
    print("=" * 60)

    try:
        # Connect to database
        print("\n🔌 Connecting to MongoDB...")
        await database.connect()
        print("✅ Connected to database")

        # Step 1: Clear existing data
        await clear_user_transactions()

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
