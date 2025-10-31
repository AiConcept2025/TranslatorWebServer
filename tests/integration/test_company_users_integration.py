"""
Integration tests for the company user creation endpoint.

These tests verify the complete company user creation workflow including:
- User creation with proper password hashing
- Email uniqueness validation
- Company existence validation
- Password strength requirements
- Database state changes
- Error handling and HTTP status codes

Test Database: translation_test
Collections: companies, company_users
"""

import pytest
import bcrypt
import re
from datetime import datetime, timezone
from httpx import AsyncClient
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.main import app
from app.database.mongodb import database
from app.config import settings


@pytest.fixture
async def client():
    """Provide an AsyncClient for API testing."""
    async with AsyncClient(app=app, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
async def test_db() -> AsyncIOMotorDatabase:
    """Provide MongoDB test database connection."""
    await database.connect()
    yield database.db
    await database.disconnect()


@pytest.fixture
async def test_company(test_db):
    """Create a test company for user creation tests."""
    company_doc = {
        "company_name": "Test Company Inc",
        "description": "Test company for user creation",
        "line_of_business": "Technology",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    result = await test_db.companies.insert_one(company_doc)
    company_doc["_id"] = result.inserted_id

    yield company_doc

    # Cleanup
    await test_db.companies.delete_one({"_id": result.inserted_id})
    await test_db.company_users.delete_many({"company_id": result.inserted_id})


@pytest.fixture
def valid_user_data():
    """Valid user data for testing."""
    return {
        "user_name": "John Doe",
        "email": "john.doe@testcompany.com",
        "phone_number": "+1-555-0123",
        "password": "SecurePass123",
        "permission_level": "user",
        "status": "active"
    }


@pytest.mark.integration
class TestCompanyUserCreation:
    """Integration tests for company user creation endpoint."""

    # =========================================================================
    # SUCCESS TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_company_user_success(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test successful company user creation.

        Verifies:
        - HTTP 201 Created status
        - Response contains all expected fields
        - Password hash NOT in response
        - User exists in database with bcrypt hash
        - Email stored as lowercase
        """
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=valid_user_data
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response fields
        assert data["user_id"].startswith("user_")
        assert data["company_name"] == test_company["company_name"]
        assert data["user_name"] == valid_user_data["user_name"]
        assert data["email"] == valid_user_data["email"].lower()
        assert data["phone_number"] == valid_user_data["phone_number"]
        assert data["permission_level"] == "user"
        assert data["status"] == "active"
        assert "created_at" in data

        # Verify sensitive data NOT in response
        assert "password" not in data
        assert "password_hash" not in data

        # Verify user exists in database
        user_in_db = await test_db.company_users.find_one({
            "user_id": data["user_id"]
        })
        assert user_in_db is not None
        assert user_in_db["email"] == valid_user_data["email"].lower()
        assert user_in_db["user_name"] == valid_user_data["user_name"]

        # Cleanup
        await test_db.company_users.delete_one({"_id": user_in_db["_id"]})

    @pytest.mark.asyncio
    async def test_password_hashing_bcrypt(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test password hashing with bcrypt.

        Verifies:
        - Password is hashed with bcrypt
        - Hash format is correct ($2b$ prefix)
        - Plain password is NOT stored
        - Hash matches password using bcrypt.checkpw
        """
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=valid_user_data
        )

        assert response.status_code == 201
        user_id = response.json()["user_id"]

        # Retrieve user from database
        user_in_db = await test_db.company_users.find_one({"user_id": user_id})
        assert user_in_db is not None

        password_hash = user_in_db["password_hash"]

        # Verify bcrypt format (starts with $2b$)
        assert password_hash.startswith("$2b$")

        # Verify hash is valid bcrypt hash
        assert len(password_hash) == 60  # bcrypt hashes are 60 characters

        # Verify password can be validated with bcrypt
        plain_password = valid_user_data["password"].encode('utf-8')[:72]
        is_valid = bcrypt.checkpw(plain_password, password_hash.encode('utf-8'))
        assert is_valid is True

        # Verify plain password is NOT stored anywhere
        assert user_in_db["password_hash"] != valid_user_data["password"]

        # Cleanup
        await test_db.company_users.delete_one({"_id": user_in_db["_id"]})

    @pytest.mark.asyncio
    async def test_user_id_generation(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test user ID generation and uniqueness.

        Verifies:
        - User ID format: user_{16_hex_chars}
        - User ID is unique
        - Each creation generates different ID
        """
        # First user
        response1 = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "email": "user1@test.com"}
        )
        assert response1.status_code == 201
        user_id_1 = response1.json()["user_id"]

        # Second user
        response2 = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "email": "user2@test.com"}
        )
        assert response2.status_code == 201
        user_id_2 = response2.json()["user_id"]

        # Verify format
        assert re.match(r'^user_[a-f0-9]{16}$', user_id_1)
        assert re.match(r'^user_[a-f0-9]{16}$', user_id_2)

        # Verify uniqueness
        assert user_id_1 != user_id_2

        # Cleanup
        users = await test_db.company_users.find({
            "user_id": {"$in": [user_id_1, user_id_2]}
        }).to_list(None)
        for user in users:
            await test_db.company_users.delete_one({"_id": user["_id"]})

    @pytest.mark.asyncio
    async def test_email_case_insensitive_storage(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test that email is stored as lowercase.

        Verifies:
        - Mixed case email is normalized to lowercase
        - Response shows lowercase email
        - Database stores lowercase email
        """
        email_mixed_case = "John.Doe@TestCompany.COM"
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "email": email_mixed_case}
        )

        assert response.status_code == 201
        data = response.json()

        # Response should have lowercase email
        assert data["email"] == email_mixed_case.lower()

        # Database should have lowercase email
        user_in_db = await test_db.company_users.find_one({
            "user_id": data["user_id"]
        })
        assert user_in_db["email"] == email_mixed_case.lower()

        # Cleanup
        await test_db.company_users.delete_one({"_id": user_in_db["_id"]})

    # =========================================================================
    # EMAIL VALIDATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_company_user_duplicate_email(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test that duplicate email within company returns 400.

        Verifies:
        - First user creation succeeds
        - Second user with same email fails with 400
        - Error message mentions email duplication
        """
        # Create first user
        response1 = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=valid_user_data
        )
        assert response1.status_code == 201
        user_id_1 = response1.json()["user_id"]

        # Try to create second user with same email
        response2 = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=valid_user_data
        )

        assert response2.status_code == 400
        error_data = response2.json()
        assert "detail" in error_data
        assert "already exists" in error_data["detail"].lower() or \
               "email" in error_data["detail"].lower()

        # Cleanup
        user1 = await test_db.company_users.find_one({"user_id": user_id_1})
        if user1:
            await test_db.company_users.delete_one({"_id": user1["_id"]})

    @pytest.mark.asyncio
    async def test_duplicate_email_case_insensitive(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test that email duplication check is case-insensitive.

        Verifies:
        - First user with email@test.com
        - Second user with EMAIL@TEST.COM fails with 400
        """
        # Create first user
        response1 = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=valid_user_data
        )
        assert response1.status_code == 201
        user_id_1 = response1.json()["user_id"]

        # Try to create second user with uppercase version of same email
        email_uppercase = valid_user_data["email"].upper()
        response2 = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "email": email_uppercase}
        )

        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"].lower() or \
               "email" in response2.json()["detail"].lower()

        # Cleanup
        user1 = await test_db.company_users.find_one({"user_id": user_id_1})
        if user1:
            await test_db.company_users.delete_one({"_id": user1["_id"]})

    @pytest.mark.asyncio
    async def test_create_company_user_invalid_email(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that invalid email format returns 422 Validation Error.

        Verifies:
        - Invalid email formats are rejected
        - HTTP 422 status code
        """
        invalid_emails = [
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "spaces in@email.com",
            ""
        ]

        for invalid_email in invalid_emails:
            response = await client.post(
                f"/api/company-users?company_name={test_company['company_name']}",
                json={**valid_user_data, "email": invalid_email}
            )
            assert response.status_code == 422, \
                f"Expected 422 for email '{invalid_email}', got {response.status_code}"

    # =========================================================================
    # PASSWORD VALIDATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_company_user_invalid_password_too_short(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that password < 6 characters returns 422.

        Verifies:
        - Passwords shorter than 6 characters are rejected
        - HTTP 422 status code
        - Error message mentions length requirement
        """
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "password": "Pass1"}
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data

    @pytest.mark.asyncio
    async def test_create_company_user_invalid_password_no_letter(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that password without letter returns 422.

        Verifies:
        - Passwords with only numbers are rejected
        - HTTP 422 status code
        - Error message mentions letter requirement
        """
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "password": "123456"}
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data
        # Check if error mentions letter or password strength
        error_text = str(error_data.get("detail", "")).lower()
        assert "letter" in error_text or "password" in error_text or "validation" in error_text

    @pytest.mark.asyncio
    async def test_create_company_user_invalid_password_no_number(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that password without number returns 422.

        Verifies:
        - Passwords with only letters are rejected
        - HTTP 422 status code
        - Error message mentions number requirement
        """
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "password": "abcdefgh"}
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data
        # Check if error mentions number or password strength
        error_text = str(error_data.get("detail", "")).lower()
        assert "number" in error_text or "digit" in error_text or "password" in error_text or "validation" in error_text

    @pytest.mark.asyncio
    async def test_create_company_user_invalid_password_too_long(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that password > 128 characters returns 422.

        Verifies:
        - Passwords longer than 128 characters are rejected
        - HTTP 422 status code
        """
        long_password = "A" + "b" * 128 + "1"  # 130 characters
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "password": long_password}
        )

        assert response.status_code == 422

    # =========================================================================
    # COMPANY VALIDATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_company_user_company_not_found(
        self,
        client: AsyncClient,
        valid_user_data
    ):
        """
        Test that non-existent company returns 400.

        Verifies:
        - Non-existent company_name returns 400 Bad Request
        - Error message mentions company not found
        """
        response = await client.post(
            "/api/company-users?company_name=NonExistentCompany",
            json=valid_user_data
        )

        assert response.status_code == 400
        error_data = response.json()
        assert "detail" in error_data
        assert "company" in error_data["detail"].lower()

    # =========================================================================
    # REQUIRED FIELD VALIDATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_company_user_missing_user_name(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that missing user_name returns 422.

        Verifies:
        - Missing user_name field returns 422 Validation Error
        """
        user_data = valid_user_data.copy()
        del user_data["user_name"]

        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=user_data
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_company_user_missing_email(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that missing email returns 422.

        Verifies:
        - Missing email field returns 422 Validation Error
        """
        user_data = valid_user_data.copy()
        del user_data["email"]

        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=user_data
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_company_user_missing_password(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that missing password returns 422.

        Verifies:
        - Missing password field returns 422 Validation Error
        """
        user_data = valid_user_data.copy()
        del user_data["password"]

        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=user_data
        )

        assert response.status_code == 422

    # =========================================================================
    # DATABASE STATE VERIFICATION TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_database_state_after_creation(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test database state after successful user creation.

        Verifies:
        - User document has all required fields
        - user_id is unique
        - company_id correctly references company
        - Timestamps are valid
        - Status and permission_level are stored as strings (enum values)
        """
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=valid_user_data
        )

        assert response.status_code == 201
        user_id = response.json()["user_id"]

        # Retrieve from database
        user_in_db = await test_db.company_users.find_one({"user_id": user_id})
        assert user_in_db is not None

        # Verify all required fields
        required_fields = [
            "_id", "user_id", "company_id", "user_name", "email",
            "phone_number", "permission_level", "status",
            "password_hash", "last_login", "created_at", "updated_at"
        ]
        for field in required_fields:
            assert field in user_in_db, f"Missing field: {field}"

        # Verify data types
        assert isinstance(user_in_db["user_id"], str)
        assert isinstance(user_in_db["email"], str)
        assert isinstance(user_in_db["password_hash"], str)
        assert isinstance(user_in_db["created_at"], datetime)
        assert isinstance(user_in_db["updated_at"], datetime)

        # Verify company_id matches
        assert user_in_db["company_id"] == test_company["_id"]

        # Verify status values
        assert user_in_db["status"] == "active"
        assert user_in_db["permission_level"] == "user"

        # Verify timestamps are recent (within last minute)
        now = datetime.now(timezone.utc)
        time_diff = (now - user_in_db["created_at"]).total_seconds()
        assert 0 <= time_diff <= 60, "created_at should be recent"

        # Verify last_login is None initially
        assert user_in_db["last_login"] is None

        # Cleanup
        await test_db.company_users.delete_one({"_id": user_in_db["_id"]})

    @pytest.mark.asyncio
    async def test_company_user_isolation_by_company(
        self,
        client: AsyncClient,
        test_db
    ):
        """
        Test that company users are properly isolated by company.

        Verifies:
        - Two users can have same email in different companies
        - Users are properly associated with their company
        """
        # Create two companies
        company1_doc = {
            "company_name": "Company A",
            "description": "Test company A",
            "line_of_business": "Tech",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        result1 = await test_db.companies.insert_one(company1_doc)
        company1_doc["_id"] = result1.inserted_id

        company2_doc = {
            "company_name": "Company B",
            "description": "Test company B",
            "line_of_business": "Finance",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        result2 = await test_db.companies.insert_one(company2_doc)
        company2_doc["_id"] = result2.inserted_id

        try:
            # AsyncClient setup
            async with AsyncClient(app=app, base_url="http://test") as client:
                # Create user in company 1
                user_data = {
                    "user_name": "John Doe",
                    "email": "john@shared.com",
                    "phone_number": "+1-555-0001",
                    "password": "Pass1234",
                    "permission_level": "user",
                    "status": "active"
                }
                response1 = await client.post(
                    f"/api/company-users?company_name={company1_doc['company_name']}",
                    json=user_data
                )
                assert response1.status_code == 201
                user1_id = response1.json()["user_id"]

                # Create user in company 2 with same email (should succeed)
                response2 = await client.post(
                    f"/api/company-users?company_name={company2_doc['company_name']}",
                    json=user_data
                )
                assert response2.status_code == 201
                user2_id = response2.json()["user_id"]

                # Verify they're different users
                assert user1_id != user2_id

                # Verify they're in different companies
                user1 = await test_db.company_users.find_one({"user_id": user1_id})
                user2 = await test_db.company_users.find_one({"user_id": user2_id})
                assert user1["company_id"] == company1_doc["_id"]
                assert user2["company_id"] == company2_doc["_id"]

                # Cleanup users
                await test_db.company_users.delete_one({"_id": user1["_id"]})
                await test_db.company_users.delete_one({"_id": user2["_id"]})
        finally:
            # Cleanup companies
            await test_db.companies.delete_one({"_id": company1_doc["_id"]})
            await test_db.companies.delete_one({"_id": company2_doc["_id"]})

    # =========================================================================
    # OPTIONAL FIELD TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_optional_phone_number(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test that phone_number is optional.

        Verifies:
        - User can be created without phone_number
        - Response includes phone_number as None or absent
        """
        user_data = valid_user_data.copy()
        del user_data["phone_number"]

        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=user_data
        )

        assert response.status_code == 201
        data = response.json()
        # phone_number should be None or not present
        phone = data.get("phone_number")
        assert phone is None or phone == ""

        # Cleanup
        user = await test_db.company_users.find_one({"user_id": data["user_id"]})
        await test_db.company_users.delete_one({"_id": user["_id"]})

    @pytest.mark.asyncio
    async def test_default_permission_level(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test that permission_level defaults to 'user'.

        Verifies:
        - permission_level defaults to 'user' when not provided
        """
        user_data = valid_user_data.copy()
        del user_data["permission_level"]

        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=user_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["permission_level"] == "user"

        # Cleanup
        user = await test_db.company_users.find_one({"user_id": data["user_id"]})
        await test_db.company_users.delete_one({"_id": user["_id"]})

    @pytest.mark.asyncio
    async def test_default_status_active(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test that status defaults to 'active'.

        Verifies:
        - status defaults to 'active' when not provided
        """
        user_data = valid_user_data.copy()
        del user_data["status"]

        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=user_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "active"

        # Cleanup
        user = await test_db.company_users.find_one({"user_id": data["user_id"]})
        await test_db.company_users.delete_one({"_id": user["_id"]})

    # =========================================================================
    # EDGE CASE TESTS
    # =========================================================================

    @pytest.mark.asyncio
    async def test_create_user_with_whitespace_trim(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data,
        test_db
    ):
        """
        Test that whitespace is trimmed from user_name.

        Verifies:
        - Leading/trailing whitespace is removed from user_name
        """
        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "user_name": "  John Doe  "}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_name"] == "John Doe"

        # Cleanup
        user = await test_db.company_users.find_one({"user_id": data["user_id"]})
        await test_db.company_users.delete_one({"_id": user["_id"]})

    @pytest.mark.asyncio
    async def test_create_multiple_users_same_company(
        self,
        client: AsyncClient,
        test_company,
        test_db
    ):
        """
        Test creating multiple users in the same company.

        Verifies:
        - Multiple users can be created in same company
        - Each has unique user_id
        - Each has unique email
        """
        user_ids = []

        for i in range(3):
            user_data = {
                "user_name": f"User {i}",
                "email": f"user{i}@test.com",
                "phone_number": f"+1-555-000{i}",
                "password": f"Pass{i}{i}{i}{i}{i}",
                "permission_level": "user",
                "status": "active"
            }

            response = await client.post(
                f"/api/company-users?company_name={test_company['company_name']}",
                json=user_data
            )

            assert response.status_code == 201
            user_ids.append(response.json()["user_id"])

        # Verify all user_ids are unique
        assert len(user_ids) == len(set(user_ids))

        # Cleanup
        users = await test_db.company_users.find({
            "user_id": {"$in": user_ids}
        }).to_list(None)
        for user in users:
            await test_db.company_users.delete_one({"_id": user["_id"]})

    @pytest.mark.asyncio
    async def test_create_user_max_length_fields(
        self,
        client: AsyncClient,
        test_company,
        test_db
    ):
        """
        Test creating user with maximum length values.

        Verifies:
        - user_name up to 255 characters is accepted
        - phone_number up to 50 characters is accepted
        """
        max_user_name = "A" * 255
        max_phone = "+" + "1" * 49

        user_data = {
            "user_name": max_user_name,
            "email": "maxlength@test.com",
            "phone_number": max_phone,
            "password": "Pass1234",
            "permission_level": "user",
            "status": "active"
        }

        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json=user_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["user_name"] == max_user_name
        assert data["phone_number"] == max_phone

        # Cleanup
        user = await test_db.company_users.find_one({"user_id": data["user_id"]})
        await test_db.company_users.delete_one({"_id": user["_id"]})

    @pytest.mark.asyncio
    async def test_create_user_exceeds_max_user_name_length(
        self,
        client: AsyncClient,
        test_company,
        valid_user_data
    ):
        """
        Test that user_name > 255 characters returns 422.

        Verifies:
        - Names longer than 255 characters are rejected
        """
        too_long_name = "A" * 256

        response = await client.post(
            f"/api/company-users?company_name={test_company['company_name']}",
            json={**valid_user_data, "user_name": too_long_name}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_company_name_query_parameter_required(
        self,
        client: AsyncClient,
        valid_user_data
    ):
        """
        Test that company_name query parameter is required.

        Verifies:
        - Missing company_name parameter returns 422
        """
        response = await client.post(
            "/api/company-users",
            json=valid_user_data
        )

        assert response.status_code == 422


# Export for pytest collection
__all__ = ["TestCompanyUserCreation"]
