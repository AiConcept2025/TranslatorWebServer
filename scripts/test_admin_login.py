#!/usr/bin/env python3
"""
Test admin login endpoint with the fixed user.

This script sends a real HTTP request to the admin login endpoint
to verify that authentication works end-to-end.
"""

import asyncio
import httpx
import json
from datetime import datetime


API_BASE_URL = "http://localhost:8000"
ADMIN_EMAIL = "danishevsky@gmail.com"
ADMIN_PASSWORD = "Sveta87201120!"


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def test_admin_login():
    """Test the admin login endpoint."""
    print_section("Admin Login Endpoint Test")

    print(f"\nTest Details:")
    print(f"  Endpoint: POST {API_BASE_URL}/login/admin")
    print(f"  Email: {ADMIN_EMAIL}")
    print(f"  Password: {ADMIN_PASSWORD}")

    # Create request payload
    payload = {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }

    print(f"\n📤 Sending login request...")
    print(f"   Request body: {json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient() as client:
        try:
            # Send login request
            response = await client.post(
                f"{API_BASE_URL}/login/admin",
                json=payload,
                timeout=10.0
            )

            print(f"\n📥 Response received:")
            print(f"   Status code: {response.status_code}")
            print(f"   Headers: {dict(response.headers)}")

            # Parse response
            try:
                response_data = response.json()
                print(f"\n   Response body:")
                print(json.dumps(response_data, indent=2))
            except Exception as e:
                print(f"\n   Response body (text): {response.text}")

            # Analyze result
            print_section("Test Result")

            if response.status_code == 200:
                print("\n✅ LOGIN SUCCESSFUL!")

                if isinstance(response_data, dict):
                    # Check response structure
                    print("\n📋 Response structure:")
                    print(f"   success: {response_data.get('success')}")
                    print(f"   message: {response_data.get('message')}")

                    if 'data' in response_data:
                        data = response_data['data']
                        print(f"\n   Authentication data:")
                        print(f"     authToken: {data.get('authToken', '')[:16]}... (JWT)")
                        print(f"     tokenType: {data.get('tokenType')}")
                        print(f"     expiresIn: {data.get('expiresIn')} seconds")
                        print(f"     expiresAt: {data.get('expiresAt')}")

                        if 'user' in data:
                            user = data['user']
                            print(f"\n   User data:")
                            print(f"     user_id: {user.get('user_id')}")
                            print(f"     user_name: {user.get('user_name')}")
                            print(f"     email: {user.get('email')}")
                            print(f"     permission_level: {user.get('permission_level')}")

                            # Verify admin permission
                            if user.get('permission_level') == 'admin':
                                print(f"\n   ✅ User has ADMIN permission level")
                            else:
                                print(f"\n   ❌ User does NOT have admin permission (got: {user.get('permission_level')})")

                print("\n🎉 Admin login is working correctly!")
                print(f"   You can use this endpoint in your application")
                return True

            elif response.status_code == 401:
                print("\n❌ AUTHENTICATION FAILED (401 Unauthorized)")
                print("\n   Possible issues:")
                print("   1. Password hash mismatch")
                print("   2. Email not found in iris-admins collection")
                print("   3. bcrypt verification failed")
                return False

            elif response.status_code == 500:
                print("\n❌ SERVER ERROR (500 Internal Server Error)")
                print("\n   Check server logs for details")
                return False

            else:
                print(f"\n❌ UNEXPECTED RESPONSE (Status {response.status_code})")
                return False

        except httpx.ConnectError as e:
            print("\n❌ CONNECTION FAILED")
            print(f"   Error: {e}")
            print("\n   Is the FastAPI server running?")
            print(f"   Start it with: uvicorn app.main:app --reload")
            return False

        except Exception as e:
            print("\n❌ TEST FAILED")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """Main execution."""
    print_section("Admin Login Integration Test")
    print(f"\nTimestamp: {datetime.now().isoformat()}")

    success = await test_admin_login()

    print_section("Test Summary")
    if success:
        print("\n✅ ALL TESTS PASSED")
        print(f"\nAdmin login is working for:")
        print(f"  Email: {ADMIN_EMAIL}")
        print(f"  Password: {ADMIN_PASSWORD}")
    else:
        print("\n❌ TESTS FAILED")
        print("\nSee details above for error information")


if __name__ == "__main__":
    asyncio.run(main())
