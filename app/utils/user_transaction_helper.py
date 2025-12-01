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
from app.utils.transaction_id_generator import generate_unique_transaction_id

logger = logging.getLogger(__name__)


async def create_user_transaction(
    user_name: str,
    user_email: str,
    documents: List[Dict[str, Any]],
    number_of_units: int,
    unit_type: str,
    cost_per_unit: float,
    source_language: str,
    target_language: str,
    square_transaction_id: str,
    date: datetime,
    status: str = "processing",
    # New Square payment parameters
    square_payment_id: Optional[str] = None,
    amount_cents: Optional[int] = None,
    currency: str = "USD",
    payment_status: str = "COMPLETED",
    payment_date: Optional[datetime] = None,
    refunds: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    Create a new user transaction record with Square payment integration and multiple documents support.

    Automatically calculates total_cost and sets timestamps.

    Args:
        user_name: Full name of the user
        user_email: Email address of the user (indexed)
        documents: List of document dictionaries (at least one required)
        number_of_units: Number of units (pages, words, or characters)
        unit_type: Type of unit ("page", "word", "character")
        cost_per_unit: Cost per single unit (decimal)
        source_language: Source language code
        target_language: Target language code
        square_transaction_id: Unique Square payment transaction ID
        date: Transaction date
        status: Transaction status ("processing", "completed", "failed")
        square_payment_id: Square payment ID (defaults to square_transaction_id if not provided)
        amount_cents: Payment amount in cents (auto-calculated if not provided)
        currency: Currency code (default: "USD")
        payment_status: Payment status ("APPROVED", "COMPLETED", "CANCELED", "FAILED")
        payment_date: Payment processing date (defaults to current UTC time)
        refunds: List of refund dictionaries (default: empty list)

    Returns:
        str: transaction_id if successful, None if failed

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

        # Validate payment_status
        valid_payment_statuses = {"APPROVED", "COMPLETED", "CANCELED", "FAILED"}
        if payment_status not in valid_payment_statuses:
            logger.error(
                f"[UserTransaction] Invalid payment_status: {payment_status}. "
                f"Must be one of {valid_payment_statuses}"
            )
            return None

        # Calculate total_cost
        total_cost = float(Decimal(str(number_of_units)) * Decimal(str(cost_per_unit)))

        # Auto-calculate amount_cents if not provided
        if amount_cents is None:
            amount_cents = int(total_cost * 100)

        # Default square_payment_id to square_transaction_id if not provided
        if square_payment_id is None:
            square_payment_id = square_transaction_id

        # Get current UTC time
        current_time = datetime.now(timezone.utc)

        # Default payment_date to current time if not provided
        if payment_date is None:
            payment_date = current_time

        # Default refunds to empty list if not provided
        if refunds is None:
            refunds = []

        # Validate documents array
        if not documents or len(documents) == 0:
            logger.error("[UserTransaction] documents array cannot be empty")
            return None

        # Generate unique transaction ID (USER + 6-digit number)
        try:
            transaction_id = await generate_unique_transaction_id(collection)
            logger.info(f"[UserTransaction] Generated transaction_id: {transaction_id}")
        except Exception as e:
            logger.error(f"[UserTransaction] Failed to generate transaction_id: {e}")
            return None

        # Build transaction document with Square payment fields
        transaction_doc = {
            # Core transaction fields
            "user_name": user_name,
            "user_email": user_email,
            "documents": documents,
            "number_of_units": number_of_units,
            "unit_type": unit_type,
            "cost_per_unit": cost_per_unit,
            "source_language": source_language,
            "target_language": target_language,
            "transaction_id": transaction_id,
            "square_transaction_id": square_transaction_id,
            "date": date,
            "status": status,
            "total_cost": total_cost,
            # Square payment fields
            "square_payment_id": square_payment_id,
            "amount_cents": amount_cents,
            "currency": currency,
            "payment_status": payment_status,
            "refunds": refunds,
            "payment_date": payment_date,
            # Timestamps
            "created_at": current_time,
            "updated_at": current_time,
        }

        # Insert into database
        try:
            result = await collection.insert_one(transaction_doc)

            # Get MongoDB-generated _id
            inserted_id = str(result.inserted_id)

            logger.info(
                f"[UserTransaction] Created transaction {transaction_id} (Square: {square_transaction_id}) "
                f"for user {user_email} with status {status}, payment_status {payment_status}, "
                f"MongoDB ID: {inserted_id}",
                extra={
                    "transaction_id": transaction_id,
                    "square_transaction_id": square_transaction_id,
                    "mongodb_id": inserted_id,
                    "user_email": user_email,
                    "documents_count": len(documents),
                    "document_names": [d.get("file_name") or d.get("document_name", "unknown") for d in documents]
                }
            )

            # Console output for visibility (matching translate_user.py logging style)
            print(f"✅ Created user transaction with {len(documents)} document(s)")
            print(f"   📋 Transaction Details:")
            print(f"      • transaction_id: {transaction_id} (USER format)")
            print(f"      • square_transaction_id: {square_transaction_id}")
            print(f"      • user_email: {user_email}")
            print(f"      • total_cost: ${total_cost}")
            print(f"      • status: {status}")
            # Log each document with its translation mode (matching Enterprise flow format)
            for idx, doc in enumerate(documents, 1):
                doc_name = doc.get('file_name') or doc.get('document_name', 'unknown')
                doc_mode = doc.get('translation_mode', 'automatic')
                doc_pages = doc.get('page_count', 1)  # Get page count from document, default to 1
                print(f"   📄 Document {idx}: {doc_name} ({doc_pages} pages, mode: {doc_mode})")

            # Full transaction record logging (for debugging and verification)
            print("=" * 80)
            print("📋 FULL TRANSACTION RECORD CREATED IN DATABASE:")
            print("=" * 80)
            for key, value in transaction_doc.items():
                if key == "documents":
                    print(f"   • {key}: [{len(value)} documents]")
                    for idx, doc in enumerate(value, 1):
                        print(f"      📄 Doc {idx}: {doc}")
                else:
                    print(f"   • {key}: {value}")
            print("=" * 80)

            # Structured logging for production
            logger.info(
                f"Created user transaction {transaction_id} with {len(documents)} document(s)",
                extra={
                    "transaction_id": transaction_id,
                    "transaction_id_format": "USER######",
                    "square_transaction_id": square_transaction_id,
                    "mongodb_id": inserted_id,
                    "user_email": user_email,
                    "total_cost": total_cost,
                    "status": status,
                    "payment_status": payment_status,
                    "documents_count": len(documents),
                    "document_names": [d.get("file_name") or d.get("document_name", "unknown") for d in documents]
                }
            )

            # Debug: Verify insert by querying back
            verification = await collection.find_one({"square_transaction_id": square_transaction_id})
            if verification:
                logger.info(
                    f"[UserTransaction] VERIFIED: Transaction {square_transaction_id} "
                    f"exists in database with ID {verification.get('_id')}"
                )
            else:
                logger.warning(
                    f"[UserTransaction] WARNING: Transaction {square_transaction_id} "
                    f"was reported as inserted but cannot be found in database!"
                )
        except Exception as db_error:
            logger.error(
                f"[UserTransaction] FAILED to insert transaction {square_transaction_id}: {type(db_error).__name__}: {str(db_error)}",
                exc_info=True
            )
            raise

        return transaction_id

    except DuplicateKeyError:
        logger.error(
            f"[UserTransaction] Duplicate transaction_id or square_transaction_id: {transaction_id} / {square_transaction_id}"
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


async def add_refund_to_transaction(
    square_transaction_id: str,
    refund_data: Dict[str, Any],
) -> bool:
    """
    Add a refund to an existing user transaction.

    Args:
        square_transaction_id: Unique Square transaction ID
        refund_data: Dictionary containing refund information:
            - refund_id: Square refund ID
            - amount_cents: Refund amount in cents
            - currency: Currency code (default: "USD")
            - status: Refund status (COMPLETED, PENDING, FAILED)
            - created_at: Refund creation timestamp
            - idempotency_key: Unique idempotency key
            - reason: Optional reason for refund

    Returns:
        bool: True if refund added successfully, False otherwise

    Raises:
        None: Errors are logged and False is returned
    """
    try:
        # Check database connection
        collection = database.user_transactions
        if collection is None:
            logger.error("[UserTransaction] Database collection not available")
            return False

        # Validate required refund fields
        required_fields = {"refund_id", "amount_cents", "status", "idempotency_key"}
        if not all(field in refund_data for field in required_fields):
            logger.error(
                f"[UserTransaction] Missing required refund fields. "
                f"Required: {required_fields}, Got: {refund_data.keys()}"
            )
            return False

        # Add created_at if not provided
        if "created_at" not in refund_data:
            refund_data["created_at"] = datetime.now(timezone.utc)

        # Add currency if not provided
        if "currency" not in refund_data:
            refund_data["currency"] = "USD"

        # Add refund to array and update timestamp
        result = await collection.update_one(
            {"square_transaction_id": square_transaction_id},
            {
                "$push": {"refunds": refund_data},
                "$set": {"updated_at": datetime.now(timezone.utc)},
            },
        )

        if result.matched_count == 0:
            logger.warning(
                f"[UserTransaction] Transaction not found: {square_transaction_id}"
            )
            return False

        if result.modified_count == 0:
            logger.warning(
                f"[UserTransaction] Transaction {square_transaction_id} "
                "was not modified (possible duplicate refund)"
            )
            return False

        logger.info(
            f"[UserTransaction] Added refund {refund_data['refund_id']} "
            f"to transaction {square_transaction_id}"
        )
        return True

    except PyMongoError as e:
        logger.error(
            f"[UserTransaction] MongoDB error adding refund: {e}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"[UserTransaction] Unexpected error adding refund: {e}",
            exc_info=True,
        )
        return False


async def update_payment_status(
    square_transaction_id: str,
    new_payment_status: str,
) -> bool:
    """
    Update payment status for a user transaction.

    Args:
        square_transaction_id: Unique Square transaction ID
        new_payment_status: New payment status (APPROVED, COMPLETED, CANCELED, FAILED)

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

        # Validate payment_status
        valid_payment_statuses = {"APPROVED", "COMPLETED", "CANCELED", "FAILED"}
        if new_payment_status not in valid_payment_statuses:
            logger.error(
                f"[UserTransaction] Invalid payment_status: {new_payment_status}. "
                f"Must be one of {valid_payment_statuses}"
            )
            return False

        # Update payment status
        result = await collection.update_one(
            {"square_transaction_id": square_transaction_id},
            {
                "$set": {
                    "payment_status": new_payment_status,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        if result.matched_count == 0:
            logger.warning(
                f"[UserTransaction] Transaction not found: {square_transaction_id}"
            )
            return False

        if result.modified_count == 0:
            logger.info(
                f"[UserTransaction] Transaction {square_transaction_id} "
                "already had the same payment status"
            )
            return True

        logger.info(
            f"[UserTransaction] Updated payment status for transaction "
            f"{square_transaction_id} to {new_payment_status}"
        )
        return True

    except PyMongoError as e:
        logger.error(
            f"[UserTransaction] MongoDB error updating payment status: {e}",
            exc_info=True,
        )
        return False
    except Exception as e:
        logger.error(
            f"[UserTransaction] Unexpected error updating payment status: {e}",
            exc_info=True,
        )
        return False


# Export all public functions
__all__ = [
    "create_user_transaction",
    "update_user_transaction_status",
    "get_user_transactions_by_email",
    "get_user_transaction",
    "add_refund_to_transaction",
    "update_payment_status",
]
