"""
Stripe webhook API endpoint.

Purpose:
- Receive Stripe webhook events via HTTP POST /api/webhooks/stripe
- Verify webhook signature for security (HMAC-SHA256)
- Return 200 immediately to Stripe (< 5 seconds)
- Process events asynchronously in background

Security:
- HMAC-SHA256 signature verification prevents webhook spoofing
- Timestamp validation prevents replay attacks
- Invalid signature → 400 error

Idempotency:
- Event-level: WebhookRepository uses unique index on event_id
- Payment-level: WebhookHandler checks for existing payments
- Duplicate events → 200 response (Stripe expects 200 to stop retrying)

Performance:
- Returns 200 immediately (< 5s requirement)
- Background task processes event asynchronously
- No blocking operations in request handler

Webhook Events Handled:
1. payment_intent.succeeded → Create payment, trigger file processing
2. payment_intent.payment_failed → Log failure
3. charge.refunded → Update payment status to refunded

Integration Tests:
- tests/integration/test_webhooks_endpoint_integration.py (9 comprehensive tests)
- Test coverage: signature validation, idempotency, payment processing, error handling

TDD GREEN PHASE - Implementation to make integration tests pass.
"""

import logging
import json
import uuid
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import stripe

# Import from public API (v8+ compatible)
# Fallback to private module for backward compatibility with v7.8.0
try:
    from stripe.error import SignatureVerificationError
except ImportError:
    # Fallback for Stripe SDK < v8.0
    from stripe._error import SignatureVerificationError

from app.config import settings
from app.database.mongodb import database
from app.services.webhook_handler import WebhookHandler
from app.utils.stripe_webhook import verify_webhook_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Stripe webhook endpoint.

    Security:
    - Verifies stripe-signature header using HMAC-SHA256
    - Rejects invalid signatures with 400 status code
    - Validates timestamp to prevent replay attacks

    Idempotency:
    - Event-level: Unique index on webhook_events.event_id
    - Payment-level: Check for existing payment records
    - Returns 200 for duplicate events (Stripe expects 200 to stop retrying)

    Performance:
    - Returns 200 immediately (< 5 second requirement)
    - Processes event in background task (non-blocking)
    - Stripe retries on non-200 responses

    Webhook Events Handled:
    - payment_intent.succeeded → Create payment, trigger file processing
    - payment_intent.payment_failed → Log failure, store error
    - charge.refunded → Update payment status to refunded
    - Unsupported events → 200 response, stored for audit

    Error Handling:
    - Invalid signature → 400 {"detail": "Invalid signature"}
    - Malformed payload → 400 {"detail": "Invalid payload"}
    - Missing signature header → 400 {"detail": "Invalid signature"}
    - Processing errors → Still returns 200 (background task handles errors)

    Args:
        request: FastAPI Request object (provides raw body and headers)
        background_tasks: FastAPI BackgroundTasks (for async processing)

    Returns:
        200: {"received": True, "event_id": "evt_..."}
        400: {"detail": "Invalid signature"} or {"detail": "Invalid payload"}

    Example:
        >>> # Valid webhook from Stripe
        >>> curl -X POST http://localhost:8000/api/webhooks/stripe \\
        ...      -H "stripe-signature: t=1234567890,v1=abc123..." \\
        ...      -d '{"id": "evt_123", "type": "payment_intent.succeeded", ...}'
        >>> {"received": true, "event_id": "evt_123"}

        >>> # Invalid signature
        >>> curl -X POST http://localhost:8000/api/webhooks/stripe \\
        ...      -H "stripe-signature: invalid" \\
        ...      -d '{"id": "evt_123", ...}'
        >>> {"detail": "Invalid signature"}
    """
    # Generate unique request ID for correlation across logs
    request_id = str(uuid.uuid4())[:8]  # Short UUID for readability

    # STEP 1: Extract raw payload and signature header
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    logger.info(f"[WEBHOOK] [{request_id}] Received webhook from {request.client.host}")

    # STEP 2: VERIFY SIGNATURE (Security Critical - MUST happen BEFORE processing)
    try:
        verify_webhook_signature(payload, sig_header, settings.stripe_webhook_secret)
        logger.info(f"[WEBHOOK_SECURITY] [{request_id}] Valid signature verified from IP {request.client.host}")
    except SignatureVerificationError as e:
        # Invalid signature - log security event and reject request
        logger.warning(f"[WEBHOOK_SECURITY] [{request_id}] Invalid signature from IP {request.client.host}: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        # Other signature verification errors (malformed header, etc.)
        logger.error(f"[WEBHOOK_SECURITY] [{request_id}] Signature verification error: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # STEP 3: PARSE EVENT (Convert raw payload to Stripe Event object)
    try:
        # Parse JSON payload
        event_dict = json.loads(payload.decode('utf-8'))

        # Construct Stripe Event object (validates event structure)
        event = stripe.Event.construct_from(event_dict, settings.stripe_api_key)

        logger.info(f"[WEBHOOK] [{request_id}] Event received: {event.id} type={event.type}")
    except (ValueError, json.JSONDecodeError) as e:
        # Malformed JSON payload
        logger.error(f"[WEBHOOK] [{request_id}] Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    # STEP 4: PROCESS ASYNCHRONOUSLY (Background Task)
    # IMPORTANT: Return 200 IMMEDIATELY to Stripe (< 5 second requirement)
    # Background task handles event processing, idempotency, database operations
    handler = WebhookHandler(database)

    async def process_event():
        """
        Background task to process webhook event.

        Flow:
        1. Store event in webhook_events (deduplication via unique index)
        2. Route event by type (payment_intent.succeeded, payment_failed, charge.refunded)
        3. Implement payment-level idempotency (check for existing payments)
        4. Trigger payment processing or update payment status
        5. Mark event as processed

        Error Handling:
        - All errors caught and logged (don't crash background task)
        - Events marked as processed with error message
        - Duplicate events handled gracefully (return success)
        """
        try:
            result = await handler.handle_event(event.to_dict())
            logger.info(f"[WEBHOOK] [{request_id}] Completed {event.id}: {result}")
        except Exception as e:
            # Catch all errors in background task (don't crash)
            # Event will be marked as processed with error in WebhookHandler
            logger.error(f"[WEBHOOK] [{request_id}] Failed {event.id}: {e}", exc_info=True)

    # Add background task to queue
    background_tasks.add_task(process_event)

    # STEP 5: RETURN 200 IMMEDIATELY (Stripe expects fast response < 5s)
    # CRITICAL: Return 200 even for duplicates/unsupported events (Stripe retries on non-200)
    logger.info(f"[WEBHOOK] [{request_id}] Queued event {event.id} for processing")
    return JSONResponse({"received": True, "event_id": event.id, "request_id": request_id})
