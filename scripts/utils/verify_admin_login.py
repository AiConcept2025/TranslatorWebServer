#!/usr/bin/env python3
"""
Verify Admin Login Script
Tests authentication against the iris-admins collection.

Usage:
    python verify_admin_login.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from pymongo import MongoClient
    import bcrypt
    from app.config import settings
except ImportError as e:
    print(f"Error: Missing required package - {e}")
    sys.exit(1)


def verify_admin_login(username: str, password: str) -> bool:
    """
    Verify admin credentials against the database.

    Args:
        username: Username to check
        password: Plain text password to verify

    Returns:
        bool: True if credentials are valid, False otherwise
    """
    try:
        # Connect to MongoDB
        client = MongoClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000
        )
        db = client[settings.mongodb_database]
        collection = db["iris-admins"]

        # Find user by username
        user = collection.find_one({"user_name": username})

        if not user:
            print(f"❌ User '{username}' not found in database")
            return False

        # Get hashed password from database
        stored_hash = user.get("password")

        if not stored_hash:
            print("❌ No password hash found in database")
            return False

        # Verify password
        is_valid = bcrypt.checkpw(
            password.encode('utf-8'),
            stored_hash.encode('utf-8')
        )

        if is_valid:
            print(f"✅ Authentication successful for user '{username}'")
            print(f"   Login date: {user.get('login_date')}")
            print(f"   Created at: {user.get('created_at')}")
        else:
            print(f"❌ Invalid password for user '{username}'")

        client.close()
        return is_valid

    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False


def main():
    """Main execution function."""
    print("=" * 60)
    print("Admin Login Verification")
    print("=" * 60)

    # Test credentials
    USERNAME = "iris-admin"
    PASSWORD = "Sveta87201120!"

    print(f"\nTesting credentials:")
    print(f"  Username: {USERNAME}")
    print(f"  Password: {'*' * len(PASSWORD)}")
    print()

    # Verify login
    success = verify_admin_login(USERNAME, PASSWORD)

    print("\n" + "=" * 60)
    if success:
        print("✅ VERIFICATION PASSED")
        print("The admin user is correctly configured and can authenticate")
    else:
        print("❌ VERIFICATION FAILED")
        print("There is an issue with the credentials or database")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
