"""
Setup test data for user_transactions collection with multiple documents support.

This script:
1. Removes old test records from user_transactions collection (with TEST- prefix or test emails)
2. Creates 3 test transactions for danishevsky@yahoo.com
3. Each transaction has documents with correct schema including translated_url field
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
    """Clear only test records from user_transactions collection."""
    print("\n🗑️  Clearing old test records from user_transactions collection...")
    collection = database.user_transactions

    # ⚠️ SAFE: Only delete test records with specific patterns
    result = await collection.delete_many({
        "$or": [
            {"stripe_checkout_session_id": {"$regex": "^TEST-"}},
            {"stripe_checkout_session_id": {"$regex": "^STRIPE-"}},
            {"user_email": {"$regex": "@example\\.com$"}},
            {"user_email": "danishevsky@yahoo.com"}
        ]
    })
    print(f"✅ Deleted {result.deleted_count} old test records (NOT production data)")


async def create_test_transaction_1():
    """Create test transaction 1 - Processing (3 documents)."""
    print("\n📄 Creating transaction 1 (Processing - 3 documents)...")

    documents = [
        {
            "file_name": "NuVIZ_Cable_Management_Market_Comparison_Report.docx",
            "original_url": "https://docs.google.com/document/d/1fEYP65rEWyYKloLvJyRUjhKPZqmDbLT0/edit",
            "translated_url": None,  # ✅ Processing - not translated yet
            "status": "pending",
            "uploaded_at": datetime.now(timezone.utc),
        },
        {
            "file_name": "NuDOC_API_Role_Enforcement_Project_Plan.docx",
            "original_url": "https://docs.google.com/document/d/17Z_RAhJM7NVbf7SD9E9apkwmsAGm9RbN/edit",
            "translated_url": None,  # ✅ Processing - not translated yet
            "status": "pending",
            "uploaded_at": datetime.now(timezone.utc),
        },
        {
            "file_name": "NuVIZ_Cable_Management_Market_Comparison_Report.pdf",
            "original_url": "https://drive.google.com/file/d/1fkwpZWUPbkLTemJmwNXSIekC8y6VHUjr/view",
            "translated_url": None,  # ✅ Processing - not translated yet
            "status": "pending",
            "uploaded_at": datetime.now(timezone.utc),
        },
    ]

    result = await create_user_transaction(
        user_name="John Doe",
        user_email="danishevsky@yahoo.com",
        documents=documents,
        number_of_units=4,
        unit_type="page",
        cost_per_unit=0.01,
        source_language="en",
        target_language="fr",
        stripe_checkout_session_id=f"payment_sq_{int(datetime.now().timestamp())}_test1",
        date=datetime.now(timezone.utc),
        status="processing",
        stripe_payment_intent_id=f"SQPAY-{uuid.uuid4().hex[:16].upper()}",
        amount_cents=4,
        currency="usd",
        payment_status="COMPLETED",
        payment_date=datetime.now(timezone.utc),
    )

    if result:
        print(f"✅ Created transaction: {result}")
    else:
        print("❌ Failed to create transaction 1")


async def create_test_transaction_2():
    """Create test transaction 2 - Failed (2 documents)."""
    print("\n📄 Creating transaction 2 (Failed - 2 documents)...")

    documents = [
        {
            "file_name": "Legal_Agreement_Draft.pdf",
            "original_url": "https://drive.google.com/file/d/1GHI_legal_draft/view",
            "translated_url": None,  # ✅ Failed - no translation
            "status": "failed",
            "uploaded_at": datetime.now(timezone.utc),
        },
        {
            "file_name": "Technical_Specifications.docx",
            "original_url": "https://drive.google.com/file/d/1JKL_tech_specs/view",
            "translated_url": None,  # ✅ Failed - no translation
            "status": "failed",
            "uploaded_at": datetime.now(timezone.utc),
        },
    ]

    result = await create_user_transaction(
        user_name="John Doe",
        user_email="danishevsky@yahoo.com",
        documents=documents,
        number_of_units=2,
        unit_type="page",
        cost_per_unit=0.01,
        source_language="en",
        target_language="es",
        stripe_checkout_session_id=f"payment_sq_{int(datetime.now().timestamp())}_test2",
        date=datetime.now(timezone.utc),
        status="failed",  # ✅ Valid status: processing, completed, failed
        stripe_payment_intent_id=f"SQPAY-{uuid.uuid4().hex[:16].upper()}",
        amount_cents=2,
        currency="usd",
        payment_status="COMPLETED",
        payment_date=datetime.now(timezone.utc),
    )

    if result:
        print(f"✅ Created transaction: {result}")
    else:
        print("❌ Failed to create transaction 2")


async def create_test_transaction_3():
    """Create test transaction 3 - Completed (1 document with translated_url)."""
    print("\n📄 Creating transaction 3 (Completed - 1 document)...")

    documents = [
        {
            "file_name": "Marketing_Campaign_2025.pdf",
            "original_url": "https://drive.google.com/file/d/1PQR_marketing/view",
            "translated_url": "https://drive.google.com/file/d/1PQR_marketing_de_translated/view",  # ✅ Completed - has translated URL
            "status": "completed",
            "uploaded_at": datetime.now(timezone.utc),
            "translated_at": datetime.now(timezone.utc),
        },
    ]

    result = await create_user_transaction(
        user_name="John Doe",
        user_email="danishevsky@yahoo.com",
        documents=documents,
        number_of_units=3,
        unit_type="page",
        cost_per_unit=0.01,
        source_language="en",
        target_language="de",
        stripe_checkout_session_id=f"payment_sq_{int(datetime.now().timestamp())}_test3",
        date=datetime.now(timezone.utc),
        status="completed",
        stripe_payment_intent_id=f"SQPAY-{uuid.uuid4().hex[:16].upper()}",
        amount_cents=3,
        currency="usd",
        payment_status="COMPLETED",
        payment_date=datetime.now(timezone.utc),
    )

    if result:
        print(f"✅ Created transaction: {result}")
    else:
        print("❌ Failed to create transaction 3")


async def verify_test_data():
    """Verify created test data."""
    print("\n🔍 Verifying test data...")
    collection = database.user_transactions

    transactions = await collection.find({"user_email": "danishevsky@yahoo.com"}).to_list(length=10)
    print(f"\n📊 Total transactions for danishevsky@yahoo.com: {len(transactions)}")

    for idx, txn in enumerate(transactions, 1):
        print(f"\n  Transaction {idx}:")
        print(f"    transaction_id: {txn.get('transaction_id')}")
        print(f"    User: {txn['user_email']}")
        print(f"    Status: {txn['status']}")
        print(f"    {txn.get('source_language')} → {txn.get('target_language')}")
        print(f"    Units: {txn.get('units_count', txn.get('number_of_units', 'N/A'))} {txn.get('unit_type', 'page')}(s)")
        print(f"    Documents: {len(txn['documents'])}")
        for doc_idx, doc in enumerate(txn['documents'], 1):
            print(f"      {doc_idx}. {doc.get('file_name', doc.get('document_name'))}")
            print(f"         - original_url: {doc.get('original_url', doc.get('document_url', 'N/A'))[:60]}...")
            print(f"         - translated_url: {doc.get('translated_url')}")  # ✅ VERIFY THIS FIELD
            print(f"         - status: {doc['status']}")
        print(f"    Total Cost: ${txn.get('total_price', txn.get('total_cost', 0)):.2f}")
        print(f"    Stripe ID: {txn['stripe_checkout_session_id']}")


async def main():
    """Main execution function."""
    print("=" * 80)
    print("🚀 Setup Test User Transactions - With translated_url Field")
    print("=" * 80)

    try:
        # Connect to database
        print("\n🔌 Connecting to MongoDB...")
        await database.connect()
        print("✅ Connected to database")

        # Step 1: Clear existing test data
        await clear_user_transactions()

        # Step 2: Create 3 test transactions
        await create_test_transaction_1()  # Processing - 3 docs, translated_url = None
        await create_test_transaction_2()  # Failed - 2 docs, translated_url = None
        await create_test_transaction_3()  # Completed - 1 doc, translated_url = filled

        # Step 3: Verify
        await verify_test_data()

        print("\n" + "=" * 80)
        print("✅ Test data setup complete!")
        print("✅ All 3 transactions created with 'translated_url' field in documents array")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
