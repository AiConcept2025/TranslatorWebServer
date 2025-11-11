#!/usr/bin/env python3
"""
Validation script for real integration test setup.

This script checks all prerequisites before running real integration tests:
1. Server is running on http://localhost:8000
2. MongoDB is accessible
3. Google Drive credentials are configured
4. Required Python packages are installed

Run this BEFORE running integration tests to ensure everything is ready.

Usage:
    python tests/integration/validate_test_setup.py
"""

import sys
import asyncio
import os
from pathlib import Path


async def check_server_running() -> bool:
    """Check if FastAPI server is running on localhost:8000."""
    print("\n1. Checking if server is running...")
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get("http://localhost:8000/health")
                if response.status_code == 200:
                    print("   ✅ Server is running on http://localhost:8000")
                    return True
                else:
                    print(f"   ❌ Server responded with status {response.status_code}")
                    return False
            except httpx.ConnectError:
                print("   ❌ Cannot connect to http://localhost:8000")
                print("   → Start server: uvicorn app.main:app --reload --port 8000")
                return False
    except ImportError:
        print("   ❌ httpx not installed")
        print("   → Install: pip install httpx")
        return False


async def check_mongodb_running() -> bool:
    """Check if MongoDB is running and accessible."""
    print("\n2. Checking if MongoDB is running...")
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from app.config import settings

        client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)

        # Try to get server info
        await client.admin.command("ping")

        print(f"   ✅ MongoDB is running at {settings.mongodb_uri}")

        # Check if test database exists
        db_list = await client.list_database_names()
        if "translation_test" in db_list:
            print("   ✅ translation_test database exists")
        else:
            print("   ⚠️  translation_test database does not exist (will be created)")

        client.close()
        return True

    except ImportError:
        print("   ❌ motor not installed")
        print("   → Install: pip install motor")
        return False
    except Exception as e:
        print(f"   ❌ Cannot connect to MongoDB: {e}")
        print("   → Start MongoDB: brew services start mongodb-community")
        return False


def check_google_drive_credentials() -> bool:
    """Check if Google Drive credentials are configured."""
    print("\n3. Checking Google Drive credentials...")

    # Check if credentials file exists
    credentials_path = Path("service-account-key.json")

    if not credentials_path.exists():
        print(f"   ❌ Credentials file not found: {credentials_path}")
        print("   → Download service account key from Google Cloud Console")
        return False

    print(f"   ✅ Credentials file exists: {credentials_path}")

    # Check if .env has Google Drive settings
    env_path = Path(".env")

    if not env_path.exists():
        print("   ❌ .env file not found")
        print("   → Create .env from .env.example")
        return False

    with open(env_path, "r") as f:
        env_content = f.read()

    if "GOOGLE_DRIVE_ENABLED=true" in env_content or "GOOGLE_DRIVE_ENABLED=True" in env_content:
        print("   ✅ GOOGLE_DRIVE_ENABLED=true in .env")
    else:
        print("   ⚠️  GOOGLE_DRIVE_ENABLED not set to true in .env")

    if "GOOGLE_DRIVE_CREDENTIALS_PATH" in env_content:
        print("   ✅ GOOGLE_DRIVE_CREDENTIALS_PATH configured in .env")
    else:
        print("   ⚠️  GOOGLE_DRIVE_CREDENTIALS_PATH not configured in .env")

    return True


def check_required_packages() -> bool:
    """Check if required Python packages are installed."""
    print("\n4. Checking required Python packages...")

    required_packages = [
        ("pytest", "pytest"),
        ("httpx", "httpx"),
        ("motor", "motor"),
        ("bson", "pymongo"),
        ("jose", "python-jose"),
        ("google.auth", "google-auth"),
        ("googleapiclient", "google-api-python-client"),
    ]

    all_installed = True

    for package_name, install_name in required_packages:
        try:
            __import__(package_name)
            print(f"   ✅ {package_name} installed")
        except ImportError:
            print(f"   ❌ {package_name} not installed")
            print(f"      → Install: pip install {install_name}")
            all_installed = False

    return all_installed


def check_jwt_secret() -> bool:
    """Check if JWT secret is configured."""
    print("\n5. Checking JWT secret configuration...")

    try:
        from app.config import settings

        if hasattr(settings, "secret_key") and settings.secret_key:
            if len(settings.secret_key) >= 32:
                print(f"   ✅ SECRET_KEY configured (length: {len(settings.secret_key)})")
                return True
            else:
                print(f"   ❌ SECRET_KEY too short (length: {len(settings.secret_key)}, need: 32+)")
                return False
        else:
            print("   ❌ SECRET_KEY not configured in .env")
            return False

    except Exception as e:
        print(f"   ❌ Cannot load settings: {e}")
        return False


async def main():
    """Run all validation checks."""
    print("=" * 80)
    print("REAL INTEGRATION TEST SETUP VALIDATION")
    print("=" * 80)
    print("\nChecking prerequisites for real integration tests...")

    checks = [
        ("Server Running", await check_server_running()),
        ("MongoDB Running", await check_mongodb_running()),
        ("Google Drive Credentials", check_google_drive_credentials()),
        ("Required Packages", check_required_packages()),
        ("JWT Secret", check_jwt_secret()),
    ]

    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    all_passed = True
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not result:
            all_passed = False

    print("=" * 80)

    if all_passed:
        print("\n✅ ALL CHECKS PASSED - Ready to run real integration tests!")
        print("\nRun tests:")
        print("  pytest tests/integration/test_confirm_square_payment.py -v")
        sys.exit(0)
    else:
        print("\n❌ SOME CHECKS FAILED - Fix issues before running tests")
        print("\nSee output above for specific issues to fix.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
