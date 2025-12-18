"""
User Transaction Payment API Router.

This module provides payment management endpoints for user_transactions collection:
- Creating user transactions with Square payment details
- Processing refunds
- Retrieving all user transactions (admin endpoint)
- Retrieving transaction history by email
- Updating payment status
"""

from fastapi import APIRouter, HTTPException, Query, Path, status, Request
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timezone
from pydantic import EmailStr
import logging
import uuid
from bson.decimal128 import Decimal128

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


def serialize_transaction_for_json(txn: dict) -> dict:
    """
    Convert MongoDB transaction document to JSON-serializable dict.

    Handles:
    - ObjectId → string
    - Decimal128 → float
    - datetime → ISO 8601 string (all fields at all levels)
    - Field name mapping for API consistency:
      - price_per_unit → cost_per_unit
      - total_price → total_cost
      - units_count → number_of_units

    Args:
        txn: Transaction document from MongoDB

    Returns:
        JSON-serializable dict with frontend-compatible field names

    Note:
        Maps database field names to match API documentation and frontend TypeScript interfaces.
    """
    import copy
    from bson import ObjectId

    def serialize_value(value):
        """Recursively serialize a value to JSON-compatible format."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, Decimal128):
            return float(value.to_decimal())
        if isinstance(value, dict):
            return {k: serialize_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [serialize_value(item) for item in value]
        return value

    # Create a deep copy to avoid modifying the original
    txn = copy.deepcopy(txn)

    # Recursively serialize all values
    serialized = {key: serialize_value(value) for key, value in txn.items()}

    # Map database field names to API field names for consistency
    field_mappings = {
        'price_per_unit': 'cost_per_unit',
        'total_price': 'total_cost',
        'units_count': 'number_of_units'
    }

    for db_field, api_field in field_mappings.items():
        if db_field in serialized:
            serialized[api_field] = serialized.pop(db_field)

    return serialized

router = APIRouter(prefix="/api/v1/user-transactions", tags=["User Transaction Payments"])


@router.post("/process", response_model=UserTransactionResponse, status_code=status.HTTP_201_CREATED)
async def process_payment_transaction(request: Request, transaction_data: UserTransactionCreate):
    """
    Process a payment and create user transaction record.

    This endpoint creates a user transaction with Square payment details for
    individual translation jobs. All 22 fields are stored in the users_transactions collection.

    **Required Fields:**
    - `user_name`: Full name of the user
    - `user_email`: User email address
    - `documents`: Array of document objects (at least one required)
    - `number_of_units`: Number of units (pages, words, or characters)
    - `unit_type`: Type of unit (page | word | character)
    - `cost_per_unit`: Cost per single unit
    - `source_language`: Source language code (e.g., "en")
    - `target_language`: Target language code (e.g., "es")
    - `stripe_checkout_session_id`: Unique Square transaction ID
    - `stripe_payment_intent_id`: Square payment ID

    **Optional Fields (with defaults):**
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
        "documents": [
            {
                "document_name": "contract.pdf",
                "document_url": "https://drive.google.com/file/d/1ABC_contract/view",
                "translated_url": null,
                "status": "uploaded",
                "uploaded_at": "2025-10-23T23:56:55.438Z",
                "translated_at": null
            },
            {
                "document_name": "invoice.docx",
                "document_url": "https://drive.google.com/file/d/1DEF_invoice/view",
                "translated_url": null,
                "status": "uploaded",
                "uploaded_at": "2025-10-23T23:57:00.438Z",
                "translated_at": null
            }
        ],
        "number_of_units": 10,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "en",
        "target_language": "es",
        "stripe_checkout_session_id": "SQR-1EC28E70F10B4D9E",
        "stripe_payment_intent_id": "SQR-1EC28E70F10B4D9E",
        "amount_cents": 150,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "status": "processing"
    }
    ```

    **Response Example:**
    ```json
    {
        "id": "68fad3c2a0f41c24037c4810",
        "user_name": "John Doe",
        "user_email": "john.doe@example.com",
        "documents": [
            {
                "document_name": "contract.pdf",
                "document_url": "https://drive.google.com/file/d/1ABC_contract/view",
                "translated_url": null,
                "status": "uploaded",
                "uploaded_at": "2025-10-23T23:56:55.438Z",
                "translated_at": null
            },
            {
                "document_name": "invoice.docx",
                "document_url": "https://drive.google.com/file/d/1DEF_invoice/view",
                "translated_url": null,
                "status": "uploaded",
                "uploaded_at": "2025-10-23T23:57:00.438Z",
                "translated_at": null
            }
        ],
        "number_of_units": 10,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "en",
        "target_language": "es",
        "transaction_id": "USER123456",
        "stripe_checkout_session_id": "SQR-1EC28E70F10B4D9E",
        "date": "2025-10-23T23:56:55.438Z",
        "status": "processing",
        "total_cost": 1.5,
        "stripe_payment_intent_id": "SQR-1EC28E70F10B4D9E",
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
           "documents": [
             {
               "document_name": "contract.pdf",
               "document_url": "https://drive.google.com/file/d/1ABC_contract/view",
               "translated_url": null,
               "status": "uploaded",
               "uploaded_at": "2025-10-23T23:56:55.438Z",
               "translated_at": null
             }
           ],
           "number_of_units": 10,
           "unit_type": "page",
           "cost_per_unit": 0.15,
           "source_language": "en",
           "target_language": "es",
           "stripe_checkout_session_id": "SQR-1EC28E70F10B4D9E",
           "stripe_payment_intent_id": "SQR-1EC28E70F10B4D9E",
           "amount_cents": 150
         }'
    ```
    """
    try:
        # Request Start
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] POST /api/v1/user-transactions/process - START")

        # Raw Request Body
        try:
            raw_body = await request.body()
            raw_body_str = raw_body.decode('utf-8') if raw_body else "{}"
            logger.info(f"📨 Raw Request Body: {raw_body_str}")
        except Exception as e:
            logger.error(f"❌ Failed to read raw request body: {e}")

        # Pydantic Validation
        logger.info(f"🔍 Validating with UserTransactionCreate...")
        set_fields = {k: v for k, v in transaction_data.model_dump().items() if v is not None}
        unset_fields = {k for k in transaction_data.model_fields.keys() if k not in set_fields}
        logger.info(f"📋 Parsed Fields (Set={len(set_fields)}, Unset={len(unset_fields)}):")
        for key, value in set_fields.items():
            if key == "documents":
                logger.info(f"   - {key}: {len(value)} documents")
            else:
                logger.info(f"   - {key}: {value}")
        logger.info(f"✅ Validation passed")

        logger.info(f"📥 Request Data:")
        logger.info(f"   - user_email: {transaction_data.user_email}")
        logger.info(f"   - stripe_checkout_session_id: {transaction_data.stripe_checkout_session_id}")
        logger.info(f"   - number_of_units: {transaction_data.number_of_units}")
        logger.info(f"   - unit_type: {transaction_data.unit_type}")
        logger.info(f"   - documents_count: {len(transaction_data.documents)}")

        # Use provided date or default to current UTC time
        transaction_date = transaction_data.date if transaction_data.date else datetime.now(timezone.utc)
        payment_date = transaction_data.payment_date if transaction_data.payment_date else datetime.now(timezone.utc)

        # Convert documents to dict format
        logger.info(f"🔄 Converting {len(transaction_data.documents)} documents to dict format...")
        documents_dict = [doc.model_dump() for doc in transaction_data.documents]
        logger.info(f"✅ Document conversion complete")

        # Create transaction using helper function
        logger.info(f"🔄 Calling create_user_transaction()...")
        result = await create_user_transaction(
            user_name=transaction_data.user_name,
            user_email=transaction_data.user_email,
            documents=documents_dict,
            number_of_units=transaction_data.number_of_units,
            unit_type=transaction_data.unit_type,
            cost_per_unit=transaction_data.cost_per_unit,
            source_language=transaction_data.source_language,
            target_language=transaction_data.target_language,
            stripe_checkout_session_id=transaction_data.stripe_checkout_session_id,
            date=transaction_date,
            status=transaction_data.status,
            stripe_payment_intent_id=transaction_data.stripe_payment_intent_id,
            amount_cents=transaction_data.amount_cents,
            currency=transaction_data.currency,
            payment_status=transaction_data.payment_status,
            payment_date=payment_date,
        )
        logger.info(f"🔎 Database Result: created={result is not None}")

        if not result:
            logger.error(f"❌ Failed to create transaction record in database")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create transaction record"
            )

        # Retrieve created transaction
        logger.info(f"🔄 Calling get_user_transaction({transaction_data.stripe_checkout_session_id})...")
        transaction_doc = await get_user_transaction(transaction_data.stripe_checkout_session_id)
        logger.info(f"🔎 Database Result: found={transaction_doc is not None}")

        if not transaction_doc:
            logger.error(f"❌ Transaction created but could not be retrieved")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Transaction created but could not be retrieved"
            )

        logger.info(f"✅ Transaction creation successful:")
        logger.info(f"   - stripe_checkout_session_id: {transaction_data.stripe_checkout_session_id}")
        logger.info(f"   - user_email: {transaction_data.user_email}")
        logger.info(f"   - status: {transaction_data.status}")
        logger.info(f"   - payment_status: {transaction_data.payment_status}")
        logger.info(f"📤 Response: UserTransactionResponse with _id={transaction_doc.get('_id')}")

        # Convert to response format
        transaction_doc["_id"] = str(transaction_doc["_id"])
        return UserTransactionResponse(**transaction_doc)

    except HTTPException as e:
        logger.error(f"❌ HTTPException:", exc_info=True)
        logger.error(f"   - Error: {e.detail}")
        logger.error(f"   - Status code: {e.status_code}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to process payment transaction:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Context: user_email={transaction_data.user_email}, stripe_checkout_session_id={transaction_data.stripe_checkout_session_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process transaction: {str(e)}"
        )


@router.post("/{stripe_checkout_session_id}/refund", status_code=status.HTTP_200_OK)
async def process_transaction_refund(
    request: Request,
    stripe_checkout_session_id: str = Path(..., description="Square transaction ID"),
    refund_request: UserTransactionRefundRequest = None
):
    """
    Process a refund for a user transaction.

    Adds refund information to the transaction's refunds array and updates payment status if needed.

    **Path Parameters:**
    - `stripe_checkout_session_id`: Square transaction ID (e.g., "SQR-1EC28E70F10B4D9E")

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
            "stripe_checkout_session_id": "SQR-1EC28E70F10B4D9E",
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
        # Request Start
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] POST /api/v1/user-transactions/{stripe_checkout_session_id}/refund - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - stripe_checkout_session_id (path): {stripe_checkout_session_id}")

        # Raw Request Body
        try:
            raw_body = await request.body()
            raw_body_str = raw_body.decode('utf-8') if raw_body else "{}"
            logger.info(f"📨 Raw Request Body: {raw_body_str}")
        except Exception as e:
            logger.error(f"❌ Failed to read raw request body: {e}")

        # Pydantic Validation
        logger.info(f"🔍 Validating with UserTransactionRefundRequest...")
        set_fields = {k: v for k, v in refund_request.model_dump().items() if v is not None}
        unset_fields = {k for k in refund_request.model_fields.keys() if k not in set_fields}
        logger.info(f"📋 Parsed Fields (Set={len(set_fields)}, Unset={len(unset_fields)}):")
        for key, value in set_fields.items():
            logger.info(f"   - {key}: {value}")
        logger.info(f"✅ Validation passed")

        logger.info(f"📥 Refund Data:")
        logger.info(f"   - refund_id: {refund_request.refund_id}")
        logger.info(f"   - amount_cents: {refund_request.amount_cents}")
        logger.info(f"   - currency: {refund_request.currency}")

        # Check if transaction exists
        logger.info(f"🔄 Calling get_user_transaction({stripe_checkout_session_id})...")
        transaction = await get_user_transaction(stripe_checkout_session_id)
        logger.info(f"🔎 Database Result: found={transaction is not None}")

        if not transaction:
            logger.error(f"❌ Transaction not found: {stripe_checkout_session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction not found: {stripe_checkout_session_id}"
            )

        # Prepare refund data
        logger.info(f"🔄 Preparing refund data...")
        refund_data = {
            "refund_id": refund_request.refund_id,
            "amount_cents": refund_request.amount_cents,
            "currency": refund_request.currency,
            "status": "COMPLETED",  # Default status
            "created_at": datetime.now(timezone.utc),
            "idempotency_key": refund_request.idempotency_key,
        }

        if refund_request.reason:
            refund_data["reason"] = refund_request.reason

        logger.info(f"   - refund_data prepared with {len(refund_data)} fields")

        # Add refund to transaction
        logger.info(f"🔄 Calling add_refund_to_transaction()...")
        success = await add_refund_to_transaction(stripe_checkout_session_id, refund_data)
        logger.info(f"🔎 Database Result: success={success}")

        if not success:
            logger.error(f"❌ Failed to add refund to transaction")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process refund"
            )

        # Retrieve updated transaction
        logger.info(f"🔄 Calling get_user_transaction() to verify refund...")
        updated_transaction = await get_user_transaction(stripe_checkout_session_id)
        total_refunds = len(updated_transaction.get("refunds", []))
        logger.info(f"🔎 Database Result: total_refunds={total_refunds}")

        logger.info(f"✅ Refund processing successful:")
        logger.info(f"   - stripe_checkout_session_id: {stripe_checkout_session_id}")
        logger.info(f"   - refund_id: {refund_request.refund_id}")
        logger.info(f"   - amount_cents: {refund_request.amount_cents}")
        logger.info(f"   - total_refunds: {total_refunds}")
        logger.info(f"📤 Response: success=True, message='Refund processed successfully'")

        return JSONResponse(content={
            "success": True,
            "message": "Refund processed successfully",
            "data": {
                "stripe_checkout_session_id": stripe_checkout_session_id,
                "refund_id": refund_request.refund_id,
                "amount_cents": refund_request.amount_cents,
                "total_refunds": total_refunds
            }
        })

    except HTTPException as e:
        logger.error(f"❌ HTTPException:", exc_info=True)
        logger.error(f"   - Error: {e.detail}")
        logger.error(f"   - Status code: {e.status_code}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to process refund:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Context: stripe_checkout_session_id={stripe_checkout_session_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process refund: {str(e)}"
        )


@router.get("")
async def get_all_user_transactions(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by transaction status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of transactions to return"),
    skip: int = Query(0, ge=0, description="Number of transactions to skip for pagination")
):
    """
    Get all user transactions from the database (admin endpoint).

    Retrieves all transactions from the user_transactions collection, with optional status filtering
    and pagination. Returns complete transaction records sorted by date (newest first).

    **Query Parameters:**
    - `status`: Optional filter by transaction status (completed | pending | failed)
    - `limit`: Maximum number of results (1-1000, default: 100)
    - `skip`: Number of results to skip for pagination (default: 0)

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
                    "stripe_checkout_session_id": "SQR-1EC28E70F10B4D9E",
                    "date": "2025-10-23T23:56:55.438Z",
                    "status": "completed",
                    "total_cost": 1.5,
                    "created_at": "2025-10-23T23:56:55.438Z",
                    "updated_at": "2025-10-23T23:56:55.438Z"
                }
            ],
            "count": 1,
            "limit": 100,
            "skip": 0,
            "filters": {
                "status": "completed"
            }
        }
    }
    ```

    **Status Codes:**
    - **200**: Transaction list retrieved (may be empty array)
    - **400**: Invalid status filter value
    - **500**: Internal server error

    **cURL Examples:**
    ```bash
    # Get all transactions (first 100)
    curl -X GET "http://localhost:8000/api/v1/user-transactions"

    # Get all completed transactions
    curl -X GET "http://localhost:8000/api/v1/user-transactions?status=completed"

    # Get transactions with pagination (50 per page, page 2)
    curl -X GET "http://localhost:8000/api/v1/user-transactions?limit=50&skip=50"

    # Get up to 500 pending transactions
    curl -X GET "http://localhost:8000/api/v1/user-transactions?status=pending&limit=500"
    ```
    """
    try:
        # Request Start
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] GET /api/v1/user-transactions - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - status (query): {status_filter}")
        logger.info(f"   - limit (query): {limit}")
        logger.info(f"   - skip (query): {skip}")

        # Validate status filter if provided
        logger.info(f"🔍 Validating status filter...")
        valid_statuses = ["completed", "pending", "failed"]
        if status_filter and status_filter not in valid_statuses:
            logger.error(f"❌ Invalid status filter: {status_filter}")
            logger.error(f"   - Valid statuses: {', '.join(valid_statuses)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transaction status. Must be one of: {', '.join(valid_statuses)}"
            )
        logger.info(f"✅ Validation passed")

        # Build query filter
        match_stage = {}
        if status_filter:
            match_stage["status"] = status_filter

        logger.info(f"🔍 Building aggregation pipeline...")
        logger.info(f"   - match_stage: {match_stage}")

        # Query transactions with sorting (newest first) using aggregation
        from app.database.mongodb import database

        pipeline = []
        if match_stage:
            pipeline.append({"$match": match_stage})

        pipeline.extend([
            {"$sort": {"created_at": -1}},  # Sort by created_at descending (newest first)
            {"$skip": skip},
            {"$limit": limit}
        ])
        logger.info(f"   - pipeline stages: {len(pipeline)}")

        # Execute aggregation
        logger.info(f"🔄 Calling database.user_transactions.aggregate()...")
        transactions = await database.user_transactions.aggregate(pipeline).to_list(length=None)
        logger.info(f"🔎 Database Result: found={len(transactions)} transactions")

        # Get total count for the query
        logger.info(f"🔄 Calling database.user_transactions.count_documents()...")
        total_count = await database.user_transactions.count_documents(match_stage)
        logger.info(f"🔎 Database Result: total_count={total_count}")

        # Convert all transactions to JSON-serializable format
        logger.info(f"🔄 Serializing {len(transactions)} transactions...")
        transactions = [serialize_transaction_for_json(txn) for txn in transactions]
        logger.info(f"✅ Serialization complete")

        logger.info(f"✅ Retrieval successful:")
        logger.info(f"   - transactions_returned: {len(transactions)}")
        logger.info(f"   - total_matching: {total_count}")
        logger.info(f"   - status_filter: {status_filter}")
        logger.info(f"📤 Response: success=True, count={len(transactions)}, total={total_count}")

        return JSONResponse(content={
            "success": True,
            "data": {
                "transactions": transactions,
                "count": len(transactions),
                "total": total_count,
                "limit": limit,
                "skip": skip,
                "filters": {
                    "status": status_filter
                }
            }
        })

    except HTTPException as e:
        logger.error(f"❌ HTTPException:", exc_info=True)
        logger.error(f"   - Error: {e.detail}")
        logger.error(f"   - Status code: {e.status_code}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve all transactions:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Context: status_filter={status_filter}, limit={limit}, skip={skip}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transactions: {str(e)}"
        )


@router.get("/user/{email}")
async def get_user_transaction_history(
    request: Request,
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
                    "stripe_checkout_session_id": "SQR-1EC28E70F10B4D9E",
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
        # Request Start
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] GET /api/v1/user-transactions/user/{email} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - email (path): {email}")
        logger.info(f"   - status (query): {status_filter}")
        logger.info(f"   - limit (query): {limit}")
        logger.info(f"   - skip (query): {skip}")

        # Validate status filter if provided
        logger.info(f"🔍 Validating status filter...")
        valid_statuses = ["completed", "pending", "failed"]
        if status_filter and status_filter not in valid_statuses:
            logger.error(f"❌ Invalid status filter: {status_filter}")
            logger.error(f"   - Valid statuses: {', '.join(valid_statuses)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transaction status. Must be one of: {', '.join(valid_statuses)}"
            )
        logger.info(f"✅ Validation passed")

        # Build query filter
        match_stage = {"user_email": email}
        if status_filter:
            match_stage["status"] = status_filter

        logger.info(f"🔍 Building aggregation pipeline...")
        logger.info(f"   - match_stage: {match_stage}")

        # Query transactions with sorting (newest first) using aggregation
        from app.database.mongodb import database

        pipeline = [
            {"$match": match_stage},
            {"$sort": {"date": -1}},  # Sort by date descending (newest first)
            {"$skip": skip},
            {"$limit": limit}
        ]
        logger.info(f"   - pipeline stages: {len(pipeline)}")

        # Execute aggregation
        logger.info(f"🔄 Calling database.user_transactions.aggregate()...")
        transactions = await database.user_transactions.aggregate(pipeline).to_list(length=limit)
        logger.info(f"🔎 Database Result: found={len(transactions)} transactions")

        # Convert all transactions to JSON-serializable format
        logger.info(f"🔄 Serializing {len(transactions)} transactions...")
        transactions = [serialize_transaction_for_json(txn) for txn in transactions]
        logger.info(f"✅ Serialization complete")

        logger.info(f"✅ Retrieval successful:")
        logger.info(f"   - user_email: {email}")
        logger.info(f"   - transactions_count: {len(transactions)}")
        logger.info(f"   - status_filter: {status_filter}")
        logger.info(f"📤 Response: success=True, count={len(transactions)}")

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

    except HTTPException as e:
        logger.error(f"❌ HTTPException:", exc_info=True)
        logger.error(f"   - Error: {e.detail}")
        logger.error(f"   - Status code: {e.status_code}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve transaction history:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Context: email={email}, status_filter={status_filter}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transaction history: {str(e)}"
        )


@router.get("/{stripe_checkout_session_id}")
async def get_transaction_by_id(
    request: Request,
    stripe_checkout_session_id: str = Path(..., description="Square transaction ID")
):
    """
    Get transaction details by Square transaction ID.

    Retrieves complete transaction record including all 22 fields from the users_transactions collection.

    **Path Parameters:**
    - `stripe_checkout_session_id`: Square transaction ID (e.g., "SQR-1EC28E70F10B4D9E")

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
            "stripe_checkout_session_id": "SQR-1EC28E70F10B4D9E",
            "date": "2025-10-23T23:56:55.438Z",
            "status": "completed",
            "total_cost": 1.5,
            "stripe_payment_intent_id": "SQR-1EC28E70F10B4D9E",
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
        # Request Start
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] GET /api/v1/user-transactions/{stripe_checkout_session_id} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - stripe_checkout_session_id (path): {stripe_checkout_session_id}")

        # Database Operations
        logger.info(f"🔄 Calling get_user_transaction({stripe_checkout_session_id})...")
        transaction = await get_user_transaction(stripe_checkout_session_id)
        logger.info(f"🔎 Database Result: found={transaction is not None}")

        if not transaction:
            logger.error(f"❌ Transaction not found: {stripe_checkout_session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction not found: {stripe_checkout_session_id}"
            )

        # Serialize transaction for JSON (handles ObjectId, datetime, Decimal128)
        transaction = serialize_transaction_for_json(transaction)

        logger.info(f"✅ Retrieval successful:")
        logger.info(f"   - stripe_checkout_session_id: {stripe_checkout_session_id}")
        logger.info(f"   - user_email: {transaction.get('user_email')}")
        logger.info(f"   - status: {transaction.get('status')}")
        logger.info(f"📤 Response: success=True, transaction data included")

        return JSONResponse(content={
            "success": True,
            "data": transaction
        })

    except HTTPException as e:
        logger.error(f"❌ HTTPException:", exc_info=True)
        logger.error(f"   - Error: {e.detail}")
        logger.error(f"   - Status code: {e.status_code}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to retrieve transaction:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Context: stripe_checkout_session_id={stripe_checkout_session_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve transaction: {str(e)}"
        )


@router.patch("/{stripe_checkout_session_id}/payment-status")
async def update_transaction_payment_status(
    request: Request,
    stripe_checkout_session_id: str = Path(..., description="Square transaction ID"),
    payment_status: str = Query(..., description="New payment status (APPROVED, COMPLETED, CANCELED, FAILED)")
):
    """
    Update payment status for a transaction.

    Updates the payment_status field in the users_transactions collection.

    **Path Parameters:**
    - `stripe_checkout_session_id`: Square transaction ID (e.g., "SQR-1EC28E70F10B4D9E")

    **Query Parameters:**
    - `payment_status`: New payment status (APPROVED | COMPLETED | CANCELED | FAILED)

    **Response Example:**
    ```json
    {
        "success": true,
        "message": "Payment status updated successfully",
        "data": {
            "stripe_checkout_session_id": "SQR-1EC28E70F10B4D9E",
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
        # Request Start
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] PATCH /api/v1/user-transactions/{stripe_checkout_session_id}/payment-status - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - stripe_checkout_session_id (path): {stripe_checkout_session_id}")
        logger.info(f"   - payment_status (query): {payment_status}")

        # Check if transaction exists
        logger.info(f"🔄 Calling get_user_transaction({stripe_checkout_session_id})...")
        transaction = await get_user_transaction(stripe_checkout_session_id)
        logger.info(f"🔎 Database Result: found={transaction is not None}")

        if not transaction:
            logger.error(f"❌ Transaction not found: {stripe_checkout_session_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Transaction not found: {stripe_checkout_session_id}"
            )

        # Update payment status
        logger.info(f"🔄 Calling update_payment_status({stripe_checkout_session_id}, {payment_status})...")
        success = await update_payment_status(stripe_checkout_session_id, payment_status)
        logger.info(f"🔎 Database Result: success={success}")

        if not success:
            logger.error(f"❌ Failed to update payment status in database")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update payment status"
            )

        logger.info(f"✅ Payment status update successful:")
        logger.info(f"   - stripe_checkout_session_id: {stripe_checkout_session_id}")
        logger.info(f"   - new_payment_status: {payment_status}")
        logger.info(f"   - updated_at: {datetime.now(timezone.utc).isoformat()}")
        logger.info(f"📤 Response: success=True, message='Payment status updated successfully'")

        return JSONResponse(content={
            "success": True,
            "message": "Payment status updated successfully",
            "data": {
                "stripe_checkout_session_id": stripe_checkout_session_id,
                "payment_status": payment_status,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        })

    except HTTPException as e:
        logger.error(f"❌ HTTPException:", exc_info=True)
        logger.error(f"   - Error: {e.detail}")
        logger.error(f"   - Status code: {e.status_code}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update payment status:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Context: stripe_checkout_session_id={stripe_checkout_session_id}, payment_status={payment_status}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update payment status: {str(e)}"
        )
