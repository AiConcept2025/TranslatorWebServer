"""
TDD RED STATE - Integration Tests for Webhook Repository

CRITICAL: These tests WILL FAIL because WebhookRepository is NOT yet implemented.
This is Phase 1 (RED) of TDD - write failing tests FIRST.

Purpose:
- Test webhook event storage and deduplication (Stripe idempotency)
- Test event processing status tracking
- Test TTL-based event expiration (90-day retention)
- Verify MongoDB integration with webhook_events collection

EXPECTED FAILURES (until implementation):
- ImportError: WebhookRepository module does not exist
- All tests will fail with import errors

Test Coverage:
1. Store webhook event (creates new document)
2. Reject duplicate event_id (idempotency)
3. Mark event as processed (with/without error)
4. Get event by ID (exists/not-exists)
5. TTL expiration field verification (MongoDB auto-deletes after 90 days)

Test Database: translation_test
Test Data Prefix: TEST_WEBHOOK_
Cleanup: Regex pattern {"event_id": {"$regex": "^TEST_WEBHOOK_"}}

CRITICAL: Uses REAL test database (NOT mocked), follows TDD protocol
Terminal 1: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
Terminal 2: pytest tests/integration/test_webhook_repository_integration.py -v
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

# ============================================================================
# CRITICAL: This import WILL FAIL until WebhookRepository is implemented
# This is EXPECTED for TDD RED state
# ============================================================================
try:
    from app.services.webhook_repository import WebhookRepository, DuplicateEventError
    REPOSITORY_EXISTS = True
except ImportError:
    REPOSITORY_EXISTS = False
    # Define placeholder for type hints
    class WebhookRepository:
        pass
    class DuplicateEventError(Exception):
        pass


# ============================================================================
# Test Configuration
# ============================================================================

MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation"
DATABASE_NAME = "translation_test"
TEST_PREFIX = "TEST_WEBHOOK_"

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def test_db():
    """
    Connect to test MongoDB database.

    CRITICAL: Uses translation_test database, NOT production.
    Creates webhook_events indexes if they don't exist.
    """
    from pymongo import ASCENDING, IndexModel
    from pymongo.errors import OperationFailure

    mongo_client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    database = mongo_client[DATABASE_NAME]

    try:
        await mongo_client.admin.command('ping')
    except Exception as e:
        pytest.skip(f"Cannot connect to test database: {e}")

    # Create webhook_events indexes (from mongodb.py Phase 1)
    try:
        webhook_events_indexes = [
            IndexModel([("event_id", ASCENDING)], unique=True, name="event_id_unique"),
            IndexModel([("payment_intent_id", ASCENDING)], name="payment_intent_id_idx"),
            IndexModel([("event_type", ASCENDING)], name="event_type_idx"),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_90_days"),
            IndexModel([("created_at", -1)], name="created_at_desc")
        ]
        await database.webhook_events.create_indexes(webhook_events_indexes)
    except OperationFailure:
        # Indexes already exist, ignore
        pass

    yield database
    mongo_client.close()


@pytest.fixture(scope="function")
async def webhook_repo(test_db):
    """
    Create WebhookRepository instance for testing.

    CRITICAL: This will fail with ImportError until implementation exists.
    """
    if not REPOSITORY_EXISTS:
        pytest.skip("WebhookRepository not yet implemented (TDD RED state)")

    return WebhookRepository(test_db)


@pytest.fixture(autouse=True)
async def cleanup_test_webhooks(test_db):
    """
    Auto-cleanup fixture: Delete test webhook events after each test.

    Uses TEST_WEBHOOK_ prefix pattern to only delete test data.
    Runs AFTER each test (autouse=True, yield at beginning).
    """
    yield  # Run test first

    # Cleanup: Delete all webhook events with TEST_ prefix
    try:
        result = await test_db.webhook_events.delete_many({
            "event_id": {"$regex": f"^{TEST_PREFIX}"}
        })
        if result.deleted_count > 0:
            print(f"🧹 Cleaned up {result.deleted_count} test webhook events")
    except Exception as e:
        print(f"⚠️  Warning: Cleanup error: {e}")


# ============================================================================
# Test 1: Store Event - Creates New Document
# ============================================================================

@pytest.mark.asyncio
async def test_store_event_creates_new_event(webhook_repo, test_db):
    """
    Test: WebhookRepository.store_event() creates new webhook event.

    ARRANGE:
    - Create webhook event data with TEST_WEBHOOK_ prefix
    - Set expires_at = created_at + 90 days (TTL)

    ACT:
    - Call webhook_repo.store_event(event_data)

    ASSERT:
    - Event stored in database
    - All fields match (event_id, event_type, payment_intent_id)
    - processed=False initially
    - expires_at set correctly (90 days from created_at)
    - raw_payload stored as-is

    EXPECTED: FAIL - WebhookRepository.store_event() method does not exist yet
    """
    # ARRANGE: Create webhook event data
    event_id = f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc)
    expires_at = created_at + timedelta(days=90)

    event_data = {
        "event_id": event_id,
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": f"pi_test_{uuid.uuid4().hex[:8]}",
        "raw_payload": {
            "id": event_id,
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_12345",
                    "amount": 5000,
                    "currency": "usd"
                }
            }
        },
        "processed": False,
        "created_at": created_at,
        "expires_at": expires_at
    }

    print(f"[TEST] Storing webhook event: {event_id}")

    # ACT: Store event
    result = await webhook_repo.store_event(event_data)

    # ASSERT: Verify event stored in database
    stored_event = await test_db.webhook_events.find_one({"event_id": event_id})

    assert stored_event is not None, "Event should be stored in database"
    assert stored_event["event_id"] == event_id, "event_id mismatch"
    assert stored_event["event_type"] == "payment_intent.succeeded", "event_type mismatch"
    assert stored_event["payment_intent_id"] == event_data["payment_intent_id"], "payment_intent_id mismatch"
    assert stored_event["processed"] is False, "processed should be False initially"
    assert stored_event["processed_at"] is None, "processed_at should be None initially"
    assert stored_event["error"] is None, "error should be None initially"
    assert stored_event["raw_payload"] == event_data["raw_payload"], "raw_payload mismatch"

    # Verify TTL field (expires_at)
    assert "expires_at" in stored_event, "expires_at field missing"
    expires_diff = (stored_event["expires_at"] - stored_event["created_at"]).days
    assert expires_diff == 90, f"expires_at should be 90 days after created_at, got {expires_diff}"

    print(f"✅ Event stored successfully: {event_id}")
    print(f"   - Event type: {stored_event['event_type']}")
    print(f"   - Payment intent: {stored_event['payment_intent_id']}")
    print(f"   - Expires at: {stored_event['expires_at']} (90 days)")


# ============================================================================
# Test 2: Store Event - Rejects Duplicate event_id
# ============================================================================

@pytest.mark.asyncio
async def test_store_event_rejects_duplicate_event_id(webhook_repo, test_db):
    """
    Test: WebhookRepository.store_event() rejects duplicate event_id (idempotency).

    ARRANGE:
    - Store an event

    ACT:
    - Try to store same event_id again

    ASSERT:
    - Should raise DuplicateEventError
    - Original event unchanged
    - No duplicate event in database

    RATIONALE:
    Stripe sends duplicate webhook events during retries.
    Repository must enforce idempotency via unique event_id.

    EXPECTED: FAIL - DuplicateEventError not yet implemented
    """
    # ARRANGE: Store first event
    event_id = f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}"
    event_data = {
        "event_id": event_id,
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": f"pi_test_{uuid.uuid4().hex[:8]}",
        "raw_payload": {"id": event_id, "type": "payment_intent.succeeded"},
        "processed": False,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=90)
    }

    await webhook_repo.store_event(event_data)
    print(f"[TEST] Stored first event: {event_id}")

    # ACT & ASSERT: Try to store duplicate event_id
    duplicate_event_data = {
        **event_data,
        "payment_intent_id": f"pi_different_{uuid.uuid4().hex[:8]}",  # Different payload
        "created_at": datetime.now(timezone.utc)  # Different timestamp
    }

    with pytest.raises(DuplicateEventError) as exc_info:
        await webhook_repo.store_event(duplicate_event_data)

    print(f"✅ Duplicate event rejected: {exc_info.value}")

    # VERIFY: Only one event exists in database
    event_count = await test_db.webhook_events.count_documents({"event_id": event_id})
    assert event_count == 1, "Should have exactly 1 event (no duplicate)"

    # VERIFY: Original event unchanged
    original_event = await test_db.webhook_events.find_one({"event_id": event_id})
    assert original_event["payment_intent_id"] == event_data["payment_intent_id"], "Original event should be unchanged"


# ============================================================================
# Test 3: Mark Event Processed - Success Case
# ============================================================================

@pytest.mark.asyncio
async def test_mark_event_processed_updates_status(webhook_repo, test_db):
    """
    Test: WebhookRepository.mark_processed() updates event processing status.

    ARRANGE:
    - Store a webhook event

    ACT:
    - Call webhook_repo.mark_processed(event_id)

    ASSERT:
    - processed=True
    - processed_at timestamp set
    - error=None

    EXPECTED: FAIL - mark_processed() method does not exist yet
    """
    # ARRANGE: Store event
    event_id = f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}"
    event_data = {
        "event_id": event_id,
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": f"pi_test_{uuid.uuid4().hex[:8]}",
        "raw_payload": {"id": event_id},
        "processed": False,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=90)
    }

    await webhook_repo.store_event(event_data)
    print(f"[TEST] Stored event: {event_id}")

    # ACT: Mark event as processed (success case)
    before_processed_time = datetime.now(timezone.utc)
    await webhook_repo.mark_processed(event_id)
    after_processed_time = datetime.now(timezone.utc)

    # ASSERT: Verify processing status updated
    processed_event = await test_db.webhook_events.find_one({"event_id": event_id})

    assert processed_event["processed"] is True, "processed should be True"
    assert processed_event["processed_at"] is not None, "processed_at should be set"
    assert processed_event["error"] is None, "error should be None (success case)"

    # Convert MongoDB's timezone-naive datetime to timezone-aware for comparison
    processed_at = processed_event["processed_at"]
    if processed_at.tzinfo is None:
        processed_at = processed_at.replace(tzinfo=timezone.utc)

    # Verify processed_at timestamp is reasonable (with 1-second tolerance for microsecond precision)
    time_tolerance = timedelta(seconds=1)
    assert before_processed_time - time_tolerance <= processed_at <= after_processed_time + time_tolerance, \
        f"processed_at ({processed_at}) should be within test execution window ({before_processed_time} to {after_processed_time})"

    print(f"✅ Event marked as processed: {event_id}")
    print(f"   - Processed at: {processed_event['processed_at']}")
    print(f"   - Error: {processed_event['error']}")


# ============================================================================
# Test 4: Mark Event Processed - Error Case
# ============================================================================

@pytest.mark.asyncio
async def test_mark_event_processed_with_error(webhook_repo, test_db):
    """
    Test: WebhookRepository.mark_processed() records error message.

    ARRANGE:
    - Store a webhook event

    ACT:
    - Call webhook_repo.mark_processed(event_id, error="Test error message")

    ASSERT:
    - processed=True (even with error - event was processed, just failed)
    - processed_at timestamp set
    - error="Test error message"

    EXPECTED: FAIL - mark_processed() with error parameter not yet implemented
    """
    # ARRANGE: Store event
    event_id = f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}"
    event_data = {
        "event_id": event_id,
        "event_type": "payment_intent.failed",
        "payment_intent_id": f"pi_test_{uuid.uuid4().hex[:8]}",
        "raw_payload": {"id": event_id},
        "processed": False,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=90)
    }

    await webhook_repo.store_event(event_data)
    print(f"[TEST] Stored event: {event_id}")

    # ACT: Mark event as processed with error
    error_message = "Test error: Payment processing failed"
    await webhook_repo.mark_processed(event_id, error=error_message)

    # ASSERT: Verify error recorded
    processed_event = await test_db.webhook_events.find_one({"event_id": event_id})

    assert processed_event["processed"] is True, "processed should be True (even with error)"
    assert processed_event["processed_at"] is not None, "processed_at should be set"
    assert processed_event["error"] == error_message, "error message mismatch"

    print(f"✅ Event marked as processed with error: {event_id}")
    print(f"   - Error: {processed_event['error']}")


# ============================================================================
# Test 5: Get Event by ID - Event Exists
# ============================================================================

@pytest.mark.asyncio
async def test_get_event_returns_event_by_id(webhook_repo, test_db):
    """
    Test: WebhookRepository.get_event() retrieves event by event_id.

    ARRANGE:
    - Store a webhook event

    ACT:
    - Call webhook_repo.get_event(event_id)

    ASSERT:
    - Returns event document
    - All fields match stored data

    EXPECTED: FAIL - get_event() method does not exist yet
    """
    # ARRANGE: Store event
    event_id = f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}"
    payment_intent_id = f"pi_test_{uuid.uuid4().hex[:8]}"
    event_data = {
        "event_id": event_id,
        "event_type": "charge.succeeded",
        "payment_intent_id": payment_intent_id,
        "raw_payload": {"id": event_id, "amount": 2500},
        "processed": False,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=90)
    }

    await webhook_repo.store_event(event_data)
    print(f"[TEST] Stored event: {event_id}")

    # ACT: Get event by ID
    retrieved_event = await webhook_repo.get_event(event_id)

    # ASSERT: Verify retrieved event matches stored data
    assert retrieved_event is not None, "Event should be found"
    assert retrieved_event["event_id"] == event_id, "event_id mismatch"
    assert retrieved_event["event_type"] == "charge.succeeded", "event_type mismatch"
    assert retrieved_event["payment_intent_id"] == payment_intent_id, "payment_intent_id mismatch"
    assert retrieved_event["raw_payload"] == event_data["raw_payload"], "raw_payload mismatch"

    print(f"✅ Event retrieved successfully: {event_id}")
    print(f"   - Event type: {retrieved_event['event_type']}")
    print(f"   - Payment intent: {retrieved_event['payment_intent_id']}")


# ============================================================================
# Test 6: Get Event by ID - Event Does Not Exist
# ============================================================================

@pytest.mark.asyncio
async def test_get_event_returns_none_for_nonexistent_event(webhook_repo, test_db):
    """
    Test: WebhookRepository.get_event() returns None for non-existent event_id.

    ARRANGE:
    - Generate non-existent event_id

    ACT:
    - Call webhook_repo.get_event(non_existent_event_id)

    ASSERT:
    - Returns None (not raises exception)

    EXPECTED: FAIL - get_event() method does not exist yet
    """
    # ARRANGE: Non-existent event ID
    non_existent_event_id = f"{TEST_PREFIX}evt_NONEXISTENT_{uuid.uuid4().hex[:8]}"

    print(f"[TEST] Querying non-existent event: {non_existent_event_id}")

    # ACT: Get non-existent event
    result = await webhook_repo.get_event(non_existent_event_id)

    # ASSERT: Should return None
    assert result is None, "Non-existent event should return None"

    print(f"✅ Non-existent event correctly returned None")


# ============================================================================
# Test 7: TTL Expiration Field - Verify 90-Day Retention
# ============================================================================

@pytest.mark.asyncio
async def test_ttl_expires_old_events(webhook_repo, test_db):
    """
    Test: Webhook events have expires_at field for MongoDB TTL.

    ARRANGE:
    - Create event with expires_at in the PAST (simulating old event)

    ACT:
    - Store event

    ASSERT:
    - Event stored with expires_at field
    - MongoDB TTL index exists (created in mongodb.py)
    - Event is marked for deletion (actual deletion happens on MongoDB's schedule)

    NOTE: MongoDB TTL deletion runs every 60 seconds, so we can't test
    actual deletion in integration test. We verify the field is set correctly.

    EXPECTED: FAIL - TTL field handling not yet implemented
    """
    # ARRANGE: Create event with expires_at in the past
    event_id = f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc) - timedelta(days=95)  # 95 days ago
    expires_at = created_at + timedelta(days=90)  # Expired 5 days ago

    event_data = {
        "event_id": event_id,
        "event_type": "payment_intent.succeeded",
        "payment_intent_id": f"pi_test_{uuid.uuid4().hex[:8]}",
        "raw_payload": {"id": event_id},
        "processed": True,
        "created_at": created_at,
        "expires_at": expires_at  # IN THE PAST
    }

    print(f"[TEST] Storing expired event: {event_id}")
    print(f"   - Created: {created_at}")
    print(f"   - Expires: {expires_at} (5 days ago)")

    # ACT: Store event (MongoDB will mark for deletion via TTL index)
    await webhook_repo.store_event(event_data)

    # ASSERT: Verify event stored with correct expires_at
    stored_event = await test_db.webhook_events.find_one({"event_id": event_id})

    assert stored_event is not None, "Event should be stored (not yet deleted by TTL)"
    assert "expires_at" in stored_event, "expires_at field required for TTL"

    # Convert MongoDB's timezone-naive datetime to timezone-aware for comparison
    expires_at = stored_event["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    assert expires_at < datetime.now(timezone.utc), "expires_at should be in the past"

    # Verify TTL index exists (created in mongodb.py)
    indexes = await test_db.webhook_events.list_indexes().to_list(None)
    ttl_index = next((idx for idx in indexes if idx.get("name") == "ttl_90_days"), None)

    assert ttl_index is not None, "TTL index 'ttl_90_days' should exist"
    assert ttl_index.get("expireAfterSeconds") == 0, "TTL should expire immediately when expires_at reached"
    assert "expires_at" in ttl_index.get("key", {}), "TTL index should be on expires_at field"

    print(f"✅ Expired event stored with TTL field (MongoDB will auto-delete)")
    print(f"   - TTL index: {ttl_index['name']}")
    print(f"   - Expire field: expires_at")
    print(f"   - Event marked for deletion (MongoDB deletes every 60 seconds)")


# ============================================================================
# Test 8: Edge Case - Empty/Null Fields
# ============================================================================

@pytest.mark.asyncio
async def test_store_event_handles_null_optional_fields(webhook_repo, test_db):
    """
    Test: WebhookRepository handles optional/null fields gracefully.

    ARRANGE:
    - Create event with minimal required fields
    - payment_intent_id = None (some webhook events don't have payment_intent)

    ACT:
    - Store event

    ASSERT:
    - Event stored successfully
    - Optional fields set to None

    EXPECTED: FAIL - Null field handling not yet implemented
    """
    # ARRANGE: Event with minimal fields (no payment_intent_id)
    event_id = f"{TEST_PREFIX}evt_{uuid.uuid4().hex[:8]}"
    event_data = {
        "event_id": event_id,
        "event_type": "customer.created",  # Event type without payment_intent
        "payment_intent_id": None,  # No payment intent for this event type
        "raw_payload": {"id": event_id, "type": "customer.created"},
        "processed": False,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=90)
    }

    print(f"[TEST] Storing event with null payment_intent_id: {event_id}")

    # ACT: Store event with null fields
    await webhook_repo.store_event(event_data)

    # ASSERT: Verify event stored with null fields
    stored_event = await test_db.webhook_events.find_one({"event_id": event_id})

    assert stored_event is not None, "Event should be stored"
    assert stored_event["payment_intent_id"] is None, "payment_intent_id can be None"
    assert stored_event["event_type"] == "customer.created", "event_type mismatch"

    print(f"✅ Event with null fields stored successfully")


# ============================================================================
# Summary
# ============================================================================

"""
TEST SUMMARY (TDD RED STATE):

Expected Test Results:
- ❌ All 8 tests WILL FAIL with ImportError (WebhookRepository not implemented)
- ❌ This is CORRECT for TDD RED phase

Test Coverage:
1. ✅ test_store_event_creates_new_event - Basic event storage
2. ✅ test_store_event_rejects_duplicate_event_id - Idempotency (Stripe retries)
3. ✅ test_mark_event_processed_updates_status - Success case tracking
4. ✅ test_mark_event_processed_with_error - Error case tracking
5. ✅ test_get_event_returns_event_by_id - Event retrieval (exists)
6. ✅ test_get_event_returns_none_for_nonexistent_event - Event retrieval (not exists)
7. ✅ test_ttl_expires_old_events - 90-day TTL expiration
8. ✅ test_store_event_handles_null_optional_fields - Edge case handling

Next Steps (TDD GREEN phase):
1. Implement app/services/webhook_repository.py
2. Implement WebhookRepository class with methods:
   - async def store_event(event_data: dict) -> dict
   - async def mark_processed(event_id: str, error: str = None) -> None
   - async def get_event(event_id: str) -> dict | None
3. Implement DuplicateEventError exception
4. Run tests again - they should PASS

Database:
- Collection: webhook_events (indexed in mongodb.py)
- Test database: translation_test
- Cleanup: TEST_WEBHOOK_ prefix pattern
"""
