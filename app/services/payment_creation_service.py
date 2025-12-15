"""
Centralized PaymentService for atomic payment creation with idempotency.

This service consolidates payment creation logic from multiple locations:
- payment_simplified.py (lines 149-166, 676-689)
- webhook_handler.py (lines 264-278)

Uses atomic MongoDB upsert to prevent race conditions and duplicate payments.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.database.mongodb import database

logger = logging.getLogger(__name__)


class PaymentCreationService:
    """
    Service for creating or updating payment records with idempotency.

    This service uses atomic MongoDB upsert operations to ensure that:
    1. Duplicate payment intents don't create multiple records
    2. Concurrent webhook/API calls are handled safely
    3. Payment creation is idempotent (safe to retry)
    """

    async def create_or_update_payment(
        self,
        payment_intent_id: str,
        amount_cents: int,
        currency: str,
        customer_email: str,
        webhook_event_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        company_name: Optional[str] = None,
        db = None
    ) -> Dict[str, Any]:
        """
        Atomic payment creation with idempotency using MongoDB upsert.

        This method uses $setOnInsert to ensure that only the FIRST call
        creates the payment record. Subsequent calls with the same payment_intent_id
        will detect the existing record and skip creation.

        Args:
            payment_intent_id: Stripe payment intent ID (unique identifier)
            amount_cents: Payment amount in cents
            currency: Currency code (e.g., "USD", "EUR")
            customer_email: Customer email address
            webhook_event_id: Optional webhook event ID for tracking
            metadata: Optional additional metadata
            company_name: Optional company name (for enterprise users)
            db: Optional database instance (uses global database if not provided)

        Returns:
            {
                "created": bool,  # True if new payment, False if already existed
                "payment": dict   # The payment document
            }

        Raises:
            ValueError: If payment_intent_id is empty or amount_cents <= 0

        Example:
            >>> service = PaymentCreationService()
            >>> result = await service.create_or_update_payment(
            ...     payment_intent_id="pi_1234567890",
            ...     amount_cents=1500,
            ...     currency="USD",
            ...     customer_email="user@example.com"
            ... )
            >>> result["created"]
            True
            >>> result["payment"]["amount"]
            1500
        """
        # Validate inputs
        if not payment_intent_id or not payment_intent_id.strip():
            raise ValueError("payment_intent_id cannot be empty")

        if amount_cents <= 0:
            raise ValueError(f"amount_cents must be greater than 0, got {amount_cents}")

        # Default currency to USD if None
        if not currency:
            currency = "usd"

        # Normalize currency to uppercase
        currency = currency.upper()

        logger.info(
            f"[PaymentCreationService] Creating/updating payment: "
            f"payment_intent_id={payment_intent_id}, "
            f"amount_cents={amount_cents}, "
            f"currency={currency}, "
            f"customer_email={customer_email}"
        )

        # Use provided db or fallback to global database
        payments_collection = db.payments if db is not None else database.payments

        # Build payment document
        payment_doc = {
            "stripe_payment_intent_id": payment_intent_id,
            "amount": amount_cents,
            "currency": currency,
            "user_email": customer_email,
            "status": "succeeded",
            "payment_status": "succeeded",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "payment_date": datetime.now(timezone.utc),
            "refunds": []  # Always start with empty refunds array
        }

        # Add optional fields
        if company_name:
            payment_doc["company_name"] = company_name

        if webhook_event_id:
            payment_doc["webhook_event_id"] = webhook_event_id

        if metadata:
            payment_doc["metadata"] = metadata

        # Atomic upsert: Only inserts if payment_intent_id doesn't exist
        try:
            result = await payments_collection.update_one(
                {"stripe_payment_intent_id": payment_intent_id},
                {"$setOnInsert": payment_doc},
                upsert=True
            )

            # Check if this was a new payment or existing one
            if result.matched_count > 0:
                # Payment already existed - another process got here first
                logger.info(
                    f"[PaymentCreationService] Duplicate payment detected for "
                    f"{payment_intent_id}, skipping creation"
                )

                # Fetch the existing payment
                existing_payment = await payments_collection.find_one(
                    {"stripe_payment_intent_id": payment_intent_id}
                )

                return {
                    "created": False,
                    "payment": existing_payment
                }

            # New payment was created
            logger.info(
                f"[PaymentCreationService] Successfully created new payment "
                f"for {payment_intent_id}"
            )

            # Fetch the newly created payment
            new_payment = await payments_collection.find_one(
                {"stripe_payment_intent_id": payment_intent_id}
            )

            return {
                "created": True,
                "payment": new_payment
            }

        except Exception as e:
            logger.error(
                f"[PaymentCreationService] Error creating/updating payment "
                f"for {payment_intent_id}: {e}",
                exc_info=True
            )
            raise

    async def get_payment_by_intent_id(
        self,
        payment_intent_id: str,
        db = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a payment by its Stripe payment intent ID.

        Args:
            payment_intent_id: Stripe payment intent ID
            db: Optional database instance (uses global database if not provided)

        Returns:
            Payment document or None if not found

        Example:
            >>> service = PaymentCreationService()
            >>> payment = await service.get_payment_by_intent_id("pi_1234567890")
            >>> payment["amount"]
            1500
        """
        if not payment_intent_id or not payment_intent_id.strip():
            raise ValueError("payment_intent_id cannot be empty")

        # Use provided db or fallback to global database
        payments_collection = db.payments if db is not None else database.payments

        try:
            payment = await payments_collection.find_one(
                {"stripe_payment_intent_id": payment_intent_id}
            )
            return payment
        except Exception as e:
            logger.error(
                f"[PaymentCreationService] Error fetching payment "
                f"for {payment_intent_id}: {e}",
                exc_info=True
            )
            return None


# Global service instance
payment_creation_service = PaymentCreationService()
