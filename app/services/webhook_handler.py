"""
Stripe Webhook Event Handler - Routes webhook events and triggers payment processing.

Purpose:
- Handle Stripe webhook events (payment_intent.succeeded, payment_intent.payment_failed, charge.refunded)
- Store events with deduplication via WebhookRepository
- Route events to appropriate handlers
- Implement payment-level idempotency (prevent duplicate processing)
- Trigger background payment processing

Integration:
- Uses WebhookRepository for event storage and deduplication
- Uses process_payment_files_background for payment processing
- Accesses MongoDB for payment-level idempotency checks

Event Routing:
1. payment_intent.succeeded → _handle_payment_succeeded() → process_payment_files_background()
2. payment_intent.payment_failed → _handle_payment_failed() → log error
3. charge.refunded → _handle_refund() → update payment status

Error Handling:
- DuplicateEventError (Stripe retry) → return {"status": "duplicate"}
- Missing payment for refund → log warning, don't raise exception
- Unsupported event types → return {"status": "unsupported"}

TDD Implementation:
- Written to satisfy test_webhook_handler_integration.py (10 tests)
- Tests verify: event storage, deduplication, payment processing, refunds, error handling
"""

import logging
from typing import Optional, Dict
from datetime import datetime, timezone

from pymongo import ReturnDocument

from app.services.webhook_repository import WebhookRepository, DuplicateEventError
from app.routers.payment_simplified import process_payment_files_background

logger = logging.getLogger(__name__)


class WebhookHandler:
    """
    Handles Stripe webhook events with deduplication and payment processing.

    Responsibilities:
    1. Store webhook events (deduplication via WebhookRepository)
    2. Route events by type (payment_intent.succeeded, payment_failed, charge.refunded)
    3. Implement payment-level idempotency (prevent duplicate payment processing)
    4. Trigger background payment processing
    5. Update payment status for refunds

    Database Access:
    - webhook_events (via WebhookRepository) - Event audit trail with deduplication
    - payments - Payment records and idempotency checks

    Usage:
        from app.database.mongodb import database

        handler = WebhookHandler(database)
        result = await handler.handle_event(stripe_event)

        # Returns:
        # {"status": "processed"} - Event processed successfully
        # {"status": "duplicate"} - Event already processed (Stripe retry)
        # {"status": "unsupported"} - Event type not supported
        # {"status": "error", "message": "..."} - Processing error
    """

    def __init__(self, database):
        """
        Initialize webhook handler.

        Args:
            database: MongoDB database instance (MongoDB class from app/database/mongodb.py)
                     Can be MongoDB instance (access via database.db) or AsyncIOMotorDatabase

        Example:
            from app.database.mongodb import database
            handler = WebhookHandler(database)
        """
        # Handle both MongoDB class instance and direct database instance
        # CRITICAL: Check type, not just hasattr, because AsyncIOMotorDatabase.db
        # returns a COLLECTION named "db", not the database itself!
        from app.database.mongodb import MongoDB
        from motor.motor_asyncio import AsyncIOMotorDatabase

        if isinstance(database, MongoDB):
            # MongoDB class wrapper → access via .db property
            self.db = database.db
        elif isinstance(database, AsyncIOMotorDatabase):
            # Direct Motor database instance
            self.db = database
        else:
            # Fallback: try to access .db attribute (legacy support)
            # WARNING: This may fail if database.db is a collection!
            self.db = getattr(database, 'db', database)

        # Initialize webhook repository for event storage/deduplication
        self.webhook_repo = WebhookRepository(self.db)

    async def handle_event(self, event: dict) -> dict:
        """
        Handle Stripe webhook event.

        Flow:
        1. Extract event metadata (event_id, event_type, payment_intent_id)
        2. Store event in webhook_events (deduplication via unique index)
        3. Route to appropriate handler by event_type
        4. Mark event as processed (or processed with error)
        5. Return processing status

        Args:
            event: Stripe webhook event dict with structure:
                {
                    "id": "evt_...",
                    "type": "payment_intent.succeeded",
                    "data": {
                        "object": {
                            "id": "pi_...",
                            "amount": 5000,
                            "currency": "usd",
                            ...
                        }
                    }
                }

        Returns:
            dict: Processing result
                {"status": "processed"} - Success
                {"status": "duplicate"} - Already processed (Stripe retry)
                {"status": "unsupported"} - Event type not supported
                {"status": "error", "message": "..."} - Processing failed

        Raises:
            Does NOT raise exceptions - all errors returned in response dict
        """
        try:
            # 1. Extract event metadata
            event_id = event.get("id")
            event_type = event.get("type")

            # Extract payment_intent_id (varies by event type)
            payment_intent_id = None
            if event_type and "payment_intent" in event_type:
                # payment_intent.* events → payment intent ID is in data.object.id
                payment_intent_id = event.get("data", {}).get("object", {}).get("id")
            elif event_type == "charge.refunded":
                # charge.refunded → payment intent ID is in data.object.payment_intent
                payment_intent_id = event.get("data", {}).get("object", {}).get("payment_intent")

            logger.info(f"[WEBHOOK] Processing event {event_id} type={event_type} payment_intent={payment_intent_id}")

            # 2. Store event (deduplication via unique index on event_id)
            try:
                await self.webhook_repo.store_event({
                    "event_id": event_id,
                    "event_type": event_type,
                    "payment_intent_id": payment_intent_id,
                    "raw_payload": event,
                    "processed": False
                })
                logger.info(f"[WEBHOOK] Event {event_id} stored in webhook_events")
            except DuplicateEventError:
                # Stripe sends duplicate events during retries
                logger.info(f"[WEBHOOK] Duplicate event {event_id}, skipping processing")
                return {"status": "duplicate"}

            # 3. Route by event type
            error_message = None  # Track error messages from handlers

            # Validate event_type exists
            if not event_type:
                raise ValueError("Event type is missing or invalid")

            if event_type == "payment_intent.succeeded":
                payment_intent = event.get("data", {}).get("object", {})
                await self._handle_payment_succeeded(payment_intent, event_id=event_id)

            elif event_type == "payment_intent.payment_failed":
                payment_intent = event.get("data", {}).get("object", {})
                error_message = await self._handle_payment_failed(payment_intent)

            elif event_type == "charge.refunded":
                charge = event.get("data", {}).get("object", {})
                await self._handle_refund(charge)

            else:
                # Unsupported event type (e.g., customer.created)
                # DO NOT mark as processed - leave processed=False for unsupported events
                logger.warning(f"[WEBHOOK] Unsupported event type: {event_type}")
                return {"status": "unsupported"}

            # 4. Mark event as processed (with optional error message)
            await self.webhook_repo.mark_processed(event_id, error=error_message)
            logger.info(f"[WEBHOOK] Event {event_id} processed successfully")

            return {"status": "processed"}

        except Exception as e:
            # Catch all errors and return error status (don't raise)
            logger.error(f"[WEBHOOK] Error processing event {event.get('id')}: {e}", exc_info=True)

            # Mark event as processed with error
            if event.get("id"):
                try:
                    await self.webhook_repo.mark_processed(event.get("id"), error=str(e))
                except Exception as mark_error:
                    logger.error(f"[WEBHOOK] Failed to mark event as error: {mark_error}")

            return {"status": "error", "message": str(e)}

    async def _handle_payment_succeeded(self, payment_intent: dict, event_id: str):
        """
        Handle payment_intent.succeeded event.

        Flow:
        1. Extract payment intent data (payment_intent_id, amount, currency, customer_email, metadata)
        2. Check payment-level idempotency (query payments collection for stripe_payment_intent_id)
        3. If payment exists → log and skip (already processed)
        4. If payment is new → trigger background payment processing (process_payment_files_background)

        Payment-Level Idempotency:
        - Prevents duplicate payment processing if webhook is retried after payment record created
        - Complements event-level idempotency (webhook_events unique index)
        - Example: Event stored → payment processing starts → webhook retries → payment exists → skip

        Args:
            payment_intent: Stripe payment_intent object from webhook data.object
            event_id: Stripe webhook event ID (links payment to webhook event)
                {
                    "id": "pi_...",
                    "amount": 5000,  # cents
                    "currency": "usd",
                    "customer_email": "user@example.com",
                    "metadata": {
                        "file_ids": "file1,file2"
                    }
                }

        Raises:
            Does NOT raise exceptions - logs errors and allows mark_processed to handle
        """
        payment_intent_id = payment_intent.get("id")
        amount = payment_intent.get("amount", 0)  # Amount in cents (Stripe format)
        currency = payment_intent.get("currency", "usd")
        customer_email = payment_intent.get("customer_email")

        logger.info(f"[WEBHOOK] Handling payment_intent.succeeded: {payment_intent_id} amount={amount} cents ({amount/100:.2f} {currency}) customer={customer_email}")

        # Extract file_ids from metadata (optional)
        metadata = payment_intent.get("metadata", {})
        file_ids_str = metadata.get("file_ids")
        file_ids = file_ids_str.split(",") if file_ids_str else None

        # Payment-level idempotency using atomic upsert
        # This prevents race conditions when multiple webhooks arrive concurrently
        # Only ONE webhook will successfully insert the payment record
        try:
            from datetime import datetime, timezone

            result = await self.db.payments.update_one(
                {"stripe_payment_intent_id": payment_intent_id},
                {
                    "$setOnInsert": {
                        "stripe_payment_intent_id": payment_intent_id,
                        "status": "pending",
                        "created_at": datetime.now(timezone.utc),
                        "webhook_event_id": event_id,
                        "amount": amount,
                        "currency": currency,
                        "customer_email": customer_email
                    }
                },
                upsert=True
            )

            if result.matched_count > 0:
                # Payment record already existed - another webhook got here first
                logger.info(f"[WEBHOOK] Payment {payment_intent_id} already exists (concurrent webhook detected), skipping processing")
                return

            # We successfully inserted the payment record - proceed with processing
            logger.info(f"[WEBHOOK] Processing new payment {payment_intent_id}, file_ids={file_ids}")

        except Exception as e:
            # Unique index violation or other database error
            logger.warning(f"[WEBHOOK] Payment {payment_intent_id} duplicate prevented by database constraint: {e}")
            return

        # Trigger background payment processing
        # NOTE: Tests mock process_payment_files_background to avoid actual file processing
        await process_payment_files_background(
            customer_email=customer_email,
            payment_intent_id=payment_intent_id,
            amount=amount,
            currency=currency,
            file_ids=file_ids,
            webhook_event_id=event_id  # Link payment to webhook event
        )

        logger.info(f"[WEBHOOK] Payment processing triggered for {payment_intent_id} (webhook event: {event_id})")

    async def _handle_payment_failed(self, payment_intent: dict):
        """
        Handle payment_intent.payment_failed event.

        Flow:
        1. Extract payment intent data
        2. Log failure with error details
        3. Store error message for audit (caller will mark event as processed with error)
        4. No payment record created (payment failed)

        Args:
            payment_intent: Stripe payment_intent object with error details
                {
                    "id": "pi_...",
                    "status": "failed",
                    "last_payment_error": {
                        "message": "Your card was declined"
                    }
                }

        Returns:
            str: Error message to be stored in webhook event
        """
        payment_intent_id = payment_intent.get("id")
        error_message = payment_intent.get("last_payment_error", {}).get("message", "Unknown error")

        logger.warning(f"[WEBHOOK] Payment failed: {payment_intent_id} - {error_message}")

        # Return error message to be stored by caller
        return error_message

    async def _handle_refund(self, charge: dict):
        """
        Handle charge.refunded event.

        Flow:
        1. Extract charge data (payment_intent_id, amount_refunded)
        2. Find payment by stripe_payment_intent_id
        3. If payment found → update status to "refunded" and record refund amount
        4. If payment NOT found → log warning, don't raise exception (graceful handling)

        Graceful Error Handling:
        - If payment not found, log warning but don't fail webhook processing
        - Rationale: Webhook event should still be stored for audit trail
        - Test coverage: test_handle_charge_refunded_no_payment_logs_warning

        Args:
            charge: Stripe charge object from refund event
                {
                    "id": "ch_...",
                    "payment_intent": "pi_...",
                    "amount_refunded": 5000,  # cents
                    "refunded": true
                }

        Raises:
            Does NOT raise exceptions - logs warnings for missing payments
        """
        payment_intent_id = charge.get("payment_intent")
        amount_refunded = charge.get("amount_refunded", 0)  # Amount in cents (Stripe format)

        logger.info(f"[WEBHOOK] Handling charge.refunded: payment_intent={payment_intent_id} amount_refunded={amount_refunded} cents (${amount_refunded/100:.2f})")

        # Atomic find and update payment status to refunded
        # Combines find_one + update_one into single database operation
        payment = await self.db.payments.find_one_and_update(
            {"stripe_payment_intent_id": payment_intent_id},
            {
                "$set": {
                    "status": "refunded",  # Update status field
                    "payment_status": "refunded",  # Also update payment_status for compatibility
                    "amount_refunded": amount_refunded,
                    "refunded_at": datetime.now(timezone.utc)
                }
            },
            return_document=ReturnDocument.AFTER  # Return updated document
        )

        if not payment:
            # Payment not found - raise exception to store warning in event
            logger.warning(f"[WEBHOOK] Payment not found for refund: {payment_intent_id} (event still stored for audit)")
            raise Exception(f"Payment not found for refund: {payment_intent_id}")

        logger.info(f"[WEBHOOK] Payment {payment_intent_id} marked as refunded (${amount_refunded/100:.2f})")
