"""
INTEGRATION TESTS FOR SUBMIT SERVICE WITH REAL DATABASE

These tests verify the SubmitService methods work correctly with
the real translation_test database. Tests the internal service logic
without going through the HTTP layer.

Test Database: translation_test (separate from production)
Uses: Real MongoDB connection via Motor
"""

import pytest
import pytest_asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from motor.motor_asyncio import AsyncIOMotorClient

from app.services.submit_service import SubmitService


# ============================================================================
# Test Configuration
# ============================================================================

TEST_MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation"
TEST_DATABASE_NAME = "translation_test"


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def test_db():
    """
    Provide a connection to the test database (translation_test).
    """
    mongo_client = AsyncIOMotorClient(TEST_MONGODB_URI, serverSelectionTimeoutMS=5000)
    test_database = mongo_client[TEST_DATABASE_NAME]

    # Verify connection
    try:
        await mongo_client.admin.command('ping')
    except Exception as e:
        pytest.skip(f"Cannot connect to test database: {e}")

    yield test_database

    # Cleanup: Close connection
    mongo_client.close()


@pytest_asyncio.fixture(scope="function")
async def test_enterprise_transaction(test_db):
    """
    Create a test enterprise transaction in translation_transactions collection.
    Automatically cleaned up after test.
    """
    collection = test_db.translation_transactions

    transaction_id = f"TXN-SUBMIT-TEST-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "company_name": "Submit Test Corp",
        "user_id": "submit_test@testcorp.com",
        "user_name": "Submit Test User",
        "status": "processing",
        "source_language": "en",
        "target_language": "es",
        "documents": [
            {
                "file_name": "submit_report.pdf",
                "file_size": 524288,
                "original_url": "https://drive.google.com/file/d/submit_orig_1/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None
            },
            {
                "file_name": "submit_summary.docx",
                "file_size": 262144,
                "original_url": "https://drive.google.com/file/d/submit_orig_2/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None
            }
        ],
        "total_documents": 2,
        "completed_documents": 0,
        "batch_email_sent": False,
        "created_at": now,
        "updated_at": now
    }

    await collection.insert_one(transaction_doc)
    yield transaction_doc

    # Cleanup
    await collection.delete_one({"transaction_id": transaction_id})


@pytest_asyncio.fixture(scope="function")
async def test_individual_transaction(test_db):
    """
    Create a test individual transaction in user_transactions collection.
    Automatically cleaned up after test.
    """
    collection = test_db.user_transactions

    transaction_id = f"TXN-IND-SUBMIT-{uuid.uuid4().hex[:8].upper()}"
    square_txn_id = f"SQR-SUBMIT-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    transaction_doc = {
        "transaction_id": transaction_id,
        "stripe_checkout_session_id": square_txn_id,
        "user_id": "individual_submit@example.com",
        "user_name": "Jane Submit Test",
        "status": "processing",
        "source_language": "fr",
        "target_language": "en",
        "documents": [
            {
                "file_name": "submit_passport.pdf",
                "file_size": 131072,
                "original_url": "https://drive.google.com/file/d/submit_passport_orig/view",
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": now,
                "translated_at": None
            }
        ],
        "total_documents": 1,
        "completed_documents": 0,
        "batch_email_sent": False,
        "created_at": now,
        "updated_at": now
    }

    await collection.insert_one(transaction_doc)
    yield transaction_doc

    # Cleanup
    await collection.delete_one({"transaction_id": transaction_id})


@pytest_asyncio.fixture(scope="function")
async def submit_service_instance():
    """
    Create SubmitService instance and connect to database.
    """
    from app.database.mongodb import database
    await database.connect()
    return SubmitService()


# ============================================================================
# Test Cases - Enterprise Submissions
# ============================================================================

class TestSubmitServiceEnterpriseIntegration:
    """Integration tests for enterprise submissions using real database."""

    @pytest.mark.asyncio
    async def test_process_submission_enterprise_success(
        self, submit_service_instance, test_enterprise_transaction, test_db
    ):
        """
        Test successful enterprise submission with real database.

        Verifies:
        - Database is updated with translated_url
        - completed_documents counter is incremented
        - Response includes correct transaction details
        - Email sending is mocked (we test email separately)
        """
        service = submit_service_instance
        transaction_id = test_enterprise_transaction["transaction_id"]
        file_url = "https://drive.google.com/file/d/submit_trans_1/view"

        # Mock email service (external dependency)
        mock_email_result = Mock()
        mock_email_result.success = True
        mock_email_result.error = None
        mock_email_result.message = "Email sent"
        mock_email_result.recipient = "submit_test@testcorp.com"

        with patch('app.services.submit_service.email_service.send_translation_notification') as mock_email:
            mock_email.return_value = mock_email_result

            result = await service.process_submission(
                file_name="submit_report.pdf",
                file_url=file_url,
                user_email="submit_test@testcorp.com",
                company_name="Submit Test Corp",
                transaction_id=transaction_id
            )

        # Verify result
        assert result["status"] == "success"
        assert result["transaction_id"] == transaction_id
        assert result["all_documents_complete"] is False  # Only 1 of 2 done
        assert result["completed_documents"] == 1
        assert result["total_documents"] == 2

        # Verify database state
        collection = test_db.translation_transactions
        updated = await collection.find_one({"transaction_id": transaction_id})
        assert updated["completed_documents"] == 1
        assert updated["documents"][0]["translated_url"] == file_url

    @pytest.mark.asyncio
    async def test_process_submission_enterprise_all_complete(
        self, submit_service_instance, test_enterprise_transaction, test_db
    ):
        """
        Test enterprise submission when all documents complete.

        Verifies:
        - all_documents_complete is True
        - Email is sent when all complete
        - documents_count shows all translated documents
        """
        service = submit_service_instance
        transaction_id = test_enterprise_transaction["transaction_id"]

        mock_email_result = Mock()
        mock_email_result.success = True
        mock_email_result.error = None
        mock_email_result.message = "Email sent"
        mock_email_result.recipient = "submit_test@testcorp.com"

        with patch('app.services.submit_service.email_service.send_translation_notification') as mock_email:
            mock_email.return_value = mock_email_result

            # Submit first document
            await service.process_submission(
                file_name="submit_report.pdf",
                file_url="https://drive.google.com/file/d/t1/view",
                user_email="submit_test@testcorp.com",
                company_name="Submit Test Corp",
                transaction_id=transaction_id
            )

            # Submit second document
            result = await service.process_submission(
                file_name="submit_summary.docx",
                file_url="https://drive.google.com/file/d/t2/view",
                user_email="submit_test@testcorp.com",
                company_name="Submit Test Corp",
                transaction_id=transaction_id
            )

        # Verify completion
        assert result["status"] == "success"
        assert result["all_documents_complete"] is True
        assert result["completed_documents"] == 2
        assert result["documents_count"] == 2
        assert result["email_sent"] is True

        # Verify email was called with all documents
        mock_email.assert_called()
        call_args = mock_email.call_args
        documents_in_email = call_args.kwargs.get('documents', [])
        assert len(documents_in_email) == 2

    @pytest.mark.asyncio
    async def test_process_submission_enterprise_not_found(
        self, submit_service_instance
    ):
        """
        Test submission when enterprise transaction doesn't exist.
        """
        service = submit_service_instance

        result = await service.process_submission(
            file_name="test.pdf",
            file_url="https://drive.google.com/file/d/test/view",
            user_email="test@test.com",
            company_name="Test Corp",
            transaction_id="TXN-SUBMIT-NOTFOUND-999"
        )

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()
        assert result["email_sent"] is False


# ============================================================================
# Test Cases - Individual Submissions
# ============================================================================

class TestSubmitServiceIndividualIntegration:
    """Integration tests for individual submissions using real database."""

    @pytest.mark.asyncio
    async def test_process_submission_individual_success(
        self, submit_service_instance, test_individual_transaction, test_db
    ):
        """
        Test successful individual submission with real database.

        Verifies:
        - Database (user_transactions) is updated
        - Correct routing to individual collection
        - Email sent when complete (single document)
        """
        service = submit_service_instance
        transaction_id = test_individual_transaction["transaction_id"]
        file_url = "https://drive.google.com/file/d/submit_passport_trans/view"

        mock_email_result = Mock()
        mock_email_result.success = True
        mock_email_result.error = None
        mock_email_result.message = "Email sent"
        mock_email_result.recipient = "individual_submit@example.com"

        with patch('app.services.submit_service.email_service.send_translation_notification') as mock_email:
            mock_email.return_value = mock_email_result

            result = await service.process_submission(
                file_name="submit_passport.pdf",
                file_url=file_url,
                user_email="individual_submit@example.com",
                company_name="Ind",  # Individual customer
                transaction_id=transaction_id
            )

        # Verify result
        assert result["status"] == "success"
        assert result["all_documents_complete"] is True
        assert result["email_sent"] is True

        # Verify database state
        collection = test_db.user_transactions
        updated = await collection.find_one({"transaction_id": transaction_id})
        assert updated["completed_documents"] == 1
        assert updated["documents"][0]["translated_url"] == file_url


# ============================================================================
# Test Cases - Email Failure Handling
# ============================================================================

class TestSubmitServiceEmailHandlingIntegration:
    """Integration tests for email failure handling."""

    @pytest.mark.asyncio
    async def test_submission_success_even_if_email_fails(
        self, submit_service_instance, test_enterprise_transaction, test_db
    ):
        """
        Test that submission succeeds even if email fails.

        Verifies:
        - Database update succeeds
        - status is "success"
        - email_sent is False
        - email_error contains error message
        """
        service = submit_service_instance
        transaction_id = test_enterprise_transaction["transaction_id"]

        mock_email_result = Mock()
        mock_email_result.success = False
        mock_email_result.error = "SMTP connection failed"
        mock_email_result.message = None
        mock_email_result.recipient = "submit_test@testcorp.com"

        with patch('app.services.submit_service.email_service.send_translation_notification') as mock_email:
            mock_email.return_value = mock_email_result

            # Submit both documents so email should be attempted
            await service.process_submission(
                file_name="submit_report.pdf",
                file_url="https://drive.google.com/t1",
                user_email="submit_test@testcorp.com",
                company_name="Submit Test Corp",
                transaction_id=transaction_id
            )

            result = await service.process_submission(
                file_name="submit_summary.docx",
                file_url="https://drive.google.com/t2",
                user_email="submit_test@testcorp.com",
                company_name="Submit Test Corp",
                transaction_id=transaction_id
            )

        # Submission succeeded despite email failure
        assert result["status"] == "success"
        assert result["email_sent"] is False
        assert result["email_error"] == "SMTP connection failed"

        # Database was still updated
        collection = test_db.translation_transactions
        updated = await collection.find_one({"transaction_id": transaction_id})
        assert all(doc["translated_url"] for doc in updated["documents"])


# ============================================================================
# Test Cases - User Name Extraction
# ============================================================================

class TestSubmitServiceUserNameExtraction:
    """Tests for _extract_user_name method."""

    def test_extract_user_name_from_transaction(self):
        """Test extracting user name from transaction with user_name field."""
        service = SubmitService()

        transaction = {
            "user_name": "John Doe",
            "user_id": "john.doe@example.com"
        }

        result = service._extract_user_name(transaction, "john.doe@example.com")
        assert result == "John Doe"

    def test_extract_user_name_from_email(self):
        """Test extracting user name from email when user_name not present."""
        service = SubmitService()

        transaction = {"user_id": "jane_smith@example.com"}

        result = service._extract_user_name(transaction, "jane_smith@example.com")
        assert result == "Jane Smith"

    def test_extract_user_name_fallback(self):
        """Test fallback when extraction fails with simple string.

        When a simple string (no @ symbol) is provided:
        - "invalid" splits on @ → ["invalid"]
        - Takes first part → "invalid"
        - Capitalizes → "Invalid"
        """
        service = SubmitService()

        transaction = {}

        # Simple string "invalid" is parsed as a name and capitalized
        result = service._extract_user_name(transaction, "invalid")
        assert result == "Invalid"
