"""
Stripe test utilities - replaces private API usage.

This module provides HMAC-SHA256 signature generation for webhook testing,
replacing the private method: stripe.WebhookSignature._compute_signature()

Security Note:
- This utility is ONLY for testing purposes
- Uses the same HMAC-SHA256 algorithm as Stripe
- Generates signatures compatible with Stripe's webhook verification

Migration Context:
- Created during Stripe SDK migration (v7.8.0 → v13.2.0)
- Eliminates dependency on private Stripe API methods
- Ensures test suite remains stable across Stripe SDK upgrades
"""

import hmac
import hashlib
from typing import Union


def generate_stripe_webhook_signature(
    payload: Union[bytes, str],
    secret: str,
    timestamp: int
) -> str:
    """
    Generate Stripe webhook signature using HMAC-SHA256.

    This function replicates Stripe's webhook signature algorithm to generate
    valid signatures for testing purposes. It replaces the private method:
    stripe.WebhookSignature._compute_signature()

    Algorithm:
    1. Create signed payload: "{timestamp}.{payload}"
    2. Compute HMAC-SHA256 hash using webhook secret as key
    3. Format as Stripe signature header: "t={timestamp},v1={signature}"

    Args:
        payload: Raw webhook payload (bytes or str)
                 - If str, will be encoded to UTF-8
                 - If bytes, will be decoded then re-encoded
        secret: Webhook signing secret (e.g., "whsec_test_secret_12345")
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        Stripe signature header in format: "t={timestamp},v1={signature}"

    Example:
        >>> payload = b'{"id": "evt_123", "type": "payment_intent.succeeded"}'
        >>> secret = "whsec_test_secret_12345"
        >>> timestamp = 1638360000
        >>> sig = generate_stripe_webhook_signature(payload, secret, timestamp)
        >>> print(sig)
        "t=1638360000,v1=abc123def456..."

    Security:
        - ONLY use for testing purposes
        - NEVER use production webhook secrets in tests
        - Use test secrets like "whsec_test_secret_12345"

    References:
        - Stripe Webhook Signatures: https://stripe.com/docs/webhooks/signatures
        - HMAC-SHA256: https://en.wikipedia.org/wiki/HMAC
    """
    # Convert payload to bytes if it's a string
    if isinstance(payload, str):
        payload_bytes = payload.encode('utf-8')
    else:
        payload_bytes = payload

    # Decode payload to string for signature computation
    payload_str = payload_bytes.decode('utf-8')

    # Create the signed payload: "{timestamp}.{payload}"
    signed_payload = f"{timestamp}.{payload_str}"

    # Compute HMAC-SHA256 signature
    signature = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Return in Stripe signature header format
    return f"t={timestamp},v1={signature}"


# Backward compatibility alias for existing test code
compute_stripe_signature = generate_stripe_webhook_signature
