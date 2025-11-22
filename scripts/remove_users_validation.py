#!/usr/bin/env python3
"""
Remove Database-Level Validation for Users Collection

This script removes the JSON Schema validation from users collection
to allow null company_name for individual users.
"""

import asyncio
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/translation")

async def remove_validation():
    """Remove JSON Schema validation from users collection."""
    client = AsyncIOMotorClient(MONGODB_URI)
    db_name = MONGODB_URI.split("/")[-1] if "/" in MONGODB_URI else "translation"
    db = client[db_name]

    print(f"🔧 Removing validation from users collection in '{db_name}'...")

    try:
        # Remove validator by setting it to empty
        await db.command("collMod", "users", validator={}, validationLevel="off")
        print("✅ Removed JSON Schema validation from users collection")
        print("   - NULL company_name is now allowed")
        print("   - Empty string company_name is now allowed")
    except Exception as e:
        print(f"❌ Failed to remove validator: {e}")
        raise
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(remove_validation())
