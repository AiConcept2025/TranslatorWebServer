#!/usr/bin/env python3
"""
Create 2 user transactions for testing the User Transactions table.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def create_user_transactions():
    """Create 2 user transactions for john.doe@example.com."""
    print("=" * 80)
    print("CREATING USER TRANSACTIONS FOR TESTING")
    print("=" * 80)

    # Connect to database
    print("\nConnecting to MongoDB...")
    await database.connect()
    print("✓ Connected")

    # User email (matches the hardcoded email in AdminDashboard.tsx)
    user_email = "john.doe@example.com"
    user_name = "John Doe"

    # Transaction 1: Completed transaction from 5 days ago
    transaction_1 = {
        "user_name": user_name,
        "user_email": user_email,
        "document_url": "https://drive.google.com/file/d/1XYZ_contract_document/view",
        "number_of_units": 15,
        "unit_type": "page",
        "cost_per_unit": 0.12,
        "source_language": "en",
        "target_language": "fr",
        "square_transaction_id": f"SQR-{datetime.now().strftime('%Y%m%d')}A1B2C3",
        "date": datetime.now() - timedelta(days=5),
        "status": "completed",
        "total_cost": 1.80,  # 15 * 0.12
        "created_at": datetime.now() - timedelta(days=5),
        "updated_at": datetime.now() - timedelta(days=5)
    }

    # Transaction 2: Pending transaction from 2 days ago
    transaction_2 = {
        "user_name": user_name,
        "user_email": user_email,
        "document_url": "https://drive.google.com/file/d/2ABC_report_document/view",
        "number_of_units": 8,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "de",
        "target_language": "en",
        "square_transaction_id": f"SQR-{datetime.now().strftime('%Y%m%d')}D4E5F6",
        "date": datetime.now() - timedelta(days=2),
        "status": "pending",
        "total_cost": 1.20,  # 8 * 0.15
        "created_at": datetime.now() - timedelta(days=2),
        "updated_at": datetime.now() - timedelta(days=2)
    }

    print(f"\nInserting transactions for user: {user_email}")

    # Check if the user already has transactions (to avoid duplicate square_transaction_ids)
    existing_txn_1 = await database.user_transactions.find_one(
        {"square_transaction_id": transaction_1["square_transaction_id"]}
    )
    existing_txn_2 = await database.user_transactions.find_one(
        {"square_transaction_id": transaction_2["square_transaction_id"]}
    )

    # Insert transaction 1
    if existing_txn_1:
        print(f"\n1. Transaction already exists: {transaction_1['square_transaction_id']}")
    else:
        print("\n1. Inserting completed transaction (5 days ago)...")
        result_1 = await database.user_transactions.insert_one(transaction_1)
        print(f"   ✓ Inserted transaction: {result_1.inserted_id}")
        print(f"   - Square ID: {transaction_1['square_transaction_id']}")
        print(f"   - Status: {transaction_1['status']}")
        print(f"   - Amount: ${transaction_1['total_cost']}")
        print(f"   - Units: {transaction_1['number_of_units']} {transaction_1['unit_type']}")
        print(f"   - Languages: {transaction_1['source_language']} → {transaction_1['target_language']}")

    # Insert transaction 2
    if existing_txn_2:
        print(f"\n2. Transaction already exists: {transaction_2['square_transaction_id']}")
    else:
        print("\n2. Inserting pending transaction (2 days ago)...")
        result_2 = await database.user_transactions.insert_one(transaction_2)
        print(f"   ✓ Inserted transaction: {result_2.inserted_id}")
        print(f"   - Square ID: {transaction_2['square_transaction_id']}")
        print(f"   - Status: {transaction_2['status']}")
        print(f"   - Amount: ${transaction_2['total_cost']}")
        print(f"   - Units: {transaction_2['number_of_units']} {transaction_2['unit_type']}")
        print(f"   - Languages: {transaction_2['source_language']} → {transaction_2['target_language']}")

    # Verify all transactions for user
    print(f"\n\nVerifying all transactions for user {user_email}...")
    all_transactions = await database.user_transactions.find(
        {"user_email": user_email}
    ).sort("date", -1).to_list(length=100)

    print(f"\n✅ Total transactions found: {len(all_transactions)}")
    print("\nTransaction Summary (sorted by date, newest first):")
    print("-" * 80)
    for txn in all_transactions:
        print(f"  • {txn['square_transaction_id']} - ${txn['total_cost']:.2f} - Status: {txn['status']}")
        print(f"    Date: {txn['date'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Units: {txn['number_of_units']} {txn['unit_type']}")
        print(f"    Languages: {txn['source_language']} → {txn['target_language']}")
        print(f"    Document: {txn['document_url']}")
        print(f"    ID: {txn['_id']}")
        print()

    # Disconnect
    print("=" * 80)
    await database.disconnect()
    print("✓ Disconnected")
    print("\n✅ SUCCESS: User transactions created and verified!")


if __name__ == "__main__":
    asyncio.run(create_user_transactions())
