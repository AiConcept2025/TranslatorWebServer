"""
Transaction update service for handling document metadata updates.

This service manages updates to translation_transactions (Enterprise) and
user_transactions (Individual) collections when translated files are ready.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.database.mongodb import database

logger = logging.getLogger(__name__)


class TransactionUpdateService:
    """Service for updating transaction documents with translation metadata."""

    async def update_enterprise_transaction(
        self,
        transaction_id: str,
        file_name: str,
        file_url: str
    ) -> Dict[str, Any]:
        """
        Update enterprise transaction in translation_transactions collection.

        Args:
            transaction_id: Transaction ID (e.g., "TXN-ABC123")
            file_name: Name of the translated file
            file_url: Google Drive URL of translated file

        Returns:
            dict: Update result with transaction details
        """
        logger.info(f"Updating enterprise transaction {transaction_id} for file {file_name}")

        try:
            collection = database.translation_transactions

            if collection is None:
                logger.error("Database collection not available")
                return {
                    "success": False,
                    "error": "Database connection error",
                    "transaction_id": transaction_id
                }

            # Find the transaction
            transaction = await collection.find_one({"transaction_id": transaction_id})

            if not transaction:
                logger.error(f"Transaction not found: {transaction_id}")
                return {
                    "success": False,
                    "error": f"Transaction {transaction_id} not found",
                    "transaction_id": transaction_id
                }

            # Find matching document in array
            document_index = None
            for idx, doc in enumerate(transaction.get("documents", [])):
                if doc.get("document_name") == file_name:
                    document_index = idx
                    break

            if document_index is None:
                logger.error(f"Document {file_name} not found in transaction {transaction_id}")
                return {
                    "success": False,
                    "error": f"Document {file_name} not found in transaction",
                    "transaction_id": transaction_id
                }

            # Generate translated_name (remove language suffix if present)
            translated_name = self._generate_translated_name(file_name)

            # Update the specific document in the array
            update_result = await collection.update_one(
                {
                    "transaction_id": transaction_id,
                    f"documents.{document_index}.document_name": file_name
                },
                {
                    "$set": {
                        f"documents.{document_index}.translated_url": file_url,
                        f"documents.{document_index}.translated_name": translated_name,
                        f"documents.{document_index}.translated_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            if update_result.modified_count > 0:
                logger.info(f"Successfully updated document {file_name} in transaction {transaction_id}")

                # Get updated transaction for email
                updated_transaction = await collection.find_one({"transaction_id": transaction_id})

                return {
                    "success": True,
                    "transaction_id": transaction_id,
                    "document_name": file_name,
                    "translated_url": file_url,
                    "translated_name": translated_name,
                    "transaction": updated_transaction
                }
            else:
                logger.warning(f"No modifications made to transaction {transaction_id}")
                return {
                    "success": False,
                    "error": "Document update failed - no modifications made",
                    "transaction_id": transaction_id
                }

        except Exception as e:
            logger.error(f"Error updating enterprise transaction {transaction_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "transaction_id": transaction_id
            }

    async def update_individual_transaction(
        self,
        transaction_id: str,
        file_name: str,
        file_url: str
    ) -> Dict[str, Any]:
        """
        Update individual transaction in user_transactions collection.

        Args:
            transaction_id: Transaction ID (e.g., "TXN-XYZ789")
            file_name: Name of the translated file
            file_url: Google Drive URL of translated file

        Returns:
            dict: Update result with transaction details
        """
        logger.info(f"Updating individual transaction {transaction_id} for file {file_name}")

        try:
            collection = database.user_transactions

            if collection is None:
                logger.error("Database collection not available")
                return {
                    "success": False,
                    "error": "Database connection error",
                    "transaction_id": transaction_id
                }

            # Find the transaction
            transaction = await collection.find_one({"transaction_id": transaction_id})

            if not transaction:
                logger.error(f"Transaction not found: {transaction_id}")
                return {
                    "success": False,
                    "error": f"Transaction {transaction_id} not found",
                    "transaction_id": transaction_id
                }

            # Find matching document in array
            document_index = None
            for idx, doc in enumerate(transaction.get("documents", [])):
                if doc.get("document_name") == file_name:
                    document_index = idx
                    break

            if document_index is None:
                logger.error(f"Document {file_name} not found in transaction {transaction_id}")
                return {
                    "success": False,
                    "error": f"Document {file_name} not found in transaction",
                    "transaction_id": transaction_id
                }

            # Generate translated_name
            translated_name = self._generate_translated_name(file_name)

            # Update the specific document in the array
            update_result = await collection.update_one(
                {
                    "transaction_id": transaction_id,
                    f"documents.{document_index}.document_name": file_name
                },
                {
                    "$set": {
                        f"documents.{document_index}.translated_url": file_url,
                        f"documents.{document_index}.translated_name": translated_name,
                        f"documents.{document_index}.translated_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            if update_result.modified_count > 0:
                logger.info(f"Successfully updated document {file_name} in transaction {transaction_id}")

                # Get updated transaction for email
                updated_transaction = await collection.find_one({"transaction_id": transaction_id})

                return {
                    "success": True,
                    "transaction_id": transaction_id,
                    "document_name": file_name,
                    "translated_url": file_url,
                    "translated_name": translated_name,
                    "transaction": updated_transaction
                }
            else:
                logger.warning(f"No modifications made to transaction {transaction_id}")
                return {
                    "success": False,
                    "error": "Document update failed - no modifications made",
                    "transaction_id": transaction_id
                }

        except Exception as e:
            logger.error(f"Error updating individual transaction {transaction_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Database error: {str(e)}",
                "transaction_id": transaction_id
            }

    def _generate_translated_name(self, file_name: str) -> str:
        """
        Generate translated file name.

        Examples:
            "report.pdf" -> "report_translated.pdf"
            "document_en.docx" -> "document_translated.docx"

        Args:
            file_name: Original file name

        Returns:
            str: Translated file name
        """
        # Split name and extension
        if '.' in file_name:
            name_part, ext = file_name.rsplit('.', 1)
            # Remove language code if present (e.g., _en, _es)
            if '_' in name_part:
                parts = name_part.split('_')
                # Check if last part looks like a language code (2 chars)
                if len(parts[-1]) == 2:
                    name_part = '_'.join(parts[:-1])
            return f"{name_part}_translated.{ext}"
        else:
            return f"{file_name}_translated"

    async def check_transaction_complete(
        self,
        transaction_id: str,
        is_enterprise: bool
    ) -> bool:
        """
        Check if all documents in transaction have been translated.

        Args:
            transaction_id: Transaction ID
            is_enterprise: True for enterprise, False for individual

        Returns:
            bool: True if all documents have translated_url
        """
        collection = (database.translation_transactions if is_enterprise
                     else database.user_transactions)

        if collection is None:
            logger.error("Database collection not available")
            return False

        transaction = await collection.find_one({"transaction_id": transaction_id})

        if not transaction:
            return False

        documents = transaction.get("documents", [])
        if not documents:
            return False

        # Check if all documents have translated_url
        all_translated = all(
            doc.get("translated_url") for doc in documents
        )

        # Update transaction status if complete
        if all_translated:
            await collection.update_one(
                {"transaction_id": transaction_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logger.info(f"Transaction {transaction_id} marked as completed")

        return all_translated


# Create singleton instance
transaction_update_service = TransactionUpdateService()
