#!/usr/bin/env python3
"""
Test suite for enterprise (corporate) authentication.
Verifies that enterprise users authenticate against company_users collection ONLY.
Uses REAL database with actual Iris Trading company data.
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
async def iris_trading_credentials():
    """Return real Iris Trading company credentials."""
    return {
        "company_name": "Iris Trading",
        "email": "danishevsky@gmail.com",
        "user_name": "Vladimir Danishevsky",
        "password": "Sveta87201120!"
    }


class TestEnterpriseAuthentication:
    """Test suite for enterprise user authentication using REAL database."""

    @pytest.mark.asyncio
    async def test_successful_enterprise_login(self, real_database, iris_trading_credentials):
        """Test successful login with valid Iris Trading enterprise credentials."""
        creds = iris_trading_credentials

        # Get last_login before authentication
        user_before = await real_database.company_users.find_one({
            "email": creds["email"],
            "user_name": creds["user_name"]
        })
        assert user_before is not None, "Iris Trading user must exist in company_users"
        last_login_before = user_before.get("last_login")

        # Authenticate
        result = await auth_service.authenticate_user(
            company_name=creds["company_name"],
            email=creds["email"],
            user_name=creds["user_name"],
            password=creds["password"]
        )

        # Verify result
        assert result is not None
        assert "access_token" in result
        assert result["user_data"]["email"] == creds["email"]
        assert result["user_data"]["company"] == "Iris Trading"

        # Verify last_login was updated in company_users
        user_after = await real_database.company_users.find_one({
            "email": creds["email"],
            "user_name": creds["user_name"]
        })
        assert user_after["last_login"] > last_login_before or user_after["last_login"] != last_login_before

    @pytest.mark.asyncio
    async def test_login_failure_invalid_company(self, iris_trading_credentials):
        """Test login failure with invalid company name."""
        creds = iris_trading_credentials

        with pytest.raises(AuthenticationError, match="Company not found"):
            await auth_service.authenticate_user(
                company_name="NonExistent Company",
                email=creds["email"],
                user_name=creds["user_name"],
                password=creds["password"]
            )

    @pytest.mark.asyncio
    async def test_login_failure_invalid_password(self, iris_trading_credentials):
        """Test login failure with invalid password."""
        creds = iris_trading_credentials

        with pytest.raises(AuthenticationError, match="Invalid password"):
            await auth_service.authenticate_user(
                company_name=creds["company_name"],
                email=creds["email"],
                user_name=creds["user_name"],
                password="WrongPassword123"
            )

    @pytest.mark.asyncio
    async def test_jwt_verification_no_database_access(self, iris_trading_credentials):
        """Test JWT verification does NOT require database access (stateless)."""
        # Create JWT token with Iris Trading data
        token_data = {
            "user_id": "user_iris_test",
            "email": iris_trading_credentials["email"],
            "fullName": iris_trading_credentials["user_name"],
            "company": "Iris Trading",
            "permission_level": "admin"
        }

        token = jwt_service.create_access_token(token_data, timedelta(hours=8))

        # Verify token WITHOUT database (stateless JWT)
        decoded = jwt_service.verify_token(token)

        assert decoded is not None
        assert decoded["email"] == iris_trading_credentials["email"]
        assert decoded["fullName"] == iris_trading_credentials["user_name"]

    @pytest.mark.asyncio
    async def test_login_updates_company_users_only(self, real_database, iris_trading_credentials):
        """Test login updates company_users collection ONLY, not users collection."""
        creds = iris_trading_credentials

        # Check if user exists in users collection (should NOT for enterprise)
        user_in_users_before = await real_database.users.find_one({
            "email": creds["email"]
        })

        # Authenticate
        await auth_service.authenticate_user(
            company_name=creds["company_name"],
            email=creds["email"],
            user_name=creds["user_name"],
            password=creds["password"]
        )

        # Verify user in company_users was updated
        user_in_company_users = await real_database.company_users.find_one({
            "email": creds["email"],
            "user_name": creds["user_name"]
        })
        assert user_in_company_users is not None
        assert user_in_company_users["last_login"] is not None

        # Verify users collection was NOT touched (should still be same state)
        user_in_users_after = await real_database.users.find_one({
            "email": creds["email"]
        })
        assert user_in_users_after == user_in_users_before  # No change

    @pytest.mark.asyncio
    async def test_jwt_contains_correct_enterprise_data(self, iris_trading_credentials):
        """Test JWT contains correct enterprise user data."""
        creds = iris_trading_credentials

        result = await auth_service.authenticate_user(
            company_name=creds["company_name"],
            email=creds["email"],
            user_name=creds["user_name"],
            password=creds["password"]
        )

        # Decode JWT
        token = result["access_token"]
        decoded = jwt_service.verify_token(token)

        # Verify JWT payload
        assert decoded["email"] == creds["email"]
        assert decoded["fullName"] == creds["user_name"]

    @pytest.mark.asyncio
    async def test_expired_jwt_rejection(self):
        """Test expired JWT is rejected."""
        # Create expired token
        token_data = {
            "user_id": "user_123",
            "email": "test@example.com",
            "fullName": "Test User",
            "company": "Test Company",
            "permission_level": "user"
        }

        # Create token that expires immediately
        expired_token = jwt_service.create_access_token(token_data, timedelta(seconds=-1))

        # Verify token is rejected
        decoded = jwt_service.verify_token(expired_token)
        assert decoded is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
