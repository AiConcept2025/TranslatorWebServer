#!/usr/bin/env python3
"""
Payments Collection Schema Definition and Verification
Creates a dummy payment record with Square integration and refunds array.

COLLECTION: payments
PURPOSE: Track company payments with Square payment integration

SCHEMA FIELDS:
  _id (ObjectId, auto): MongoDB document ID
  company_id (str, required, indexed): Company identifier (e.g., "cmp_00123")
  company_name (str, required): Company name
  user_email (str, required, indexed): User email address
  square_payment_id (str, required, indexed): Square payment ID
  amount (int, required): Payment amount in cents
  currency (str, default "USD"): Currency code (ISO 4217)
  payment_status (str, required, indexed): COMPLETED | PENDING | FAILED | REFUNDED
  refunds (array, default []): Array of refund objects
  created_at (datetime, auto, indexed): Record creation timestamp
  updated_at (datetime, auto): Last update timestamp
  payment_date (datetime, required, indexed): Payment processing date

REFUND OBJECT SCHEMA:
  refund_id (str, required): Refund identifier
  amount (int, required): Refund amount in cents
  currency (str, required): Currency code
  status (str, required): COMPLETED | PENDING | FAILED
  idempotency_key (str, required): Idempotency key for Square API
  created_at (datetime, required): Refund creation timestamp

INDEXES:
  - square_payment_id (non-unique for stub implementation)
  - company_id
  - subscription_id
  - user_id
  - payment_status
  - payment_date
  - user_email
  - company_id + payment_status (compound)
  - user_id + payment_date (compound)
  - square_order_id
  - square_customer_id
  - created_at

Usage:
    python3 server/scripts/schema_payments.py
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
    """Create and document payments schema, then insert dummy record."""
    print("=" * 80)
    print("PAYMENTS COLLECTION SCHEMA")
    print("=" * 80)

    # Document schema fields
    schema_fields = {
        "_id": "ObjectId (auto) - MongoDB document ID",
        "company_id": "str (required, indexed) - Company identifier",
        "company_name": "str (required) - Company name",
        "user_email": "str (required, indexed) - User email address",
        "square_payment_id": "str (required, indexed) - Square payment ID",
        "amount": "int (required) - Payment amount in cents",
        "currency": "str (default 'USD') - Currency code ISO 4217",
        "payment_status": "str (required, indexed) - COMPLETED | PENDING | FAILED | REFUNDED",
        "refunds": "array (default []) - Array of refund objects",
        "created_at": "datetime (auto, indexed) - Record creation timestamp",
        "updated_at": "datetime (auto) - Last update timestamp",
        "payment_date": "datetime (required, indexed) - Payment processing date",
    }

    refund_schema = {
        "refund_id": "str (required) - Refund identifier",
        "amount": "int (required) - Refund amount in cents",
        "currency": "str (required) - Currency code",
        "status": "str (required) - COMPLETED | PENDING | FAILED",
        "idempotency_key": "str (required) - Idempotency key for Square API",
        "created_at": "datetime (required) - Refund creation timestamp",
    }

    print("\nPRIMARY FIELDS:")
    print("-" * 80)
    for field, description in schema_fields.items():
        print(f"  {field:25} {description}")

    print("\nREFUND OBJECT FIELDS:")
    print("-" * 80)
    for field, description in refund_schema.items():
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

        # Generate dummy payment record
        print("\n[2/4] Generating dummy payment record...")

        now = datetime.now(timezone.utc)
        payment_id = f"payment_sq_{int(now.timestamp())}_{uuid.uuid4().hex[:8]}"

        # REFUND OBJECT STRUCTURE (for reference - not created in this record)
        # When a refund is processed, objects with this structure are added to the refunds array:
        # {
        #     "refund_id": "rfn_01J2M9ABCD",
        #     "amount": 500,  # in cents
        #     "currency": "USD",
        #     "status": "COMPLETED",
        #     "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62",
        #     "created_at": datetime
        # }

        dummy_payment = {
            "company_id": "cmp_00123",
            "company_name": "Acme Health LLC",
            "user_email": "test5@yahoo.com",
            "square_payment_id": payment_id,
            "amount": 1299,  # $12.99
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],  # EMPTY array - refunds are added when processed
            "created_at": now,
            "updated_at": now,
            "payment_date": now,
        }

        print("\nDummy Payment Record:")
        print("-" * 80)
        for key, value in dummy_payment.items():
            if key == "refunds":
                print(f"  {key}: [] (empty array)")
            else:
                print(f"  {key}: {value}")

        # Insert the document
        print("\n[3/4] Inserting document into payments collection...")
        result = await database.payments.insert_one(dummy_payment)
        print(f"✓ Insert successful!")
        print(f"  Inserted ID: {result.inserted_id}")

        # Verify insertion
        print("\n[4/4] Verifying insertion...")
        verified_payment = await database.payments.find_one(
            {"_id": result.inserted_id}
        )

        if verified_payment:
            print("✓ Payment verified in database")
            print("\nVerified Payment Data:")
            print("-" * 80)
            print(f"  Document ID:        {verified_payment['_id']}")
            print(f"  Company ID:         {verified_payment['company_id']}")
            print(f"  Company Name:       {verified_payment['company_name']}")
            print(f"  User Email:         {verified_payment['user_email']}")
            print(f"  Square Payment ID:  {verified_payment['square_payment_id']}")
            print(f"  Amount:             ${verified_payment['amount'] / 100:.2f}")
            print(f"  Currency:           {verified_payment['currency']}")
            print(f"  Payment Status:     {verified_payment['payment_status']}")
            print(f"  Number of Refunds:  {len(verified_payment.get('refunds', []))}")
            print(f"  Created At:         {verified_payment['created_at']}")
            print(f"  Updated At:         {verified_payment['updated_at']}")
            print(f"  Payment Date:       {verified_payment['payment_date']}")

            # Show refund details (if any)
            if verified_payment.get('refunds'):
                print("\n  Refund Details:")
                for idx, refund in enumerate(verified_payment['refunds'], 1):
                    print(f"    Refund #{idx}:")
                    print(f"      ID:               {refund['refund_id']}")
                    print(f"      Amount:           ${refund['amount'] / 100:.2f}")
                    print(f"      Currency:         {refund['currency']}")
                    print(f"      Status:           {refund['status']}")
                    print(f"      Idempotency Key:  {refund['idempotency_key']}")
                    print(f"      Created At:       {refund['created_at']}")
            else:
                print("\n  Refunds: [] (no refunds)")
            print("-" * 80)
        else:
            print("✗ Payment NOT found in database")
            return False

        # Show collection stats
        total_count = await database.payments.count_documents({})
        print(f"\n✓ Total payments in collection: {total_count}")

        print("\n" + "=" * 80)
        print("SUCCESS: Payments schema verified and dummy record inserted!")
        print("=" * 80)

        # Show query examples
        print("\nQuery Examples:")
        print("-" * 80)
        print("1. Find by square_payment_id:")
        print(f"   db.payments.find_one({{'square_payment_id': '{payment_id}'}})")
        print("\n2. Find by company_id:")
        print(f"   db.payments.find({{'company_id': 'cmp_00123'}})")
        print("\n3. Find by payment_status:")
        print(f"   db.payments.find({{'payment_status': 'COMPLETED'}})")
        print("\n4. Find payments with refunds:")
        print("   db.payments.find({'refunds': {'$ne': []}})")
        print("\n5. Find by user email:")
        print(f"   db.payments.find({{'user_email': 'test5@yahoo.com'}})")
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
