#!/usr/bin/env python3
"""
Test script to verify user authentication against the users_login collection.
"""

import bcrypt
from pymongo import MongoClient
from typing import Optional, Dict, Any


# MongoDB Configuration
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
MONGODB_DATABASE = "translation"
COLLECTION_NAME = "users_login"


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


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user by username and password.

    Args:
        username: Username to authenticate
        password: Password to verify

    Returns:
        User document if authentication succeeds, None otherwise
    """
    try:
        # Connect to MongoDB
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[MONGODB_DATABASE]
        collection = db[COLLECTION_NAME]

        # Find user by username
        user = collection.find_one({"user_name": username})

        if not user:
            print(f"✗ User '{username}' not found")
            client.close()
            return None

        # Verify password
        if verify_password(password, user['password']):
            print(f"✓ Authentication successful for user '{username}'")
            # Remove password from returned user object
            user.pop('password', None)
            client.close()
            return user
        else:
            print(f"✗ Invalid password for user '{username}'")
            client.close()
            return None

    except Exception as e:
        print(f"✗ Authentication error: {e}")
        return None


def main():
    """Main test function."""
    print("="*60)
    print("USER AUTHENTICATION TEST")
    print("="*60)
    print()

    # Test cases
    test_cases = [
        ("john_smith", "Password123!", True),
        ("sarah_jones", "Password123!", True),
        ("john_smith", "WrongPassword", False),
        ("nonexistent_user", "Password123!", False),
    ]

    passed = 0
    failed = 0

    for username, password, should_succeed in test_cases:
        print(f"\nTest: Authenticating '{username}' with password '{password}'")
        print(f"Expected: {'SUCCESS' if should_succeed else 'FAILURE'}")
        print("-" * 60)

        result = authenticate_user(username, password)

        if should_succeed and result:
            print(f"✓ TEST PASSED")
            passed += 1
        elif not should_succeed and not result:
            print(f"✓ TEST PASSED (Expected failure)")
            passed += 1
        else:
            print(f"✗ TEST FAILED")
            failed += 1

        if result:
            print(f"\nUser Details:")
            print(f"  Email: {result.get('user_email')}")
            print(f"  Created: {result.get('created_at')}")
            print(f"  Last Login: {result.get('last_login', 'Never')}")

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total Tests: {passed + failed}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("="*60)


if __name__ == "__main__":
    main()
