#!/usr/bin/env python3
"""
Translation Transactions Collection Schema Definition and Verification
Creates a dummy translation transaction record for company translations.

COLLECTION: translation_transactions
PURPOSE: Track company translation transactions (subscription-based or individual)

SCHEMA FIELDS:
  _id (ObjectId, auto): MongoDB document ID
  transaction_id (str, required, unique indexed): Transaction identifier
  company_id (str, required, indexed): Company identifier
  user_id (str, optional): User identifier
  subscription_id (str, optional, indexed): Subscription identifier (null for individual transactions)
  file_name (str, required): Original file name
  file_size (int, required): File size in bytes
  original_file_url (str, required): URL to original file (e.g., Google Drive)
  translated_file_url (str, default ""): URL to translated file (empty until completed)
  source_language (str, required): Source language code (ISO 639-1)
  target_language (str, required): Target language code (ISO 639-1)
  status (str, required): pending | processing | completed | failed
  unit_type (str, required): "page" | "word" | "character"
  units_count (int, required): Number of units
  price_per_unit (float, required): Price per unit in dollars
  total_price (float, required): Total price (units_count * price_per_unit)
  estimated_cost (float, required): Estimated cost before processing
  actual_cost (float, optional): Actual cost after completion (null until completed)
  error_message (str, default ""): Error message if failed
  metadata (object, optional): Additional metadata
  created_at (datetime, auto, indexed): Record creation timestamp
  updated_at (datetime, auto): Last update timestamp
  completed_at (datetime, optional): Completion timestamp (null until completed)

METADATA OBJECT SCHEMA (optional):
  customer_email (str): Customer email address
  translation_service (str): Translation service used (e.g., "google", "deepl")
  preserve_formatting (bool): Whether to preserve original formatting
  original_file_type (str): Original file type/extension
  target_file_type (str): Target file type/extension

INDEXES:
  - transaction_id (unique)
  - company_id + status (compound)
  - created_at

Usage:
    python3 server/scripts/schema_translation_transactions.py
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database


async def create_schema_and_dummy_record():
    """Create and document translation_transactions schema, then insert dummy record."""
    print("=" * 80)
    print("TRANSLATION_TRANSACTIONS COLLECTION SCHEMA")
    print("=" * 80)

    # Document schema fields
    schema_fields = {
        "_id": "ObjectId (auto) - MongoDB document ID",
        "transaction_id": "str (required, unique indexed) - Transaction identifier",
        "company_id": "str (required, indexed) - Company identifier",
        "user_id": "str (optional) - User identifier",
        "subscription_id": "str (optional, indexed) - Subscription ID (null for individual)",
        "file_name": "str (required) - Original file name",
        "file_size": "int (required) - File size in bytes",
        "original_file_url": "str (required) - URL to original file",
        "translated_file_url": "str (default '') - URL to translated file",
        "source_language": "str (required) - Source language code (ISO 639-1)",
        "target_language": "str (required) - Target language code (ISO 639-1)",
        "status": "str (required) - pending | processing | completed | failed",
        "unit_type": "str (required) - 'page' | 'word' | 'character'",
        "units_count": "int (required) - Number of units",
        "price_per_unit": "float (required) - Price per unit in dollars",
        "total_price": "float (required) - Total price (units_count * price_per_unit)",
        "estimated_cost": "float (required) - Estimated cost before processing",
        "actual_cost": "float (optional) - Actual cost after completion (null until done)",
        "error_message": "str (default '') - Error message if failed",
        "metadata": "object (optional) - Additional metadata",
        "created_at": "datetime (auto, indexed) - Record creation timestamp",
        "updated_at": "datetime (auto) - Last update timestamp",
        "completed_at": "datetime (optional) - Completion timestamp (null until done)",
    }

    metadata_schema = {
        "customer_email": "str (optional) - Customer email address",
        "translation_service": "str (optional) - Translation service (e.g., 'google', 'deepl')",
        "preserve_formatting": "bool (optional) - Preserve original formatting",
        "original_file_type": "str (optional) - Original file type/extension",
        "target_file_type": "str (optional) - Target file type/extension",
    }

    print("\nPRIMARY FIELDS:")
    print("-" * 80)
    for field, description in schema_fields.items():
        print(f"  {field:25} {description}")

    print("\nMETADATA OBJECT FIELDS (optional):")
    print("-" * 80)
    for field, description in metadata_schema.items():
        print(f"  {field:25} {description}")

    try:
        # Connect to database
        print("\n[1/4] Connecting to MongoDB...")
        connection_success = await database.connect()

        if not connection_success:
            print("✗ Failed to connect to MongoDB")
            print("  Check your MONGODB_URI in .env file")
            return False

        print("✓ Successfully connected to MongoDB")

        # Generate dummy translation transaction record
        print("\n[2/4] Generating dummy translation transaction record...")

        now = datetime.now(timezone.utc)
        transaction_id = f"TXN-MOCK-{uuid.uuid4().hex[:12].upper()}"

        # Transaction details
        units_count = 12
        price_per_unit = 0.10
        total_price = units_count * price_per_unit
        estimated_cost = total_price

        dummy_transaction = {
            # Core identifiers
            "transaction_id": transaction_id,
            "company_id": "test-company-123",
            "user_id": "test-user-456",
            "subscription_id": None,  # Individual transaction, not subscription

            # File information
            "file_name": "business_proposal_2024.pdf",
            "file_size": 2457600,  # ~2.4 MB
            "original_file_url": "https://drive.google.com/file/d/1ABC_mock_original_file/view",
            "translated_file_url": "",  # Empty until translation complete

            # Translation details
            "source_language": "en",
            "target_language": "es",
            "status": "pending",  # pending, processing, completed, failed

            # Pricing and units
            "unit_type": "page",  # page, word, character
            "units_count": units_count,
            "price_per_unit": price_per_unit,
            "total_price": total_price,
            "estimated_cost": estimated_cost,
            "actual_cost": None,  # Set when completed

            # Error handling
            "error_message": "",

            # Metadata
            "metadata": {
                "customer_email": "test@example.com",
                "translation_service": "google",
                "preserve_formatting": True,
                "original_file_type": "pdf",
                "target_file_type": "pdf"
            },

            # Timestamps
            "created_at": now,
            "updated_at": now,
            "completed_at": None,  # Set when status changes to completed
        }

        print("\nDummy Translation Transaction Record:")
        print("-" * 80)
        for key, value in dummy_transaction.items():
            if key == "metadata":
                print(f"  {key}:")
                for mkey, mval in value.items():
                    print(f"    {mkey}: {mval}")
            else:
                # Truncate long URLs
                if isinstance(value, str) and len(value) > 60:
                    print(f"  {key}: {value[:60]}...")
                else:
                    print(f"  {key}: {value}")

        # Insert the document
        print("\n[3/4] Inserting document into translation_transactions collection...")
        result = await database.translation_transactions.insert_one(dummy_transaction)
        print(f"✓ Insert successful!")
        print(f"  Inserted ID: {result.inserted_id}")

        # Verify insertion
        print("\n[4/4] Verifying insertion...")
        verified_transaction = await database.translation_transactions.find_one(
            {"_id": result.inserted_id}
        )

        if verified_transaction:
            print("✓ Translation transaction verified in database")
            print("\nVerified Transaction Data:")
            print("-" * 80)
            print(f"  Document ID:              {verified_transaction['_id']}")
            print(f"  Transaction ID:           {verified_transaction['transaction_id']}")
            print(f"  Company ID:               {verified_transaction['company_id']}")
            print(f"  User ID:                  {verified_transaction.get('user_id', 'N/A')}")
            print(f"  Subscription ID:          {verified_transaction.get('subscription_id', 'N/A')}")
            print(f"  File Name:                {verified_transaction['file_name']}")
            print(f"  File Size:                {verified_transaction['file_size']:,} bytes")
            print(f"  Original File URL:        {verified_transaction['original_file_url'][:50]}...")
            print(f"  Translated File URL:      {verified_transaction['translated_file_url'] or '(pending)'}")
            print(f"  Source Language:          {verified_transaction['source_language']}")
            print(f"  Target Language:          {verified_transaction['target_language']}")
            print(f"  Status:                   {verified_transaction['status']}")
            print(f"  Unit Type:                {verified_transaction['unit_type']}")
            print(f"  Units Count:              {verified_transaction['units_count']}")
            print(f"  Price per Unit:           ${verified_transaction['price_per_unit']:.2f}")
            print(f"  Total Price:              ${verified_transaction['total_price']:.2f}")
            print(f"  Estimated Cost:           ${verified_transaction['estimated_cost']:.2f}")
            print(f"  Actual Cost:              {verified_transaction.get('actual_cost', 'N/A')}")
            print(f"  Error Message:            {verified_transaction['error_message'] or '(none)'}")
            print(f"  Created At:               {verified_transaction['created_at']}")
            print(f"  Updated At:               {verified_transaction['updated_at']}")
            print(f"  Completed At:             {verified_transaction.get('completed_at', 'N/A')}")

            # Show metadata
            if verified_transaction.get('metadata'):
                print("\n  Metadata:")
                for mkey, mval in verified_transaction['metadata'].items():
                    print(f"    {mkey}: {mval}")
            print("-" * 80)
        else:
            print("✗ Translation transaction NOT found in database")
            return False

        # Show collection stats
        total_count = await database.translation_transactions.count_documents({})
        print(f"\n✓ Total translation transactions in collection: {total_count}")

        # Stats by status
        pending_count = await database.translation_transactions.count_documents({"status": "pending"})
        processing_count = await database.translation_transactions.count_documents({"status": "processing"})
        completed_count = await database.translation_transactions.count_documents({"status": "completed"})
        failed_count = await database.translation_transactions.count_documents({"status": "failed"})

        print(f"  - Pending:    {pending_count}")
        print(f"  - Processing: {processing_count}")
        print(f"  - Completed:  {completed_count}")
        print(f"  - Failed:     {failed_count}")

        print("\n" + "=" * 80)
        print("SUCCESS: Translation transactions schema verified and dummy record inserted!")
        print("=" * 80)

        # Show query examples
        print("\nQuery Examples:")
        print("-" * 80)
        print("1. Find by transaction_id:")
        print(f"   db.translation_transactions.find_one({{'transaction_id': '{transaction_id}'}})")
        print("\n2. Find by company_id:")
        print(f"   db.translation_transactions.find({{'company_id': 'test-company-123'}})")
        print("\n3. Find by status:")
        print("   db.translation_transactions.find({'status': 'pending'})")
        print("\n4. Find by language pair:")
        print("   db.translation_transactions.find({'source_language': 'en', 'target_language': 'es'})")
        print("\n5. Find subscription-based transactions:")
        print("   db.translation_transactions.find({'subscription_id': {'$ne': null}})")
        print("\n6. Find individual transactions:")
        print("   db.translation_transactions.find({'subscription_id': null})")
        print("\n7. Aggregate total cost by company:")
        print("   db.translation_transactions.aggregate([")
        print("     {'$group': {'_id': '$company_id', 'total': {'$sum': '$total_price'}}}")
        print("   ])")
        print("\n8. Find failed transactions:")
        print("   db.translation_transactions.find({'status': 'failed', 'error_message': {'$ne': ''}})")
        print("-" * 80)

        return True

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Disconnect from database
        await database.disconnect()
        print("\n✓ Database connection closed")


def main():
    """Main entry point."""
    try:
        success = asyncio.run(create_schema_and_dummy_record())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
