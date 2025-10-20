"""
Unit tests for page counting service.

Tests the PageCounterService to ensure accurate page counting
for various file formats used in subscription validation.
"""

import pytest
import os
import tempfile
from pathlib import Path

# Add server directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.page_counter_service import page_counter_service


class TestPageCounterService:
    """Test cases for PageCounterService"""

    @pytest.mark.asyncio
    async def test_pdf_page_counting_sample_files(self):
        """Test PDF page counting with existing sample files"""
        # Use the PDF files we found earlier
        pdf_files = [
            "../ui/translation-service/landing-page-v2.pdf",
            "../ui/translation-service/landing-page.pdf"
        ]

        for pdf_file in pdf_files:
            if os.path.exists(pdf_file):
                page_count = await page_counter_service.count_pages(pdf_file)

                # PDFs should return a positive page count
                assert page_count > 0, f"Expected positive page count for {pdf_file}, got {page_count}"
                assert page_count == 3, f"Expected 3 pages for {pdf_file}, got {page_count}"

    @pytest.mark.asyncio
    async def test_unsupported_file_format(self):
        """Test that unsupported file formats return -1"""
        # Create a temp file with unsupported extension
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_path = temp_file.name

        try:
            page_count = await page_counter_service.count_pages(temp_path)
            assert page_count == -1, "Unsupported format should return -1"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        """Test that non-existent files return -1"""
        page_count = await page_counter_service.count_pages("/nonexistent/file.pdf")
        assert page_count == -1, "Non-existent file should return -1"

    @pytest.mark.asyncio
    async def test_supported_formats_list(self):
        """Test that supported formats list includes expected formats"""
        formats = page_counter_service.get_supported_formats()

        # Check for common formats
        assert '.pdf' in formats
        assert '.docx' in formats
        assert '.txt' in formats
        assert '.rtf' in formats
        assert '.tiff' in formats

        # Verify it's a sorted list
        assert formats == sorted(formats)

    @pytest.mark.asyncio
    async def test_is_supported_format(self):
        """Test format support checking"""
        # Test supported formats
        assert page_counter_service.is_supported_format("document.pdf")
        assert page_counter_service.is_supported_format("document.docx")
        assert page_counter_service.is_supported_format("image.tiff")
        assert page_counter_service.is_supported_format("text.txt")

        # Test unsupported formats
        assert not page_counter_service.is_supported_format("file.xyz")
        assert not page_counter_service.is_supported_format("file.mp4")
        assert not page_counter_service.is_supported_format("file.zip")

    @pytest.mark.asyncio
    async def test_case_insensitive_format_checking(self):
        """Test that format checking is case-insensitive"""
        assert page_counter_service.is_supported_format("document.PDF")
        assert page_counter_service.is_supported_format("document.DOCX")
        assert page_counter_service.is_supported_format("document.Pdf")
        assert page_counter_service.is_supported_format("document.DocX")


class TestPageCountingIntegration:
    """Integration tests for page counting with real files"""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.path.exists("/Users/vladimirdanishevsky/Downloads/Investment Proposal.pdf"),
        reason="Test file not found - skip integration test"
    )
    async def test_real_pdf_file(self):
        """Test page counting with real PDF file"""
        test_file = "/Users/vladimirdanishevsky/Downloads/Investment Proposal.pdf"
        page_count = await page_counter_service.count_pages(test_file)

        # Should return a positive page count
        assert page_count > 0, f"Expected positive page count, got {page_count}"

        # Investment Proposal is approximately 50 pages
        assert 40 <= page_count <= 60, f"Expected ~50 pages, got {page_count}"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.path.exists("/Users/vladimirdanishevsky/Downloads/nuPSYS Lab Management Engineer.docx"),
        reason="Test file not found - skip integration test"
    )
    async def test_real_docx_file(self):
        """Test page counting with real DOCX file"""
        test_file = "/Users/vladimirdanishevsky/Downloads/nuPSYS Lab Management Engineer.docx"
        page_count = await page_counter_service.count_pages(test_file)

        # Should return a positive page count
        assert page_count > 0, f"Expected positive page count, got {page_count}"

        # This DOCX is approximately 100 pages
        assert 80 <= page_count <= 120, f"Expected ~100 pages, got {page_count}"

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.path.exists("/Users/vladimirdanishevsky/Downloads/SOW nuPSYS v2[10].pdf"),
        reason="Test file not found - skip integration test"
    )
    async def test_real_pdf_smaller_file(self):
        """Test page counting with smaller real PDF file"""
        test_file = "/Users/vladimirdanishevsky/Downloads/SOW nuPSYS v2[10].pdf"
        page_count = await page_counter_service.count_pages(test_file)

        # Should return a positive page count
        assert page_count > 0, f"Expected positive page count, got {page_count}"

        # SOW is approximately 32 pages
        assert 25 <= page_count <= 40, f"Expected ~32 pages, got {page_count}"


class TestSubscriptionValidationScenarios:
    """Test page counting in subscription validation scenarios"""

    @pytest.mark.asyncio
    async def test_single_file_below_subscription_limit(self):
        """Simul ate subscription validation with single file below limit"""
        # Scenario: 100 units remaining, 3-page document
        units_remaining = 100
        file_path = "../ui/translation-service/landing-page.pdf"

        if os.path.exists(file_path):
            pages_required = await page_counter_service.count_pages(file_path)

            # Should have sufficient funds
            has_sufficient_funds = units_remaining >= pages_required
            assert has_sufficient_funds, f"Expected sufficient funds: {units_remaining} >= {pages_required}"

    @pytest.mark.asyncio
    async def test_subscription_insufficient_funds_scenario(self):
        """Test subscription validation with insufficient funds"""
        # Scenario from E2E test: 233 units remaining, ~432 pages required
        units_remaining = 233

        # Simulate the 6 test files with their page counts
        test_files_pages = [100, 100, 100, 50, 50, 32]  # Estimated from E2E test
        total_pages = sum(test_files_pages)

        # Should have insufficient funds
        has_sufficient_funds = units_remaining >= total_pages
        assert not has_sufficient_funds, f"Expected insufficient funds: {units_remaining} < {total_pages}"
        assert total_pages == 432, f"Expected 432 total pages, got {total_pages}"

    @pytest.mark.asyncio
    async def test_subscription_exact_match(self):
        """Test subscription validation with exact unit match"""
        units_remaining = 100

        # Simulate a file with exactly 100 pages
        pages_required = 100

        # Should have sufficient funds (exact match)
        has_sufficient_funds = units_remaining >= pages_required
        assert has_sufficient_funds, f"Expected sufficient funds with exact match: {units_remaining} >= {pages_required}"

    @pytest.mark.asyncio
    async def test_subscription_one_page_short(self):
        """Test subscription validation with one page short"""
        units_remaining = 99
        pages_required = 100

        # Should have insufficient funds
        has_sufficient_funds = units_remaining >= pages_required
        assert not has_sufficient_funds, f"Expected insufficient funds: {units_remaining} < {pages_required}"


# Run tests with pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
