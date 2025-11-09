"""
Debug script for email batching - tracks counter state during multi-document transactions.

This script helps diagnose the "two emails sent separately" issue by:
1. Creating a test transaction with 2 documents
2. Simulating the submission of document 1, then document 2
3. Logging counter values at each step
4. Showing when email gates pass/fail

Run with: python test_email_batching_debug.py
"""

import asyncio
import logging
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncMotorClient
import sys
import os

# Add server module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from app.database.mongodb import database
from app.services.transaction_update_service import transaction_update_service
from app.services.submit_service import submit_service

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_email_batching():
    """Test email batching with detailed counter logging."""

    logger.info("=" * 80)
    logger.info("EMAIL BATCHING DEBUG TEST")
    logger.info("=" * 80)

    try:
        # Initialize database connection
        logger.info("Connecting to MongoDB...")
        await database.connect()

        # Create test transaction with 2 documents
        transaction_id = f"TEST-EMAIL-BATCH-{datetime.now(timezone.utc).timestamp()}"
        collection = database.translation_transactions

        logger.info(f"\nCreating test transaction: {transaction_id}")
        logger.info("=" * 80)

        test_transaction = {
            "transaction_id": transaction_id,
            "user_id": "test@example.com",
            "company_name": "TestCorp",
            "user_name": "Test User",
            "source_language": "en",
            "target_language": "fr",
            "status": "pending",
            # NOTE: total_documents and completed_documents NOT initialized
            # They should be auto-initialized on first document completion
            "documents": [
                {
                    "file_name": "NuDOC_API_Role_Enforcement_Project_Plan.docx",
                    "file_size": 1024,
                    "original_url": "https://example.com/doc1.docx",
                    "translated_url": None,
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": datetime.now(timezone.utc)
                },
                {
                    "file_name": "NuVIZ_Cable_Management_Market_Comparison_Report.pdf",
                    "file_size": 2048,
                    "original_url": "https://example.com/doc2.pdf",
                    "translated_url": None,
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": datetime.now(timezone.utc)
                }
            ],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await collection.insert_one(test_transaction)
        logger.info(f"Test transaction created with ID: {result.inserted_id}")

        # Fetch and log initial state
        txn = await collection.find_one({"transaction_id": transaction_id})
        logger.info(f"\nINITIAL STATE:")
        logger.info(f"  total_documents: {txn.get('total_documents')}")
        logger.info(f"  completed_documents: {txn.get('completed_documents')}")
        logger.info(f"  documents count: {len(txn.get('documents', []))}")
        logger.info(f"  Document 1 translated_url: {txn['documents'][0].get('translated_url')}")
        logger.info(f"  Document 2 translated_url: {txn['documents'][1].get('translated_url')}")

        # STEP 1: Submit Document 1
        logger.info("\n" + "=" * 80)
        logger.info("STEP 1: Submitting Document 1")
        logger.info("=" * 80)

        result1 = await submit_service.process_submission(
            file_name="NuDOC_API_Role_Enforcement_Project_Plan_translated.docx",
            file_url="https://drive.google.com/file/d/doc1-translated",
            user_email="test@example.com",
            company_name="TestCorp",
            transaction_id=transaction_id
        )

        logger.info(f"\nDocument 1 Submission Result:")
        logger.info(f"  Status: {result1.get('status')}")
        logger.info(f"  Message: {result1.get('message')}")
        logger.info(f"  Email Sent: {result1.get('email_sent')}")
        logger.info(f"  Completed Documents: {result1.get('completed_documents')}")
        logger.info(f"  Total Documents: {result1.get('total_documents')}")
        logger.info(f"  All Documents Complete: {result1.get('all_documents_complete')}")

        # Check state after document 1
        txn = await collection.find_one({"transaction_id": transaction_id})
        logger.info(f"\nSTATE AFTER DOCUMENT 1:")
        logger.info(f"  total_documents: {txn.get('total_documents')}")
        logger.info(f"  completed_documents: {txn.get('completed_documents')}")
        logger.info(f"  Document 1 translated_url: {bool(txn['documents'][0].get('translated_url'))}")
        logger.info(f"  Document 2 translated_url: {bool(txn['documents'][1].get('translated_url'))}")

        # STEP 2: Submit Document 2
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Submitting Document 2")
        logger.info("=" * 80)

        result2 = await submit_service.process_submission(
            file_name="NuVIZ_Cable_Management_Market_Comparison_Report_translated.docx",
            file_url="https://drive.google.com/file/d/doc2-translated",
            user_email="test@example.com",
            company_name="TestCorp",
            transaction_id=transaction_id
        )

        logger.info(f"\nDocument 2 Submission Result:")
        logger.info(f"  Status: {result2.get('status')}")
        logger.info(f"  Message: {result2.get('message')}")
        logger.info(f"  Email Sent: {result2.get('email_sent')}")
        logger.info(f"  Completed Documents: {result2.get('completed_documents')}")
        logger.info(f"  Total Documents: {result2.get('total_documents')}")
        logger.info(f"  All Documents Complete: {result2.get('all_documents_complete')}")

        # Check state after document 2
        txn = await collection.find_one({"transaction_id": transaction_id})
        logger.info(f"\nSTATE AFTER DOCUMENT 2:")
        logger.info(f"  total_documents: {txn.get('total_documents')}")
        logger.info(f"  completed_documents: {txn.get('completed_documents')}")
        logger.info(f"  Document 1 translated_url: {bool(txn['documents'][0].get('translated_url'))}")
        logger.info(f"  Document 2 translated_url: {bool(txn['documents'][1].get('translated_url'))}")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("TEST SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Document 1 Email Sent: {result1.get('email_sent')} (SHOULD BE False)")
        logger.info(f"Document 2 Email Sent: {result2.get('email_sent')} (SHOULD BE True)")

        if result1.get('email_sent') == False and result2.get('email_sent') == True:
            logger.info("\n✅ TEST PASSED: Email batching working correctly!")
        else:
            logger.error("\n❌ TEST FAILED: Email batching not working as expected!")
            if result1.get('email_sent') == True:
                logger.error("   - Document 1 incorrectly sent email (should wait for document 2)")
            if result2.get('email_sent') == False:
                logger.error("   - Document 2 did not send email (should send when all complete)")

        # Cleanup
        logger.info(f"\nCleaning up test data...")
        await collection.delete_one({"transaction_id": transaction_id})
        logger.info("Test transaction deleted")

    except Exception as e:
        logger.error(f"Test error: {e}", exc_info=True)

    finally:
        await database.disconnect()
        logger.info("\nDatabase disconnected")


if __name__ == "__main__":
    asyncio.run(test_email_batching())
