#!/usr/bin/env python3
"""
Verify user_translations collection data
"""

from pymongo import MongoClient
import json
from datetime import datetime


# MongoDB Configuration
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
MONGODB_DATABASE = "translation"
COLLECTION_NAME = "user_translations"


def main():
    """Query and display sample data from user_translations."""
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DATABASE]
    collection = db[COLLECTION_NAME]

    print("\n" + "="*80)
    print("USER TRANSLATIONS COLLECTION VERIFICATION")
    print("="*80)

    # Count documents
    total_count = collection.count_documents({})
    print(f"\nTotal documents: {total_count}")

    # Get all transactions
    print("\n" + "="*80)
    print("ALL TRANSACTIONS")
    print("="*80)

    transactions = list(collection.find().sort("date", -1))

    for idx, t in enumerate(transactions, 1):
        print(f"\n--- Transaction {idx} ---")
        print(f"ID: {t['_id']}")
        print(f"User: {t['user_name']} ({t['user_email']})")
        print(f"Document: {t['document_url'][:80]}...")
        print(f"Units: {t['number_of_units']} {t['unit_type']}(s) @ ${t['cost_per_unit']:.2f}/{t['unit_type']}")
        print(f"Languages: {t['source_language']} → {t['target_language']}")
        print(f"Stripe Transaction ID: {t['stripe_checkout_session_id']}")
        print(f"Date: {t['date'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Status: {t['status']}")
        print(f"Total Cost: ${t['total_cost']:.2f}")

    # Query by user
    print("\n" + "="*80)
    print("TRANSACTIONS BY JOHN SMITH")
    print("="*80)

    john_transactions = list(collection.find({"user_email": "john.smith@example.com"}).sort("date", -1))
    print(f"\nTotal: {len(john_transactions)} transactions")
    for t in john_transactions:
        print(f"  {t['date'].strftime('%Y-%m-%d')} | {t['source_language']} → {t['target_language']} | ${t['total_cost']:.2f} | {t['status']}")

    # Status breakdown
    print("\n" + "="*80)
    print("STATUS BREAKDOWN")
    print("="*80)

    statuses = collection.aggregate([
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "total_revenue": {"$sum": "$total_cost"}
        }}
    ])

    for status in statuses:
        print(f"  {status['_id'].capitalize()}: {status['count']} transactions, ${status['total_revenue']:.2f}")

    # Language pairs
    print("\n" + "="*80)
    print("LANGUAGE PAIRS")
    print("="*80)

    pairs = collection.aggregate([
        {"$group": {
            "_id": {
                "source": "$source_language",
                "target": "$target_language"
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ])

    for pair in pairs:
        print(f"  {pair['_id']['source']} → {pair['_id']['target']}: {pair['count']} transactions")

    client.close()
    print("\n" + "="*80)
    print("Verification complete!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
