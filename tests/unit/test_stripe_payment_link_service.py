"""
Unit tests for StripePaymentLinkService.

Tests payment link creation, idempotency, error handling, and amount conversion
with mocked Stripe API calls.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId, Decimal128
from datetime import datetime, timezone

from app.services.stripe_payment_link_service import (
    StripePaymentLinkService,
    stripe_payment_link_service
)


class TestStripePaymentLinkService:
    """Unit tests for StripePaymentLinkService."""

    @pytest.mark.asyncio
    async def test_create_payment_link_success(self):
        """Test successful payment link creation with Stripe API."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-001",
            "total_amount": Decimal128("106.00"),
            "status": "sent"
        }

        mock_db = MagicMock()
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )

        # Act & Assert
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            mock_price.return_value = MagicMock(id="price_123abc")
            mock_link.return_value = MagicMock(
                id="plink_456def",
                url="https://buy.stripe.com/test_payment_link"
            )

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Payment link URL returned
            assert result == "https://buy.stripe.com/test_payment_link"

            # Verify Stripe API calls
            mock_price.assert_called_once_with(
                currency="usd",
                unit_amount=10600,  # $106.00 → 10600 cents
                product_data={
                    "name": "Invoice INV-2025-001",
                    "description": "Payment for invoice INV-2025-001"
                }
            )

            mock_link.assert_called_once()
            link_args = mock_link.call_args
            assert link_args[1]["line_items"][0]["price"] == "price_123abc"
            assert link_args[1]["line_items"][0]["quantity"] == 1
            assert link_args[1]["metadata"]["invoice_number"] == "INV-2025-001"

            # Verify database update
            mock_db.invoices.update_one.assert_called_once()
            update_call = mock_db.invoices.update_one.call_args
            assert update_call[0][0] == {"_id": invoice["_id"]}
            update_data = update_call[0][1]["$set"]
            assert update_data["stripe_payment_link_url"] == "https://buy.stripe.com/test_payment_link"
            assert update_data["stripe_payment_link_id"] == "plink_456def"
            assert "payment_link_created_at" in update_data

    @pytest.mark.asyncio
    async def test_idempotency_returns_existing_link(self):
        """Test that existing payment links are reused (idempotency)."""
        # Arrange
        service = StripePaymentLinkService()

        existing_url = "https://buy.stripe.com/existing_link"
        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-002",
            "total_amount": Decimal128("50.00"),
            "status": "sent",
            "stripe_payment_link_url": existing_url,  # Already has link
            "stripe_payment_link_id": "plink_existing"
        }

        mock_db = MagicMock()

        # Act
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Returns existing URL without creating new link
            assert result == existing_url

            # Stripe API should NOT be called
            mock_price.assert_not_called()
            mock_link.assert_not_called()

            # Database should NOT be updated
            mock_db.invoices.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_skip_paid_invoice(self):
        """Test that paid invoices are skipped (no payment link needed)."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-003",
            "total_amount": Decimal128("200.00"),
            "status": "paid"  # Already paid
        }

        mock_db = MagicMock()

        # Act
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Returns None for paid invoice
            assert result is None

            # Stripe API should NOT be called
            mock_price.assert_not_called()
            mock_link.assert_not_called()

            # Database should NOT be updated
            mock_db.invoices.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_decimal128_to_cents_conversion(self):
        """Test conversion of Decimal128 to cents for Stripe API."""
        # Arrange
        service = StripePaymentLinkService()

        test_cases = [
            (Decimal128("100.00"), 10000),  # Whole number
            (Decimal128("99.99"), 9999),     # Cents precision
            (Decimal128("0.50"), 50),        # Less than $1
            (Decimal128("1234.56"), 123456), # Large amount
            (Decimal128("10.005"), 1001),    # Rounding (10.005 → 10.01 → 1001 cents)
        ]

        for decimal_value, expected_cents in test_cases:
            # Act
            result = service._convert_to_cents(decimal_value)

            # Assert
            assert result == expected_cents, f"Failed for {decimal_value}: expected {expected_cents}, got {result}"

    @pytest.mark.asyncio
    async def test_convert_to_cents_handles_none(self):
        """Test that None amount is handled gracefully."""
        # Arrange
        service = StripePaymentLinkService()

        # Act
        result = service._convert_to_cents(None)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_convert_to_cents_handles_zero(self):
        """Test that zero amount is rejected."""
        # Arrange
        service = StripePaymentLinkService()

        # Act
        result = service._convert_to_cents(0)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_convert_to_cents_handles_negative(self):
        """Test that negative amounts are rejected."""
        # Arrange
        service = StripePaymentLinkService()

        # Act
        result = service._convert_to_cents(-50.00)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_convert_to_cents_handles_invalid_types(self):
        """Test that invalid types return None."""
        # Arrange
        service = StripePaymentLinkService()

        # Act & Assert
        assert service._convert_to_cents("invalid") is None
        assert service._convert_to_cents([100]) is None
        assert service._convert_to_cents({"amount": 100}) is None

    @pytest.mark.asyncio
    async def test_stripe_api_error_returns_none(self):
        """Test graceful handling of Stripe API errors."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-004",
            "total_amount": Decimal128("75.00"),
            "status": "sent"
        }

        mock_db = MagicMock()

        # Act
        with patch('stripe.Price.create') as mock_price:
            import stripe
            mock_price.side_effect = stripe.APIError("Stripe API error")

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Returns None on Stripe error (graceful degradation)
            assert result is None

            # Database should NOT be updated on error
            mock_db.invoices.update_one.assert_not_called()

    @pytest.mark.asyncio
    async def test_stripe_authentication_error_returns_none(self):
        """Test handling of Stripe authentication errors."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-005",
            "total_amount": Decimal128("100.00"),
            "status": "sent"
        }

        mock_db = MagicMock()

        # Act
        with patch('stripe.Price.create') as mock_price:
            import stripe
            mock_price.side_effect = stripe.AuthenticationError("Invalid API key")

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Returns None on auth error
            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_amount_returns_none(self):
        """Test that invalid invoice amounts prevent payment link creation."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-006",
            "total_amount": None,  # Invalid amount
            "status": "sent"
        }

        mock_db = MagicMock()

        # Act
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Returns None for invalid amount
            assert result is None

            # Stripe API should NOT be called
            mock_price.assert_not_called()
            mock_link.assert_not_called()

    @pytest.mark.asyncio
    async def test_database_update_failure_does_not_crash(self):
        """Test that database update failures are logged but don't crash."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-007",
            "total_amount": Decimal128("80.00"),
            "status": "sent"
        }

        mock_db = MagicMock()
        # Simulate database update failure
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=0)
        )

        # Act
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            mock_price.return_value = MagicMock(id="price_789")
            mock_link.return_value = MagicMock(
                id="plink_789",
                url="https://buy.stripe.com/test_789"
            )

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Payment link still returned even if DB update fails
            assert result == "https://buy.stripe.com/test_789"

            # Verify update was attempted
            mock_db.invoices.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_none(self):
        """Test graceful handling of unexpected errors."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-008",
            "total_amount": Decimal128("60.00"),
            "status": "sent"
        }

        mock_db = MagicMock()

        # Act
        with patch('stripe.Price.create') as mock_price:
            mock_price.side_effect = Exception("Unexpected error")

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Returns None on unexpected error
            assert result is None

    @pytest.mark.asyncio
    async def test_singleton_instance_exists(self):
        """Test that singleton instance is available."""
        # Assert: Singleton instance exists
        assert stripe_payment_link_service is not None
        assert isinstance(stripe_payment_link_service, StripePaymentLinkService)

    @pytest.mark.asyncio
    async def test_metadata_includes_invoice_info(self):
        """Test that payment link metadata includes invoice information."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "invoice_number": "INV-2025-009",
            "total_amount": Decimal128("90.00"),
            "status": "sent"
        }

        mock_db = MagicMock()
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )

        # Act
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            mock_price.return_value = MagicMock(id="price_meta")
            mock_link.return_value = MagicMock(
                id="plink_meta",
                url="https://buy.stripe.com/test_meta"
            )

            await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: Metadata includes invoice_id and invoice_number
            link_args = mock_link.call_args
            metadata = link_args[1]["metadata"]
            assert metadata["invoice_id"] == "507f1f77bcf86cd799439011"
            assert metadata["invoice_number"] == "INV-2025-009"

    @pytest.mark.asyncio
    async def test_payment_link_url_format(self):
        """Test that payment link URL has correct format."""
        # Arrange
        service = StripePaymentLinkService()

        invoice = {
            "_id": ObjectId(),
            "invoice_number": "INV-2025-010",
            "total_amount": Decimal128("120.00"),
            "status": "sent"
        }

        mock_db = MagicMock()
        mock_db.invoices.update_one = AsyncMock(
            return_value=MagicMock(modified_count=1)
        )

        # Act
        with patch('stripe.Price.create') as mock_price, \
             patch('stripe.PaymentLink.create') as mock_link:

            mock_price.return_value = MagicMock(id="price_url")
            mock_link.return_value = MagicMock(
                id="plink_url",
                url="https://buy.stripe.com/test_payment_url_format"
            )

            result = await service.create_or_get_payment_link(invoice, mock_db)

            # Assert: URL starts with https://
            assert result.startswith("https://")
            assert "buy.stripe.com" in result
