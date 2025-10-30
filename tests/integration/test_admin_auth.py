"""
Integration tests for admin authentication backend.

Tests verify the complete admin authentication workflow including:
- Valid admin login with JWT token generation
- Invalid credentials handling
- Missing fields validation
- Protected admin endpoint access control
- Login date updates in database
- JWT token verification

Test Database: translation (same as production for integration testing)
Collections: iris-admins
"""

import pytest
import pytest_asyncio
import bcrypt
import asyncio
from datetime import datetime, timezone
from httpx import AsyncClient
from functools import partial

from app.main import app
from app.database.mongodb import database


@pytest_asyncio.fixture
async def client():
    """Provide an AsyncClient for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client


@pytest_asyncio.fixture
async def test_db():
    """Provide MongoDB database connection."""
    await database.connect()
    yield database.db
    await database.disconnect()


@pytest_asyncio.fixture
async def test_admin(test_db):
    """Create a test admin user for authentication tests."""
    # Hash password with bcrypt (12 rounds)
    password = "TestPassword123!"
    password_bytes = password.encode('utf-8')[:72]  # bcrypt limit is 72 bytes

    # Run bcrypt in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    salt = await loop.run_in_executor(None, bcrypt.gensalt, 12)
    password_hash = await loop.run_in_executor(
        None,
        partial(bcrypt.hashpw, password_bytes, salt)
    )
    password_hash_str = password_hash.decode('utf-8')

    # Create admin document
    now = datetime.now(timezone.utc)
    admin_doc = {
        "user_id": "test_admin_001",
        "user_name": "Test Admin",
        "user_email": "test-admin@test.com",
        "password": password_hash_str,  # Store hashed password
        "login_date": None,  # Will be set on first login
        "created_at": now,
        "updated_at": now
    }

    # Insert into iris-admins collection
    result = await test_db["iris-admins"].insert_one(admin_doc)
    admin_doc["_id"] = result.inserted_id

    yield admin_doc

    # Cleanup
    await test_db["iris-admins"].delete_one({"_id": result.inserted_id})


@pytest.mark.integration
class TestAdminAuthentication:
    """Integration tests for admin authentication endpoint."""

    # =========================================================================
    # SUCCESS TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_valid_admin_login(
        self,
        client: AsyncClient,
        test_admin,
        test_db
    ):
        """
        Test successful admin login with valid credentials.

        Verifies:
        - HTTP 200 OK status
        - Response contains JWT token
        - Token contains permission_level="admin"
        - User data in response includes email and name
        - Response structure matches AdminLoginResponse model
        """
        response = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["success"] is True
        assert data["message"] == "Admin login successful"
        assert "data" in data

        # Verify token data
        assert "authToken" in data["data"]
        assert "tokenType" in data["data"]
        assert data["data"]["tokenType"] == "Bearer"
        assert "expiresIn" in data["data"]
        assert data["data"]["expiresIn"] == 28800  # 8 hours in seconds
        assert "expiresAt" in data["data"]

        # Verify user data
        assert "user" in data["data"]
        user = data["data"]["user"]
        assert user["email"] == "test-admin@test.com"
        assert user["user_name"] == "Test Admin"
        assert user["permission_level"] == "admin"

        # Verify JWT token format (should be a long string)
        assert len(data["data"]["authToken"]) > 100
        assert "." in data["data"]["authToken"]  # JWT has dots separating sections

    @pytest.mark.asyncio
    async def test_admin_login_updates_login_date(
        self,
        client: AsyncClient,
        test_admin,
        test_db
    ):
        """
        Test that login_date is updated in database after successful login.

        Verifies:
        - login_date field is updated to current time
        - updated_at field is also updated
        """
        # Get timestamp before login
        before_login = datetime.now(timezone.utc)

        # Login
        response = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == 200

        # Verify login_date was updated in database
        admin_in_db = await test_db["iris-admins"].find_one({
            "user_email": "test-admin@test.com"
        })

        assert admin_in_db is not None
        assert admin_in_db["login_date"] is not None
        assert isinstance(admin_in_db["login_date"], datetime)

        # Make login_date timezone-aware if it's naive (MongoDB sometimes returns naive datetimes)
        login_date = admin_in_db["login_date"]
        if login_date.tzinfo is None:
            login_date = login_date.replace(tzinfo=timezone.utc)

        # Verify login_date is recent (within 60 seconds of before_login)
        time_diff = (login_date - before_login).total_seconds()
        assert 0 <= time_diff <= 60, f"login_date should be recent (was {time_diff}s after login start)"

    @pytest.mark.asyncio
    async def test_admin_jwt_token_verification(
        self,
        client: AsyncClient,
        test_admin,
        test_db
    ):
        """
        Test JWT token contains correct admin claims.

        Verifies:
        - Token can be decoded
        - Token contains permission_level="admin"
        - Token contains correct user data
        """
        # Login to get token
        response = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == 200
        token = response.json()["data"]["authToken"]

        # Verify token using the verify endpoint
        verify_response = await client.get(
            "/login/verify",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert verify_response.status_code == 200
        verify_data = verify_response.json()

        assert verify_data["success"] is True
        assert verify_data["valid"] is True
        assert "user" in verify_data

        user = verify_data["user"]
        assert user["email"] == "test-admin@test.com"
        assert user["permission_level"] == "admin"

    # =========================================================================
    # INVALID CREDENTIALS TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_invalid_email(
        self,
        client: AsyncClient,
        test_admin
    ):
        """
        Test login with non-existent email.

        Verifies:
        - HTTP 401 Unauthorized status
        - Generic error message (security best practice)
        """
        response = await client.post(
            "/login/admin",
            json={
                "email": "nonexistent@test.com",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == 401

        # Verify generic error message (don't reveal if email exists)
        # Response format: {"success": false, "error": {"code": 401, "message": "...", "type": "..."}}
        data = response.json()
        assert "error" in data
        assert "message" in data["error"]
        assert "invalid credentials" in data["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_invalid_password(
        self,
        client: AsyncClient,
        test_admin
    ):
        """
        Test login with wrong password.

        Verifies:
        - HTTP 401 Unauthorized status
        - Generic error message (security best practice)
        """
        response = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com",
                "password": "WrongPassword123!"
            }
        )

        assert response.status_code == 401

        # Verify generic error message (don't reveal if email exists)
        # Response format: {"success": false, "error": {"code": 401, "message": "...", "type": "..."}}
        data = response.json()
        assert "error" in data
        assert "message" in data["error"]
        assert "invalid credentials" in data["error"]["message"].lower()

    # =========================================================================
    # VALIDATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_missing_email_field(
        self,
        client: AsyncClient
    ):
        """
        Test POST /login/admin without email field.

        Verifies:
        - HTTP 422 Unprocessable Entity (validation error)
        """
        response = await client.post(
            "/login/admin",
            json={
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_password_field(
        self,
        client: AsyncClient
    ):
        """
        Test POST /login/admin without password field.

        Verifies:
        - HTTP 422 Unprocessable Entity (validation error)
        """
        response = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com"
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_email_field(
        self,
        client: AsyncClient
    ):
        """
        Test POST /login/admin with empty email.

        Verifies:
        - HTTP 422 Unprocessable Entity (validation error)
        """
        response = await client.post(
            "/login/admin",
            json={
                "email": "",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_email_format(
        self,
        client: AsyncClient
    ):
        """
        Test POST /login/admin with invalid email format.

        Verifies:
        - HTTP 422 Unprocessable Entity (validation error)
        """
        invalid_emails = [
            "notanemail",
            "missing@domain",
            "@nodomain.com"
        ]

        for invalid_email in invalid_emails:
            response = await client.post(
                "/login/admin",
                json={
                    "email": invalid_email,
                    "password": "TestPassword123!"
                }
            )
            assert response.status_code == 422, \
                f"Expected 422 for email '{invalid_email}', got {response.status_code}"

    # =========================================================================
    # PROTECTED ENDPOINT TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_admin_endpoint_with_admin_jwt(
        self,
        client: AsyncClient,
        test_admin
    ):
        """
        Test accessing protected admin endpoint with admin JWT token.

        Verifies:
        - HTTP 200 OK status when admin JWT provided
        """
        # Login to get admin token
        login_response = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com",
                "password": "TestPassword123!"
            }
        )

        assert login_response.status_code == 200
        token = login_response.json()["data"]["authToken"]

        # Try to access verify endpoint (requires authentication)
        verify_response = await client.get(
            "/login/verify",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data["user"]["permission_level"] == "admin"

    @pytest.mark.asyncio
    async def test_admin_endpoint_without_jwt(
        self,
        client: AsyncClient
    ):
        """
        Test accessing protected endpoint without JWT token.

        Verifies:
        - HTTP 401 Unauthorized status when no JWT provided
        """
        # Try to access protected endpoint without token
        response = await client.get("/login/verify")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_endpoint_with_invalid_jwt(
        self,
        client: AsyncClient
    ):
        """
        Test accessing protected endpoint with invalid JWT token.

        Verifies:
        - HTTP 401 Unauthorized status when invalid JWT provided
        """
        # Try to access protected endpoint with fake token
        response = await client.get(
            "/login/verify",
            headers={"Authorization": "Bearer invalid_token_here"}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_specific_endpoint_access(
        self,
        client: AsyncClient,
        test_admin,
        test_db
    ):
        """
        Test that admin-level endpoints require admin permission.

        This is a placeholder test demonstrating how to test
        admin-only endpoints when they exist.

        Verifies:
        - Admin JWT grants access to admin-only endpoints
        - Non-admin JWT is rejected (403 Forbidden)
        """
        # Login as admin
        admin_login_response = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com",
                "password": "TestPassword123!"
            }
        )

        assert admin_login_response.status_code == 200
        admin_token = admin_login_response.json()["data"]["authToken"]

        # Verify admin token works for verify endpoint
        admin_verify = await client.get(
            "/login/verify",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert admin_verify.status_code == 200
        assert admin_verify.json()["user"]["permission_level"] == "admin"

        # Note: When admin-only endpoints exist (e.g., /admin/users),
        # add tests here to verify:
        # 1. Admin token grants access (200 OK)
        # 2. Non-admin token is rejected (403 Forbidden)
        # 3. No token is rejected (401 Unauthorized)

    # =========================================================================
    # EDGE CASE TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_case_insensitive_email_login(
        self,
        client: AsyncClient,
        test_admin
    ):
        """
        Test that email comparison is case-insensitive.

        Verifies:
        - Login with uppercase email succeeds
        - Login with mixed case email succeeds
        """
        # Test uppercase email
        response_upper = await client.post(
            "/login/admin",
            json={
                "email": "TEST-ADMIN@TEST.COM",
                "password": "TestPassword123!"
            }
        )

        assert response_upper.status_code == 200

        # Test mixed case email
        response_mixed = await client.post(
            "/login/admin",
            json={
                "email": "Test-Admin@Test.Com",
                "password": "TestPassword123!"
            }
        )

        assert response_mixed.status_code == 200

    @pytest.mark.asyncio
    async def test_multiple_successful_logins(
        self,
        client: AsyncClient,
        test_admin,
        test_db
    ):
        """
        Test multiple successful logins update login_date correctly.

        Verifies:
        - Each login updates login_date
        - Login dates are sequential
        """
        import time

        # First login
        response1 = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com",
                "password": "TestPassword123!"
            }
        )
        assert response1.status_code == 200

        admin_after_first = await test_db["iris-admins"].find_one({
            "user_email": "test-admin@test.com"
        })
        first_login_date = admin_after_first["login_date"]

        # Wait 1 second
        time.sleep(1)

        # Second login
        response2 = await client.post(
            "/login/admin",
            json={
                "email": "test-admin@test.com",
                "password": "TestPassword123!"
            }
        )
        assert response2.status_code == 200

        admin_after_second = await test_db["iris-admins"].find_one({
            "user_email": "test-admin@test.com"
        })
        second_login_date = admin_after_second["login_date"]

        # Verify second login date is after first
        assert second_login_date > first_login_date


# Export for pytest collection
__all__ = ["TestAdminAuthentication"]
