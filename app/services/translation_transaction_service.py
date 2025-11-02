"""
Translation Transaction Service

Service layer for managing translation_transactions collection operations.
Provides helper functions for updating transaction records, file information, and timestamps.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from app.database import database

logger = logging.getLogger(__name__)


async def update_translated_file_info(
    transaction_id: str,
    translated_file_name: str,
    translated_file_url: str
) -> bool:
    """
    Update translated file information for a translation transaction.

    This function updates the translated_file_name, translated_file_url, and updated_at
    timestamp for a given transaction. It's designed to be called by background jobs,
    webhook handlers, or admin tools when a translation is completed.

    Args:
        transaction_id: The unique transaction identifier (e.g., "TXN-20FEF6D8FE")
        translated_file_name: The name of the translated file (e.g., "document_fr.pdf")
        translated_file_url: The Google Drive URL of the translated file

    Returns:
        bool: True if the update was successful, False otherwise

    Example:
        >>> success = await update_translated_file_info(
        ...     transaction_id="TXN-20FEF6D8FE",
        ...     translated_file_name="contract_fr.pdf",
        ...     translated_file_url="https://drive.google.com/file/d/abc123/view"
        ... )
        >>> if success:
        ...     print("Translation file info updated successfully")
    """
    try:
        logger.info(
            f"Updating translated file info for transaction {transaction_id}",
            extra={
                "transaction_id": transaction_id,
                "translated_file_name": translated_file_name,
                "has_url": bool(translated_file_url)
            }
        )

        # Prepare update document
        update_doc = {
            "$set": {
                "translated_file_name": translated_file_name,
                "translated_file_url": translated_file_url,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }

        # Update the transaction
        result = await database.translation_transactions.update_one(
            {"transaction_id": transaction_id},
            update_doc
        )

        if result.matched_count == 0:
            logger.warning(
                f"Transaction {transaction_id} not found for update",
                extra={"transaction_id": transaction_id}
            )
            return False

        if result.modified_count == 0:
            logger.info(
                f"Transaction {transaction_id} matched but not modified (values unchanged)",
                extra={"transaction_id": transaction_id}
            )
            return True  # Still consider this a success

        logger.info(
            f"Successfully updated translated file info for transaction {transaction_id}",
            extra={
                "transaction_id": transaction_id,
                "matched_count": result.matched_count,
                "modified_count": result.modified_count
            }
        )

        return True

    except Exception as e:
        logger.error(
            f"Error updating translated file info for transaction {transaction_id}: {str(e)}",
            extra={
                "transaction_id": transaction_id,
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        return False


async def get_translation_transaction(transaction_id: str) -> Optional[dict]:
    """
    Retrieve a translation transaction by its transaction_id.

    Args:
        transaction_id: The unique transaction identifier

    Returns:
        Optional[dict]: The transaction document if found, None otherwise
    """
    try:
        transaction = await database.translation_transactions.find_one(
            {"transaction_id": transaction_id}
        )
        return transaction
    except Exception as e:
        logger.error(
            f"Error retrieving transaction {transaction_id}: {str(e)}",
            extra={"transaction_id": transaction_id, "error": str(e)},
            exc_info=True
        )
        return None
