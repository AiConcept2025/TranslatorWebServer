"""
Simplified integration tests for Payments API without complex fixtures.

This test file uses a simpler approach without class-based organization
to work around pytest-asyncio fixture issues.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from app.main import app
from app.database.mongodb import database


@pytest.mark.asyncio
async def test_create_subscription_payment_success():
    """Test successful creation of subscription payment with all fields."""
    # Setup
    await database.connect()
    test_db = database.db

    # Create admin user
    admin_user = {
        "user_id": f"admin_user_{ObjectId()}",  # Add unique user_id
        "user_name": "Admin User",
        "email": "admin@test.com",
        "company_name": "Test Admin Company",
        "permission_level": "admin",
        "created_at": datetime.now(timezone.utc)
    }
    admin_result = await test_db.users.insert_one(admin_user)
    admin_id = str(admin_result.inserted_id)

    # Create admin session
    session_token = f"admin_test_token_{ObjectId()}"
    session_doc = {
        "session_token": session_token,
        "user_id": admin_id,
        "email": admin_user["email"],
        "user_name": admin_user["user_name"],
        "company_name": admin_user["company_name"],
        "permission_level": "admin",
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1)
    }
    await test_db.sessions.insert_one(session_doc)

    # Create test company with unique name
    company_doc = {
        "company_id": f"company_{ObjectId()}",  # Add unique company_id
        "company_name": f"Test Payment Company {ObjectId()}",
        "admin_email": "admin@testpayment.com",
        "created_at": datetime.now(timezone.utc),
        "status": "active"
    }
    company_result = await test_db.companies.insert_one(company_doc)
    company_name = company_doc["company_name"]

    # Create test subscription
    subscription_doc = {
        "company_name": company_name,
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
    subscription_result = await test_db.subscriptions.insert_one(subscription_doc)
    subscription_id = str(subscription_result.inserted_id)

    # Test the API
    async with AsyncClient(app=app, base_url="http://test") as client:
        payment_data = {
            "company_name": company_name,
            "subscription_id": subscription_id,
            "square_payment_id": f"sq_payment_test_{ObjectId()}",
            "square_order_id": f"sq_order_test_{ObjectId()}",
            "user_email": "user@testpayment.com",
            "amount": 10000,  # $100.00
            "currency": "USD",
            "payment_status": "COMPLETED"
        }

        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {session_token}"}
        )

        # Assertions
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert data["message"] == "Subscription payment created successfully"
        assert "data" in data

        payment = data["data"]
        assert payment["company_name"] == company_name
        assert payment["subscription_id"] == subscription_id
        assert payment["square_payment_id"] == payment_data["square_payment_id"]
        assert payment["amount"] == payment_data["amount"]
        assert "_id" in payment

        # Cleanup payment
        await test_db.payments.delete_one({"_id": ObjectId(payment["_id"])})

    # Cleanup
    await test_db.subscriptions.delete_one({"_id": subscription_result.inserted_id})
    await test_db.companies.delete_one({"_id": company_result.inserted_id})
    await test_db.sessions.delete_one({"session_token": session_token})
    await test_db.users.delete_one({"_id": ObjectId(admin_id)})
    await database.disconnect()


@pytest.mark.asyncio
async def test_create_subscription_payment_unauthorized():
    """Test creation fails without authentication."""
    # Setup
    await database.connect()
    test_db = database.db

    subscription_id = str(ObjectId())

    async with AsyncClient(app=app, base_url="http://test") as client:
        payment_data = {
            "company_name": "Test Company",
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
        # Check for either error response format
        assert "detail" in data or ("error" in data and data["error"]["code"] == 401)

    await database.disconnect()


@pytest.mark.asyncio
async def test_get_all_payments_unauthorized():
    """Test get all payments fails without authentication."""
    await database.connect()

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/payments/")

        assert response.status_code == 401

    await database.disconnect()


@pytest.mark.asyncio
async def test_get_payment_by_id_not_found():
    """Test 404 when payment does not exist."""
    await database.connect()

    non_existent_id = str(ObjectId())

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(f"/api/v1/payments/{non_existent_id}")

        assert response.status_code == 404
        data = response.json()
        # Handle both error response formats
        if "detail" in data:
            assert "not found" in data["detail"].lower()
        elif "error" in data:
            assert data["error"]["code"] == 404

    await database.disconnect()


@pytest.mark.asyncio
async def test_get_company_payments_empty_result():
    """Test response when company has no payments."""
    await database.connect()

    non_existent_company = f"NonExistent_{ObjectId()}"

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            f"/api/v1/payments/company/{non_existent_company}"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert data["data"]["count"] == 0
        assert len(data["data"]["payments"]) == 0

    await database.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
