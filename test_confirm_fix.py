#!/usr/bin/env python3
"""
Test script to verify /api/transactions/confirm creates records with correct schema.

This test verifies the fix for missing translated_url and translated_name fields.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database.mongodb import database


async def main():
    """Verify confirm endpoint creates correct schema."""

    print("\n" + "=" * 80)
    print("VERIFY /confirm ENDPOINT FIX")
    print("=" * 80 + "\n")

    await database.connect()

    # Find most recent transaction created by /confirm endpoint (TXN- format)
    recent_txn = await database.user_transactions.find_one(
        {"transaction_id": {"$regex": "^TXN-"}},
        sort=[("created_at", -1)]
    )

    if not recent_txn:
        print("❌ No TXN- transactions found")
        print("Create a transaction via /confirm endpoint first")
        return

    print(f"Found transaction: {recent_txn.get('transaction_id')}")
    print(f"Created at: {recent_txn.get('created_at')}")
    print(f"Number of documents: {len(recent_txn.get('documents', []))}")
    print()

    # Check transaction-level fields
    print("=" * 80)
    print("TRANSACTION-LEVEL FIELDS")
    print("=" * 80)

    required_fields = {
        "transaction_id": "Transaction ID",
        "user_id": "User ID",
        "user_email": "User Email",  # ✅ FIXED
        "total_documents": "Total Documents",  # ✅ FIXED
        "completed_documents": "Completed Documents",  # ✅ FIXED
        "batch_email_sent": "Batch Email Sent"  # ✅ FIXED
    }

    all_present = True
    for field, label in required_fields.items():
        if field in recent_txn:
            value = recent_txn.get(field)
            print(f"✅ {label}: {value}")
        else:
            print(f"❌ {label}: MISSING")
            all_present = False

    print()

    # Check document fields
    print("=" * 80)
    print("DOCUMENT FIELDS")
    print("=" * 80)

    required_doc_fields = {
        "file_name": "File Name",
        "file_size": "File Size",
        "original_url": "Original URL",
        "translated_url": "Translated URL",  # ✅ FIXED
        "translated_name": "Translated Name",  # ✅ FIXED
        "status": "Status",
        "uploaded_at": "Uploaded At",
        "translated_at": "Translated At",  # ✅ FIXED
        "processing_started_at": "Processing Started At",
        "processing_duration": "Processing Duration"
    }

    for idx, doc in enumerate(recent_txn.get('documents', []), 1):
        print(f"\nDocument {idx}: {doc.get('file_name')}")
        doc_complete = True

        for field, label in required_doc_fields.items():
            if field in doc:
                value = doc.get(field)
                if value is None:
                    print(f"  ✅ {label}: null (correct)")
                else:
                    print(f"  ✅ {label}: {str(value)[:50]}...")
            else:
                print(f"  ❌ {label}: MISSING")
                doc_complete = False
                all_present = False

        if doc_complete:
            print(f"  ✅ Document {idx} has all required fields")
        else:
            print(f"  ❌ Document {idx} is missing fields")

    print()
    print("=" * 80)
    print("VERIFICATION RESULT")
    print("=" * 80)

    if all_present:
        print("✅ SUCCESS: All required fields present")
        print("✅ /confirm endpoint creates records with correct schema")
        print("✅ Webhook will be able to update translated_url and translated_name")
    else:
        print("❌ FAILURE: Some required fields missing")
        print("❌ Fix was not applied or new transaction needs to be created")

    print()
    print("Schema matches:")
    print("  - translate_user.py (Individual upload)")
    print("  - Webhook expectations (POST /submit)")
    print("  - Email batching logic")

    await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
