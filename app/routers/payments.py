"""
Payment Management API Router.

This module provides comprehensive payment management endpoints for:
- Creating and retrieving payment records
- Querying payments by various filters (ID, company, user, email)
- Processing refunds
- Generating payment statistics

Uses the existing payment_repository for database operations.
"""

from fastapi import APIRouter, HTTPException, Query, Path, status, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
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
    PaymentListItem,
    AllPaymentsResponse,
    AllPaymentsData,
    AllPaymentsFilters,
    SubscriptionPaymentCreate
)
from app.services.payment_repository import payment_repository
from app.services.payment_application_service import payment_application_service, PaymentApplicationError
from app.middleware.auth_middleware import get_admin_user
from app.database.mongodb import database

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

    # Convert company_name if needed
    company_name = payment_doc.get("company_name")

    return {
        "_id": str(payment_doc["_id"]),
        "company_name": company_name,
        "user_email": payment_doc["user_email"],
        "stripe_payment_intent_id": payment_doc["stripe_payment_intent_id"],
        "amount": payment_doc["amount"],
        "currency": payment_doc["currency"],
        "payment_status": payment_doc["payment_status"],
        "refunds": payment_doc.get("refunds", []),
        "payment_date": payment_doc["payment_date"],
        "created_at": payment_doc["created_at"],
        "updated_at": payment_doc["updated_at"]
    }


@router.get(
    "/",
    response_model=AllPaymentsResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully retrieved all payments (admin only)",
            "content": {
                "application/json": {
                    "examples": {
                        "all_payments": {
                            "summary": "All payments across companies",
                            "description": "Example response showing payments from multiple companies",
                            "value": {
                                "success": True,
                                "data": {
                                    "payments": [
                                        {
                                            "_id": "68fad3c2a0f41c24037c4810",
                                            "company_name": "Acme Health LLC",
                                            "user_email": "test5@yahoo.com",
                                            "stripe_payment_intent_id": "payment_sq_1761244600756",
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
                                            "company_name": "TechCorp Inc",
                                            "user_email": "admin@techcorp.com",
                                            "stripe_payment_intent_id": "payment_sq_1761268674",
                                            "amount": 2499,
                                            "currency": "USD",
                                            "payment_status": "COMPLETED",
                                            "refunds": [],
                                            "payment_date": "2025-10-24T02:30:15.123Z",
                                            "created_at": "2025-10-24T02:30:15.123Z",
                                            "updated_at": "2025-10-24T02:30:15.123Z"
                                        }
                                    ],
                                    "count": 2,
                                    "total": 2,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "status": None,
                                        "company_name": None
                                    }
                                }
                            }
                        },
                        "filtered_by_status": {
                            "summary": "Filter by payment status",
                            "description": "Only show completed payments",
                            "value": {
                                "success": True,
                                "data": {
                                    "payments": [
                                        {
                                            "_id": "68fad3c2a0f41c24037c4810",
                                            "company_name": "Acme Health LLC",
                                            "user_email": "test5@yahoo.com",
                                            "stripe_payment_intent_id": "payment_sq_1761244600756",
                                            "amount": 1299,
                                            "currency": "USD",
                                            "payment_status": "COMPLETED",
                                            "refunds": [],
                                            "payment_date": "2025-10-24T01:17:54.544Z",
                                            "created_at": "2025-10-24T01:17:54.544Z",
                                            "updated_at": "2025-10-24T01:17:54.544Z"
                                        }
                                    ],
                                    "count": 1,
                                    "total": 120,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "status": "COMPLETED",
                                        "company_name": None
                                    }
                                }
                            }
                        },
                        "empty_result": {
                            "summary": "No payments found",
                            "description": "Response when no payments match the filters",
                            "value": {
                                "success": True,
                                "data": {
                                    "payments": [],
                                    "count": 0,
                                    "total": 0,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "status": "PENDING",
                                        "company_name": None
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized - Missing or invalid authentication",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authorization header missing"
                    }
                }
            }
        },
        403: {
            "description": "Forbidden - Admin permissions required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Admin permissions required"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid payment status. Must be one of: COMPLETED, PENDING, FAILED, REFUNDED"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to retrieve payments: Database connection error"
                    }
                }
            }
        }
    }
)
async def get_all_payments(
    admin_user: Dict[str, Any] = Depends(get_admin_user),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by payment status. Valid values: COMPLETED, PENDING, FAILED, REFUNDED",
        example="COMPLETED",
        alias="status"
    ),
    company_name: Optional[str] = Query(
        None,
        description="Filter by company name (e.g., Acme Health LLC)",
        example="Acme Health LLC"
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
    ),
    sort_by: str = Query(
        "payment_date",
        description="Field to sort by",
        example="payment_date"
    ),
    sort_order: str = Query(
        "desc",
        description="Sort order: asc or desc",
        pattern="^(asc|desc)$",
        example="desc"
    )
):
    """
    Get all subscription payments (Admin Only).

    This endpoint retrieves all payment records across all companies for admin dashboard viewing.
    Requires admin authentication via Bearer token.

    ## Authentication
    **Required:** Admin user with Bearer token in Authorization header

    ## Query Parameters
    - **status** *(optional)*: Filter payments by status
        - `COMPLETED`: Successfully processed payments
        - `PENDING`: Payments awaiting processing
        - `FAILED`: Failed payment attempts
        - `REFUNDED`: Payments that have been refunded (fully or partially)
    - **company_name** *(optional)*: Filter by specific company name
    - **limit** *(default: 50)*: Maximum number of records to return (1-100)
    - **skip** *(default: 0)*: Number of records to skip (for pagination)
    - **sort_by** *(default: payment_date)*: Field to sort results by
    - **sort_order** *(default: desc)*: Sort direction (asc or desc)

    ## Response Structure
    Returns a standardized response wrapper containing:
    - **success**: Boolean indicating request success
    - **data**: Object containing:
        - **payments**: Array of payment records
        - **count**: Number of payments in this response
        - **total**: Total number of payments matching filters (across all pages)
        - **limit**: Limit value used
        - **skip**: Skip value used
        - **filters**: Applied filter values

    ## Payment Record Fields
    Each payment record includes:
    - **_id**: MongoDB ObjectId (24-character hex string)
    - **stripe_payment_intent_id**: Square payment identifier
    - **stripe_invoice_id**: Square order identifier (if available)
    - **stripe_customer_id**: Square customer identifier (if available)
    - **company_name**: Full company name
    - **subscription_id**: Subscription identifier (if available)
    - **user_id**: User identifier
    - **user_email**: Email of user who made the payment
    - **amount**: Payment amount in cents (e.g., 1299 = $12.99)
    - **currency**: Currency code (ISO 4217, e.g., USD)
    - **payment_status**: Current payment status
    - **payment_date**: Payment processing date (ISO 8601)
    - **payment_method**: Payment method type (if available)
    - **card_brand**: Card brand (e.g., Visa, Mastercard) if card payment
    - **card_last_4**: Last 4 digits of card (if card payment)
    - **receipt_url**: URL to payment receipt (if available)
    - **refunds**: Array of refund objects (empty if no refunds)
    - **created_at**: Record creation timestamp (ISO 8601)
    - **updated_at**: Last update timestamp (ISO 8601)

    ## Usage Examples

    ### Get all payments (first 50)
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments" \\
         -H "Authorization: Bearer {admin_token}"
    ```

    ### Filter by status (completed only)
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED" \\
         -H "Authorization: Bearer {admin_token}"
    ```

    ### Filter by company
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments?company_name=Acme%20Health%20LLC" \\
         -H "Authorization: Bearer {admin_token}"
    ```

    ### Combine filters with pagination
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED&company_name=Acme%20Health%20LLC&limit=20&skip=20" \\
         -H "Authorization: Bearer {admin_token}"
    ```

    ### Sort by amount (ascending)
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments?sort_by=amount&sort_order=asc&limit=10" \\
         -H "Authorization: Bearer {admin_token}"
    ```

    ## Notes
    - Admin authentication is required - returns 401/403 if not authenticated or not admin
    - Returns empty array if no payments match the criteria
    - All datetime fields are returned in ISO 8601 format
    - Amount is always in cents (divide by 100 for dollar amount)
    - Total count reflects all matching records, not just the current page
    - Refunds array shows detailed refund history when applicable
    - Use pagination (skip/limit) for large datasets
    """
    try:
        logger.info(
            f"[ADMIN] Fetching all payments - Admin: {admin_user.get('email')}, "
            f"status={status_filter}, company={company_name}, limit={limit}, skip={skip}, "
            f"sort_by={sort_by}, sort_order={sort_order}"
        )

        # Validate status filter if provided
        valid_statuses = ["COMPLETED", "PENDING", "FAILED", "REFUNDED"]
        if status_filter and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid payment status. Must be one of: {', '.join(valid_statuses)}"
            )

        # Validate sort_order
        if sort_order not in ["asc", "desc"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort_order. Must be 'asc' or 'desc'"
            )

        # Get payments with total count from repository
        payments, total_count = await payment_repository.get_all_payments(
            status=status_filter,
            company_name=company_name,
            limit=limit,
            skip=skip,
            sort_by=sort_by,
            sort_order=sort_order
        )

        logger.info(
            f"[ADMIN] Retrieved {len(payments)} payments (total: {total_count} matching filters)"
        )

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
        converted_payments = [convert_doc(payment) for payment in payments]

        # Build response
        response_content = {
            "success": True,
            "data": {
                "payments": converted_payments,
                "count": len(converted_payments),
                "total": total_count,
                "limit": limit,
                "skip": skip,
                "filters": {
                    "status": status_filter,
                    "company_name": company_name
                }
            }
        }

        logger.info(
            f"[ADMIN] Successfully prepared response with {len(converted_payments)} payments"
        )

        return JSONResponse(content=response_content)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ADMIN] Failed to retrieve all payments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payments: {str(e)}"
        )


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(payment_data: PaymentCreate):
    """
    Create a new payment record.

    This endpoint creates a payment record in the database with Square payment details.

    **Required Fields:**
    - `company_name`: Company name
    - `user_email`: User email address
    - `stripe_payment_intent_id`: Square payment ID
    - `amount`: Payment amount in cents

    **Optional Fields (with defaults):**
    - `currency`: "USD"
    - `payment_status`: "PENDING"
    - `payment_date`: Current timestamp

    **Request Example:**
    ```json
    {
        "company_name": "Acme Health LLC",
        "user_email": "test5@yahoo.com",
        "stripe_payment_intent_id": "payment_sq_1761244600756",
        "amount": 1299,
        "currency": "USD",
        "payment_status": "COMPLETED"
    }
    ```

    **Response Example:**
    ```json
    {
        "_id": "68fad3c2a0f41c24037c4810",
        "company_name": "Acme Health LLC",
        "user_email": "test5@yahoo.com",
        "stripe_payment_intent_id": "payment_sq_1761244600756",
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
           "company_name": "Acme Health LLC",
           "user_email": "test5@yahoo.com",
           "stripe_payment_intent_id": "payment_sq_1761244600756",
           "amount": 1299
         }'
    ```
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] POST /api/v1/payments - START")
        logger.info(f"📥 Request Data:")
        logger.info(f"   - company_name: {payment_data.company_name}")
        logger.info(f"   - user_email: {payment_data.user_email}")
        logger.info(f"   - stripe_payment_intent_id: {payment_data.stripe_payment_intent_id}")
        logger.info(f"   - amount: {payment_data.amount} cents")
        logger.info(f"   - currency: {payment_data.currency}")
        logger.info(f"   - payment_status: {payment_data.payment_status}")

        logger.info(f"Creating payment for {payment_data.user_email}, Square ID: {payment_data.stripe_payment_intent_id}")

        # Create payment
        logger.info(f"🔄 Calling payment_repository.create_payment()...")
        payment_id = await payment_repository.create_payment(payment_data)
        logger.info(f"🔎 Payment created with ID: {payment_id}")

        # Retrieve created payment
        logger.info(f"🔄 Retrieving created payment...")
        payment_doc = await payment_repository.get_payment_by_id(payment_id)

        if not payment_doc:
            logger.error(f"❌ Payment created but could not be retrieved: id={payment_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment created but could not be retrieved"
            )

        logger.info(f"✅ Payment created successfully:")
        logger.info(f"   - _id: {payment_id}")
        logger.info(f"   - company_name: {payment_doc.get('company_name')}")
        logger.info(f"   - stripe_payment_intent_id: {payment_doc.get('stripe_payment_intent_id')}")
        logger.info(f"   - amount: {payment_doc.get('amount')}")
        logger.info(f"   - status: {payment_doc.get('payment_status')}")

        response_data = payment_doc_to_response(payment_doc)
        logger.info(f"📤 Response: _id={payment_id}, status={response_data.get('payment_status')}")

        logger.info(f"Payment created successfully: {payment_id}")
        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create payment:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - User email: {payment_data.user_email}")
        logger.error(f"   - Square ID: {payment_data.stripe_payment_intent_id}")
        logger.error(f"Failed to create payment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create payment: {str(e)}"
        )


@router.post(
    "/subscription",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Subscription payment created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Subscription payment created successfully",
                        "data": {
                            "_id": "690023c7eb2bceb90e274140",
                            "stripe_payment_intent_id": "sq_payment_e59858fff0794614",
                            "stripe_invoice_id": "sq_order_e4dce86988a847b1",
                            "stripe_customer_id": "sq_customer_c7b478ddc7b04f99",
                            "company_name": "Acme Translation Corp",
                            "subscription_id": "690023c7eb2bceb90e274133",
                            "user_id": "user_9db5a0fbe769442d",
                            "user_email": "admin@acme.com",
                            "amount": 9000,
                            "currency": "USD",
                            "payment_status": "COMPLETED",
                            "payment_date": "2025-10-28T11:18:04.213Z",
                            "payment_method": "card",
                            "card_brand": "VISA",
                            "card_last_4": "1234",
                            "receipt_url": "https://squareup.com/receipt/preview/b05a59b993294167",
                            "created_at": "2025-10-30T12:00:00.000Z",
                            "updated_at": "2025-10-30T12:00:00.000Z"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_subscription_id": {
                            "summary": "Invalid subscription ID format",
                            "value": {
                                "detail": "Invalid subscription_id format: must be a valid 24-character ObjectId"
                            }
                        },
                        "subscription_not_found": {
                            "summary": "Subscription does not exist",
                            "value": {
                                "detail": "Subscription not found with ID: 690023c7eb2bceb90e274133"
                            }
                        },
                        "company_mismatch": {
                            "summary": "Company name does not match subscription",
                            "value": {
                                "detail": "Company name mismatch: provided 'Wrong Company' but subscription belongs to 'Acme Translation Corp'"
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Unauthorized - Missing or invalid authentication",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authorization header missing"
                    }
                }
            }
        },
        403: {
            "description": "Forbidden - Admin permissions required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Admin permissions required"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to create subscription payment: Database connection error"
                    }
                }
            }
        }
    }
)
async def create_subscription_payment(
    payment_data: SubscriptionPaymentCreate,
    admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Create a subscription payment record (Admin Only).

    This endpoint allows admins to manually record a subscription payment in the database.
    It validates that the subscription exists and matches the provided company name before
    creating the payment record.

    ## Authentication
    **Required:** Admin user with Bearer token in Authorization header

    ## Purpose
    This endpoint is for **manual entry** of subscription payment records by administrators.
    It does NOT:
    - Process actual payments through Square
    - Modify existing payment records
    - Automatically create payments (that's a separate feature)

    ## Validation Rules
    1. **Subscription exists:** The subscription_id must reference an existing subscription
    2. **Company match:** The company_name must match the subscription's company_name
    3. **Valid ObjectId:** The subscription_id must be a valid 24-character MongoDB ObjectId
    4. **Admin only:** Only authenticated admin users can create payment records

    ## Request Body
    All fields from the existing payment structure in the database are supported:
    - **company_name** *(required)*: Company name (must match subscription)
    - **subscription_id** *(required)*: Subscription ObjectId
    - **stripe_payment_intent_id** *(required)*: Square payment identifier
    - **user_email** *(required)*: Email of user who made the payment
    - **amount** *(required)*: Payment amount in cents (e.g., 9000 = $90.00)
    - **stripe_invoice_id** *(optional)*: Square order ID
    - **stripe_customer_id** *(optional)*: Square customer ID
    - **user_id** *(optional)*: User identifier
    - **currency** *(optional, default: "USD")*: Currency code
    - **payment_status** *(optional, default: "COMPLETED")*: Payment status
    - **payment_method** *(optional, default: "card")*: Payment method
    - **card_brand** *(optional)*: Card brand (VISA, MASTERCARD, etc.)
    - **card_last_4** *(optional)*: Last 4 digits of card
    - **receipt_url** *(optional)*: URL to payment receipt
    - **payment_date** *(optional)*: Payment date (defaults to current time)

    ## Response Structure
    Returns a standardized response containing:
    - **success**: Boolean indicating request success
    - **message**: Human-readable success message
    - **data**: Complete payment record including:
        - **_id**: MongoDB ObjectId of created payment
        - All provided payment fields
        - **created_at**: Timestamp when record was created
        - **updated_at**: Timestamp when record was last updated

    ## Usage Examples

    ### Create subscription payment with all details
    ```bash
    curl -X POST "http://localhost:8000/api/v1/payments/subscription" \\
         -H "Authorization: Bearer {admin_token}" \\
         -H "Content-Type: application/json" \\
         -d '{
           "company_name": "Acme Translation Corp",
           "subscription_id": "690023c7eb2bceb90e274133",
           "stripe_payment_intent_id": "sq_payment_e59858fff0794614",
           "stripe_invoice_id": "sq_order_e4dce86988a847b1",
           "stripe_customer_id": "sq_customer_c7b478ddc7b04f99",
           "user_email": "admin@acme.com",
           "user_id": "user_9db5a0fbe769442d",
           "amount": 9000,
           "currency": "USD",
           "payment_status": "COMPLETED",
           "payment_method": "card",
           "card_brand": "VISA",
           "card_last_4": "1234",
           "receipt_url": "https://squareup.com/receipt/preview/b05a59b993294167"
         }'
    ```

    ### Create minimal subscription payment
    ```bash
    curl -X POST "http://localhost:8000/api/v1/payments/subscription" \\
         -H "Authorization: Bearer {admin_token}" \\
         -H "Content-Type: application/json" \\
         -d '{
           "company_name": "Acme Translation Corp",
           "subscription_id": "690023c7eb2bceb90e274133",
           "stripe_payment_intent_id": "sq_payment_abc123",
           "user_email": "admin@acme.com",
           "amount": 9000
         }'
    ```

    ## Notes
    - Admin authentication is required - returns 401/403 if not authenticated or not admin
    - Timestamps (created_at, updated_at) are automatically generated
    - payment_date defaults to current time if not provided
    - All amount values are in cents (divide by 100 for dollar amount)
    - Subscription validation ensures referential integrity with subscriptions collection
    - This creates NEW payment records only - does not modify existing records
    """
    try:
        logger.info(
            f"[ADMIN] Creating subscription payment - Admin: {admin_user.get('email')}, "
            f"Company: {payment_data.company_name}, Subscription: {payment_data.subscription_id}, "
            f"Amount: {payment_data.amount} cents"
        )

        # Validate subscription_id format
        try:
            subscription_obj_id = ObjectId(payment_data.subscription_id)
        except Exception:
            logger.error(f"[ADMIN] Invalid subscription_id format: {payment_data.subscription_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid subscription_id format: must be a valid 24-character ObjectId"
            )

        # Validate subscription exists
        subscription = await database.subscriptions.find_one({"_id": subscription_obj_id})
        if not subscription:
            logger.error(f"[ADMIN] Subscription not found: {payment_data.subscription_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscription not found with ID: {payment_data.subscription_id}"
            )

        # Validate company name matches subscription
        subscription_company = subscription.get("company_name")
        if subscription_company != payment_data.company_name:
            logger.error(
                f"[ADMIN] Company name mismatch - provided: {payment_data.company_name}, "
                f"subscription has: {subscription_company}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Company name mismatch: provided '{payment_data.company_name}' "
                       f"but subscription belongs to '{subscription_company}'"
            )

        # Create payment document with all fields
        now = datetime.now(timezone.utc)
        payment_doc = {
            "stripe_payment_intent_id": payment_data.stripe_payment_intent_id,
            "stripe_invoice_id": payment_data.stripe_invoice_id,
            "stripe_customer_id": payment_data.stripe_customer_id,
            "company_name": payment_data.company_name,
            "subscription_id": payment_data.subscription_id,
            "user_id": payment_data.user_id,
            "user_email": payment_data.user_email,
            "amount": payment_data.amount,
            "currency": payment_data.currency,
            "payment_status": payment_data.payment_status,
            "payment_date": payment_data.payment_date or now,
            "payment_method": payment_data.payment_method,
            "card_brand": payment_data.card_brand,
            "card_last_4": payment_data.card_last_4,
            "receipt_url": payment_data.receipt_url,
            "refunds": [],  # Initialize empty refunds array
            "created_at": now,
            "updated_at": now
        }

        # Remove None values to keep document clean
        payment_doc = {k: v for k, v in payment_doc.items() if v is not None}

        # Insert into MongoDB
        result = await database.payments.insert_one(payment_doc)
        payment_id = str(result.inserted_id)

        logger.info(
            f"[ADMIN] Subscription payment created successfully - "
            f"Payment ID: {payment_id}, Square ID: {payment_data.stripe_payment_intent_id}"
        )

        # Retrieve the created payment to return complete document
        created_payment = await database.payments.find_one({"_id": result.inserted_id})

        # Convert ObjectId and datetime fields for JSON response
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

        created_payment_json = convert_doc(created_payment)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "success": True,
                "message": "Subscription payment created successfully",
                "data": created_payment_json
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"[ADMIN] Failed to create subscription payment: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create subscription payment: {str(e)}"
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
    - **400**: Invalid payment ID format
    - **404**: Payment not found
    - **500**: Internal server error

    **Example:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/68ec42a48ca6a1781d9fe5c2"
    ```
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] GET /api/v1/payments/{payment_id} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - payment_id: {payment_id}")

        logger.info(f"🔍 Validating payment_id format...")
        validate_object_id(payment_id, "payment ID")
        logger.info(f"✅ Payment ID validation passed")

        logger.info(f"🔄 Calling payment_repository.get_payment_by_id()...")
        logger.info(f"Fetching payment by ID: {payment_id}")
        payment_doc = await payment_repository.get_payment_by_id(payment_id)
        logger.info(f"🔎 Database Result: found={payment_doc is not None}")

        if not payment_doc:
            logger.warning(f"❌ Payment not found: id={payment_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found: {payment_id}"
            )

        logger.info(f"✅ Payment retrieved:")
        logger.info(f"   - _id: {payment_id}")
        logger.info(f"   - company_name: {payment_doc.get('company_name')}")
        logger.info(f"   - stripe_payment_intent_id: {payment_doc.get('stripe_payment_intent_id')}")
        logger.info(f"   - amount: {payment_doc.get('amount')}")
        logger.info(f"   - status: {payment_doc.get('payment_status')}")

        response_data = payment_doc_to_response(payment_doc)
        logger.info(f"📤 Response: _id={payment_id}, status={response_data.get('payment_status')}")

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve payment:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Payment ID: {payment_id}")
        logger.error(f"Failed to retrieve payment {payment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment: {str(e)}"
        )


@router.get("/square/{stripe_payment_intent_id}")
async def get_payment_by_square_id(
    stripe_payment_intent_id: str = Path(..., description="Square payment ID")
):
    """
    Get payment by Square payment ID.

    Retrieves a payment record using the Square payment identifier.

    **Path Parameters:**
    - `stripe_payment_intent_id`: Square payment ID (e.g., "sq_payment_abc123")

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
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] GET /api/v1/payments/square/{stripe_payment_intent_id} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - stripe_payment_intent_id: {stripe_payment_intent_id}")

        logger.info(f"🔄 Calling payment_repository.get_payment_by_square_id()...")
        logger.info(f"Fetching payment by Square ID: {stripe_payment_intent_id}")
        payment_doc = await payment_repository.get_payment_by_square_id(stripe_payment_intent_id)
        logger.info(f"🔎 Database Result: found={payment_doc is not None}")

        if not payment_doc:
            logger.warning(f"❌ Payment not found for Square ID: {stripe_payment_intent_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found for Square ID: {stripe_payment_intent_id}"
            )

        logger.info(f"✅ Payment retrieved:")
        logger.info(f"   - _id: {payment_doc.get('_id')}")
        logger.info(f"   - company_name: {payment_doc.get('company_name')}")
        logger.info(f"   - stripe_payment_intent_id: {stripe_payment_intent_id}")
        logger.info(f"   - amount: {payment_doc.get('amount')}")
        logger.info(f"   - status: {payment_doc.get('payment_status')}")

        # Return full payment document (not just PaymentResponse fields)
        payment_doc["_id"] = str(payment_doc["_id"])

        logger.info(f"📤 Response: _id={payment_doc['_id']}, status={payment_doc.get('payment_status')}")

        return JSONResponse(content=payment_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve payment by Square ID:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Square Payment ID: {stripe_payment_intent_id}")
        logger.error(f"Failed to retrieve payment by Square ID {stripe_payment_intent_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment: {str(e)}"
        )


@router.get(
    "/company/{company_name}",
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
                                            "company_name": "Acme Health LLC",
                                            "user_email": "test5@yahoo.com",
                                            "stripe_payment_intent_id": "payment_sq_1761244600756",
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
                                            "company_name": "Acme Health LLC",
                                            "user_email": "admin@acmehealth.com",
                                            "stripe_payment_intent_id": "payment_sq_1761268674",
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
                                            "company_name": "Acme Health LLC",
                                            "user_email": "billing@acmehealth.com",
                                            "stripe_payment_intent_id": "payment_sq_1761278900",
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
                                        "company_name": "Acme Health LLC",
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
                                        "company_name": "Unknown Company",
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
                                            "company_name": "Acme Health LLC",
                                            "user_email": "refund@example.com",
                                            "stripe_payment_intent_id": "payment_sq_1761300000",
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
                                        "company_name": "Acme Health LLC",
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
                        "invalid_company_name": {
                            "summary": "Invalid company name format",
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
                        "detail": "Company not found: Unknown Company"
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
    company_name: str = Path(
        ...,
        description="Company name (e.g., Acme Health LLC)",
        example="Acme Health LLC"
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

    Retrieves a list of payment records associated with a specific company name.
    Results can be filtered by payment status and paginated using limit/skip parameters.

    ## Path Parameters
    - **company_name**: Company name (e.g., Acme Health LLC)

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
    - **company_name**: Full company name
    - **user_email**: Email of user who made the payment
    - **stripe_payment_intent_id**: Square payment identifier
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
    curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED&limit=20"
    ```

    ### Get second page of payments (pagination)
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?skip=20&limit=20"
    ```

    ### Get all payments regardless of status
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC"
    ```

    ### Filter by refunded payments only
    ```bash
    curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=REFUNDED"
    ```

    ## Notes
    - Returns empty array if no payments match the criteria
    - All datetime fields are returned in ISO 8601 format
    - Amount is always in cents (divide by 100 for dollar amount)
    - Refunds array shows detailed refund history when applicable
    """
    try:
        print(f"[PAYMENTS DEBUG] Fetching payments for company {company_name}, status={status_filter}, limit={limit}, skip={skip}")
        logger.info(f"Fetching payments for company {company_name}, status={status_filter}, limit={limit}, skip={skip}")

        payments = await payment_repository.get_payments_by_company(
            company_name=company_name,
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

        logger.info(f"Found {len(payments)} payments for company {company_name}, creating response")

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
                        "company_name": company_name,
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
        logger.error(f"Failed to retrieve payments for company {company_name}: {e}", exc_info=True)
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
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] GET /api/v1/payments/email/{email} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - email: {email}")
        logger.info(f"   - limit: {limit}")
        logger.info(f"   - skip: {skip}")

        logger.info(f"🔄 Calling payment_repository.get_payments_by_email()...")
        logger.info(f"Fetching payments for email {email}, limit={limit}, skip={skip}")

        payments = await payment_repository.get_payments_by_email(
            email=email,
            limit=limit,
            skip=skip
        )
        logger.info(f"🔎 Database Result: count={len(payments)}")

        # Convert ObjectIds to strings
        logger.info(f"🔄 Serializing {len(payments)} payments...")
        for payment in payments:
            payment["_id"] = str(payment["_id"])

        logger.info(f"✅ Payments retrieved successfully: count={len(payments)}")
        if payments:
            logger.info(f"📊 Sample Payment: _id={payments[0].get('_id')}, "
                       f"stripe_payment_intent_id={payments[0].get('stripe_payment_intent_id')}, "
                       f"amount={payments[0].get('amount')}")

        logger.info(f"Found {len(payments)} payments for email {email}")

        response_data = {
            "success": True,
            "data": {
                "payments": payments,
                "count": len(payments),
                "limit": limit,
                "skip": skip,
                "email": email
            }
        }
        logger.info(f"📤 Response: success=True, count={len(payments)}, email={email}")

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error(f"❌ Failed to retrieve payments for email:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Email: {email}")
        logger.error(f"Failed to retrieve payments for email {email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payments by email: {str(e)}"
        )


@router.patch("/{stripe_payment_intent_id}")
async def update_payment(
    stripe_payment_intent_id: str = Path(..., description="Square payment ID"),
    update_data: PaymentUpdate = None
):
    """
    Update a payment record.

    Updates payment information such as status, refund details, or notes.

    **Path Parameters:**
    - `stripe_payment_intent_id`: Square payment ID

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
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] PATCH /api/v1/payments/{stripe_payment_intent_id} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - stripe_payment_intent_id: {stripe_payment_intent_id}")

        if update_data:
            update_dict = update_data.model_dump(exclude_unset=True)
            logger.info(f"📨 Update Data:")
            for key, value in update_dict.items():
                logger.info(f"   - {key}: {value}")

        logger.info(f"Updating payment {stripe_payment_intent_id}")

        # Check if payment exists
        logger.info(f"🔄 Checking if payment exists...")
        existing_payment = await payment_repository.get_payment_by_square_id(stripe_payment_intent_id)
        logger.info(f"🔎 Existing Payment: found={existing_payment is not None}")

        if not existing_payment:
            logger.warning(f"❌ Payment not found: {stripe_payment_intent_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found: {stripe_payment_intent_id}"
            )

        # Update payment
        logger.info(f"🔄 Calling payment_repository.update_payment()...")
        updated = await payment_repository.update_payment(stripe_payment_intent_id, update_data)
        logger.info(f"🔎 Update Result: success={updated}")

        if not updated:
            logger.error(f"❌ Payment update failed for: {stripe_payment_intent_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment update failed"
            )

        # Retrieve updated payment
        logger.info(f"🔄 Retrieving updated payment...")
        payment_doc = await payment_repository.get_payment_by_square_id(stripe_payment_intent_id)

        logger.info(f"✅ Payment updated successfully:")
        logger.info(f"   - stripe_payment_intent_id: {stripe_payment_intent_id}")
        logger.info(f"   - status: {payment_doc.get('payment_status')}")
        logger.info(f"Payment {stripe_payment_intent_id} updated successfully")

        # Convert ObjectIds to strings
        payment_doc["_id"] = str(payment_doc["_id"])

        response_data = {
            "success": True,
            "message": "Payment updated successfully",
            "data": payment_doc
        }
        logger.info(f"📤 Response: success=True, _id={payment_doc['_id']}")

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update payment:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Square Payment ID: {stripe_payment_intent_id}")
        logger.error(f"Failed to update payment {stripe_payment_intent_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment: {str(e)}"
        )


@router.post("/{stripe_payment_intent_id}/refund")
async def process_refund(
    stripe_payment_intent_id: str = Path(..., description="Square payment ID"),
    refund_request: RefundRequest = None
):
    """
    Process a payment refund.

    Marks a payment as refunded and records refund details in the refunds array.

    **Path Parameters:**
    - `stripe_payment_intent_id`: Square payment ID (e.g., "payment_sq_1761268674_852e5fe3")

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
                "company_name": "Acme Health LLC",
                "user_email": "test5@yahoo.com",
                "stripe_payment_intent_id": "payment_sq_1761268674_852e5fe3",
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
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] POST /api/v1/payments/{stripe_payment_intent_id}/refund - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - stripe_payment_intent_id: {stripe_payment_intent_id}")
        logger.info(f"📨 Refund Data:")
        logger.info(f"   - refund_id: {refund_request.refund_id}")
        logger.info(f"   - amount: {refund_request.amount} cents")
        logger.info(f"   - currency: {refund_request.currency}")
        logger.info(f"   - idempotency_key: {refund_request.idempotency_key}")

        logger.info(f"Processing refund for payment {stripe_payment_intent_id}, amount: {refund_request.amount} cents")

        # Validate refund amount
        logger.info(f"🔍 Validating refund amount...")
        if refund_request.amount <= 0:
            logger.error(f"❌ Invalid refund amount: {refund_request.amount}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refund amount must be greater than 0"
            )
        logger.info(f"✅ Refund amount validation passed")

        # Check if payment exists
        logger.info(f"🔄 Checking if payment exists...")
        existing_payment = await payment_repository.get_payment_by_square_id(stripe_payment_intent_id)
        logger.info(f"🔎 Existing Payment: found={existing_payment is not None}")

        if not existing_payment:
            logger.warning(f"❌ Payment not found: {stripe_payment_intent_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment not found: {stripe_payment_intent_id}"
            )

        # Check if refund amount exceeds payment amount
        payment_amount = existing_payment.get("amount", 0)
        logger.info(f"🔍 Validating refund amount vs payment amount...")
        logger.info(f"   - Payment amount: {payment_amount} cents")
        logger.info(f"   - Refund amount: {refund_request.amount} cents")

        if refund_request.amount > payment_amount:
            logger.error(f"❌ Refund amount exceeds payment amount: {refund_request.amount} > {payment_amount}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Refund amount ({refund_request.amount}) exceeds payment amount ({payment_amount})"
            )
        logger.info(f"✅ Refund amount validation passed")

        # Process refund
        logger.info(f"🔄 Calling payment_repository.process_refund()...")
        refunded = await payment_repository.process_refund(
            stripe_payment_intent_id=stripe_payment_intent_id,
            refund_id=refund_request.refund_id,
            refund_amount=refund_request.amount,
            refund_reason=None
        )
        logger.info(f"🔎 Refund processing result: success={refunded}")

        if not refunded:
            logger.error(f"❌ Refund processing failed for: {stripe_payment_intent_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Refund processing failed"
            )

        # Retrieve updated payment
        logger.info(f"🔄 Retrieving updated payment...")
        payment_doc = await payment_repository.get_payment_by_square_id(stripe_payment_intent_id)

        logger.info(f"✅ Refund processed successfully:")
        logger.info(f"   - stripe_payment_intent_id: {stripe_payment_intent_id}")
        logger.info(f"   - refund_id: {refund_request.refund_id}")
        logger.info(f"   - amount: {refund_request.amount} cents")
        logger.info(f"   - payment_status: {payment_doc.get('payment_status')}")
        logger.info(f"Refund processed successfully for payment {stripe_payment_intent_id}")

        # Convert ObjectIds to strings
        payment_doc["_id"] = str(payment_doc["_id"])

        response_data = {
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
        }
        logger.info(f"📤 Response: success=True, refund_id={refund_request.refund_id}")

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to process refund:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Square Payment ID: {stripe_payment_intent_id}")
        logger.error(f"   - Refund ID: {refund_request.refund_id}")
        logger.error(f"Failed to process refund for payment {stripe_payment_intent_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process refund: {str(e)}"
        )


@router.get("/company/{company_name}/stats")
async def get_company_payment_stats(
    company_name: str = Path(..., description="Company name"),
    start_date: Optional[datetime] = Query(None, description="Start date filter (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="End date filter (ISO 8601)")
):
    """
    Get payment statistics for a company.

    Retrieves aggregated payment statistics including total payments,
    amounts, refunds, and success/failure rates.

    **Path Parameters:**
    - `company_name`: Company name

    **Query Parameters:**
    - `start_date`: Filter payments from this date (ISO 8601 format, optional)
    - `end_date`: Filter payments until this date (ISO 8601 format, optional)

    **Response:**
    - **200**: Payment statistics
    - **400**: Invalid company name or date format
    - **500**: Internal server error

    **Response Format:**
    ```json
    {
        "success": true,
        "data": {
            "company_name": "Acme Health LLC",
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
    curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats"

    # Get stats for date range
    curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats?start_date=2025-01-01T00:00:00Z&end_date=2025-12-31T23:59:59Z"
    ```
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] GET /api/v1/payments/company/{company_name}/stats - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - company_name: {company_name}")
        logger.info(f"   - start_date: {start_date}")
        logger.info(f"   - end_date: {end_date}")

        logger.info(f"🔄 Calling payment_repository.get_payment_stats_by_company()...")
        logger.info(f"Fetching payment stats for company {company_name}, start={start_date}, end={end_date}")

        stats = await payment_repository.get_payment_stats_by_company(
            company_name=company_name,
            start_date=start_date,
            end_date=end_date
        )
        logger.info(f"🔎 Stats retrieved: {stats}")

        # Calculate success rate
        total_payments = stats.get("total_payments", 0)
        completed_payments = stats.get("completed_payments", 0)
        success_rate = (completed_payments / total_payments * 100) if total_payments > 0 else 0.0

        logger.info(f"✅ Statistics calculated:")
        logger.info(f"   - company_name: {company_name}")
        logger.info(f"   - total_payments: {total_payments}")
        logger.info(f"   - completed_payments: {completed_payments}")
        logger.info(f"   - success_rate: {round(success_rate, 2)}%")
        logger.info(f"Retrieved stats for company {company_name}: {total_payments} total payments")

        response_data = {
            "success": True,
            "data": {
                "company_name": company_name,
                **stats,
                "success_rate": round(success_rate, 2),
                "date_range": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            }
        }
        logger.info(f"📤 Response: success=True, total_payments={total_payments}, success_rate={round(success_rate, 2)}%")

        return JSONResponse(content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve payment stats:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Company: {company_name}")
        logger.error(f"Failed to retrieve stats for company {company_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve payment statistics: {str(e)}"
        )


@router.post(
    "/{payment_id}/apply-to-invoice",
    status_code=status.HTTP_200_OK,
    summary="Apply Payment to Invoice",
    description="Apply a payment to an invoice, updating invoice status and payment linkage (Admin only)"
)
async def apply_payment_to_invoice(
    payment_id: str = Path(..., description="Payment ID"),
    invoice_id: str = Query(..., description="Invoice ID to apply payment to"),
    admin: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Apply a payment to an invoice.

    This endpoint links a completed payment to an invoice and updates:
    1. invoice.amount_paid += payment.amount
    2. invoice.status (sent → partially_paid → paid)
    3. payment.invoice_id = invoice_id
    4. invoice.payment_applications with payment record

    **Authentication:** Admin only

    **Request:**
    ```
    POST /api/v1/payments/{payment_id}/apply-to-invoice?invoice_id={invoice_id}
    Authorization: Bearer {admin_token}
    ```

    **Success Response (200):**
    ```json
    {
        "success": true,
        "message": "Payment applied to invoice successfully",
        "data": {
            "invoice_id": "507f1f77bcf86cd799439011",
            "invoice_number": "INV-2025-Q1-abc123",
            "amount_paid": 339.20,
            "amount_due": 0.00,
            "status": "paid"
        }
    }
    ```

    **Error Responses:**
    - 400: Payment already applied to another invoice
    - 400: Payment status not COMPLETED or APPROVED
    - 404: Payment or invoice not found
    - 500: Application failed

    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/api/v1/payments/507f191e810c19729de860ea/apply-to-invoice?invoice_id=507f1f77bcf86cd799439011" \\
      -H "Authorization: Bearer {admin_token}"
    ```
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔄 [{timestamp}] POST /api/v1/payments/{payment_id}/apply-to-invoice - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - payment_id: {payment_id}")
        logger.info(f"   - invoice_id: {invoice_id}")
        logger.info(f"   - admin_email: {admin.get('email')}")

        logger.info(f"🔄 Calling payment_application_service.apply_payment_to_invoice()...")

        # Apply payment to invoice
        updated_invoice = await payment_application_service.apply_payment_to_invoice(
            payment_id=payment_id,
            invoice_id=invoice_id
        )

        logger.info(f"✅ Payment applied successfully")

        # Serialize datetime fields for JSON response
        if "_id" in updated_invoice:
            updated_invoice["_id"] = str(updated_invoice["_id"])
        if "subscription_id" in updated_invoice and updated_invoice["subscription_id"]:
            updated_invoice["subscription_id"] = str(updated_invoice["subscription_id"])

        datetime_fields = ["invoice_date", "due_date", "created_at", "updated_at"]
        for field in datetime_fields:
            if field in updated_invoice and updated_invoice[field] is not None:
                if hasattr(updated_invoice[field], "isoformat"):
                    updated_invoice[field] = updated_invoice[field].isoformat()

        # Serialize billing_period dates
        if "billing_period" in updated_invoice and updated_invoice["billing_period"]:
            bp = updated_invoice["billing_period"]
            if "period_start" in bp and hasattr(bp["period_start"], "isoformat"):
                bp["period_start"] = bp["period_start"].isoformat()
            if "period_end" in bp and hasattr(bp["period_end"], "isoformat"):
                bp["period_end"] = bp["period_end"].isoformat()

        # Serialize payment_applications
        if "payment_applications" in updated_invoice and updated_invoice["payment_applications"]:
            for app in updated_invoice["payment_applications"]:
                if "applied_at" in app and hasattr(app["applied_at"], "isoformat"):
                    app["applied_at"] = app["applied_at"].isoformat()

        # Calculate amount_due
        total_amount = updated_invoice.get("total_amount", 0.0)
        amount_paid = updated_invoice.get("amount_paid", 0.0)
        amount_due = max(0.0, total_amount - amount_paid)

        response_data = {
            "success": True,
            "message": "Payment applied to invoice successfully",
            "data": {
                "invoice_id": str(updated_invoice["_id"]),
                "invoice_number": updated_invoice.get("invoice_number"),
                "amount_paid": amount_paid,
                "amount_due": amount_due,
                "status": updated_invoice.get("status")
            }
        }

        logger.info(f"📤 Response: success=True, invoice_id={response_data['data']['invoice_id']}, status={response_data['data']['status']}")

        return JSONResponse(content=response_data)

    except PaymentApplicationError as e:
        logger.error(f"❌ Payment application error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to apply payment:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Payment ID: {payment_id}")
        logger.error(f"   - Invoice ID: {invoice_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply payment to invoice: {str(e)}"
        )
