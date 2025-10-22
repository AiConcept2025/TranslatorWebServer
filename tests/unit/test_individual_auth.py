#!/usr/bin/env python3
"""
Test suite for individual user authentication.
Verifies that individual users authenticate against users collection ONLY with company_id=None.
Uses REAL database with auto-creation and cleanup.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

# Import the auth service
from app.services.auth_service import auth_service, AuthenticationError
from app.services.jwt_service import jwt_service
from app.config import settings


@pytest_asyncio.fixture(scope="module", autouse=True)
async def init_database():
    """Initialize global database connection for auth_service."""
    from app.database.mongodb import database
    await database.connect()
    yield
    await database.disconnect()


@pytest_asyncio.fixture
async def real_database():
    """Connect to real MongoDB database for test queries."""
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    yield db

    client.close()


@pytest_asyncio.fixture
async def test_individual_user(real_database):
    """Create and cleanup test individual user."""
    test_email = "test_individual_user@example.com"
    test_name = "Test Individual User"

    # Cleanup before test (if exists from previous run)
    await real_database.users.delete_one({"email": test_email})

    yield {"email": test_email, "user_name": test_name}

    # Cleanup after test
    await real_database.users.delete_one({"email": test_email})


class TestIndividualAuthentication:
    """Test suite for individual user authentication using REAL database."""

    @pytest.mark.asyncio
    async def test_successful_login_new_user(self, real_database, test_individual_user):
        """Test successful login for new individual user (auto-creation)."""
        email = test_individual_user["email"]
        user_name = test_individual_user["user_name"]

        # Verify user does not exist yet
        user_before = await real_database.users.find_one({
            "email": email,
            "company_id": None
        })
        assert user_before is None, "User should not exist before first login"

        # Authenticate (should auto-create user)
        result = await auth_service.authenticate_individual_user(
            email=email,
            user_name=user_name
        )

        # Verify result
        assert result is not None
        assert "access_token" in result
        assert result["user_data"]["email"] == email
        assert result["user_data"]["user_name"] == user_name
        assert result["user_data"]["company_name"] is None

        # Verify user was created in users collection
        user_after = await real_database.users.find_one({
            "email": email,
            "company_id": None
        })
        assert user_after is not None
        assert user_after["email"] == email
        assert user_after["company_id"] is None
        assert user_after["permission_level"] == "user"
        assert user_after["status"] == "active"

    @pytest.mark.asyncio
    async def test_successful_login_existing_user(self, real_database, test_individual_user):
        """Test successful login for existing individual user."""
        email = test_individual_user["email"]
        user_name = test_individual_user["user_name"]

        # First login (creates user)
        await auth_service.authenticate_individual_user(email=email, user_name=user_name)

        # Get user after first login
        user_before = await real_database.users.find_one({
            "email": email,
            "company_id": None
        })
        last_login_before = user_before["last_login"]

        # Second login (existing user)
        result = await auth_service.authenticate_individual_user(
            email=email,
            user_name=user_name
        )

        # Verify result
        assert result is not None
        assert "access_token" in result
        assert result["user_data"]["email"] == email

        # Verify last_login was updated
        user_after = await real_database.users.find_one({
            "email": email,
            "company_id": None
        })
        assert user_after["last_login"] >= last_login_before

    @pytest.mark.asyncio
    async def test_auto_creation_on_first_login(self, real_database, test_individual_user):
        """Test user record is auto-created on first login."""
        email = test_individual_user["email"]
        user_name = test_individual_user["user_name"]

        # Authenticate (auto-creates)
        result = await auth_service.authenticate_individual_user(
            email=email,
            user_name=user_name
        )

        # Verify user was created with correct fields
        created_user = await real_database.users.find_one({
            "email": email,
            "company_id": None
        })
        assert created_user is not None
        assert created_user["email"] == email
        assert created_user["user_name"] == user_name
        assert created_user["company_id"] is None
        assert created_user["permission_level"] == "user"
        assert created_user["status"] == "active"
        assert created_user["created_at"] is not None
        assert created_user["last_login"] is not None

    @pytest.mark.asyncio
    async def test_jwt_verification_without_database(self, test_individual_user):
        """Test JWT verification does NOT require database access (stateless)."""
        email = test_individual_user["email"]
        user_name = test_individual_user["user_name"]

        # Create JWT token
        token_data = {
            "user_id": "user_test_123",
            "email": email,
            "fullName": user_name,
            "company": None,  # Individual users have no company
            "permission_level": "user"
        }

        token = jwt_service.create_access_token(token_data, timedelta(hours=8))

        # Verify token WITHOUT database access (stateless JWT)
        decoded = jwt_service.verify_token(token)

        assert decoded is not None
        assert decoded["email"] == email
        assert decoded["fullName"] == user_name
        assert decoded["company"] is None
        assert decoded["permission_level"] == "user"

    @pytest.mark.asyncio
    async def test_login_updates_users_only(self, real_database, test_individual_user):
        """Test login updates users collection ONLY, not company_users."""
        email = test_individual_user["email"]
        user_name = test_individual_user["user_name"]

        # Check company_users before (should not have this user)
        company_user_before = await real_database.company_users.find_one({
            "email": email
        })

        # Authenticate
        await auth_service.authenticate_individual_user(
            email=email,
            user_name=user_name
        )

        # Verify user exists in users collection
        user_in_users = await real_database.users.find_one({
            "email": email,
            "company_id": None
        })
        assert user_in_users is not None
        assert user_in_users["last_login"] is not None

        # Verify company_users was NOT touched
        company_user_after = await real_database.company_users.find_one({
            "email": email
        })
        assert company_user_after == company_user_before  # No change (likely both None)

    @pytest.mark.asyncio
    async def test_jwt_contains_correct_individual_data(self, test_individual_user):
        """Test JWT contains correct individual user data."""
        email = test_individual_user["email"]
        user_name = test_individual_user["user_name"]

        result = await auth_service.authenticate_individual_user(
            email=email,
            user_name=user_name
        )

        # Decode JWT
        token = result["access_token"]
        decoded = jwt_service.verify_token(token)

        # Verify JWT payload
        assert decoded["email"] == email
        assert decoded["fullName"] == user_name
        assert decoded.get("company") is None  # No company for individual users
        assert decoded["permission_level"] == "user"

    @pytest.mark.asyncio
    async def test_expired_jwt_rejection(self):
        """Test expired JWT is rejected."""
        # Create expired token
        token_data = {
            "user_id": "user_456",
            "email": "individual@example.com",
            "fullName": "Test User",
            "company": None,
            "permission_level": "user"
        }

        # Create token that expires immediately
        expired_token = jwt_service.create_access_token(token_data, timedelta(seconds=-1))

        # Verify token is rejected
        decoded = jwt_service.verify_token(expired_token)
        assert decoded is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
