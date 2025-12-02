"""Delete all test data from test database."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings


async def clean_test_data():
    """Drop test collections to start fresh."""
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db_name = settings.active_mongodb_database
    db = client[db_name]

    # Verify we're in TEST database
    if "test" not in db_name.lower():
        raise Exception(f"ABORT: Not a test database! Current: {db_name}")

    print(f"Cleaning test database: {db_name}")

    # Drop collections with Stripe data
    result_txns = await db.user_transactions.delete_many({})
    print(f"✅ Deleted {result_txns.deleted_count} user_transactions")

    result_payments = await db.payments.delete_many({})
    print(f"✅ Deleted {result_payments.deleted_count} payments")

    result_translation_txns = await db.translation_transactions.delete_many({})
    print(f"✅ Deleted {result_translation_txns.deleted_count} translation_transactions")

    print("✅ Test data cleaned")
    client.close()


if __name__ == "__main__":
    asyncio.run(clean_test_data())
