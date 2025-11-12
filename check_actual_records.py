#!/usr/bin/env python3
"""
Check ACTUAL user_transactions records to see field structure.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database.mongodb import database


async def main():
    """Check actual records in user_transactions."""

    print("\n" + "=" * 80)
    print("CHECKING ACTUAL user_transactions RECORDS")
    print("=" * 80 + "\n")

    await database.connect()
    collection = database.user_transactions

    # Get some real records
    records = await collection.find({"user_email": "danishevsky@yahoo.com"}).to_list(length=5)

    print(f"Found {len(records)} records for danishevsky@yahoo.com\n")

    for idx, record in enumerate(records, 1):
        print("=" * 80)
        print(f"RECORD {idx}: {record.get('transaction_id')}")
        print("=" * 80)
        print(f"Status: {record.get('status')}")
        print(f"Number of documents: {len(record.get('documents', []))}")
        print()

        documents = record.get('documents', [])
        for doc_idx, doc in enumerate(documents, 1):
            print(f"  Document {doc_idx}:")
            print(f"    file_name: {doc.get('file_name')}")
            print(f"    original_url: {doc.get('original_url', 'N/A')[:60]}...")

            # CHECK: Does translated_url exist?
            if 'translated_url' in doc:
                print(f"    ✅ translated_url EXISTS = {doc.get('translated_url')}")
            else:
                print(f"    ❌ translated_url DOES NOT EXIST (field missing)")

            # CHECK: Does translated_name exist?
            if 'translated_name' in doc:
                print(f"    ✅ translated_name EXISTS = {doc.get('translated_name')}")
            else:
                print(f"    ❌ translated_name DOES NOT EXIST (field missing)")

            print(f"    status: {doc.get('status')}")
            print()

    # Now check the OLD record you mentioned (the one from your screenshot)
    print("\n" + "=" * 80)
    print("CHECKING THE OLD RECORD FROM YOUR SCREENSHOT")
    print("=" * 80 + "\n")

    old_record = await collection.find_one({"transaction_id": "TXN-512E81D154"})

    if old_record:
        print(f"✅ Found record: TXN-512E81D154")
        print(f"Status: {old_record.get('status')}")
        print(f"\nDocuments:")

        for doc_idx, doc in enumerate(old_record.get('documents', []), 1):
            print(f"\n  Document {doc_idx}: {doc.get('file_name')}")
            print(f"  All fields in this document:")
            for key, value in doc.items():
                print(f"    - {key}: {value}")

            # Specifically check for our fields
            print(f"\n  Field existence check:")
            print(f"    'translated_url' in doc: {'translated_url' in doc}")
            print(f"    'translated_name' in doc: {'translated_name' in doc}")
    else:
        print("❌ Record TXN-512E81D154 not found")

    # Test what happens when we try to update a record WITHOUT the field
    print("\n\n" + "=" * 80)
    print("SIMULATION: What happens when webhook tries to update?")
    print("=" * 80 + "\n")

    if old_record and 'translated_url' not in old_record.get('documents', [{}])[0]:
        print("This record's first document is MISSING translated_url field")
        print("Simulating webhook update...\n")

        # Simulate the webhook filter
        test_filter = {
            "transaction_id": "TXN-512E81D154",
            "documents.0.translated_url": None
        }

        print(f"Filter: {test_filter}")

        # Try to find with this filter
        match_result = await collection.find_one(test_filter)

        if match_result:
            print("✅ MATCHED! MongoDB found the document with this filter")
            print("   This confirms: filter {translated_url: None} DOES match when field doesn't exist")
        else:
            print("❌ NO MATCH! MongoDB did NOT find the document")
            print("   This means: filter {translated_url: None} does NOT match when field doesn't exist")
            print("   **WEBHOOK WILL FAIL** for old records!")

    await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
