#!/usr/bin/env python3
"""Drop all MongoDB collections except the 6 core ones."""

from pymongo import MongoClient

MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
KEEP_COLLECTIONS = {
    "company",
    "company_users",
    "subscriptions",
    "invoices",
    "payments",
    "translation_transactions"
}

def cleanup():
    client = MongoClient(MONGODB_URI)
    db = client.translation

    existing = set(db.list_collection_names())
    to_drop = existing - KEEP_COLLECTIONS

    print(f"\nFound {len(existing)} collections")
    print(f"Keeping: {', '.join(sorted(KEEP_COLLECTIONS))}")

    if to_drop:
        print(f"\nDropping {len(to_drop)} collections:")
        for name in sorted(to_drop):
            db[name].drop()
            print(f"  ✓ Dropped {name}")
    else:
        print("\n✓ No collections to drop")

    remaining = set(db.list_collection_names())
    print(f"\nFinal count: {len(remaining)} collections")

    client.close()

if __name__ == "__main__":
    cleanup()
