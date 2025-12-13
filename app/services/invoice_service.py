"""
Invoice service for creating invoices after successful Stripe payments.

This service generates simple payment-based invoices (different from quarterly
subscription invoices handled by invoice_generation_service.py).

Purpose:
- Create invoices immediately after successful Stripe payment_intent.succeeded events
- Store invoice records linked to payment_intent_id
- Generate unique invoice IDs with format: INV-YYYYMMDD-{ObjectId}
- Convert Stripe amounts (cents) to dollars for storage

Usage:
    from app.services.invoice_service import create_invoice_from_payment

    invoice = await create_invoice_from_payment(
        payment_intent_id="pi_1234567890",
        payment_data={
            "amount": 5000,  # cents
            "currency": "usd",
            "customer_email": "user@example.com",
            "metadata": {"order_id": "123"}
        }
    )
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from bson import ObjectId

from app.database.mongodb import database
from app.utils.amount_converter import AmountConverter

logger = logging.getLogger(__name__)


class InvoiceCreationError(Exception):
    """Raised when invoice creation fails."""
    pass


async def create_invoice_from_payment(
    payment_intent_id: str,
    payment_data: dict,
    db = None
) -> Dict[str, Any]:
    """
    Create invoice after successful Stripe payment.

    This function is called by the webhook handler after payment_intent.succeeded
    events to create a permanent invoice record.

    Args:
        payment_intent_id: Stripe payment intent ID (e.g., "pi_1234567890")
        payment_data: Payment details from webhook
            - amount: int (cents) - REQUIRED
            - currency: str (e.g., "usd") - REQUIRED
            - customer_email: str (optional)
            - metadata: dict (optional)
        db: Database instance (defaults to global database if None)

    Returns:
        Invoice document with _id, invoice_id, and all payment details

    Raises:
        InvoiceCreationError: If required fields missing or database operation fails

    Example:
        >>> invoice = await create_invoice_from_payment(
        ...     payment_intent_id="pi_1234567890",
        ...     payment_data={
        ...         "amount": 5000,
        ...         "currency": "usd",
        ...         "customer_email": "user@example.com"
        ...     }
        ... )
        >>> print(invoice["invoice_id"])
        INV-20251209-507f1f77bcf86cd799439011
    """
    logger.info(f"[INVOICE_SERVICE] Creating invoice for payment_intent: {payment_intent_id}")

    # Use provided database or default global database
    invoices_collection = db.invoices if db is not None else database.invoices

    # Validate required fields
    if "amount" not in payment_data:
        error_msg = "Missing required field: amount"
        logger.error(f"[INVOICE_SERVICE] {error_msg}")
        raise InvoiceCreationError(error_msg)

    if "currency" not in payment_data:
        error_msg = "Missing required field: currency"
        logger.error(f"[INVOICE_SERVICE] {error_msg}")
        raise InvoiceCreationError(error_msg)

    # Extract payment data
    amount_cents = payment_data["amount"]
    currency = payment_data["currency"]
    customer_email = payment_data.get("customer_email")
    metadata = payment_data.get("metadata", {})

    # Convert cents to dollars using AmountConverter
    amount_decimal128 = AmountConverter.cents_to_decimal128(amount_cents)
    amount_dollars = AmountConverter.cents_to_dollars(amount_cents)

    logger.info(
        f"[INVOICE_SERVICE] Amount: {amount_cents} cents = ${amount_dollars} {currency.upper()}, "
        f"customer: {customer_email}"
    )

    # Generate unique invoice ID: INV-YYYYMMDD-{ObjectId}
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    object_id = ObjectId()
    invoice_id = f"INV-{date_str}-{object_id}"

    logger.info(f"[INVOICE_SERVICE] Generated invoice_id: {invoice_id}")

    # Create invoice document
    invoice = {
        "invoice_id": invoice_id,
        "payment_intent_id": payment_intent_id,
        "amount": amount_decimal128,
        "currency": currency,
        "status": "paid",
        "customer_email": customer_email,
        "metadata": metadata,
        "created_at": now,
        "paid_at": now
    }

    # Insert into database
    try:
        result = await invoices_collection.insert_one(invoice)
        invoice["_id"] = result.inserted_id

        logger.info(
            f"[INVOICE_SERVICE] Invoice created successfully: {invoice_id} "
            f"(MongoDB _id: {result.inserted_id})"
        )

        return invoice

    except Exception as e:
        error_msg = f"Database error while creating invoice: {str(e)}"
        logger.error(f"[INVOICE_SERVICE] {error_msg}", exc_info=True)
        raise InvoiceCreationError(error_msg)
