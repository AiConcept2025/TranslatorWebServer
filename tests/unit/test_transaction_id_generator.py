"""
Unit tests for transaction ID generator utility.

Tests cover:
- Random format generation
- Fallback format generation
- Uniqueness checking logic
- Retry mechanism
- Format validation
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from app.utils.transaction_id_generator import (
    generate_unique_transaction_id,
    _generate_random_format,
    _generate_fallback_format,
    validate_transaction_id_format
)


class TestRandomFormatGeneration:
    """Test standard USER + 6-digit format generation."""

    def test_generates_correct_format(self):
        """Test that random format matches USER + 6 digits."""
        transaction_id = _generate_random_format()

        assert transaction_id.startswith("USER")
        assert len(transaction_id) == 10  # "USER" + 6 digits
        assert transaction_id[4:].isdigit()

    def test_generates_different_ids(self):
        """Test that multiple calls generate different IDs (usually)."""
        ids = [_generate_random_format() for _ in range(10)]

        # With 1M possibilities, duplicates are unlikely
        # But not impossible, so we just check most are unique
        unique_ids = set(ids)
        assert len(unique_ids) >= 8  # At least 8/10 should be unique

    def test_pads_zeros_correctly(self):
        """Test that numbers are zero-padded to 6 digits."""
        with patch('random.randint', return_value=42):
            transaction_id = _generate_random_format()
            assert transaction_id == "USER000042"

        with patch('random.randint', return_value=0):
            transaction_id = _generate_random_format()
            assert transaction_id == "USER000000"

        with patch('random.randint', return_value=999999):
            transaction_id = _generate_random_format()
            assert transaction_id == "USER999999"


class TestFallbackFormatGeneration:
    """Test fallback USER + timestamp + 3-digit format generation."""

    def test_generates_correct_format(self):
        """Test that fallback format has correct structure."""
        transaction_id = _generate_fallback_format()

        assert transaction_id.startswith("USER")
        assert len(transaction_id) >= 17  # "USER" + 13-digit timestamp + 3 digits
        assert transaction_id[4:].isdigit()

    def test_includes_timestamp(self):
        """Test that fallback includes current timestamp."""
        before_timestamp = int(time.time() * 1000)
        transaction_id = _generate_fallback_format()
        after_timestamp = int(time.time() * 1000)

        # Extract timestamp from ID (remove "USER" prefix and last 3 digits)
        id_timestamp = int(transaction_id[4:-3])

        assert before_timestamp <= id_timestamp <= after_timestamp

    def test_generates_unique_ids_in_sequence(self):
        """Test that sequential calls generate unique IDs."""
        ids = [_generate_fallback_format() for _ in range(5)]

        # All should be unique due to timestamp + random suffix
        assert len(set(ids)) == 5

    def test_pads_random_suffix(self):
        """Test that random suffix is zero-padded to 3 digits."""
        with patch('random.randint', return_value=5):
            transaction_id = _generate_fallback_format()
            # Last 3 characters should be "005"
            assert transaction_id[-3:] == "005"


class TestValidateTransactionIdFormat:
    """Test transaction ID format validation."""

    def test_valid_standard_format(self):
        """Test validation of standard format IDs."""
        assert validate_transaction_id_format("USER123456") is True
        assert validate_transaction_id_format("USER000000") is True
        assert validate_transaction_id_format("USER999999") is True

    def test_valid_fallback_format(self):
        """Test validation of fallback format IDs."""
        assert validate_transaction_id_format("USER1699123456789123") is True
        assert validate_transaction_id_format("USER1699123456789000") is True

    def test_invalid_prefix(self):
        """Test rejection of invalid prefixes."""
        assert validate_transaction_id_format("ADMIN123456") is False
        assert validate_transaction_id_format("123456") is False
        assert validate_transaction_id_format("user123456") is False  # lowercase

    def test_invalid_length(self):
        """Test rejection of invalid lengths."""
        assert validate_transaction_id_format("USER12345") is False  # 5 digits
        assert validate_transaction_id_format("USER1234567") is False  # 7 digits
        assert validate_transaction_id_format("USER123") is False  # 3 digits

    def test_invalid_characters(self):
        """Test rejection of non-numeric characters."""
        assert validate_transaction_id_format("USER12345A") is False
        assert validate_transaction_id_format("USER-123456") is False
        assert validate_transaction_id_format("USER 123456") is False

    def test_empty_string(self):
        """Test rejection of empty string."""
        assert validate_transaction_id_format("") is False

    def test_user_prefix_only(self):
        """Test rejection of prefix without number."""
        assert validate_transaction_id_format("USER") is False


class TestGenerateUniqueTransactionId:
    """Test unique transaction ID generation with collision detection."""

    @pytest.mark.asyncio
    async def test_generates_unique_id_first_try(self):
        """Test successful generation on first attempt."""
        # Mock collection that returns None (no collision)
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None

        transaction_id = await generate_unique_transaction_id(mock_collection)

        assert transaction_id.startswith("USER")
        assert len(transaction_id) == 10  # Standard format
        mock_collection.find_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_collision(self):
        """Test retry logic when collision occurs."""
        mock_collection = AsyncMock()

        # First 2 calls return existing doc (collision)
        # Third call returns None (unique)
        mock_collection.find_one.side_effect = [
            {"_id": "existing1"},  # Collision
            {"_id": "existing2"},  # Collision
            None,  # Success
        ]

        transaction_id = await generate_unique_transaction_id(mock_collection, max_retries=5)

        assert transaction_id.startswith("USER")
        assert mock_collection.find_one.call_count == 3

    @pytest.mark.asyncio
    async def test_uses_fallback_after_max_retries(self):
        """Test fallback format after exhausting retries."""
        mock_collection = AsyncMock()

        # Return collision for standard format (max_retries times)
        # Return None for fallback format
        def find_one_side_effect(query):
            transaction_id = query["transaction_id"]
            if len(transaction_id) == 10:  # Standard format
                return {"_id": "collision"}
            else:  # Fallback format
                return None

        mock_collection.find_one.side_effect = find_one_side_effect

        transaction_id = await generate_unique_transaction_id(mock_collection, max_retries=3)

        assert transaction_id.startswith("USER")
        assert len(transaction_id) >= 17  # Fallback format (longer)
        # Should call: 3 retries + 1 fallback check = 4 total
        assert mock_collection.find_one.call_count == 4

    @pytest.mark.asyncio
    async def test_handles_fallback_collision(self):
        """Test handling of extremely unlikely fallback collision."""
        mock_collection = AsyncMock()

        call_count = 0

        def find_one_side_effect(query):
            nonlocal call_count
            call_count += 1
            transaction_id = query["transaction_id"]

            # All standard format: collision
            if len(transaction_id) == 10:
                return {"_id": "collision"}
            # First fallback: collision (extremely unlikely)
            elif call_count == 4:
                return {"_id": "fallback_collision"}
            # Extended fallback: success
            else:
                return None

        mock_collection.find_one.side_effect = find_one_side_effect

        transaction_id = await generate_unique_transaction_id(mock_collection, max_retries=3)

        assert transaction_id.startswith("USER")
        # Extended fallback should have additional 2 digits
        assert len(transaction_id) >= 19

    @pytest.mark.asyncio
    async def test_respects_max_retries_parameter(self):
        """Test that max_retries parameter is respected."""
        mock_collection = AsyncMock()

        # Always return collision for standard format
        def find_one_side_effect(query):
            transaction_id = query["transaction_id"]
            if len(transaction_id) == 10:  # Standard format
                return {"_id": "collision"}
            else:  # Fallback format
                return None

        mock_collection.find_one.side_effect = find_one_side_effect

        # Test with max_retries=2
        await generate_unique_transaction_id(mock_collection, max_retries=2)
        assert mock_collection.find_one.call_count == 3  # 2 retries + 1 fallback

        # Reset mock
        mock_collection.find_one.reset_mock()
        mock_collection.find_one.side_effect = find_one_side_effect

        # Test with max_retries=10
        await generate_unique_transaction_id(mock_collection, max_retries=10)
        assert mock_collection.find_one.call_count == 11  # 10 retries + 1 fallback

    @pytest.mark.asyncio
    async def test_validates_format_of_generated_id(self):
        """Test that generated IDs pass format validation."""
        mock_collection = AsyncMock()
        mock_collection.find_one.return_value = None

        for _ in range(10):
            transaction_id = await generate_unique_transaction_id(mock_collection)
            assert validate_transaction_id_format(transaction_id) is True
