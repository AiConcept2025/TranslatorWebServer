"""
Pricing Service for the Translation Web Server.

Orchestrates pricing calculations for both individual and enterprise customers.
Provides a unified interface for all pricing-related operations.
"""

import logging
from decimal import Decimal
from typing import Dict, Literal, Optional, Union

from app.pricing.pricing_calculator import (
    calculate_enterprise_quota,
    calculate_individual_price,
)
from app.pricing.pricing_config import PricingConfig, load_pricing_config

# Set up module logger
logger = logging.getLogger(__name__)

# Type aliases
UserType = Literal["individual", "enterprise"]
TranslationMode = Literal["default", "human", "handwriting", "formats"]


class PricingService:
    """
    Service for calculating prices and quotas for translation services.

    This service acts as an orchestration layer that:
    1. Determines whether to calculate price (individual) or quota (enterprise)
    2. Delegates to the appropriate pricing calculator
    3. Provides additional helper methods for pricing transparency

    The service supports dependency injection of config for testing while
    using the global config by default for production.
    """

    def __init__(self, config: Optional[PricingConfig] = None):
        """
        Initialize the pricing service.

        Args:
            config: Optional pricing configuration for testing.
                If None, loads config from default YAML file.
        """
        if config is None:
            logger.debug("Loading default pricing configuration")
            config = load_pricing_config()
        else:
            logger.debug("Using injected pricing configuration (likely for testing)")

        self._config = config
        logger.info("PricingService initialized successfully")

    def calculate_price(
        self,
        page_count: int,
        user_type: UserType,
        translation_mode: str = "default",
    ) -> Union[Decimal, int]:
        """
        Calculate price or quota based on user type.

        This is the primary method for pricing calculations. It routes to the
        appropriate calculator based on user_type:
        - Individual: Returns dollar amount (Decimal)
        - Enterprise: Returns quota pages (int)

        Args:
            page_count: Number of pages to translate. Must be positive.
            user_type: Type of customer - "individual" or "enterprise".
            translation_mode: Translation mode determining complexity.
                Valid modes: "default", "human", "handwriting", "formats".
                Default: "default"

        Returns:
            Union[Decimal, int]:
                - Decimal for individual (dollar amount, e.g., Decimal("25.00"))
                - int for enterprise (quota pages, e.g., 100)

        Raises:
            ValueError: If user_type is invalid (not "individual" or "enterprise").
            ValueError: If page_count is <= 0.
            ValueError: If translation_mode is invalid for the user_type.

        Examples:
            >>> service = PricingService()
            >>> # Individual customer: 5 pages with default mode
            >>> service.calculate_price(5, "individual", "default")
            Decimal('25.00')
            >>> # Enterprise customer: 100 pages with human translation
            >>> service.calculate_price(100, "enterprise", "human")
            1500
        """
        logger.debug(
            f"calculate_price called: page_count={page_count}, "
            f"user_type='{user_type}', translation_mode='{translation_mode}'"
        )

        # Route to appropriate calculator based on user type
        if user_type == "individual":
            logger.debug("Routing to individual pricing calculator")
            result = calculate_individual_price(
                page_count, translation_mode, self._config
            )
            logger.info(
                f"Individual pricing: {page_count} pages ({translation_mode}) = ${result}"
            )
            return result

        elif user_type == "enterprise":
            logger.debug("Routing to enterprise quota calculator")
            result = calculate_enterprise_quota(
                page_count, translation_mode, self._config
            )
            logger.info(
                f"Enterprise quota: {page_count} pages ({translation_mode}) = {result} quota pages"
            )
            return result

        else:
            error_msg = (
                f"Invalid user_type: '{user_type}'. Must be 'individual' or 'enterprise'"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_pricing_breakdown(
        self, page_count: int, user_type: UserType, translation_mode: str = "default"
    ) -> Dict[str, Union[str, int, float]]:
        """
        Get detailed pricing breakdown for transparency.

        Provides a human-readable breakdown of the pricing calculation,
        useful for displaying to users or logging detailed information.

        Args:
            page_count: Number of pages to translate.
            user_type: Type of customer - "individual" or "enterprise".
            translation_mode: Translation mode determining complexity.

        Returns:
            Dict with breakdown details:
                - page_count: Number of pages
                - user_type: Customer type
                - translation_mode: Translation mode
                - multiplier: Complexity coefficient
                - tier: Pricing tier (individual only)
                - base_price: Price per page (individual only)
                - total: Final price or quota
                - currency: "USD" for individual, "quota_pages" for enterprise

        Examples:
            >>> service = PricingService()
            >>> breakdown = service.get_pricing_breakdown(5, "individual", "default")
            >>> breakdown["total"]
            '25.00'
            >>> breakdown["tier"]
            'tier1'
        """
        logger.debug(
            f"get_pricing_breakdown: page_count={page_count}, "
            f"user_type='{user_type}', translation_mode='{translation_mode}'"
        )

        # Get the multiplier
        multiplier = self._config.multipliers[user_type][translation_mode]

        breakdown = {
            "page_count": page_count,
            "user_type": user_type,
            "translation_mode": translation_mode,
            "multiplier": multiplier,
        }

        if user_type == "individual":
            # Import tier determination for individual customers
            from app.pricing.pricing_calculator import determine_tier

            tier = determine_tier(page_count, "individual", self._config)
            base_price = self._config.base_pricing["individual"][tier]
            total = calculate_individual_price(
                page_count, translation_mode, self._config
            )

            breakdown.update(
                {
                    "tier": tier,
                    "base_price": float(base_price),
                    "total": str(total),  # Convert Decimal to string for JSON
                    "currency": "USD",
                }
            )

        else:  # enterprise
            total = calculate_enterprise_quota(
                page_count, translation_mode, self._config
            )

            breakdown.update(
                {
                    "tier": "N/A (enterprise uses flat multipliers)",
                    "base_price": "N/A",
                    "total": total,
                    "currency": "quota_pages",
                }
            )

        logger.debug(f"Pricing breakdown: {breakdown}")
        return breakdown

    def get_supported_modes(self, user_type: UserType) -> list[str]:
        """
        Get list of supported translation modes for a user type.

        Args:
            user_type: Type of customer - "individual" or "enterprise".

        Returns:
            List of supported translation mode names.

        Raises:
            ValueError: If user_type is invalid.

        Examples:
            >>> service = PricingService()
            >>> service.get_supported_modes("individual")
            ['default', 'formats', 'handwriting', 'human']
        """
        if user_type not in ["individual", "enterprise"]:
            raise ValueError(
                f"Invalid user_type: '{user_type}'. Must be 'individual' or 'enterprise'"
            )

        modes = sorted(list(self._config.multipliers[user_type].keys()))
        logger.debug(f"Supported modes for {user_type}: {modes}")
        return modes


# Global pricing service instance
# This singleton is used throughout the application for production code
pricing_service = PricingService()
