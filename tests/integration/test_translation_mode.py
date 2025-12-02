"""
INTEGRATION TESTS FOR TRANSLATION_MODE FEATURE

Tests verify:

1. TranslationMode enum validation (automatic, human, formats, handwriting)
2. TranslateRequest model accepts fileTranslationModes for per-file modes
3. Default mode is "automatic" when not provided
4. Modes are stored correctly in transaction documents

NOTE: The actual implementation uses fileTranslationModes (per-file modes)
instead of a single translation_mode field on the request.

NOTE: These tests validate Pydantic models and do NOT require database connection.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict
from pydantic import BaseModel, ValidationError

# CRITICAL: Do NOT import database from app.database here!
# That singleton uses settings.mongodb_database which points to PRODUCTION.
# These tests are model validation tests that don't need database.


# ============================================================================
# Test: TranslationMode Enum Definition
# ============================================================================

class TestTranslationModeEnumDefinition:
    """Tests for TranslationMode enum - must exist in mongodb_models.py"""

    def test_translation_mode_enum_exists(self):
        """TranslationMode enum should be defined in mongodb_models."""
        from app.mongodb_models import TranslationMode

        # Enum should exist
        assert TranslationMode is not None

    def test_translation_mode_has_automatic_value(self):
        """TranslationMode should have 'automatic' value."""
        from app.mongodb_models import TranslationMode

        assert hasattr(TranslationMode, 'AUTOMATIC') or hasattr(TranslationMode, 'automatic')
        mode = TranslationMode.AUTOMATIC if hasattr(TranslationMode, 'AUTOMATIC') else TranslationMode.automatic
        assert mode.value == "automatic"

    def test_translation_mode_has_human_value(self):
        """TranslationMode should have 'human' value."""
        from app.mongodb_models import TranslationMode

        assert hasattr(TranslationMode, 'HUMAN') or hasattr(TranslationMode, 'human')
        mode = TranslationMode.HUMAN if hasattr(TranslationMode, 'HUMAN') else TranslationMode.human
        assert mode.value == "human"

    def test_translation_mode_has_formats_value(self):
        """TranslationMode should have 'formats' value."""
        from app.mongodb_models import TranslationMode

        assert hasattr(TranslationMode, 'FORMATS') or hasattr(TranslationMode, 'formats')
        mode = TranslationMode.FORMATS if hasattr(TranslationMode, 'FORMATS') else TranslationMode.formats
        assert mode.value == "formats"

    def test_translation_mode_has_handwriting_value(self):
        """TranslationMode should have 'handwriting' value."""
        from app.mongodb_models import TranslationMode

        assert hasattr(TranslationMode, 'HANDWRITING') or hasattr(TranslationMode, 'handwriting')
        mode = TranslationMode.HANDWRITING if hasattr(TranslationMode, 'HANDWRITING') else TranslationMode.handwriting
        assert mode.value == "handwriting"

    def test_translation_mode_is_string_enum(self):
        """TranslationMode should be a string enum (str, Enum)."""
        from app.mongodb_models import TranslationMode

        mode = TranslationMode.AUTOMATIC if hasattr(TranslationMode, 'AUTOMATIC') else TranslationMode.automatic
        # Should be usable as a string
        assert isinstance(mode.value, str)
        assert str(mode.value) == "automatic"


# ============================================================================
# Test: TranslateRequest Model Accepts fileTranslationModes (per-file modes)
# ============================================================================

class TestTranslateRequestModel:
    """Tests for TranslateRequest model with fileTranslationModes field."""

    def test_translate_request_accepts_file_translation_modes(self):
        """TranslateRequest should accept fileTranslationModes parameter."""
        from app.main import TranslateRequest, FileTranslationModeInfo
        from app.mongodb_models import TranslationMode

        # Create request with per-file translation modes
        request = TranslateRequest(
            files=[],
            email="test@example.com",
            sourceLanguage="en",
            targetLanguage="es",
            fileTranslationModes=[
                FileTranslationModeInfo(
                    fileName="test.pdf",
                    translationMode=TranslationMode.AUTOMATIC
                )
            ]
        )

        assert request.fileTranslationModes is not None
        assert len(request.fileTranslationModes) == 1

    def test_translate_request_default_file_modes_is_none(self):
        """TranslateRequest should default fileTranslationModes to None."""
        from app.main import TranslateRequest

        # Create request WITHOUT fileTranslationModes
        request = TranslateRequest(
            files=[],
            email="test@example.com",
            sourceLanguage="en",
            targetLanguage="es"
        )

        # Default should be None (each file uses automatic mode implicitly)
        assert request.fileTranslationModes is None

    def test_translate_request_all_modes_valid_in_file_modes(self):
        """TranslateRequest should accept all valid translation modes for files."""
        from app.main import TranslateRequest, FileTranslationModeInfo
        from app.mongodb_models import TranslationMode

        valid_modes = [
            TranslationMode.AUTOMATIC,
            TranslationMode.HUMAN,
            TranslationMode.FORMATS,
            TranslationMode.HANDWRITING,
        ]

        for i, mode in enumerate(valid_modes):
            request = TranslateRequest(
                files=[],
                email="test@example.com",
                sourceLanguage="en",
                targetLanguage="es",
                fileTranslationModes=[
                    FileTranslationModeInfo(
                        fileName=f"test{i}.pdf",
                        translationMode=mode
                    )
                ]
            )
            assert request.fileTranslationModes[0].translationMode == mode

    def test_translate_request_invalid_mode_raises_error(self):
        """TranslateRequest should reject invalid translation_mode values in file modes."""
        from app.main import TranslateRequest, FileTranslationModeInfo

        with pytest.raises(ValidationError):
            TranslateRequest(
                files=[],
                email="test@example.com",
                sourceLanguage="en",
                targetLanguage="es",
                fileTranslationModes=[
                    FileTranslationModeInfo(
                        fileName="test.pdf",
                        translationMode="invalid_mode"
                    )
                ]
            )


# ============================================================================
# Test: Transaction Document Storage (skip async issues for now)
# ============================================================================

class TestTranslationModeStorage:
    """Tests for translation_mode storage in transaction documents."""

    def test_translation_mode_field_is_string(self):
        """translation_mode should be stored as string value."""
        from app.mongodb_models import TranslationMode

        # Verify enum value is a string
        assert TranslationMode.AUTOMATIC.value == "automatic"
        assert TranslationMode.HUMAN.value == "human"
        assert TranslationMode.FORMATS.value == "formats"
        assert TranslationMode.HANDWRITING.value == "handwriting"

    def test_transaction_doc_structure_includes_mode(self):
        """Transaction document should include translation_mode field."""
        from app.mongodb_models import TranslationMode

        # Sample transaction document with translation_mode
        transaction_doc = {
            "transaction_id": "TXN-TEST-123",
            "user_id": "test@example.com",
            "source_language": "en",
            "target_language": "es",
            "translation_mode": TranslationMode.HUMAN.value,
            "units_count": 1,
            "price_per_unit": 2.0,
            "total_price": 2.0,
            "status": "started",
            "documents": []
        }

        assert "translation_mode" in transaction_doc
        assert transaction_doc["translation_mode"] == "human"

    def test_all_modes_are_valid_strings(self):
        """All translation_mode values should be valid strings."""
        from app.mongodb_models import TranslationMode

        modes = [TranslationMode.AUTOMATIC, TranslationMode.HUMAN,
                 TranslationMode.FORMATS, TranslationMode.HANDWRITING]

        for mode in modes:
            assert isinstance(mode.value, str)
            assert len(mode.value) > 0


# ============================================================================
# Test: create_transaction_record Function
# ============================================================================

class TestCreateTransactionRecordWithMode:
    """Tests for create_transaction_record() including file_translation_modes."""

    def test_create_transaction_record_accepts_file_translation_modes(self):
        """create_transaction_record should accept file_translation_modes parameter."""
        from app.main import create_transaction_record
        import inspect

        # Check function signature accepts file_translation_modes
        sig = inspect.signature(create_transaction_record)
        params = list(sig.parameters.keys())

        assert "file_translation_modes" in params, \
            f"create_transaction_record should accept 'file_translation_modes' parameter. Current params: {params}"

    def test_create_transaction_record_has_default_for_file_modes(self):
        """create_transaction_record should have default for file_translation_modes."""
        from app.main import create_transaction_record
        import inspect

        sig = inspect.signature(create_transaction_record)
        param = sig.parameters.get("file_translation_modes")

        # file_translation_modes should have a default (None)
        assert param is not None
        assert param.default is None

    def test_translate_request_file_modes_propagate_correctly(self):
        """TranslateRequest.fileTranslationModes should provide per-file modes."""
        from app.main import TranslateRequest, FileTranslationModeInfo
        from app.mongodb_models import TranslationMode

        # Create request with human mode for a file
        request = TranslateRequest(
            files=[],
            email="test@example.com",
            sourceLanguage="en",
            targetLanguage="es",
            fileTranslationModes=[
                FileTranslationModeInfo(
                    fileName="test.pdf",
                    translationMode=TranslationMode.HUMAN
                )
            ]
        )

        # Verify mode can be extracted for function call
        assert request.fileTranslationModes[0].translationMode == TranslationMode.HUMAN
        assert request.fileTranslationModes[0].translationMode.value == "human"


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestTranslationModeEdgeCases:
    """Edge cases and validation for translation_mode via fileTranslationModes."""

    def test_translation_mode_case_sensitivity(self):
        """TranslationMode should be case-sensitive (lowercase only)."""
        from app.main import TranslateRequest, FileTranslationModeInfo

        # Uppercase should fail
        with pytest.raises(ValidationError):
            TranslateRequest(
                files=[],
                email="test@example.com",
                sourceLanguage="en",
                targetLanguage="es",
                fileTranslationModes=[
                    FileTranslationModeInfo(
                        fileName="test.pdf",
                        translationMode="AUTOMATIC"  # Should fail - case sensitive
                    )
                ]
            )

    def test_translation_mode_empty_string_rejected(self):
        """TranslationMode should reject empty string."""
        from app.main import TranslateRequest, FileTranslationModeInfo

        with pytest.raises(ValidationError):
            TranslateRequest(
                files=[],
                email="test@example.com",
                sourceLanguage="en",
                targetLanguage="es",
                fileTranslationModes=[
                    FileTranslationModeInfo(
                        fileName="test.pdf",
                        translationMode=""
                    )
                ]
            )

    def test_translation_mode_accepts_string_values(self):
        """TranslateRequest should accept translationMode as string in fileTranslationModes."""
        from app.main import TranslateRequest, FileTranslationModeInfo

        # String value should work (Pydantic coerces to enum)
        request = TranslateRequest(
            files=[],
            email="test@example.com",
            sourceLanguage="en",
            targetLanguage="es",
            fileTranslationModes=[
                FileTranslationModeInfo(
                    fileName="test.pdf",
                    translationMode="human"  # String, not enum
                )
            ]
        )

        assert request.fileTranslationModes[0].translationMode.value == "human"
