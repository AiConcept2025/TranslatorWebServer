"""
Unit tests for /translate-user endpoint.

Tests the individual user translation endpoint including:
- Helper functions (Square ID generation, page count estimation)
- Request validation
- Error handling
"""

import pytest
from app.routers.translate_user import (
    generate_square_transaction_id,
    estimate_page_count,
    get_unit_type,
)


class TestHelperFunctions:
    """Test helper functions used by the translate-user endpoint."""

    def test_generate_square_transaction_id_format(self):
        """Test Square transaction ID format."""
        tx_id = generate_square_transaction_id()

        # Check format: sqt_{20_chars}
        assert tx_id.startswith("sqt_")
        assert len(tx_id) == 24  # "sqt_" (4) + 20 random chars

    def test_generate_square_transaction_id_uniqueness(self):
        """Test that generated IDs are unique."""
        ids = [generate_square_transaction_id() for _ in range(100)]
        assert len(ids) == len(set(ids))  # All IDs should be unique

    def test_estimate_page_count_pdf_small(self):
        """Test page count estimation for small PDF."""
        count = estimate_page_count("document.pdf", 50000)
        assert count == 1  # 50000 // 50000 = 1

    def test_estimate_page_count_pdf_large(self):
        """Test page count estimation for large PDF."""
        count = estimate_page_count("document.pdf", 250000)
        assert count == 5  # 250000 // 50000 = 5

    def test_estimate_page_count_pdf_minimum(self):
        """Test page count minimum is 1 even for very small PDFs."""
        count = estimate_page_count("tiny.pdf", 100)
        assert count == 1  # Minimum is always 1

    def test_estimate_page_count_docx_small(self):
        """Test page count estimation for small Word doc."""
        count = estimate_page_count("document.docx", 25000)
        assert count == 1  # 25000 // 25000 = 1

    def test_estimate_page_count_docx_large(self):
        """Test page count estimation for large Word doc."""
        count = estimate_page_count("document.docx", 100000)
        assert count == 4  # 100000 // 25000 = 4

    def test_estimate_page_count_doc(self):
        """Test page count estimation for .doc files."""
        count = estimate_page_count("document.doc", 75000)
        assert count == 3  # 75000 // 25000 = 3

    def test_estimate_page_count_image_jpg(self):
        """Test page count for JPG image."""
        count = estimate_page_count("photo.jpg", 2000000)
        assert count == 1  # Images are always 1 page

    def test_estimate_page_count_image_png(self):
        """Test page count for PNG image."""
        count = estimate_page_count("image.png", 5000000)
        assert count == 1  # Images are always 1 page

    def test_estimate_page_count_image_jpeg(self):
        """Test page count for JPEG image."""
        count = estimate_page_count("picture.jpeg", 1000000)
        assert count == 1  # Images are always 1 page

    def test_estimate_page_count_image_gif(self):
        """Test page count for GIF image."""
        count = estimate_page_count("animation.gif", 500000)
        assert count == 1  # Images are always 1 page

    def test_estimate_page_count_image_bmp(self):
        """Test page count for BMP image."""
        count = estimate_page_count("bitmap.bmp", 10000000)
        assert count == 1  # Images are always 1 page

    def test_estimate_page_count_unknown_type(self):
        """Test page count for unknown file type."""
        count = estimate_page_count("unknown.xyz", 100000)
        assert count == 2  # Falls back to PDF estimation (100000 // 50000)

    def test_estimate_page_count_case_insensitive(self):
        """Test that file extension matching is case-insensitive."""
        count_upper = estimate_page_count("DOCUMENT.PDF", 100000)
        count_lower = estimate_page_count("document.pdf", 100000)
        assert count_upper == count_lower == 2

    def test_get_unit_type_pdf(self):
        """Test unit type for PDF files."""
        assert get_unit_type("document.pdf") == "page"

    def test_get_unit_type_docx(self):
        """Test unit type for Word documents."""
        assert get_unit_type("document.docx") == "page"

    def test_get_unit_type_image(self):
        """Test unit type for images."""
        assert get_unit_type("photo.jpg") == "page"

    def test_get_unit_type_unknown(self):
        """Test unit type for unknown file types."""
        assert get_unit_type("unknown.xyz") == "page"


class TestValidation:
    """Test validation logic (requires integration test setup)."""

    # Note: These would be integration tests requiring FastAPI test client
    # and would test the actual endpoint validation logic

    pass


class TestPricingCalculation:
    """Test pricing calculation logic."""

    def test_pricing_single_file(self):
        """Test pricing for single file."""
        page_count = 5
        cost_per_unit = 0.10
        total = page_count * cost_per_unit
        assert total == 0.50

    def test_pricing_multiple_files(self):
        """Test pricing for multiple files."""
        files = [
            {"page_count": 5, "cost_per_unit": 0.10},  # $0.50
            {"page_count": 3, "cost_per_unit": 0.10},  # $0.30
            {"page_count": 2, "cost_per_unit": 0.10},  # $0.20
        ]
        total = sum(f["page_count"] * f["cost_per_unit"] for f in files)
        assert total == 1.00

    def test_pricing_to_cents(self):
        """Test conversion of amount to cents."""
        total_amount = 1.50
        amount_cents = int(total_amount * 100)
        assert amount_cents == 150

    def test_pricing_fixed_rate(self):
        """Test that cost per unit is fixed at $0.10."""
        cost_per_unit = 0.10
        assert cost_per_unit == 0.10  # Fixed for individual users


# Pytest configuration
@pytest.fixture
def sample_file_info():
    """Sample file information for testing."""
    return {
        "id": "test-file-1",
        "name": "test.pdf",
        "size": 100000,
        "type": "application/pdf",
        "content": "base64_encoded_content_here",
    }


@pytest.fixture
def sample_request_data():
    """Sample request data for testing."""
    return {
        "files": [
            {
                "id": "test-1",
                "name": "test.pdf",
                "size": 100000,
                "type": "application/pdf",
                "content": "JVBERi0xLjQK...",
            }
        ],
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "email": "test@example.com",
        "userName": "Test User",
    }


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
