"""
Integration tests for Invoice Payment Link webhook flow.

This test verifies that when a customer pays an invoice via Stripe Payment Link,
the webhook handler correctly UPDATES the existing invoice instead of creating
a duplicate.

Critical Bug Fix Test:
- Before fix: Webhook created duplicate invoice (original stayed "sent", duplicate was "paid")
- After fix: Webhook updates existing invoice (status changes from "sent" to "paid")
"""

import pytest
from datetime import datetime, timezone
from bson import ObjectId, Decimal128
from unittest.mock import AsyncMock, patch

from app.services.webhook_handler import WebhookHandler


@pytest.mark.asyncio
async def test_payment_link_webhook_updates_existing_invoice(test_db):
    """
    Test that webhook UPDATES existing invoice instead of creating duplicate.

    Flow:
    1. Create invoice with status="sent" and payment link metadata
    2. Simulate payment_intent.succeeded webhook with invoice_id in metadata
    3. Verify existing invoice updated to status="paid"
    4. Verify NO duplicate invoice created
    5. Verify all payment fields updated correctly

    This is the CRITICAL bug fix test.
    """
    # ARRANGE: Create invoice with payment link
    invoice_doc = {
        "invoice_number": "INV-TEST-WEBHOOK-001",
        "company_name": "Test Company LLC",
        "subscription_id": "sub_test_123",
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc),
        "total_amount": Decimal128("100.00"),
        "tax_amount": Decimal128("0.00"),
        "status": "sent",  # Initial status
        "stripe_payment_link_url": "https://buy.stripe.com/test_xxxxx",
        "stripe_payment_link_id": "plink_test_123",
        "payment_link_created_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc)
    }

    result = await test_db.invoices.insert_one(invoice_doc)
    invoice_id = str(result.inserted_id)

    # Verify invoice created
    created_invoice = await test_db.invoices.find_one({"_id": result.inserted_id})
    assert created_invoice is not None
    assert created_invoice["status"] == "sent"
    assert created_invoice["invoice_number"] == "INV-TEST-WEBHOOK-001"

    # Count invoices before webhook (should be 1)
    invoice_count_before = await test_db.invoices.count_documents(
        {"invoice_number": "INV-TEST-WEBHOOK-001"}
    )
    assert invoice_count_before == 1, "Should have exactly 1 invoice before webhook"

    # ACT: Simulate payment_intent.succeeded webhook
    payment_intent_id = "pi_test_webhook_12345"
    webhook_event = {
        "id": "evt_test_webhook_001",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": 10000,  # $100.00 in cents
                "currency": "usd",
                "customer_email": "test-webhook@example.com",
                "metadata": {
                    "invoice_id": invoice_id,
                    "invoice_number": "INV-TEST-WEBHOOK-001"
                }
            }
        }
    }

    # Mock background task to avoid actual file processing
    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock):
        handler = WebhookHandler(test_db)
        result = await handler.handle_event(webhook_event)

    # ASSERT: Verify webhook processed successfully
    assert result["status"] == "processed", f"Webhook processing failed: {result}"

    # CRITICAL: Verify NO duplicate invoice created
    invoice_count_after = await test_db.invoices.count_documents(
        {"invoice_number": "INV-TEST-WEBHOOK-001"}
    )
    assert invoice_count_after == 1, (
        f"CRITICAL BUG: Duplicate invoice created! "
        f"Expected 1 invoice, found {invoice_count_after}"
    )

    # VERIFY: Invoice updated correctly
    updated_invoice = await test_db.invoices.find_one({"_id": ObjectId(invoice_id)})
    assert updated_invoice is not None, "Invoice should still exist"

    # Verify status changed from "sent" to "paid"
    assert updated_invoice["status"] == "paid", (
        f"Invoice status should be 'paid', got '{updated_invoice['status']}'"
    )

    # Verify amount_paid updated
    assert "amount_paid" in updated_invoice, "Invoice should have amount_paid field"
    amount_paid = float(updated_invoice["amount_paid"].to_decimal())
    assert amount_paid == 100.00, f"Expected amount_paid=$100.00, got ${amount_paid}"

    # Verify stripe_payment_intent_id set
    assert "stripe_payment_intent_id" in updated_invoice, "Invoice should have stripe_payment_intent_id"
    assert updated_invoice["stripe_payment_intent_id"] == payment_intent_id, (
        f"Expected payment_intent_id={payment_intent_id}, "
        f"got {updated_invoice['stripe_payment_intent_id']}"
    )

    # Verify paid_at timestamp set
    assert "paid_at" in updated_invoice, "Invoice should have paid_at timestamp"
    assert isinstance(updated_invoice["paid_at"], datetime), "paid_at should be datetime object"

    # Verify original fields unchanged
    assert updated_invoice["invoice_number"] == "INV-TEST-WEBHOOK-001"
    assert updated_invoice["company_name"] == "Test Company LLC"
    assert updated_invoice["stripe_payment_link_url"] == "https://buy.stripe.com/test_xxxxx"

    # VERIFY: Payment record created
    payment = await test_db.payments.find_one({"stripe_payment_intent_id": payment_intent_id})
    assert payment is not None, "Payment record should be created"
    assert payment["status"] == "succeeded" or payment["payment_status"] == "succeeded"

    print(f"✅ TEST PASSED: Invoice {invoice_id} correctly updated (no duplicate created)")


@pytest.mark.asyncio
async def test_payment_link_webhook_handles_missing_invoice_gracefully(test_db):
    """
    Test that webhook handles missing invoice gracefully (doesn't crash).

    Scenario: Payment metadata contains invoice_id that doesn't exist in database.
    Expected: Webhook logs warning, doesn't crash, payment record still created.
    """
    # ACT: Simulate webhook with invoice_id that doesn't exist
    fake_invoice_id = str(ObjectId())  # Valid ObjectId format, but doesn't exist in DB
    payment_intent_id = "pi_test_missing_invoice_123"

    webhook_event = {
        "id": "evt_test_missing_invoice",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": 5000,  # $50.00
                "currency": "usd",
                "customer_email": "test@example.com",
                "metadata": {
                    "invoice_id": fake_invoice_id,
                    "invoice_number": "INV-NONEXISTENT"
                }
            }
        }
    }

    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock):
        handler = WebhookHandler(test_db)
        result = await handler.handle_event(webhook_event)

    # ASSERT: Webhook should still process successfully
    assert result["status"] == "processed", "Webhook should handle missing invoice gracefully"

    # Verify payment record created (even though invoice update failed)
    payment = await test_db.payments.find_one({"stripe_payment_intent_id": payment_intent_id})
    assert payment is not None, "Payment record should still be created"

    # Verify no invoice was created by accident
    invoice_count = await test_db.invoices.count_documents({"invoice_number": "INV-NONEXISTENT"})
    assert invoice_count == 0, "No invoice should be created when metadata points to missing invoice"

    print("✅ TEST PASSED: Webhook handles missing invoice gracefully")


@pytest.mark.asyncio
async def test_legacy_payment_without_invoice_metadata_creates_invoice(test_db):
    """
    Test legacy behavior: Payments without invoice metadata create new invoice.

    This ensures backward compatibility with payments that don't come from Payment Links
    (e.g., direct Stripe Checkout, manual payments, etc.)
    """
    # ACT: Simulate payment without invoice metadata
    payment_intent_id = "pi_test_legacy_no_metadata"

    webhook_event = {
        "id": "evt_test_legacy",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": 7500,  # $75.00
                "currency": "usd",
                "customer_email": "legacy-customer@example.com",
                "metadata": {}  # No invoice_id or invoice_number
            }
        }
    }

    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock):
        handler = WebhookHandler(test_db)
        result = await handler.handle_event(webhook_event)

    # ASSERT: Webhook processed successfully
    assert result["status"] == "processed"

    # Verify NEW invoice created (legacy behavior)
    invoice = await test_db.invoices.find_one({"payment_intent_id": payment_intent_id})
    assert invoice is not None, "Legacy payment should create new invoice"
    assert invoice["status"] == "paid", "New invoice should be marked as paid"

    # Verify invoice has auto-generated invoice_id
    assert "invoice_id" in invoice
    assert invoice["invoice_id"].startswith("INV-"), "Should have auto-generated invoice ID"

    print("✅ TEST PASSED: Legacy payments without metadata create new invoice")


@pytest.mark.asyncio
async def test_payment_link_webhook_idempotency(test_db):
    """
    Test that duplicate webhook events don't cause duplicate updates.

    Scenario: Stripe sends duplicate payment_intent.succeeded webhook (retry).
    Expected: Second webhook skips processing (payment already exists).
    """
    # ARRANGE: Create invoice
    invoice_doc = {
        "invoice_number": "INV-TEST-IDEMPOTENT",
        "company_name": "Idempotent Test LLC",
        "subscription_id": "sub_test_456",
        "invoice_date": datetime.now(timezone.utc),
        "due_date": datetime.now(timezone.utc),
        "total_amount": Decimal128("200.00"),
        "tax_amount": Decimal128("0.00"),
        "status": "sent",
        "stripe_payment_link_url": "https://buy.stripe.com/test_yyyyy",
        "stripe_payment_link_id": "plink_test_456",
        "created_at": datetime.now(timezone.utc)
    }

    result = await test_db.invoices.insert_one(invoice_doc)
    invoice_id = str(result.inserted_id)

    payment_intent_id = "pi_test_idempotent_789"
    webhook_event = {
        "id": "evt_test_idempotent",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": payment_intent_id,
                "amount": 20000,  # $200.00
                "currency": "usd",
                "customer_email": "idempotent@example.com",
                "metadata": {
                    "invoice_id": invoice_id,
                    "invoice_number": "INV-TEST-IDEMPOTENT"
                }
            }
        }
    }

    # ACT: Process webhook FIRST time
    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock):
        handler = WebhookHandler(test_db)
        result1 = await handler.handle_event(webhook_event)

    assert result1["status"] == "processed", "First webhook should process successfully"

    # Verify invoice updated
    invoice_after_first = await test_db.invoices.find_one({"_id": ObjectId(invoice_id)})
    assert invoice_after_first["status"] == "paid"
    first_paid_at = invoice_after_first["paid_at"]

    # ACT: Process DUPLICATE webhook (Stripe retry)
    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock):
        handler2 = WebhookHandler(test_db)
        result2 = await handler2.handle_event(webhook_event)

    # ASSERT: Duplicate webhook handled gracefully
    assert result2["status"] == "duplicate", "Duplicate webhook should be detected"

    # Verify invoice NOT updated again (timestamp unchanged)
    invoice_after_second = await test_db.invoices.find_one({"_id": ObjectId(invoice_id)})
    assert invoice_after_second["status"] == "paid", "Status should still be paid"
    assert invoice_after_second["paid_at"] == first_paid_at, "paid_at should not change on duplicate webhook"

    # Verify still only ONE invoice
    invoice_count = await test_db.invoices.count_documents({"invoice_number": "INV-TEST-IDEMPOTENT"})
    assert invoice_count == 1, "Should still have exactly 1 invoice after duplicate webhook"

    print("✅ TEST PASSED: Duplicate webhooks handled idempotently")
