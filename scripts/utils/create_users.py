#!/usr/bin/env python3
"""
MongoDB User Collection Setup Script
Creates the 'users_login' collection with dummy user data.
"""

import sys
from datetime import datetime, timezone
from typing import List, Dict, Any
import bcrypt
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError, OperationFailure


# MongoDB Configuration (from app/config.py)
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
MONGODB_DATABASE = "translation"
COLLECTION_NAME = "users_login"

# Password settings
BCRYPT_SALT_ROUNDS = 12
DEFAULT_PASSWORD = "Password123!"


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with 12 salt rounds.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password as a string
    """
    salt = bcrypt.gensalt(rounds=BCRYPT_SALT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def create_dummy_users() -> List[Dict[str, Any]]:
    """
    Create dummy user data with hashed passwords.

    Returns:
        List of user dictionaries with hashed passwords
    """
    now = datetime.now(timezone.utc)
    hashed_password = hash_password(DEFAULT_PASSWORD)

    users = [
        {
            "user_name": "john_smith",
            "user_email": "john.smith@example.com",
            "password": hashed_password,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        },
        {
            "user_name": "sarah_jones",
            "user_email": "sarah.jones@example.com",
            "password": hashed_password,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        },
        {
            "user_name": "mike_wilson",
            "user_email": "mike.wilson@example.com",
            "password": hashed_password,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        },
        {
            "user_name": "emma_brown",
            "user_email": "emma.brown@example.com",
            "password": hashed_password,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        },
        {
            "user_name": "david_taylor",
            "user_email": "david.taylor@example.com",
            "password": hashed_password,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        },
        {
            "user_name": "lisa_anderson",
            "user_email": "lisa.anderson@example.com",
            "password": hashed_password,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        },
        {
            "user_name": "james_martinez",
            "user_email": "james.martinez@example.com",
            "password": hashed_password,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        },
        {
            "user_name": "sophia_garcia",
            "user_email": "sophia.garcia@example.com",
            "password": hashed_password,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        }
    ]

    return users


def create_indexes(collection):
    """
    Create unique indexes on user_name and user_email fields.

    Args:
        collection: MongoDB collection object

    Returns:
        List of created index names
    """
    print("\nCreating indexes...")

    indexes = []

    # Create unique index on user_email
    email_index = collection.create_index(
        [("user_email", ASCENDING)],
        unique=True,
        name="idx_user_email_unique"
    )
    indexes.append(email_index)
    print(f"  ✓ Created unique index: {email_index}")

    # Create unique index on user_name
    username_index = collection.create_index(
        [("user_name", ASCENDING)],
        unique=True,
        name="idx_user_name_unique"
    )
    indexes.append(username_index)
    print(f"  ✓ Created unique index: {username_index}")

    # Create index on created_at for sorting
    created_index = collection.create_index(
        [("created_at", ASCENDING)],
        name="idx_created_at"
    )
    indexes.append(created_index)
    print(f"  ✓ Created index: {created_index}")

    return indexes


def verify_password_authentication(users: List[Dict[str, Any]]) -> bool:
    """
    Verify that all stored passwords can be authenticated.

    Args:
        users: List of user dictionaries with hashed passwords

    Returns:
        True if all passwords can be authenticated, False otherwise
    """
    print("\n" + "="*60)
    print("PASSWORD VERIFICATION")
    print("="*60)

    all_valid = True
    for user in users:
        username = user['user_name']
        hashed_pw = user['password']

        # Verify the password
        is_valid = verify_password(DEFAULT_PASSWORD, hashed_pw)
        status = "✓ PASS" if is_valid else "✗ FAIL"
        print(f"  {status} - {username}")

        if not is_valid:
            all_valid = False

    return all_valid


def main():
    """Main execution function."""
    print("="*60)
    print("MONGODB USER COLLECTION SETUP")
    print("="*60)
    print(f"Database: {MONGODB_DATABASE}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Default Password: {DEFAULT_PASSWORD}")
    print(f"BCrypt Salt Rounds: {BCRYPT_SALT_ROUNDS}")
    print("="*60)

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

        # Create dummy users
        print("\n2. Creating dummy user data...")
        users = create_dummy_users()
        print(f"  ✓ Created {len(users)} dummy users")

        # Create indexes
        print("\n3. Creating indexes...")
        indexes = create_indexes(collection)
        print(f"  ✓ Created {len(indexes)} indexes")

        # Insert users
        print("\n4. Inserting users into collection...")
        try:
            result = collection.insert_many(users)
            inserted_count = len(result.inserted_ids)
            print(f"  ✓ Successfully inserted {inserted_count} users")
        except DuplicateKeyError as e:
            print(f"  ✗ Error: Duplicate key detected - {e}")
            sys.exit(1)

        # Verify password authentication
        print("\n5. Verifying password authentication...")
        if verify_password_authentication(users):
            print("  ✓ All passwords verified successfully")
        else:
            print("  ✗ Some passwords failed verification")
            sys.exit(1)

        # Display collection schema
        print("\n" + "="*60)
        print("COLLECTION SCHEMA")
        print("="*60)
        print("""
Field Name       Type        Required  Unique  Description
---------------- ----------- --------- ------- --------------------------
user_name        string      Yes       Yes     Username for login
user_email       string      Yes       Yes     User's email address
password         string      Yes       No      BCrypt hashed password
created_at       datetime    Yes       No      Account creation timestamp
updated_at       datetime    Yes       No      Last update timestamp
last_login       datetime    No        No      Last login timestamp
        """)

        # Display created users
        print("="*60)
        print("CREATED USERS")
        print("="*60)
        print(f"\n{'#':<4} {'Username':<20} {'Email':<30}")
        print("-" * 54)
        for idx, user in enumerate(users, 1):
            print(f"{idx:<4} {user['user_name']:<20} {user['user_email']:<30}")

        # Display indexes
        print("\n" + "="*60)
        print("CREATED INDEXES")
        print("="*60)
        index_info = collection.index_information()
        for idx_name, idx_details in index_info.items():
            print(f"\nIndex: {idx_name}")
            print(f"  Keys: {idx_details.get('key', [])}")
            print(f"  Unique: {idx_details.get('unique', False)}")

        # Final summary
        print("\n" + "="*60)
        print("EXECUTION SUMMARY")
        print("="*60)
        print(f"✓ Collection '{COLLECTION_NAME}' created successfully")
        print(f"✓ {inserted_count} users inserted")
        print(f"✓ {len(indexes)} indexes created")
        print(f"✓ All passwords hashed with BCrypt (12 rounds)")
        print(f"✓ All passwords verified for authentication")
        print(f"✓ Unique constraints applied to user_name and user_email")
        print("="*60)

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
        sys.exit(1)


if __name__ == "__main__":
    main()
