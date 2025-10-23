"""
Payment Management API Router.

This module provides comprehensive payment management endpoints for:
- Creating and retrieving payment records
- Querying payments by various filters (ID, company, user, email)
- Processing refunds
- Generating payment statistics

Uses the existing payment_repository for database operations.
"""

from fastapi import APIRouter, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pydantic import EmailStr
import logging

from app.models.payment import PaymentCreate, PaymentUpdate, PaymentResponse
from app.services.payment_repository import payment_repository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payments", tags=["Payment Management"])


def validate_object_id(object_id: str, field_name: str = "ID") -> None:
    """
    Validate that a string is a valid MongoDB ObjectId.

    Args:
        object_id: String to validate
        field_name: Name of the field (for error messages)

    Raises:
        HTTPException: If object_id is not a valid ObjectId
    """
    try:
        ObjectId(object_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} format: {object_id}"
        )


def payment_doc_to_response(payment_doc: dict) -> dict:
    """
    Convert a MongoDB payment document to PaymentResponse format.

    Args:
        payment_doc: Payment document from MongoDB

    Returns:
        Dictionary compatible with PaymentResponse schema
    """
    if not payment_doc:
        return None

    return {
        "_id": str(payment_doc["_id"]),
        "company_id": payment_doc.get("company_id"),
        "subscription_id": payment_doc.get("subscription_id"),
        "user_id": payment_doc.get("user_id"),
        "user_email": payment_doc["user_email"],
        "square_payment_id": payment_doc["square_payment_id"],
        "amount": payment_doc["amount"],
        "currency": payment_doc["currency"],
        "payment_status": payment_doc["payment_status"],
        "payment_date": payment_doc["payment_date"],
        "created_at": payment_doc["created_at"],
        "updated_at": payment_doc["updated_at"]
    }


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(payment_data: PaymentCreate):
    """
    Create a new payment record.

    This endpoint creates a payment record in the database with comprehensive
    payment details including Square integration data.

    **Request Body:**
    ```json
    {
        "user_email": "user@example.com",
        "square_payment_id": "sq_payment_abc123",
        "amount": 10600,
        "currency": "USD",
        "payment_status": "completed",
        "company_id": "68ec42a48ca6a1781d9fe5c2",
        "card_brand": "VISA",
        "last_4_digits": "4242"
    }
    ```

    **Response:**
    - **201**: Payment created successfully
    - **400**: Invalid payment data
    - **500**: Internal server error

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/payments" \\
         -H "Content-Type: application/json" \\
         -d '{"user_email":"user@example.com","square_payment_id":"sq_pay_123","amount":10600,"payment_status":"completed"}'
    ```
    """
    try:
        logger.info(f"Creating payment for {payment_data.user_email}, Square ID: {payment_data.square_payment_id}")

        # Validate company_id if provided
        if payment_data.company_id:
            validate_object_id(payment_data.company_id, "company_id")

        # Create payment
        payment_id = await payment_repository.create_payment(payment_data)

        # Retrieve created payment
        payment_doc = await payment_repository.get_payment_by_id(payment_id)

        if not payment_doc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment created but could not be retrieved"
            )

        logger.info(f"Payment created successfully: {payment_id}")
        return payment_doc_to_response(payment_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create payment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment: {str(e)}"
        )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment_by_id(
    payment_id: str = Path(..., description="MongoDB ObjectId of the payment")
):
    """
    Get payment by MongoDB ObjectId.

    Retrieves a single payment record using its MongoDB _id.

    **Path Parameters:**
    - `payment_id`: MongoDB ObjectId (24 character hex string)

    **Response:**
    - **200**: Payment found and returned
    - **400**: Invalid payment_id format
    - **404**: Payment not found
    - **500**: Internal server error

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/68ec42a48ca6a1781d9fe5c2"
    ```
    """
    try:
        validate_object_id(payment_id, "payment_id")

        logger.info(f"Fetching payment by ID: {payment_id}")
        payment_doc = await payment_repository.get_payment_by_id(payment_id)

        if not payment_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found: {payment_id}"
            )

        return payment_doc_to_response(payment_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve payment {payment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment: {str(e)}"
        )


@router.get("/square/{square_payment_id}")
async def get_payment_by_square_id(
    square_payment_id: str = Path(..., description="Square payment ID")
):
    """
    Get payment by Square payment ID.

    Retrieves a payment record using the Square payment identifier.

    **Path Parameters:**
    - `square_payment_id`: Square payment ID (e.g., "sq_payment_abc123")

    **Response:**
    - **200**: Payment found and returned (full payment details)
    - **404**: Payment not found
    - **500**: Internal server error

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/square/sq_payment_abc123"
    ```
    """
    try:
        logger.info(f"Fetching payment by Square ID: {square_payment_id}")
        payment_doc = await payment_repository.get_payment_by_square_id(square_payment_id)

        if not payment_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found for Square ID: {square_payment_id}"
            )

        # Return full payment document (not just PaymentResponse fields)
        payment_doc["_id"] = str(payment_doc["_id"])
        if payment_doc.get("company_id"):
            payment_doc["company_id"] = str(payment_doc["company_id"])
        if payment_doc.get("subscription_id"):
            payment_doc["subscription_id"] = str(payment_doc["subscription_id"])

        return JSONResponse(content=payment_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve payment by Square ID {square_payment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment: {str(e)}"
        )


@router.get("/company/{company_id}")
async def get_company_payments(
    company_id: str = Path(..., description="Company ObjectId"),
    status: Optional[str] = Query(None, description="Filter by payment status (completed, pending, failed, refunded)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip (for pagination)")
):
    """
    Get all payments for a company.

    Retrieves payments associated with a specific company, with optional
    filtering by payment status and pagination support.

    **Path Parameters:**
    - `company_id`: Company MongoDB ObjectId

    **Query Parameters:**
    - `status`: Filter by payment status (optional)
        - `completed`: Successfully processed payments
        - `pending`: Payments awaiting processing
        - `failed`: Failed payment attempts
        - `refunded`: Refunded payments
    - `limit`: Maximum results (1-100, default: 50)
    - `skip`: Results to skip for pagination (default: 0)

    **Response:**
    - **200**: List of payments (may be empty)
    - **400**: Invalid company_id or parameters
    - **500**: Internal server error

    **Example:**
    ```bash
    # Get all completed payments for a company
    curl -X GET "http://localhost:8000/api/v1/payments/company/68ec42a48ca6a1781d9fe5c2?status=completed&limit=20"

    # Get second page of payments
    curl -X GET "http://localhost:8000/api/v1/payments/company/68ec42a48ca6a1781d9fe5c2?skip=20&limit=20"
    ```
    """
    try:
        validate_object_id(company_id, "company_id")

        logger.info(f"Fetching payments for company {company_id}, status={status}, limit={limit}, skip={skip}")

        payments = await payment_repository.get_payments_by_company(
            company_id=company_id,
            status=status,
            limit=limit,
            skip=skip
        )

        # Convert ObjectIds to strings
        for payment in payments:
            payment["_id"] = str(payment["_id"])
            if payment.get("company_id"):
                payment["company_id"] = str(payment["company_id"])
            if payment.get("subscription_id"):
                payment["subscription_id"] = str(payment["subscription_id"])

        logger.info(f"Found {len(payments)} payments for company {company_id}")

        return JSONResponse(content={
            "success": True,
            "data": {
                "payments": payments,
                "count": len(payments),
                "limit": limit,
                "skip": skip,
                "filters": {
                    "company_id": company_id,
                    "status": status
                }
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve payments for company {company_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve company payments: {str(e)}"
        )


@router.get("/user/{user_id}")
async def get_user_payments(
    user_id: str = Path(..., description="User ObjectId or identifier"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip (for pagination)")
):
    """
    Get all payments for a user.

    Retrieves payments associated with a specific user by user_id.

    **Path Parameters:**
    - `user_id`: User identifier (ObjectId or string)

    **Query Parameters:**
    - `limit`: Maximum results (1-100, default: 50)
    - `skip`: Results to skip for pagination (default: 0)

    **Response:**
    - **200**: List of payments (may be empty)
    - **500**: Internal server error

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/user/68ec42a48ca6a1781d9fe5c5?limit=20"
    ```
    """
    try:
        logger.info(f"Fetching payments for user {user_id}, limit={limit}, skip={skip}")

        payments = await payment_repository.get_payments_by_user(
            user_id=user_id,
            limit=limit,
            skip=skip
        )

        # Convert ObjectIds to strings
        for payment in payments:
            payment["_id"] = str(payment["_id"])
            if payment.get("company_id"):
                payment["company_id"] = str(payment["company_id"])
            if payment.get("subscription_id"):
                payment["subscription_id"] = str(payment["subscription_id"])

        logger.info(f"Found {len(payments)} payments for user {user_id}")

        return JSONResponse(content={
            "success": True,
            "data": {
                "payments": payments,
                "count": len(payments),
                "limit": limit,
                "skip": skip,
                "user_id": user_id
            }
        })

    except Exception as e:
        logger.error(f"Failed to retrieve payments for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user payments: {str(e)}"
        )


@router.get("/email/{email}")
async def get_payments_by_email(
    email: EmailStr = Path(..., description="User email address"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip (for pagination)")
):
    """
    Get all payments by user email.

    Retrieves payments associated with a specific email address.

    **Path Parameters:**
    - `email`: User email address

    **Query Parameters:**
    - `limit`: Maximum results (1-100, default: 50)
    - `skip`: Results to skip for pagination (default: 0)

    **Response:**
    - **200**: List of payments (may be empty)
    - **422**: Invalid email format
    - **500**: Internal server error

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/email/user@example.com"
    ```
    """
    try:
        logger.info(f"Fetching payments for email {email}, limit={limit}, skip={skip}")

        payments = await payment_repository.get_payments_by_email(
            email=email,
            limit=limit,
            skip=skip
        )

        # Convert ObjectIds to strings
        for payment in payments:
            payment["_id"] = str(payment["_id"])
            if payment.get("company_id"):
                payment["company_id"] = str(payment["company_id"])
            if payment.get("subscription_id"):
                payment["subscription_id"] = str(payment["subscription_id"])

        logger.info(f"Found {len(payments)} payments for email {email}")

        return JSONResponse(content={
            "success": True,
            "data": {
                "payments": payments,
                "count": len(payments),
                "limit": limit,
                "skip": skip,
                "email": email
            }
        })

    except Exception as e:
        logger.error(f"Failed to retrieve payments for email {email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payments by email: {str(e)}"
        )


@router.patch("/{square_payment_id}")
async def update_payment(
    square_payment_id: str = Path(..., description="Square payment ID"),
    update_data: PaymentUpdate = None
):
    """
    Update a payment record.

    Updates payment information such as status, refund details, or notes.

    **Path Parameters:**
    - `square_payment_id`: Square payment ID

    **Request Body:**
    ```json
    {
        "payment_status": "refunded",
        "refund_id": "sq_refund_xyz789",
        "refund_reason": "Customer request",
        "notes": "Full refund processed"
    }
    ```

    **Response:**
    - **200**: Payment updated successfully
    - **400**: Invalid update data
    - **404**: Payment not found
    - **500**: Internal server error

    **Example:**
    ```bash
    curl -X PATCH "http://localhost:8000/api/v1/payments/sq_payment_abc123" \\
         -H "Content-Type: application/json" \\
         -d '{"payment_status":"completed","notes":"Payment verified"}'
    ```
    """
    try:
        logger.info(f"Updating payment {square_payment_id}")

        # Check if payment exists
        existing_payment = await payment_repository.get_payment_by_square_id(square_payment_id)
        if not existing_payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found: {square_payment_id}"
            )

        # Update payment
        updated = await payment_repository.update_payment(square_payment_id, update_data)

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment update failed"
            )

        # Retrieve updated payment
        payment_doc = await payment_repository.get_payment_by_square_id(square_payment_id)

        logger.info(f"Payment {square_payment_id} updated successfully")

        # Convert ObjectIds to strings
        payment_doc["_id"] = str(payment_doc["_id"])
        if payment_doc.get("company_id"):
            payment_doc["company_id"] = str(payment_doc["company_id"])
        if payment_doc.get("subscription_id"):
            payment_doc["subscription_id"] = str(payment_doc["subscription_id"])

        return JSONResponse(content={
            "success": True,
            "message": "Payment updated successfully",
            "data": payment_doc
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update payment {square_payment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment: {str(e)}"
        )


@router.post("/{square_payment_id}/refund")
async def process_refund(
    square_payment_id: str = Path(..., description="Square payment ID"),
    refund_id: str = Query(..., description="Square refund ID"),
    refund_amount: int = Query(..., description="Refund amount in cents"),
    refund_reason: Optional[str] = Query(None, description="Reason for refund")
):
    """
    Process a payment refund.

    Marks a payment as refunded and records refund details.

    **Path Parameters:**
    - `square_payment_id`: Square payment ID

    **Query Parameters:**
    - `refund_id`: Square refund ID (required)
    - `refund_amount`: Refund amount in cents (required)
    - `refund_reason`: Reason for refund (optional)

    **Response:**
    - **200**: Refund processed successfully
    - **400**: Invalid refund parameters
    - **404**: Payment not found
    - **500**: Internal server error

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/payments/sq_payment_abc123/refund?refund_id=sq_refund_xyz&refund_amount=10600&refund_reason=Customer+request"
    ```
    """
    try:
        logger.info(f"Processing refund for payment {square_payment_id}, amount: {refund_amount} cents")

        # Validate refund amount
        if refund_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refund amount must be greater than 0"
            )

        # Check if payment exists
        existing_payment = await payment_repository.get_payment_by_square_id(square_payment_id)
        if not existing_payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found: {square_payment_id}"
            )

        # Check if refund amount exceeds payment amount
        payment_amount = existing_payment.get("amount", 0)
        if refund_amount > payment_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Refund amount ({refund_amount}) exceeds payment amount ({payment_amount})"
            )

        # Process refund
        refunded = await payment_repository.process_refund(
            square_payment_id=square_payment_id,
            refund_id=refund_id,
            refund_amount=refund_amount,
            refund_reason=refund_reason
        )

        if not refunded:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Refund processing failed"
            )

        # Retrieve updated payment
        payment_doc = await payment_repository.get_payment_by_square_id(square_payment_id)

        logger.info(f"Refund processed successfully for payment {square_payment_id}")

        # Convert ObjectIds to strings
        payment_doc["_id"] = str(payment_doc["_id"])
        if payment_doc.get("company_id"):
            payment_doc["company_id"] = str(payment_doc["company_id"])
        if payment_doc.get("subscription_id"):
            payment_doc["subscription_id"] = str(payment_doc["subscription_id"])

        return JSONResponse(content={
            "success": True,
            "message": f"Refund processed: {refund_amount} cents",
            "data": {
                "payment": payment_doc,
                "refund": {
                    "refund_id": refund_id,
                    "refund_amount": refund_amount,
                    "refund_reason": refund_reason,
                    "refund_date": payment_doc.get("refund_date")
                }
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process refund for payment {square_payment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process refund: {str(e)}"
        )


@router.get("/company/{company_id}/stats")
async def get_company_payment_stats(
    company_id: str = Path(..., description="Company ObjectId"),
    start_date: Optional[datetime] = Query(None, description="Start date filter (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (ISO 8601)")
):
    """
    Get payment statistics for a company.

    Retrieves aggregated payment statistics including total payments,
    amounts, refunds, and success/failure rates.

    **Path Parameters:**
    - `company_id`: Company MongoDB ObjectId

    **Query Parameters:**
    - `start_date`: Filter payments from this date (ISO 8601 format, optional)
    - `end_date`: Filter payments until this date (ISO 8601 format, optional)

    **Response:**
    - **200**: Payment statistics
    - **400**: Invalid company_id or date format
    - **500**: Internal server error

    **Response Format:**
    ```json
    {
        "success": true,
        "data": {
            "company_id": "68ec42a48ca6a1781d9fe5c2",
            "total_payments": 125,
            "total_amount_cents": 1325000,
            "total_amount_dollars": 13250.00,
            "total_refunded_cents": 21200,
            "total_refunded_dollars": 212.00,
            "completed_payments": 120,
            "failed_payments": 5,
            "success_rate": 96.0,
            "date_range": {
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-10-22T00:00:00Z"
            }
        }
    }
    ```

    **Example:**
    ```bash
    # Get all-time stats
    curl -X GET "http://localhost:8000/api/v1/payments/company/68ec42a48ca6a1781d9fe5c2/stats"

    # Get stats for date range
    curl -X GET "http://localhost:8000/api/v1/payments/company/68ec42a48ca6a1781d9fe5c2/stats?start_date=2025-01-01T00:00:00Z&end_date=2025-12-31T23:59:59Z"
    ```
    """
    try:
        validate_object_id(company_id, "company_id")

        logger.info(f"Fetching payment stats for company {company_id}, start={start_date}, end={end_date}")

        stats = await payment_repository.get_payment_stats_by_company(
            company_id=company_id,
            start_date=start_date,
            end_date=end_date
        )

        # Calculate success rate
        total_payments = stats.get("total_payments", 0)
        completed_payments = stats.get("completed_payments", 0)
        success_rate = (completed_payments / total_payments * 100) if total_payments > 0 else 0.0

        logger.info(f"Retrieved stats for company {company_id}: {total_payments} total payments")

        return JSONResponse(content={
            "success": True,
            "data": {
                "company_id": company_id,
                **stats,
                "success_rate": round(success_rate, 2),
                "date_range": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve stats for company {company_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment statistics: {str(e)}"
        )
