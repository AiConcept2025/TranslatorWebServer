"""
Integration tests for /api/transactions/confirm endpoint with nested document structure.

Tests the confirm endpoint's ability to extract file URLs from the nested documents array
after migration from flat structure.
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from app.main import app
from app.database import database


@pytest.fixture
async def test_transaction_nested():
    """
    Create a test transaction with nested documents array (post-migration structure).
    """
    transaction = {
        "transaction_id": "TXN-TEST-CONFIRM-001",
        "user_id": "test@example.com",
        "company_name": "Test Company",
        "subscription_id": "test-sub-001",
        "source_language": "en",
        "target_language": "es",
        "units_count": 5,
        "price_per_unit": 0.01,
        "total_price": 0.05,
        "unit_type": "page",
        "status": "started",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "documents": [
            {
                "file_name": "test_doc.pdf",
                "file_size": 12345,
                "original_url": "https://docs.google.com/document/d/ABC123TEST456/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }

    result = await database.translation_transactions.insert_one(transaction)
    transaction["_id"] = result.inserted_id

    yield transaction

    # Cleanup
    await database.translation_transactions.delete_one({"transaction_id": "TXN-TEST-CONFIRM-001"})


@pytest.fixture
async def test_transaction_multi_doc():
    """
    Create a test transaction with multiple documents (post-migration structure).
    """
    transaction = {
        "transaction_id": "TXN-TEST-CONFIRM-002",
        "user_id": "test@example.com",
        "company_name": "Test Company",
        "subscription_id": "test-sub-001",
        "source_language": "en",
        "target_language": "fr",
        "units_count": 10,
        "price_per_unit": 0.01,
        "total_price": 0.10,
        "unit_type": "page",
        "status": "started",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "documents": [
            {
                "file_name": "doc1.pdf",
                "file_size": 10000,
                "original_url": "https://docs.google.com/document/d/DOC1TEST123/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            },
            {
                "file_name": "doc2.pdf",
                "file_size": 20000,
                "original_url": "https://drive.google.com/file/d/DOC2TEST456/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            },
            {
                "file_name": "sheet1.xlsx",
                "file_size": 15000,
                "original_url": "https://docs.google.com/spreadsheets/d/SHEET1TEST789/edit",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            }
        ]
    }

    result = await database.translation_transactions.insert_one(transaction)
    transaction["_id"] = result.inserted_id

    yield transaction

    # Cleanup
    await database.translation_transactions.delete_one({"transaction_id": "TXN-TEST-CONFIRM-002"})


@pytest.fixture
async def test_transaction_legacy():
    """
    Create a test transaction with flat structure (pre-migration - for backward compatibility test).
    """
    transaction = {
        "transaction_id": "TXN-TEST-CONFIRM-003",
        "user_id": "test@example.com",
        "company_name": "Test Company",
        "subscription_id": "test-sub-001",
        "source_language": "en",
        "target_language": "de",
        "units_count": 3,
        "price_per_unit": 0.01,
        "total_price": 0.03,
        "unit_type": "page",
        "status": "started",
        "error_message": "",
        # Old flat structure
        "file_name": "legacy_doc.pdf",
        "file_size": 8888,
        "original_file_url": "https://docs.google.com/document/d/LEGACYTEST999/edit",
        "translated_file_url": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await database.translation_transactions.insert_one(transaction)
    transaction["_id"] = result.inserted_id

    yield transaction

    # Cleanup
    await database.translation_transactions.delete_one({"transaction_id": "TXN-TEST-CONFIRM-003"})


@pytest.mark.asyncio
async def test_confirm_extracts_file_ids_from_nested_single_document(test_transaction_nested):
    """
    Test that confirm endpoint correctly extracts file IDs from nested documents array (single doc).

    CRITICAL: After migration, file URLs are in documents[].original_url, not top-level original_file_url.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Mock authentication
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={"transaction_ids": ["TXN-TEST-CONFIRM-001"]},
            headers=headers
        )

        # Should succeed (200) and not fail with empty file_ids
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["success"] is True
        assert data["data"]["confirmed_transactions"] == 1
        assert data["data"]["total_files"] == 1, "Should extract 1 file from nested structure"
        assert data["data"]["customer_email"] == "test@example.com"


@pytest.mark.asyncio
async def test_confirm_extracts_file_ids_from_nested_multiple_documents(test_transaction_multi_doc):
    """
    Test that confirm endpoint correctly extracts file IDs from multiple documents in nested array.

    Tests all Google Drive URL patterns:
    - /document/d/
    - /file/d/
    - /spreadsheets/d/
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={"transaction_ids": ["TXN-TEST-CONFIRM-002"]},
            headers=headers
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["success"] is True
        assert data["data"]["confirmed_transactions"] == 1
        assert data["data"]["total_files"] == 3, "Should extract 3 files from nested structure"
        assert data["data"]["customer_email"] == "test@example.com"


@pytest.mark.asyncio
async def test_confirm_handles_legacy_flat_structure(test_transaction_legacy):
    """
    Test backward compatibility: confirm endpoint handles old flat structure if needed.

    Defensive coding - shouldn't happen after migration but ensures no crashes.
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        headers = {"Authorization": "Bearer test-token"}

        response = await client.post(
            "/api/transactions/confirm",
            json={"transaction_ids": ["TXN-TEST-CONFIRM-003"]},
            headers=headers
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert data["success"] is True
        assert data["data"]["confirmed_transactions"] == 1
        assert data["data"]["total_files"] == 1, "Should extract 1 file from legacy flat structure"
        assert data["data"]["customer_email"] == "test@example.com"


@pytest.mark.asyncio
async def test_confirm_extracts_correct_file_ids_nested():
    """
    Test that file IDs are correctly extracted from nested documents.

    Verifies the actual file ID extraction logic.
    """
    transaction = {
        "transaction_id": "TXN-TEST-CONFIRM-004",
        "user_id": "test@example.com",
        "company_name": "Test Company",
        "source_language": "en",
        "target_language": "es",
        "units_count": 5,
        "price_per_unit": 0.01,
        "total_price": 0.05,
        "unit_type": "page",
        "status": "started",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "documents": [
            {
                "file_name": "test.pdf",
                "file_size": 100,
                "original_url": "https://docs.google.com/document/d/1ABC-DEF-GHI-123/edit",
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc)
            }
        ]
    }

    await database.translation_transactions.insert_one(transaction)

    try:
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm",
                json={"transaction_ids": ["TXN-TEST-CONFIRM-004"]},
                headers=headers
            )

            assert response.status_code == 200
            data = response.json()

            # The file ID should be extracted: 1ABC-DEF-GHI-123
            assert data["data"]["total_files"] == 1

    finally:
        await database.translation_transactions.delete_one({"transaction_id": "TXN-TEST-CONFIRM-004"})


@pytest.mark.asyncio
async def test_confirm_handles_empty_documents_array():
    """
    Test that confirm endpoint handles transactions with empty documents array gracefully.
    """
    transaction = {
        "transaction_id": "TXN-TEST-CONFIRM-005",
        "user_id": "test@example.com",
        "source_language": "en",
        "target_language": "es",
        "units_count": 0,
        "price_per_unit": 0.01,
        "total_price": 0.00,
        "unit_type": "page",
        "status": "started",
        "error_message": "",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "documents": []  # Empty array
    }

    await database.translation_transactions.insert_one(transaction)

    try:
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": "Bearer test-token"}

            response = await client.post(
                "/api/transactions/confirm",
                json={"transaction_ids": ["TXN-TEST-CONFIRM-005"]},
                headers=headers
            )

            # Should still succeed but with 0 files
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["total_files"] == 0

    finally:
        await database.translation_transactions.delete_one({"transaction_id": "TXN-TEST-CONFIRM-005"})
