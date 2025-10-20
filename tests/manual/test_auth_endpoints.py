"""
Test script for the new signup and login endpoints.
Run this after starting the server with: python -m app.main
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_signup():
    """Test user signup endpoint."""
    print("\n" + "=" * 80)
    print("Testing Signup Endpoint: POST /login/api/auth/signup")
    print("=" * 80)

    signup_data = {
        "user_name": "Test User",
        "user_email": "testuser@example.com",
        "password": "SecurePass123"
    }

    print(f"\n📤 Request:")
    print(json.dumps(signup_data, indent=2))

    try:
        response = requests.post(
            f"{BASE_URL}/login/api/auth/signup",
            json=signup_data,
            headers={"Content-Type": "application/json"}
        )

        print(f"\n📥 Response Status: {response.status_code}")
        print(f"📥 Response Body:")
        print(json.dumps(response.json(), indent=2))

        if response.status_code == 201:
            print("\n✅ Signup Test PASSED!")
            return True
        else:
            print(f"\n❌ Signup Test FAILED! Expected 201, got {response.status_code}")
            return False

    except Exception as e:
        print(f"\n💥 Error: {e}")
        return False


def test_login():
    """Test user login endpoint."""
    print("\n" + "=" * 80)
    print("Testing Login Endpoint: POST /login/api/auth/login")
    print("=" * 80)

    login_data = {
        "email": "testuser@example.com",
        "password": "SecurePass123"
    }

    print(f"\n📤 Request:")
    print(json.dumps(login_data, indent=2))

    try:
        response = requests.post(
            f"{BASE_URL}/login/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )

        print(f"\n📥 Response Status: {response.status_code}")
        print(f"📥 Response Body:")
        print(json.dumps(response.json(), indent=2))

        if response.status_code == 200:
            print("\n✅ Login Test PASSED!")
            return True
        else:
            print(f"\n❌ Login Test FAILED! Expected 200, got {response.status_code}")
            return False

    except Exception as e:
        print(f"\n💥 Error: {e}")
        return False


def test_login_invalid():
    """Test user login with invalid credentials."""
    print("\n" + "=" * 80)
    print("Testing Login with Invalid Credentials")
    print("=" * 80)

    login_data = {
        "email": "testuser@example.com",
        "password": "WrongPassword123"
    }

    print(f"\n📤 Request:")
    print(json.dumps(login_data, indent=2))

    try:
        response = requests.post(
            f"{BASE_URL}/login/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )

        print(f"\n📥 Response Status: {response.status_code}")
        print(f"📥 Response Body:")
        print(json.dumps(response.json(), indent=2))

        if response.status_code == 401:
            print("\n✅ Invalid Login Test PASSED! (correctly rejected)")
            return True
        else:
            print(f"\n❌ Invalid Login Test FAILED! Expected 401, got {response.status_code}")
            return False

    except Exception as e:
        print(f"\n💥 Error: {e}")
        return False


def test_duplicate_signup():
    """Test signup with duplicate email."""
    print("\n" + "=" * 80)
    print("Testing Duplicate Signup (should fail)")
    print("=" * 80)

    signup_data = {
        "user_name": "Test User 2",
        "user_email": "testuser@example.com",  # Same email
        "password": "AnotherPass456"
    }

    print(f"\n📤 Request:")
    print(json.dumps(signup_data, indent=2))

    try:
        response = requests.post(
            f"{BASE_URL}/login/api/auth/signup",
            json=signup_data,
            headers={"Content-Type": "application/json"}
        )

        print(f"\n📥 Response Status: {response.status_code}")
        print(f"📥 Response Body:")
        print(json.dumps(response.json(), indent=2))

        if response.status_code == 400:
            print("\n✅ Duplicate Signup Test PASSED! (correctly rejected)")
            return True
        else:
            print(f"\n❌ Duplicate Signup Test FAILED! Expected 400, got {response.status_code}")
            return False

    except Exception as e:
        print(f"\n💥 Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("🧪 AUTHENTICATION ENDPOINTS TEST SUITE")
    print("=" * 80)
    print("Make sure the server is running on http://localhost:8000")
    print("Start with: cd /Users/vladimirdanishevsky/projects/Translator/server && python -m app.main")

    # Wait for user
    input("\nPress Enter to start tests...")

    results = []

    # Test 1: Signup
    results.append(("Signup", test_signup()))

    # Test 2: Login with correct credentials
    results.append(("Login (valid)", test_login()))

    # Test 3: Login with invalid credentials
    results.append(("Login (invalid)", test_login_invalid()))

    # Test 4: Duplicate signup
    results.append(("Duplicate Signup", test_duplicate_signup()))

    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")

    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    print("=" * 80)

    # Cleanup note
    print("\n📝 NOTE: To clean up test data, run:")
    print('mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"')
    print('db.users_login.deleteOne({"user_email": "testuser@example.com"})')


if __name__ == "__main__":
    main()
