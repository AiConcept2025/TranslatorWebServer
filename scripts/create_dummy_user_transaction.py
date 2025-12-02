#!/usr/bin/env python3
"""
Create Dummy User Transaction
Inserts a realistic test entry in the user_transactions collection.

Usage:
    python3 server/scripts/create_dummy_user_transaction.py
"""
import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.mongodb import database
from app.utils.user_transaction_helper import create_user_transaction


async def create_dummy_transaction():
    """Create and insert a realistic dummy user transaction."""
    print("=" * 80)
    print("Creating Dummy User Transaction")
    print("=" * 80)

    try:
        # Connect to database
        print("\n[1/4] Connecting to MongoDB...")
        connection_success = await database.connect()

        if not connection_success:
            print("✗ Failed to connect to MongoDB")
            print("  Check your MONGODB_URI in .env file")
            return False

        print("✓ Successfully connected to MongoDB")

        # Generate realistic dummy data
        print("\n[2/4] Generating dummy transaction data...")

        # User information
        user_name = "John Doe"
        user_email = "john.doe@example.com"

        # Document information
        document_url = "https://drive.google.com/file/d/1ABC_sample_document/view"

        # Transaction details
        number_of_units = 10
        unit_type = "page"  # Valid: "page", "word", "character"
        cost_per_unit = 0.15  # $0.15 per page

        # Languages
        source_language = "en"  # English
        target_language = "es"  # Spanish

        # Stripe payment details
        stripe_checkout_session_id = f"STRIPE-{uuid.uuid4().hex[:16].upper()}"
        stripe_payment_intent_id = f"STRIPE-PAY-{uuid.uuid4().hex[:12].upper()}"

        # Transaction metadata
        date = datetime.now(timezone.utc)
        status = "completed"  # Valid: "processing", "completed", "failed"

        # Calculate total cost and amount in cents
        total_cost = number_of_units * cost_per_unit
        amount_cents = int(total_cost * 100)

        # Stripe payment fields
        currency = "USD"
        payment_status = "COMPLETED"  # Valid: "APPROVED", "COMPLETED", "CANCELED", "FAILED"
        payment_date = datetime.now(timezone.utc)

        print("\nTransaction Details:")
        print("-" * 80)
        print(f"  User Name:               {user_name}")
        print(f"  User Email:              {user_email}")
        print(f"  Document URL:            {document_url}")
        print(f"  Units:                   {number_of_units} {unit_type}s")
        print(f"  Cost per Unit:           ${cost_per_unit:.2f}")
        print(f"  Total Cost:              ${total_cost:.2f}")
        print(f"  Source Language:         {source_language}")
        print(f"  Target Language:         {target_language}")
        print(f"  Stripe Transaction ID:   {stripe_checkout_session_id}")
        print(f"  Stripe Payment ID:       {stripe_payment_intent_id}")
        print(f"  Amount (cents):          {amount_cents}")
        print(f"  Currency:                {currency}")
        print(f"  Payment Status:          {payment_status}")
        print(f"  Date:                    {date.isoformat()}")
        print(f"  Payment Date:            {payment_date.isoformat()}")
        print(f"  Status:                  {status}")
        print("-" * 80)

        # Insert transaction using helper function
        print("\n[3/4] Inserting transaction into database...")

        result = await create_user_transaction(
            user_name=user_name,
            user_email=user_email,
            document_url=document_url,
            number_of_units=number_of_units,
            unit_type=unit_type,
            cost_per_unit=cost_per_unit,
            source_language=source_language,
            target_language=target_language,
            stripe_checkout_session_id=stripe_checkout_session_id,
            date=date,
            status=status,
            # Stripe payment fields
            stripe_payment_intent_id=stripe_payment_intent_id,
            amount_cents=amount_cents,
            currency=currency,
            payment_status=payment_status,
            payment_date=payment_date,
        )

        if result is None:
            print("✗ Failed to insert transaction")
            print("  Check logs for detailed error information")
            return False

        print(f"✓ Transaction inserted successfully!")
        print(f"  Returned ID: {result}")

        # Verify insertion
        print("\n[4/4] Verifying insertion...")
        from app.utils.user_transaction_helper import get_user_transaction

        verified_transaction = await get_user_transaction(stripe_checkout_session_id)

        if verified_transaction:
            print("✓ Transaction verified in database")
            print("\nVerified Transaction Data:")
            print("-" * 80)
            print(f"  Transaction ID:    {verified_transaction['stripe_checkout_session_id']}")
            print(f"  Payment ID:        {verified_transaction.get('stripe_payment_intent_id', 'N/A')}")
            print(f"  User Email:        {verified_transaction['user_email']}")
            print(f"  User Name:         {verified_transaction['user_name']}")
            print(f"  Units:             {verified_transaction['number_of_units']} {verified_transaction['unit_type']}s")
            print(f"  Total Cost:        ${verified_transaction['total_cost']:.2f}")
            print(f"  Amount (cents):    {verified_transaction.get('amount_cents', 'N/A')}")
            print(f"  Currency:          {verified_transaction.get('currency', 'N/A')}")
            print(f"  Payment Status:    {verified_transaction.get('payment_status', 'N/A')}")
            print(f"  Languages:         {verified_transaction['source_language']} → {verified_transaction['target_language']}")
            print(f"  Status:            {verified_transaction['status']}")
            print(f"  Created At:        {verified_transaction['created_at']}")
            print(f"  Payment Date:      {verified_transaction.get('payment_date', 'N/A')}")
            print(f"  Refunds:           {len(verified_transaction.get('refunds', []))}")
            print("-" * 80)
        else:
            print("✗ Transaction NOT found in database")
            return False

        # Show collection stats
        from app.utils.user_transaction_helper import get_user_transactions_by_email

        user_transactions = await get_user_transactions_by_email(user_email)
        print(f"\n✓ Total transactions for {user_email}: {len(user_transactions)}")

        print("\n" + "=" * 80)
        print("SUCCESS: Dummy transaction created successfully!")
        print("=" * 80)

        # Show query examples
        print("\nQuery Examples:")
        print("-" * 80)
        print("1. Find by stripe_checkout_session_id:")
        print(f"   db.user_transactions.find_one({{'stripe_checkout_session_id': '{stripe_checkout_session_id}'}})")
        print("\n2. Find by user email:")
        print(f"   db.user_transactions.find({{'user_email': '{user_email}'}})")
        print("\n3. Find by status:")
        print(f"   db.user_transactions.find({{'status': '{status}'}})")
        print("\n4. Find by language pair:")
        print(f"   db.user_transactions.find({{'source_language': '{source_language}', 'target_language': '{target_language}'}})")
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
        success = asyncio.run(create_dummy_transaction())
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
