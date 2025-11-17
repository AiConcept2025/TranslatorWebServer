#!/usr/bin/env python3
"""
Test MongoDB behavior: field doesn't exist vs field is None/null
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.database.mongodb import database


async def main():
    """Test MongoDB filter behavior with missing vs None fields."""

    print("\n" + "=" * 80)
    print("MONGODB FIELD BEHAVIOR TEST")
    print("=" * 80 + "\n")

    await database.connect()
    collection = database.user_transactions

    # Clean up test data
    await collection.delete_many({"transaction_id": {"$regex": "^TEST-FIELD-"}})

    # Create 3 test documents
    print("Creating 3 test documents:\n")

    # Document 1: Field DOES NOT EXIST
    doc1 = {
        "transaction_id": "TEST-FIELD-001",
        "user_email": "test@example.com",
        "square_transaction_id": "TEST-SQ-001",  # Required unique field
        "documents": [{
            "file_name": "doc1.pdf",
            "original_url": "https://example.com/doc1"
            # NO translated_url field at all
        }]
    }
    await collection.insert_one(doc1)
    print("✅ Document 1: translated_url field DOES NOT EXIST")

    # Document 2: Field EXISTS but is None
    doc2 = {
        "transaction_id": "TEST-FIELD-002",
        "user_email": "test@example.com",
        "square_transaction_id": "TEST-SQ-002",  # Required unique field
        "documents": [{
            "file_name": "doc2.pdf",
            "original_url": "https://example.com/doc2",
            "translated_url": None  # Explicitly set to None
        }]
    }
    await collection.insert_one(doc2)
    print("✅ Document 2: translated_url = None (explicitly)")

    # Document 3: Field EXISTS with a value
    doc3 = {
        "transaction_id": "TEST-FIELD-003",
        "user_email": "test@example.com",
        "square_transaction_id": "TEST-SQ-003",  # Required unique field
        "documents": [{
            "file_name": "doc3.pdf",
            "original_url": "https://example.com/doc3",
            "translated_url": "https://example.com/doc3_translated"  # Has value
        }]
    }
    await collection.insert_one(doc3)
    print("✅ Document 3: translated_url = 'https://...' (has value)\n")

    print("=" * 80)
    print("FILTER TEST RESULTS")
    print("=" * 80 + "\n")

    # Test 1: Filter by translated_url = None
    print("TEST 1: Filter {\"documents.0.translated_url\": None}")
    print("-" * 80)
    result1 = await collection.find({"documents.0.translated_url": None}).to_list(length=10)
    print(f"Matches: {len(result1)} documents")
    for doc in result1:
        print(f"  - {doc['transaction_id']}: translated_url = {doc['documents'][0].get('translated_url', 'FIELD DOES NOT EXIST')}")
    print()

    # Test 2: Filter by field exists = False
    print("TEST 2: Filter {\"documents.0.translated_url\": {\"$exists\": False}}")
    print("-" * 80)
    result2 = await collection.find({"documents.0.translated_url": {"$exists": False}}).to_list(length=10)
    print(f"Matches: {len(result2)} documents")
    for doc in result2:
        print(f"  - {doc['transaction_id']}: translated_url = {doc['documents'][0].get('translated_url', 'FIELD DOES NOT EXIST')}")
    print()

    # Test 3: Filter by field exists = True
    print("TEST 3: Filter {\"documents.0.translated_url\": {\"$exists\": True}}")
    print("-" * 80)
    result3 = await collection.find({"documents.0.translated_url": {"$exists": True}}).to_list(length=10)
    print(f"Matches: {len(result3)} documents")
    for doc in result3:
        print(f"  - {doc['transaction_id']}: translated_url = {doc['documents'][0].get('translated_url', 'FIELD DOES NOT EXIST')}")
    print()

    # Test 4: Filter by $or (None OR not exists)
    print("TEST 4: Filter {\"$or\": [{\"documents.0.translated_url\": None}, {\"documents.0.translated_url\": {\"$exists\": False}}]}")
    print("-" * 80)
    result4 = await collection.find({
        "$or": [
            {"documents.0.translated_url": None},
            {"documents.0.translated_url": {"$exists": False}}
        ]
    }).to_list(length=10)
    print(f"Matches: {len(result4)} documents")
    for doc in result4:
        print(f"  - {doc['transaction_id']}: translated_url = {doc['documents'][0].get('translated_url', 'FIELD DOES NOT EXIST')}")
    print()

    # Test 5: Try to UPDATE with translated_url = None filter
    print("=" * 80)
    print("UPDATE TEST: What happens when we try to update?")
    print("=" * 80 + "\n")

    print("TEST 5A: Update Document 1 (field doesn't exist) with filter {translated_url: None}")
    print("-" * 80)
    update_result1 = await collection.update_one(
        {
            "transaction_id": "TEST-FIELD-001",
            "documents.0.translated_url": None
        },
        {
            "$set": {
                "documents.0.translated_url": "https://updated1.com",
                "documents.0.translated_name": "doc1_translated.pdf"
            }
        }
    )
    print(f"Matched: {update_result1.matched_count} | Modified: {update_result1.modified_count}")
    doc1_after = await collection.find_one({"transaction_id": "TEST-FIELD-001"})
    print(f"Result: translated_url = {doc1_after['documents'][0].get('translated_url', 'STILL DOES NOT EXIST')}\n")

    print("TEST 5B: Update Document 2 (field = None) with filter {translated_url: None}")
    print("-" * 80)
    update_result2 = await collection.update_one(
        {
            "transaction_id": "TEST-FIELD-002",
            "documents.0.translated_url": None
        },
        {
            "$set": {
                "documents.0.translated_url": "https://updated2.com",
                "documents.0.translated_name": "doc2_translated.pdf"
            }
        }
    )
    print(f"Matched: {update_result2.matched_count} | Modified: {update_result2.modified_count}")
    doc2_after = await collection.find_one({"transaction_id": "TEST-FIELD-002"})
    print(f"Result: translated_url = {doc2_after['documents'][0].get('translated_url')}\n")

    print("TEST 5C: Update Document 1 with $or filter (None OR not exists)")
    print("-" * 80)
    update_result3 = await collection.update_one(
        {
            "transaction_id": "TEST-FIELD-001",
            "$or": [
                {"documents.0.translated_url": None},
                {"documents.0.translated_url": {"$exists": False}}
            ]
        },
        {
            "$set": {
                "documents.0.translated_url": "https://updated_with_or.com",
                "documents.0.translated_name": "doc1_translated.pdf"
            }
        }
    )
    print(f"Matched: {update_result3.matched_count} | Modified: {update_result3.modified_count}")
    doc1_final = await collection.find_one({"transaction_id": "TEST-FIELD-001"})
    print(f"Result: translated_url = {doc1_final['documents'][0].get('translated_url')}\n")

    # Cleanup
    print("=" * 80)
    print("CLEANUP")
    print("=" * 80)
    await collection.delete_many({"transaction_id": {"$regex": "^TEST-FIELD-"}})
    print("✅ Test documents cleaned up\n")

    await database.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
