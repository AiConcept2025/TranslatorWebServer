"""
User transaction helper module for managing user_transactions collection.

This module provides CRUD operations for individual user transactions
with Square payment integration.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pymongo.errors import DuplicateKeyError, PyMongoError

from app.database import database

logger = logging.getLogger(__name__)


async def create_user_transaction(
    user_name: str,
    user_email: str,
    document_url: str,
    number_of_units: int,
    unit_type: str,
    cost_per_unit: float,
    source_language: str,
    target_language: str,
    square_transaction_id: str,
    date: datetime,
    status: str = "processing",
) -> Optional[str]:
    """
    Create a new user transaction record.

    Automatically calculates total_cost and sets timestamps.

    Args:
        user_name: Full name of the user
        user_email: Email address of the user (indexed)
        document_url: URL or path to the document
        number_of_units: Number of units (pages, words, or characters)
        unit_type: Type of unit ("page", "word", "character")
        cost_per_unit: Cost per single unit (decimal)
        source_language: Source language code
        target_language: Target language code
        square_transaction_id: Unique Square payment transaction ID
        date: Transaction date
        status: Transaction status ("processing", "completed", "failed")

    Returns:
        str: square_transaction_id if successful, None if failed

    Raises:
        None: Errors are logged and None is returned
    """
    try:
        # Check database connection
        collection = database.user_transactions
        if collection is None:
            logger.error("[UserTransaction] Database collection not available")
            return None

        # Validate unit_type
        valid_unit_types = {"page", "word", "character"}
        if unit_type not in valid_unit_types:
            logger.error(
                f"[UserTransaction] Invalid unit_type: {unit_type}. "
                f"Must be one of {valid_unit_types}"
            )
            return None

        # Validate status
        valid_statuses = {"processing", "completed", "failed"}
        if status not in valid_statuses:
            logger.error(
                f"[UserTransaction] Invalid status: {status}. "
                f"Must be one of {valid_statuses}"
            )
            return None

        # Calculate total_cost
        total_cost = float(Decimal(str(number_of_units)) * Decimal(str(cost_per_unit)))

        # Get current UTC time
        current_time = datetime.now(timezone.utc)

        # Build transaction document
        transaction_doc = {
            "user_name": user_name,
            "user_email": user_email,
            "document_url": document_url,
            "number_of_units": number_of_units,
            "unit_type": unit_type,
            "cost_per_unit": cost_per_unit,
            "source_language": source_language,
            "target_language": target_language,
            "square_transaction_id": square_transaction_id,
            "date": date,
            "status": status,
            "total_cost": total_cost,
            "created_at": current_time,
            "updated_at": current_time,
        }

        # Insert into database
        await collection.insert_one(transaction_doc)

        logger.info(
            f"[UserTransaction] Created transaction {square_transaction_id} "
            f"for user {user_email} with status {status}"
        )

        return square_transaction_id

    except DuplicateKeyError:
        logger.error(
            f"[UserTransaction] Duplicate square_transaction_id: {square_transaction_id}"
        )
        return None
    except PyMongoError as e:
        logger.error(
            f"[UserTransaction] MongoDB error creating transaction: {e}",
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(
            f"[UserTransaction] Unexpected error creating transaction: {e}",
            exc_info=True,
        )
        return None


async def update_user_transaction_status(
    square_transaction_id: str,
    new_status: str,
    error_message: Optional[str] = None,
) -> bool:
    """
    Update transaction status by square_transaction_id.

    Updates the status and updated_at timestamp. Optionally adds error_message.

    Args:
        square_transaction_id: Unique Square transaction ID
        new_status: New status ("processing", "completed", "failed")
        error_message: Optional error message (added only if provided)

    Returns:
        bool: True if update successful, False otherwise

    Raises:
        None: Errors are logged and False is returned
    """
    try:
        # Check database connection
        collection = database.user_transactions
        if collection is None:
            logger.error("[UserTransaction] Database collection not available")
            return False

        # Validate status
        valid_statuses = {"processing", "completed", "failed"}
        if new_status not in valid_statuses:
            logger.error(
                f"[UserTransaction] Invalid status: {new_status}. "
                f"Must be one of {valid_statuses}"
            )
            return False

        # Build update document
        update_doc = {
            "$set": {
                "status": new_status,
                "updated_at": datetime.now(timezone.utc),
            }
        }

        # Add error_message if provided
        if error_message is not None:
            update_doc["$set"]["error_message"] = error_message

        # Update transaction
        result = await collection.update_one(
            {"square_transaction_id": square_transaction_id},
            update_doc,
        )

        if result.matched_count == 0:
            logger.warning(
                f"[UserTransaction] Transaction not found: {square_transaction_id}"
            )
            return False

        if result.modified_count == 0:
            logger.info(
                f"[UserTransaction] Transaction {square_transaction_id} "
                "already had the same status"
            )
            return True

        logger.info(
            f"[UserTransaction] Updated transaction {square_transaction_id} "
            f"to status {new_status}"
        )
        return True

    except PyMongoError as e:
        logger.error(
            f"[UserTransaction] MongoDB error updating transaction: {e}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"[UserTransaction] Unexpected error updating transaction: {e}",
            exc_info=True,
        )
        return False


async def get_user_transactions_by_email(
    user_email: str,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get all transactions for a user by email.

    Optionally filters by status. Results are sorted by date descending
    (most recent first).

    Args:
        user_email: Email address of the user
        status: Optional status filter ("processing", "completed", "failed")

    Returns:
        list: List of transaction dictionaries (empty list if none found)

    Raises:
        None: Errors are logged and empty list is returned
    """
    try:
        # Check database connection
        collection = database.user_transactions
        if collection is None:
            logger.error("[UserTransaction] Database collection not available")
            return []

        # Build query
        query = {"user_email": user_email}

        # Add status filter if provided
        if status is not None:
            valid_statuses = {"processing", "completed", "failed"}
            if status not in valid_statuses:
                logger.error(
                    f"[UserTransaction] Invalid status filter: {status}. "
                    f"Must be one of {valid_statuses}"
                )
                return []
            query["status"] = status

        # Query database with sort
        cursor = collection.find(query).sort("date", -1)

        # Convert to list
        transactions = await cursor.to_list(length=None)

        # Convert ObjectId to string for JSON serialization
        for transaction in transactions:
            if "_id" in transaction:
                transaction["_id"] = str(transaction["_id"])

        logger.info(
            f"[UserTransaction] Found {len(transactions)} transactions "
            f"for user {user_email}"
            + (f" with status {status}" if status else "")
        )

        return transactions

    except PyMongoError as e:
        logger.error(
            f"[UserTransaction] MongoDB error retrieving transactions: {e}",
            exc_info=True,
        )
        return []
    except Exception as e:
        logger.error(
            f"[UserTransaction] Unexpected error retrieving transactions: {e}",
            exc_info=True,
        )
        return []


async def get_user_transaction(
    square_transaction_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get single transaction by Square transaction ID.

    Args:
        square_transaction_id: Unique Square transaction ID

    Returns:
        dict: Transaction dictionary if found, None otherwise

    Raises:
        None: Errors are logged and None is returned
    """
    try:
        # Check database connection
        collection = database.user_transactions
        if collection is None:
            logger.error("[UserTransaction] Database collection not available")
            return None

        # Query database
        transaction = await collection.find_one(
            {"square_transaction_id": square_transaction_id}
        )

        if transaction is None:
            logger.info(
                f"[UserTransaction] Transaction not found: {square_transaction_id}"
            )
            return None

        # Convert ObjectId to string for JSON serialization
        if "_id" in transaction:
            transaction["_id"] = str(transaction["_id"])

        logger.info(
            f"[UserTransaction] Retrieved transaction {square_transaction_id}"
        )

        return transaction

    except PyMongoError as e:
        logger.error(
            f"[UserTransaction] MongoDB error retrieving transaction: {e}",
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(
            f"[UserTransaction] Unexpected error retrieving transaction: {e}",
            exc_info=True,
        )
        return None


# Export all public functions
__all__ = [
    "create_user_transaction",
    "update_user_transaction_status",
    "get_user_transactions_by_email",
    "get_user_transaction",
]
