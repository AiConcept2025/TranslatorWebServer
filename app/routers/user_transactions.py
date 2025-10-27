"""
User Transaction Payment API Router.

This module provides payment management endpoints for user_transactions collection:
- Creating user transactions with Square payment details
- Processing refunds
- Retrieving transaction history by email
- Updating payment status
"""

from fastapi import APIRouter, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime
from pydantic import EmailStr
import logging
import uuid

from app.models.payment import (
    UserTransactionCreate,
    UserTransactionResponse,
    UserTransactionRefundRequest,
)
from app.utils.user_transaction_helper import (
    create_user_transaction,
    get_user_transactions_by_email,
    get_user_transaction,
    add_refund_to_transaction,
    update_payment_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/user-transactions", tags=["User Transaction Payments"])


@router.post("/process", response_model=UserTransactionResponse, status_code=status.HTTP_201_CREATED)
async def process_payment_transaction(transaction_data: UserTransactionCreate):
    """
    Process a payment and create user transaction record.

    This endpoint creates a user transaction with Square payment details for
    individual translation jobs. All 22 fields are stored in the users_transactions collection.

    **Required Fields:**
    - `user_name`: Full name of the user
    - `user_email`: User email address
    - `document_url`: URL to the original document
    - `number_of_units`: Number of units (pages, words, or characters)
    - `unit_type`: Type of unit (page | word | character)
    - `cost_per_unit`: Cost per single unit
    - `source_language`: Source language code (e.g., "en")
    - `target_language`: Target language code (e.g., "es")
    - `square_transaction_id`: Unique Square transaction ID
    - `square_payment_id`: Square payment ID

    **Optional Fields (with defaults):**
    - `translated_url`: URL to the translated document (null initially)
    - `currency`: "USD"
    - `payment_status`: "COMPLETED"
    - `status`: "processing"
    - `date`: Current timestamp
    - `payment_date`: Current timestamp
    - `amount_cents`: Auto-calculated from units if not provided

    **Request Body Example:**
    ```json
    {
        "user_name": "John Doe",
        "user_email": "john.doe@example.com",
        "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
        "translated_url": "https://drive.google.com/file/d/1ABC_transl_document/view",
        "number_of_units": 10,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "en",
        "target_language": "es",
        "square_transaction_id": "SQR-1EC28E70F10B4D9E",
        "square_payment_id": "SQR-1EC28E70F10B4D9E",
        "amount_cents": 150,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "status": "completed"
    }
    ```

    **Response Example:**
    ```json
    {
        "id": "68fad3c2a0f41c24037c4810",
        "user_name": "John Doe",
        "user_email": "john.doe@example.com",
        "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
        "translated_url": "https://drive.google.com/file/d/1ABC_transl_document/view",
        "number_of_units": 10,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "en",
        "target_language": "es",
        "square_transaction_id": "SQR-1EC28E70F10B4D9E",
        "date": "2025-10-23T23:56:55.438Z",
        "status": "completed",
        "total_cost": 1.5,
        "square_payment_id": "SQR-1EC28E70F10B4D9E",
        "amount_cents": 150,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": "2025-10-23T23:56:55.438Z",
        "created_at": "2025-10-23T23:56:55.438Z",
        "updated_at": "2025-10-23T23:56:55.438Z"
    }
    ```

    **Status Codes:**
    - **201**: Transaction created successfully
    - **400**: Invalid request data (missing required fields, invalid email, etc.)
    - **500**: Internal server error

    **cURL Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/user-transactions/process" \\
         -H "Content-Type: application/json" \\
         -d '{
           "user_name": "John Doe",
           "user_email": "john.doe@example.com",
           "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
           "translated_url": "https://drive.google.com/file/d/1ABC_transl_document/view",
           "number_of_units": 10,
           "unit_type": "page",
           "cost_per_unit": 0.15,
           "source_language": "en",
           "target_language": "es",
           "square_transaction_id": "SQR-1EC28E70F10B4D9E",
           "square_payment_id": "SQR-1EC28E70F10B4D9E",
           "amount_cents": 150
         }'
    ```
    """
    try:
        logger.info(
            f"Processing payment transaction for {transaction_data.user_email}, "
            f"Square ID: {transaction_data.square_transaction_id}"
        )

        # Use provided date or default to current UTC time
        transaction_date = transaction_data.date if transaction_data.date else datetime.utcnow()
        payment_date = transaction_data.payment_date if transaction_data.payment_date else datetime.utcnow()

        # Create transaction using helper function
        result = await create_user_transaction(
            user_name=transaction_data.user_name,
            user_email=transaction_data.user_email,
            document_url=transaction_data.document_url,
            translated_url=transaction_data.translated_url,
            number_of_units=transaction_data.number_of_units,
            unit_type=transaction_data.unit_type,
            cost_per_unit=transaction_data.cost_per_unit,
            source_language=transaction_data.source_language,
            target_language=transaction_data.target_language,
            square_transaction_id=transaction_data.square_transaction_id,
            date=transaction_date,
            status=transaction_data.status,
            square_payment_id=transaction_data.square_payment_id,
            amount_cents=transaction_data.amount_cents,
            currency=transaction_data.currency,
            payment_status=transaction_data.payment_status,
            payment_date=payment_date,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create transaction record"
            )

        # Retrieve created transaction
        transaction_doc = await get_user_transaction(transaction_data.square_transaction_id)

        if not transaction_doc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Transaction created but could not be retrieved"
            )

        logger.info(
            f"Transaction created successfully: {transaction_data.square_transaction_id}"
        )

        # Convert to response format
        transaction_doc["_id"] = str(transaction_doc["_id"])
        return UserTransactionResponse(**transaction_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process payment transaction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process transaction: {str(e)}"
        )


@router.post("/{square_transaction_id}/refund", status_code=status.HTTP_200_OK)
async def process_transaction_refund(
    square_transaction_id: str = Path(..., description="Square transaction ID"),
    refund_request: UserTransactionRefundRequest = None
):
    """
    Process a refund for a user transaction.

    Adds refund information to the transaction's refunds array and updates payment status if needed.

    **Path Parameters:**
    - `square_transaction_id`: Square transaction ID (e.g., "SQR-1EC28E70F10B4D9E")

    **Request Body:**
    ```json
    {
        "refund_id": "rfn_01J2M9ABCD",
        "amount_cents": 50,
        "currency": "USD",
        "idempotency_key": "rfd_c8e1a4b5-1c7a-4f9b-9f2d-1a2b3c4d5e6f",
        "reason": "Customer request"
    }
    ```

    **Response Example:**
    ```json
    {
        "success": true,
        "message": "Refund processed successfully",
        "data": {
            "square_transaction_id": "SQR-1EC28E70F10B4D9E",
            "refund_id": "rfn_01J2M9ABCD",
            "amount_cents": 50,
            "total_refunds": 1
        }
    }
    ```

    **Status Codes:**
    - **200**: Refund processed successfully
    - **404**: Transaction not found
    - **400**: Invalid refund data or amount exceeds transaction total
    - **500**: Internal server error

    **cURL Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/user-transactions/SQR-1EC28E70F10B4D9E/refund" \\
         -H "Content-Type: application/json" \\
         -d '{
           "refund_id": "rfn_01J2M9ABCD",
           "amount_cents": 50,
           "currency": "USD",
           "idempotency_key": "rfd_c8e1a4b5-1c7a-4f9b-9f2d-1a2b3c4d5e6f",
           "reason": "Customer request"
         }'
    ```
    """
    try:
        logger.info(
            f"Processing refund for transaction {square_transaction_id}, "
            f"amount: {refund_request.amount_cents} cents"
        )

        # Check if transaction exists
        transaction = await get_user_transaction(square_transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction not found: {square_transaction_id}"
            )

        # Prepare refund data
        refund_data = {
            "refund_id": refund_request.refund_id,
            "amount_cents": refund_request.amount_cents,
            "currency": refund_request.currency,
            "status": "COMPLETED",  # Default status
            "created_at": datetime.utcnow(),
            "idempotency_key": refund_request.idempotency_key,
        }

        if refund_request.reason:
            refund_data["reason"] = refund_request.reason

        # Add refund to transaction
        success = await add_refund_to_transaction(square_transaction_id, refund_data)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process refund"
            )

        # Retrieve updated transaction
        updated_transaction = await get_user_transaction(square_transaction_id)

        logger.info(f"Refund processed successfully for transaction {square_transaction_id}")

        return JSONResponse(content={
            "success": True,
            "message": "Refund processed successfully",
            "data": {
                "square_transaction_id": square_transaction_id,
                "refund_id": refund_request.refund_id,
                "amount_cents": refund_request.amount_cents,
                "total_refunds": len(updated_transaction.get("refunds", []))
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process refund: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process refund: {str(e)}"
        )


@router.get("/user/{email}")
async def get_user_transaction_history(
    email: EmailStr = Path(..., description="User email address"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (completed, pending, failed)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip for pagination"),
):
    """
    Get transaction history for a user by email.

    Retrieves all transactions for a specific user, with optional status filtering and pagination.
    Returns complete transaction records sorted by date (newest first).

    **Path Parameters:**
    - `email`: User email address

    **Query Parameters:**
    - `status`: Optional status filter (completed | pending | failed)
    - `limit`: Maximum results (1-100, default: 50)
    - `skip`: Number of results to skip (default: 0)

    **Response Example:**
    ```json
    {
        "success": true,
        "data": {
            "transactions": [
                {
                    "_id": "68fac0c78d81a68274ac140b",
                    "user_name": "John Doe",
                    "user_email": "john.doe@example.com",
                    "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
                    "number_of_units": 10,
                    "unit_type": "page",
                    "cost_per_unit": 0.15,
                    "source_language": "en",
                    "target_language": "es",
                    "square_transaction_id": "SQR-1EC28E70F10B4D9E",
                    "date": "2025-10-23T23:56:55.438Z",
                    "status": "completed",
                    "total_cost": 1.5,
                    "created_at": "2025-10-23T23:56:55.438Z",
                    "updated_at": "2025-10-23T23:56:55.438Z"
                }
            ],
            "count": 1,
            "limit": 50,
            "skip": 0,
            "filters": {
                "user_email": "john.doe@example.com",
                "status": "completed"
            }
        }
    }
    ```

    **Status Codes:**
    - **200**: Transaction history retrieved (may be empty array)
    - **400**: Invalid status filter
    - **422**: Invalid email format
    - **500**: Internal server error

    **cURL Examples:**
    ```bash
    # Get all transactions for user
    curl -X GET "http://localhost:8000/api/v1/user-transactions/user/john.doe@example.com"

    # Get only completed transactions
    curl -X GET "http://localhost:8000/api/v1/user-transactions/user/john.doe@example.com?status=completed"

    # Get first 10 transactions with pagination
    curl -X GET "http://localhost:8000/api/v1/user-transactions/user/john.doe@example.com?limit=10&skip=0"
    ```
    """
    try:
        logger.info(
            f"Retrieving transaction history for {email}, "
            f"status filter: {status_filter or 'all'}, limit={limit}, skip={skip}"
        )

        # Validate status filter if provided
        valid_statuses = ["completed", "pending", "failed"]
        if status_filter and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transaction status. Must be one of: {', '.join(valid_statuses)}"
            )

        # Build query filter
        match_stage = {"user_email": email}
        if status_filter:
            match_stage["status"] = status_filter

        # Query transactions with sorting (newest first) using aggregation
        from app.database.mongodb import database
        from bson.decimal128 import Decimal128

        pipeline = [
            {"$match": match_stage},
            {"$sort": {"date": -1}},  # Sort by date descending (newest first)
            {"$skip": skip},
            {"$limit": limit}
        ]

        # Execute aggregation
        transactions = await database.user_transactions.aggregate(pipeline).to_list(length=limit)

        # Convert ObjectIds and data types to JSON-serializable format
        for txn in transactions:
            if "_id" in txn:
                txn["_id"] = str(txn["_id"])

            # Convert Decimal128 fields to float
            for key, value in list(txn.items()):
                if isinstance(value, Decimal128):
                    txn[key] = float(value.to_decimal())

            # Convert datetime fields to ISO format strings
            datetime_fields = ["date", "created_at", "updated_at", "payment_date"]
            for field in datetime_fields:
                if field in txn and hasattr(txn[field], "isoformat"):
                    txn[field] = txn[field].isoformat()

        logger.info(f"Found {len(transactions)} transactions for {email}")

        return JSONResponse(content={
            "success": True,
            "data": {
                "transactions": transactions,
                "count": len(transactions),
                "limit": limit,
                "skip": skip,
                "filters": {
                    "user_email": email,
                    "status": status_filter
                }
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve transaction history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transaction history: {str(e)}"
        )


@router.get("/{square_transaction_id}")
async def get_transaction_by_id(
    square_transaction_id: str = Path(..., description="Square transaction ID")
):
    """
    Get transaction details by Square transaction ID.

    Retrieves complete transaction record including all 22 fields from the users_transactions collection.

    **Path Parameters:**
    - `square_transaction_id`: Square transaction ID (e.g., "SQR-1EC28E70F10B4D9E")

    **Response Example:**
    ```json
    {
        "success": true,
        "data": {
            "_id": "68fad3c2a0f41c24037c4810",
            "user_name": "John Doe",
            "user_email": "john.doe@example.com",
            "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
            "translated_url": "https://drive.google.com/file/d/1ABC_transl_document/view",
            "number_of_units": 10,
            "unit_type": "page",
            "cost_per_unit": 0.15,
            "source_language": "en",
            "target_language": "es",
            "square_transaction_id": "SQR-1EC28E70F10B4D9E",
            "date": "2025-10-23T23:56:55.438Z",
            "status": "completed",
            "total_cost": 1.5,
            "square_payment_id": "SQR-1EC28E70F10B4D9E",
            "amount_cents": 150,
            "currency": "USD",
            "payment_status": "COMPLETED",
            "refunds": [],
            "payment_date": "2025-10-23T23:56:55.438Z",
            "created_at": "2025-10-23T23:56:55.438Z",
            "updated_at": "2025-10-23T23:56:55.438Z"
        }
    }
    ```

    **Status Codes:**
    - **200**: Transaction found and returned
    - **404**: Transaction not found
    - **500**: Internal server error

    **cURL Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/user-transactions/SQR-1EC28E70F10B4D9E"
    ```
    """
    try:
        logger.info(f"Retrieving transaction: {square_transaction_id}")

        transaction = await get_user_transaction(square_transaction_id)

        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction not found: {square_transaction_id}"
            )

        # Convert ObjectId to string
        transaction["_id"] = str(transaction["_id"])

        return JSONResponse(content={
            "success": True,
            "data": transaction
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve transaction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transaction: {str(e)}"
        )


@router.patch("/{square_transaction_id}/payment-status")
async def update_transaction_payment_status(
    square_transaction_id: str = Path(..., description="Square transaction ID"),
    payment_status: str = Query(..., description="New payment status (APPROVED, COMPLETED, CANCELED, FAILED)")
):
    """
    Update payment status for a transaction.

    Updates the payment_status field in the users_transactions collection.

    **Path Parameters:**
    - `square_transaction_id`: Square transaction ID (e.g., "SQR-1EC28E70F10B4D9E")

    **Query Parameters:**
    - `payment_status`: New payment status (APPROVED | COMPLETED | CANCELED | FAILED)

    **Response Example:**
    ```json
    {
        "success": true,
        "message": "Payment status updated successfully",
        "data": {
            "square_transaction_id": "SQR-1EC28E70F10B4D9E",
            "payment_status": "COMPLETED",
            "updated_at": "2025-10-24T01:20:00.000Z"
        }
    }
    ```

    **Status Codes:**
    - **200**: Payment status updated successfully
    - **404**: Transaction not found
    - **400**: Invalid payment status (must be APPROVED, COMPLETED, CANCELED, or FAILED)
    - **500**: Internal server error

    **cURL Example:**
    ```bash
    curl -X PATCH "http://localhost:8000/api/v1/user-transactions/SQR-1EC28E70F10B4D9E/payment-status?payment_status=COMPLETED"
    ```
    """
    try:
        logger.info(
            f"Updating payment status for transaction {square_transaction_id} "
            f"to {payment_status}"
        )

        # Check if transaction exists
        transaction = await get_user_transaction(square_transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction not found: {square_transaction_id}"
            )

        # Update payment status
        success = await update_payment_status(square_transaction_id, payment_status)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update payment status"
            )

        logger.info(
            f"Payment status updated successfully for transaction {square_transaction_id}"
        )

        return JSONResponse(content={
            "success": True,
            "message": "Payment status updated successfully",
            "data": {
                "square_transaction_id": square_transaction_id,
                "payment_status": payment_status,
                "updated_at": datetime.utcnow().isoformat()
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update payment status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment status: {str(e)}"
        )
