#!/usr/bin/env python3
"""
Test suite for collection separation between enterprise and individual users.
Verifies that:
1. Enterprise auth does NOT query users collection
2. Individual auth does NOT query company_users collection
3. Field names are consistent (company_id, not customer_id)
4. No cross-collection contamination
Uses REAL database with actual Iris Trading data.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

# Import the auth service
from app.services.auth_service import auth_service
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


@pytest_asyncio.fixture
async def test_individual_user(real_database):
    """Create and cleanup test individual user."""
    test_email = "test_separation@example.com"
    test_name = "Test Separation User"

    # Cleanup before test
    await real_database.users.delete_one({"email": test_email})

    yield {"email": test_email, "user_name": test_name}

    # Cleanup after test
    await real_database.users.delete_one({"email": test_email})


class TestCollectionSeparation:
    """Test suite for collection separation verification using REAL database."""

    @pytest.mark.asyncio
    async def test_enterprise_auth_does_not_query_users(self, real_database, iris_trading_credentials):
        """Test enterprise authentication does NOT query or update users collection."""
        creds = iris_trading_credentials

        # Get count of records in users collection before
        users_count_before = await real_database.users.count_documents({})

        # Check if Iris Trading email exists in users (should NOT after our fixes)
        user_in_users_before = await real_database.users.find_one({
            "email": creds["email"]
        })

        # Authenticate as enterprise user
        result = await auth_service.authenticate_user(
            company_name=creds["company_name"],
            email=creds["email"],
            user_name=creds["user_name"],
            password=creds["password"]
        )

        assert result is not None

        # Verify users collection count unchanged
        users_count_after = await real_database.users.count_documents({})
        assert users_count_after == users_count_before, "Users collection should not be modified"

        # Verify the specific email still has same state in users collection
        user_in_users_after = await real_database.users.find_one({
            "email": creds["email"]
        })
        assert user_in_users_after == user_in_users_before, "Users collection should not be touched"

        # Verify user exists in company_users (enterprise collection)
        user_in_company_users = await real_database.company_users.find_one({
            "email": creds["email"],
            "user_name": creds["user_name"]
        })
        assert user_in_company_users is not None, "Enterprise user must exist in company_users"

    @pytest.mark.asyncio
    async def test_individual_auth_does_not_query_company_users(self, real_database, test_individual_user):
        """Test individual authentication does NOT query or update company_users collection."""
        email = test_individual_user["email"]
        user_name = test_individual_user["user_name"]

        # Get count of records in company_users before
        company_users_count_before = await real_database.company_users.count_documents({})

        # Authenticate as individual user
        result = await auth_service.authenticate_individual_user(
            email=email,
            user_name=user_name
        )

        assert result is not None

        # Verify company_users collection count unchanged
        company_users_count_after = await real_database.company_users.count_documents({})
        assert company_users_count_after == company_users_count_before, "Company_users should not be modified"

        # Verify the email does NOT exist in company_users
        user_in_company_users = await real_database.company_users.find_one({
            "email": email
        })
        assert user_in_company_users is None, "Individual user should NOT be in company_users"

        # Verify user exists in users collection with company_id=None
        user_in_users = await real_database.users.find_one({
            "email": email,
            "company_id": None
        })
        assert user_in_users is not None, "Individual user must exist in users with company_id=None"

    @pytest.mark.asyncio
    async def test_field_name_consistency_company_id(self, real_database, iris_trading_credentials):
        """Test that company_id is used consistently (not customer_id) in company_users."""
        creds = iris_trading_credentials

        # Get enterprise user from company_users
        user = await real_database.company_users.find_one({
            "email": creds["email"],
            "user_name": creds["user_name"]
        })

        assert user is not None, "Enterprise user must exist"

        # Verify 'company_id' field exists
        assert "company_id" in user, "Field 'company_id' must exist"
        assert user["company_id"] is not None, "company_id must have a value"

        # Verify 'customer_id' field does NOT exist (old incorrect naming)
        assert "customer_id" not in user, "Field 'customer_id' should NOT exist (deprecated)"

    @pytest.mark.asyncio
    async def test_no_cross_collection_contamination(self, real_database, iris_trading_credentials, test_individual_user):
        """Test that enterprise and individual data stay in separate collections."""
        enterprise_creds = iris_trading_credentials
        individual_user = test_individual_user

        # Test 1: Authenticate as enterprise user
        result_enterprise = await auth_service.authenticate_user(
            company_name=enterprise_creds["company_name"],
            email=enterprise_creds["email"],
            user_name=enterprise_creds["user_name"],
            password=enterprise_creds["password"]
        )

        # Verify enterprise user is ONLY in company_users
        user_in_company_users = await real_database.company_users.find_one({
            "email": enterprise_creds["email"]
        })
        assert user_in_company_users is not None, "Enterprise user must be in company_users"
        assert user_in_company_users["company_id"] is not None, "Enterprise user must have company_id"

        # Test 2: Authenticate as individual user
        result_individual = await auth_service.authenticate_individual_user(
            email=individual_user["email"],
            user_name=individual_user["user_name"]
        )

        # Verify individual user is ONLY in users with company_id=None
        user_in_users = await real_database.users.find_one({
            "email": individual_user["email"]
        })
        assert user_in_users is not None, "Individual user must be in users"
        assert user_in_users["company_id"] is None, "Individual user must have company_id=None"

        # Verify individual user is NOT in company_users
        individual_in_company_users = await real_database.company_users.find_one({
            "email": individual_user["email"]
        })
        assert individual_in_company_users is None, "Individual user should NOT be in company_users"

        # Verify response data is correct for each type
        assert result_enterprise["user_data"]["company"] == "Iris Trading"
        assert result_individual["user_data"]["company_name"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
