#!/usr/bin/env python3
"""
Test Script: Test admin login via API

This script simulates the admin login process to identify the issue.
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import httpx
except ImportError as e:
    print(f"Error: Missing required package - {e}")
    sys.exit(1)


async def test_admin_login():
    """Test admin login via API endpoint."""
    print("=" * 80)
    print("ADMIN LOGIN API TEST")
    print("=" * 80)
    print()

    api_url = "http://localhost:8000/login/admin"
    email = "danishevsky@gmail.com"
    password = "Sveta87201120!"

    print(f"Testing admin login:")
    print(f"  URL: {api_url}")
    print(f"  Email: {email}")
    print(f"  Password: {password}")
    print()

    async with httpx.AsyncClient() as client:
        try:
            # Test admin login
            print("Sending POST request...")
            response = await client.post(
                api_url,
                json={
                    "email": email,
                    "password": password
                },
                timeout=10.0
            )

            print(f"Response Status: {response.status_code}")
            print()
            print("Response Headers:")
            for key, value in response.headers.items():
                print(f"  {key}: {value}")
            print()
            print("Response Body:")
            print(response.text)
            print()

            if response.status_code == 200:
                print("✅ LOGIN SUCCESSFUL")
                data = response.json()
                if "session_token" in data:
                    print(f"  Token: {data['session_token'][:30]}...")
            else:
                print("❌ LOGIN FAILED")
                try:
                    error_data = response.json()
                    print(f"  Error: {error_data}")
                except:
                    print(f"  Raw response: {response.text}")

        except httpx.ConnectError:
            print("✗ Could not connect to backend server")
            print("  Make sure the server is running on http://localhost:8000")
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_admin_login())
