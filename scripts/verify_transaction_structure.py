"""
Verification script for user transaction structure.

This script queries the database and verifies:
1. transaction_id exists at parent level (USER format)
2. transaction_id does NOT exist in documents array
3. Clear display of transaction structure

Run: python scripts/verify_transaction_structure.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import database
from app.utils.transaction_id_generator import validate_transaction_id_format


async def verify_structure():
    """Verify user transaction structure in database."""
    print("=" * 80)
    print("USER TRANSACTION STRUCTURE VERIFICATION")
    print("=" * 80)
    print()

    # Connect to database
    print("📡 Connecting to database...")
    await database.connect()
    print("✅ Database connected\n")

    collection = database.user_transactions

    # Get recent transactions (limit to 5 for display)
    print("🔍 Fetching recent user transactions...")
    cursor = collection.find().sort("created_at", -1).limit(5)
    transactions = await cursor.to_list(length=5)

    if not transactions:
        print("⚠️  No user transactions found in database\n")
        return

    print(f"✅ Found {len(transactions)} recent transactions\n")
    print("=" * 80)

    for idx, txn in enumerate(transactions, 1):
        print(f"\n📋 Transaction {idx}/{len(transactions)}")
        print("-" * 80)

        # Check parent-level transaction_id
        has_parent_txn_id = "transaction_id" in txn
        parent_txn_id = txn.get("transaction_id", "MISSING")

        if has_parent_txn_id:
            is_valid_format = validate_transaction_id_format(parent_txn_id)
            format_emoji = "✅" if is_valid_format else "❌"

            print(f"  Parent Level:")
            print(f"    transaction_id: {format_emoji} {parent_txn_id}")
            print(f"    Format: {'USER format (CORRECT)' if is_valid_format else 'Invalid format (WRONG)'}")
        else:
            print(f"  Parent Level:")
            print(f"    transaction_id: ❌ MISSING (should exist at parent level)")

        print(f"    stripe_checkout_session_id: {txn.get('stripe_checkout_session_id', 'N/A')}")
        print(f"    user_email: {txn.get('user_email', 'N/A')}")
        print(f"    status: {txn.get('status', 'N/A')}")
        print(f"    total_cost: ${txn.get('total_cost', 0)}")

        # Check documents array
        documents = txn.get("documents", [])
        print(f"\n  Documents Array ({len(documents)} documents):")

        if not documents:
            print("    (No documents)")
        else:
            all_correct = True
            for doc_idx, doc in enumerate(documents, 1):
                has_doc_txn_id = "transaction_id" in doc
                file_name = doc.get('file_name') or doc.get('document_name', f'Document {doc_idx}')

                if has_doc_txn_id:
                    print(f"    ❌ Document {doc_idx}: {file_name}")
                    print(f"       ERROR: Has transaction_id field (should NOT be here)")
                    print(f"       Value: {doc['transaction_id']}")
                    all_correct = False
                else:
                    print(f"    ✅ Document {doc_idx}: {file_name}")
                    print(f"       CORRECT: No transaction_id field")

            if all_correct:
                print(f"\n  ✅ STRUCTURE CORRECT: All documents have no transaction_id")
            else:
                print(f"\n  ❌ STRUCTURE INCORRECT: Some documents have transaction_id (should be removed)")

        print()
        print("-" * 80)

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    correct_count = 0
    incorrect_count = 0

    for txn in transactions:
        has_parent_txn_id = "transaction_id" in txn
        is_valid_format = validate_transaction_id_format(txn.get("transaction_id", "")) if has_parent_txn_id else False

        documents = txn.get("documents", [])
        docs_have_txn_id = any("transaction_id" in doc for doc in documents)

        if has_parent_txn_id and is_valid_format and not docs_have_txn_id:
            correct_count += 1
        else:
            incorrect_count += 1

    print(f"\n✅ Correct Structure: {correct_count}/{len(transactions)} transactions")
    print(f"❌ Incorrect Structure: {incorrect_count}/{len(transactions)} transactions")

    if incorrect_count == 0:
        print(f"\n🎉 ALL TRANSACTIONS HAVE CORRECT STRUCTURE!")
        print(f"   • transaction_id at parent level (USER format)")
        print(f"   • No transaction_id in documents array")
    else:
        print(f"\n⚠️  SOME TRANSACTIONS HAVE INCORRECT STRUCTURE")
        print(f"   Action needed: Review transactions above")

    print("\n" + "=" * 80)
    print()


async def verify_single_transaction(stripe_checkout_session_id: str):
    """Verify structure of a specific transaction by stripe_checkout_session_id."""
    print("=" * 80)
    print(f"VERIFYING TRANSACTION: {stripe_checkout_session_id}")
    print("=" * 80)
    print()

    await database.connect()

    collection = database.user_transactions
    txn = await collection.find_one({"stripe_checkout_session_id": stripe_checkout_session_id})

    if not txn:
        print(f"❌ Transaction not found: {stripe_checkout_session_id}\n")
        return

    print("📋 Transaction Found")
    print("-" * 80)

    # Parent level
    print("\n  Parent Level Fields:")
    print(f"    • _id: {txn['_id']}")
    print(f"    • transaction_id: {txn.get('transaction_id', 'MISSING')}")
    print(f"    • stripe_checkout_session_id: {txn.get('stripe_checkout_session_id')}")
    print(f"    • user_email: {txn.get('user_email')}")

    # Validate format
    if "transaction_id" in txn:
        is_valid = validate_transaction_id_format(txn["transaction_id"])
        print(f"    • Format Valid: {'✅ YES' if is_valid else '❌ NO'}")

    # Documents
    print(f"\n  Documents Array ({len(txn.get('documents', []))} documents):")
    for idx, doc in enumerate(txn.get("documents", []), 1):
        print(f"\n    Document {idx}: {doc.get('file_name')}")
        print(f"      • file_size: {doc.get('file_size')} bytes")
        print(f"      • status: {doc.get('status')}")

        if "transaction_id" in doc:
            print(f"      • transaction_id: ❌ {doc['transaction_id']} (SHOULD NOT BE HERE)")
        else:
            print(f"      • transaction_id: ✅ Not present (CORRECT)")

    print("\n" + "=" * 80)
    print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Verify specific transaction
        square_txn_id = sys.argv[1]
        asyncio.run(verify_single_transaction(square_txn_id))
    else:
        # Verify recent transactions
        asyncio.run(verify_structure())
