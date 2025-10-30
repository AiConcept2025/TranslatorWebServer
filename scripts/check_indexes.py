#!/usr/bin/env python3
"""Quick script to check current indexes."""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def main():
    client = AsyncIOMotorClient('mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation')
    db = client['translation']

    print("users_login indexes:")
    async for idx in db.users_login.list_indexes():
        print(f"  {idx['name']}: {idx.get('key', {})}")

    print("\nusers indexes:")
    async for idx in db.users.list_indexes():
        print(f"  {idx['name']}: {idx.get('key', {})}")

    print("\npayments indexes:")
    async for idx in db.payments.list_indexes():
        print(f"  {idx['name']}: {idx.get('key', {})}")

    client.close()

asyncio.run(main())
