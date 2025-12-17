"""
Invoice generation service for creating quarterly invoices with line items.

This service generates invoices for subscriptions based on billing periods,
calculating base subscription charges and overage fees.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from bson import ObjectId
from decimal import Decimal

from app.database.mongodb import database
from app.models.invoice import BillingPeriod, LineItem

logger = logging.getLogger(__name__)

# Module load marker
logger.warning("🔄 INVOICE_GENERATION_SERVICE MODULE LOADED - v1.0")


class InvoiceGenerationError(Exception):
    """Base invoice generation error."""
    pass


# Quarter to period number mapping
QUARTER_TO_PERIODS = {
    1: [1, 2, 3],   # Q1: Jan, Feb, Mar
    2: [4, 5, 6],   # Q2: Apr, May, Jun
    3: [7, 8, 9],   # Q3: Jul, Aug, Sep
    4: [10, 11, 12] # Q4: Oct, Nov, Dec
}

# Tax rate (6%)
TAX_RATE = 0.06


class InvoiceGenerationService:
    """Service for generating quarterly invoices."""

    def _get_period_numbers_for_quarter(self, quarter: int) -> List[int]:
        """
        Get period numbers for a given quarter.

        Args:
            quarter: Quarter number (1-4)

        Returns:
            List of period numbers [1-12]

        Raises:
            InvoiceGenerationError: If quarter is invalid
        """
        if quarter not in QUARTER_TO_PERIODS:
            raise InvoiceGenerationError(f"Invalid quarter: {quarter}. Must be 1-4.")

        return QUARTER_TO_PERIODS[quarter]

    def _calculate_billing_period_dates(
        self,
        subscription_start: datetime,
        period_numbers: List[int]
    ) -> tuple[datetime, datetime]:
        """
        Calculate billing period start and end dates.

        Args:
            subscription_start: Subscription start date
            period_numbers: List of period numbers (e.g., [1, 2, 3])

        Returns:
            Tuple of (period_start, period_end)
        """
        # For simplicity, assume periods are calendar months from subscription start
        # In production, this would use actual period dates from usage_periods
        from dateutil.relativedelta import relativedelta

        first_period = min(period_numbers)
        last_period = max(period_numbers)

        # Start date is the beginning of the first period
        period_start = subscription_start + relativedelta(months=first_period - 1)

        # End date is the end of the last period
        period_end = subscription_start + relativedelta(months=last_period) - relativedelta(days=1)
        period_end = period_end.replace(hour=23, minute=59, second=59, microsecond=999999)

        return period_start, period_end

    def _generate_line_items(
        self,
        subscription: Dict[str, Any],
        period_numbers: List[int]
    ) -> List[Dict[str, Any]]:
        """
        Generate line items for the invoice.

        Args:
            subscription: Subscription document
            period_numbers: List of period numbers to bill

        Returns:
            List of line item dictionaries
        """
        line_items = []

        # Line Item 1: Base Subscription Charge
        subscription_price = subscription.get("subscription_price", 0.0)
        if isinstance(subscription_price, Decimal):
            subscription_price = float(subscription_price)

        num_months = len(period_numbers)
        base_amount = subscription_price * num_months

        # Determine description based on period type
        if len(period_numbers) == 1:
            # Monthly invoice - use month name
            import calendar
            month_name = calendar.month_name[period_numbers[0]]
            description = f"Base Subscription - {month_name}"
        else:
            # Quarterly invoice - use quarter number
            quarter = self._get_quarter_from_periods(period_numbers)
            description = f"Base Subscription - Q{quarter}"

        line_items.append({
            "description": description,
            "period_numbers": period_numbers,
            "quantity": num_months,
            "unit_price": subscription_price,
            "amount": base_amount
        })

        # Line Items 2+: Overage Charges (per period)
        usage_periods = subscription.get("usage_periods", [])
        price_per_unit = subscription.get("price_per_unit", 0.0)
        if isinstance(price_per_unit, Decimal):
            price_per_unit = float(price_per_unit)

        for period in usage_periods:
            period_num = period.get("period_number")
            if period_num not in period_numbers:
                continue

            units_allocated = period.get("units_allocated", 0)
            units_used = period.get("units_used", 0)
            overage = max(0, units_used - units_allocated)

            if overage > 0:
                overage_amount = overage * price_per_unit
                line_items.append({
                    "description": f"Overage - Period {period_num}",
                    "period_numbers": [period_num],
                    "quantity": overage,
                    "unit_price": price_per_unit,
                    "amount": overage_amount
                })

        return line_items

    def _get_quarter_from_periods(self, period_numbers: List[int]) -> int:
        """Get quarter number from period numbers."""
        for quarter, periods in QUARTER_TO_PERIODS.items():
            if period_numbers == periods:
                return quarter
        return 0  # Unknown quarter

    def _calculate_invoice_totals(self, line_items: List[Dict[str, Any]]) -> tuple[float, float, float]:
        """
        Calculate invoice totals.

        Args:
            line_items: List of line item dictionaries

        Returns:
            Tuple of (subtotal, tax_amount, total_amount)
        """
        subtotal = sum(item["amount"] for item in line_items)
        tax_amount = subtotal * TAX_RATE
        total_amount = subtotal + tax_amount

        return subtotal, tax_amount, total_amount

    def _generate_invoice_number(self, subscription_id: str, quarter: int, year: int) -> str:
        """
        Generate unique invoice number.

        Format: INV-{YEAR}-Q{QUARTER}-{SUBSCRIPTION_SHORT_ID}

        Args:
            subscription_id: Subscription ID
            quarter: Quarter number
            year: Year

        Returns:
            Invoice number string
        """
        # Use last 6 characters of subscription ID for uniqueness
        short_id = str(subscription_id)[-6:]
        return f"INV-{year}-Q{quarter}-{short_id}"

    async def _create_invoice_document(
        self,
        subscription_id: str,
        period_numbers: List[int],
        invoice_number: str
    ) -> Dict[str, Any]:
        """
        Create invoice document with billing period, line items, and totals.

        Shared logic for both monthly and quarterly invoice generation.

        Args:
            subscription_id: Subscription ObjectId
            period_numbers: List of period numbers (e.g., [1,2,3] for Q1 or [3] for March)
            invoice_number: Pre-generated invoice number (format varies by type)

        Returns:
            dict: Created invoice document with _id

        Raises:
            InvoiceGenerationError: If subscription not found or invoice creation fails
        """
        logger.info(f"[INVOICE_GEN] Creating invoice for subscription: {subscription_id}")
        logger.info(f"[INVOICE_GEN] Period numbers: {period_numbers}")

        # Step 1: Fetch subscription
        try:
            subscription = await database.subscriptions.find_one({"_id": ObjectId(subscription_id)})
            if not subscription:
                raise InvoiceGenerationError(f"Subscription not found: {subscription_id}")
        except Exception as e:
            logger.error(f"[INVOICE_GEN] Error fetching subscription: {e}")
            raise InvoiceGenerationError(f"Failed to fetch subscription: {str(e)}")

        logger.info(f"[INVOICE_GEN] Subscription found: {subscription.get('company_name')}")

        # Step 2: Check if usage periods exist for this period
        usage_periods = subscription.get("usage_periods", [])
        available_periods = [p.get("period_number") for p in usage_periods if p.get("period_number") in period_numbers]

        if not available_periods:
            logger.warning(f"[INVOICE_GEN] No usage periods found for periods {period_numbers}")

        # Step 3: Generate billing period
        subscription_start = subscription.get("start_date")
        if not subscription_start:
            raise InvoiceGenerationError("Subscription has no start_date")

        period_start, period_end = self._calculate_billing_period_dates(subscription_start, period_numbers)

        billing_period_dict = {
            "period_numbers": period_numbers,
            "period_start": period_start,
            "period_end": period_end
        }

        billing_period = BillingPeriod(**billing_period_dict)
        logger.info(f"[INVOICE_GEN] Billing period: {period_start.date()} to {period_end.date()}")

        # Step 4: Generate line items
        line_items_data = self._generate_line_items(subscription, period_numbers)
        line_items = [LineItem(**item) for item in line_items_data]
        logger.info(f"[INVOICE_GEN] Generated {len(line_items)} line items")

        # Step 5: Calculate totals
        subtotal, tax_amount, total_amount = self._calculate_invoice_totals(line_items_data)
        logger.info(f"[INVOICE_GEN] Totals - Subtotal: ${subtotal:.2f}, Tax: ${tax_amount:.2f}, Total: ${total_amount:.2f}")

        # Step 6: Create invoice document
        now = datetime.now(timezone.utc)
        payment_terms_days = subscription.get("payment_terms_days", 30)
        from dateutil.relativedelta import relativedelta
        due_date = now + relativedelta(days=payment_terms_days)

        invoice_doc = {
            "company_name": subscription.get("company_name"),
            "subscription_id": subscription_id,
            "invoice_number": invoice_number,
            "invoice_date": now,
            "due_date": due_date,
            "total_amount": total_amount,
            "tax_amount": tax_amount,
            "status": "sent",
            "pdf_url": None,
            "payment_applications": [],
            "created_at": now,
            "billing_period": billing_period.model_dump(),
            "line_items": [item.model_dump() for item in line_items],
            "subtotal": subtotal,
            "amount_paid": 0.0,
            "stripe_invoice_id": None
        }

        # Step 7: Insert into database
        try:
            result = await database.invoices.insert_one(invoice_doc)
            invoice_doc["_id"] = result.inserted_id
            logger.info(f"[INVOICE_GEN] Invoice created successfully: {result.inserted_id}")
        except Exception as e:
            logger.error(f"[INVOICE_GEN] Error creating invoice: {e}")
            raise InvoiceGenerationError(f"Failed to create invoice: {str(e)}")

        return invoice_doc

    async def generate_quarterly_invoice(
        self,
        subscription_id: str,
        quarter: int
    ) -> Dict[str, Any]:
        """
        Generate quarterly invoice with line items.

        Args:
            subscription_id: Subscription ObjectId
            quarter: Quarter number (1-4)

        Returns:
            dict: Created invoice document

        Raises:
            InvoiceGenerationError: If generation fails
        """
        logger.info(f"[INVOICE_GEN] Generating Q{quarter} invoice for subscription: {subscription_id}")

        # Validate quarter and get period numbers
        period_numbers = self._get_period_numbers_for_quarter(quarter)
        logger.info(f"[INVOICE_GEN] Quarter {quarter} maps to periods: {period_numbers}")

        # Generate invoice number
        year = datetime.now(timezone.utc).year
        invoice_number = self._generate_invoice_number(subscription_id, quarter, year)
        logger.info(f"[INVOICE_GEN] Invoice number: {invoice_number}")

        # Use shared creation logic
        return await self._create_invoice_document(subscription_id, period_numbers, invoice_number)

    async def generate_monthly_invoice(
        self,
        subscription_id: str,
        month: int
    ) -> Dict[str, Any]:
        """
        Generate monthly invoice with line items.

        Args:
            subscription_id: Subscription ObjectId
            month: Month number (1-12)

        Returns:
            dict: Created invoice document

        Raises:
            InvoiceGenerationError: If generation fails
        """
        logger.info(f"[INVOICE_GEN] Generating month {month} invoice for subscription: {subscription_id}")

        # Validate month
        if month < 1 or month > 12:
            raise InvoiceGenerationError(f"Invalid month: {month}. Must be 1-12.")

        period_numbers = [month]
        logger.info(f"[INVOICE_GEN] Month {month} maps to period: {period_numbers}")

        # Generate invoice number (monthly format)
        year = datetime.now(timezone.utc).year
        short_id = str(subscription_id)[-6:]
        invoice_number = f"INV-{year}-M{month:02d}-{short_id}"
        logger.info(f"[INVOICE_GEN] Invoice number: {invoice_number}")

        # Use shared creation logic
        return await self._create_invoice_document(subscription_id, period_numbers, invoice_number)


# Singleton instance
invoice_generation_service = InvoiceGenerationService()
