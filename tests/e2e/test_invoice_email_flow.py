"""
E2E tests for complete invoice email flow.

Tests the end-to-end flow:
1. Create company
2. Create subscription
3. Create invoice
4. Send invoice email with PDF attachment
"""
import pytest
from bson import ObjectId


class TestInvoiceEmailE2EFlow:
    """End-to-end tests for invoice email functionality"""

    @pytest.mark.asyncio
    async def test_full_invoice_email_flow(self, http_client, test_db, auth_headers):
        """
        Test complete flow: Create company → Create subscription → Create invoice → Send email.

        This tests the full integration of:
        - Company creation
        - Subscription setup
        - Invoice generation
        - PDF creation
        - Email sending with attachment
        """
        # 1. Create company
        company_data = {
            "company_name": "E2E Test Corporation",
            "contact_email": "e2e_invoice@example.com",
            "subscription_type": "enterprise",
            "contact_name": "John Doe",
            "phone": "555-0123",
            "address": {
                "street": "123 Test St",
                "city": "Test City",
                "state": "NY",
                "zip": "10001",
                "country": "USA"
            }
        }

        company_response = await http_client.post(
            "/api/v1/companies",
            json=company_data,
            headers=auth_headers
        )

        assert company_response.status_code in [200, 201], f"Company creation failed: {company_response.text}"
        company_id = company_data["company_name"]  # company_id is company_name string

        # 2. Create subscription
        subscription_data = {
            "company_id": company_id,
            "plan_name": "Enterprise Plan",
            "monthly_price": 300.00,
            "allocated_units": 1000,
            "price_per_unit": 0.50,
            "status": "active"
        }

        subscription_response = await http_client.post(
            "/api/v1/subscriptions",
            json=subscription_data,
            headers=auth_headers
        )

        assert subscription_response.status_code in [200, 201], f"Subscription creation failed: {subscription_response.text}"
        subscription_id = subscription_response.json().get("_id") or subscription_response.json().get("id")

        # 3. Create invoice
        invoice_data = {
            "company_id": company_id,
            "subscription_id": subscription_id,
            "billing_period": {
                "period_numbers": [1, 2, 3],
                "period_start": "2025-01-01T00:00:00Z",
                "period_end": "2025-03-31T23:59:59Z"
            },
            "line_items": [
                {
                    "description": "Enterprise Plan - Q1 (Jan-Mar)",
                    "period_numbers": [1, 2, 3],
                    "quantity": 3,
                    "unit_price": 300.00,
                    "amount": 900.00
                },
                {
                    "description": "Overage Charges - 200 units",
                    "period_numbers": [1, 2, 3],
                    "quantity": 200,
                    "unit_price": 0.50,
                    "amount": 100.00
                }
            ]
        }

        invoice_response = await http_client.post(
            "/api/v1/invoices",
            json=invoice_data,
            headers=auth_headers
        )

        assert invoice_response.status_code in [200, 201], f"Invoice creation failed: {invoice_response.text}"
        invoice_result = invoice_response.json()
        invoice_id = invoice_result.get("data", {}).get("_id") or invoice_result.get("_id")

        # 4. Send invoice email
        send_response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=auth_headers
        )

        # Assert: Email sent successfully
        assert send_response.status_code == 200, f"Send email failed: {send_response.text}"
        send_data = send_response.json()
        assert send_data["success"] is True
        assert "e2e_invoice@example.com" in send_data["message"]
        assert invoice_id in send_data["invoice_id"]

        # Verify invoice exists in database
        invoice_in_db = await test_db.invoices.find_one({"_id": ObjectId(invoice_id)})
        assert invoice_in_db is not None
        assert invoice_in_db["company_id"] == company_id
        assert len(invoice_in_db["line_items"]) == 2

    @pytest.mark.asyncio
    async def test_invoice_email_with_quarterly_generation(self, http_client, test_db, auth_headers):
        """
        Test flow using quarterly invoice generation endpoint.

        Flow:
        1. Create company
        2. Create subscription with usage data
        3. Generate quarterly invoice
        4. Send invoice email
        """
        # 1. Create company
        company_data = {
            "company_name": "Quarterly Test Corp",
            "contact_email": "quarterly_test@example.com",
            "subscription_type": "enterprise",
            "address": {
                "street": "456 Test Ave",
                "city": "Test City",
                "state": "NY",
                "zip": "10002",
                "country": "USA"
            }
        }

        company_response = await http_client.post(
            "/api/v1/companies",
            json=company_data,
            headers=auth_headers
        )

        assert company_response.status_code in [200, 201]
        company_id = company_data["company_name"]  # company_id is company_name string

        # 2. Create subscription
        subscription_data = {
            "company_id": company_id,
            "plan_name": "Standard Plan",
            "monthly_price": 200.00,
            "allocated_units": 500,
            "price_per_unit": 0.75,
            "status": "active"
        }

        subscription_response = await http_client.post(
            "/api/v1/subscriptions",
            json=subscription_data,
            headers=auth_headers
        )

        assert subscription_response.status_code in [200, 201]
        subscription_id = subscription_response.json().get("_id") or subscription_response.json().get("id")

        # 3. Generate Q1 invoice
        quarterly_response = await http_client.post(
            f"/api/v1/invoices/generate-quarterly?subscription_id={subscription_id}&quarter=1",
            headers=auth_headers
        )

        assert quarterly_response.status_code in [200, 201], f"Quarterly generation failed: {quarterly_response.text}"
        invoice_data = quarterly_response.json().get("data", {})
        invoice_id = invoice_data.get("_id")

        # 4. Send invoice email
        send_response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=auth_headers
        )

        # Assert: Email sent
        assert send_response.status_code == 200
        send_data = send_response.json()
        assert send_data["success"] is True
        assert "quarterly_test@example.com" in send_data["message"]
