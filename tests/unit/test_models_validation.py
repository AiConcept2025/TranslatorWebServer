"""
Unit tests for Pydantic model validation in subscription, invoice, and payment models.

Tests validate:
- Field constraints (min/max, required fields)
- Custom validators
- Computed fields
- Business logic validation
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.subscription import UsagePeriod, SubscriptionCreate, SubscriptionUpdate
from app.models.invoice import BillingPeriod, LineItem, InvoiceListItem
from app.models.payment import Payment, PaymentListItem, RefundSchema


# ============================================================================
# Subscription Model Tests
# ============================================================================

class TestUsagePeriod:
    """Test UsagePeriod model validation."""

    def test_period_number_valid_range(self):
        """Test period_number accepts values 1-12."""
        valid_data = {
            "period_start": datetime.now(timezone.utc),
            "period_end": datetime.now(timezone.utc),
            "units_allocated": 100,
            "units_used": 50,
            "units_remaining": 50
        }

        # Valid period numbers
        for period_num in [1, 6, 12]:
            data = {**valid_data, "period_number": period_num}
            period = UsagePeriod(**data)
            assert period.period_number == period_num

    def test_period_number_invalid_range(self):
        """Test period_number rejects values outside 1-12."""
        base_data = {
            "period_start": datetime.now(timezone.utc),
            "period_end": datetime.now(timezone.utc),
            "units_allocated": 100,
            "units_used": 50,
            "units_remaining": 50
        }

        # Invalid: 0
        with pytest.raises(ValidationError) as exc_info:
            UsagePeriod(**{**base_data, "period_number": 0})
        assert "greater than or equal to 1" in str(exc_info.value)

        # Invalid: 13
        with pytest.raises(ValidationError) as exc_info:
            UsagePeriod(**{**base_data, "period_number": 13})
        assert "less than or equal to 12" in str(exc_info.value)


class TestSubscriptionCreate:
    """Test SubscriptionCreate model validation."""

    def test_billing_frequency_default(self):
        """Test billing_frequency defaults to 'monthly'."""
        data = {
            "company_name": "Test Corp",
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.15,
            "subscription_price": 150.00,
            "start_date": datetime.now(timezone.utc)
        }
        sub = SubscriptionCreate(**data)
        assert sub.billing_frequency == "monthly"

    def test_billing_frequency_valid_values(self):
        """Test billing_frequency accepts monthly, quarterly, yearly."""
        base_data = {
            "company_name": "Test Corp",
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.15,
            "subscription_price": 150.00,
            "start_date": datetime.now(timezone.utc)
        }

        for freq in ["monthly", "quarterly", "yearly"]:
            data = {**base_data, "billing_frequency": freq}
            sub = SubscriptionCreate(**data)
            assert sub.billing_frequency == freq

    def test_billing_frequency_invalid_value(self):
        """Test billing_frequency rejects invalid values."""
        data = {
            "company_name": "Test Corp",
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.15,
            "subscription_price": 150.00,
            "start_date": datetime.now(timezone.utc),
            "billing_frequency": "daily"
        }

        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**data)
        assert "billing_frequency" in str(exc_info.value)

    def test_payment_terms_days_default(self):
        """Test payment_terms_days defaults to 30."""
        data = {
            "company_name": "Test Corp",
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.15,
            "subscription_price": 150.00,
            "start_date": datetime.now(timezone.utc)
        }
        sub = SubscriptionCreate(**data)
        assert sub.payment_terms_days == 30

    def test_payment_terms_days_valid_range(self):
        """Test payment_terms_days accepts values 1-90."""
        base_data = {
            "company_name": "Test Corp",
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.15,
            "subscription_price": 150.00,
            "start_date": datetime.now(timezone.utc)
        }

        for days in [1, 30, 60, 90]:
            data = {**base_data, "payment_terms_days": days}
            sub = SubscriptionCreate(**data)
            assert sub.payment_terms_days == days

    def test_payment_terms_days_invalid_range(self):
        """Test payment_terms_days rejects values outside 1-90."""
        base_data = {
            "company_name": "Test Corp",
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.15,
            "subscription_price": 150.00,
            "start_date": datetime.now(timezone.utc)
        }

        # Invalid: 0
        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**{**base_data, "payment_terms_days": 0})
        assert "greater than or equal to 1" in str(exc_info.value)

        # Invalid: 91
        with pytest.raises(ValidationError) as exc_info:
            SubscriptionCreate(**{**base_data, "payment_terms_days": 91})
        assert "less than or equal to 90" in str(exc_info.value)


# ============================================================================
# Invoice Model Tests
# ============================================================================

class TestBillingPeriod:
    """Test BillingPeriod model validation."""

    def test_valid_billing_period(self):
        """Test BillingPeriod with valid data."""
        data = {
            "period_numbers": [1, 2, 3],
            "period_start": datetime.now(timezone.utc),
            "period_end": datetime.now(timezone.utc)
        }
        period = BillingPeriod(**data)
        assert period.period_numbers == [1, 2, 3]

    def test_period_numbers_must_be_sorted(self):
        """Test period_numbers must be sorted."""
        data = {
            "period_numbers": [3, 1, 2],
            "period_start": datetime.now(timezone.utc),
            "period_end": datetime.now(timezone.utc)
        }

        with pytest.raises(ValidationError) as exc_info:
            BillingPeriod(**data)
        assert "must be sorted" in str(exc_info.value)

    def test_period_numbers_range_validation(self):
        """Test period_numbers must be 1-12."""
        base_data = {
            "period_start": datetime.now(timezone.utc),
            "period_end": datetime.now(timezone.utc)
        }

        # Invalid: 0
        with pytest.raises(ValidationError) as exc_info:
            BillingPeriod(**{**base_data, "period_numbers": [0, 1, 2]})
        assert "between 1 and 12" in str(exc_info.value)

        # Invalid: 13
        with pytest.raises(ValidationError) as exc_info:
            BillingPeriod(**{**base_data, "period_numbers": [11, 12, 13]})
        assert "between 1 and 12" in str(exc_info.value)

    def test_period_numbers_cannot_be_empty(self):
        """Test period_numbers cannot be empty."""
        data = {
            "period_numbers": [],
            "period_start": datetime.now(timezone.utc),
            "period_end": datetime.now(timezone.utc)
        }

        with pytest.raises(ValidationError) as exc_info:
            BillingPeriod(**data)
        assert "cannot be empty" in str(exc_info.value)


class TestLineItem:
    """Test LineItem model validation."""

    def test_valid_line_item(self):
        """Test LineItem with valid data."""
        data = {
            "description": "Base Subscription",
            "period_numbers": [1, 2, 3],
            "quantity": 3,
            "unit_price": 100.00,
            "amount": 300.00
        }
        item = LineItem(**data)
        assert item.amount == 300.00

    def test_amount_must_equal_quantity_times_unit_price(self):
        """Test amount validation (quantity × unit_price)."""
        # Valid calculation
        data = {
            "description": "Test Item",
            "period_numbers": [1],
            "quantity": 5,
            "unit_price": 10.50,
            "amount": 52.50
        }
        item = LineItem(**data)
        assert item.amount == 52.50

        # Invalid: wrong amount
        with pytest.raises(ValidationError) as exc_info:
            LineItem(**{
                "description": "Test Item",
                "period_numbers": [1],
                "quantity": 5,
                "unit_price": 10.50,
                "amount": 100.00  # Wrong!
            })
        assert "must equal quantity" in str(exc_info.value)

    def test_period_numbers_validation(self):
        """Test period_numbers must be 1-12."""
        base_data = {
            "description": "Test Item",
            "quantity": 1,
            "unit_price": 10.00,
            "amount": 10.00
        }

        # Invalid: 0
        with pytest.raises(ValidationError) as exc_info:
            LineItem(**{**base_data, "period_numbers": [0]})
        assert "between 1 and 12" in str(exc_info.value)

        # Invalid: empty
        with pytest.raises(ValidationError) as exc_info:
            LineItem(**{**base_data, "period_numbers": []})
        assert "cannot be empty" in str(exc_info.value)


class TestInvoiceListItem:
    """Test InvoiceListItem model validation."""

    def test_amount_due_computed_field(self):
        """Test amount_due is computed correctly."""
        data = {
            "_id": "507f1f77bcf86cd799439011",
            "company_name": "Test Corp",
            "subscription_id": "sub_123",
            "invoice_number": "INV-2025-001",
            "invoice_date": "2025-01-01T00:00:00Z",
            "due_date": "2025-01-31T00:00:00Z",
            "total_amount": 1000.00,
            "tax_amount": 60.00,
            "status": "sent",
            "created_at": "2025-01-01T00:00:00Z",
            "amount_paid": 250.00
        }
        invoice = InvoiceListItem(**data)
        assert invoice.amount_due == 750.00

    def test_amount_due_never_negative(self):
        """Test amount_due is never negative (overpaid scenario)."""
        data = {
            "_id": "507f1f77bcf86cd799439011",
            "company_name": "Test Corp",
            "subscription_id": "sub_123",
            "invoice_number": "INV-2025-001",
            "invoice_date": "2025-01-01T00:00:00Z",
            "due_date": "2025-01-31T00:00:00Z",
            "total_amount": 1000.00,
            "tax_amount": 60.00,
            "status": "paid",
            "created_at": "2025-01-01T00:00:00Z",
            "amount_paid": 1200.00  # Overpaid
        }
        invoice = InvoiceListItem(**data)
        assert invoice.amount_due == 0.0  # Never negative

    def test_amount_due_with_zero_paid(self):
        """Test amount_due when nothing is paid."""
        data = {
            "_id": "507f1f77bcf86cd799439011",
            "company_name": "Test Corp",
            "subscription_id": "sub_123",
            "invoice_number": "INV-2025-001",
            "invoice_date": "2025-01-01T00:00:00Z",
            "due_date": "2025-01-31T00:00:00Z",
            "total_amount": 1000.00,
            "tax_amount": 60.00,
            "status": "sent",
            "created_at": "2025-01-01T00:00:00Z",
            "amount_paid": 0.0
        }
        invoice = InvoiceListItem(**data)
        assert invoice.amount_due == 1000.00


# ============================================================================
# Payment Model Tests
# ============================================================================

class TestPayment:
    """Test Payment model validation."""

    def test_net_amount_computed_field(self):
        """Test net_amount is computed correctly."""
        data = {
            "company_name": "Test Corp",
            "user_email": "test@example.com",
            "stripe_payment_intent_id": "pi_123",
            "amount": 10000,  # $100.00 in cents
            "payment_status": "COMPLETED",
            "total_refunded": 25.00  # $25.00 refunded
        }
        payment = Payment(**data)
        assert payment.net_amount == 75.00

    def test_net_amount_never_negative(self):
        """Test net_amount is never negative (fully refunded)."""
        data = {
            "company_name": "Test Corp",
            "user_email": "test@example.com",
            "stripe_payment_intent_id": "pi_123",
            "amount": 10000,  # $100.00 in cents
            "payment_status": "REFUNDED",
            "total_refunded": 150.00  # Over-refunded (shouldn't happen but test boundary)
        }

        # Should fail validation
        with pytest.raises(ValidationError) as exc_info:
            Payment(**data)
        assert "cannot exceed payment amount" in str(exc_info.value)

    def test_total_refunded_validation(self):
        """Test total_refunded cannot exceed payment amount."""
        base_data = {
            "company_name": "Test Corp",
            "user_email": "test@example.com",
            "stripe_payment_intent_id": "pi_123",
            "amount": 10000,  # $100.00
            "payment_status": "COMPLETED"
        }

        # Valid: partial refund
        valid_data = {**base_data, "total_refunded": 50.00}
        payment = Payment(**valid_data)
        assert payment.total_refunded == 50.00

        # Valid: full refund
        valid_data = {**base_data, "total_refunded": 100.00}
        payment = Payment(**valid_data)
        assert payment.total_refunded == 100.00

        # Invalid: exceeds amount
        invalid_data = {**base_data, "total_refunded": 100.01}
        with pytest.raises(ValidationError) as exc_info:
            Payment(**invalid_data)
        assert "cannot exceed payment amount" in str(exc_info.value)

    def test_optional_subscription_fields(self):
        """Test invoice_id and subscription_id are optional."""
        # Individual user payment (no subscription)
        data = {
            "company_name": "N/A",
            "user_email": "user@example.com",
            "stripe_payment_intent_id": "pi_individual",
            "amount": 5000,
            "payment_status": "COMPLETED"
        }
        payment = Payment(**data)
        assert payment.invoice_id is None
        assert payment.subscription_id is None

        # Subscription payment
        data_with_subscription = {
            **data,
            "invoice_id": "inv_123",
            "subscription_id": "sub_456"
        }
        payment = Payment(**data_with_subscription)
        assert payment.invoice_id == "inv_123"
        assert payment.subscription_id == "sub_456"


# ============================================================================
# Integration Tests (Model Interoperability)
# ============================================================================

class TestModelInteroperability:
    """Test models work together correctly."""

    def test_invoice_with_billing_period_and_line_items(self):
        """Test invoice with quarterly billing period and line items."""
        # Create billing period
        billing_period_data = {
            "period_numbers": [1, 2, 3],
            "period_start": datetime(2025, 1, 1, tzinfo=timezone.utc),
            "period_end": datetime(2025, 3, 31, 23, 59, 59, tzinfo=timezone.utc)
        }
        billing_period = BillingPeriod(**billing_period_data)

        # Create line items
        line_items = [
            LineItem(
                description="Base Subscription - Q1",
                period_numbers=[1, 2, 3],
                quantity=3,
                unit_price=100.00,
                amount=300.00
            ),
            LineItem(
                description="Overage - January",
                period_numbers=[1],
                quantity=50,
                unit_price=0.10,
                amount=5.00
            )
        ]

        # Create invoice
        invoice_data = {
            "_id": "507f1f77bcf86cd799439011",
            "company_name": "Test Corp",
            "subscription_id": "sub_123",
            "invoice_number": "INV-2025-Q1-001",
            "invoice_date": "2025-04-01T00:00:00Z",
            "due_date": "2025-05-01T00:00:00Z",
            "total_amount": 323.30,  # 305 + 18.30 tax
            "tax_amount": 18.30,
            "status": "sent",
            "created_at": "2025-04-01T00:00:00Z",
            "billing_period": billing_period,
            "line_items": line_items,
            "subtotal": 305.00,
            "amount_paid": 0.0
        }
        invoice = InvoiceListItem(**invoice_data)

        # Assertions
        assert invoice.billing_period.period_numbers == [1, 2, 3]
        assert len(invoice.line_items) == 2
        assert invoice.subtotal == 305.00
        assert invoice.amount_due == 323.30

    def test_payment_linked_to_invoice_and_subscription(self):
        """Test payment with invoice and subscription linkage."""
        payment_data = {
            "company_name": "Test Corp",
            "user_email": "admin@testcorp.com",
            "stripe_payment_intent_id": "pi_quarterly_payment",
            "amount": 32330,  # $323.30 in cents
            "payment_status": "COMPLETED",
            "invoice_id": "507f1f77bcf86cd799439011",
            "subscription_id": "sub_123",
            "total_refunded": 0.0
        }
        payment = Payment(**payment_data)

        # Assertions
        assert payment.invoice_id == "507f1f77bcf86cd799439011"
        assert payment.subscription_id == "sub_123"
        assert payment.net_amount == 323.30
        assert payment.total_refunded == 0.0
