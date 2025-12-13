"""
Integration tests for Stripe webhook event handler.

TDD RED PHASE: These tests are written FIRST and will FAIL/SKIP until implementation exists.

Test Coverage:
1. Payment intent succeeded → creates payment
2. Duplicate event handling → skips processing
3. Payment failed → logs error, no payment created
4. Charge refunded → updates payment status
5. Unsupported event types → logged appropriately

Database: Uses translation_test with TEST_WEBHOOK_ prefix for cleanup
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

# CRITICAL: This import WILL FAIL until implementation exists (TDD RED state)
try:
    from app.services.webhook_handler import WebhookHandler
    HANDLER_EXISTS = True
except ImportError:
    HANDLER_EXISTS = False
    # Placeholder for type hints
    class WebhookHandler:
        pass

TEST_PREFIX = "TEST_WEBHOOK_"


@pytest.fixture
def webhook_handler(test_db):
    """
    Create WebhookHandler instance with test database.

    NOTE: This is a non-async fixture that returns the WebhookHandler instance.
    The test_db fixture is async, but we can use it directly since pytest handles
    the async fixture dependency injection.
    """
    if not HANDLER_EXISTS:
        pytest.skip("WebhookHandler not yet implemented (TDD RED state)")

    # Pass test_db directly (AsyncIOMotorDatabase instance)
    # WebhookHandler accepts both MongoDB class instance and direct database
    return WebhookHandler(test_db)


@pytest.fixture(autouse=True)
async def cleanup_test_data(test_db):
    """Cleanup test webhook events and payments before/after each test."""
    from pymongo import ASCENDING, IndexModel

    # Ensure unique index exists on webhook_events.event_id (critical for deduplication)
    try:
        await test_db.webhook_events.create_index(
            [("event_id", ASCENDING)],
            unique=True,
            name="event_id_unique"
        )
    except Exception:
        pass  # Index already exists

    # Cleanup before test (in case of previous failures)
    await test_db.webhook_events.delete_many({"event_id": {"$regex": f"^{TEST_PREFIX}"}})
    await test_db.payments.delete_many({"stripe_payment_intent_id": {"$regex": f"^{TEST_PREFIX}"}})

    yield

    # Cleanup after test
    await test_db.webhook_events.delete_many({"event_id": {"$regex": f"^{TEST_PREFIX}"}})
    await test_db.payments.delete_many({"stripe_payment_intent_id": {"$regex": f"^{TEST_PREFIX}"}})


@pytest.fixture
def payment_intent_succeeded_event():
    """Factory fixture for payment_intent.succeeded events."""
    def _create_event(
        event_id: str = None,
        payment_intent_id: str = None,
        amount: int = 5000,
        currency: str = "usd",
        customer_email: str = None,
        file_ids: str = "file1,file2"
    ):
        return {
            "id": event_id or f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}",
            "type": "payment_intent.succeeded",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {
                "object": {
                    "id": payment_intent_id or f"{TEST_PREFIX}pi_{uuid.uuid4().hex[:8]}",
                    "amount": amount,
                    "currency": currency,
                    "status": "succeeded",
                    "customer_email": customer_email or f"test_{uuid.uuid4().hex[:8]}@example.com",
                    "metadata": {
                        "file_ids": file_ids
                    }
                }
            }
        }
    return _create_event


@pytest.fixture
def payment_failed_event():
    """Factory fixture for payment_intent.payment_failed events."""
    def _create_event(
        event_id: str = None,
        payment_intent_id: str = None,
        error_message: str = "Card declined"
    ):
        return {
            "id": event_id or f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}",
            "type": "payment_intent.payment_failed",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {
                "object": {
                    "id": payment_intent_id or f"{TEST_PREFIX}pi_{uuid.uuid4().hex[:8]}",
                    "status": "failed",
                    "last_payment_error": {
                        "message": error_message
                    }
                }
            }
        }
    return _create_event


@pytest.fixture
def charge_refunded_event():
    """Factory fixture for charge.refunded events."""
    def _create_event(
        event_id: str = None,
        charge_id: str = None,
        payment_intent_id: str = None,
        amount_refunded: int = 5000
    ):
        return {
            "id": event_id or f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}",
            "type": "charge.refunded",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "data": {
                "object": {
                    "id": charge_id or f"{TEST_PREFIX}ch_{uuid.uuid4().hex[:8]}",
                    "payment_intent": payment_intent_id or f"{TEST_PREFIX}pi_{uuid.uuid4().hex[:8]}",
                    "amount_refunded": amount_refunded,
                    "refunded": True
                }
            }
        }
    return _create_event


@pytest.mark.asyncio
async def test_handle_payment_intent_succeeded_creates_payment(
    webhook_handler,
    test_db,
    payment_intent_succeeded_event
):
    """
    Test handling payment_intent.succeeded event.

    TDD RED: This test will FAIL until WebhookHandler._handle_payment_succeeded() is implemented.

    Expected behavior:
    1. Event stored in webhook_events collection
    2. Payment processing triggered (mocked)
    3. Event marked as processed
    4. Returns {"status": "processed"}
    """
    # ARRANGE: Create payment_intent.succeeded event
    event = payment_intent_succeeded_event()
    event_id = event["id"]
    payment_intent_id = event["data"]["object"]["id"]

    # Mock payment processing to avoid actual file processing
    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock) as mock_process:
        # ACT: Handle event
        result = await webhook_handler.handle_event(event)

        # ASSERT: Response status
        assert result["status"] == "processed", "Expected 'processed' status for successful payment intent"

        # ASSERT: Event stored in webhook_events
        stored_event = await test_db.webhook_events.find_one({"event_id": event_id})
        assert stored_event is not None, "Event should be stored in webhook_events collection"
        assert stored_event["event_type"] == "payment_intent.succeeded"
        assert stored_event["payment_intent_id"] == payment_intent_id
        assert stored_event["processed"] is True, "Event should be marked as processed"
        assert stored_event.get("error") is None, "Successful event should have no error"

        # ASSERT: Payment processing was triggered
        mock_process.assert_called_once()
        call_args = mock_process.call_args[1]  # Get kwargs
        assert call_args["payment_intent_id"] == payment_intent_id
        assert call_args["amount"] == 5000
        assert call_args["currency"] == "usd"


@pytest.mark.asyncio
async def test_handle_duplicate_event_skips_processing(
    webhook_handler,
    test_db,
    payment_intent_succeeded_event
):
    """
    Test handling duplicate events (same event_id).

    TDD RED: This test will FAIL until duplicate detection is implemented.

    Expected behavior:
    1. First event stored and processed
    2. Second event with same event_id returns {"status": "duplicate"}
    3. Payment processing only called once
    """
    # ARRANGE: Create event and store it FIRST (simulate duplicate)
    event = payment_intent_succeeded_event()
    event_id = event["id"]

    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock) as mock_process:
        # ACT: Handle event first time
        result1 = await webhook_handler.handle_event(event)
        assert result1["status"] == "processed"

        # ACT: Handle same event again (duplicate)
        result2 = await webhook_handler.handle_event(event)

        # ASSERT: Second call returns duplicate status
        assert result2["status"] == "duplicate", "Duplicate event should return 'duplicate' status"

        # ASSERT: Payment processing only called once
        assert mock_process.call_count == 1, "Payment processing should only be called once for duplicates"

        # ASSERT: Only one event stored
        event_count = await test_db.webhook_events.count_documents({"event_id": event_id})
        assert event_count == 1, "Only one event should be stored for duplicate event_id"


@pytest.mark.asyncio
async def test_handle_payment_failed_marks_event_with_error(
    webhook_handler,
    test_db,
    payment_failed_event
):
    """
    Test handling payment_intent.payment_failed event.

    TDD RED: This test will FAIL until WebhookHandler._handle_payment_failed() is implemented.

    Expected behavior:
    1. Event stored with error message
    2. No payment created
    3. Returns {"status": "processed"}
    """
    # ARRANGE: Create payment_intent.payment_failed event
    error_message = "Insufficient funds"
    event = payment_failed_event(error_message=error_message)
    event_id = event["id"]
    payment_intent_id = event["data"]["object"]["id"]

    # ACT: Handle failed payment event
    result = await webhook_handler.handle_event(event)

    # ASSERT: Response status
    assert result["status"] == "processed", "Failed payment events should still be processed"

    # ASSERT: Event stored with error message
    stored_event = await test_db.webhook_events.find_one({"event_id": event_id})
    assert stored_event is not None, "Failed payment event should be stored"
    assert stored_event["event_type"] == "payment_intent.payment_failed"
    assert stored_event["payment_intent_id"] == payment_intent_id
    assert stored_event["processed"] is True
    assert error_message in stored_event.get("error", ""), "Error message should be stored in event"

    # ASSERT: No payment created
    payment = await test_db.payments.find_one({"stripe_payment_intent_id": payment_intent_id})
    assert payment is None, "Failed payment should not create payment record"


@pytest.mark.asyncio
async def test_handle_charge_refunded_updates_payment_status(
    webhook_handler,
    test_db,
    payment_intent_succeeded_event,
    charge_refunded_event
):
    """
    Test handling charge.refunded event.

    TDD RED: This test will FAIL until WebhookHandler._handle_refund() is implemented.

    Expected behavior:
    1. Existing payment status updated to "refunded"
    2. Refund amount recorded
    3. Event stored and marked as processed
    """
    # ARRANGE: Create payment first
    payment_intent_id = f"{TEST_PREFIX}pi_{uuid.uuid4().hex[:8]}"
    payment_doc = {
        "stripe_payment_intent_id": payment_intent_id,
        "amount": 5000,
        "currency": "usd",
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc)
    }
    await test_db.payments.insert_one(payment_doc)

    # ARRANGE: Create charge.refunded event
    refund_event = charge_refunded_event(payment_intent_id=payment_intent_id, amount_refunded=5000)
    event_id = refund_event["id"]

    # ACT: Handle refund event
    result = await webhook_handler.handle_event(refund_event)

    # ASSERT: Response status
    assert result["status"] == "processed", "Refund event should be processed"

    # ASSERT: Event stored
    stored_event = await test_db.webhook_events.find_one({"event_id": event_id})
    assert stored_event is not None, "Refund event should be stored"
    assert stored_event["event_type"] == "charge.refunded"
    assert stored_event["processed"] is True

    # ASSERT: Payment status updated to refunded
    updated_payment = await test_db.payments.find_one({"stripe_payment_intent_id": payment_intent_id})
    assert updated_payment is not None, "Payment should exist"
    assert updated_payment["status"] == "refunded", "Payment status should be updated to 'refunded'"
    assert updated_payment.get("amount_refunded") == 5000, "Refund amount should be recorded"


@pytest.mark.asyncio
async def test_handle_charge_refunded_no_payment_logs_warning(
    webhook_handler,
    test_db,
    charge_refunded_event
):
    """
    Test handling charge.refunded when payment doesn't exist.

    TDD RED: This test will FAIL until graceful error handling is implemented.

    Expected behavior:
    1. Event stored with warning/error message
    2. No exception raised
    3. Returns {"status": "processed"} or {"status": "error"}
    """
    # ARRANGE: Create refund event for non-existent payment
    payment_intent_id = f"{TEST_PREFIX}pi_nonexistent_{uuid.uuid4().hex[:8]}"
    refund_event = charge_refunded_event(payment_intent_id=payment_intent_id)
    event_id = refund_event["id"]

    # ACT: Handle refund event (payment doesn't exist)
    result = await webhook_handler.handle_event(refund_event)

    # ASSERT: Should not raise exception
    assert result["status"] in ["processed", "error"], "Should handle missing payment gracefully"

    # ASSERT: Event stored with error/warning
    stored_event = await test_db.webhook_events.find_one({"event_id": event_id})
    assert stored_event is not None, "Event should be stored even if payment not found"
    assert stored_event.get("error") is not None or stored_event.get("warning") is not None, \
        "Should log warning/error when payment not found"


@pytest.mark.asyncio
async def test_handle_unsupported_event_type_logged(
    webhook_handler,
    test_db
):
    """
    Test handling unsupported event types.

    TDD RED: This test will FAIL until unsupported event handling is implemented.

    Expected behavior:
    1. Event stored with unsupported status
    2. Returns {"status": "unsupported"}
    3. No processing attempted
    """
    # ARRANGE: Create unsupported event type
    unsupported_event = {
        "id": f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}",
        "type": "customer.created",
        "created": int(datetime.now(timezone.utc).timestamp()),
        "data": {
            "object": {
                "id": f"cus_{uuid.uuid4().hex[:8]}",
                "email": "customer@example.com"
            }
        }
    }
    event_id = unsupported_event["id"]

    # ACT: Handle unsupported event
    result = await webhook_handler.handle_event(unsupported_event)

    # ASSERT: Response status
    assert result["status"] == "unsupported", "Unsupported events should return 'unsupported' status"

    # ASSERT: Event still stored for audit trail
    stored_event = await test_db.webhook_events.find_one({"event_id": event_id})
    assert stored_event is not None, "Unsupported events should still be stored for audit"
    assert stored_event["event_type"] == "customer.created"
    assert stored_event["processed"] is False, "Unsupported events should be marked as not processed"


@pytest.mark.asyncio
async def test_handle_payment_intent_succeeded_with_missing_metadata(
    webhook_handler,
    test_db,
    payment_intent_succeeded_event
):
    """
    Test handling payment_intent.succeeded with missing metadata.

    TDD RED: This test will FAIL until graceful metadata handling is implemented.

    Expected behavior:
    1. Event stored successfully
    2. Handles missing file_ids gracefully
    3. Returns {"status": "processed"} or logs warning
    """
    # ARRANGE: Create event with no metadata
    event = payment_intent_succeeded_event(file_ids=None)
    event["data"]["object"]["metadata"] = {}  # Empty metadata
    event_id = event["id"]

    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock) as mock_process:
        # ACT: Handle event with missing metadata
        result = await webhook_handler.handle_event(event)

        # ASSERT: Should handle gracefully
        assert result["status"] in ["processed", "error"], "Should handle missing metadata gracefully"

        # ASSERT: Event stored
        stored_event = await test_db.webhook_events.find_one({"event_id": event_id})
        assert stored_event is not None, "Event should be stored even with missing metadata"


@pytest.mark.asyncio
async def test_handle_event_with_invalid_structure(
    webhook_handler,
    test_db
):
    """
    Test handling events with invalid/malformed structure.

    TDD RED: This test will FAIL until error handling is implemented.

    Expected behavior:
    1. Returns {"status": "error"}
    2. Logs error appropriately
    3. No exception raised
    """
    # ARRANGE: Create malformed event (missing required fields)
    malformed_event = {
        "id": f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}",
        # Missing 'type' and 'data' fields
    }

    # ACT: Handle malformed event
    result = await webhook_handler.handle_event(malformed_event)

    # ASSERT: Should handle gracefully
    assert result["status"] == "error", "Malformed events should return 'error' status"
    assert "error" in result or "message" in result, "Error response should include error details"


@pytest.mark.asyncio
async def test_handle_multiple_events_in_sequence(
    webhook_handler,
    test_db,
    payment_intent_succeeded_event,
    payment_failed_event
):
    """
    Test handling multiple different events in sequence.

    TDD RED: Integration test for overall workflow.

    Expected behavior:
    1. All events stored correctly
    2. Each event processed according to its type
    3. No interference between events
    """
    # ARRANGE: Create multiple events
    success_event = payment_intent_succeeded_event()
    failed_event = payment_failed_event()

    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock):
        # ACT: Handle events in sequence
        result1 = await webhook_handler.handle_event(success_event)
        result2 = await webhook_handler.handle_event(failed_event)

        # ASSERT: Both processed correctly
        assert result1["status"] == "processed"
        assert result2["status"] == "processed"

        # ASSERT: Both stored
        event_count = await test_db.webhook_events.count_documents({
            "event_id": {"$regex": f"^{TEST_PREFIX}"}
        })
        assert event_count == 2, "Both events should be stored"


# Performance/Edge case tests

@pytest.mark.asyncio
async def test_handle_event_concurrent_same_event(
    webhook_handler,
    test_db,
    payment_intent_succeeded_event
):
    """
    Test concurrent handling of the same event (race condition).

    TDD RED: This test will FAIL until proper locking/duplicate detection is implemented.

    Expected behavior:
    1. Only one event stored
    2. One returns "processed", others return "duplicate"
    3. Payment processing only triggered once
    """
    import asyncio

    # ARRANGE: Create event
    event = payment_intent_succeeded_event()

    with patch("app.services.webhook_handler.process_payment_files_background", new_callable=AsyncMock) as mock_process:
        # ACT: Handle same event concurrently (simulate race condition)
        results = await asyncio.gather(
            webhook_handler.handle_event(event),
            webhook_handler.handle_event(event),
            webhook_handler.handle_event(event),
            return_exceptions=True
        )

        # ASSERT: Only one processed, others duplicates
        statuses = [r["status"] for r in results if isinstance(r, dict)]
        assert statuses.count("processed") == 1, "Only one should be processed"
        assert statuses.count("duplicate") == 2, "Others should be marked as duplicates"

        # ASSERT: Payment processing only called once
        assert mock_process.call_count == 1, "Payment processing should only be called once"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
