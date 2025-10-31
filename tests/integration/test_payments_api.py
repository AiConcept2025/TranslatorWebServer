"""
Comprehensive integration tests for Payments API endpoints.

This test suite covers all payment endpoints with real MongoDB integration
and real API calls (no mocking). Tests authentication, authorization,
validation, and business logic.

Test Coverage:
- POST /api/v1/payments/subscription (admin only)
- GET /api/v1/payments/ (admin only)
- GET /api/v1/payments/company/{company_name}
- GET /api/v1/payments/email/{email}
- GET /api/v1/payments/{payment_id}
- GET /api/v1/payments/square/{square_payment_id}
- PATCH /api/v1/payments/{square_payment_id}
- POST /api/v1/payments/{square_payment_id}/refund
- GET /api/v1/payments/company/{company_name}/stats
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Tuple

from app.main import app
from app.database.mongodb import database


# ============================================================================
# Test Fixtures
# ============================================================================

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
async def admin_token(test_db):
    """Create admin user and return authentication token."""
    # Create admin user in database
    admin_user = {
        "user_name": "Admin User",
        "email": "admin@test.com",
        "company_name": "Test Admin Company",
        "permission_level": "admin",
        "created_at": datetime.now(timezone.utc)
    }

    result = await test_db.users.insert_one(admin_user)
    user_id = str(result.inserted_id)

    # Create session token
    session_token = f"admin_test_token_{ObjectId()}"
    session_doc = {
        "session_token": session_token,
        "user_id": user_id,
        "email": admin_user["email"],
        "user_name": admin_user["user_name"],
        "company_name": admin_user["company_name"],
        "permission_level": "admin",
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1)
    }

    await test_db.sessions.insert_one(session_doc)

    yield session_token

    # Cleanup
    await test_db.users.delete_one({"_id": ObjectId(user_id)})
    await test_db.sessions.delete_one({"session_token": session_token})


@pytest.fixture
async def user_token(test_db):
    """Create regular user and return authentication token."""
    # Create regular user (non-admin)
    user_doc = {
        "user_name": "Regular User",
        "email": "user@test.com",
        "company_name": "Test User Company",
        "permission_level": "user",
        "created_at": datetime.now(timezone.utc)
    }

    result = await test_db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Create session for regular user
    session_token = f"user_token_{ObjectId()}"
    session_doc = {
        "session_token": session_token,
        "user_id": user_id,
        "email": user_doc["email"],
        "user_name": user_doc["user_name"],
        "company_name": user_doc["company_name"],
        "permission_level": "user",
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1)
    }

    await test_db.sessions.insert_one(session_doc)

    yield session_token

    # Cleanup
    await test_db.users.delete_one({"_id": ObjectId(user_id)})
    await test_db.sessions.delete_one({"session_token": session_token})


@pytest.fixture
async def test_company(test_db) -> str:
    """Create a test company and return company name."""
    company_doc = {
        "company_name": "Test Payment Company",
        "admin_email": "admin@testpayment.com",
        "created_at": datetime.now(timezone.utc),
        "status": "active"
    }

    result = await test_db.companies.insert_one(company_doc)
    company_id = result.inserted_id

    yield company_doc["company_name"]

    # Cleanup
    await test_db.companies.delete_one({"_id": company_id})


@pytest.fixture
async def test_subscription(test_db, test_company):
    """
    Create a test subscription.

    Returns:
        Tuple of (subscription_id, company_name)
    """
    subscription_doc = {
        "company_name": test_company,
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        "price_per_unit": 0.10,
        "promotional_units": 100,
        "discount": 1.0,
        "subscription_price": 100.00,
        "start_date": datetime.now(timezone.utc),
        "end_date": None,
        "status": "active",
        "usage_periods": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.subscriptions.insert_one(subscription_doc)
    subscription_id = str(result.inserted_id)

    # Return tuple for unpacking
    yield (subscription_id, test_company)

    # Cleanup
    await test_db.subscriptions.delete_one({"_id": ObjectId(subscription_id)})


@pytest.fixture
async def sample_payment(test_db, test_company) -> Dict:
    """
    Create a sample payment record for testing.

    Returns:
        Payment document with _id as string
    """
    payment_doc = {
        "company_name": test_company,
        "user_email": "test@example.com",
        "square_payment_id": f"sq_payment_sample_{ObjectId()}",
        "amount": 5000,  # $50.00
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await test_db.payments.insert_one(payment_doc)
    payment_doc["_id"] = str(result.inserted_id)

    yield payment_doc

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment_doc["_id"])})


# ============================================================================
# POST /api/v1/payments/subscription Tests
# ============================================================================

class TestCreateSubscriptionPayment:
    """Tests for POST /api/v1/payments/subscription endpoint."""

    @pytest.mark.asyncio
    async def test_create_subscription_payment_success(
        self, client, admin_token, test_subscription, test_db
    ):
        """Test successful creation of subscription payment with all fields."""
        token = admin_token
        subscription_id, company_name = test_subscription

        payment_data = {
            "company_name": company_name,
            "subscription_id": subscription_id,
            "square_payment_id": f"sq_payment_test_{ObjectId()}",
            "square_order_id": f"sq_order_test_{ObjectId()}",
            "square_customer_id": f"sq_customer_test_{ObjectId()}",
            "user_email": "user@testpayment.com",
            "user_id": f"user_test_{ObjectId()}",
            "amount": 10000,  # $100.00
            "currency": "USD",
            "payment_status": "COMPLETED",
            "payment_method": "card",
            "card_brand": "VISA",
            "card_last_4": "4242",
            "receipt_url": "https://squareup.com/receipt/test123"
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assert response structure
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert data["message"] == "Subscription payment created successfully"
        assert "data" in data

        # Validate payment fields
        payment = data["data"]
        assert payment["company_name"] == company_name
        assert payment["subscription_id"] == subscription_id
        assert payment["square_payment_id"] == payment_data["square_payment_id"]
        assert payment["user_email"] == payment_data["user_email"]
        assert payment["amount"] == payment_data["amount"]
        assert payment["currency"] == "USD"
        assert payment["payment_status"] == "COMPLETED"
        assert payment["card_brand"] == "VISA"
        assert payment["card_last_4"] == "4242"
        assert "_id" in payment
        assert "created_at" in payment
        assert "updated_at" in payment
        assert "payment_date" in payment

        # Validate data types
        assert isinstance(payment["amount"], int)
        assert isinstance(payment["_id"], str)
        assert len(payment["_id"]) == 24  # Valid ObjectId

        # Cleanup - remove created payment
        await test_db.payments.delete_one({"_id": ObjectId(payment["_id"])})

    @pytest.mark.asyncio
    async def test_create_subscription_payment_minimal_fields(
        self, client, admin_token, test_subscription, test_db
    ):
        """Test subscription payment creation with minimal required fields."""
        token = admin_token
        subscription_id, company_name = test_subscription

        payment_data = {
            "company_name": company_name,
            "subscription_id": subscription_id,
            "square_payment_id": f"sq_payment_minimal_{ObjectId()}",
            "user_email": "minimal@testpayment.com",
            "amount": 5000  # $50.00
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        payment = data["data"]
        assert payment["amount"] == 5000
        assert payment["currency"] == "USD"  # Default
        assert payment["payment_status"] == "COMPLETED"  # Default
        assert payment["payment_method"] == "card"  # Default

        # Cleanup
        await test_db.payments.delete_one({"_id": ObjectId(payment["_id"])})

    @pytest.mark.asyncio
    async def test_create_subscription_payment_no_auth(
        self, client, test_subscription
    ):
        """Test creation fails without authentication."""
        subscription_id, company_name = test_subscription

        payment_data = {
            "company_name": company_name,
            "subscription_id": subscription_id,
            "square_payment_id": f"sq_payment_noauth_{ObjectId()}",
            "user_email": "user@test.com",
            "amount": 10000
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_create_subscription_payment_non_admin(
        self, client, user_token, test_subscription
    ):
        """Test creation fails with non-admin user."""
        token = user_token
        subscription_id, company_name = test_subscription

        payment_data = {
            "company_name": company_name,
            "subscription_id": subscription_id,
            "square_payment_id": f"sq_payment_nonadmin_{ObjectId()}",
            "user_email": "user@test.com",
            "amount": 10000
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        data = response.json()
        assert "Admin permissions required" in data["detail"]

    @pytest.mark.asyncio
    async def test_create_subscription_payment_invalid_subscription_id(
        self, client, admin_token, test_company
    ):
        """Test error when subscription_id is invalid format."""
        token = admin_token

        payment_data = {
            "company_name": test_company,
            "subscription_id": "invalid_not_objectid",
            "square_payment_id": f"sq_payment_invalid_{ObjectId()}",
            "user_email": "user@test.com",
            "amount": 10000
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid subscription_id format" in data["detail"]

    @pytest.mark.asyncio
    async def test_create_subscription_payment_subscription_not_found(
        self, client, admin_token, test_company
    ):
        """Test error when subscription does not exist."""
        token = admin_token
        fake_subscription_id = str(ObjectId())

        payment_data = {
            "company_name": test_company,
            "subscription_id": fake_subscription_id,
            "square_payment_id": f"sq_payment_notfound_{ObjectId()}",
            "user_email": "user@test.com",
            "amount": 10000
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Subscription not found" in data["detail"]

    @pytest.mark.asyncio
    async def test_create_subscription_payment_company_mismatch(
        self, client, admin_token, test_subscription
    ):
        """Test error when company name does not match subscription."""
        token = admin_token
        subscription_id, _ = test_subscription

        payment_data = {
            "company_name": "Wrong Company Name",
            "subscription_id": subscription_id,
            "square_payment_id": f"sq_payment_mismatch_{ObjectId()}",
            "user_email": "user@test.com",
            "amount": 10000
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Company name mismatch" in data["detail"]

    @pytest.mark.asyncio
    async def test_create_subscription_payment_with_custom_date(
        self, client, admin_token, test_subscription, test_db
    ):
        """Test subscription payment creation with custom payment_date."""
        token = admin_token
        subscription_id, company_name = test_subscription

        custom_date = datetime(2025, 10, 15, 10, 30, 0, tzinfo=timezone.utc)

        payment_data = {
            "company_name": company_name,
            "subscription_id": subscription_id,
            "square_payment_id": f"sq_payment_custom_date_{ObjectId()}",
            "user_email": "user@testpayment.com",
            "amount": 7500,
            "payment_date": custom_date.isoformat()
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201
        data = response.json()

        payment = data["data"]
        assert payment["payment_date"] == custom_date.isoformat()

        # Cleanup
        await test_db.payments.delete_one({"_id": ObjectId(payment["_id"])})


# ============================================================================
# GET /api/v1/payments/ Tests (Admin Only)
# ============================================================================

class TestGetAllPayments:
    """Tests for GET /api/v1/payments/ endpoint (admin only)."""

    @pytest.mark.asyncio
    async def test_get_all_payments_success(
        self, client, admin_token, test_db, test_company
    ):
        """Test successful retrieval of all payments by admin."""
        token = admin_token

        # Create test payments
        payment1 = {
            "company_name": test_company,
            "user_email": "user1@test.com",
            "square_payment_id": f"sq_payment_1_{ObjectId()}",
            "amount": 1000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        payment2 = {
            "company_name": test_company,
            "user_email": "user2@test.com",
            "square_payment_id": f"sq_payment_2_{ObjectId()}",
            "amount": 2000,
            "currency": "USD",
            "payment_status": "PENDING",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result1 = await test_db.payments.insert_one(payment1)
        result2 = await test_db.payments.insert_one(payment2)

        response = await client.get(
            "/api/v1/payments/",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert "payments" in data["data"]
        assert "count" in data["data"]
        assert "total" in data["data"]
        assert "filters" in data["data"]

        # Should contain at least our test payments
        assert data["data"]["count"] >= 2

        # Cleanup
        await test_db.payments.delete_one({"_id": result1.inserted_id})
        await test_db.payments.delete_one({"_id": result2.inserted_id})

    @pytest.mark.asyncio
    async def test_get_all_payments_filter_by_status(
        self, client, admin_token, test_db, test_company
    ):
        """Test filtering payments by status."""
        token = admin_token

        # Create payments with different statuses
        completed_payment = {
            "company_name": test_company,
            "user_email": "completed@test.com",
            "square_payment_id": f"sq_payment_completed_{ObjectId()}",
            "amount": 1000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        pending_payment = {
            "company_name": test_company,
            "user_email": "pending@test.com",
            "square_payment_id": f"sq_payment_pending_{ObjectId()}",
            "amount": 2000,
            "currency": "USD",
            "payment_status": "PENDING",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result1 = await test_db.payments.insert_one(completed_payment)
        result2 = await test_db.payments.insert_one(pending_payment)

        # Query for COMPLETED only
        response = await client.get(
            "/api/v1/payments/?status=COMPLETED",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # All returned payments should be COMPLETED
        for payment in data["data"]["payments"]:
            assert payment["payment_status"] == "COMPLETED"

        # Cleanup
        await test_db.payments.delete_one({"_id": result1.inserted_id})
        await test_db.payments.delete_one({"_id": result2.inserted_id})

    @pytest.mark.asyncio
    async def test_get_all_payments_filter_by_company(
        self, client, admin_token, test_db
    ):
        """Test filtering payments by company name."""
        token = admin_token

        company1 = "Test Company A"
        company2 = "Test Company B"

        # Create payments for different companies
        payment1 = {
            "company_name": company1,
            "user_email": "usera@test.com",
            "square_payment_id": f"sq_payment_a_{ObjectId()}",
            "amount": 1000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        payment2 = {
            "company_name": company2,
            "user_email": "userb@test.com",
            "square_payment_id": f"sq_payment_b_{ObjectId()}",
            "amount": 2000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result1 = await test_db.payments.insert_one(payment1)
        result2 = await test_db.payments.insert_one(payment2)

        # Query for company1 only
        response = await client.get(
            f"/api/v1/payments/?company_name={company1}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # All returned payments should be for company1
        for payment in data["data"]["payments"]:
            assert payment["company_name"] == company1

        # Cleanup
        await test_db.payments.delete_one({"_id": result1.inserted_id})
        await test_db.payments.delete_one({"_id": result2.inserted_id})

    @pytest.mark.asyncio
    async def test_get_all_payments_pagination(
        self, client, admin_token, test_db, test_company
    ):
        """Test pagination with skip and limit."""
        token = admin_token

        # Create multiple payments
        payment_ids = []
        for i in range(5):
            payment = {
                "company_name": test_company,
                "user_email": f"user{i}@test.com",
                "square_payment_id": f"sq_payment_page_{i}_{ObjectId()}",
                "amount": 1000 * (i + 1),
                "currency": "USD",
                "payment_status": "COMPLETED",
                "refunds": [],
                "payment_date": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            result = await test_db.payments.insert_one(payment)
            payment_ids.append(result.inserted_id)

        # Test with limit=2, skip=0
        response = await client.get(
            "/api/v1/payments/?limit=2&skip=0",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["limit"] == 2
        assert data["data"]["skip"] == 0

        # Test with limit=2, skip=2
        response = await client.get(
            "/api/v1/payments/?limit=2&skip=2",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["limit"] == 2
        assert data["data"]["skip"] == 2

        # Cleanup
        for payment_id in payment_ids:
            await test_db.payments.delete_one({"_id": payment_id})

    @pytest.mark.asyncio
    async def test_get_all_payments_sorting(
        self, client, admin_token, test_db, test_company
    ):
        """Test sorting by different fields."""
        token = admin_token

        # Create payments with different amounts
        payment1 = {
            "company_name": test_company,
            "user_email": "user1@test.com",
            "square_payment_id": f"sq_payment_sort1_{ObjectId()}",
            "amount": 1000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        payment2 = {
            "company_name": test_company,
            "user_email": "user2@test.com",
            "square_payment_id": f"sq_payment_sort2_{ObjectId()}",
            "amount": 5000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result1 = await test_db.payments.insert_one(payment1)
        result2 = await test_db.payments.insert_one(payment2)

        # Sort by amount ascending
        response = await client.get(
            "/api/v1/payments/?sort_by=amount&sort_order=asc&limit=10",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200

        # Cleanup
        await test_db.payments.delete_one({"_id": result1.inserted_id})
        await test_db.payments.delete_one({"_id": result2.inserted_id})

    @pytest.mark.asyncio
    async def test_get_all_payments_unauthorized(self, client):
        """Test error when no authentication provided."""
        response = await client.get("/api/v1/payments/")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_all_payments_non_admin(self, client, user_token):
        """Test error when non-admin user tries to access."""
        token = user_token

        response = await client.get(
            "/api/v1/payments/",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_all_payments_invalid_status(self, client, admin_token):
        """Test error with invalid status filter."""
        token = admin_token

        response = await client.get(
            "/api/v1/payments/?status=INVALID_STATUS",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        data = response.json()
        assert "Invalid payment status" in data["detail"]


# ============================================================================
# GET /api/v1/payments/company/{company_name} Tests
# ============================================================================

class TestGetCompanyPayments:
    """Tests for GET /api/v1/payments/company/{company_name} endpoint."""

    @pytest.mark.asyncio
    async def test_get_company_payments_success(
        self, client, test_db, test_company
    ):
        """Test successful retrieval of company payments."""
        # Create test payments for the company
        payment1 = {
            "company_name": test_company,
            "user_email": "user1@test.com",
            "square_payment_id": f"sq_payment_company1_{ObjectId()}",
            "amount": 1500,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        payment2 = {
            "company_name": test_company,
            "user_email": "user2@test.com",
            "square_payment_id": f"sq_payment_company2_{ObjectId()}",
            "amount": 2500,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result1 = await test_db.payments.insert_one(payment1)
        result2 = await test_db.payments.insert_one(payment2)

        response = await client.get(f"/api/v1/payments/company/{test_company}")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert "payments" in data["data"]
        assert data["data"]["count"] >= 2

        # All payments should be for the test company
        for payment in data["data"]["payments"]:
            assert payment["company_name"] == test_company

        # Cleanup
        await test_db.payments.delete_one({"_id": result1.inserted_id})
        await test_db.payments.delete_one({"_id": result2.inserted_id})

    @pytest.mark.asyncio
    async def test_get_company_payments_filter_by_status(
        self, client, test_db, test_company
    ):
        """Test filtering company payments by status."""
        # Create payments with different statuses
        completed = {
            "company_name": test_company,
            "user_email": "completed@test.com",
            "square_payment_id": f"sq_payment_comp_{ObjectId()}",
            "amount": 1000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        pending = {
            "company_name": test_company,
            "user_email": "pending@test.com",
            "square_payment_id": f"sq_payment_pend_{ObjectId()}",
            "amount": 2000,
            "currency": "USD",
            "payment_status": "PENDING",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result1 = await test_db.payments.insert_one(completed)
        result2 = await test_db.payments.insert_one(pending)

        response = await client.get(
            f"/api/v1/payments/company/{test_company}?status=COMPLETED"
        )

        assert response.status_code == 200
        data = response.json()

        # All returned payments should be COMPLETED
        for payment in data["data"]["payments"]:
            assert payment["payment_status"] == "COMPLETED"

        # Cleanup
        await test_db.payments.delete_one({"_id": result1.inserted_id})
        await test_db.payments.delete_one({"_id": result2.inserted_id})

    @pytest.mark.asyncio
    async def test_get_company_payments_pagination(
        self, client, test_db, test_company
    ):
        """Test pagination for company payments."""
        # Create multiple payments
        payment_ids = []
        for i in range(3):
            payment = {
                "company_name": test_company,
                "user_email": f"page{i}@test.com",
                "square_payment_id": f"sq_payment_page_comp_{i}_{ObjectId()}",
                "amount": 1000,
                "currency": "USD",
                "payment_status": "COMPLETED",
                "refunds": [],
                "payment_date": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            result = await test_db.payments.insert_one(payment)
            payment_ids.append(result.inserted_id)

        # Test pagination
        response = await client.get(
            f"/api/v1/payments/company/{test_company}?limit=2&skip=0"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["limit"] == 2
        assert data["data"]["skip"] == 0

        # Cleanup
        for payment_id in payment_ids:
            await test_db.payments.delete_one({"_id": payment_id})

    @pytest.mark.asyncio
    async def test_get_company_payments_empty_result(self, client):
        """Test response when company has no payments."""
        non_existent_company = f"NonExistent_{ObjectId()}"

        response = await client.get(
            f"/api/v1/payments/company/{non_existent_company}"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["count"] == 0
        assert len(data["data"]["payments"]) == 0


# ============================================================================
# GET /api/v1/payments/email/{email} Tests
# ============================================================================

class TestGetPaymentsByEmail:
    """Tests for GET /api/v1/payments/email/{email} endpoint."""

    @pytest.mark.asyncio
    async def test_get_payments_by_email_success(
        self, client, test_db, test_company
    ):
        """Test successful retrieval of payments by email."""
        test_email = "testuser@example.com"

        # Create payments for this email
        payment1 = {
            "company_name": test_company,
            "user_email": test_email,
            "square_payment_id": f"sq_payment_email1_{ObjectId()}",
            "amount": 1000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        payment2 = {
            "company_name": test_company,
            "user_email": test_email,
            "square_payment_id": f"sq_payment_email2_{ObjectId()}",
            "amount": 2000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result1 = await test_db.payments.insert_one(payment1)
        result2 = await test_db.payments.insert_one(payment2)

        response = await client.get(f"/api/v1/payments/email/{test_email}")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["count"] >= 2
        assert data["data"]["email"] == test_email

        # All payments should be for this email
        for payment in data["data"]["payments"]:
            assert payment["user_email"] == test_email

        # Cleanup
        await test_db.payments.delete_one({"_id": result1.inserted_id})
        await test_db.payments.delete_one({"_id": result2.inserted_id})

    @pytest.mark.asyncio
    async def test_get_payments_by_email_pagination(
        self, client, test_db, test_company
    ):
        """Test pagination for email payments."""
        test_email = "paginated@example.com"

        # Create multiple payments
        payment_ids = []
        for i in range(3):
            payment = {
                "company_name": test_company,
                "user_email": test_email,
                "square_payment_id": f"sq_payment_email_page_{i}_{ObjectId()}",
                "amount": 1000,
                "currency": "USD",
                "payment_status": "COMPLETED",
                "refunds": [],
                "payment_date": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            result = await test_db.payments.insert_one(payment)
            payment_ids.append(result.inserted_id)

        response = await client.get(
            f"/api/v1/payments/email/{test_email}?limit=2&skip=0"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["limit"] == 2

        # Cleanup
        for payment_id in payment_ids:
            await test_db.payments.delete_one({"_id": payment_id})

    @pytest.mark.asyncio
    async def test_get_payments_by_email_empty_result(self, client):
        """Test response when email has no payments."""
        non_existent_email = f"nonexistent{ObjectId()}@test.com"

        response = await client.get(f"/api/v1/payments/email/{non_existent_email}")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["count"] == 0


# ============================================================================
# GET /api/v1/payments/{payment_id} Tests
# ============================================================================

class TestGetPaymentById:
    """Tests for GET /api/v1/payments/{payment_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_payment_by_id_success(self, client, sample_payment):
        """Test successful retrieval of payment by ID."""
        payment_id = sample_payment["_id"]

        response = await client.get(f"/api/v1/payments/{payment_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["_id"] == payment_id
        assert data["company_name"] == sample_payment["company_name"]
        assert data["user_email"] == sample_payment["user_email"]
        assert data["amount"] == sample_payment["amount"]

    @pytest.mark.asyncio
    async def test_get_payment_by_id_invalid_format(self, client):
        """Test error with invalid ObjectId format."""
        invalid_id = "not_a_valid_objectid"

        response = await client.get(f"/api/v1/payments/{invalid_id}")

        assert response.status_code == 400
        data = response.json()
        assert "Invalid" in data["detail"]

    @pytest.mark.asyncio
    async def test_get_payment_by_id_not_found(self, client):
        """Test 404 when payment does not exist."""
        non_existent_id = str(ObjectId())

        response = await client.get(f"/api/v1/payments/{non_existent_id}")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


# ============================================================================
# GET /api/v1/payments/square/{square_payment_id} Tests
# ============================================================================

class TestGetPaymentBySquareId:
    """Tests for GET /api/v1/payments/square/{square_payment_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_payment_by_square_id_success(self, client, sample_payment):
        """Test successful retrieval by Square payment ID."""
        square_payment_id = sample_payment["square_payment_id"]

        response = await client.get(f"/api/v1/payments/square/{square_payment_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["square_payment_id"] == square_payment_id
        assert data["company_name"] == sample_payment["company_name"]

    @pytest.mark.asyncio
    async def test_get_payment_by_square_id_not_found(self, client):
        """Test 404 when Square payment ID does not exist."""
        non_existent_square_id = f"sq_payment_nonexistent_{ObjectId()}"

        response = await client.get(
            f"/api/v1/payments/square/{non_existent_square_id}"
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


# ============================================================================
# PATCH /api/v1/payments/{square_payment_id} Tests
# ============================================================================

class TestUpdatePayment:
    """Tests for PATCH /api/v1/payments/{square_payment_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_payment_status_success(
        self, client, test_db, test_company
    ):
        """Test successful payment status update."""
        # Create payment
        payment = {
            "company_name": test_company,
            "user_email": "update@test.com",
            "square_payment_id": f"sq_payment_update_{ObjectId()}",
            "amount": 1000,
            "currency": "USD",
            "payment_status": "PENDING",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await test_db.payments.insert_one(payment)
        square_payment_id = payment["square_payment_id"]

        # Update status
        update_data = {"payment_status": "COMPLETED"}

        response = await client.patch(
            f"/api/v1/payments/{square_payment_id}",
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["payment_status"] == "COMPLETED"

        # Cleanup
        await test_db.payments.delete_one({"_id": result.inserted_id})

    @pytest.mark.asyncio
    async def test_update_payment_not_found(self, client):
        """Test error when payment does not exist."""
        non_existent_square_id = f"sq_payment_noexist_{ObjectId()}"
        update_data = {"payment_status": "COMPLETED"}

        response = await client.patch(
            f"/api/v1/payments/{non_existent_square_id}",
            json=update_data
        )

        assert response.status_code == 404


# ============================================================================
# POST /api/v1/payments/{square_payment_id}/refund Tests
# ============================================================================

class TestProcessRefund:
    """Tests for POST /api/v1/payments/{square_payment_id}/refund endpoint."""

    @pytest.mark.asyncio
    async def test_process_refund_success(self, client, test_db, test_company):
        """Test successful refund processing."""
        # Create payment
        payment = {
            "company_name": test_company,
            "user_email": "refund@test.com",
            "square_payment_id": f"sq_payment_refund_{ObjectId()}",
            "amount": 5000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await test_db.payments.insert_one(payment)
        square_payment_id = payment["square_payment_id"]

        # Process refund
        refund_data = {
            "refund_id": f"rfn_{ObjectId()}",
            "amount": 500,
            "currency": "USD",
            "idempotency_key": f"rfd_{ObjectId()}"
        }

        response = await client.post(
            f"/api/v1/payments/{square_payment_id}/refund",
            json=refund_data
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "refund" in data["data"]
        assert data["data"]["refund"]["refund_id"] == refund_data["refund_id"]
        assert data["data"]["payment"]["payment_status"] == "REFUNDED"

        # Verify refund added to array
        updated_payment = await test_db.payments.find_one({"_id": result.inserted_id})
        assert len(updated_payment["refunds"]) == 1
        assert updated_payment["refunds"][0]["amount"] == 500

        # Cleanup
        await test_db.payments.delete_one({"_id": result.inserted_id})

    @pytest.mark.asyncio
    async def test_process_refund_exceeds_amount(
        self, client, test_db, test_company
    ):
        """Test error when refund exceeds payment amount."""
        # Create payment
        payment = {
            "company_name": test_company,
            "user_email": "exceed@test.com",
            "square_payment_id": f"sq_payment_exceed_{ObjectId()}",
            "amount": 1000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await test_db.payments.insert_one(payment)
        square_payment_id = payment["square_payment_id"]

        # Try to refund more than payment amount
        refund_data = {
            "refund_id": f"rfn_{ObjectId()}",
            "amount": 5000,  # More than 1000
            "currency": "USD",
            "idempotency_key": f"rfd_{ObjectId()}"
        }

        response = await client.post(
            f"/api/v1/payments/{square_payment_id}/refund",
            json=refund_data
        )

        assert response.status_code == 400
        data = response.json()
        assert "exceeds" in data["detail"].lower()

        # Cleanup
        await test_db.payments.delete_one({"_id": result.inserted_id})

    @pytest.mark.asyncio
    async def test_process_refund_invalid_amount(self, client, sample_payment):
        """Test error with zero or negative refund amount."""
        square_payment_id = sample_payment["square_payment_id"]

        refund_data = {
            "refund_id": f"rfn_{ObjectId()}",
            "amount": 0,  # Invalid
            "currency": "USD",
            "idempotency_key": f"rfd_{ObjectId()}"
        }

        response = await client.post(
            f"/api/v1/payments/{square_payment_id}/refund",
            json=refund_data
        )

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_process_refund_payment_not_found(self, client):
        """Test error when payment does not exist."""
        non_existent_square_id = f"sq_payment_norefund_{ObjectId()}"

        refund_data = {
            "refund_id": f"rfn_{ObjectId()}",
            "amount": 500,
            "currency": "USD",
            "idempotency_key": f"rfd_{ObjectId()}"
        }

        response = await client.post(
            f"/api/v1/payments/{non_existent_square_id}/refund",
            json=refund_data
        )

        assert response.status_code == 404


# ============================================================================
# GET /api/v1/payments/company/{company_name}/stats Tests
# ============================================================================

class TestGetCompanyPaymentStats:
    """Tests for GET /api/v1/payments/company/{company_name}/stats endpoint."""

    @pytest.mark.asyncio
    async def test_get_company_stats_success(
        self, client, test_db, test_company
    ):
        """Test successful retrieval of company payment statistics."""
        # Create payments for statistics
        payments = []
        for i in range(3):
            payment = {
                "company_name": test_company,
                "user_email": f"stats{i}@test.com",
                "square_payment_id": f"sq_payment_stats_{i}_{ObjectId()}",
                "amount": 1000 * (i + 1),
                "currency": "USD",
                "payment_status": "COMPLETED",
                "refunds": [],
                "payment_date": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            result = await test_db.payments.insert_one(payment)
            payments.append(result.inserted_id)

        response = await client.get(
            f"/api/v1/payments/company/{test_company}/stats"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert "total_payments" in data["data"]
        assert "total_amount_cents" in data["data"]
        assert "total_amount_dollars" in data["data"]
        assert "completed_payments" in data["data"]
        assert "success_rate" in data["data"]

        # Cleanup
        for payment_id in payments:
            await test_db.payments.delete_one({"_id": payment_id})

    @pytest.mark.asyncio
    async def test_get_company_stats_with_date_range(
        self, client, test_db, test_company
    ):
        """Test stats with date range filtering."""
        # Create payment with specific date
        past_date = datetime.now(timezone.utc) - timedelta(days=10)
        payment = {
            "company_name": test_company,
            "user_email": "daterange@test.com",
            "square_payment_id": f"sq_payment_daterange_{ObjectId()}",
            "amount": 2000,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": past_date,
            "created_at": past_date,
            "updated_at": past_date
        }

        result = await test_db.payments.insert_one(payment)

        # Query with date range
        start_date = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        end_date = datetime.now(timezone.utc).isoformat()

        response = await client.get(
            f"/api/v1/payments/company/{test_company}/stats"
            f"?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Cleanup
        await test_db.payments.delete_one({"_id": result.inserted_id})

    @pytest.mark.asyncio
    async def test_get_company_stats_no_payments(self, client):
        """Test stats for company with no payments."""
        non_existent_company = f"NoPayments_{ObjectId()}"

        response = await client.get(
            f"/api/v1/payments/company/{non_existent_company}/stats"
        )

        assert response.status_code == 200
        data = response.json()

        # Should return zero stats
        assert data["data"]["total_payments"] == 0
        assert data["data"]["total_amount_cents"] == 0
