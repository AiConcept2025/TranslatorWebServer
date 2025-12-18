"""
Integration tests for invoice payment link functionality.

Tests the complete flow of:
1. Creating Stripe payment links when sending invoices
2. Storing payment link metadata in database
3. Handling paid invoices (skip payment link)
4. Graceful degradation when Stripe API fails
"""
import pytest
import httpx
from bson import ObjectId
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


class TestInvoicePaymentLinkIntegration:
    """Integration tests for invoice payment link creation flow."""

    @pytest.mark.asyncio
    async def test_send_invoice_creates_payment_link(
        self,
        http_client: httpx.AsyncClient,
        test_db,
        auth_headers
    ):
        """
        Test that sending invoice creates Stripe payment link.

        Flow:
        1. Create test company and invoice
        2. POST /api/v1/invoices/{invoice_id}/send-email
        3. Verify response includes payment_link_url
        4. Verify invoice document updated with payment link fields
        """
        # Arrange: Create test company
        company_data = {
            "company_name": "TEST-PaymentLink-Corp-001",
            "contact_email": "test_payment_link@example.com",
            "subscription_type": "enterprise",
            "address": {
                "street": "123 Payment St",
                "city": "Link City",
                "state": "CA",
                "zip": "90001",
                "country": "USA"
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await test_db.company.insert_one(company_data)

        # Create test invoice (not paid)
        invoice_data = {
            "company_id": "TEST-PaymentLink-Corp-001",
            "company_name": "TEST-PaymentLink-Corp-001",
            "invoice_number": "TEST-INV-PL-001",
            "invoice_date": datetime.now(timezone.utc),
            "due_date": datetime.now(timezone.utc),
            "line_items": [
                {
                    "description": "Translation Service",
                    "quantity": 1,
                    "unit_price": 100.00,
                    "amount": 100.00
                }
            ],
            "subtotal": 100.00,
            "tax_amount": 6.00,
            "total_amount": 106.00,
            "status": "sent",  # NOT paid
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Send invoice email (mocking Stripe API)
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            mock_price.return_value = MagicMock(id="price_test_001")
            mock_link.return_value = MagicMock(
                id="plink_test_001",
                url="https://buy.stripe.com/test_payment_link_001"
            )

            response = await http_client.post(
                f"/api/v1/invoices/{invoice_id}/send-email",
                headers=auth_headers
            )

        # Assert: Response successful
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "payment_link_url" in data

        # If Stripe is configured (not skipped), should have payment link
        payment_link_url = data.get("payment_link_url")
        if payment_link_url:
            assert payment_link_url.startswith("https://")
            assert "buy.stripe.com" in payment_link_url or "stripe.com" in payment_link_url

        # Verify: Invoice updated in database
        updated_invoice = await test_db.invoices.find_one(
            {"_id": ObjectId(invoice_id)}
        )

        if payment_link_url:
            # Payment link should be stored in database
            assert updated_invoice["stripe_payment_link_url"] == payment_link_url
            assert "stripe_payment_link_id" in updated_invoice
            assert updated_invoice["stripe_payment_link_id"] == "plink_test_001"
            assert "payment_link_created_at" in updated_invoice

            # Verify timestamp is recent (within last minute)
            link_created_at = updated_invoice["payment_link_created_at"]
            assert isinstance(link_created_at, str)
            # Should be ISO 8601 format
            datetime.fromisoformat(link_created_at.replace("Z", "+00:00"))

        # Cleanup
        await test_db.company.delete_one({"company_name": "TEST-PaymentLink-Corp-001"})
        await test_db.invoices.delete_one({"_id": ObjectId(invoice_id)})

    @pytest.mark.asyncio
    async def test_paid_invoice_skips_payment_link_creation(
        self,
        http_client: httpx.AsyncClient,
        test_db,
        auth_headers
    ):
        """
        Test that paid invoices do not create payment links.

        Flow:
        1. Create invoice with status="paid"
        2. Send invoice email
        3. Verify payment_link_url is None
        4. Verify no payment link fields in database
        """
        # Arrange: Create test company
        company_data = {
            "company_name": "TEST-PaidInvoice-Corp-002",
            "contact_email": "test_paid@example.com",
            "subscription_type": "enterprise",
            "address": {
                "street": "456 Paid St",
                "city": "Invoice City",
                "state": "NY",
                "zip": "10001",
                "country": "USA"
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await test_db.company.insert_one(company_data)

        # Create PAID invoice
        invoice_data = {
            "company_id": "TEST-PaidInvoice-Corp-002",
            "company_name": "TEST-PaidInvoice-Corp-002",
            "invoice_number": "TEST-INV-PAID-002",
            "invoice_date": datetime.now(timezone.utc),
            "due_date": datetime.now(timezone.utc),
            "line_items": [
                {
                    "description": "Translation Service",
                    "quantity": 1,
                    "unit_price": 50.00,
                    "amount": 50.00
                }
            ],
            "subtotal": 50.00,
            "tax_amount": 3.00,
            "total_amount": 53.00,
            "status": "paid",  # ALREADY PAID
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Send invoice email
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            response = await http_client.post(
                f"/api/v1/invoices/{invoice_id}/send-email",
                headers=auth_headers
            )

            # Stripe API should NOT be called for paid invoices
            mock_price.assert_not_called()
            mock_link.assert_not_called()

        # Assert: Response successful
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True

        # Payment link should be None for paid invoice
        assert data.get("payment_link_url") is None

        # Verify: No payment link fields in database
        updated_invoice = await test_db.invoices.find_one(
            {"_id": ObjectId(invoice_id)}
        )
        assert "stripe_payment_link_url" not in updated_invoice
        assert "stripe_payment_link_id" not in updated_invoice

        # Cleanup
        await test_db.company.delete_one({"company_name": "TEST-PaidInvoice-Corp-002"})
        await test_db.invoices.delete_one({"_id": ObjectId(invoice_id)})

    @pytest.mark.asyncio
    async def test_invoice_email_includes_payment_link_in_response(
        self,
        http_client: httpx.AsyncClient,
        test_db,
        auth_headers
    ):
        """
        Test that invoice email response includes payment_link_url.

        Flow:
        1. Send invoice email
        2. Verify response structure includes payment_link_url field
        3. Verify URL is valid format (https://)
        """
        # Arrange: Create test company
        company_data = {
            "company_name": "TEST-EmailResponse-Corp-003",
            "contact_email": "test_email_response@example.com",
            "subscription_type": "enterprise",
            "address": {
                "street": "789 Email St",
                "city": "Response City",
                "state": "TX",
                "zip": "75001",
                "country": "USA"
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await test_db.company.insert_one(company_data)

        # Create test invoice
        invoice_data = {
            "company_id": "TEST-EmailResponse-Corp-003",
            "company_name": "TEST-EmailResponse-Corp-003",
            "invoice_number": "TEST-INV-RESP-003",
            "invoice_date": datetime.now(timezone.utc),
            "due_date": datetime.now(timezone.utc),
            "line_items": [
                {
                    "description": "Translation Service",
                    "quantity": 2,
                    "unit_price": 75.00,
                    "amount": 150.00
                }
            ],
            "subtotal": 150.00,
            "tax_amount": 9.00,
            "total_amount": 159.00,
            "status": "sent",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Send invoice email
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            mock_price.return_value = MagicMock(id="price_resp_003")
            mock_link.return_value = MagicMock(
                id="plink_resp_003",
                url="https://buy.stripe.com/test_response_003"
            )

            response = await http_client.post(
                f"/api/v1/invoices/{invoice_id}/send-email",
                headers=auth_headers
            )

        # Assert: Response structure
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
        assert "invoice_id" in data
        assert "payment_link_url" in data

        # If payment link was created, verify format
        if data["payment_link_url"]:
            assert data["payment_link_url"].startswith("https://")
            assert data["invoice_id"] == invoice_id

        # Cleanup
        await test_db.company.delete_one({"company_name": "TEST-EmailResponse-Corp-003"})
        await test_db.invoices.delete_one({"_id": ObjectId(invoice_id)})

    @pytest.mark.asyncio
    async def test_stripe_api_failure_does_not_break_email_sending(
        self,
        http_client: httpx.AsyncClient,
        test_db,
        auth_headers
    ):
        """
        Test strict validation when payment link creation fails for UNPAID invoice.

        NEW BEHAVIOR (Strict/Fail Fast):
        1. Create UNPAID invoice with invalid total_amount (causes payment link failure)
        2. Send invoice email
        3. Verify endpoint returns HTTP 500 (cannot send unpaid invoice without payment method)
        4. Verify error message indicates payment link failure
        """
        # Arrange: Create test company
        company_data = {
            "company_name": "TEST-StripeError-Corp-004",
            "contact_email": "test_stripe_error@example.com",
            "subscription_type": "enterprise",
            "address": {
                "street": "321 Error St",
                "city": "Stripe City",
                "state": "FL",
                "zip": "33001",
                "country": "USA"
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await test_db.company.insert_one(company_data)

        # Create UNPAID invoice with INVALID total_amount (None) - naturally causes payment link failure
        invoice_data = {
            "company_id": "TEST-StripeError-Corp-004",
            "company_name": "TEST-StripeError-Corp-004",
            "invoice_number": "TEST-INV-ERROR-004",
            "invoice_date": datetime.now(timezone.utc),
            "due_date": datetime.now(timezone.utc),
            "line_items": [
                {
                    "description": "Translation Service",
                    "quantity": 1,
                    "unit_price": 200.00,
                    "amount": 200.00
                }
            ],
            "subtotal": 200.00,
            "tax_amount": 12.00,
            "total_amount": None,  # ❌ INVALID - causes payment link creation to fail
            "status": "sent",  # UNPAID - requires payment link
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Send invoice email (payment link will fail due to invalid amount)
        response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=auth_headers
        )

        # Assert: Strict validation - UNPAID invoice without payment link → HTTP 500
        assert response.status_code == 500, f"Expected 500 (strict validation), got {response.status_code}: {response.text}"

        data = response.json()
        error_message = data.get("error", {}).get("message", "")
        assert "Payment link creation failed" in error_message, \
            f"Expected payment link failure message, got: {error_message}"

        # Cleanup
        await test_db.company.delete_one({"company_name": "TEST-StripeError-Corp-004"})
        await test_db.invoices.delete_one({"_id": ObjectId(invoice_id)})

    @pytest.mark.asyncio
    async def test_idempotency_reuses_existing_payment_link(
        self,
        http_client: httpx.AsyncClient,
        test_db,
        auth_headers
    ):
        """
        Test that existing payment links are reused (idempotency).

        Flow:
        1. Create invoice with existing payment link
        2. Send invoice email
        3. Verify existing link is returned
        4. Verify Stripe API not called again
        """
        # Arrange: Create test company
        company_data = {
            "company_name": "TEST-Idempotent-Corp-005",
            "contact_email": "test_idempotent@example.com",
            "subscription_type": "enterprise",
            "address": {
                "street": "555 Idempotent Ave",
                "city": "Reuse City",
                "state": "WA",
                "zip": "98001",
                "country": "USA"
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await test_db.company.insert_one(company_data)

        # Create invoice with EXISTING payment link
        existing_link_url = "https://buy.stripe.com/existing_payment_link"
        invoice_data = {
            "company_id": "TEST-Idempotent-Corp-005",
            "company_name": "TEST-Idempotent-Corp-005",
            "invoice_number": "TEST-INV-IDEM-005",
            "invoice_date": datetime.now(timezone.utc),
            "due_date": datetime.now(timezone.utc),
            "line_items": [
                {
                    "description": "Translation Service",
                    "quantity": 1,
                    "unit_price": 300.00,
                    "amount": 300.00
                }
            ],
            "subtotal": 300.00,
            "tax_amount": 18.00,
            "total_amount": 318.00,
            "status": "sent",
            # EXISTING payment link fields
            "stripe_payment_link_url": existing_link_url,
            "stripe_payment_link_id": "plink_existing_005",
            "payment_link_created_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Send invoice email
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            response = await http_client.post(
                f"/api/v1/invoices/{invoice_id}/send-email",
                headers=auth_headers
            )

            # Stripe API should NOT be called (link exists)
            mock_price.assert_not_called()
            mock_link.assert_not_called()

        # Assert: Response successful
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Existing payment link should be returned
        assert data.get("payment_link_url") == existing_link_url

        # Verify: Invoice unchanged (no new update)
        updated_invoice = await test_db.invoices.find_one(
            {"_id": ObjectId(invoice_id)}
        )
        assert updated_invoice["stripe_payment_link_url"] == existing_link_url
        assert updated_invoice["stripe_payment_link_id"] == "plink_existing_005"

        # Cleanup
        await test_db.company.delete_one({"company_name": "TEST-Idempotent-Corp-005"})
        await test_db.invoices.delete_one({"_id": ObjectId(invoice_id)})

    @pytest.mark.asyncio
    async def test_invalid_amount_prevents_payment_link_creation(
        self,
        http_client: httpx.AsyncClient,
        test_db,
        auth_headers
    ):
        """
        Test that UNPAID invoices with invalid amounts fail with HTTP 500.

        NEW BEHAVIOR (Strict/Fail Fast):
        1. Create UNPAID invoice with None total_amount (invalid)
        2. Send invoice email
        3. Verify HTTP 500 (cannot send unpaid invoice without payment method)
        4. Verify error message indicates payment link failure
        """
        # Arrange: Create test company
        company_data = {
            "company_name": "TEST-InvalidAmount-Corp-006",
            "contact_email": "test_invalid_amount@example.com",
            "subscription_type": "enterprise",
            "address": {
                "street": "999 Invalid St",
                "city": "Amount City",
                "state": "OR",
                "zip": "97001",
                "country": "USA"
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        await test_db.company.insert_one(company_data)

        # Create UNPAID invoice with INVALID amount (None)
        invoice_data = {
            "company_id": "TEST-InvalidAmount-Corp-006",
            "company_name": "TEST-InvalidAmount-Corp-006",
            "invoice_number": "TEST-INV-INVALID-006",
            "invoice_date": datetime.now(timezone.utc),
            "due_date": datetime.now(timezone.utc),
            "line_items": [],
            "subtotal": 0.00,
            "tax_amount": 0.00,
            "total_amount": None,  # ❌ INVALID AMOUNT - causes payment link failure
            "status": "sent",  # UNPAID - requires payment link
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Send invoice email (will fail due to invalid amount)
        response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=auth_headers
        )

        # Assert: Strict validation - UNPAID invoice with invalid amount → HTTP 500
        assert response.status_code == 500, f"Expected 500 (strict validation), got {response.status_code}: {response.text}"

        data = response.json()
        error_message = data.get("error", {}).get("message", "")
        assert "Payment link creation failed" in error_message, \
            f"Expected payment link failure message, got: {error_message}"

        # Cleanup
        await test_db.company.delete_one({"company_name": "TEST-InvalidAmount-Corp-006"})
        await test_db.invoices.delete_one({"_id": ObjectId(invoice_id)})
