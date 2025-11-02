"""
Pytest configuration for integration tests.
"""

import pytest


# Configure pytest to use asyncio
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )
