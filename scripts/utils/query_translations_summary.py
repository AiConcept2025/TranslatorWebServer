#!/usr/bin/env python3
"""
Generate a comprehensive summary report of the user_translations collection
"""

from pymongo import MongoClient
from datetime import datetime


# MongoDB Configuration
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
MONGODB_DATABASE = "translation"
COLLECTION_NAME = "user_translations"


def main():
    """Generate comprehensive summary report."""
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DATABASE]
    collection = db[COLLECTION_NAME]

    print("\n" + "="*80)
    print("USER TRANSLATIONS COLLECTION - COMPREHENSIVE SUMMARY")
    print("="*80)

    # 1. Collection Information
    total_count = collection.count_documents({})
    print(f"\n{'Collection Name:':<30} {COLLECTION_NAME}")
    print(f"{'Total Documents:':<30} {total_count}")

    # 2. Collection Schema
    print("\n" + "="*80)
    print("COLLECTION SCHEMA")
    print("="*80)
    print("""
Field Name              Type        Required  Unique  Description
----------------------- ----------- --------- ------- ---------------------------
user_name               string      Yes       No      Username from users_login
user_email              string      Yes       No      Email from users_login
document_url            string      Yes       No      URL/path to document
number_of_units         integer     Yes       No      Count of units
unit_type               string      Yes       No      "page", "word", "character"
cost_per_unit           decimal     Yes       No      Price per unit in dollars
source_language         string      Yes       No      Source language
target_language         string      Yes       No      Target language
square_transaction_id   string      Yes       Yes     Square payment transaction ID
date                    datetime    Yes       No      Transaction date
status                  string      Yes       No      "completed", "processing", "failed"
total_cost              decimal     Yes       No      number_of_units × cost_per_unit
created_at              datetime    Yes       No      Record creation timestamp
updated_at              datetime    Yes       No      Last update timestamp
    """)

    # 3. Indexes
    print("="*80)
    print("INDEXES CREATED")
    print("="*80)

    index_info = collection.index_information()
    for idx_name, idx_details in sorted(index_info.items()):
        if idx_name == "_id_":
            continue
        print(f"\n{idx_name}:")
        print(f"  Keys: {idx_details.get('key', [])}")
        print(f"  Unique: {idx_details.get('unique', False)}")
        print(f"  Purpose: ", end="")
        if "email" in idx_name and "date" in idx_name:
            print("Query user's translation history efficiently")
        elif "email" in idx_name:
            print("Query translations by user")
        elif "date" in idx_name:
            print("Query translations by date range")
        elif "square" in idx_name:
            print("Verify payment transactions (unique constraint)")
        elif "status" in idx_name:
            print("Filter by transaction status")

    # 4. User Distribution
    print("\n" + "="*80)
    print("BREAKDOWN BY USER")
    print("="*80)

    user_pipeline = [
        {
            "$group": {
                "_id": {
                    "name": "$user_name",
                    "email": "$user_email"
                },
                "transaction_count": {"$sum": 1},
                "total_spent": {"$sum": "$total_cost"},
                "avg_transaction": {"$avg": "$total_cost"}
            }
        },
        {"$sort": {"transaction_count": -1}}
    ]

    user_stats = list(collection.aggregate(user_pipeline))
    print(f"\n{'User':<25} {'Email':<30} {'Transactions':<15} {'Total Spent':<15} {'Avg/Transaction'}")
    print("-" * 95)
    for user in user_stats:
        name = user['_id']['name']
        email = user['_id']['email']
        count = user['transaction_count']
        total = user['total_spent']
        avg = user['avg_transaction']
        print(f"{name:<25} {email:<30} {count:<15} ${total:<14.2f} ${avg:.2f}")

    # Users with no transactions
    all_users = [
        "john_smith", "sarah_jones", "mike_wilson", "emma_brown",
        "david_taylor", "lisa_anderson", "james_martinez", "sophia_garcia"
    ]
    users_with_transactions = [u['_id']['name'] for u in user_stats]
    users_without = [u for u in all_users if u not in users_with_transactions]

    if users_without:
        print(f"\nUsers without transactions: {', '.join(users_without)}")

    # 5. Total Revenue
    revenue_pipeline = [
        {
            "$group": {
                "_id": None,
                "total_revenue": {"$sum": "$total_cost"},
                "avg_transaction": {"$avg": "$total_cost"},
                "min_transaction": {"$min": "$total_cost"},
                "max_transaction": {"$max": "$total_cost"}
            }
        }
    ]

    revenue_stats = list(collection.aggregate(revenue_pipeline))[0]

    print("\n" + "="*80)
    print("REVENUE STATISTICS")
    print("="*80)
    print(f"\n{'Total Revenue:':<30} ${revenue_stats['total_revenue']:.2f}")
    print(f"{'Average Transaction:':<30} ${revenue_stats['avg_transaction']:.2f}")
    print(f"{'Minimum Transaction:':<30} ${revenue_stats['min_transaction']:.2f}")
    print(f"{'Maximum Transaction:':<30} ${revenue_stats['max_transaction']:.2f}")

    # 6. Status Breakdown
    print("\n" + "="*80)
    print("STATUS BREAKDOWN")
    print("="*80)

    status_pipeline = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "revenue": {"$sum": "$total_cost"}
            }
        }
    ]

    status_stats = list(collection.aggregate(status_pipeline))
    print(f"\n{'Status':<15} {'Count':<10} {'Percentage':<15} {'Revenue'}")
    print("-" * 55)
    for status in sorted(status_stats, key=lambda x: x['count'], reverse=True):
        count = status['count']
        percentage = (count / total_count) * 100
        revenue = status['revenue']
        print(f"{status['_id'].capitalize():<15} {count:<10} {percentage:<14.1f}% ${revenue:.2f}")

    # 7. Unit Type Breakdown
    print("\n" + "="*80)
    print("UNIT TYPE BREAKDOWN")
    print("="*80)

    unit_pipeline = [
        {
            "$group": {
                "_id": "$unit_type",
                "count": {"$sum": 1},
                "total_units": {"$sum": "$number_of_units"},
                "avg_cost_per_unit": {"$avg": "$cost_per_unit"},
                "revenue": {"$sum": "$total_cost"}
            }
        }
    ]

    unit_stats = list(collection.aggregate(unit_pipeline))
    print(f"\n{'Unit Type':<15} {'Count':<10} {'Total Units':<15} {'Avg $/Unit':<15} {'Revenue'}")
    print("-" * 70)
    for unit in sorted(unit_stats, key=lambda x: x['count'], reverse=True):
        unit_type = unit['_id'].capitalize()
        count = unit['count']
        total_units = unit['total_units']
        avg_cost = unit['avg_cost_per_unit']
        revenue = unit['revenue']
        print(f"{unit_type:<15} {count:<10} {total_units:<15,} ${avg_cost:<14.2f} ${revenue:.2f}")

    # 8. Language Pairs
    print("\n" + "="*80)
    print("LANGUAGE PAIRS")
    print("="*80)

    lang_pipeline = [
        {
            "$group": {
                "_id": {
                    "source": "$source_language",
                    "target": "$target_language"
                },
                "count": {"$sum": 1},
                "revenue": {"$sum": "$total_cost"}
            }
        },
        {"$sort": {"count": -1}}
    ]

    lang_stats = list(collection.aggregate(lang_pipeline))
    print(f"\n{'Language Pair':<30} {'Count':<10} {'Revenue'}")
    print("-" * 50)
    for lang in lang_stats[:10]:  # Top 10
        pair = f"{lang['_id']['source']} → {lang['_id']['target']}"
        count = lang['count']
        revenue = lang['revenue']
        print(f"{pair:<30} {count:<10} ${revenue:.2f}")

    # 9. Date Range
    print("\n" + "="*80)
    print("DATE RANGE")
    print("="*80)

    earliest = collection.find_one(sort=[("date", 1)])
    latest = collection.find_one(sort=[("date", -1)])

    print(f"\n{'Earliest Transaction:':<30} {earliest['date'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'Latest Transaction:':<30} {latest['date'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'Date Span:':<30} {(latest['date'] - earliest['date']).days + 1} days")

    # 10. Sample Transactions
    print("\n" + "="*80)
    print("SAMPLE TRANSACTIONS (3 Examples)")
    print("="*80)

    samples = list(collection.find().sort("date", -1).limit(3))
    for idx, t in enumerate(samples, 1):
        print(f"\nSample #{idx}:")
        print(f"  User: {t['user_name']} ({t['user_email']})")
        print(f"  Document: {t['document_url'][:70]}...")
        print(f"  Units: {t['number_of_units']} {t['unit_type']}(s) @ ${t['cost_per_unit']}/{t['unit_type']}")
        print(f"  Languages: {t['source_language']} → {t['target_language']}")
        print(f"  Square ID: {t['square_transaction_id']}")
        print(f"  Date: {t['date'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Status: {t['status']}")
        print(f"  Total Cost: ${t['total_cost']:.2f}")

    # Final Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"""
✓ Collection: {COLLECTION_NAME}
✓ Total Transactions: {total_count}
✓ Total Revenue: ${revenue_stats['total_revenue']:.2f}
✓ Users with Transactions: {len(user_stats)}/{len(all_users)}
✓ Date Range: {earliest['date'].strftime('%Y-%m-%d')} to {latest['date'].strftime('%Y-%m-%d')} ({(latest['date'] - earliest['date']).days + 1} days)
✓ Indexes Created: {len([k for k in index_info.keys() if k != '_id_'])}
✓ Status Distribution: {len(status_stats)} statuses (completed, processing, failed)
✓ Unit Types: {len(unit_stats)} types (page, word, character)
✓ Unique Language Pairs: {len(lang_stats)}
✓ Average Transaction Value: ${revenue_stats['avg_transaction']:.2f}
    """)

    print("="*80)

    client.close()
    print("\nReport generation complete!\n")


if __name__ == "__main__":
    main()
