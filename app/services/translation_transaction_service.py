"""
Translation Transaction Service

Service layer for managing translation_transactions collection operations.
Provides helper functions for creating, updating transaction records, file information, and timestamps.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging

from app.database import database

logger = logging.getLogger(__name__)


async def create_translation_transaction(
    transaction_id: str,
    user_id: str,
    documents: List[Dict[str, Any]],
    source_language: str,
    target_language: str,
    units_count: int,
    price_per_unit: float,
    total_price: float,
    status: str = "started",
    error_message: str = "",
    company_name: Optional[str] = None,
    subscription_id: Optional[str] = None,
    unit_type: str = "page"
) -> Optional[str]:
    """
    Create a new translation transaction with multiple documents support.

    This function inserts a new record into the translation_transactions collection
    with support for multiple documents per transaction.

    Args:
        transaction_id: Unique transaction identifier (e.g., "TXN-20FEF6D8FE")
        user_id: User email address
        documents: List of document dicts with fields: file_name, file_size, original_url,
                  translated_url, translated_name, status, uploaded_at, translated_at,
                  processing_started_at, processing_duration
        source_language: Source language code (e.g., "en")
        target_language: Target language code (e.g., "fr")
        units_count: Number of translation units (pages or words)
        price_per_unit: Price per translation unit in dollars
        total_price: Total transaction price in dollars
        status: Transaction status (default: "started")
        error_message: Error message if status is failed (default: "")
        company_name: Company name if enterprise customer
        subscription_id: Subscription identifier (ObjectId) if enterprise customer
        unit_type: Unit type for billing: "page" | "word" (default: "page")

    Returns:
        Optional[str]: The inserted document's _id (as string) if successful, None otherwise

    Example:
        >>> documents = [
        ...     {
        ...         "file_name": "contract.pdf",
        ...         "file_size": 524288,
        ...         "original_url": "https://drive.google.com/file/d/abc123/view",
        ...         "translated_url": None,
        ...         "translated_name": None,
        ...         "status": "uploaded",
        ...         "uploaded_at": datetime(2025, 10, 20, 10, 0, 0, tzinfo=timezone.utc),
        ...         "translated_at": None,
        ...         "processing_started_at": None,
        ...         "processing_duration": None
        ...     }
        ... ]
        >>> txn_id = await create_translation_transaction(
        ...     transaction_id="TXN-20FEF6D8FE",
        ...     user_id="user@example.com",
        ...     documents=documents,
        ...     source_language="en",
        ...     target_language="fr",
        ...     units_count=15,
        ...     price_per_unit=0.01,
        ...     total_price=0.15,
        ...     company_name="Iris Trading",
        ...     subscription_id="68fa6add22b0c739f4f4b273"
        ... )
    """
    # Validate documents array
    if not documents or len(documents) == 0:
        logger.error(
            "[TranslationTransaction] documents array cannot be empty",
            extra={"transaction_id": transaction_id}
        )
        return None

    try:
        logger.info(
            f"Creating translation transaction {transaction_id} with {len(documents)} documents",
            extra={
                "transaction_id": transaction_id,
                "user_id": user_id,
                "documents_count": len(documents),
                "company_name": company_name,
                "will_add_transaction_id_to_metadata": company_name is not None,
                "documents": [
                    {"file_name": d["file_name"], "file_size": d["file_size"]}
                    for d in documents
                ]
            }
        )

        # Prepare transaction document
        now = datetime.now(timezone.utc)
        transaction_doc = {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "documents": documents,
            "source_language": source_language,
            "target_language": target_language,
            "units_count": units_count,
            "price_per_unit": price_per_unit,
            "total_price": total_price,
            "status": status,
            "error_message": error_message,
            "created_at": now,
            "updated_at": now,
            "company_name": company_name,
            "subscription_id": subscription_id,
            "unit_type": unit_type
        }

        # Insert into database
        result = await database.translation_transactions.insert_one(transaction_doc)

        # Get MongoDB-generated _id
        inserted_id = str(result.inserted_id)

        # ONLY for enterprise customers: Add transaction_id to all document metadata
        if company_name:
            await database.translation_transactions.update_one(
                {"_id": result.inserted_id},
                {"$set": {
                    "documents.$[].transaction_id": inserted_id
                }}
            )

            logger.info(
                f"Added transaction_id to {len(documents)} document(s) metadata for enterprise customer",
                extra={
                    "transaction_id": transaction_id,
                    "mongodb_id": inserted_id,
                    "company_name": company_name,
                    "documents_count": len(documents),
                    "document_names": [d["file_name"] for d in documents]
                }
            )

        logger.info(
            f"Successfully created translation transaction {transaction_id}",
            extra={
                "transaction_id": transaction_id,
                "inserted_id": inserted_id,
                "documents_count": len(documents)
            }
        )

        return inserted_id

    except Exception as e:
        logger.error(
            f"Error creating translation transaction {transaction_id}: {str(e)}",
            extra={
                "transaction_id": transaction_id,
                "error": str(e),
                "error_type": type(e).__name__
            },
            exc_info=True
        )
        return None


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
