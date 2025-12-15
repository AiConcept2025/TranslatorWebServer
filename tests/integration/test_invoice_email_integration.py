"""
Integration tests for invoice email functionality with PDF generation.

Tests the complete flow of:
1. Generating PDF invoices from invoice data
2. Attaching PDFs to emails
3. Sending invoice emails via API endpoint
"""
import pytest
from io import BytesIO
from PyPDF2 import PdfReader
from datetime import datetime


class TestInvoicePDFGeneration:
    """Tests for PDF invoice generation"""

    @pytest.mark.asyncio
    async def test_generate_invoice_pdf(self):
        """Test PDF generation produces valid PDF with correct content."""
        from app.services.invoice_pdf_service import generate_invoice_pdf

        # Arrange: Create test invoice data
        invoice_data = {
            "invoice_number": "INV-TEST-001",
            "company_name": "Test Company LLC",
            "invoice_date": "2025-01-15",
            "due_date": "2025-02-15",
            "line_items": [
                {
                    "description": "Translation Service - Monthly Subscription",
                    "quantity": 1,
                    "unit_price": 100.00,
                    "amount": 100.00
                },
                {
                    "description": "Overage Charges",
                    "quantity": 50,
                    "unit_price": 0.50,
                    "amount": 25.00
                }
            ],
            "subtotal": 125.00,
            "tax_amount": 7.50,
            "total_amount": 132.50
        }

        # Act: Generate PDF
        pdf_buffer = generate_invoice_pdf(invoice_data)

        # Assert: Validate PDF structure
        assert isinstance(pdf_buffer, BytesIO), "PDF buffer should be BytesIO instance"
        assert len(pdf_buffer.getvalue()) > 0, "PDF buffer should contain data"

        # Validate PDF is readable
        pdf_reader = PdfReader(pdf_buffer)
        assert len(pdf_reader.pages) >= 1, "PDF should have at least one page"

        # Validate PDF content contains key invoice data
        page_text = pdf_reader.pages[0].extract_text()
        assert "INV-TEST-001" in page_text, "PDF should contain invoice number"
        assert "Test Company LLC" in page_text, "PDF should contain company name"
        assert "Translation Service" in page_text, "PDF should contain service description"
        assert "132.50" in page_text or "132.5" in page_text, "PDF should contain total amount"

    @pytest.mark.asyncio
    async def test_generate_invoice_pdf_with_minimal_data(self):
        """Test PDF generation with minimal invoice data."""
        from app.services.invoice_pdf_service import generate_invoice_pdf

        # Arrange: Minimal invoice data
        invoice_data = {
            "invoice_number": "INV-MIN-001",
            "company_name": "Minimal Corp",
            "invoice_date": "2025-01-01",
            "due_date": "2025-02-01",
            "line_items": [
                {"description": "Service", "quantity": 1, "unit_price": 50.00, "amount": 50.00}
            ],
            "subtotal": 50.00,
            "tax_amount": 3.00,
            "total_amount": 53.00
        }

        # Act: Generate PDF
        pdf_buffer = generate_invoice_pdf(invoice_data)

        # Assert: PDF is valid
        assert isinstance(pdf_buffer, BytesIO)
        pdf_buffer.seek(0)
        pdf_reader = PdfReader(pdf_buffer)
        assert len(pdf_reader.pages) >= 1

    @pytest.mark.asyncio
    async def test_generate_invoice_pdf_with_multiple_line_items(self):
        """Test PDF generation with multiple line items."""
        from app.services.invoice_pdf_service import generate_invoice_pdf

        # Arrange: Invoice with many line items
        invoice_data = {
            "invoice_number": "INV-MULTI-001",
            "company_name": "Multi Corp",
            "invoice_date": "2025-01-01",
            "due_date": "2025-02-01",
            "line_items": [
                {"description": f"Service {i}", "quantity": i, "unit_price": 10.00, "amount": i * 10.00}
                for i in range(1, 11)  # 10 line items
            ],
            "subtotal": sum(i * 10.00 for i in range(1, 11)),
            "tax_amount": sum(i * 10.00 for i in range(1, 11)) * 0.06,
            "total_amount": sum(i * 10.00 for i in range(1, 11)) * 1.06
        }

        # Act: Generate PDF
        pdf_buffer = generate_invoice_pdf(invoice_data)

        # Assert: PDF is valid and contains all items
        assert isinstance(pdf_buffer, BytesIO)
        pdf_buffer.seek(0)
        pdf_reader = PdfReader(pdf_buffer)
        assert len(pdf_reader.pages) >= 1

        # Verify at least some line items are present
        page_text = pdf_reader.pages[0].extract_text()
        assert "Service 1" in page_text or "Service" in page_text


class TestInvoiceEmailEndpoint:
    """Tests for invoice email API endpoint"""

    @pytest.mark.asyncio
    async def test_send_invoice_email_endpoint(self, http_client, test_db, auth_headers):
        """Test API endpoint sends invoice email successfully."""
        # Arrange: Create test company
        company_data = {
            "company_name": "Test Email Corp",
            "contact_email": "test_invoice@example.com",
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
                    "unit_price": 100.00,
                    "amount": 100.00
                }
            ],
            "subtotal": 100.00,
            "tax_amount": 6.00,
            "total_amount": 106.00,
            "status": "sent"
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Call send email endpoint
        response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=auth_headers
        )

        # Assert: Response is successful
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert "test_invoice@example.com" in data["message"]
        assert invoice_id in data["invoice_id"]

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
        invoice_data = {
            "company_id": company_id,
            "invoice_number": "INV-NO-EMAIL-001",
            "company_name": "No Email Corp",
            "invoice_date": "2025-01-15",
            "due_date": "2025-02-15",
            "line_items": [{"description": "Service", "quantity": 1, "unit_price": 50.00, "amount": 50.00}],
            "subtotal": 50.00,
            "tax_amount": 3.00,
            "total_amount": 53.00
        }
        invoice_result = await test_db.invoices.insert_one(invoice_data)
        invoice_id = str(invoice_result.inserted_id)

        # Act: Call endpoint
        response = await http_client.post(
            f"/api/v1/invoices/{invoice_id}/send-email",
            headers=auth_headers
        )

        # Assert: 400 error
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
