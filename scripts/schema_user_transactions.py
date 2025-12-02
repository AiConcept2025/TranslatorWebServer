#!/usr/bin/env python3
"""
User Transactions Collection Schema Definition and Verification
Creates a dummy user transaction record for individual user translations.

COLLECTION: user_transactions
PURPOSE: Track individual user translation transactions with Stripe payments

SCHEMA FIELDS:
  _id (ObjectId, auto): MongoDB document ID
  user_name (str, required): Full name of the user
  user_email (str, required, indexed): User email address
  document_url (str, required): Document URL/path (e.g., Google Drive)
  translated_url (str, optional): Translated document URL/path
  number_of_units (int, required): Number of units translated
  unit_type (str, required): "page" | "word" | "character"
  cost_per_unit (float, required): Cost per unit in dollars
  source_language (str, required): Source language code (ISO 639-1)
  target_language (str, required): Target language code (ISO 639-1)
  stripe_checkout_session_id (str, required, unique indexed): Stripe transaction ID
  date (datetime, required): Transaction date
  status (str, default "processing"): processing | completed | failed
  total_cost (float, required): Total cost (auto-calculated: number_of_units * cost_per_unit)
  created_at (datetime, auto, indexed): Record creation timestamp
  updated_at (datetime, auto): Last update timestamp
  stripe_payment_intent_id (str, required): Stripe payment ID
  amount_cents (int, required): Payment amount in cents
  currency (str, default "USD"): Currency code (ISO 4217)
  payment_status (str, default "COMPLETED"): APPROVED | COMPLETED | CANCELED | FAILED
  refunds (array, default []): Array of refund objects
  payment_date (datetime, required): Payment processing date

INDEXES:
  - stripe_checkout_session_id (unique)
  - user_email
  - date (descending)
  - user_email + date (compound)
  - status
  - created_at

Usage:
    python3 server/scripts/schema_user_transactions.py
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
    """Create and document user_transactions schema, then insert dummy record."""
    print("=" * 80)
    print("USER_TRANSACTIONS COLLECTION SCHEMA")
    print("=" * 80)

    # Document schema fields
    schema_fields = {
        "_id": "ObjectId (auto) - MongoDB document ID",
        "user_name": "str (required) - Full name of the user",
        "user_email": "str (required, indexed) - User email address",
        "document_url": "str (required) - Document URL/path",
        "translated_url": "str (optional) - Translated document URL/path",
        "number_of_units": "int (required) - Number of units translated",
        "unit_type": "str (required) - 'page' | 'word' | 'character'",
        "cost_per_unit": "float (required) - Cost per unit in dollars",
        "source_language": "str (required) - Source language code (ISO 639-1)",
        "target_language": "str (required) - Target language code (ISO 639-1)",
        "stripe_checkout_session_id": "str (required, unique indexed) - Stripe transaction ID",
        "date": "datetime (required) - Transaction date",
        "status": "str (default 'processing') - processing | completed | failed",
        "total_cost": "float (required) - Total cost (number_of_units * cost_per_unit)",
        "created_at": "datetime (auto, indexed) - Record creation timestamp",
        "updated_at": "datetime (auto) - Last update timestamp",
        "stripe_payment_intent_id": "str (required) - Stripe payment ID",
        "amount_cents": "int (required) - Payment amount in cents",
        "currency": "str (default 'USD') - Currency code (ISO 4217)",
        "payment_status": "str (default 'COMPLETED') - APPROVED | COMPLETED | CANCELED | FAILED",
        "refunds": "array (default []) - Array of refund objects",
        "payment_date": "datetime (required) - Payment processing date",
    }

    print("\nSCHEMA FIELDS:")
    print("-" * 80)
    for field, description in schema_fields.items():
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

        # Generate dummy user transaction record
        print("\n[2/4] Generating dummy user transaction record...")

        now = datetime.now(timezone.utc)
        stripe_checkout_session_id = f"STRIPE-{uuid.uuid4().hex[:16].upper()}"
        stripe_payment_intent_id = f"STRIPE-{uuid.uuid4().hex[:16].upper()}"

        # Transaction details
        number_of_units = 10
        cost_per_unit = 0.15
        total_cost = number_of_units * cost_per_unit
        amount_cents = int(total_cost * 100)

        dummy_transaction = {
            "user_name": "John Doe",
            "user_email": "john.doe@example.com",
            "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
            "translated_url": "https://drive.google.com/file/d/1ABC_transl_document/view",
            "number_of_units": number_of_units,
            "unit_type": "page",
            "cost_per_unit": cost_per_unit,
            "source_language": "en",
            "target_language": "es",
            "stripe_checkout_session_id": stripe_checkout_session_id,
            "date": now,
            "status": "completed",
            "total_cost": total_cost,
            "created_at": now,
            "updated_at": now,
            "stripe_payment_intent_id": stripe_payment_intent_id,
            "amount_cents": amount_cents,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],  # Empty refunds array
            "payment_date": now,
        }

        print("\nDummy User Transaction Record:")
        print("-" * 80)
        for key, value in dummy_transaction.items():
            if key == "refunds":
                print(f"  {key}: [{len(value)} refund(s)]")
            else:
                print(f"  {key}: {value}")

        # Insert the document
        print("\n[3/4] Inserting document into user_transactions collection...")
        result = await database.user_transactions.insert_one(dummy_transaction)
        print(f"✓ Insert successful!")
        print(f"  Inserted ID: {result.inserted_id}")

        # Verify insertion
        print("\n[4/4] Verifying insertion...")
        verified_transaction = await database.user_transactions.find_one(
            {"_id": result.inserted_id}
        )

        if verified_transaction:
            print("✓ User transaction verified in database")
            print("\nVerified Transaction Data:")
            print("-" * 80)
            print(f"  Document ID:              {verified_transaction['_id']}")
            print(f"  User Name:                {verified_transaction['user_name']}")
            print(f"  User Email:               {verified_transaction['user_email']}")
            print(f"  Document URL:             {verified_transaction['document_url'][:50]}...")
            translated_url = verified_transaction.get('translated_url', 'N/A')
            if translated_url and translated_url != 'N/A':
                print(f"  Translated URL:           {translated_url[:50]}...")
            else:
                print(f"  Translated URL:           {translated_url}")
            print(f"  Number of Units:          {verified_transaction['number_of_units']}")
            print(f"  Unit Type:                {verified_transaction['unit_type']}")
            print(f"  Cost per Unit:            ${verified_transaction['cost_per_unit']:.2f}")
            print(f"  Total Cost:               ${verified_transaction['total_cost']:.2f}")
            print(f"  Source Language:          {verified_transaction['source_language']}")
            print(f"  Target Language:          {verified_transaction['target_language']}")
            print(f"  Stripe Transaction ID:    {verified_transaction['stripe_checkout_session_id']}")
            print(f"  Stripe Payment ID:        {verified_transaction['stripe_payment_intent_id']}")
            print(f"  Amount (cents):           {verified_transaction['amount_cents']}")
            print(f"  Currency:                 {verified_transaction['currency']}")
            print(f"  Payment Status:           {verified_transaction['payment_status']}")
            print(f"  Status:                   {verified_transaction['status']}")
            print(f"  Date:                     {verified_transaction['date']}")
            print(f"  Payment Date:             {verified_transaction['payment_date']}")
            print(f"  Created At:               {verified_transaction['created_at']}")
            print(f"  Updated At:               {verified_transaction['updated_at']}")
            print(f"  Refunds:                  {len(verified_transaction.get('refunds', []))}")
            print("-" * 80)
        else:
            print("✗ User transaction NOT found in database")
            return False

        # Show collection stats
        total_count = await database.user_transactions.count_documents({})
        print(f"\n✓ Total user transactions in collection: {total_count}")

        # Stats by status
        completed_count = await database.user_transactions.count_documents({"status": "completed"})
        processing_count = await database.user_transactions.count_documents({"status": "processing"})
        failed_count = await database.user_transactions.count_documents({"status": "failed"})

        print(f"  - Completed:  {completed_count}")
        print(f"  - Processing: {processing_count}")
        print(f"  - Failed:     {failed_count}")

        print("\n" + "=" * 80)
        print("SUCCESS: User transactions schema verified and dummy record inserted!")
        print("=" * 80)

        # Show query examples
        print("\nQuery Examples:")
        print("-" * 80)
        print("1. Find by stripe_checkout_session_id:")
        print(f"   db.user_transactions.find_one({{'stripe_checkout_session_id': '{stripe_checkout_session_id}'}})")
        print("\n2. Find by user email:")
        print(f"   db.user_transactions.find({{'user_email': 'john.doe@example.com'}})")
        print("\n3. Find by status:")
        print("   db.user_transactions.find({'status': 'completed'})")
        print("\n4. Find by language pair:")
        print("   db.user_transactions.find({'source_language': 'en', 'target_language': 'es'})")
        print("\n5. Find recent transactions (last 30 days):")
        print("   db.user_transactions.find({'date': {'$gte': new Date(Date.now() - 30*24*60*60*1000)}})")
        print("\n6. Find by unit type:")
        print("   db.user_transactions.find({'unit_type': 'page'})")
        print("\n7. Aggregate total cost by user:")
        print("   db.user_transactions.aggregate([")
        print("     {'$group': {'_id': '$user_email', 'total': {'$sum': '$total_cost'}}}")
        print("   ])")
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
