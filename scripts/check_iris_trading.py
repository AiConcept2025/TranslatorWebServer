"""
Check Iris Trading company and related records.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import json
from datetime import datetime


MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"


async def check_iris_trading():
    """Check Iris Trading company and all related records."""

    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.translation

    print("=" * 80)
    print("IRIS TRADING COMPANY INVESTIGATION")
    print("=" * 80)
    print()

    # Check company collection
    company_collection = db.company
    iris_company = await company_collection.find_one({"company_id": "iris_trading"})

    if iris_company:
        print("🏢 COMPANY RECORD FOUND")
        print()
        # Convert datetime for JSON
        for key, value in iris_company.items():
            if isinstance(value, datetime):
                iris_company[key] = value.isoformat()
        print(json.dumps(iris_company, indent=2, default=str))
        print()
    else:
        print("⚠️  NO COMPANY RECORD FOUND for company_id='iris_trading'")
        print()

    # Search by company name
    iris_by_name = await company_collection.find_one({"company_name": "Iris Trading"})
    if iris_by_name:
        print("🏢 COMPANY RECORD FOUND BY NAME")
        print()
        for key, value in iris_by_name.items():
            if isinstance(value, datetime):
                iris_by_name[key] = value.isoformat()
        print(json.dumps(iris_by_name, indent=2, default=str))
        print()

    # Check all users for this company
    print("=" * 80)
    print("USERS FOR IRIS TRADING")
    print("=" * 80)
    print()

    company_users = db.company_users
    users_cursor = company_users.find({"company_id": "iris_trading"})
    user_count = 0
    async for user in users_cursor:
        user_count += 1
        print(f"👤 User #{user_count}")
        for key, value in user.items():
            if isinstance(value, datetime):
                user[key] = value.isoformat()
        print(json.dumps(user, indent=2, default=str))
        print()

    if user_count == 0:
        print("⚠️  NO USERS FOUND for company_id='iris_trading'")
        print()

    # Check by company name
    users_cursor = company_users.find({"company_name": "Iris Trading"})
    user_count_by_name = 0
    async for user in users_cursor:
        user_count_by_name += 1
        if user_count_by_name == 1:
            print("Found by company_name:")
        print(f"👤 User #{user_count_by_name}")
        for key, value in user.items():
            if isinstance(value, datetime):
                user[key] = value.isoformat()
        print(json.dumps(user, indent=2, default=str))
        print()

    # Check all payments for this company
    print("=" * 80)
    print("PAYMENTS FOR IRIS TRADING")
    print("=" * 80)
    print()

    payments = db.payments
    payments_cursor = payments.find({"company_id": "iris_trading"})
    payment_count = 0
    async for payment in payments_cursor:
        payment_count += 1
        print(f"💳 Payment #{payment_count}")
        for key, value in payment.items():
            if isinstance(value, datetime):
                payment[key] = value.isoformat()
        print(json.dumps(payment, indent=2, default=str))
        print()

    print(f"Total payments: {payment_count}")
    print()

    # Check subscriptions
    print("=" * 80)
    print("SUBSCRIPTIONS FOR IRIS TRADING")
    print("=" * 80)
    print()

    subscriptions = db.subscriptions
    subs_cursor = subscriptions.find({"company_id": "iris_trading"})
    sub_count = 0
    async for sub in subs_cursor:
        sub_count += 1
        print(f"📅 Subscription #{sub_count}")
        for key, value in sub.items():
            if isinstance(value, datetime):
                sub[key] = value.isoformat()
        print(json.dumps(sub, indent=2, default=str))
        print()

    if sub_count == 0:
        print("⚠️  NO SUBSCRIPTIONS FOUND")
        print()

    # Check invoices
    print("=" * 80)
    print("INVOICES FOR IRIS TRADING")
    print("=" * 80)
    print()

    invoices = db.invoices
    inv_cursor = invoices.find({"company_id": "iris_trading"})
    inv_count = 0
    async for inv in inv_cursor:
        inv_count += 1
        print(f"🧾 Invoice #{inv_count}")
        for key, value in inv.items():
            if isinstance(value, datetime):
                inv[key] = value.isoformat()
        print(json.dumps(inv, indent=2, default=str))
        print()

    if inv_count == 0:
        print("⚠️  NO INVOICES FOUND")
        print()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Company exists: {'Yes' if iris_company or iris_by_name else 'No'}")
    print(f"Users: {max(user_count, user_count_by_name)}")
    print(f"Payments: {payment_count}")
    print(f"Subscriptions: {sub_count}")
    print(f"Invoices: {inv_count}")
    print()

    client.close()


if __name__ == "__main__":
    asyncio.run(check_iris_trading())
