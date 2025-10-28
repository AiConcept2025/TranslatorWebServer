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

from app.models.payment import (
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    RefundRequest,
    PaymentListResponse,
    PaymentListData,
    PaymentListFilters,
    PaymentListItem
)
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

    # Convert company_id if it's an ObjectId
    company_id = payment_doc.get("company_id")
    if isinstance(company_id, ObjectId):
        company_id = str(company_id)

    return {
        "_id": str(payment_doc["_id"]),
        "company_id": company_id,
        "company_name": payment_doc.get("company_name"),
        "user_email": payment_doc["user_email"],
        "square_payment_id": payment_doc["square_payment_id"],
        "amount": payment_doc["amount"],
        "currency": payment_doc["currency"],
        "payment_status": payment_doc["payment_status"],
        "refunds": payment_doc.get("refunds", []),
        "payment_date": payment_doc["payment_date"],
        "created_at": payment_doc["created_at"],
        "updated_at": payment_doc["updated_at"]
    }


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(payment_data: PaymentCreate):
    """
    Create a new payment record.

    This endpoint creates a payment record in the database with Square payment details.

    **Required Fields:**
    - `company_id`: Company identifier (e.g., "cmp_00123")
    - `company_name`: Company name
    - `user_email`: User email address
    - `square_payment_id`: Square payment ID
    - `amount`: Payment amount in cents

    **Optional Fields (with defaults):**
    - `currency`: "USD"
    - `payment_status`: "PENDING"
    - `payment_date`: Current timestamp

    **Request Example:**
    ```json
    {
        "company_id": "cmp_00123",
        "company_name": "Acme Health LLC",
        "user_email": "test5@yahoo.com",
        "square_payment_id": "payment_sq_1761244600756",
        "amount": 1299,
        "currency": "USD",
        "payment_status": "COMPLETED"
    }
    ```

    **Response Example:**
    ```json
    {
        "_id": "68fad3c2a0f41c24037c4810",
        "company_id": "cmp_00123",
        "company_name": "Acme Health LLC",
        "user_email": "test5@yahoo.com",
        "square_payment_id": "payment_sq_1761244600756",
        "amount": 1299,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "created_at": "2025-10-24T01:17:54.544Z",
        "updated_at": "2025-10-24T01:17:54.544Z",
        "payment_date": "2025-10-24T01:17:54.544Z"
    }
    ```

    **Status Codes:**
    - **201**: Payment created successfully
    - **400**: Invalid payment data
    - **500**: Internal server error

    **cURL Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/payments" \\
         -H "Content-Type: application/json" \\
         -d '{
           "company_id": "cmp_00123",
           "company_name": "Acme Health LLC",
           "user_email": "test5@yahoo.com",
           "square_payment_id": "payment_sq_1761244600756",
           "amount": 1299
         }'
    ```
    """
    try:
        logger.info(f"Creating payment for {payment_data.user_email}, Square ID: {payment_data.square_payment_id}")

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

        return JSONResponse(content=payment_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve payment by Square ID {square_payment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment: {str(e)}"
        )


@router.get(
    "/company/{company_id}",
    response_model=PaymentListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully retrieved company payments",
            "content": {
                "application/json": {
                    "examples": {
                        "multiple_payments": {
                            "summary": "Multiple completed payments",
                            "description": "Example response with multiple completed payments for a company",
                            "value": {
                                "success": True,
                                "data": {
                                    "payments": [
                                        {
                                            "_id": "68fad3c2a0f41c24037c4810",
                                            "company_id": "cmp_00123",
                                            "company_name": "Acme Health LLC",
                                            "user_email": "test5@yahoo.com",
                                            "square_payment_id": "payment_sq_1761244600756",
                                            "amount": 1299,
                                            "currency": "USD",
                                            "payment_status": "COMPLETED",
                                            "refunds": [],
                                            "payment_date": "2025-10-24T01:17:54.544Z",
                                            "created_at": "2025-10-24T01:17:54.544Z",
                                            "updated_at": "2025-10-24T01:17:54.544Z"
                                        },
                                        {
                                            "_id": "68fad3c2a0f41c24037c4811",
                                            "company_id": "cmp_00123",
                                            "company_name": "Acme Health LLC",
                                            "user_email": "admin@acmehealth.com",
                                            "square_payment_id": "payment_sq_1761268674",
                                            "amount": 2499,
                                            "currency": "USD",
                                            "payment_status": "COMPLETED",
                                            "refunds": [],
                                            "payment_date": "2025-10-24T02:30:15.123Z",
                                            "created_at": "2025-10-24T02:30:15.123Z",
                                            "updated_at": "2025-10-24T02:30:15.123Z"
                                        },
                                        {
                                            "_id": "68fad3c2a0f41c24037c4812",
                                            "company_id": "cmp_00123",
                                            "company_name": "Acme Health LLC",
                                            "user_email": "billing@acmehealth.com",
                                            "square_payment_id": "payment_sq_1761278900",
                                            "amount": 999,
                                            "currency": "USD",
                                            "payment_status": "COMPLETED",
                                            "refunds": [],
                                            "payment_date": "2025-10-24T03:45:00.000Z",
                                            "created_at": "2025-10-24T03:45:00.000Z",
                                            "updated_at": "2025-10-24T03:45:00.000Z"
                                        }
                                    ],
                                    "count": 3,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "company_id": "cmp_00123",
                                        "status": "COMPLETED"
                                    }
                                }
                            }
                        },
                        "empty_result": {
                            "summary": "No payments found",
                            "description": "Response when no payments match the query filters",
                            "value": {
                                "success": True,
                                "data": {
                                    "payments": [],
                                    "count": 0,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "company_id": "cmp_00999",
                                        "status": None
                                    }
                                }
                            }
                        },
                        "with_refunds": {
                            "summary": "Payment with refund",
                            "description": "Example showing a payment that has been partially refunded",
                            "value": {
                                "success": True,
                                "data": {
                                    "payments": [
                                        {
                                            "_id": "68fad3c2a0f41c24037c4820",
                                            "company_id": "cmp_00123",
                                            "company_name": "Acme Health LLC",
                                            "user_email": "refund@example.com",
                                            "square_payment_id": "payment_sq_1761300000",
                                            "amount": 5000,
                                            "currency": "USD",
                                            "payment_status": "REFUNDED",
                                            "refunds": [
                                                {
                                                    "refund_id": "rfn_01J2M9ABCD",
                                                    "amount": 500,
                                                    "currency": "USD",
                                                    "status": "COMPLETED",
                                                    "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62",
                                                    "created_at": "2025-10-24T05:00:00.000Z"
                                                }
                                            ],
                                            "payment_date": "2025-10-24T04:00:00.000Z",
                                            "created_at": "2025-10-24T04:00:00.000Z",
                                            "updated_at": "2025-10-24T05:00:00.000Z"
                                        }
                                    ],
                                    "count": 1,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "company_id": "cmp_00123",
                                        "status": "REFUNDED"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_company_id": {
                            "summary": "Invalid company_id format",
                            "value": {
                                "detail": "Invalid company identifier format"
                            }
                        },
                        "invalid_status": {
                            "summary": "Invalid status filter",
                            "value": {
                                "detail": "Invalid payment status. Must be one of: COMPLETED, PENDING, FAILED, REFUNDED"
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "Company not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Company not found: cmp_00999"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to retrieve company payments: Database connection error"
                    }
                }
            }
        }
    }
)
async def get_company_payments(
    company_id: str = Path(
        ...,
        description="Company identifier (e.g., cmp_00123)",
        example="cmp_00123"
    ),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by payment status. Valid values: COMPLETED, PENDING, FAILED, REFUNDED",
        example="COMPLETED",
        alias="status"
    ),
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Maximum number of results to return (1-100)",
        example=50
    ),
    skip: int = Query(
        0,
        ge=0,
        description="Number of results to skip for pagination",
        example=0
    )
):
    """
    Get all payments for a company with filtering and pagination.

    Retrieves a list of payment records associated with a specific company ID.
    Results can be filtered by payment status and paginated using limit/skip parameters.

    ## Path Parameters
    - **company_id**: Company identifier (format: cmp_XXXXX)

    ## Query Parameters
    - **status** *(optional)*: Filter payments by status
        - `COMPLETED`: Successfully processed payments
        - `PENDING`: Payments awaiting processing
        - `FAILED`: Failed payment attempts
        - `REFUNDED`: Payments that have been refunded (fully or partially)
    - **limit** *(default: 50)*: Maximum number of records to return (1-100)
    - **skip** *(default: 0)*: Number of records to skip (for pagination)

    ## Response Structure
    Returns a standardized response wrapper containing:
    - **success**: Boolean indicating request success
    - **data**: Object containing:
        - **payments**: Array of payment records
        - **count**: Number of payments in this response
        - **limit**: Limit value used
        - **skip**: Skip value used
        - **filters**: Applied filter values

    ## Payment Record Fields
    Each payment record includes:
    - **_id**: MongoDB ObjectId (24-character hex string)
    - **company_id**: Company identifier
    - **company_name**: Full company name
    - **user_email**: Email of user who made the payment
    - **square_payment_id**: Square payment identifier
    - **amount**: Payment amount in cents (e.g., 1299 = $12.99)
    - **currency**: Currency code (ISO 4217, e.g., USD)
    - **payment_status**: Current payment status
    - **refunds**: Array of refund objects (empty if no refunds)
    - **payment_date**: Payment processing date (ISO 8601)
    - **created_at**: Record creation timestamp (ISO 8601)
    - **updated_at**: Last update timestamp (ISO 8601)

    ## Usage Examples

    ### Get all completed payments
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/company/cmp_00123?status=COMPLETED&limit=20"
    ```

    ### Get second page of payments (pagination)
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/company/cmp_00123?skip=20&limit=20"
    ```

    ### Get all payments regardless of status
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/company/cmp_00123"
    ```

    ### Filter by refunded payments only
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/company/cmp_00123?status=REFUNDED"
    ```

    ## Notes
    - Returns empty array if no payments match the criteria
    - All datetime fields are returned in ISO 8601 format
    - Amount is always in cents (divide by 100 for dollar amount)
    - Refunds array shows detailed refund history when applicable
    """
    try:
        print(f"[PAYMENTS DEBUG] Fetching payments for company {company_id}, status={status_filter}, limit={limit}, skip={skip}")
        logger.info(f"Fetching payments for company {company_id}, status={status_filter}, limit={limit}, skip={skip}")

        payments = await payment_repository.get_payments_by_company(
            company_id=company_id,
            status=status_filter,
            limit=limit,
            skip=skip
        )

        print(f"[PAYMENTS DEBUG] Retrieved {len(payments)} payments from repository")
        logger.info(f"Retrieved {len(payments)} payments from repository")

        # Helper function to recursively convert ObjectIds and datetimes
        def convert_doc(obj):
            """Recursively convert ObjectIds and datetimes to JSON-serializable types."""
            if isinstance(obj, ObjectId):
                return str(obj)
            elif isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {key: convert_doc(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_doc(item) for item in obj]
            else:
                return obj

        # Convert all payments using recursive converter
        for idx, payment in enumerate(payments):
            print(f"[PAYMENTS DEBUG] Processing payment {idx + 1}")
            # Apply recursive conversion
            payments[idx] = convert_doc(payment)
            print(f"[PAYMENTS DEBUG] Payment {idx + 1} converted successfully")

        logger.info(f"Found {len(payments)} payments for company {company_id}, creating response")

        # Try to serialize the response before returning it
        import json
        try:
            response_content = {
                "success": True,
                "data": {
                    "payments": payments,
                    "count": len(payments),
                    "limit": limit,
                    "skip": skip,
                    "filters": {
                        "company_id": company_id,
                        "status": status_filter
                    }
                }
            }
            # Test serialization
            test_json = json.dumps(response_content, default=str)
            logger.info(f"Response serialization successful, size: {len(test_json)} bytes")
        except Exception as json_err:
            logger.error(f"JSON serialization test failed: {json_err}")
            logger.error(f"Problematic data: {payments}")
            raise

        return JSONResponse(content=response_content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve payments for company {company_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve company payments: {str(e)}"
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
    refund_request: RefundRequest = None
):
    """
    Process a payment refund.

    Marks a payment as refunded and records refund details in the refunds array.

    **Path Parameters:**
    - `square_payment_id`: Square payment ID (e.g., "payment_sq_1761268674_852e5fe3")

    **Request Body:**
    ```json
    {
        "refund_id": "rfn_01J2M9ABCD",
        "amount": 500,
        "currency": "USD",
        "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
    }
    ```

    **Response Example:**
    ```json
    {
        "success": true,
        "message": "Refund processed: 500 cents",
        "data": {
            "payment": {
                "_id": "68fad3c2a0f41c24037c4810",
                "company_id": "cmp_00123",
                "company_name": "Acme Health LLC",
                "user_email": "test5@yahoo.com",
                "square_payment_id": "payment_sq_1761268674_852e5fe3",
                "amount": 1299,
                "currency": "USD",
                "payment_status": "REFUNDED",
                "refunds": [
                    {
                        "refund_id": "rfn_01J2M9ABCD",
                        "amount": 500,
                        "currency": "USD",
                        "status": "COMPLETED",
                        "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62",
                        "created_at": "2025-10-24T01:15:43.453Z"
                    }
                ],
                "created_at": "2025-10-24T01:17:54.544Z",
                "updated_at": "2025-10-24T01:17:54.544Z",
                "payment_date": "2025-10-24T01:17:54.544Z"
            },
            "refund": {
                "refund_id": "rfn_01J2M9ABCD",
                "amount": 500,
                "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
            }
        }
    }
    ```

    **Status Codes:**
    - **200**: Refund processed successfully
    - **400**: Invalid refund parameters or refund amount exceeds payment amount
    - **404**: Payment not found
    - **500**: Internal server error

    **cURL Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/payments/payment_sq_1761268674_852e5fe3/refund" \\
         -H "Content-Type: application/json" \\
         -d '{
           "refund_id": "rfn_01J2M9ABCD",
           "amount": 500,
           "currency": "USD",
           "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
         }'
    ```
    """
    try:
        logger.info(f"Processing refund for payment {square_payment_id}, amount: {refund_request.amount} cents")

        # Validate refund amount
        if refund_request.amount <= 0:
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
        if refund_request.amount > payment_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Refund amount ({refund_request.amount}) exceeds payment amount ({payment_amount})"
            )

        # Process refund
        refunded = await payment_repository.process_refund(
            square_payment_id=square_payment_id,
            refund_id=refund_request.refund_id,
            refund_amount=refund_request.amount,
            refund_reason=None
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

        return JSONResponse(content={
            "success": True,
            "message": f"Refund processed: {refund_request.amount} cents",
            "data": {
                "payment": payment_doc,
                "refund": {
                    "refund_id": refund_request.refund_id,
                    "amount": refund_request.amount,
                    "idempotency_key": refund_request.idempotency_key
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
