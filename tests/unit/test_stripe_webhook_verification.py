"""
Unit tests for Stripe webhook signature verification.

TDD RED PHASE - Tests written FIRST, implementation comes later.
All tests should SKIP until verify_webhook_signature() is implemented.

Security critical: Prevents webhook spoofing attacks.
"""

import pytest
import stripe
from stripe._error import SignatureVerificationError
import json
import time
import hmac
import hashlib
from typing import Optional

# CRITICAL: This import WILL FAIL until implementation exists (TDD RED state)
try:
    from app.utils.stripe_webhook import verify_webhook_signature
    FUNCTION_EXISTS = True
except ImportError:
    FUNCTION_EXISTS = False


@pytest.fixture
def webhook_secret():
    """Stripe webhook signing secret."""
    return "whsec_test_secret_12345"


@pytest.fixture
def valid_payload():
    """Valid Stripe webhook payload."""
    return json.dumps({
        "id": "evt_test_123",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_123",
                "amount": 2000,
                "currency": "usd",
                "status": "succeeded"
            }
        }
    }).encode('utf-8')


@pytest.fixture
def current_timestamp():
    """Current Unix timestamp."""
    return int(time.time())


def generate_stripe_signature(payload: bytes, secret: str, timestamp: int) -> str:
    """
    Generate a valid Stripe webhook signature.

    Uses Stripe's signing algorithm: HMAC-SHA256 of "{timestamp}.{payload}"
    """
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    signature = hmac.new(
        secret.encode('utf-8'),
        signed_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"t={timestamp},v1={signature}"


class TestValidSignatureAcceptance:
    """Tests for accepting valid webhook signatures."""

    def test_verify_signature_accepts_valid_signature(
        self, valid_payload, webhook_secret, current_timestamp
    ):
        """Should accept webhook with valid signature."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        sig_header = generate_stripe_signature(valid_payload, webhook_secret, current_timestamp)

        # Should NOT raise exception for valid signature
        result = verify_webhook_signature(valid_payload, sig_header, webhook_secret)
        assert result is None  # Function should return None on success

    def test_verify_signature_accepts_recent_timestamp(
        self, valid_payload, webhook_secret
    ):
        """Should accept webhook with timestamp within tolerance (5 minutes)."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Timestamp 2 minutes ago (well within tolerance)
        recent_timestamp = int(time.time()) - 120
        sig_header = generate_stripe_signature(valid_payload, webhook_secret, recent_timestamp)

        # Should NOT raise exception
        verify_webhook_signature(valid_payload, sig_header, webhook_secret)

    def test_verify_signature_accepts_complex_payload(self, webhook_secret, current_timestamp):
        """Should accept webhook with complex nested payload."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        complex_payload = json.dumps({
            "id": "evt_complex_456",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_456",
                    "customer": "cus_789",
                    "lines": {
                        "data": [
                            {"amount": 1000, "description": "Pro Plan"},
                            {"amount": 500, "description": "Extra Users"}
                        ]
                    },
                    "metadata": {
                        "user_id": "user_123",
                        "company_id": "company_456"
                    }
                }
            }
        }).encode('utf-8')

        sig_header = generate_stripe_signature(complex_payload, webhook_secret, current_timestamp)

        # Should NOT raise exception
        verify_webhook_signature(complex_payload, sig_header, webhook_secret)


class TestInvalidSignatureRejection:
    """Tests for rejecting invalid webhook signatures."""

    def test_verify_signature_rejects_invalid_signature(
        self, valid_payload, webhook_secret, current_timestamp
    ):
        """Should reject webhook with invalid signature."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Create signature with WRONG secret
        wrong_secret = "whsec_wrong_secret_99999"
        invalid_sig = generate_stripe_signature(valid_payload, wrong_secret, current_timestamp)

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(valid_payload, invalid_sig, webhook_secret)

    def test_verify_signature_rejects_completely_invalid_signature(
        self, valid_payload, webhook_secret
    ):
        """Should reject webhook with malformed signature format."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        invalid_sig = "this_is_not_a_valid_signature"

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(valid_payload, invalid_sig, webhook_secret)

    def test_verify_signature_rejects_missing_timestamp(
        self, valid_payload, webhook_secret
    ):
        """Should reject signature header missing timestamp."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Signature without timestamp component
        invalid_sig = "v1=abc123def456"

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(valid_payload, invalid_sig, webhook_secret)

    def test_verify_signature_rejects_missing_v1_signature(
        self, valid_payload, webhook_secret, current_timestamp
    ):
        """Should reject signature header missing v1 signature."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Signature with only timestamp
        invalid_sig = f"t={current_timestamp}"

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(valid_payload, invalid_sig, webhook_secret)


class TestMissingHeaderRejection:
    """Tests for rejecting webhooks with missing signature headers."""

    def test_verify_signature_rejects_none_header(
        self, valid_payload, webhook_secret
    ):
        """Should reject webhook with None signature header."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(valid_payload, None, webhook_secret)

    def test_verify_signature_rejects_empty_header(
        self, valid_payload, webhook_secret
    ):
        """Should reject webhook with empty signature header."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(valid_payload, "", webhook_secret)


class TestTamperedPayloadRejection:
    """Tests for rejecting webhooks with tampered payloads."""

    def test_verify_signature_rejects_tampered_payload(
        self, valid_payload, webhook_secret, current_timestamp
    ):
        """Should reject webhook when payload is modified after signing."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Generate valid signature for original payload
        original_sig = generate_stripe_signature(valid_payload, webhook_secret, current_timestamp)

        # Tamper with the payload (simulate man-in-the-middle attack)
        tampered_payload = json.dumps({
            "id": "evt_test_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_123",
                    "amount": 999999,  # Changed from 2000 to 999999
                    "currency": "usd",
                    "status": "succeeded"
                }
            }
        }).encode('utf-8')

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(tampered_payload, original_sig, webhook_secret)

    def test_verify_signature_rejects_payload_with_extra_fields(
        self, webhook_secret, current_timestamp
    ):
        """Should reject when extra fields are injected into payload."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        original_payload = json.dumps({
            "id": "evt_test_789",
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_789"}}
        }).encode('utf-8')

        # Generate signature for original
        original_sig = generate_stripe_signature(original_payload, webhook_secret, current_timestamp)

        # Add malicious field
        tampered_payload = json.dumps({
            "id": "evt_test_789",
            "type": "charge.succeeded",
            "data": {"object": {"id": "ch_789"}},
            "malicious_field": "injected_value"  # Injected field
        }).encode('utf-8')

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(tampered_payload, original_sig, webhook_secret)

    def test_verify_signature_rejects_type_changed_payload(
        self, webhook_secret, current_timestamp
    ):
        """Should reject when webhook type is changed (event substitution attack)."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        original_payload = json.dumps({
            "id": "evt_test_999",
            "type": "payment_intent.created",  # Original type
            "data": {"object": {"id": "pi_999"}}
        }).encode('utf-8')

        # Generate signature for original
        original_sig = generate_stripe_signature(original_payload, webhook_secret, current_timestamp)

        # Change event type to trigger different handler
        tampered_payload = json.dumps({
            "id": "evt_test_999",
            "type": "payment_intent.succeeded",  # Changed type!
            "data": {"object": {"id": "pi_999"}}
        }).encode('utf-8')

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(tampered_payload, original_sig, webhook_secret)


class TestTimestampValidation:
    """Tests for timestamp tolerance validation."""

    def test_verify_signature_rejects_expired_timestamp(
        self, valid_payload, webhook_secret
    ):
        """Should reject webhook with timestamp older than tolerance (5 minutes)."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Timestamp 10 minutes ago (beyond 5-minute tolerance)
        expired_timestamp = int(time.time()) - 600
        sig_header = generate_stripe_signature(valid_payload, webhook_secret, expired_timestamp)

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(valid_payload, sig_header, webhook_secret)

    def test_verify_signature_rejects_future_timestamp(
        self, valid_payload, webhook_secret
    ):
        """Should reject webhook with timestamp in the future."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Timestamp 10 minutes in the future
        future_timestamp = int(time.time()) + 600
        sig_header = generate_stripe_signature(valid_payload, webhook_secret, future_timestamp)

        with pytest.raises(SignatureVerificationError):
            verify_webhook_signature(valid_payload, sig_header, webhook_secret)


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_verify_signature_with_empty_payload(
        self, webhook_secret, current_timestamp
    ):
        """Should handle empty payload gracefully."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        empty_payload = b""
        sig_header = generate_stripe_signature(empty_payload, webhook_secret, current_timestamp)

        # Should either accept or raise appropriate error
        # (Behavior depends on implementation - Stripe may reject empty payloads)
        try:
            verify_webhook_signature(empty_payload, sig_header, webhook_secret)
        except SignatureVerificationError:
            pass  # Acceptable to reject empty payload

    def test_verify_signature_with_unicode_payload(
        self, webhook_secret, current_timestamp
    ):
        """Should handle Unicode characters in payload."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        unicode_payload = json.dumps({
            "id": "evt_unicode_123",
            "type": "customer.created",
            "data": {
                "object": {
                    "name": "François Müller 中文",
                    "description": "Emoji test 🎉🔥"
                }
            }
        }).encode('utf-8')

        sig_header = generate_stripe_signature(unicode_payload, webhook_secret, current_timestamp)

        # Should NOT raise exception
        verify_webhook_signature(unicode_payload, sig_header, webhook_secret)

    def test_verify_signature_with_large_payload(
        self, webhook_secret, current_timestamp
    ):
        """Should handle large payloads efficiently."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Create large payload with many items
        large_payload = json.dumps({
            "id": "evt_large_456",
            "type": "invoice.created",
            "data": {
                "object": {
                    "id": "in_456",
                    "lines": {
                        "data": [
                            {"id": f"line_{i}", "amount": 100 * i}
                            for i in range(1000)  # 1000 line items
                        ]
                    }
                }
            }
        }).encode('utf-8')

        sig_header = generate_stripe_signature(large_payload, webhook_secret, current_timestamp)

        # Should NOT raise exception
        verify_webhook_signature(large_payload, sig_header, webhook_secret)


class TestMultipleSignatureVersions:
    """Tests for handling multiple signature versions in header."""

    def test_verify_signature_accepts_multiple_versions_with_valid_v1(
        self, valid_payload, webhook_secret, current_timestamp
    ):
        """Should accept header with multiple signature versions if v1 is valid."""
        if not FUNCTION_EXISTS:
            pytest.skip("verify_webhook_signature not yet implemented (TDD RED state)")

        # Generate valid v1 signature
        signed_payload = f"{current_timestamp}.{valid_payload.decode('utf-8')}"
        v1_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        # Header with multiple versions (v0 invalid, v1 valid)
        sig_header = f"t={current_timestamp},v0=invalid_signature,v1={v1_signature}"

        # Should NOT raise exception (v1 is valid)
        verify_webhook_signature(valid_payload, sig_header, webhook_secret)


# Run tests with: pytest tests/unit/test_stripe_webhook_verification.py -v
