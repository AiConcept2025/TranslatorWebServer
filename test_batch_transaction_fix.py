#!/usr/bin/env python3
"""
Test script to verify batch transaction fix.
Checks that /translate-user creates ONE transaction record for multiple files.
"""

import asyncio
from datetime import datetime, timezone
from app.database.mongodb import database


async def check_recent_transactions():
    """Check recent transactions to verify fix."""

    print("\n" + "=" * 80)
    print("BATCH TRANSACTION FIX VERIFICATION")
    print("=" * 80)
    print()

    await database.connect()

    # Get the 5 most recent user_transactions
    recent_txns = await database.user_transactions.find().sort("created_at", -1).limit(5).to_list(5)

    print(f"Found {len(recent_txns)} recent transactions")
    print()

    for idx, txn in enumerate(recent_txns, 1):
        txn_id = txn.get("transaction_id", "N/A")
        user_email = txn.get("user_email", txn.get("user_id", "N/A"))
        created_at = txn.get("created_at", "N/A")
        num_docs = len(txn.get("documents", []))
        square_tx_id = txn.get("square_transaction_id", "N/A")

        print(f"Transaction {idx}:")
        print(f"  ID: {txn_id}")
        print(f"  User: {user_email}")
        print(f"  Created: {created_at}")
        print(f"  Documents: {num_docs}")
        print(f"  Square TX ID: {square_tx_id}")

        # Show document names
        if num_docs > 0:
            print(f"  Files:")
            for doc_idx, doc in enumerate(txn.get("documents", []), 1):
                print(f"    {doc_idx}. {doc.get('file_name', 'N/A')}")

        print()

    print("=" * 80)
    print("EXPECTED BEHAVIOR AFTER FIX")
    print("=" * 80)
    print()
    print("✅ If user uploads 2 files → should see 1 transaction with 2 documents")
    print("❌ BEFORE FIX: Would see 2 transactions with 1 document each")
    print()
    print("To test:")
    print("1. Upload 2 files via UI")
    print("2. Check this list again")
    print("3. Verify ONE transaction record created with BOTH documents")
    print()

    await database.disconnect()


if __name__ == "__main__":
    asyncio.run(check_recent_transactions())
