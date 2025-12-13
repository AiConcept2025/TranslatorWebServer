"""
Amount conversion utilities for financial operations.

Provides centralized conversion between different amount representations:
- Dollars (float) for human-readable amounts
- Cents (int) for Stripe API operations
- Decimal128 (BSON) for precise MongoDB storage

All conversions maintain precision and validate inputs to prevent financial errors.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Union
from bson import Decimal128


class AmountConverter:
    """
    Static utility class for converting amounts between different representations.

    Conversions supported:
    - Dollars ↔ Cents (for Stripe API)
    - Cents ↔ Decimal128 (for MongoDB storage)
    - Dollars ↔ Decimal128 (for direct storage)

    All methods validate inputs and raise ValueError for invalid amounts.
    """

    # Constants
    CENTS_PER_DOLLAR = 100
    DECIMAL_PLACES = 2

    @staticmethod
    def cents_to_dollars(cents: int) -> float:
        """
        Convert cents to dollars.

        Used when converting Stripe amounts to human-readable format.

        Args:
            cents: Amount in cents (e.g., 5000)

        Returns:
            Amount in dollars (e.g., 50.00)

        Raises:
            ValueError: If cents is negative
            TypeError: If cents is not an integer

        Examples:
            >>> AmountConverter.cents_to_dollars(5000)
            50.0
            >>> AmountConverter.cents_to_dollars(0)
            0.0
            >>> AmountConverter.cents_to_dollars(1)
            0.01
            >>> AmountConverter.cents_to_dollars(-100)
            ValueError: Amount cannot be negative: -100 cents
        """
        if not isinstance(cents, int):
            raise TypeError(f"Cents must be an integer, got {type(cents).__name__}")

        if cents < 0:
            raise ValueError(f"Amount cannot be negative: {cents} cents")

        return round(cents / AmountConverter.CENTS_PER_DOLLAR, AmountConverter.DECIMAL_PLACES)

    @staticmethod
    def dollars_to_cents(dollars: Union[float, int, Decimal]) -> int:
        """
        Convert dollars to cents.

        Used when preparing amounts for Stripe API calls.
        Handles floating-point precision by using Decimal internally.

        Args:
            dollars: Amount in dollars (e.g., 50.00)

        Returns:
            Amount in cents (e.g., 5000)

        Raises:
            ValueError: If dollars is negative
            TypeError: If dollars cannot be converted to Decimal

        Examples:
            >>> AmountConverter.dollars_to_cents(50.00)
            5000
            >>> AmountConverter.dollars_to_cents(0.01)
            1
            >>> AmountConverter.dollars_to_cents(0)
            0
            >>> AmountConverter.dollars_to_cents(99.99)
            9999
            >>> AmountConverter.dollars_to_cents(-10.00)
            ValueError: Amount cannot be negative: -10.00 dollars
        """
        try:
            decimal_amount = Decimal(str(dollars))
        except (ValueError, TypeError) as e:
            raise TypeError(f"Cannot convert {dollars} to Decimal: {e}")

        if decimal_amount < 0:
            raise ValueError(f"Amount cannot be negative: {dollars} dollars")

        # Multiply by 100 and round to nearest integer
        cents_decimal = (decimal_amount * AmountConverter.CENTS_PER_DOLLAR).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP
        )

        return int(cents_decimal)

    @staticmethod
    def cents_to_decimal128(cents: int) -> Decimal128:
        """
        Convert cents to Decimal128 for MongoDB storage.

        Used when storing amounts in MongoDB to maintain precision.

        Args:
            cents: Amount in cents (e.g., 5000)

        Returns:
            Decimal128 object representing dollars (e.g., Decimal128("50.00"))

        Raises:
            ValueError: If cents is negative
            TypeError: If cents is not an integer

        Examples:
            >>> AmountConverter.cents_to_decimal128(5000)
            Decimal128("50.00")
            >>> AmountConverter.cents_to_decimal128(0)
            Decimal128("0.00")
            >>> AmountConverter.cents_to_decimal128(1)
            Decimal128("0.01")
            >>> AmountConverter.cents_to_decimal128(-100)
            ValueError: Amount cannot be negative: -100 cents
        """
        if not isinstance(cents, int):
            raise TypeError(f"Cents must be an integer, got {type(cents).__name__}")

        if cents < 0:
            raise ValueError(f"Amount cannot be negative: {cents} cents")

        # Convert to Decimal first to ensure precision
        decimal_amount = Decimal(cents) / Decimal(AmountConverter.CENTS_PER_DOLLAR)

        # Format with exactly 2 decimal places
        formatted = decimal_amount.quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        return Decimal128(formatted)

    @staticmethod
    def decimal128_to_cents(decimal: Decimal128) -> int:
        """
        Convert Decimal128 from MongoDB to cents.

        Used when reading amounts from MongoDB and preparing for Stripe operations.

        Args:
            decimal: Decimal128 object representing dollars (e.g., Decimal128("50.00"))

        Returns:
            Amount in cents (e.g., 5000)

        Raises:
            ValueError: If decimal represents a negative amount
            TypeError: If decimal is not Decimal128

        Examples:
            >>> AmountConverter.decimal128_to_cents(Decimal128("50.00"))
            5000
            >>> AmountConverter.decimal128_to_cents(Decimal128("0.01"))
            1
            >>> AmountConverter.decimal128_to_cents(Decimal128("0.00"))
            0
            >>> AmountConverter.decimal128_to_cents(Decimal128("-10.00"))
            ValueError: Amount cannot be negative: -10.00 dollars
        """
        if not isinstance(decimal, Decimal128):
            raise TypeError(f"Expected Decimal128, got {type(decimal).__name__}")

        # Convert to Python Decimal
        decimal_amount = decimal.to_decimal()

        if decimal_amount < 0:
            raise ValueError(f"Amount cannot be negative: {decimal_amount} dollars")

        # Multiply by 100 and round to nearest integer
        cents_decimal = (decimal_amount * AmountConverter.CENTS_PER_DOLLAR).quantize(
            Decimal('1'), rounding=ROUND_HALF_UP
        )

        return int(cents_decimal)

    @staticmethod
    def dollars_to_decimal128(dollars: Union[float, int, Decimal]) -> Decimal128:
        """
        Convert dollars to Decimal128 for MongoDB storage.

        Convenience method for direct dollar-to-MongoDB conversion.

        Args:
            dollars: Amount in dollars (e.g., 50.00)

        Returns:
            Decimal128 object representing dollars (e.g., Decimal128("50.00"))

        Raises:
            ValueError: If dollars is negative
            TypeError: If dollars cannot be converted to Decimal

        Examples:
            >>> AmountConverter.dollars_to_decimal128(50.00)
            Decimal128("50.00")
            >>> AmountConverter.dollars_to_decimal128(0.01)
            Decimal128("0.01")
            >>> AmountConverter.dollars_to_decimal128(-10.00)
            ValueError: Amount cannot be negative: -10.00 dollars
        """
        # Use existing methods to ensure consistent validation
        cents = AmountConverter.dollars_to_cents(dollars)
        return AmountConverter.cents_to_decimal128(cents)

    @staticmethod
    def decimal128_to_dollars(decimal: Decimal128) -> float:
        """
        Convert Decimal128 from MongoDB to dollars.

        Convenience method for reading amounts from MongoDB as floats.

        Args:
            decimal: Decimal128 object representing dollars (e.g., Decimal128("50.00"))

        Returns:
            Amount in dollars (e.g., 50.00)

        Raises:
            ValueError: If decimal represents a negative amount
            TypeError: If decimal is not Decimal128

        Examples:
            >>> AmountConverter.decimal128_to_dollars(Decimal128("50.00"))
            50.0
            >>> AmountConverter.decimal128_to_dollars(Decimal128("0.01"))
            0.01
            >>> AmountConverter.decimal128_to_dollars(Decimal128("-10.00"))
            ValueError: Amount cannot be negative: -10.00 dollars
        """
        # Use existing methods to ensure consistent validation
        cents = AmountConverter.decimal128_to_cents(decimal)
        return AmountConverter.cents_to_dollars(cents)

    @staticmethod
    def format_dollars(dollars: Union[float, int, Decimal], currency_symbol: str = "$") -> str:
        """
        Format dollar amount as currency string.

        Args:
            dollars: Amount in dollars
            currency_symbol: Currency symbol to prepend (default: "$")

        Returns:
            Formatted currency string (e.g., "$50.00")

        Examples:
            >>> AmountConverter.format_dollars(50.00)
            "$50.00"
            >>> AmountConverter.format_dollars(1234.56, "€")
            "€1,234.56"
            >>> AmountConverter.format_dollars(0)
            "$0.00"
        """
        if dollars < 0:
            return f"-{currency_symbol}{abs(dollars):,.2f}"
        return f"{currency_symbol}{dollars:,.2f}"
