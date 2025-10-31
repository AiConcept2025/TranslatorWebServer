"""
Integration tests for POST /api/v1/payments/subscription endpoint.

Tests the subscription payment creation endpoint with real MongoDB integration.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.main import app
from app.database.mongodb import database


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
    session_token = "admin_test_token_12345"
    session_doc = {
        "session_token": session_token,
        "user_id": user_id,
        "email": admin_user["email"],
        "user_name": admin_user["user_name"],
        "company_name": admin_user["company_name"],
        "permission_level": "admin",
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + 86400, timezone.utc)
    }

    await test_db.sessions.insert_one(session_doc)

    yield session_token

    # Cleanup
    await test_db.users.delete_one({"_id": ObjectId(user_id)})
    await test_db.sessions.delete_one({"session_token": session_token})


@pytest.fixture
async def test_company(test_db):
    """Create a test company."""
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
    """Create a test subscription."""
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

    yield subscription_id, test_company

    # Cleanup
    await test_db.subscriptions.delete_one({"_id": ObjectId(subscription_id)})


@pytest.mark.asyncio
async def test_create_subscription_payment_success(client, admin_token, test_subscription, test_db):
    """Test successful creation of subscription payment."""
    subscription_id, company_name = test_subscription

    payment_data = {
        "company_name": company_name,
        "subscription_id": subscription_id,
        "square_payment_id": "sq_payment_test_12345",
        "square_order_id": "sq_order_test_67890",
        "square_customer_id": "sq_customer_test_abc",
        "user_email": "user@testpayment.com",
        "user_id": "user_test_123",
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
        headers={"Authorization": f"Bearer {admin_token}"}
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

    # Cleanup - remove created payment
    await test_db.payments.delete_one({"_id": ObjectId(payment["_id"])})


@pytest.mark.asyncio
async def test_create_subscription_payment_minimal(client, admin_token, test_subscription, test_db):
    """Test subscription payment creation with minimal fields."""
    subscription_id, company_name = test_subscription

    payment_data = {
        "company_name": company_name,
        "subscription_id": subscription_id,
        "square_payment_id": "sq_payment_minimal_12345",
        "user_email": "minimal@testpayment.com",
        "amount": 5000  # $50.00
    }

    response = await client.post(
        "/api/v1/payments/subscription",
        json=payment_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 201
    data = response.json()

    assert data["success"] is True
    payment = data["data"]
    assert payment["amount"] == 5000
    assert payment["currency"] == "USD"  # Default
    assert payment["payment_status"] == "COMPLETED"  # Default

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment["_id"])})


@pytest.mark.asyncio
async def test_create_subscription_payment_invalid_subscription_id(client, admin_token, test_company):
    """Test error when subscription_id is invalid format."""
    payment_data = {
        "company_name": test_company,
        "subscription_id": "invalid_not_objectid",
        "square_payment_id": "sq_payment_invalid_12345",
        "user_email": "user@test.com",
        "amount": 10000
    }

    response = await client.post(
        "/api/v1/payments/subscription",
        json=payment_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 400
    data = response.json()
    assert "Invalid subscription_id format" in data["detail"]


@pytest.mark.asyncio
async def test_create_subscription_payment_subscription_not_found(client, admin_token, test_company):
    """Test error when subscription does not exist."""
    fake_subscription_id = str(ObjectId())

    payment_data = {
        "company_name": test_company,
        "subscription_id": fake_subscription_id,
        "square_payment_id": "sq_payment_notfound_12345",
        "user_email": "user@test.com",
        "amount": 10000
    }

    response = await client.post(
        "/api/v1/payments/subscription",
        json=payment_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 400
    data = response.json()
    assert "Subscription not found" in data["detail"]


@pytest.mark.asyncio
async def test_create_subscription_payment_company_mismatch(client, admin_token, test_subscription):
    """Test error when company name does not match subscription."""
    subscription_id, _ = test_subscription

    payment_data = {
        "company_name": "Wrong Company Name",
        "subscription_id": subscription_id,
        "square_payment_id": "sq_payment_mismatch_12345",
        "user_email": "user@test.com",
        "amount": 10000
    }

    response = await client.post(
        "/api/v1/payments/subscription",
        json=payment_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 400
    data = response.json()
    assert "Company name mismatch" in data["detail"]


@pytest.mark.asyncio
async def test_create_subscription_payment_unauthorized(client):
    """Test error when no authentication token provided."""
    payment_data = {
        "company_name": "Test Company",
        "subscription_id": str(ObjectId()),
        "square_payment_id": "sq_payment_unauth_12345",
        "user_email": "user@test.com",
        "amount": 10000
    }

    response = await client.post(
        "/api/v1/payments/subscription",
        json=payment_data
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_subscription_payment_non_admin(client, test_db):
    """Test error when user is not admin."""
    # Create regular user (non-admin)
    user_doc = {
        "user_name": "Regular User",
        "email": "user@test.com",
        "company_name": "Test Company",
        "permission_level": "user",
        "created_at": datetime.now(timezone.utc)
    }

    result = await test_db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Create session for regular user
    session_token = "user_token_12345"
    session_doc = {
        "session_token": session_token,
        "user_id": user_id,
        "email": user_doc["email"],
        "user_name": user_doc["user_name"],
        "company_name": user_doc["company_name"],
        "permission_level": "user",
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + 86400, timezone.utc)
    }

    await test_db.sessions.insert_one(session_doc)

    payment_data = {
        "company_name": "Test Company",
        "subscription_id": str(ObjectId()),
        "square_payment_id": "sq_payment_nonadmin_12345",
        "user_email": "user@test.com",
        "amount": 10000
    }

    response = await client.post(
        "/api/v1/payments/subscription",
        json=payment_data,
        headers={"Authorization": f"Bearer {session_token}"}
    )

    assert response.status_code == 403
    data = response.json()
    assert "Admin permissions required" in data["detail"]

    # Cleanup
    await test_db.users.delete_one({"_id": ObjectId(user_id)})
    await test_db.sessions.delete_one({"session_token": session_token})


@pytest.mark.asyncio
async def test_create_subscription_payment_with_custom_date(client, admin_token, test_subscription, test_db):
    """Test subscription payment creation with custom payment_date."""
    subscription_id, company_name = test_subscription

    custom_date = datetime(2025, 10, 15, 10, 30, 0, tzinfo=timezone.utc)

    payment_data = {
        "company_name": company_name,
        "subscription_id": subscription_id,
        "square_payment_id": "sq_payment_custom_date_12345",
        "user_email": "user@testpayment.com",
        "amount": 7500,
        "payment_date": custom_date.isoformat()
    }

    response = await client.post(
        "/api/v1/payments/subscription",
        json=payment_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 201
    data = response.json()

    payment = data["data"]
    assert payment["payment_date"] == custom_date.isoformat()

    # Cleanup
    await test_db.payments.delete_one({"_id": ObjectId(payment["_id"])})
