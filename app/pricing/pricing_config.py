"""
Pricing configuration loader for translation service.

Loads and validates pricing configuration from YAML file.
Implements caching for performance optimization.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

# Set up module logger
logger = logging.getLogger(__name__)

# Type aliases for complex types
TierRange = List[Optional[int]]
TierRanges = Dict[str, TierRange]
PageTiers = Dict[str, TierRanges]
BasePricing = Dict[str, Dict[str, float]]
Multipliers = Dict[str, Dict[str, int]]


class PricingConfig(BaseModel):
    """
    Top-level pricing configuration model.

    Validates the structure of pricing configuration loaded from YAML.
    Uses strict validation to reject unknown fields.

    Attributes:
        page_tiers: Tier ranges by user type (individual/enterprise).
            Example: {"individual": {"tier1": [1, 9], "tier2": [10, 249]}}
        base_pricing: Base prices per page by user type and tier.
            Example: {"individual": {"tier1": 5.0, "tier2": 4.0}}
        multipliers: Price multipliers by user type and service type.
            Example: {"individual": {"default": 1, "human": 10}}
    """

    model_config = ConfigDict(
        extra="forbid",  # Reject unknown fields
        frozen=True,  # Make immutable after creation
    )

    page_tiers: PageTiers
    base_pricing: BasePricing
    multipliers: Multipliers


@lru_cache(maxsize=1)
def load_pricing_config(path: str = "pricing-tiers.yaml") -> PricingConfig:
    """
    Load and validate pricing configuration from YAML file.

    This function is cached using @lru_cache to avoid re-loading the YAML file
    on every call. The cache is invalidated when the path changes.

    Args:
        path: Path to YAML configuration file (default: "pricing-tiers.yaml").
            Can be absolute or relative. Relative paths are resolved from the
            current working directory.

    Returns:
        PricingConfig: Validated and immutable pricing configuration object.

    Raises:
        FileNotFoundError: If configuration file doesn't exist at the specified path.
        yaml.YAMLError: If YAML file contains syntax errors.
        ValidationError: If YAML structure doesn't match PricingConfig schema.

    Example:
        >>> config = load_pricing_config("pricing-tiers.yaml")
        >>> config.base_pricing["individual"]["tier1"]
        5.0
        >>> config.multipliers["enterprise"]["human"]
        15
    """
    # Resolve path (handles both absolute and relative paths)
    config_path = Path(path).resolve()

    logger.info(f"Loading pricing configuration from: {config_path}")

    # Check file exists
    if not config_path.exists():
        logger.error(f"Pricing configuration file not found: {config_path}")
        raise FileNotFoundError(
            f"Pricing configuration file not found: {config_path}\n"
            f"Expected location: {config_path.absolute()}"
        )

    # Load YAML
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        logger.debug(f"Successfully loaded YAML data with keys: {list(data.keys())}")
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML file: {e}")
        raise yaml.YAMLError(f"Invalid YAML format in {config_path}: {e}") from e

    # Validate with Pydantic
    try:
        config = PricingConfig(**data)
        logger.info(
            f"Successfully validated pricing config: "
            f"{len(config.page_tiers)} user types, "
            f"{sum(len(tiers) for tiers in config.page_tiers.values())} tiers total"
        )
        return config
    except ValidationError as e:
        logger.error(f"Pricing configuration validation failed: {e}")
        raise  # Re-raise with original context
