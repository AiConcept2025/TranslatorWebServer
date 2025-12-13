"""
Integration tests for invoice_service.py - Payment-based invoice creation.

Tests verify invoice creation after successful Stripe payments with:
- Real MongoDB test database (translation_test)
- Invoice ID generation (INV-YYYYMMDD-{ObjectId} format)
- Amount conversion (cents to dollars with Decimal128)
- Required field validation
- Database operations and error handling

Setup:
    DATABASE_MODE=test pytest tests/integration/test_invoice_service_integration.py -v

Test Coverage:
- Invoice creation with all fields
- Invoice creation with minimal fields
- Amount conversion (cents to Decimal128)
- Invoice ID uniqueness
- Error handling (missing required fields)
- Database error handling
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from bson import Decimal128, ObjectId

from app.services.invoice_service import create_invoice_from_payment, InvoiceCreationError


# Prefix for test data cleanup
TEST_PREFIX = "TEST_INVOICE_"


@pytest.fixture(autouse=True)
async def cleanup(test_db):
    """Clean up test invoices after each test."""
    yield
    # Delete test invoices with TEST_ prefix in payment_intent_id
    await test_db.invoices.delete_many({
        "payment_intent_id": {"$regex": f"^{TEST_PREFIX}"}
    })


@pytest.mark.asyncio
async def test_create_invoice_with_all_fields(test_db):
    """
    Test invoice creation with all optional fields populated.

    Verifies:
    - Invoice document created in database
    - Invoice ID format: INV-YYYYMMDD-{ObjectId}
    - Amount conversion: 5000 cents → $50.00 Decimal128
    - All fields stored correctly (customer_email, metadata)
    - Status defaults to "paid"
    - Timestamps created correctly
    """
    # ARRANGE
    payment_intent_id = f"{TEST_PREFIX}pi_full_fields"
    payment_data = {
        "amount": 5000,  # $50.00
        "currency": "usd",
        "customer_email": "user@example.com",
        "metadata": {
            "order_id": "order_123",
            "product": "Translation Service"
        }
    }

    # ACT
    invoice = await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)

    # ASSERT - Response structure
    assert invoice is not None
    assert "_id" in invoice
    assert "invoice_id" in invoice

    # ASSERT - Invoice ID format (INV-YYYYMMDD-{ObjectId})
    invoice_id = invoice["invoice_id"]
    assert invoice_id.startswith("INV-")
    parts = invoice_id.split("-")
    assert len(parts) == 3, f"Expected 3 parts, got: {parts}"
    assert len(parts[1]) == 8, f"Date should be YYYYMMDD, got: {parts[1]}"
    assert len(parts[2]) == 24, f"ObjectId should be 24 chars, got: {parts[2]}"

    # ASSERT - Payment details
    assert invoice["payment_intent_id"] == payment_intent_id
    assert invoice["currency"] == "usd"
    assert invoice["status"] == "paid"
    assert invoice["customer_email"] == "user@example.com"

    # ASSERT - Metadata
    assert invoice["metadata"]["order_id"] == "order_123"
    assert invoice["metadata"]["product"] == "Translation Service"

    # ASSERT - Amount conversion (cents to Decimal128)
    assert isinstance(invoice["amount"], Decimal128)
    amount_decimal = invoice["amount"].to_decimal()
    assert amount_decimal == Decimal("50.00")

    # ASSERT - Timestamps
    assert "created_at" in invoice
    assert "paid_at" in invoice
    assert isinstance(invoice["created_at"], datetime)
    assert isinstance(invoice["paid_at"], datetime)

    # VERIFY - Database record
    db_invoice = await test_db.invoices.find_one({"invoice_id": invoice_id})
    assert db_invoice is not None
    assert db_invoice["payment_intent_id"] == payment_intent_id
    assert db_invoice["customer_email"] == "user@example.com"


@pytest.mark.asyncio
async def test_create_invoice_minimal_fields(test_db):
    """
    Test invoice creation with only required fields.

    Verifies:
    - Invoice created with just amount and currency
    - Optional fields (customer_email, metadata) default to None/empty
    - Amount conversion works with minimal data
    """
    # ARRANGE
    payment_intent_id = f"{TEST_PREFIX}pi_minimal"
    payment_data = {
        "amount": 2500,  # $25.00
        "currency": "usd"
        # No customer_email, no metadata
    }

    # ACT
    invoice = await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)

    # ASSERT - Basic structure
    assert invoice is not None
    assert invoice["payment_intent_id"] == payment_intent_id
    assert invoice["currency"] == "usd"

    # ASSERT - Amount conversion
    amount_decimal = invoice["amount"].to_decimal()
    assert amount_decimal == Decimal("25.00")

    # ASSERT - Optional fields
    assert invoice["customer_email"] is None
    assert invoice["metadata"] == {}

    # VERIFY - Database
    db_invoice = await test_db.invoices.find_one({"payment_intent_id": payment_intent_id})
    assert db_invoice is not None


@pytest.mark.asyncio
async def test_amount_conversion_various_amounts(test_db):
    """
    Test amount conversion for various amounts in cents.

    Verifies:
    - Small amounts: 99 cents → $0.99
    - Large amounts: 999999 cents → $9999.99
    - Zero amounts: 0 cents → $0.00
    - Precision maintained with Decimal128
    """
    test_cases = [
        (99, Decimal("0.99")),      # 99 cents
        (1000, Decimal("10.00")),   # $10.00
        (12345, Decimal("123.45")), # $123.45
        (999999, Decimal("9999.99")),  # $9999.99
        (0, Decimal("0.00"))        # $0.00
    ]

    for amount_cents, expected_dollars in test_cases:
        # ARRANGE
        payment_intent_id = f"{TEST_PREFIX}pi_amount_{amount_cents}"
        payment_data = {
            "amount": amount_cents,
            "currency": "usd"
        }

        # ACT
        invoice = await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)

        # ASSERT
        amount_decimal = invoice["amount"].to_decimal()
        assert amount_decimal == expected_dollars, \
            f"Expected {expected_dollars}, got {amount_decimal} for {amount_cents} cents"


@pytest.mark.asyncio
async def test_invoice_id_uniqueness(test_db):
    """
    Test that each invoice gets a unique invoice_id.

    Verifies:
    - Multiple invoices created for same payment_intent_id get different invoice_ids
    - Invoice IDs use ObjectId for uniqueness
    - Date portion is current date
    """
    # ARRANGE
    payment_intent_id = f"{TEST_PREFIX}pi_uniqueness"
    payment_data = {
        "amount": 1000,
        "currency": "usd"
    }

    # ACT - Create 3 invoices with same payment_intent_id
    invoice1 = await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)
    invoice2 = await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)
    invoice3 = await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)

    # ASSERT - All invoice_ids are different
    invoice_ids = [invoice1["invoice_id"], invoice2["invoice_id"], invoice3["invoice_id"]]
    assert len(set(invoice_ids)) == 3, "Invoice IDs should be unique"

    # ASSERT - Date portion is today
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    for invoice_id in invoice_ids:
        assert invoice_id.startswith(f"INV-{today}-")


@pytest.mark.asyncio
async def test_error_missing_amount(test_db):
    """
    Test error handling when amount is missing.

    Verifies:
    - InvoiceCreationError raised
    - Error message indicates missing field
    - No invoice created in database
    """
    # ARRANGE
    payment_intent_id = f"{TEST_PREFIX}pi_no_amount"
    payment_data = {
        "currency": "usd"
        # Missing amount
    }

    # ACT & ASSERT
    with pytest.raises(InvoiceCreationError) as exc_info:
        await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)

    assert "amount" in str(exc_info.value).lower()

    # VERIFY - No invoice created
    db_invoice = await test_db.invoices.find_one({"payment_intent_id": payment_intent_id})
    assert db_invoice is None


@pytest.mark.asyncio
async def test_error_missing_currency(test_db):
    """
    Test error handling when currency is missing.

    Verifies:
    - InvoiceCreationError raised
    - Error message indicates missing field
    - No invoice created in database
    """
    # ARRANGE
    payment_intent_id = f"{TEST_PREFIX}pi_no_currency"
    payment_data = {
        "amount": 5000
        # Missing currency
    }

    # ACT & ASSERT
    with pytest.raises(InvoiceCreationError) as exc_info:
        await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)

    assert "currency" in str(exc_info.value).lower()

    # VERIFY - No invoice created
    db_invoice = await test_db.invoices.find_one({"payment_intent_id": payment_intent_id})
    assert db_invoice is None


@pytest.mark.asyncio
async def test_multiple_currencies(test_db):
    """
    Test invoice creation with different currencies.

    Verifies:
    - Currency stored correctly
    - Amount conversion works regardless of currency
    """
    currencies = ["usd", "eur", "gbp"]

    for currency in currencies:
        # ARRANGE
        payment_intent_id = f"{TEST_PREFIX}pi_{currency}"
        payment_data = {
            "amount": 3000,  # 30.00
            "currency": currency
        }

        # ACT
        invoice = await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)

        # ASSERT
        assert invoice["currency"] == currency
        assert invoice["amount"].to_decimal() == Decimal("30.00")


@pytest.mark.asyncio
async def test_invoice_returned_has_mongodb_id(test_db):
    """
    Test that returned invoice includes MongoDB _id.

    Verifies:
    - _id field present in returned document
    - _id is ObjectId type
    - _id matches database record
    """
    # ARRANGE
    payment_intent_id = f"{TEST_PREFIX}pi_id_check"
    payment_data = {
        "amount": 1500,
        "currency": "usd"
    }

    # ACT
    invoice = await create_invoice_from_payment(payment_intent_id, payment_data, db=test_db)

    # ASSERT - _id in response
    assert "_id" in invoice
    assert isinstance(invoice["_id"], ObjectId)

    # VERIFY - _id matches database
    db_invoice = await test_db.invoices.find_one({"_id": invoice["_id"]})
    assert db_invoice is not None
    assert db_invoice["invoice_id"] == invoice["invoice_id"]
