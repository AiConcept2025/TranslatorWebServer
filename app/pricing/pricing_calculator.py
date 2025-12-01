"""
Pricing calculator module for determining tiers and calculating prices.

This module provides core pricing logic for the translation service,
including tier determination based on page count and customer type.
"""

import logging
from decimal import Decimal
from typing import Literal

from app.pricing.pricing_config import PricingConfig

# Type aliases for better type safety
TierKey = str  # Dynamic tier keys from YAML (e.g., "small", "medium", "large")
CustomerType = Literal["individual", "enterprise"]

logger = logging.getLogger(__name__)


def determine_tier(
    num_pages: int,
    customer_type: CustomerType,
    config: PricingConfig
) -> TierKey:
    """
    Determine pricing tier based on page count and customer type.

    This function maps a page count to the appropriate pricing tier (tier1, tier2, or tier3)
    based on the ranges defined in the pricing configuration. Each customer type
    (individual vs enterprise) may have different tier boundaries.

    Args:
        num_pages: Number of pages to determine tier for. Must be a positive integer.
        customer_type: Type of customer - either "individual" or "enterprise".
        config: Loaded pricing configuration containing tier range definitions.

    Returns:
        TierKey: The tier key that matches the page count - one of:
            - "tier1": Smallest page count range
            - "tier2": Medium page count range
            - "tier3": Largest page count range (typically unlimited upper bound)

    Raises:
        ValueError: If num_pages is <= 0, indicating invalid input.
        ValueError: If customer_type is not found in the configuration,
                   indicating an invalid or unsupported customer type.
        ValueError: If num_pages doesn't match any tier range, indicating
                   a configuration error.

    Examples:
        >>> from app.pricing.pricing_config import load_pricing_config
        >>> config = load_pricing_config()
        >>> determine_tier(5, "individual", config)
        'small'
        >>> determine_tier(30, "individual", config)
        'medium'
        >>> determine_tier(100, "individual", config)
        'large'

    Note:
        The function assumes tier ranges are non-overlapping and cover all
        positive integers. The last tier typically has no upper limit (None).
        Tier names come from the YAML configuration (e.g., "small", "medium", "large").
    """
    # Validate inputs
    if num_pages <= 0:
        error_msg = f"Page count must be positive, received: {num_pages}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Check customer_type exists
    if customer_type not in config.page_tiers:
        available_types = ", ".join(config.page_tiers.keys())
        error_msg = f"Invalid customer type: '{customer_type}'. Available types: {available_types}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Get tier ranges for this customer type
    tiers = config.page_tiers[customer_type]

    logger.debug(
        f"Determining tier for customer_type='{customer_type}', num_pages={num_pages}"
    )

    # Check each tier in order (dictionary order from YAML)
    # Note: Python 3.7+ dicts maintain insertion order
    for tier_key in tiers.keys():
        tier_range = tiers[tier_key]
        min_pages, max_pages = tier_range[0], tier_range[1]

        # Check if page count falls within this tier's range
        if max_pages is None:
            # Unlimited upper bound (typically tier3)
            if num_pages >= min_pages:
                logger.debug(
                    f"Matched {tier_key}: {num_pages} pages >= {min_pages} (unlimited upper bound)"
                )
                return tier_key
        else:
            # Fixed range with upper bound
            if min_pages <= num_pages <= max_pages:
                logger.debug(
                    f"Matched {tier_key}: {num_pages} pages in range [{min_pages}, {max_pages}]"
                )
                return tier_key

    # Should never reach here if config is valid
    error_msg = (
        f"Page count {num_pages} doesn't match any tier for customer_type='{customer_type}'. "
        f"This indicates a configuration error. Available tiers: {list(tiers.keys())}"
    )
    logger.error(error_msg)
    raise ValueError(error_msg)


def calculate_individual_price(
    num_pages: int,
    translation_mode: str,
    config: PricingConfig
) -> Decimal:
    """
    Calculate price for individual customers based on page count and translation mode.

    This function implements the individual pricing formula:
        price = num_pages × price_per_page × complexity_coefficient

    The calculation proceeds in steps:
    1. Determine pricing tier based on page count (tier1/tier2/tier3)
    2. Get base price per page from tier
    3. Get complexity coefficient from translation mode
    4. Calculate total: pages × base_price × coefficient
    5. Round to 2 decimal places

    Args:
        num_pages: Number of pages to translate. Must be a positive integer.
            This is validated by determine_tier() which raises ValueError if <= 0.
        translation_mode: Translation mode determining complexity multiplier.
            Valid modes: "default" (1x), "human" (20x), "handwriting" (30x), "formats" (5x).
            Must match a key in config.multipliers["individual"].
        config: Loaded pricing configuration containing tier ranges, base prices,
            and complexity multipliers.

    Returns:
        Decimal: Total price rounded to 2 decimal places (e.g., Decimal("25.00")).
            Always returns a positive value since inputs are validated.

    Raises:
        ValueError: If num_pages is <= 0 (raised by determine_tier).
        ValueError: If translation_mode is not a valid mode in the configuration.
            This provides a clearer error than the underlying KeyError.

    Examples:
        >>> from app.pricing.pricing_config import load_pricing_config
        >>> config = load_pricing_config()

        # Simple calculation: 5 pages at tier1 ($5/page) with default mode (1x)
        >>> calculate_individual_price(5, "default", config)
        Decimal('25.00')

        # Higher complexity: 5 pages with human translation (20x multiplier)
        >>> calculate_individual_price(5, "human", config)
        Decimal('500.00')

        # Different tier: 50 pages at tier2 ($4/page) with handwriting (30x)
        >>> calculate_individual_price(50, "handwriting", config)
        Decimal('6000.00')

        # Volume discount: 300 pages at tier3 ($3/page) with formats (5x)
        >>> calculate_individual_price(300, "formats", config)
        Decimal('4500.00')

    Note:
        - Tier boundaries affect pricing: more pages may cost less if tier discount applies
        - Example: 9 pages at tier1 ($5) = $45, but 10 pages at tier2 ($4) = $40
        - All intermediate calculations use Python floats, final result converts to Decimal
    """
    logger.debug(
        f"Calculating individual price: num_pages={num_pages}, "
        f"translation_mode='{translation_mode}'"
    )

    # Step 1: Determine tier based on page count
    tier: TierKey = determine_tier(num_pages, "individual", config)
    logger.debug(f"Tier determined: {tier}")

    # Step 2: Get price per page for this tier
    price_per_page: float = config.base_pricing['individual'][tier]
    logger.debug(f"Base price per page for {tier}: ${price_per_page}")

    # Step 3: Get complexity coefficient from translation mode
    # Wrap KeyError in ValueError for better error messaging
    try:
        complexity_coefficient: int = config.multipliers['individual'][translation_mode]
        logger.debug(f"Complexity coefficient for '{translation_mode}': {complexity_coefficient}x")
    except KeyError:
        available_modes = ", ".join(config.multipliers['individual'].keys())
        error_msg = (
            f"Invalid translation mode: '{translation_mode}'. "
            f"Available modes for individual customers: {available_modes}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg) from None

    # Step 4: Calculate total price
    total: float = num_pages * price_per_page * complexity_coefficient
    logger.debug(
        f"Price calculation: {num_pages} pages × ${price_per_page}/page × "
        f"{complexity_coefficient}x = ${total}"
    )

    # Step 5: Return as Decimal with 2 decimal places
    final_price: Decimal = Decimal(str(total)).quantize(Decimal("0.01"))
    logger.info(
        f"Individual price calculated: {num_pages} pages ({tier}) with "
        f"'{translation_mode}' mode = ${final_price}"
    )

    return final_price


def calculate_enterprise_quota(
    num_pages: int,
    translation_mode: str,
    config: PricingConfig
) -> int:
    """
    Calculate quota pages for enterprise customers.

    Enterprise quota uses a SIMPLE formula based only on complexity multipliers:
        quota_pages = num_pages × complexity_coefficient

    **Key Differences from Individual Pricing:**

    Enterprise (this function):
    - ❌ NO tier determination (no page count tiers)
    - ❌ NO base_pricing lookup (no per-page pricing)
    - ✅ Simple multiplication only: pages × multiplier
    - ✅ Returns int (quota pages)

    Individual (calculate_individual_price):
    - ✅ HAS tier determination (tier1/tier2/tier3 based on page count)
    - ✅ HAS base_pricing ($5/$4/$3 per page by tier)
    - ✅ Complex formula: pages × base_price × multiplier
    - ✅ Returns Decimal (dollar amount)

    **Why Enterprise is Simpler:**
    Enterprise customers pre-purchase quota pages at a negotiated rate.
    This function only converts requested pages to quota consumption based
    on translation complexity. Pricing happens at subscription time, not
    per-translation.

    Args:
        num_pages: Number of pages to convert to quota. Must be a positive integer.
            Unlike individual pricing, there are no tier boundaries - all page
            counts use the same multiplier.
        translation_mode: Translation mode determining complexity multiplier.
            Valid modes: "default" (1x), "human" (15x), "handwriting" (25x), "formats" (3x).
            Must match a key in config.multipliers["enterprise"].
            Note: Enterprise multipliers differ from individual (e.g., 15x vs 20x for human).
        config: Loaded pricing configuration containing complexity multipliers.
            Only uses config.multipliers["enterprise"], NOT config.base_pricing or
            config.page_tiers (those are individual-only).

    Returns:
        int: Total quota pages to deduct from customer's subscription.
            Example: 100 pages × 15 (human) = 1500 quota pages.
            Always returns a positive integer (no rounding needed).

    Raises:
        ValueError: If num_pages is <= 0, indicating invalid input.
        ValueError: If translation_mode is None or empty.
        ValueError: If translation_mode is not a valid mode in the enterprise
            configuration (e.g., typo or unsupported mode).

    Examples:
        >>> from app.pricing.pricing_config import load_pricing_config
        >>> config = load_pricing_config()

        # Default mode: 1x multiplier (1 page = 1 quota page)
        >>> calculate_enterprise_quota(100, "default", config)
        100

        # Human translation: 15x multiplier (1 page = 15 quota pages)
        >>> calculate_enterprise_quota(100, "human", config)
        1500

        # Handwriting: 25x multiplier (most expensive)
        >>> calculate_enterprise_quota(100, "handwriting", config)
        2500

        # Multiple formats: 3x multiplier
        >>> calculate_enterprise_quota(100, "formats", config)
        300

        # Large volume - no tier changes (unlike individual)
        >>> calculate_enterprise_quota(1000, "human", config)
        15000

    Note:
        - No tier logic - 10 pages uses same multiplier as 10,000 pages
        - Returns int, not Decimal (quota pages, not dollars)
        - Multipliers are different from individual (check config for exact values)
        - Enterprise customers must have sufficient quota or transaction fails
    """
    logger.debug(
        f"[ENTERPRISE QUOTA] Starting calculation: num_pages={num_pages}, "
        f"translation_mode='{translation_mode}'"
    )

    # Step 1: Validate num_pages (must be positive)
    if num_pages <= 0:
        error_msg = f"Page count must be positive, received: {num_pages}"
        logger.error(f"[ENTERPRISE QUOTA] Validation error: {error_msg}")
        raise ValueError(error_msg)

    logger.debug(f"[ENTERPRISE QUOTA] ✓ Page count validation passed: {num_pages} pages")

    # Step 2: Validate translation_mode (must be non-empty)
    if translation_mode is None or translation_mode == "":
        error_msg = "translation_mode is required and cannot be empty"
        logger.error(f"[ENTERPRISE QUOTA] Validation error: {error_msg}")
        raise ValueError(error_msg)

    logger.debug(f"[ENTERPRISE QUOTA] ✓ Translation mode validation passed: '{translation_mode}'")

    # Step 3: Get complexity coefficient from enterprise multipliers
    # NOTE: Enterprise does NOT use base_pricing or page_tiers - those are individual-only!
    # We ONLY need config.multipliers["enterprise"][translation_mode]
    try:
        complexity_coefficient: int = config.multipliers['enterprise'][translation_mode]
        logger.debug(
            f"[ENTERPRISE QUOTA] ✓ Multiplier found: '{translation_mode}' = {complexity_coefficient}x "
            f"(NOTE: Enterprise multipliers differ from individual)"
        )
    except KeyError:
        # Provide helpful error message with available modes
        available_modes = ", ".join(config.multipliers['enterprise'].keys())
        error_msg = (
            f"Invalid translation mode: '{translation_mode}'. "
            f"Available enterprise modes: {available_modes}"
        )
        logger.error(f"[ENTERPRISE QUOTA] Mode lookup failed: {error_msg}")
        raise ValueError(error_msg) from None

    # Step 4: Calculate quota pages (simple multiplication - NO tier logic!)
    # Enterprise formula: quota_pages = num_pages × complexity_coefficient
    # (Compare to individual: price = num_pages × base_price × complexity_coefficient)
    quota_pages: int = num_pages * complexity_coefficient

    logger.debug(
        f"[ENTERPRISE QUOTA] Calculation: {num_pages} pages × {complexity_coefficient}x = "
        f"{quota_pages} quota pages (NOTE: No tier logic - same multiplier for all page counts)"
    )

    # Step 5: Log final result and return
    logger.info(
        f"[ENTERPRISE QUOTA] ✓ Calculation complete: {num_pages} pages with "
        f"'{translation_mode}' mode = {quota_pages} quota pages to deduct from subscription"
    )

    return quota_pages
