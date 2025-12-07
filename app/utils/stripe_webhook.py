"""
Stripe webhook signature verification utility.

Security critical: Prevents webhook spoofing and replay attacks.
Uses Stripe's HMAC-SHA256 signature verification with timestamp validation.

TDD GREEN PHASE - Implementation to make tests pass.
"""

import stripe
from typing import Optional
import time
import re

# Import from public API (v8+ compatible)
# Fallback to private module for backward compatibility with v7.8.0
try:
    from stripe.error import SignatureVerificationError
except ImportError:
    # Fallback for Stripe SDK < v8.0
    from stripe._error import SignatureVerificationError


def verify_webhook_signature(
    payload: bytes,
    sig_header: Optional[str],
    secret: str
) -> None:
    """
    Verify Stripe webhook signature.

    Validates webhook authenticity by verifying HMAC-SHA256 signature and timestamp.
    Prevents webhook spoofing, replay attacks, and payload tampering.

    Args:
        payload: Raw webhook payload (bytes) - must be original request body
        sig_header: stripe-signature header value containing timestamp and signature
        secret: Webhook signing secret (STRIPE_WEBHOOK_SECRET from environment)

    Raises:
        SignatureVerificationError: If signature verification fails due to:
            - Missing or empty sig_header
            - Invalid signature format
            - Signature mismatch (wrong secret or tampered payload)
            - Expired timestamp (>5 minutes old)
            - Future timestamp
            - Missing required signature components (t= or v1=)

    Security Notes:
        - Uses HMAC-SHA256 signature verification
        - Validates timestamp to prevent replay attacks
        - Tolerance window: 5 minutes (Stripe default)
        - Signature format: "t=<timestamp>,v1=<signature>[,v0=<signature>]"
        - Verifies payload integrity (rejects modified payloads)

    Implementation:
        Uses Stripe's official webhook verification library for security best practices.
        The library handles:
        1. Signature header parsing
        2. HMAC-SHA256 signature computation
        3. Constant-time signature comparison (timing attack protection)
        4. Timestamp validation with configurable tolerance

    Example:
        >>> from fastapi import Request, HTTPException
        >>> from app.core.config import settings
        >>>
        >>> @app.post("/webhooks/stripe")
        >>> async def stripe_webhook(request: Request):
        ...     payload = await request.body()
        ...     sig_header = request.headers.get("stripe-signature")
        ...
        ...     try:
        ...         verify_webhook_signature(payload, sig_header, settings.stripe_webhook_secret)
        ...         # Signature valid, process webhook event
        ...         event = stripe.Event.construct_from(json.loads(payload), stripe.api_key)
        ...         return {"status": "success"}
        ...     except stripe.error.SignatureVerificationError as e:
        ...         # Invalid signature, reject webhook
        ...         raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    Attack Prevention:
        - Spoofing: Rejects requests without valid HMAC signature
        - Replay: Rejects timestamps outside tolerance window
        - Tampering: Rejects modified payloads (signature won't match)
        - Event substitution: Signature covers entire payload including event type
        - Man-in-the-middle: HTTPS + signature ensures end-to-end authenticity

    References:
        - Stripe Webhook Security: https://stripe.com/docs/webhooks/signatures
        - HMAC-SHA256: https://en.wikipedia.org/wiki/HMAC
        - Timing attacks: https://codahale.com/a-lesson-in-timing-attacks/
    """
    # CRITICAL: Check for missing header BEFORE calling Stripe verification
    # Tests require explicit check with clear error message
    if not sig_header:
        raise SignatureVerificationError(
            "Missing stripe-signature header", sig_header
        )

    # Extract timestamp from signature header for additional validation
    # Format: "t=<timestamp>,v1=<signature>[,v0=<signature>]"
    timestamp_match = re.search(r't=(\d+)', sig_header)
    if timestamp_match:
        webhook_timestamp = int(timestamp_match.group(1))
        current_timestamp = int(time.time())

        # Reject future timestamps (clock skew tolerance: 5 minutes)
        # Stripe library only checks for expired timestamps, not future ones
        if webhook_timestamp > current_timestamp + 300:  # 5 minutes tolerance
            raise SignatureVerificationError(
                "Timestamp is too far in the future", sig_header
            )

    # Verify signature using Stripe's official library
    # This automatically validates:
    # 1. Signature format (t=<timestamp>,v1=<signature>)
    # 2. HMAC-SHA256 signature correctness
    # 3. Timestamp freshness (default 5-minute tolerance)
    # 4. Payload integrity (rejects tampered data)
    #
    # construct_event() performs verification and returns parsed event object
    # We only need verification, so we call it but don't use the return value
    try:
        stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=secret
        )
    except SignatureVerificationError:
        # Re-raise to propagate to caller with original error details
        # Stripe library provides detailed error messages:
        # - "No signatures found with expected scheme"
        # - "Timestamp outside the tolerance zone"
        # - "None of the signatures matched the expected signature"
        raise
    except Exception:
        # Handle edge cases like empty payload causing JSON decode errors
        # Treat as invalid signature (empty payloads are not valid webhooks)
        raise SignatureVerificationError(
            "Invalid webhook payload", sig_header
        )
