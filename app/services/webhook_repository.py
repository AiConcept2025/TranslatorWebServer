"""
Webhook Repository - MongoDB Integration for Stripe Webhook Events

Purpose:
- Store webhook events with deduplication (idempotency)
- Track event processing status (processed/error)
- Implement 90-day TTL retention (automatic MongoDB expiration)

Database Collection: webhook_events (indexed in app/db/mongodb.py)

Key Features:
1. Idempotency - Reject duplicate event_id (Stripe retries)
2. Processing Status - Track processed/error state
3. TTL Expiration - Auto-delete events after 90 days
4. Timezone-Aware Timestamps - Python 3.12+ compatible

Usage:
    from app.services.webhook_repository import WebhookRepository, DuplicateEventError

    repo = WebhookRepository(database)

    # Store new event
    try:
        event = await repo.store_event({
            "event_id": "evt_12345",
            "event_type": "payment_intent.succeeded",
            "payment_intent_id": "pi_12345",
            "raw_payload": {...},
            "created_at": datetime.now(timezone.utc)
        })
    except DuplicateEventError:
        # Event already processed (Stripe retry)
        pass

    # Mark as processed
    await repo.mark_processed("evt_12345")

    # Mark as processed with error
    await repo.mark_processed("evt_12345", error="Payment processing failed")

    # Retrieve event
    event = await repo.get_event("evt_12345")
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError


class DuplicateEventError(Exception):
    """
    Raised when webhook event_id already exists.

    Purpose: Stripe sends duplicate webhook events during retries.
    Repository enforces idempotency by rejecting duplicate event_id.

    Example:
        try:
            await repo.store_event(event_data)
        except DuplicateEventError:
            logger.info(f"Duplicate event {event_id} ignored (Stripe retry)")
    """
    pass


class WebhookRepository:
    """
    Repository for webhook event storage and processing status tracking.

    Handles:
    - Event storage with deduplication
    - Processing status updates
    - TTL-based event expiration (90 days)

    Database Collection: webhook_events
    Indexes:
    - event_id (unique) - Enforces idempotency
    - ttl_90_days (expires_at) - Auto-deletes old events

    Methods:
    - store_event() - Insert webhook event
    - mark_processed() - Update processing status
    - get_event() - Retrieve event by ID
    """

    def __init__(self, database: AsyncIOMotorDatabase):
        """
        Initialize webhook repository.

        Args:
            database: AsyncIOMotorDatabase instance (translation_test or translation)

        Example:
            from motor.motor_asyncio import AsyncIOMotorClient

            client = AsyncIOMotorClient("mongodb://localhost:27017")
            db = client["translation_test"]
            repo = WebhookRepository(db)
        """
        self.db = database

    async def store_event(self, event_data: dict) -> dict:
        """
        Store webhook event in database.

        Sets default values:
        - processed = False (if not present)
        - processed_at = None (if not present)
        - error = None (if not present)
        - expires_at = created_at + 90 days (if not present)

        Args:
            event_data: Webhook event data with required fields:
                - event_id (str, required) - Unique Stripe event ID
                - event_type (str, required) - Event type (e.g., "payment_intent.succeeded")
                - payment_intent_id (str, optional) - Payment intent ID (can be None)
                - raw_payload (dict, required) - Raw Stripe webhook payload
                - created_at (datetime, optional) - Event timestamp (defaults to now)
                - expires_at (datetime, optional) - TTL expiration (defaults to created_at + 90 days)

        Returns:
            dict: Inserted document (includes _id from MongoDB)

        Raises:
            DuplicateEventError: If event_id already exists (Stripe retry)

        Example:
            event = await repo.store_event({
                "event_id": "evt_12345",
                "event_type": "payment_intent.succeeded",
                "payment_intent_id": "pi_12345",
                "raw_payload": {"id": "evt_12345", "type": "payment_intent.succeeded"},
                "created_at": datetime.now(timezone.utc)
            })
            print(f"Stored event: {event['_id']}")
        """
        # Set default values for TTL and processing status
        if "processed" not in event_data:
            event_data["processed"] = False

        if "processed_at" not in event_data:
            event_data["processed_at"] = None

        if "error" not in event_data:
            event_data["error"] = None

        # Set created_at if not provided
        if "created_at" not in event_data:
            event_data["created_at"] = datetime.now(timezone.utc)

        # Calculate expires_at for TTL (90 days from created_at)
        if "expires_at" not in event_data:
            event_data["expires_at"] = event_data["created_at"] + timedelta(days=90)

        # Insert event into database
        try:
            result = await self.db.webhook_events.insert_one(event_data)
            # Return document with _id
            event_data["_id"] = result.inserted_id
            return event_data

        except DuplicateKeyError as e:
            # MongoDB E11000 duplicate key error - event_id already exists
            raise DuplicateEventError(
                f"Duplicate event_id: {event_data.get('event_id')} (Stripe retry)"
            ) from e

    async def mark_processed(self, event_id: str, error: Optional[str] = None) -> None:
        """
        Mark webhook event as processed.

        Updates:
        - processed = True
        - processed_at = datetime.now(timezone.utc)
        - error = error parameter (None for success, error message for failure)

        Args:
            event_id: Stripe event ID
            error: Optional error message (None = success, str = failure)

        Returns:
            None

        Example (success):
            await repo.mark_processed("evt_12345")

        Example (error):
            await repo.mark_processed("evt_12345", error="Payment intent not found")
        """
        await self.db.webhook_events.update_one(
            {"event_id": event_id},
            {
                "$set": {
                    "processed": True,
                    "processed_at": datetime.now(timezone.utc),
                    "error": error
                }
            }
        )

    def _make_datetime_aware(self, document: Optional[dict]) -> Optional[dict]:
        """
        Convert timezone-naive datetime fields to timezone-aware (UTC).

        MongoDB stores datetime as UTC but returns them as timezone-naive.
        This helper converts them back to timezone-aware for consistency.

        Args:
            document: MongoDB document (or None)

        Returns:
            dict: Document with timezone-aware datetimes (or None if input is None)
        """
        if document is None:
            return None

        # List of datetime fields in webhook_events collection
        datetime_fields = ["created_at", "processed_at", "expires_at"]

        for field in datetime_fields:
            if field in document and document[field] is not None:
                # Convert timezone-naive datetime to timezone-aware (UTC)
                if document[field].tzinfo is None:
                    document[field] = document[field].replace(tzinfo=timezone.utc)

        return document

    async def get_event(self, event_id: str) -> Optional[dict]:
        """
        Retrieve webhook event by event_id.

        Args:
            event_id: Stripe event ID

        Returns:
            dict: Event document if found (with timezone-aware datetimes)
            None: If event does not exist

        Example:
            event = await repo.get_event("evt_12345")
            if event:
                print(f"Event type: {event['event_type']}")
                print(f"Processed: {event['processed']}")
            else:
                print("Event not found")
        """
        document = await self.db.webhook_events.find_one({"event_id": event_id})
        return self._make_datetime_aware(document)
