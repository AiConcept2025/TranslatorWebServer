#!/usr/bin/env python3
"""
Add contact_email field to Iris Trading company record.

This script adds a top-level contact_email field to the Iris Trading company
by copying the value from contact_person.email.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from bson import ObjectId
from app.database.mongodb import MongoDB


async def add_contact_email(db):
    """Add contact_email field to Iris Trading company."""

    print("=" * 60)
    print("Adding contact_email to Iris Trading company")
    print("=" * 60)

    # Find Iris Trading company
    company = await db.company.find_one({"company_name": "Iris Trading"})

    if not company:
        print("❌ ERROR: Iris Trading company not found in database")
        return False

    print(f"\n✅ Found company: {company['company_name']}")
    print(f"   Company ID: {company['_id']}")

    # Check if contact_email already exists
    if company.get("contact_email"):
        print(f"   contact_email already exists: {company['contact_email']}")
        print("\n✅ No update needed - field already set")
        return True

    # Get email from contact_person
    contact_person = company.get("contact_person", {})
    email = contact_person.get("email")

    if not email:
        print("❌ ERROR: No email found in contact_person.email")
        print(f"   contact_person fields: {list(contact_person.keys())}")
        return False

    print(f"   Email from contact_person: {email}")

    # Update the company record
    print(f"\n📝 Updating company record...")
    result = await db.company.update_one(
        {"_id": company["_id"]},
        {"$set": {"contact_email": email}}
    )

    if result.modified_count > 0:
        print(f"✅ SUCCESS: Added contact_email field")
        print(f"   contact_email: {email}")

        # Verify the update
        updated_company = await db.company.find_one({"_id": company["_id"]})
        print(f"\n✅ Verification: contact_email = {updated_company.get('contact_email')}")
        return True
    else:
        print("⚠️  No changes made (field may already exist)")
        return True


async def main():
    """Main entry point."""
    # Initialize database connection
    mongodb = MongoDB()

    try:
        # Connect to database
        print("Connecting to MongoDB...")
        connected = await mongodb.connect()
        if not connected:
            print("❌ ERROR: Failed to connect to MongoDB")
            sys.exit(1)

        print("✅ Connected to MongoDB\n")

        # Run the update
        success = await add_contact_email(mongodb.db)

        if success:
            print("\n" + "=" * 60)
            print("✅ COMPLETE: Iris Trading company updated successfully")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("❌ FAILED: Could not update company")
            print("=" * 60)
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Disconnect from database
        if mongodb.client:
            await mongodb.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
