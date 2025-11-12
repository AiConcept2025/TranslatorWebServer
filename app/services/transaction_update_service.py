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


def normalize_filename_for_comparison(filename: str) -> str:
    """
    Normalize filename for extension-agnostic comparison.

    Removes file extension and ALL _translated suffixes (handles multiple),
    lowercases for case-insensitive matching. This allows matching files that
    differ only in extension (e.g., original PDF vs translated DOCX) and handles
    cases where GoogleTranslator re-processes already-translated files.

    Examples:
        "report_translated.docx" → "report"
        "report.pdf" → "report"
        "report_translated_translated.docx" → "report"  ← Fixed multiple suffixes
        "My.Document.translated.docx" → "my.document"
        "file.backup.pdf" → "file.backup"
        "NuVIZ_Report_translated.docx" → "nuviz_report"
        "NuVIZ_Report_translated_translated_translated.pdf" → "nuviz_report"

    Args:
        filename: Full filename with extension

    Returns:
        Normalized name without extension or suffix, lowercased
    """
    import os

    # Remove extension (handles multiple dots correctly)
    name_without_ext = os.path.splitext(filename)[0]

    # Remove ALL _translated suffixes (handles multiple re-translations)
    # Loop until no more _translated suffixes remain
    while name_without_ext.lower().endswith('_translated'):
        name_without_ext = name_without_ext[:-11]  # len('_translated') = 11

    # Lowercase for case-insensitive comparison
    return name_without_ext.lower()


def generate_translated_filename(original_filename: str) -> str:
    """
    Generate translated filename by adding '_translated' suffix before extension.

    Args:
        original_filename: Original filename (e.g., "report.pdf" or "report_translated.pdf")

    Returns:
        Translated filename (e.g., "report_translated.pdf")

    Examples:
        "report.pdf" → "report_translated.pdf"
        "document.docx" → "document_translated.docx"
        "file_translated.pdf" → "file_translated.pdf" (idempotent - no double suffix)
        "My.Document.pdf" → "My.Document_translated.pdf"

    Note:
        This function is idempotent - calling it multiple times on same filename
        will not add multiple _translated suffixes.
    """
    import os

    # Split filename and extension
    base_name, extension = os.path.splitext(original_filename)

    # Check if already has _translated suffix (idempotency check)
    if base_name.endswith('_translated'):
        return original_filename

    # Add _translated suffix before extension
    return f"{base_name}_translated{extension}"


def normalize_filename_for_lookup(file_name: str) -> str:
    """
    DEPRECATED: Use normalize_filename_for_comparison instead.

    Normalize translated filename to match original database entry.

    Strips _translated suffix to match the original file_name stored during upload.
    The GoogleTranslator service adds "_translated" before the extension, but the
    database stores the original filename without this suffix.

    Examples:
        "report_translated.pdf" → "report.pdf"
        "Kevin questions[81]_translated.docx" → "Kevin questions[81].docx"
        "document.docx" → "document.docx" (no change if no suffix)

    Args:
        file_name: Filename with or without _translated suffix

    Returns:
        Normalized filename matching database file_name field
    """
    if "_translated." in file_name:
        return file_name.replace("_translated.", ".")
    return file_name


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
        logger.info("=" * 80)
        logger.info("TRANSACTION UPDATE SERVICE - Enterprise Transaction")
        logger.info("=" * 80)
        logger.info(f"Updating enterprise transaction {transaction_id} for file {file_name}")
        logger.debug(
            "Enterprise transaction update parameters",
            extra={
                "transaction_id": transaction_id,
                "file_name": file_name,
                "file_url": file_url,
                "collection": "translation_transactions"
            }
        )

        try:
            collection = database.translation_transactions

            if collection is None:
                logger.error(
                    "Database collection not available",
                    extra={
                        "collection": "translation_transactions",
                        "transaction_id": transaction_id
                    }
                )
                return {
                    "success": False,
                    "error": "Database connection error",
                    "transaction_id": transaction_id
                }

            # Find the transaction
            logger.debug(
                "DB QUERY - find_one",
                extra={
                    "collection": "translation_transactions",
                    "operation": "find_one",
                    "filter": {"transaction_id": transaction_id}
                }
            )
            logger.debug(f"Executing: db.translation_transactions.find_one({{'transaction_id': '{transaction_id}'}})")

            transaction = await collection.find_one({"transaction_id": transaction_id})

            logger.debug(
                f"DB QUERY RESULT - Transaction {'found' if transaction else 'not found'}",
                extra={
                    "transaction_id": transaction_id,
                    "found": bool(transaction),
                    "transaction_keys": list(transaction.keys()) if transaction else None
                }
            )

            if not transaction:
                logger.error(f"Transaction not found: {transaction_id}")
                return {
                    "success": False,
                    "error": f"Transaction {transaction_id} not found",
                    "transaction_id": transaction_id
                }

            # Get all documents for enhanced logging
            documents = transaction.get("documents", [])

            # Log transaction details with all document filenames
            logger.info(
                f"Transaction {transaction_id} found with {len(documents)} document(s)",
                extra={
                    "transaction_id": transaction_id,
                    "document_count": len(documents),
                    "documents": [
                        {
                            "index": idx,
                            "file_name": doc.get("file_name", "unknown"),
                            "document_name": doc.get("document_name", "unknown"),
                            "has_translated_url": bool(doc.get("translated_url")),
                            "normalized_name": normalize_filename_for_comparison(
                                doc.get("file_name", "")
                            )
                        }
                        for idx, doc in enumerate(documents)
                    ]
                }
            )

            # Normalize the submitted filename for extension-agnostic comparison
            # Example: "NuVIZ_Report_translated.docx" → "nuviz_report"
            #          "NuVIZ_Report.pdf" → "nuviz_report"
            # This allows matching even when extensions differ (PDF → DOCX conversion)
            search_normalized = normalize_filename_for_comparison(file_name)

            logger.info(
                f"Searching for document matching '{file_name}'",
                extra={
                    "transaction_id": transaction_id,
                    "search_file_name": file_name,
                    "search_normalized": search_normalized,
                    "comparison_method": "extension-agnostic (basename only)"
                }
            )

            # Enhanced diagnostic logging
            logger.info("=" * 80)
            logger.info("DOCUMENT LOOKUP - Starting Detailed Comparison")
            logger.info("=" * 80)
            logger.info(f"Incoming filename from webhook: '{file_name}'")
            logger.info(f"Transaction ID: {transaction_id}")
            logger.info(f"Search normalized (after removing '_translated'): '{search_normalized}'")

            # Count how many _translated suffixes are in the incoming filename
            translated_count = file_name.lower().count('_translated')
            logger.info(f"Number of '_translated' suffixes found: {translated_count}")
            if translated_count > 1:
                logger.warning(f"⚠️  MULTIPLE '_translated' SUFFIXES DETECTED! GoogleTranslator may have re-processed this file.")

            logger.info(f"\nTransaction has {len(documents)} document(s) in database:")
            for i, doc in enumerate(documents, 1):
                logger.info(f"  Document {i}:")
                logger.info(f"    file_name:          '{doc.get('file_name')}'")
                logger.info(f"    status:             {doc.get('status')}")
                logger.info(f"    has translated_url: {bool(doc.get('translated_url'))}")
                logger.info(f"    db_normalized:      '{normalize_filename_for_comparison(doc.get('file_name', ''))}'")

            logger.info(f"\nStarting filename comparison...")

            # Find matching document by comparing normalized names (without extension)
            document_index = None
            matched_db_filename = None
            comparison_details = []

            for idx, doc in enumerate(documents):
                db_filename = doc.get("file_name", "")
                db_normalized = normalize_filename_for_comparison(db_filename)

                # Track comparison for debugging
                is_match = db_normalized == search_normalized
                comparison_details.append({
                    "index": idx,
                    "db_filename": db_filename,
                    "db_normalized": db_normalized,
                    "search_normalized": search_normalized,
                    "match": is_match
                })

                if is_match:
                    document_index = idx
                    matched_db_filename = db_filename
                    break

            # Log detailed comparison results
            logger.info(
                f"Document lookup comparison results for '{file_name}'",
                extra={
                    "transaction_id": transaction_id,
                    "search_file_name": file_name,
                    "search_normalized": search_normalized,
                    "found_match": document_index is not None,
                    "matched_index": document_index,
                    "matched_db_filename": matched_db_filename,
                    "comparison_details": comparison_details
                }
            )

            if document_index is None:
                logger.error(
                    f"Document lookup FAILED - no match found for '{file_name}'",
                    extra={
                        "transaction_id": transaction_id,
                        "search_file_name": file_name,
                        "search_normalized": search_normalized,
                        "comparison_method": "extension-agnostic (basename only)",
                        "comparison_details": comparison_details,
                        "total_documents": len(documents),
                        "failure_reason": (
                            "No document in DB matches the normalized filename. "
                            "Check if file was uploaded with a different name or "
                            "if there's a typo in the webhook filename."
                        )
                    }
                )

                return {
                    "success": False,
                    "error": f"Document {file_name} not found in transaction",
                    "transaction_id": transaction_id
                }

            # Generate translated_name (remove language suffix if present)
            translated_name = self._generate_translated_name(file_name)
            logger.debug(f"Generated translated_name: {translated_name}")

            # Update the specific document in the array with IDEMPOTENCY guard
            # NOTE: We already found the correct document_index above by matching lookup_name,
            # so we only need transaction_id in the filter. Adding file_name here would cause
            # a mismatch because file_name contains "_translated" suffix but database stores
            # the original filename without this suffix.
            #
            # IDEMPOTENCY: Only update if translated_url is null (prevents duplicate webhook processing)
            update_filter = {
                "transaction_id": transaction_id,
                f"documents.{document_index}.translated_url": None  # Only if not already translated
            }
            update_operations = {
                "$set": {
                    f"documents.{document_index}.translated_url": file_url,
                    f"documents.{document_index}.translated_name": translated_name,
                    f"documents.{document_index}.translated_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                },
                # Increment completed_documents counter ONLY after successful match
                "$inc": {
                    "completed_documents": 1
                }
            }

            logger.info(
                f"DB UPDATE - update_one (Enterprise)",
                extra={
                    "collection": "translation_transactions",
                    "operation": "update_one",
                    "filter": update_filter,
                    "update_operations": update_operations,
                    "document_index": document_index
                }
            )
            logger.debug(
                f"Executing: db.translation_transactions.update_one("
                f"\n  filter={update_filter},"
                f"\n  update={update_operations}"
                f"\n)"
            )

            update_result = await collection.update_one(update_filter, update_operations)

            logger.debug(
                f"DB UPDATE RESULT (Enterprise)",
                extra={
                    "matched_count": update_result.matched_count,
                    "modified_count": update_result.modified_count,
                    "upserted_id": update_result.upserted_id,
                    "acknowledged": update_result.acknowledged
                }
            )

            if update_result.modified_count > 0:
                logger.info(
                    f"Successfully updated document in transaction {transaction_id}",
                    extra={
                        "transaction_id": transaction_id,
                        "file_name": file_name,
                        "document_index": document_index,
                        "translated_url": file_url,
                        "translated_name": translated_name,
                        "modified_count": update_result.modified_count,
                        "matched_count": update_result.matched_count
                    }
                )

                # Get updated transaction for email
                updated_transaction = await collection.find_one({"transaction_id": transaction_id})

                # Log counter state after update (for email batching tracking)
                completed_docs = updated_transaction.get("completed_documents", 0)
                total_docs = updated_transaction.get("total_documents", 0)
                logger.info(
                    f"COUNTER STATE AFTER UPDATE - Transaction {transaction_id}",
                    extra={
                        "transaction_id": transaction_id,
                        "file_name": file_name,
                        "completed_documents": completed_docs,
                        "total_documents": total_docs,
                        "all_complete": completed_docs >= total_docs,
                        "progress": f"{completed_docs}/{total_docs}"
                    }
                )

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
        logger.info("=" * 80)
        logger.info("TRANSACTION UPDATE SERVICE - Individual Transaction")
        logger.info("=" * 80)
        logger.info(f"Updating individual transaction {transaction_id} for file {file_name}")
        logger.debug(
            "Individual transaction update parameters",
            extra={
                "transaction_id": transaction_id,
                "file_name": file_name,
                "file_url": file_url,
                "collection": "user_transactions"
            }
        )

        try:
            collection = database.user_transactions

            if collection is None:
                logger.error(
                    "Database collection not available",
                    extra={
                        "collection": "user_transactions",
                        "transaction_id": transaction_id
                    }
                )
                return {
                    "success": False,
                    "error": "Database connection error",
                    "transaction_id": transaction_id
                }

            # Find the transaction
            logger.debug(
                "DB QUERY - find_one",
                extra={
                    "collection": "user_transactions",
                    "operation": "find_one",
                    "filter": {"transaction_id": transaction_id}
                }
            )
            logger.debug(f"Executing: db.user_transactions.find_one({{'transaction_id': '{transaction_id}'}})")

            transaction = await collection.find_one({"transaction_id": transaction_id})

            logger.debug(
                f"DB QUERY RESULT - Transaction {'found' if transaction else 'not found'}",
                extra={
                    "transaction_id": transaction_id,
                    "found": bool(transaction),
                    "transaction_keys": list(transaction.keys()) if transaction else None
                }
            )

            if not transaction:
                logger.error(f"Transaction not found: {transaction_id}")
                return {
                    "success": False,
                    "error": f"Transaction {transaction_id} not found",
                    "transaction_id": transaction_id
                }

            # Get all documents for enhanced logging
            documents = transaction.get("documents", [])

            # Log transaction details with all document filenames
            logger.info(
                f"Transaction {transaction_id} found with {len(documents)} document(s)",
                extra={
                    "transaction_id": transaction_id,
                    "document_count": len(documents),
                    "documents": [
                        {
                            "index": idx,
                            "file_name": doc.get("file_name", "unknown"),
                            "document_name": doc.get("document_name", "unknown"),
                            "has_translated_url": bool(doc.get("translated_url")),
                            "normalized_name": normalize_filename_for_comparison(
                                doc.get("file_name", "")
                            )
                        }
                        for idx, doc in enumerate(documents)
                    ]
                }
            )

            # Normalize the submitted filename for extension-agnostic comparison
            # Example: "NuVIZ_Report_translated.docx" → "nuviz_report"
            #          "NuVIZ_Report.pdf" → "nuviz_report"
            # This allows matching even when extensions differ (PDF → DOCX conversion)
            search_normalized = normalize_filename_for_comparison(file_name)

            logger.info(
                f"Searching for document matching '{file_name}'",
                extra={
                    "transaction_id": transaction_id,
                    "search_file_name": file_name,
                    "search_normalized": search_normalized,
                    "comparison_method": "extension-agnostic (basename only)"
                }
            )

            # Enhanced diagnostic logging
            logger.info("=" * 80)
            logger.info("DOCUMENT LOOKUP - Starting Detailed Comparison")
            logger.info("=" * 80)
            logger.info(f"Incoming filename from webhook: '{file_name}'")
            logger.info(f"Transaction ID: {transaction_id}")
            logger.info(f"Search normalized (after removing '_translated'): '{search_normalized}'")

            # Count how many _translated suffixes are in the incoming filename
            translated_count = file_name.lower().count('_translated')
            logger.info(f"Number of '_translated' suffixes found: {translated_count}")
            if translated_count > 1:
                logger.warning(f"⚠️  MULTIPLE '_translated' SUFFIXES DETECTED! GoogleTranslator may have re-processed this file.")

            logger.info(f"\nTransaction has {len(documents)} document(s) in database:")
            for i, doc in enumerate(documents, 1):
                logger.info(f"  Document {i}:")
                logger.info(f"    file_name:          '{doc.get('file_name')}'")
                logger.info(f"    status:             {doc.get('status')}")
                logger.info(f"    has translated_url: {bool(doc.get('translated_url'))}")
                logger.info(f"    db_normalized:      '{normalize_filename_for_comparison(doc.get('file_name', ''))}'")

            logger.info(f"\nStarting filename comparison...")

            # Find matching document by comparing normalized names (without extension)
            document_index = None
            matched_db_filename = None
            comparison_details = []

            for idx, doc in enumerate(documents):
                db_filename = doc.get("file_name", "")
                db_normalized = normalize_filename_for_comparison(db_filename)

                # Track comparison for debugging
                is_match = db_normalized == search_normalized
                comparison_details.append({
                    "index": idx,
                    "db_filename": db_filename,
                    "db_normalized": db_normalized,
                    "search_normalized": search_normalized,
                    "match": is_match
                })

                if is_match:
                    document_index = idx
                    matched_db_filename = db_filename
                    break

            # Log detailed comparison results
            logger.info(
                f"Document lookup comparison results for '{file_name}'",
                extra={
                    "transaction_id": transaction_id,
                    "search_file_name": file_name,
                    "search_normalized": search_normalized,
                    "found_match": document_index is not None,
                    "matched_index": document_index,
                    "matched_db_filename": matched_db_filename,
                    "comparison_details": comparison_details
                }
            )

            if document_index is None:
                logger.error(
                    f"Document lookup FAILED - no match found for '{file_name}'",
                    extra={
                        "transaction_id": transaction_id,
                        "search_file_name": file_name,
                        "search_normalized": search_normalized,
                        "comparison_method": "extension-agnostic (basename only)",
                        "comparison_details": comparison_details,
                        "total_documents": len(documents),
                        "failure_reason": (
                            "No document in DB matches the normalized filename. "
                            "Check if file was uploaded with a different name or "
                            "if there's a typo in the webhook filename."
                        )
                    }
                )

                return {
                    "success": False,
                    "error": f"Document {file_name} not found in transaction",
                    "transaction_id": transaction_id
                }

            # Generate translated_name
            translated_name = self._generate_translated_name(file_name)
            logger.debug(f"Generated translated_name: {translated_name}")

            # Enhanced logging: Show exactly what will be updated
            logger.info("=" * 80)
            logger.info("PREPARING DATABASE UPDATE (Individual)")
            logger.info("=" * 80)
            logger.info(
                "Fields to update in user_transactions",
                extra={
                    "transaction_id": transaction_id,
                    "document_index": document_index,
                    "fields_to_update": {
                        "translated_url": file_url,
                        "translated_name": translated_name,
                        "translated_at": "datetime.now(timezone.utc)",
                        "updated_at": "datetime.now(timezone.utc)"
                    },
                    "increment_completed_documents": True
                }
            )
            logger.info(f"Document index: {document_index}")
            logger.info(f"Setting translated_url: {file_url}")
            logger.info(f"Setting translated_name: {translated_name}")
            logger.info(f"Will increment completed_documents counter")

            # Update the specific document in the array with IDEMPOTENCY guard
            # NOTE: We already found the correct document_index above by matching lookup_name,
            # so we only need transaction_id in the filter. Adding file_name here would cause
            # a mismatch because file_name contains "_translated" suffix but database stores
            # the original filename without this suffix.
            #
            # IDEMPOTENCY: Only update if translated_url is null (prevents duplicate webhook processing)
            update_filter = {
                "transaction_id": transaction_id,
                f"documents.{document_index}.translated_url": None  # Only if not already translated
            }
            update_operations = {
                "$set": {
                    f"documents.{document_index}.translated_url": file_url,
                    f"documents.{document_index}.translated_name": translated_name,
                    f"documents.{document_index}.translated_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                },
                # Increment completed_documents counter ONLY after successful match
                "$inc": {
                    "completed_documents": 1
                }
            }

            logger.info(
                f"DB UPDATE - update_one (Individual)",
                extra={
                    "collection": "user_transactions",
                    "operation": "update_one",
                    "filter": update_filter,
                    "update_operations": update_operations,
                    "document_index": document_index
                }
            )
            logger.debug(
                f"Executing: db.user_transactions.update_one("
                f"\n  filter={update_filter},"
                f"\n  update={update_operations}"
                f"\n)"
            )

            update_result = await collection.update_one(update_filter, update_operations)

            # Enhanced update result logging
            logger.info("=" * 80)
            logger.info("DATABASE UPDATE RESULT")
            logger.info("=" * 80)
            logger.info(
                "MongoDB update_one result",
                extra={
                    "matched_count": update_result.matched_count,
                    "modified_count": update_result.modified_count,
                    "update_successful": update_result.matched_count > 0 and update_result.modified_count > 0,
                    "transaction_id": transaction_id,
                    "document_index": document_index
                }
            )
            logger.info(f"Matched: {update_result.matched_count}")
            logger.info(f"Modified: {update_result.modified_count}")

            if update_result.matched_count == 0:
                logger.error("⚠️  UPDATE FAILED - No document matched the filter!")
                logger.error(f"Filter used: {update_filter}")
            elif update_result.modified_count == 0:
                logger.warning("⚠️  UPDATE MATCHED but MODIFIED 0 - Document may already be updated (idempotency check)")
            else:
                logger.info(f"✅ Successfully updated document {document_index} in transaction {transaction_id}")

            logger.debug(
                f"DB UPDATE RESULT (Individual)",
                extra={
                    "matched_count": update_result.matched_count,
                    "modified_count": update_result.modified_count,
                    "upserted_id": update_result.upserted_id,
                    "acknowledged": update_result.acknowledged
                }
            )

            if update_result.modified_count > 0:
                logger.info(
                    f"Successfully updated document in transaction {transaction_id}",
                    extra={
                        "transaction_id": transaction_id,
                        "file_name": file_name,
                        "document_index": document_index,
                        "translated_url": file_url,
                        "translated_name": translated_name,
                        "modified_count": update_result.modified_count,
                        "matched_count": update_result.matched_count
                    }
                )

                # Get updated transaction for email
                updated_transaction = await collection.find_one({"transaction_id": transaction_id})

                # Log counter state after update (for email batching tracking)
                completed_docs = updated_transaction.get("completed_documents", 0)
                total_docs = updated_transaction.get("total_documents", 0)
                logger.info(
                    f"COUNTER STATE AFTER UPDATE - Transaction {transaction_id}",
                    extra={
                        "transaction_id": transaction_id,
                        "file_name": file_name,
                        "completed_documents": completed_docs,
                        "total_documents": total_docs,
                        "all_complete": completed_docs >= total_docs,
                        "progress": f"{completed_docs}/{total_docs}"
                    }
                )

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
