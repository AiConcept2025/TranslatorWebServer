#!/usr/bin/env python3
"""
Debug the malformed record to understand what happened.
"""

import asyncio
from app.database.mongodb import database
import json

async def main():
    await database.connect()

    # Get the malformed record
    malformed = await database.user_transactions.find_one(
        {"transaction_id": "TXN-7AEBBE7D6E"}
    )

    if not malformed:
        print("Record not found")
        return

    print("=" * 80)
    print("MALFORMED RECORD ANALYSIS")
    print("=" * 80)
    print()

    print(f"Transaction ID: {malformed['transaction_id']}")
    print(f"Total documents field: {malformed.get('total_documents')}")
    print(f"Actual documents array length: {len(malformed.get('documents', []))}")
    print()

    print("Documents array:")
    for idx, doc in enumerate(malformed.get('documents', [])):
        print(f"\n  Document {idx}:")
        print(f"    Keys: {list(doc.keys())}")
        print(f"    Type analysis:")

        # Check if it looks like a document
        if 'file_name' in doc:
            print(f"      ✅ Has file_name: {doc['file_name']}")
        else:
            print(f"      ❌ Missing file_name")

        if 'file_size' in doc:
            print(f"      ✅ Has file_size: {doc['file_size']}")
        else:
            print(f"      ❌ Missing file_size")

        # Check if it looks like payment metadata
        if 'payment_method' in doc:
            print(f"      ⚠️  HAS PAYMENT_METHOD! This is transaction-level metadata!")

        if 'square_transaction_id' in doc:
            print(f"      ⚠️  HAS square_transaction_id! This is transaction-level metadata!")

        if 'total_documents' in doc:
            print(f"      ⚠️  HAS total_documents! This is transaction-level metadata!")

        print(f"\n    Full content:")
        print(f"    {json.dumps(doc, indent=6, default=str)}")

    print("\n" + "=" * 80)
    print("HYPOTHESIS")
    print("=" * 80)
    print()
    print("The second element in documents array contains payment metadata.")
    print("This suggests one of these scenarios:")
    print()
    print("1. files_in_temp[1] returned a dict with payment metadata instead of file info")
    print("2. The documents array was corrupted after creation")
    print("3. There was a merge/append operation that went wrong")
    print()
    print("Expected behavior:")
    print("  documents = [")
    print("    {file_name, file_size, original_url, ...},  # Doc 1")
    print("    {file_name, file_size, original_url, ...},  # Doc 2")
    print("  ]")
    print()
    print("Actual behavior:")
    print("  documents = [")
    print("    {file_name, file_size, original_url, ...},  # Doc 1")
    print("    {payment_method, square_transaction_id, ...},  # WRONG!")
    print("  ]")

    await database.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
