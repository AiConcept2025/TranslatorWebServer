#!/usr/bin/env python3
"""
Diagnostic script to understand why webhook is not updating translated_url and translated_name.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database.mongodb import database


async def main():
    """Diagnose webhook update issue."""

    print("\n" + "=" * 80)
    print("WEBHOOK ISSUE DIAGNOSIS")
    print("=" * 80 + "\n")

    await database.connect()

    # Get the transaction
    transaction_id = "TXN-E4E38F3A75"

    transaction = await database.user_transactions.find_one(
        {"transaction_id": transaction_id}
    )

    if not transaction:
        print(f"❌ Transaction {transaction_id} not found")
        return

    print(f"Transaction ID: {transaction['transaction_id']}")
    print(f"User: {transaction['user_email']}")
    print(f"Created: {transaction['created_at']}")
    print(f"Status: {transaction['status']}")
    print()

    documents = transaction.get("documents", [])
    print(f"Documents in transaction: {len(documents)}")
    print()

    # Show each document
    for idx, doc in enumerate(documents, 1):
        print(f"Document {idx}:")
        print(f"  file_name: {doc.get('file_name')}")
        print(f"  file_size: {doc.get('file_size')}")
        print(f"  status: {doc.get('status')}")
        print(f"  original_url: {doc.get('original_url', 'N/A')[:60]}...")
        print(f"  translated_url: {doc.get('translated_url')}")
        print(f"  translated_name: {doc.get('translated_name')}")
        print(f"  uploaded_at: {doc.get('uploaded_at')}")
        print(f"  translated_at: {doc.get('translated_at')}")
        print()

    # Simulate what webhook would do
    print("=" * 80)
    print("SIMULATING WEBHOOK PROCESSING")
    print("=" * 80)
    print()

    # The two files that were sent to webhook based on the filenames in the record
    file1 = "Cable_Management_Changes_PRD.docx"
    file2 = "Kevin questions[81] (1).docx"

    print("Simulating webhook for file 1:")
    print(f"  Incoming: {file1}")
    print(f"  Would match: {documents[0]['file_name']}")
    print(f"  Currently translated_url is: {documents[0].get('translated_url')}")
    print()

    print("Simulating webhook for file 2:")
    print(f"  Incoming: {file2}")
    print(f"  Would match: {documents[1]['file_name']}")
    print(f"  Currently translated_url is: {documents[1].get('translated_url')}")
    print()

    # Check if the webhook would find a match
    from app.services.transaction_update_service import normalize_filename_for_comparison

    print("=" * 80)
    print("FILENAME NORMALIZATION CHECK")
    print("=" * 80)
    print()

    for idx, doc in enumerate(documents, 1):
        db_filename = doc.get("file_name", "")
        db_normalized = normalize_filename_for_comparison(db_filename)

        print(f"Document {idx}:")
        print(f"  DB filename: {db_filename}")
        print(f"  Normalized: {db_normalized}")
        print()

    print("Webhook incoming filenames (normalized):")
    print(f"  File 1: {file1} → {normalize_filename_for_comparison(file1)}")
    print(f"  File 2: {file2} → {normalize_filename_for_comparison(file2)}")
    print()

    # Check if the idempotency check would block updates
    print("=" * 80)
    print("IDEMPOTENCY CHECK")
    print("=" * 80)
    print()

    for idx, doc in enumerate(documents, 1):
        has_translated_url = bool(doc.get("translated_url"))
        print(f"Document {idx}: translated_url = {doc.get('translated_url')}")
        print(f"  Would webhook update? {'NO (already has translated_url)' if has_translated_url else 'YES (translated_url is null)'}")
        print()

    await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
