"""
BASIC API INTEGRATION TESTS - Real HTTP requests to running server

PURPOSE: Test basic CRUD operations via HTTP API without authentication.

All tests output human-readable logs with:
- Test PURPOSE (what is being verified)
- API requests being made (visible in server logs)
- Response details and verification results
"""

import pytest
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from tests.test_logger import TestLogger, get_test_headers

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_PREFIX = "TEST_BASIC_"


@pytest.fixture(scope="function")
async def db(test_db):
    """Use test database from conftest.py fixture."""
    yield test_db


@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for API calls."""
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="function", autouse=True)
async def cleanup(db):
    """Clean test data before and after each test."""
    # Before
    await db.subscriptions.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}", "$options": "i"}})
    await db.company_users.delete_many({"email": {"$regex": f"^{TEST_PREFIX}", "$options": "i"}})
    await db.companies.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}", "$options": "i"}})
    await db.company.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}", "$options": "i"}})

    yield

    # After
    await db.subscriptions.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}", "$options": "i"}})
    await db.company_users.delete_many({"email": {"$regex": f"^{TEST_PREFIX}", "$options": "i"}})
    await db.companies.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}", "$options": "i"}})
    await db.company.delete_many({"company_name": {"$regex": f"^{TEST_PREFIX}", "$options": "i"}})


@pytest.mark.asyncio
class TestCompanyAPI:
    """Test Company API endpoints."""

    async def test_get_companies(self, http_client, db, test_logger, test_headers):
        """Test GET /api/v1/companies returns companies list."""
        test_logger.start("Verify GET /api/v1/companies returns list of all companies")

        # Create test company in database
        test_logger.step("Create test company in database")
        company_doc = {
            "company_name": f"{TEST_PREFIX}TestCorp",
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        }
        await db.companies.insert_one(company_doc)
        test_logger.info(f"Created test company: {TEST_PREFIX}TestCorp")

        # Call API
        test_logger.step("Call GET /api/v1/companies endpoint")
        test_logger.request("GET", "/api/v1/companies", headers=test_headers)
        response = await http_client.get("/api/v1/companies", headers=test_headers)
        data = response.json()

        # API returns {success: True, data: {companies: [...], count: N}}
        test_logger.response(response.status_code, {"success": data.get("success"), "count": data.get("data", {}).get("count", "N/A")})

        test_logger.assert_check("Status code is 200", response.status_code == 200, response.status_code, 200)
        test_logger.assert_check("Response has success field", data.get("success") is True, data.get("success"), True)
        test_logger.assert_check("Response has data.companies list", isinstance(data.get("data", {}).get("companies"), list), type(data.get("data", {}).get("companies")).__name__, "list")

        assert response.status_code == 200
        assert data.get("success") is True
        companies = data.get("data", {}).get("companies", [])
        assert isinstance(companies, list)

        test_logger.passed(f"GET /api/v1/companies returned {len(companies)} companies")


@pytest.mark.asyncio
class TestCompanyUserAPI:
    """Test Company User API endpoints."""

    async def test_create_company_user(self, http_client, db, test_logger, test_headers):
        """Test POST /api/company-users creates a user."""
        test_logger.start("Verify POST /api/company-users creates a new user for a company")

        company_name = f"{TEST_PREFIX}TestCorp"

        # Create company in BOTH collections
        test_logger.step("Create test company in database collections")
        company_doc = {
            "company_name": company_name,
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        }
        await db.company.insert_one(company_doc.copy())
        await db.companies.insert_one(company_doc.copy())
        test_logger.info(f"Created company: {company_name}")

        # Verify company exists in database before API call
        verify = await db.company.find_one({"company_name": company_name})
        test_logger.assert_check("Company exists in 'company' collection", verify is not None, verify is not None, True)
        assert verify is not None, "Company not found in 'company' collection after insert"

        # Create user via API
        test_logger.step("Create user via POST /api/company-users endpoint")
        user_data = {
            "user_name": "Test User",
            "email": f"{TEST_PREFIX}user@test.com",
            "phone_number": "+1234567890",
            "password": "TestPass123",
            "permission_level": "user",
            "status": "active"
        }

        test_logger.request("POST", f"/api/company-users?company_name={company_name}", user_data, test_headers)
        response = await http_client.post(
            f"/api/company-users?company_name={company_name}",
            json=user_data,
            headers=test_headers
        )

        if response.status_code in [200, 201]:
            test_logger.response(response.status_code, response.json())
        else:
            test_logger.response(response.status_code, {"error": response.text})

        test_logger.assert_check("Status code is 200 or 201", response.status_code in [200, 201], response.status_code, "200 or 201")

        assert response.status_code in [200, 201]

        test_logger.passed(f"User '{user_data['user_name']}' created successfully for company '{company_name}'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
