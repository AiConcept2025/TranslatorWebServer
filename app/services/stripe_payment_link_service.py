"""
Stripe Payment Link Service for generating payment links for invoices.

This service creates Stripe Payment Links that allow customers to pay invoices
through a hosted Stripe checkout page. It handles:
- Idempotency (reuses existing links)
- Amount conversion (Decimal128 to cents)
- Graceful error handling (returns None on failure)
- Database updates with payment link metadata
"""

import logging
import stripe
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from bson import Decimal128

from app.config import settings

logger = logging.getLogger(__name__)

# Configure Stripe with API key from settings
stripe.api_key = settings.stripe_secret_key


class StripePaymentLinkService:
    """Service for creating and managing Stripe Payment Links for invoices."""

    def __init__(self):
        """Initialize Stripe Payment Link Service."""
        logger.info("[PAYMENT_LINK] StripePaymentLinkService initialized")

    def _convert_to_cents(self, amount: Any) -> Optional[int]:
        """
        Convert amount to cents for Stripe API.

        Args:
            amount: Amount to convert (Decimal128, float, int, or None)

        Returns:
            Amount in cents (int) or None if conversion fails

        Example:
            100.50 → 10050
            Decimal128("99.99") → 9999
        """
        try:
            if amount is None:
                logger.warning("[PAYMENT_LINK] Amount is None, cannot convert to cents")
                return None

            # Handle Decimal128 from MongoDB
            if isinstance(amount, Decimal128):
                amount = float(amount.to_decimal())

            # Convert to cents (multiply by 100 and round to integer)
            cents = int(round(float(amount) * 100))

            if cents <= 0:
                logger.warning(f"[PAYMENT_LINK] Invalid amount: {amount} (converted to {cents} cents)")
                return None

            return cents

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"[PAYMENT_LINK] Failed to convert amount to cents: {amount}, error: {e}", exc_info=True)
            return None

    async def create_or_get_payment_link(
        self,
        invoice: Dict[str, Any],
        db: Any
    ) -> Optional[str]:
        """
        Create or retrieve existing Stripe Payment Link for an invoice.

        Features:
        - Idempotency: Returns existing link if already created
        - Skip paid invoices: Returns None for paid invoices
        - Graceful errors: Returns None on failure (doesn't crash)

        Args:
            invoice: Invoice document from MongoDB (dict)
            db: Database connection for updating invoice

        Returns:
            Payment link URL (str) or None if:
            - Invoice is already paid
            - Link creation failed
            - Invalid invoice data

        Side Effects:
            Updates invoice in database with:
            - stripe_payment_link_url
            - stripe_payment_link_id
            - payment_link_created_at
        """
        try:
            invoice_number = invoice.get("invoice_number", "UNKNOWN")
            invoice_id = str(invoice.get("_id", "UNKNOWN"))
            status = invoice.get("status", "unknown")
            total_amount = invoice.get("total_amount")

            logger.info(f"[PAYMENT_LINK] Processing invoice {invoice_number} (status: {status})")

            # 1. Check if link already exists (idempotency)
            existing_url = invoice.get("stripe_payment_link_url")
            if existing_url:
                logger.info(f"[PAYMENT_LINK] Invoice {invoice_number} already has payment link: {existing_url}")
                return existing_url

            # 2. Skip paid invoices
            if status == "paid":
                logger.info(f"[PAYMENT_LINK] Invoice {invoice_number} is already paid, skipping payment link creation")
                return None

            # 3. Validate and convert amount
            amount_cents = self._convert_to_cents(total_amount)
            if amount_cents is None:
                logger.error(f"[PAYMENT_LINK] Invalid total_amount for invoice {invoice_number}: {total_amount}")
                return None

            logger.info(f"[PAYMENT_LINK] Creating payment link for invoice {invoice_number}: ${total_amount} ({amount_cents} cents)")

            # 4. Create Stripe Price object
            price = stripe.Price.create(
                currency="usd",
                unit_amount=amount_cents,
                product_data={
                    "name": f"Invoice {invoice_number}"
                }
            )

            logger.info(f"[PAYMENT_LINK] Created Stripe Price: {price.id} for invoice {invoice_number}")

            # 5. Create Stripe Payment Link (restricted to card payments only for enterprise invoices)
            payment_link = stripe.PaymentLink.create(
                line_items=[{
                    "price": price.id,
                    "quantity": 1
                }],
                payment_method_types=["card"],  # Only allow credit/debit card payments
                metadata={
                    "invoice_id": invoice_id,
                    "invoice_number": invoice_number
                }
            )

            logger.info(f"[PAYMENT_LINK] Created Stripe Payment Link: {payment_link.id} → {payment_link.url}")

            # 6. Update invoice in database
            update_result = await db.invoices.update_one(
                {"_id": invoice["_id"]},
                {
                    "$set": {
                        "stripe_payment_link_url": payment_link.url,
                        "stripe_payment_link_id": payment_link.id,
                        "payment_link_created_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )

            if update_result.modified_count > 0:
                logger.info(f"[PAYMENT_LINK] Updated invoice {invoice_number} with payment link metadata")
            else:
                logger.warning(f"[PAYMENT_LINK] Failed to update invoice {invoice_number} in database")

            return payment_link.url

        except stripe.StripeError as e:
            # Stripe API errors (authentication, rate limits, invalid requests)
            logger.error(
                f"[PAYMENT_LINK] Stripe API error for invoice {invoice.get('invoice_number', 'UNKNOWN')}: {str(e)}",
                exc_info=True
            )
            return None

        except Exception as e:
            # Unexpected errors (database errors, network issues, etc.)
            logger.error(
                f"[PAYMENT_LINK] Unexpected error for invoice {invoice.get('invoice_number', 'UNKNOWN')}: {str(e)}",
                exc_info=True
            )
            return None


# Singleton instance
stripe_payment_link_service = StripePaymentLinkService()
