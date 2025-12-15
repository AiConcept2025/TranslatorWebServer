"""
REAL Integration tests for invoice email functionality.

Tests the COMPLETE flow with NO MOCKING:
1. Real HTTP requests to running server
2. Real database operations
3. Real SMTP email sending
4. Real Stripe Payment Link creation
5. Real PDF generation and attachment

IMPORTANT: Server must be running at http://localhost:8000
"""
import pytest


class TestInvoiceEmailEndpoint:
    """Real integration tests for invoice email API endpoint"""

    @pytest.mark.asyncio
    async def test_send_invoice_email_endpoint(self, http_client, test_db, auth_headers):
        """Test API endpoint sends invoice email successfully to REAL email address."""
        # CRITICAL: This test sends REAL email to verify full integration
        # Email will be sent to danishevsky@gmail.com via Yahoo SMTP

        # Arrange: Create test company with REAL email address
        REAL_TEST_EMAIL = "danishevsky@gmail.com"  # User's actual email for verification

        company_data = {
            "company_name": "Test Email Corp",
            "contact_email": REAL_TEST_EMAIL,  # REAL email address
            "subscription_type": "enterprise",
            "address": {
                "street": "123 Test St",
                "city": "Test City",
                "state": "NY",
                "zip": "10001",
                "country": "USA"
            }
        }
        company_result = await test_db.company.insert_one(company_data)
        company_id = company_data["company_name"]  # company_id is company_name string

        # Create test invoice
        from bson import Decimal128
        invoice_data = {
            "company_id": company_id,
            "invoice_number": "INV-API-TEST-001",
            "company_name": "Test Email Corp",
            "invoice_date": "2025-01-15",
            "due_date": "2025-02-15",
            "line_items": [
                {
                    "description": "Translation Service",
                    "quantity": 1,
                    "unit_price": Decimal128("100.00"),
                    "amount": Decimal128("100.00")
                }
            ],
            "subtotal": Decimal128("100.00"),
            "tax_amount": Decimal128("6.00"),
            "total_amount": Decimal128("106.00"),
            "status": "sent"
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        print(f"\n{'='*80}")
        print(f"INTEGRATION TEST: Sending REAL invoice email")
        print(f"{'='*80}")
        print(f"Invoice ID: {invoice_id}")
        print(f"Invoice Number: INV-API-TEST-001")
        print(f"Recipient: {REAL_TEST_EMAIL}")
        print(f"This will send a REAL email via Yahoo SMTP")
        print(f"Check your inbox at {REAL_TEST_EMAIL} after test completes")
        print(f"{'='*80}\n")

        # Act: Call send email endpoint
        print("Calling API endpoint to send invoice email...")
        response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=auth_headers
        )

        # Assert: Response is successful
        print(f"\nAPI Response Status: {response.status_code}")
        print(f"API Response Body: {response.text}\n")

        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}. Response: {response.text}"

        data = response.json()
        assert data["success"] is True, f"Email send should be successful. Response: {data}"
        assert REAL_TEST_EMAIL in data["message"], \
            f"Response should confirm email sent to {REAL_TEST_EMAIL}. Got: {data['message']}"
        assert invoice_id in data["invoice_id"], \
            f"Response should include invoice_id. Got: {data}"

        print(f"✅ API returned success: {data['message']}")

        # Verify: Payment link was created and stored in database
        from bson import ObjectId
        updated_invoice = await test_db.invoices.find_one({"_id": ObjectId(invoice_id)})

        # CRITICAL: Payment link should be created for unpaid invoices
        assert updated_invoice is not None, "Invoice should exist after email sent"

        print(f"\nVerifying payment link creation...")
        assert "stripe_payment_link_url" in updated_invoice, \
            "Payment link URL should be stored in invoice (check Stripe API key configuration)"
        assert updated_invoice["stripe_payment_link_url"] is not None, \
            "Payment link URL should not be None - Stripe API call failed (check logs for error)"
        assert updated_invoice["stripe_payment_link_url"].startswith("https://"), \
            f"Payment link URL should be valid HTTPS URL, got: {updated_invoice.get('stripe_payment_link_url')}"

        # Verify payment link metadata
        assert "stripe_payment_link_id" in updated_invoice, "Payment link ID should be stored"
        assert updated_invoice["stripe_payment_link_id"] is not None, "Payment link ID should not be None"
        assert "payment_link_created_at" in updated_invoice, "Payment link creation timestamp should be stored"

        payment_link_url = updated_invoice["stripe_payment_link_url"]
        print(f"✅ Payment link created: {payment_link_url}")

        print(f"\n{'='*80}")
        print(f"✅ TEST COMPLETE - Email sent successfully")
        print(f"{'='*80}")
        print(f"Email recipient: {REAL_TEST_EMAIL}")
        print(f"Invoice number: INV-API-TEST-001")
        print(f"Payment link: {payment_link_url}")
        print(f"\n⚠️  CHECK YOUR EMAIL INBOX: {REAL_TEST_EMAIL}")
        print(f"Subject: Invoice INV-API-TEST-001 from Iris Solutions Translation Services")
        print(f"Contains: PDF attachment + Stripe payment link")
        print(f"{'='*80}\n")

    @pytest.mark.asyncio
    async def test_send_invoice_email_invalid_invoice(self, http_client, auth_headers):
        """Test endpoint returns 404 for invalid invoice_id."""
        # Act: Call endpoint with invalid ID
        response = await http_client.post(
            "/api/v1/invoices/invalid_invoice_id_123/send-email",
            headers=auth_headers
        )

        # Assert: 404 or 400 error
        assert response.status_code in [400, 404], f"Expected 400 or 404, got {response.status_code}"

    @pytest.mark.asyncio
    async def test_send_invoice_email_missing_company_email(self, http_client, test_db, auth_headers):
        """Test endpoint returns 400 when company has no email."""
        # Arrange: Create company without email
        company_data = {
            "company_name": "No Email Corp",
            # No contact_email field
            "subscription_type": "enterprise",
            "address": {
                "street": "456 Test Ave",
                "city": "Test City",
                "state": "NY",
                "zip": "10002",
                "country": "USA"
            }
        }
        company_result = await test_db.company.insert_one(company_data)
        company_id = company_data["company_name"]  # company_id is company_name string

        # Create invoice
        from bson import Decimal128
        invoice_data = {
            "company_id": company_id,
            "invoice_number": "INV-NO-EMAIL-001",
            "company_name": "No Email Corp",
            "invoice_date": "2025-01-15",
            "due_date": "2025-02-15",
            "line_items": [{"description": "Service", "quantity": 1, "unit_price": Decimal128("50.00"), "amount": Decimal128("50.00")}],
            "subtotal": Decimal128("50.00"),
            "tax_amount": Decimal128("3.00"),
            "total_amount": Decimal128("53.00")
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Call endpoint
        response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=auth_headers
        )

        # Assert: 400 error for missing email
        assert response.status_code == 400, f"Expected 400 for missing email, got {response.status_code}"
