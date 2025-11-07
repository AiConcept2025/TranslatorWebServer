"""
UNIT TESTS FOR TRANSLATION TRANSACTION MODELS

Tests Pydantic model validation for nested translation transaction structure.
Covers TranslationDocumentSchema and TranslationTransactionListItem models.

Test Coverage:
- TranslationDocumentSchema validation
- Required vs optional fields
- Default values
- Datetime handling
- TranslationTransactionListItem with documents array
- Min 1 document requirement
- Serialization to JSON
"""

import pytest
from datetime import datetime, timezone
from typing import List
from pydantic import ValidationError

from app.models.translation_transaction import (
    TranslationDocumentSchema,
    TranslationTransactionListItem,
    TranslationTransactionListFilters,
    TranslationTransactionListData,
    TranslationTransactionListResponse
)


# ============================================================================
# Test 1: TranslationDocumentSchema - Required Fields
# ============================================================================

def test_translation_document_schema_required_fields():
    """
    Test TranslationDocumentSchema with all required fields.

    Verifies:
    - Required fields: file_name, file_size, original_url
    - Default values: status="uploaded", uploaded_at=now()
    - Optional fields: translated_url, translated_name, translated_at
    """
    doc = TranslationDocumentSchema(
        file_name="test.pdf",
        file_size=102400,
        original_url="https://docs.google.com/document/d/test123/edit"
    )

    assert doc.file_name == "test.pdf"
    assert doc.file_size == 102400
    assert doc.original_url == "https://docs.google.com/document/d/test123/edit"

    # Default values
    assert doc.status == "uploaded"
    assert doc.uploaded_at is not None
    assert isinstance(doc.uploaded_at, datetime)
    assert doc.uploaded_at.tzinfo == timezone.utc

    # Optional fields default to None
    assert doc.translated_url is None
    assert doc.translated_name is None
    assert doc.translated_at is None
    assert doc.processing_started_at is None
    assert doc.processing_duration is None


def test_translation_document_schema_missing_required_fields():
    """
    Test that missing required fields raise ValidationError.
    """
    with pytest.raises(ValidationError) as exc_info:
        TranslationDocumentSchema(
            file_name="test.pdf"
            # Missing file_size and original_url
        )

    errors = exc_info.value.errors()
    error_fields = [e["loc"][0] for e in errors]

    assert "file_size" in error_fields
    assert "original_url" in error_fields


def test_translation_document_schema_all_fields():
    """
    Test TranslationDocumentSchema with all fields populated.
    """
    now = datetime.now(timezone.utc)

    doc = TranslationDocumentSchema(
        file_name="contract.docx",
        file_size=524288,
        original_url="https://docs.google.com/document/d/orig123/edit",
        translated_url="https://docs.google.com/document/d/trans456/edit",
        translated_name="contract_fr.docx",
        status="completed",
        uploaded_at=now,
        translated_at=now,
        processing_started_at=now,
        processing_duration=125.5,
        transaction_id="TXN-ABC123"
    )

    assert doc.file_name == "contract.docx"
    assert doc.file_size == 524288
    assert doc.original_url == "https://docs.google.com/document/d/orig123/edit"
    assert doc.translated_url == "https://docs.google.com/document/d/trans456/edit"
    assert doc.translated_name == "contract_fr.docx"
    assert doc.status == "completed"
    assert doc.uploaded_at == now
    assert doc.translated_at == now
    assert doc.processing_started_at == now
    assert doc.processing_duration == 125.5
    assert doc.transaction_id == "TXN-ABC123"


def test_translation_document_schema_status_values():
    """
    Test valid status values: uploaded, translating, completed, failed.
    """
    valid_statuses = ["uploaded", "translating", "completed", "failed"]

    for status_val in valid_statuses:
        doc = TranslationDocumentSchema(
            file_name="test.pdf",
            file_size=100000,
            original_url="https://docs.google.com/document/d/test/edit",
            status=status_val
        )
        assert doc.status == status_val


def test_translation_document_schema_file_size_validation():
    """
    Test file_size validation (must be >= 0).
    """
    # Valid: file_size = 0
    doc = TranslationDocumentSchema(
        file_name="empty.txt",
        file_size=0,
        original_url="https://docs.google.com/document/d/empty/edit"
    )
    assert doc.file_size == 0

    # Invalid: file_size < 0
    with pytest.raises(ValidationError) as exc_info:
        TranslationDocumentSchema(
            file_name="invalid.pdf",
            file_size=-1,
            original_url="https://docs.google.com/document/d/test/edit"
        )

    errors = exc_info.value.errors()
    assert any(e["loc"][0] == "file_size" for e in errors)


def test_translation_document_schema_processing_duration_validation():
    """
    Test processing_duration validation (must be >= 0).
    """
    # Valid: processing_duration = 0
    doc = TranslationDocumentSchema(
        file_name="instant.pdf",
        file_size=1000,
        original_url="https://docs.google.com/document/d/instant/edit",
        processing_duration=0.0
    )
    assert doc.processing_duration == 0.0

    # Valid: processing_duration > 0
    doc = TranslationDocumentSchema(
        file_name="normal.pdf",
        file_size=1000,
        original_url="https://docs.google.com/document/d/normal/edit",
        processing_duration=89.5
    )
    assert doc.processing_duration == 89.5

    # Invalid: processing_duration < 0
    with pytest.raises(ValidationError) as exc_info:
        TranslationDocumentSchema(
            file_name="invalid.pdf",
            file_size=1000,
            original_url="https://docs.google.com/document/d/test/edit",
            processing_duration=-10.5
        )

    errors = exc_info.value.errors()
    assert any(e["loc"][0] == "processing_duration" for e in errors)


# ============================================================================
# Test 2: TranslationTransactionListItem - Documents Array
# ============================================================================

def test_translation_transaction_with_documents_array():
    """
    Test TranslationTransactionListItem with nested documents array.

    Verifies:
    - documents array is required
    - Min 1 document required
    - Nested document validation works
    """
    now = datetime.now(timezone.utc)

    txn = TranslationTransactionListItem(
        _id="68fe1edeac2359ccbc6b05b2",
        transaction_id="TXN-ABC123",
        user_id="user@example.com",
        documents=[
            TranslationDocumentSchema(
                file_name="doc1.pdf",
                file_size=100000,
                original_url="https://docs.google.com/document/d/doc1/edit",
                status="uploaded",
                uploaded_at=now
            )
        ],
        source_language="en",
        target_language="fr",
        units_count=10,
        price_per_unit=0.10,
        total_price=1.00,
        status="started",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        unit_type="page"
    )

    assert txn.transaction_id == "TXN-ABC123"
    assert len(txn.documents) == 1
    assert txn.documents[0].file_name == "doc1.pdf"


def test_translation_transaction_min_documents_requirement():
    """
    Test that at least 1 document is required in documents array.
    """
    now = datetime.now(timezone.utc)

    # Empty documents array should fail validation
    with pytest.raises(ValidationError) as exc_info:
        TranslationTransactionListItem(
            _id="68fe1edeac2359ccbc6b05b2",
            transaction_id="TXN-ABC123",
            user_id="user@example.com",
            documents=[],  # Empty - should fail
            source_language="en",
            target_language="fr",
            units_count=10,
            price_per_unit=0.10,
            total_price=1.00,
            status="started",
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            unit_type="page"
        )

    errors = exc_info.value.errors()
    assert any("documents" in str(e["loc"]) for e in errors)


def test_translation_transaction_multiple_documents():
    """
    Test TranslationTransactionListItem with multiple documents.
    """
    now = datetime.now(timezone.utc)

    txn = TranslationTransactionListItem(
        _id="68fe1edeac2359ccbc6b05b2",
        transaction_id="TXN-MULTI123",
        user_id="user@example.com",
        documents=[
            TranslationDocumentSchema(
                file_name="doc1.pdf",
                file_size=100000,
                original_url="https://docs.google.com/document/d/doc1/edit"
            ),
            TranslationDocumentSchema(
                file_name="doc2.docx",
                file_size=200000,
                original_url="https://docs.google.com/document/d/doc2/edit"
            ),
            TranslationDocumentSchema(
                file_name="doc3.txt",
                file_size=50000,
                original_url="https://docs.google.com/document/d/doc3/edit"
            )
        ],
        source_language="de",
        target_language="en",
        units_count=30,
        price_per_unit=0.08,
        total_price=2.40,
        status="started",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        unit_type="page"
    )

    assert len(txn.documents) == 3
    assert txn.documents[0].file_name == "doc1.pdf"
    assert txn.documents[1].file_name == "doc2.docx"
    assert txn.documents[2].file_name == "doc3.txt"


# ============================================================================
# Test 3: Datetime Handling and Serialization
# ============================================================================

def test_datetime_serialization_to_json():
    """
    Test that datetime fields serialize to ISO 8601 strings.

    Verifies:
    - Datetime objects in documents serialize correctly
    - ISO 8601 format with timezone
    - model_dump() produces JSON-compatible dict
    """
    now = datetime.now(timezone.utc)

    doc = TranslationDocumentSchema(
        file_name="serialize_test.pdf",
        file_size=150000,
        original_url="https://docs.google.com/document/d/test/edit",
        uploaded_at=now,
        translated_at=now
    )

    # Serialize to dict
    doc_dict = doc.model_dump()

    # Datetime fields should be serialized as datetime objects by default
    assert isinstance(doc_dict["uploaded_at"], datetime)
    assert isinstance(doc_dict["translated_at"], datetime)

    # Use mode='json' to get JSON-compatible dict with ISO strings
    doc_json = doc.model_dump(mode='json')

    # Should be ISO strings
    assert isinstance(doc_json["uploaded_at"], str)
    assert isinstance(doc_json["translated_at"], str)

    # Verify ISO 8601 format
    datetime.fromisoformat(doc_json["uploaded_at"].replace("Z", "+00:00"))
    datetime.fromisoformat(doc_json["translated_at"].replace("Z", "+00:00"))


def test_transaction_list_item_serialization():
    """
    Test full transaction serialization with nested documents.
    """
    now = datetime.now(timezone.utc)

    txn = TranslationTransactionListItem(
        _id="68fe1edeac2359ccbc6b05b2",
        transaction_id="TXN-SERIALIZE",
        user_id="user@example.com",
        documents=[
            TranslationDocumentSchema(
                file_name="test.pdf",
                file_size=100000,
                original_url="https://docs.google.com/document/d/test/edit",
                uploaded_at=now,
                translated_at=now
            )
        ],
        source_language="en",
        target_language="es",
        units_count=15,
        price_per_unit=0.12,
        total_price=1.80,
        status="confirmed",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        unit_type="page"
    )

    # Serialize with mode='json' for API response
    txn_json = txn.model_dump(mode='json', by_alias=True)

    # Verify _id alias works
    assert "_id" in txn_json
    assert txn_json["_id"] == "68fe1edeac2359ccbc6b05b2"

    # Verify nested documents serialize
    assert "documents" in txn_json
    assert len(txn_json["documents"]) == 1

    doc = txn_json["documents"][0]
    assert isinstance(doc["uploaded_at"], str)
    assert isinstance(doc["translated_at"], str)


# ============================================================================
# Test 4: TranslationTransactionListData and Response
# ============================================================================

def test_translation_transaction_list_data():
    """
    Test TranslationTransactionListData wrapper model.
    """
    now = datetime.now(timezone.utc)

    txn = TranslationTransactionListItem(
        _id="68fe1edeac2359ccbc6b05b2",
        transaction_id="TXN-LIST",
        user_id="user@example.com",
        documents=[
            TranslationDocumentSchema(
                file_name="list_test.pdf",
                file_size=80000,
                original_url="https://docs.google.com/document/d/list/edit"
            )
        ],
        source_language="fr",
        target_language="de",
        units_count=8,
        price_per_unit=0.09,
        total_price=0.72,
        status="pending",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        unit_type="page"
    )

    filters = TranslationTransactionListFilters(
        company_name="Test Company",
        status="pending"
    )

    list_data = TranslationTransactionListData(
        transactions=[txn],
        count=1,
        limit=50,
        skip=0,
        filters=filters
    )

    assert len(list_data.transactions) == 1
    assert list_data.count == 1
    assert list_data.limit == 50
    assert list_data.skip == 0
    assert list_data.filters.company_name == "Test Company"
    assert list_data.filters.status == "pending"


def test_translation_transaction_list_response():
    """
    Test full TranslationTransactionListResponse model.
    """
    now = datetime.now(timezone.utc)

    txn = TranslationTransactionListItem(
        _id="68fe1edeac2359ccbc6b05b2",
        transaction_id="TXN-RESPONSE",
        user_id="user@example.com",
        documents=[
            TranslationDocumentSchema(
                file_name="response_test.pdf",
                file_size=120000,
                original_url="https://docs.google.com/document/d/response/edit"
            )
        ],
        source_language="ja",
        target_language="en",
        units_count=20,
        price_per_unit=0.15,
        total_price=3.00,
        status="started",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        unit_type="word"
    )

    filters = TranslationTransactionListFilters(
        company_name="Test Company",
        status=None
    )

    list_data = TranslationTransactionListData(
        transactions=[txn],
        count=1,
        limit=50,
        skip=0,
        filters=filters
    )

    response = TranslationTransactionListResponse(
        success=True,
        data=list_data
    )

    assert response.success is True
    assert len(response.data.transactions) == 1
    assert response.data.transactions[0].transaction_id == "TXN-RESPONSE"

    # Serialize to JSON
    response_json = response.model_dump(mode='json', by_alias=True)

    assert response_json["success"] is True
    assert "data" in response_json
    assert "transactions" in response_json["data"]
    assert len(response_json["data"]["transactions"]) == 1


# ============================================================================
# Test 5: Field Type Validation
# ============================================================================

def test_units_count_validation():
    """
    Test units_count must be >= 0.
    """
    now = datetime.now(timezone.utc)

    # Valid: units_count = 0
    txn = TranslationTransactionListItem(
        _id="68fe1edeac2359ccbc6b05b2",
        transaction_id="TXN-ZERO",
        user_id="user@example.com",
        documents=[
            TranslationDocumentSchema(
                file_name="zero.pdf",
                file_size=1000,
                original_url="https://docs.google.com/document/d/zero/edit"
            )
        ],
        source_language="en",
        target_language="fr",
        units_count=0,
        price_per_unit=0.10,
        total_price=0.00,
        status="started",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        unit_type="page"
    )
    assert txn.units_count == 0

    # Invalid: units_count < 0
    with pytest.raises(ValidationError):
        TranslationTransactionListItem(
            _id="68fe1edeac2359ccbc6b05b2",
            transaction_id="TXN-NEGATIVE",
            user_id="user@example.com",
            documents=[
                TranslationDocumentSchema(
                    file_name="negative.pdf",
                    file_size=1000,
                    original_url="https://docs.google.com/document/d/neg/edit"
                )
            ],
            source_language="en",
            target_language="fr",
            units_count=-5,
            price_per_unit=0.10,
            total_price=0.00,
            status="started",
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            unit_type="page"
        )


def test_price_validation():
    """
    Test price_per_unit and total_price must be >= 0.
    """
    now = datetime.now(timezone.utc)

    # Valid: prices = 0
    txn = TranslationTransactionListItem(
        _id="68fe1edeac2359ccbc6b05b2",
        transaction_id="TXN-FREE",
        user_id="user@example.com",
        documents=[
            TranslationDocumentSchema(
                file_name="free.pdf",
                file_size=1000,
                original_url="https://docs.google.com/document/d/free/edit"
            )
        ],
        source_language="en",
        target_language="fr",
        units_count=10,
        price_per_unit=0.0,
        total_price=0.0,
        status="started",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        unit_type="page"
    )
    assert txn.price_per_unit == 0.0
    assert txn.total_price == 0.0

    # Invalid: negative price_per_unit
    with pytest.raises(ValidationError):
        TranslationTransactionListItem(
            _id="68fe1edeac2359ccbc6b05b2",
            transaction_id="TXN-NEG-PRICE",
            user_id="user@example.com",
            documents=[
                TranslationDocumentSchema(
                    file_name="neg.pdf",
                    file_size=1000,
                    original_url="https://docs.google.com/document/d/neg/edit"
                )
            ],
            source_language="en",
            target_language="fr",
            units_count=10,
            price_per_unit=-0.10,
            total_price=1.00,
            status="started",
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            unit_type="page"
        )
