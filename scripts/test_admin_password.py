#!/usr/bin/env python3
"""
Test Script: Verify admin password hash in database

This script checks if the stored password hash matches the expected password.
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import bcrypt
    from app.database import database
except ImportError as e:
    print(f"Error: Missing required package - {e}")
    sys.exit(1)


async def test_password():
    """Test password verification for Vladimir's admin account."""
    print("=" * 80)
    print("ADMIN PASSWORD VERIFICATION TEST")
    print("=" * 80)
    print()

    try:
        # Connect to database
        print("Connecting to database...")
        await database.connect()
        print("✓ Connected to database")
        print()

        # Get Vladimir's admin record
        print("Looking up admin record...")
        admin = await database.db["iris-admins"].find_one({
            "user_email": "danishevsky@gmail.com"
        })

        if not admin:
            print("✗ Admin not found!")
            print("  Email searched: danishevsky@gmail.com")
            print()

            # List all admins
            print("Available admins in iris-admins collection:")
            all_admins = await database.db["iris-admins"].find({}).to_list(length=100)
            for a in all_admins:
                print(f"  - {a.get('user_name')} ({a.get('user_email')})")

            return

        print("✓ Found admin record:")
        print(f"  - user_name: {admin.get('user_name')}")
        print(f"  - user_email: {admin.get('user_email')}")
        print(f"  - _id: {admin.get('_id')}")
        print()

        # Check password field
        password_hash = admin.get('password')
        if not password_hash:
            print("✗ No password hash found in record!")
            print(f"  Available fields: {list(admin.keys())}")
            return

        print("✓ Password hash found:")
        print(f"  - Hash (first 50 chars): {password_hash[:50]}...")
        print(f"  - Hash length: {len(password_hash)} characters")
        print()

        # Test password verification
        test_password = "Sveta87201120!"
        print(f"Testing password: '{test_password}'")
        print()

        try:
            # Convert to bytes
            password_bytes = test_password.encode('utf-8')
            hash_bytes = password_hash.encode('utf-8')

            print(f"Password bytes length: {len(password_bytes)}")
            print(f"Hash starts with: {password_hash[:7]}")  # Should be "$2b$12$" for bcrypt
            print()

            # Verify password
            is_valid = bcrypt.checkpw(password_bytes, hash_bytes)

            if is_valid:
                print("✅ PASSWORD VERIFICATION: PASSED")
                print("   The password matches the stored hash!")
            else:
                print("❌ PASSWORD VERIFICATION: FAILED")
                print("   The password does NOT match the stored hash!")
                print()
                print("   This means either:")
                print("   1. The password in the migration script was different")
                print("   2. The hash was corrupted during storage")
                print("   3. There's an encoding issue")

        except Exception as e:
            print(f"✗ Error during password verification: {e}")
            import traceback
            traceback.print_exc()

        print()
        print("=" * 80)

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Disconnect
        await database.disconnect()
        print("Database connection closed")


if __name__ == "__main__":
    asyncio.run(test_password())
