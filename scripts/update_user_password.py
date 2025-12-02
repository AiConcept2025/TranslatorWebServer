#!/usr/bin/env python3
"""
UPDATE USER PASSWORD IN GOLDEN SOURCE DATABASE

This script updates the password hash for a user across all user collections
in the Golden Source JSON files.

Usage:
    python scripts/update_user_password.py <email> <new_password>

Example:
    python scripts/update_user_password.py sam.danishevsky@gmail.com password123
    python scripts/update_user_password.py danishevsky@gmail.com Admin123

Collections checked:
    - iris-admins.json (field: password)
    - company_users.json (field: password_hash)
    - users_login.json (field: password)
"""

import sys
import json
import bcrypt
from pathlib import Path
from datetime import datetime

# Golden Source directory
GOLDEN_SOURCE_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "golden_db"

# Collections and their password field names
COLLECTIONS = {
    "iris-admins.json": "password",
    "company_users.json": "password_hash",
    "users_login.json": "password",
}

# Email field names per collection
EMAIL_FIELDS = {
    "iris-admins.json": "user_email",
    "company_users.json": "email",
    "users_login.json": "user_email",
}


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def update_password_in_file(file_path: Path, email: str, password_hash: str,
                            password_field: str, email_field: str) -> bool:
    """
    Update password for user with given email in JSON file.

    Returns True if user was found and updated, False otherwise.
    """
    if not file_path.exists():
        print(f"  ⚠️  File not found: {file_path.name}")
        return False

    with open(file_path, 'r') as f:
        data = json.load(f)

    updated = False
    for record in data:
        record_email = record.get(email_field, "")
        if record_email.lower() == email.lower():
            old_hash = record.get(password_field, "N/A")
            record[password_field] = password_hash
            record["updated_at"] = {"$date": datetime.utcnow().isoformat() + "Z"}
            updated = True
            print(f"  ✅ Updated in {file_path.name}")
            print(f"     Email: {record_email}")
            print(f"     Old hash: {old_hash[:30]}...")
            print(f"     New hash: {password_hash[:30]}...")

    if updated:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    return updated


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/update_user_password.py <email> <new_password>")
        print()
        print("Example:")
        print("  python scripts/update_user_password.py sam.danishevsky@gmail.com password123")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]

    print("=" * 70)
    print("UPDATE USER PASSWORD IN GOLDEN SOURCE")
    print("=" * 70)
    print(f"Email: {email}")
    print(f"New password: {password}")
    print(f"Golden Source: {GOLDEN_SOURCE_DIR}")
    print("=" * 70)

    # Hash the password
    print("\n🔐 Hashing password...")
    password_hash = hash_password(password)
    print(f"   Hash: {password_hash[:40]}...")

    # Update in all collections
    print("\n📁 Updating collections...")
    found_in_any = False

    for filename, password_field in COLLECTIONS.items():
        file_path = GOLDEN_SOURCE_DIR / filename
        email_field = EMAIL_FIELDS[filename]

        if update_password_in_file(file_path, email, password_hash, password_field, email_field):
            found_in_any = True

    print("\n" + "=" * 70)
    if found_in_any:
        print("✅ PASSWORD UPDATED SUCCESSFULLY")
        print()
        print("Next steps:")
        print("  1. Run: python scripts/restore_test_db.py")
        print("     (to reload Golden Source into test database)")
        print()
        print("  2. Run tests to verify:")
        print("     pytest tests/integration/ -v")
    else:
        print(f"❌ USER NOT FOUND: {email}")
        print()
        print("Available users:")
        for filename, email_field in EMAIL_FIELDS.items():
            file_path = GOLDEN_SOURCE_DIR / filename
            if file_path.exists():
                with open(file_path, 'r') as f:
                    data = json.load(f)
                print(f"\n  {filename}:")
                for record in data:
                    print(f"    - {record.get(email_field, 'N/A')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
