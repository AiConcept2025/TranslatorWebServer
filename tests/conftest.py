"""
Pytest configuration for integration tests.
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from app.database.mongodb import database


# Configure pytest to use asyncio
def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test"
    )


# ============================================================================
# Shared Test Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def test_transaction_with_nested_docs():
    """
    Create test transaction with nested documents structure.

    Returns a complete transaction document matching the new nested structure.
    Automatically cleaned up after test.

    Structure:
    - transaction_id: TXN-TEST-{uuid}
    - documents: array with 1 document
    - All required transaction fields
    """
    await database.connect()
    collection = database.translation_transactions

    transaction_id = f"TXN-TEST-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "user_id": "testuser@example.com",
        "company_name": None,  # Individual customer
        "source_language": "en",
        "target_language": "fr",
        "units_count": 15,
        "price_per_unit": 0.10,
        "total_price": 1.50,
        "status": "started",
        "error_message": "",
        "created_at": now,
        "updated_at": now,
        "unit_type": "page",

        # Nested documents array (NEW STRUCTURE)
        "documents": [
            {
                "file_name": "test_document.pdf",
                "file_size": 204800,
                "original_url": "https://docs.google.com/document/d/test123/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }

    result = await collection.insert_one(transaction_doc)
    transaction_doc["_id"] = result.inserted_id

    yield transaction_doc

    # Cleanup
    await collection.delete_one({"transaction_id": transaction_id})


@pytest.fixture(scope="function")
async def sample_nested_transaction_data() -> Dict[str, Any]:
    """
    Sample nested transaction data for testing without database insertion.

    Returns a dict with complete transaction structure including nested documents.
    Useful for model validation tests that don't require database.
    """
    now = datetime.now(timezone.utc)

    return {
        "transaction_id": f"TXN-SAMPLE-{uuid.uuid4().hex[:8].upper()}",
        "user_id": "sample@example.com",
        "company_name": "Sample Company",
        "source_language": "de",
        "target_language": "en",
        "units_count": 20,
        "price_per_unit": 0.12,
        "total_price": 2.40,
        "status": "confirmed",
        "error_message": "",
        "created_at": now,
        "updated_at": now,
        "unit_type": "word",

        "documents": [
            {
                "file_name": "sample_doc_1.pdf",
                "file_size": 150000,
                "original_url": "https://docs.google.com/document/d/sample1/edit",
                "translated_url": "https://docs.google.com/document/d/sample1_trans/edit",
                "translated_name": "sample_doc_1_en.pdf",
                "status": "completed",
                "uploaded_at": now,
                "translated_at": now,
                "processing_started_at": now,
                "processing_duration": 95.3
            },
            {
                "file_name": "sample_doc_2.docx",
                "file_size": 250000,
                "original_url": "https://docs.google.com/document/d/sample2/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }
