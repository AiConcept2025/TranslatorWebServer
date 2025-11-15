"""
BASIC API INTEGRATION TESTS - Real HTTP requests to running server

Tests basic CRUD operations via HTTP API without authentication.
"""

import pytest
import httpx
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta

# Configuration
API_BASE_URL = "http://localhost:8000"
# Use same database as running API server (not translation_test)
MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
DATABASE_NAME = "translation"
TEST_PREFIX = "TEST_BASIC_"

@pytest.fixture(scope="function")
async def db():
    """Connect to test database."""
    client = AsyncIOMotorClient(MONGODB_URI)
    database = client[DATABASE_NAME]
    yield database
    client.close()

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
    
    async def test_get_companies(self, http_client, db):
        """Test GET /api/v1/companies returns companies list."""
        
        print("\n✅ TEST: GET all companies")
        
        # Create test company in database
        await db.companies.insert_one({
            "company_name": f"{TEST_PREFIX}TestCorp",
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        })
        
        # Call API
        response = await http_client.get("/api/v1/companies")
        
        print(f"📤 GET /api/v1/companies")
        print(f"📥 Status: {response.status_code}")
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"✅ API returned companies successfully")
        print(f"📊 Response contains {len(data)} companies")

@pytest.mark.asyncio  
class TestCompanyUserAPI:
    """Test Company User API endpoints."""
    
    async def test_create_company_user(self, http_client, db):
        """Test POST /api/company-users creates a user."""
        
        print("\n✅ TEST: Create company user")
        
        company_name = f"{TEST_PREFIX}TestCorp"
        
        # Create company in BOTH collections
        company_doc = {
            "company_name": company_name,
            "status": "active",
            "created_at": datetime.now(timezone.utc)
        }
        await db.company.insert_one(company_doc.copy())
        await db.companies.insert_one(company_doc.copy())
        print(f"✅ Created company: {company_name}")

        # Verify company exists in database before API call
        verify = await db.company.find_one({"company_name": company_name})
        assert verify is not None, f"Company not found in 'company' collection after insert"
        print(f"✅ Verified company exists in 'company' collection")

        # Create user via API
        user_data = {
            "user_name": "Test User",
            "email": f"{TEST_PREFIX}user@test.com",
            "phone_number": "+1234567890",
            "password": "TestPass123",
            "permission_level": "user",
            "status": "active"
        }
        
        response = await http_client.post(
            f"/api/company-users?company_name={company_name}",
            json=user_data
        )
        
        print(f"📤 POST /api/company-users?company_name={company_name}")
        print(f"📥 Status: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            print(f"❌ Error: {response.text}")
        
        assert response.status_code in [200, 201]
        print(f"✅ User created successfully via API")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
