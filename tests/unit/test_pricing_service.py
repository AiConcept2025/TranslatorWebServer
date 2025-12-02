"""
Unit tests for pricing tier determination logic.

TDD Cycle 2 - RED Phase
Expected to FAIL: app.pricing.pricing_calculator module does not exist yet.
"""

import pytest
from app.pricing.pricing_config import load_pricing_config, PricingConfig
from app.pricing.pricing_calculator import determine_tier


@pytest.fixture
def config() -> PricingConfig:
    """Load pricing config once for all tests."""
    return load_pricing_config()


class TestTierDetermination:
    """Test suite for tier determination algorithm."""

    def test_tier1_boundary_lower(self, config: PricingConfig):
        """Test small tier lower boundary: 1 page should map to small."""
        # Act
        tier = determine_tier(num_pages=1, customer_type="individual", config=config)

        # Assert
        assert tier == "small", "1 page should fall into small tier (1-10 pages)"

    def test_tier1_boundary_upper(self, config: PricingConfig):
        """Test small tier upper boundary: 10 pages should map to small."""
        # Act
        tier = determine_tier(num_pages=10, customer_type="individual", config=config)

        # Assert
        assert tier == "small", "10 pages should fall into small tier (upper boundary)"

    def test_tier2_boundary_lower(self, config: PricingConfig):
        """Test medium tier lower boundary: 11 pages should map to medium."""
        # Act
        tier = determine_tier(num_pages=11, customer_type="individual", config=config)

        # Assert
        assert tier == "medium", "11 pages should fall into medium tier (lower boundary)"

    def test_tier2_middle(self, config: PricingConfig):
        """Test medium tier middle range: 30 pages should map to medium."""
        # Act
        tier = determine_tier(num_pages=30, customer_type="individual", config=config)

        # Assert
        assert tier == "medium", "30 pages should fall into medium tier (middle of range)"

    def test_tier2_boundary_upper(self, config: PricingConfig):
        """Test medium tier upper boundary: 50 pages should map to medium."""
        # Act
        tier = determine_tier(num_pages=50, customer_type="individual", config=config)

        # Assert
        assert tier == "medium", "50 pages should fall into medium tier (upper boundary)"

    def test_tier3_boundary_lower(self, config: PricingConfig):
        """Test large tier lower boundary: 51 pages should map to large."""
        # Act
        tier = determine_tier(num_pages=51, customer_type="individual", config=config)

        # Assert
        assert tier == "large", "51 pages should fall into large tier (lower boundary)"

    def test_tier3_unlimited(self, config: PricingConfig):
        """Test large tier unlimited upper bound: 500 pages should map to large."""
        # Act
        tier = determine_tier(num_pages=500, customer_type="individual", config=config)

        # Assert
        assert tier == "large", "500 pages should fall into large tier (unlimited upper bound)"


class TestTierDeterminationEdgeCases:
    """Test edge cases and error handling for tier determination."""

    def test_zero_pages_raises_error(self, config: PricingConfig):
        """Test that 0 pages raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Page count must be positive"):
            determine_tier(num_pages=0, customer_type="individual", config=config)

    def test_negative_pages_raises_error(self, config: PricingConfig):
        """Test that negative pages raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Page count must be positive"):
            determine_tier(num_pages=-5, customer_type="individual", config=config)

    def test_invalid_customer_type_raises_error(self, config: PricingConfig):
        """Test that invalid customer type raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid customer type"):
            determine_tier(num_pages=10, customer_type="invalid_type", config=config)


# ==============================================================================
# TDD CYCLE 3 - RED PHASE: Individual Pricing Calculation
# Expected to FAIL: calculate_individual_price() does not exist yet
# ==============================================================================

from decimal import Decimal
from app.pricing.pricing_calculator import calculate_individual_price


class TestIndividualPricingCalculation:
    """
    Test suite for individual user pricing calculation.

    Formula: price = num_pages × price_per_page × complexity_coefficient

    Where:
    - price_per_page comes from tier (small=$0.20, medium=$0.18, large=$0.16)
    - complexity_coefficient from translation_mode (default=1, human=2, handwriting=2, formats=3)
    """

    def test_5_pages_default(self, config: PricingConfig):
        """
        Test 5 pages with default translation mode.

        Expected calculation:
        - Tier: small (5 pages falls in 1-10 range) → $0.20/page
        - Mode: default → 1x multiplier
        - Price: 5 × $0.20 × 1 = $1.00
        """
        # Act
        price = calculate_individual_price(
            num_pages=5,
            translation_mode="default",
            config=config
        )

        # Assert
        assert price == Decimal("1.00"), "5 pages at small tier ($0.20/page) with default mode (1x) should be $1.00"

    def test_5_pages_human(self, config: PricingConfig):
        """
        Test 5 pages with human translation mode.

        Expected calculation:
        - Tier: small (5 pages falls in 1-10 range) → $0.20/page
        - Mode: human → 2x multiplier
        - Price: 5 × $0.20 × 2 = $2.00
        """
        # Act
        price = calculate_individual_price(
            num_pages=5,
            translation_mode="human",
            config=config
        )

        # Assert
        assert price == Decimal("2.00"), "5 pages at small tier ($0.20/page) with human mode (2x) should be $2.00"

    def test_50_pages_handwriting(self, config: PricingConfig):
        """
        Test 50 pages with handwriting recognition mode.

        Expected calculation:
        - Tier: medium (50 pages falls in 11-50 range) → $0.18/page
        - Mode: handwriting → 2x multiplier
        - Price: 50 × $0.18 × 2 = $18.00
        """
        # Act
        price = calculate_individual_price(
            num_pages=50,
            translation_mode="handwriting",
            config=config
        )

        # Assert
        assert price == Decimal("18.00"), "50 pages at medium tier ($0.18/page) with handwriting mode (2x) should be $18.00"

    def test_300_pages_formats(self, config: PricingConfig):
        """
        Test 300 pages with format preservation mode.

        Expected calculation:
        - Tier: large (300 pages falls in 51+ range) → $0.16/page
        - Mode: formats → 3x multiplier
        - Price: 300 × $0.16 × 3 = $144.00
        """
        # Act
        price = calculate_individual_price(
            num_pages=300,
            translation_mode="formats",
            config=config
        )

        # Assert
        assert price == Decimal("144.00"), "300 pages at large tier ($0.16/page) with formats mode (3x) should be $144.00"

    def test_200_pages_human(self, config: PricingConfig):
        """
        Test 200 pages with human translation mode.

        Expected calculation:
        - Tier: large (200 pages falls in 51+ range) → $0.16/page
        - Mode: human → 2x multiplier
        - Price: 200 × $0.16 × 2 = $64.00
        """
        # Act
        price = calculate_individual_price(
            num_pages=200,
            translation_mode="human",
            config=config
        )

        # Assert
        assert price == Decimal("64.00"), "200 pages at large tier ($0.16/page) with human mode (2x) should be $64.00"

    def test_tier_selection_affects_calculation(self, config: PricingConfig):
        """
        Test that tier boundaries affect pricing calculation.

        Verify that crossing from small to medium tier changes the base price:
        - 10 pages (small): 10 × $0.20 × 1 = $2.00
        - 11 pages (medium): 11 × $0.18 × 1 = $1.98

        Even though 11 pages is more volume, medium tier has lower per-page price.
        """
        # Act
        price_10_pages = calculate_individual_price(
            num_pages=10,
            translation_mode="default",
            config=config
        )

        price_11_pages = calculate_individual_price(
            num_pages=11,
            translation_mode="default",
            config=config
        )

        # Assert
        assert price_10_pages == Decimal("2.00"), "10 pages at small tier ($0.20/page) should be $2.00"
        assert price_11_pages == Decimal("1.98"), "11 pages at medium tier ($0.18/page) should be $1.98"
        assert price_10_pages > price_11_pages, "Small tier per-page is higher than medium, so 10 pages > 11 pages in total cost"

    def test_invalid_translation_mode_raises_error(self, config: PricingConfig):
        """
        Test that invalid translation mode raises ValueError.

        Valid modes: default, human, handwriting, formats
        Invalid mode should raise clear error.
        """
        # Act & Assert
        with pytest.raises((ValueError, KeyError), match="(Invalid translation mode|unknown_mode)"):
            calculate_individual_price(
                num_pages=10,
                translation_mode="unknown_mode",
                config=config
            )


# ==============================================================================
# TDD CYCLE 4 - RED PHASE: Enterprise Quota Calculation
# Expected to FAIL: calculate_enterprise_quota() does not exist yet
# ==============================================================================

from app.pricing.pricing_calculator import calculate_enterprise_quota
from unittest.mock import patch, MagicMock


class TestEnterpriseQuotaCalculation:
    """
    Test suite for enterprise customer quota calculation.

    CRITICAL: Enterprise uses ONLY multipliers - NO tier determination, NO base_pricing!

    Formula: quota_pages = num_pages × complexity_coefficient

    Where:
    - complexity_coefficient = config.multipliers['enterprise'][translation_mode]
    - Enterprise multipliers: default=1, human=2, handwriting=3, formats=4
    - Different from individual multipliers (human=2, handwriting=2, formats=3)
    """

    def test_100_pages_default(self, config: PricingConfig):
        """
        Test 100 pages with default translation mode.

        Expected calculation:
        - Mode: default → 1x multiplier
        - Quota: 100 × 1 = 100 quota pages
        """
        # Act
        quota = calculate_enterprise_quota(
            num_pages=100,
            translation_mode="default",
            config=config
        )

        # Assert
        assert quota == 100, "100 pages with default mode (1x) should be 100 quota pages"
        assert isinstance(quota, int), "Quota must be int, not Decimal"

    def test_100_pages_human(self, config: PricingConfig):
        """
        Test 100 pages with human translation mode.

        Expected calculation:
        - Mode: human → 2x multiplier (enterprise uses 2x, same as individual)
        - Quota: 100 × 2 = 200 quota pages
        """
        # Act
        quota = calculate_enterprise_quota(
            num_pages=100,
            translation_mode="human",
            config=config
        )

        # Assert
        assert quota == 200, "100 pages with human mode (2x) should be 200 quota pages"
        assert isinstance(quota, int), "Quota must be int, not Decimal"

    def test_100_pages_handwriting(self, config: PricingConfig):
        """
        Test 100 pages with handwriting recognition mode.

        Expected calculation:
        - Mode: handwriting → 3x multiplier (enterprise uses 3x, NOT 2x like individual)
        - Quota: 100 × 3 = 300 quota pages
        """
        # Act
        quota = calculate_enterprise_quota(
            num_pages=100,
            translation_mode="handwriting",
            config=config
        )

        # Assert
        assert quota == 300, "100 pages with handwriting mode (3x) should be 300 quota pages"
        assert isinstance(quota, int), "Quota must be int, not Decimal"

    def test_100_pages_formats(self, config: PricingConfig):
        """
        Test 100 pages with format preservation mode.

        Expected calculation:
        - Mode: formats → 4x multiplier (enterprise uses 4x, NOT 3x like individual)
        - Quota: 100 × 4 = 400 quota pages
        """
        # Act
        quota = calculate_enterprise_quota(
            num_pages=100,
            translation_mode="formats",
            config=config
        )

        # Assert
        assert quota == 400, "100 pages with formats mode (4x) should be 400 quota pages"
        assert isinstance(quota, int), "Quota must be int, not Decimal"

    def test_200_pages_handwriting(self, config: PricingConfig):
        """
        Test 200 pages with handwriting recognition mode.

        Expected calculation:
        - Mode: handwriting → 3x multiplier
        - Quota: 200 × 3 = 600 quota pages
        """
        # Act
        quota = calculate_enterprise_quota(
            num_pages=200,
            translation_mode="handwriting",
            config=config
        )

        # Assert
        assert quota == 600, "200 pages with handwriting mode (3x) should be 600 quota pages"
        assert isinstance(quota, int), "Quota must be int, not Decimal"

    def test_no_tier_determination(self, config: PricingConfig):
        """
        CRITICAL TEST: Verify that determine_tier() is NOT called for enterprise.

        Enterprise quota calculation must NOT use tier determination.
        This test ensures the algorithm doesn't accidentally invoke tier logic.
        """
        # Arrange - Mock determine_tier to track if it's called
        with patch('app.pricing.pricing_calculator.determine_tier') as mock_determine_tier:
            mock_determine_tier.return_value = "tier2"  # Should never be reached

            # Act
            quota = calculate_enterprise_quota(
                num_pages=100,
                translation_mode="human",
                config=config
            )

            # Assert
            assert quota == 200, "Quota calculation should work correctly (100 × 2)"
            mock_determine_tier.assert_not_called(), "Enterprise must NOT call determine_tier()"

    def test_no_base_pricing(self, config: PricingConfig):
        """
        CRITICAL TEST: Verify that base_pricing is NOT accessed for enterprise.

        Enterprise quota calculation must NOT use config.base_pricing.
        This test ensures the algorithm doesn't accidentally access base_pricing.
        """
        # Arrange - Create config mock with base_pricing that raises if accessed
        class ConfigProxy:
            def __init__(self, real_config):
                self._real_config = real_config
                self._base_pricing_accessed = False

            @property
            def multipliers(self):
                return self._real_config.multipliers

            @property
            def tiers(self):
                return self._real_config.tiers

            @property
            def base_pricing(self):
                self._base_pricing_accessed = True
                raise AssertionError("Enterprise quota calculation must NOT access base_pricing!")

        config_proxy = ConfigProxy(config)

        # Act
        quota = calculate_enterprise_quota(
            num_pages=100,
            translation_mode="human",
            config=config_proxy
        )

        # Assert
        assert quota == 200, "Quota calculation should work correctly (100 × 2)"
        assert not config_proxy._base_pricing_accessed, "Enterprise must NOT access base_pricing"

    def test_same_multiplier_all_page_counts(self, config: PricingConfig):
        """
        CRITICAL TEST: Verify multiplier is constant regardless of page count (no tier effect).

        Unlike individual pricing where tiers change the per-page price,
        enterprise uses the SAME multiplier for 10 pages or 200 pages.
        """
        # Act - Test human mode (2x multiplier) at different page counts
        quota_10_pages = calculate_enterprise_quota(
            num_pages=10,
            translation_mode="human",
            config=config
        )

        quota_200_pages = calculate_enterprise_quota(
            num_pages=200,
            translation_mode="human",
            config=config
        )

        # Assert
        assert quota_10_pages == 20, "10 pages × 2 (human) should be 20 quota pages"
        assert quota_200_pages == 400, "200 pages × 2 (human) should be 400 quota pages"

        # Verify multiplier is constant (linear relationship)
        assert quota_200_pages / quota_10_pages == 20, "Ratio should be exactly 20 (200/10), proving constant multiplier"

    def test_missing_translation_mode(self, config: PricingConfig):
        """
        Test that missing translation_mode raises ValueError.

        translation_mode is required for quota calculation.
        """
        # Act & Assert
        with pytest.raises(ValueError, match="translation_mode"):
            calculate_enterprise_quota(
                num_pages=100,
                translation_mode=None,  # Missing mode
                config=config
            )

    def test_invalid_translation_mode(self, config: PricingConfig):
        """
        Test that invalid translation_mode raises ValueError.

        Valid modes for enterprise: default, human, handwriting, formats
        Invalid mode should raise clear error.
        """
        # Act & Assert
        with pytest.raises((ValueError, KeyError), match="(Invalid translation mode|invalid_mode|enterprise)"):
            calculate_enterprise_quota(
                num_pages=100,
                translation_mode="invalid_mode",
                config=config
            )
