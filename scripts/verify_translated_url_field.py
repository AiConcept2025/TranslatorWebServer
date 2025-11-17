#!/usr/bin/env python3
"""
Verify that user_transactions collection has translated_url field in documents array.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def main():
    """Verify translated_url field exists in all documents."""
    print("\n" + "=" * 80)
    print("🔍 VERIFYING translated_url FIELD IN user_transactions")
    print("=" * 80 + "\n")

    await database.connect()

    collection = database.user_transactions
    transactions = await collection.find({"user_email": "danishevsky@yahoo.com"}).to_list(length=10)

    print(f"📊 Found {len(transactions)} transactions for danishevsky@yahoo.com\n")

    all_valid = True

    for idx, txn in enumerate(transactions, 1):
        print(f"Transaction {idx}: {txn.get('transaction_id')} (Status: {txn.get('status')})")

        documents = txn.get('documents', [])
        print(f"  Documents count: {len(documents)}")

        for doc_idx, doc in enumerate(documents, 1):
            file_name = doc.get('file_name', 'N/A')
            has_translated_url = 'translated_url' in doc
            translated_url_value = doc.get('translated_url')

            if has_translated_url:
                status_icon = "✅"
                print(f"    [{doc_idx}] ✅ {file_name}")
                print(f"         - translated_url: {translated_url_value}")
            else:
                status_icon = "❌"
                all_valid = False
                print(f"    [{doc_idx}] ❌ {file_name} - MISSING translated_url field!")

        print()

    print("=" * 80)
    if all_valid:
        print("✅ SUCCESS: All documents have 'translated_url' field")
    else:
        print("❌ FAILURE: Some documents missing 'translated_url' field")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
