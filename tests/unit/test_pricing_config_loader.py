"""
Unit tests for pricing configuration loader.

RED PHASE: These tests are written FIRST and should FAIL because the
implementation (app.config.pricing_config) does not exist yet.
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

# This import will fail initially - that's expected in TDD RED phase
from app.pricing.pricing_config import load_pricing_config, PricingConfig


class TestPricingConfigLoader:
    """Test suite for YAML pricing configuration loading and validation."""

    def test_loads_valid_yaml(self):
        """Verify YAML loads successfully from pricing-tiers.yaml"""
        # Arrange
        config_path = Path(__file__).parent.parent.parent / "pricing-tiers.yaml"

        # Act
        config = load_pricing_config(str(config_path))

        # Assert
        assert config is not None
        assert isinstance(config, PricingConfig)
        assert "individual" in config.page_tiers
        assert "enterprise" in config.multipliers

    def test_validates_individual_structure(self):
        """Individual has page_tiers, base_pricing, multipliers"""
        # Arrange
        config_path = Path(__file__).parent.parent.parent / "pricing-tiers.yaml"

        # Act
        config = load_pricing_config(str(config_path))

        # Assert - Individual should have all three sections
        assert "individual" in config.page_tiers
        assert "tier1" in config.page_tiers["individual"]
        assert "tier2" in config.page_tiers["individual"]
        assert "tier3" in config.page_tiers["individual"]

        assert "individual" in config.base_pricing
        assert "tier1" in config.base_pricing["individual"]
        assert "tier2" in config.base_pricing["individual"]
        assert "tier3" in config.base_pricing["individual"]

        assert "individual" in config.multipliers
        assert "default" in config.multipliers["individual"]
        assert "human" in config.multipliers["individual"]
        assert "handwriting" in config.multipliers["individual"]
        assert "formats" in config.multipliers["individual"]

    def test_validates_enterprise_structure(self):
        """Enterprise has ONLY multipliers (no page_tiers or base_pricing)"""
        # Arrange
        config_path = Path(__file__).parent.parent.parent / "pricing-tiers.yaml"

        # Act
        config = load_pricing_config(str(config_path))

        # Assert - Enterprise should ONLY have multipliers
        assert "enterprise" in config.multipliers
        assert "default" in config.multipliers["enterprise"]
        assert "human" in config.multipliers["enterprise"]
        assert "handwriting" in config.multipliers["enterprise"]
        assert "formats" in config.multipliers["enterprise"]

        # Verify multiplier values
        assert config.multipliers["enterprise"]["default"] == 1
        assert config.multipliers["enterprise"]["human"] == 15
        assert config.multipliers["enterprise"]["handwriting"] == 25
        assert config.multipliers["enterprise"]["formats"] == 3

    def test_rejects_missing_file(self):
        """FileNotFoundError raised when file doesn't exist"""
        # Arrange
        nonexistent_path = "/path/to/nonexistent/config.yaml"

        # Act & Assert
        with pytest.raises(FileNotFoundError) as exc_info:
            load_pricing_config(nonexistent_path)

        assert "pricing-tiers.yaml" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()

    def test_rejects_invalid_yaml(self, tmp_path):
        """ValidationError raised for malformed YAML"""
        # Arrange - Create invalid YAML file
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("""
page_tiers:
  individual: "this should be a dict not a string"
multipliers: [1, 2, 3]  # Should be dict not list
""")

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            load_pricing_config(str(invalid_yaml))

        # Pydantic will raise validation errors for incorrect structure
        assert exc_info.value.errors()

    def test_validates_tier_ranges(self):
        """Individual tier boundaries valid (tier1 min=1, max=9, etc.)"""
        # Arrange
        config_path = Path(__file__).parent.parent.parent / "pricing-tiers.yaml"

        # Act
        config = load_pricing_config(str(config_path))

        # Assert - Verify tier ranges match expected structure
        individual_tiers = config.page_tiers["individual"]

        # tier1: [1, 9]
        assert individual_tiers["tier1"][0] == 1
        assert individual_tiers["tier1"][1] == 9

        # tier2: [10, 249]
        assert individual_tiers["tier2"][0] == 10
        assert individual_tiers["tier2"][1] == 249

        # tier3: [250, null]
        assert individual_tiers["tier3"][0] == 250
        assert individual_tiers["tier3"][1] is None

        # Verify base pricing values
        individual_pricing = config.base_pricing["individual"]
        assert individual_pricing["tier1"] == 5.0
        assert individual_pricing["tier2"] == 4.0
        assert individual_pricing["tier3"] == 3.0
