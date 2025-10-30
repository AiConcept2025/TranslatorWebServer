"""
Simple integration test for POST /api/v1/payments/subscription endpoint.
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.main import app
from app.database.mongodb import database


@pytest.mark.asyncio
async def test_create_subscription_payment_success():
    """Test successful creation of subscription payment."""
    # Ensure database is connected
    if not database.is_connected:
        await database.connect()

    # 1. Create admin user and session
    import uuid
    unique_id = uuid.uuid4().hex[:12]

    admin_user = {
        "user_id": f"admin_test_{unique_id}",
        "user_name": "Admin User",
        "email": f"admin_{unique_id}@test.com",
        "company_name": f"Test Admin Company {unique_id}",
        "permission_level": "admin",
        "created_at": datetime.now(timezone.utc)
    }
    result = await database.users.insert_one(admin_user)
    admin_user_id = result.inserted_id

    session_token = f"admin_test_token_{unique_id}"
    session_doc = {
        "session_token": session_token,
        "user_id": str(admin_user_id),
        "email": admin_user["email"],
        "user_name": admin_user["user_name"],
        "company_name": admin_user["company_name"],
        "permission_level": "admin",
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + 86400, timezone.utc)
    }
    await database.sessions.insert_one(session_doc)

    # 2. Create test company
    company_doc = {
        "company_name": f"Test Payment Company {unique_id}",
        "admin_email": f"admin_{unique_id}@testpayment.com",
        "created_at": datetime.now(timezone.utc),
        "status": "active"
    }
    result = await database.companies.insert_one(company_doc)
    company_id = result.inserted_id

    # 3. Create test subscription
    subscription_doc = {
        "company_name": company_doc["company_name"],
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
    result = await database.subscriptions.insert_one(subscription_doc)
    subscription_id = str(result.inserted_id)

    # 4. Make request to create subscription payment
    payment_data = {
        "company_name": company_doc["company_name"],
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

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/payments/subscription",
            json=payment_data,
            headers={"Authorization": f"Bearer {session_token}"}
        )

        # 5. Assertions
        assert response.status_code == 201
        data = response.json()

        assert data["success"] is True
        assert data["message"] == "Subscription payment created successfully"
        assert "data" in data

        payment = data["data"]
        assert payment["company_name"] == company_doc["company_name"]
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

        # 6. Cleanup
        await database.payments.delete_one({"_id": ObjectId(payment["_id"])})
        await database.subscriptions.delete_one({"_id": ObjectId(subscription_id)})
        await database.companies.delete_one({"_id": company_id})
        await database.users.delete_one({"_id": admin_user_id})
        await database.sessions.delete_one({"session_token": session_token})
