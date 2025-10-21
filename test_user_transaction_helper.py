"""
Test script for user_transaction_helper module.

This script demonstrates usage of all CRUD operations.
Run after MongoDB is connected.
"""

import asyncio
from datetime import datetime, timezone

from app.utils.user_transaction_helper import (
    create_user_transaction,
    get_user_transaction,
    get_user_transactions_by_email,
    update_user_transaction_status,
)
from app.database import database


async def test_user_transaction_helper():
    """Test all user transaction helper functions."""
    print("\n" + "=" * 80)
    print("Testing User Transaction Helper")
    print("=" * 80 + "\n")

    # Connect to database
    print("1. Connecting to MongoDB...")
    connected = await database.connect()
    if not connected:
        print("   ❌ Failed to connect to MongoDB")
        return
    print("   ✅ Connected to MongoDB\n")

    # Test data
    test_email = "test.user@example.com"
    test_transaction_id = f"sq_test_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        # Test 1: Create transaction
        print("2. Creating new user transaction...")
        result = await create_user_transaction(
            user_name="Test User",
            user_email=test_email,
            document_url="https://drive.google.com/file/d/test123",
            number_of_units=10,
            unit_type="page",
            cost_per_unit=5.99,
            source_language="en",
            target_language="es",
            square_transaction_id=test_transaction_id,
            date=datetime.now(timezone.utc),
            status="processing",
        )

        if result:
            print(f"   ✅ Created transaction: {result}")
        else:
            print("   ❌ Failed to create transaction")
            return
        print()

        # Test 2: Get single transaction
        print("3. Retrieving single transaction...")
        transaction = await get_user_transaction(test_transaction_id)
        if transaction:
            print(f"   ✅ Found transaction:")
            print(f"      - User: {transaction['user_name']} ({transaction['user_email']})")
            print(f"      - Units: {transaction['number_of_units']} {transaction['unit_type']}(s)")
            print(f"      - Cost: ${transaction['total_cost']:.2f}")
            print(f"      - Status: {transaction['status']}")
        else:
            print("   ❌ Transaction not found")
        print()

        # Test 3: Get all transactions for user
        print("4. Retrieving all transactions for user...")
        transactions = await get_user_transactions_by_email(test_email)
        print(f"   ✅ Found {len(transactions)} transaction(s) for {test_email}")
        print()

        # Test 4: Get transactions by status
        print("5. Retrieving transactions by status (processing)...")
        processing_txs = await get_user_transactions_by_email(test_email, status="processing")
        print(f"   ✅ Found {len(processing_txs)} transaction(s) with status 'processing'")
        print()

        # Test 5: Update transaction status
        print("6. Updating transaction status to 'completed'...")
        updated = await update_user_transaction_status(
            test_transaction_id,
            new_status="completed",
        )
        if updated:
            print("   ✅ Status updated successfully")
        else:
            print("   ❌ Failed to update status")
        print()

        # Test 6: Update transaction with error
        print("7. Updating transaction status to 'failed' with error message...")
        updated = await update_user_transaction_status(
            test_transaction_id,
            new_status="failed",
            error_message="Test error: Translation service unavailable",
        )
        if updated:
            print("   ✅ Status and error message updated")
        else:
            print("   ❌ Failed to update status")
        print()

        # Test 7: Verify final state
        print("8. Verifying final transaction state...")
        final_transaction = await get_user_transaction(test_transaction_id)
        if final_transaction:
            print(f"   ✅ Final state:")
            print(f"      - Status: {final_transaction['status']}")
            print(f"      - Error: {final_transaction.get('error_message', 'None')}")
            print(f"      - Updated: {final_transaction['updated_at']}")
        print()

        # Test 8: Test duplicate transaction ID
        print("9. Testing duplicate transaction ID handling...")
        duplicate_result = await create_user_transaction(
            user_name="Another User",
            user_email="another@example.com",
            document_url="https://drive.google.com/file/d/test456",
            number_of_units=5,
            unit_type="word",
            cost_per_unit=0.10,
            source_language="en",
            target_language="fr",
            square_transaction_id=test_transaction_id,  # Same ID
            date=datetime.now(timezone.utc),
            status="processing",
        )
        if duplicate_result is None:
            print("   ✅ Duplicate transaction ID properly rejected")
        else:
            print("   ❌ Duplicate transaction ID was not rejected")
        print()

        print("=" * 80)
        print("All tests completed!")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Disconnect from database
        print("Disconnecting from MongoDB...")
        await database.disconnect()
        print("✅ Disconnected\n")


if __name__ == "__main__":
    asyncio.run(test_user_transaction_helper())
