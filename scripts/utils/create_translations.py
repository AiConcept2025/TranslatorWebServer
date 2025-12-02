#!/usr/bin/env python3
"""
MongoDB User Translations Collection Setup Script
Creates the 'user_translations' collection with realistic dummy transaction data.
"""

import sys
import random
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure


# MongoDB Configuration
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
MONGODB_DATABASE = "translation"
COLLECTION_NAME = "user_translations"

# User data from users_login collection
USERS = [
    {"user_name": "john_smith", "user_email": "john.smith@example.com"},
    {"user_name": "sarah_jones", "user_email": "sarah.jones@example.com"},
    {"user_name": "mike_wilson", "user_email": "mike.wilson@example.com"},
    {"user_name": "emma_brown", "user_email": "emma.brown@example.com"},
    {"user_name": "david_taylor", "user_email": "david.taylor@example.com"},
    {"user_name": "lisa_anderson", "user_email": "lisa.anderson@example.com"},
    {"user_name": "james_martinez", "user_email": "james.martinez@example.com"},
    {"user_name": "sophia_garcia", "user_email": "sophia.garcia@example.com"}
]

# Document types and formats
DOCUMENT_FORMATS = ["pdf", "docx", "doc", "txt", "xlsx", "pptx"]
DOCUMENT_TYPES = [
    "contract", "report", "presentation", "manual",
    "specification", "proposal", "invoice", "certificate"
]

# Language pairs (realistic combinations)
LANGUAGE_PAIRS = [
    ("English", "Spanish"),
    ("English", "French"),
    ("English", "German"),
    ("English", "Japanese"),
    ("English", "Chinese"),
    ("Spanish", "English"),
    ("French", "English"),
    ("German", "English"),
    ("English", "Portuguese"),
    ("English", "Italian"),
    ("English", "Russian"),
    ("English", "Korean"),
    ("Spanish", "French"),
    ("French", "German")
]

# Unit types with realistic cost ranges
UNIT_CONFIGS = {
    "page": {"min": 15, "max": 250, "cost_range": (2.50, 5.00)},
    "word": {"min": 500, "max": 5000, "cost_range": (0.10, 0.25)},
    "character": {"min": 2000, "max": 20000, "cost_range": (0.02, 0.05)}
}

# Status distribution (mostly completed)
STATUS_DISTRIBUTION = ["completed"] * 12 + ["processing"] * 2 + ["failed"] * 1


def generate_stripe_checkout_session_id() -> str:
    """Generate a realistic Stripe transaction ID."""
    # Stripe transaction IDs are typically 24 characters: sqt_ + 20 random chars
    chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    random_part = ''.join(random.choice(chars) for _ in range(20))
    return f"sqt_{random_part}"


def generate_document_url(doc_type: str, doc_format: str, user_email: str) -> str:
    """Generate a realistic document URL."""
    timestamp = int(datetime.now(timezone.utc).timestamp())
    filename = f"{doc_type}_{timestamp}.{doc_format}"
    # Simulate Google Drive or S3 storage URLs
    if random.random() > 0.5:
        return f"https://drive.google.com/file/d/{random.randint(10000000, 99999999)}/{filename}"
    else:
        return f"https://s3.amazonaws.com/translation-docs/{user_email.split('@')[0]}/{filename}"


def create_translation_transaction(user: Dict[str, str], days_ago: int) -> Dict[str, Any]:
    """
    Create a single realistic translation transaction.

    Args:
        user: User dictionary with user_name and user_email
        days_ago: Number of days ago for the transaction date

    Returns:
        Translation transaction dictionary
    """
    # Select random configuration
    unit_type = random.choice(list(UNIT_CONFIGS.keys()))
    unit_config = UNIT_CONFIGS[unit_type]

    # Generate values
    number_of_units = random.randint(unit_config["min"], unit_config["max"])
    cost_per_unit = round(random.uniform(*unit_config["cost_range"]), 2)
    total_cost = round(number_of_units * cost_per_unit, 2)

    # Select languages
    source_lang, target_lang = random.choice(LANGUAGE_PAIRS)

    # Generate document info
    doc_type = random.choice(DOCUMENT_TYPES)
    doc_format = random.choice(DOCUMENT_FORMATS)
    document_url = generate_document_url(doc_type, doc_format, user["user_email"])

    # Generate date (spread over last 30 days)
    transaction_date = datetime.now(timezone.utc) - timedelta(days=days_ago)

    # Status
    status = random.choice(STATUS_DISTRIBUTION)

    # Create transaction
    transaction = {
        "user_name": user["user_name"],
        "user_email": user["user_email"],
        "document_url": document_url,
        "number_of_units": number_of_units,
        "unit_type": unit_type,
        "cost_per_unit": cost_per_unit,
        "source_language": source_lang,
        "target_language": target_lang,
        "stripe_checkout_session_id": generate_stripe_checkout_session_id(),
        "date": transaction_date,
        "status": status,
        "total_cost": total_cost,
        "created_at": transaction_date,
        "updated_at": transaction_date
    }

    return transaction


def create_dummy_transactions() -> List[Dict[str, Any]]:
    """
    Create 10-15 realistic translation transactions distributed among users.

    Returns:
        List of translation transaction dictionaries
    """
    transactions = []
    num_transactions = random.randint(12, 15)

    # Distribute transactions among users (some users get multiple transactions)
    for i in range(num_transactions):
        # Some users are more active than others
        weights = [3, 2, 2, 1, 2, 1, 1, 2]  # john_smith and mike_wilson are more active
        user = random.choices(USERS, weights=weights, k=1)[0]

        # Spread transactions over last 30 days
        days_ago = random.randint(0, 30)

        transaction = create_translation_transaction(user, days_ago)
        transactions.append(transaction)

    # Sort by date (most recent first)
    transactions.sort(key=lambda x: x["date"], reverse=True)

    return transactions


def create_indexes(collection) -> List[str]:
    """
    Create indexes for the user_translations collection.

    Args:
        collection: MongoDB collection object

    Returns:
        List of created index names
    """
    print("\nCreating indexes...")

    indexes = []

    # Index on user_email for querying user's translations
    email_index = collection.create_index(
        [("user_email", ASCENDING)],
        name="idx_user_email"
    )
    indexes.append(email_index)
    print(f"  ✓ Created index: {email_index}")

    # Index on date for date-range queries
    date_index = collection.create_index(
        [("date", DESCENDING)],
        name="idx_date_desc"
    )
    indexes.append(date_index)
    print(f"  ✓ Created index: {date_index}")

    # Unique index on stripe_checkout_session_id for payment verification
    # Sparse allows multiple null values (before payment), but enforces uniqueness on non-null
    square_index = collection.create_index(
        [("stripe_checkout_session_id", ASCENDING)],
        unique=True,
        sparse=True,  # Allow multiple documents with null stripe_checkout_session_id
        name="idx_stripe_checkout_session_id_unique"
    )
    indexes.append(square_index)
    print(f"  ✓ Created unique index: {square_index}")

    # Compound index on user_email + date for user history queries
    compound_index = collection.create_index(
        [("user_email", ASCENDING), ("date", DESCENDING)],
        name="idx_user_email_date"
    )
    indexes.append(compound_index)
    print(f"  ✓ Created compound index: {compound_index}")

    # Index on status for filtering
    status_index = collection.create_index(
        [("status", ASCENDING)],
        name="idx_status"
    )
    indexes.append(status_index)
    print(f"  ✓ Created index: {status_index}")

    return indexes


def calculate_statistics(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate statistics from transactions.

    Args:
        transactions: List of transaction dictionaries

    Returns:
        Dictionary with statistics
    """
    # Total revenue
    total_revenue = sum(t["total_cost"] for t in transactions)

    # Transactions per user
    user_stats = {}
    for t in transactions:
        email = t["user_email"]
        if email not in user_stats:
            user_stats[email] = {"count": 0, "revenue": 0}
        user_stats[email]["count"] += 1
        user_stats[email]["revenue"] += t["total_cost"]

    # Status breakdown
    status_counts = {}
    for t in transactions:
        status = t["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    # Unit type breakdown
    unit_type_counts = {}
    for t in transactions:
        unit_type = t["unit_type"]
        unit_type_counts[unit_type] = unit_type_counts.get(unit_type, 0) + 1

    # Language pair breakdown
    language_pairs = {}
    for t in transactions:
        pair = f"{t['source_language']} → {t['target_language']}"
        language_pairs[pair] = language_pairs.get(pair, 0) + 1

    return {
        "total_revenue": total_revenue,
        "user_stats": user_stats,
        "status_counts": status_counts,
        "unit_type_counts": unit_type_counts,
        "language_pairs": language_pairs
    }


def display_collection_schema():
    """Display the collection schema."""
    print("\n" + "="*80)
    print("COLLECTION SCHEMA")
    print("="*80)
    print(f"""
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
stripe_checkout_session_id   string      Yes       Yes     Stripe payment transaction ID
date                    datetime    Yes       No      Transaction date
status                  string      Yes       No      "completed", "processing", "failed"
total_cost              decimal     Yes       No      number_of_units × cost_per_unit
created_at              datetime    Yes       No      Record creation timestamp
updated_at              datetime    Yes       No      Last update timestamp
    """)


def display_sample_transactions(transactions: List[Dict[str, Any]]):
    """Display 2-3 sample transactions."""
    print("="*80)
    print("SAMPLE TRANSACTIONS")
    print("="*80)

    samples = transactions[:3]
    for idx, t in enumerate(samples, 1):
        print(f"\nTransaction #{idx}:")
        print(f"  User: {t['user_name']} ({t['user_email']})")
        print(f"  Document: {t['document_url']}")
        print(f"  Units: {t['number_of_units']} {t['unit_type']}(s) @ ${t['cost_per_unit']}/{t['unit_type']}")
        print(f"  Languages: {t['source_language']} → {t['target_language']}")
        print(f"  Stripe ID: {t['stripe_checkout_session_id']}")
        print(f"  Date: {t['date'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Status: {t['status']}")
        print(f"  Total Cost: ${t['total_cost']:.2f}")


def display_statistics(stats: Dict[str, Any], num_transactions: int):
    """Display statistics report."""
    print("\n" + "="*80)
    print("TRANSACTION STATISTICS")
    print("="*80)

    print(f"\nTotal Transactions: {num_transactions}")
    print(f"Total Revenue: ${stats['total_revenue']:.2f}")

    print("\n--- Transactions by User ---")
    for email in sorted(stats['user_stats'].keys()):
        user_data = stats['user_stats'][email]
        print(f"  {email:<35} {user_data['count']:>2} transactions  ${user_data['revenue']:>8.2f}")

    print("\n--- Status Breakdown ---")
    for status, count in sorted(stats['status_counts'].items()):
        percentage = (count / num_transactions) * 100
        print(f"  {status.capitalize():<15} {count:>2} ({percentage:>5.1f}%)")

    print("\n--- Unit Type Breakdown ---")
    for unit_type, count in sorted(stats['unit_type_counts'].items()):
        percentage = (count / num_transactions) * 100
        print(f"  {unit_type.capitalize():<15} {count:>2} ({percentage:>5.1f}%)")

    print("\n--- Top Language Pairs ---")
    sorted_pairs = sorted(stats['language_pairs'].items(), key=lambda x: x[1], reverse=True)
    for pair, count in sorted_pairs[:5]:
        print(f"  {pair:<30} {count:>2}")


def display_indexes(collection):
    """Display created indexes."""
    print("\n" + "="*80)
    print("CREATED INDEXES")
    print("="*80)

    index_info = collection.index_information()
    for idx_name, idx_details in sorted(index_info.items()):
        if idx_name == "_id_":
            continue  # Skip default _id index
        print(f"\nIndex: {idx_name}")
        print(f"  Keys: {idx_details.get('key', [])}")
        print(f"  Unique: {idx_details.get('unique', False)}")


def main():
    """Main execution function."""
    print("="*80)
    print("MONGODB USER TRANSLATIONS COLLECTION SETUP")
    print("="*80)
    print(f"Database: {MONGODB_DATABASE}")
    print(f"Collection: {COLLECTION_NAME}")
    print("="*80)

    try:
        # Connect to MongoDB
        print("\n1. Connecting to MongoDB...")
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)

        # Test connection
        client.admin.command('ping')
        print("  ✓ Successfully connected to MongoDB")

        # Get database and collection
        db = client[MONGODB_DATABASE]
        collection = db[COLLECTION_NAME]

        # Check if collection exists and has data
        existing_count = collection.count_documents({})
        if existing_count > 0:
            print(f"\n⚠ Warning: Collection '{COLLECTION_NAME}' already contains {existing_count} documents")
            response = input("Do you want to drop the existing collection and recreate it? (yes/no): ")
            if response.lower() in ['yes', 'y']:
                collection.drop()
                print("  ✓ Dropped existing collection")
                collection = db[COLLECTION_NAME]  # Recreate collection reference
            else:
                print("  ✗ Aborting: Collection not modified")
                return

        # Create dummy transactions
        print("\n2. Creating dummy translation transactions...")
        transactions = create_dummy_transactions()
        print(f"  ✓ Created {len(transactions)} dummy transactions")

        # Create indexes
        print("\n3. Creating indexes...")
        indexes = create_indexes(collection)
        print(f"  ✓ Created {len(indexes)} indexes")

        # Insert transactions
        print("\n4. Inserting transactions into collection...")
        result = collection.insert_many(transactions)
        inserted_count = len(result.inserted_ids)
        print(f"  ✓ Successfully inserted {inserted_count} transactions")

        # Calculate statistics
        print("\n5. Calculating statistics...")
        stats = calculate_statistics(transactions)
        print("  ✓ Statistics calculated")

        # Display results
        display_collection_schema()
        display_sample_transactions(transactions)
        display_statistics(stats, inserted_count)
        display_indexes(collection)

        # Final summary
        print("\n" + "="*80)
        print("EXECUTION SUMMARY")
        print("="*80)
        print(f"✓ Collection '{COLLECTION_NAME}' created successfully")
        print(f"✓ {inserted_count} transactions inserted")
        print(f"✓ {len(indexes)} indexes created")
        print(f"✓ Total revenue: ${stats['total_revenue']:.2f}")
        print(f"✓ Date range: {transactions[-1]['date'].strftime('%Y-%m-%d')} to {transactions[0]['date'].strftime('%Y-%m-%d')}")
        print(f"✓ Users with transactions: {len(stats['user_stats'])}/{len(USERS)}")
        print("="*80)

        # Close connection
        client.close()
        print("\n✓ MongoDB connection closed")
        print("\nSetup completed successfully!\n")

    except ConnectionFailure as e:
        print(f"\n✗ Error: Failed to connect to MongoDB")
        print(f"  Details: {e}")
        print(f"\n  Please check:")
        print(f"  1. MongoDB is running on localhost:27017")
        print(f"  2. Credentials are correct (user: iris)")
        print(f"  3. Database 'translation' exists and is accessible")
        sys.exit(1)

    except OperationFailure as e:
        print(f"\n✗ Error: MongoDB operation failed")
        print(f"  Details: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\n✗ Error: Unexpected error occurred")
        print(f"  Type: {type(e).__name__}")
        print(f"  Details: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
