"""
Transaction ID Generator Utility

Generates unique transaction IDs in format: USER + 6-digit number
Example: USER123456, USER789012

Includes collision detection, retry logic, and fallback format.
"""

import random
import time
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorCollection


async def generate_unique_transaction_id(
    collection: AsyncIOMotorCollection,
    max_retries: int = 5
) -> str:
    """
    Generate a unique transaction ID for user transactions.

    Format: USER + 6-digit random number (e.g., USER123456)
    Fallback: USER + timestamp_ms + 3-digit random if collisions persist

    Args:
        collection: MongoDB collection to check uniqueness against
        max_retries: Maximum number of retry attempts (default: 5)

    Returns:
        Unique transaction ID string

    Raises:
        RuntimeError: If unable to generate unique ID after max_retries
                     (should never happen with fallback)
    """
    # Try random format first (up to max_retries)
    for attempt in range(max_retries):
        transaction_id = _generate_random_format()

        # Check if ID already exists in database
        existing = await collection.find_one({"transaction_id": transaction_id})

        if not existing:
            return transaction_id

        # Collision detected, will retry
        print(f"Transaction ID collision detected: {transaction_id} (attempt {attempt + 1}/{max_retries})")

    # All retries exhausted, use fallback format (guaranteed unique)
    fallback_id = _generate_fallback_format()

    # Verify fallback is unique (should always be due to timestamp)
    existing = await collection.find_one({"transaction_id": fallback_id})
    if existing:
        # Extremely unlikely - add additional randomness
        fallback_id = f"{fallback_id}{random.randint(0, 99):02d}"

    return fallback_id


def _generate_random_format() -> str:
    """
    Generate transaction ID in standard format: USER + 6-digit number.

    Returns:
        Transaction ID like USER123456
    """
    # Generate 6-digit number (000000-999999)
    random_number = random.randint(0, 999999)
    return f"USER{random_number:06d}"


def _generate_fallback_format() -> str:
    """
    Generate transaction ID in fallback format: USER + timestamp + 3-digit number.

    Uses millisecond timestamp to ensure uniqueness.

    Returns:
        Transaction ID like USER1699123456789123
    """
    # Get current timestamp in milliseconds
    timestamp_ms = int(time.time() * 1000)

    # Add 3-digit random for extra uniqueness
    random_suffix = random.randint(0, 999)

    return f"USER{timestamp_ms}{random_suffix:03d}"


def validate_transaction_id_format(transaction_id: str) -> bool:
    """
    Validate that a transaction ID matches expected format.

    Valid formats:
    - USER + 6 digits (standard): USER123456
    - USER + timestamp + 3 digits (fallback): USER1699123456789123

    Args:
        transaction_id: Transaction ID string to validate

    Returns:
        True if valid format, False otherwise
    """
    if not transaction_id.startswith("USER"):
        return False

    # Extract numeric part
    numeric_part = transaction_id[4:]  # Remove "USER" prefix

    # Check if numeric part is all digits
    if not numeric_part.isdigit():
        return False

    # Valid lengths: 6 (standard) or 16+ (fallback with timestamp)
    return len(numeric_part) == 6 or len(numeric_part) >= 16


def generate_translation_transaction_id() -> str:
    """
    Generate transaction ID for translation_transactions collection.

    Format: TXN-{10-character-hex}
    Example: TXN-20FEF6D8FE, TXN-A1B2C3D4E5

    Uses secrets module for cryptographically strong randomness.

    Returns:
        Transaction ID string like TXN-20FEF6D8FE
    """
    import secrets
    hex_suffix = secrets.token_hex(5).upper()  # 10 hex characters
    return f"TXN-{hex_suffix}"
