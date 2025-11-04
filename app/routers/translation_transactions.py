"""
Translation transaction management router for retrieving company transactions.
"""

from fastapi import APIRouter, Path, Query, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional
import logging
from bson import ObjectId
from bson.decimal128 import Decimal128
from datetime import datetime

from app.database.mongodb import database
from app.models.translation_transaction import TranslationTransactionListResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/translation-transactions",
    tags=["Translation Transactions"]
)


def serialize_translation_transaction_for_json(txn: dict) -> dict:
    """
    Convert MongoDB translation transaction to JSON-serializable dict.

    Handles ObjectId, Decimal128, and datetime fields, including nested documents array.
    Follows CLAUDE.md Rule #1: MongoDB → JSON Serialization.

    Args:
        txn: Raw transaction document from MongoDB

    Returns:
        dict: JSON-serializable transaction with all types converted
    """
    # Convert ObjectId → string
    if "_id" in txn:
        txn["_id"] = str(txn["_id"])

    # Convert Decimal128 → float
    for key, value in list(txn.items()):
        if isinstance(value, Decimal128):
            txn[key] = float(value.to_decimal())

    # Convert top-level datetime → ISO strings
    datetime_fields = ["created_at", "updated_at"]
    for field in datetime_fields:
        if field in txn and hasattr(txn[field], "isoformat"):
            txn[field] = txn[field].isoformat()

    # ⚠️ CRITICAL: Convert nested documents array datetime fields
    # This prevents "Object of type datetime is not JSON serializable" errors
    if "documents" in txn and isinstance(txn["documents"], list):
        for doc in txn["documents"]:
            doc_datetime_fields = [
                "uploaded_at",
                "translated_at",
                "processing_started_at"
            ]
            for field in doc_datetime_fields:
                if field in doc and doc[field] is not None and hasattr(doc[field], "isoformat"):
                    doc[field] = doc[field].isoformat()

    return txn


@router.get(
    "/company/{company_name}",
    response_model=TranslationTransactionListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully retrieved company translation transactions",
            "content": {
                "application/json": {
                    "examples": {
                        "multiple_transactions": {
                            "summary": "Multiple transactions",
                            "description": "Example response with multiple translation transactions for a company",
                            "value": {
                                "success": True,
                                "data": {
                                    "transactions": [
                                        {
                                            "_id": "68fe1edeac2359ccbc6b05b2",
                                            "transaction_id": "TXN-20FEF6D8FE",
                                            "user_id": "danishevsky@yahoo.com",
                                            "original_file_url": "https://docs.google.com/document/d/1ABCdef123/edit",
                                            "translated_file_url": "",
                                            "source_language": "en",
                                            "target_language": "fr",
                                            "file_name": "TCG.docx",
                                            "file_size": 838186,
                                            "units_count": 33,
                                            "price_per_unit": 0.01,
                                            "total_price": 0.33,
                                            "status": "started",
                                            "error_message": "",
                                            "created_at": "2025-10-26T13:15:10.913+00:00",
                                            "updated_at": "2025-10-26T13:15:10.913+00:00",
                                            "company_name": "Iris Trading",
                                            "subscription_id": "68fa6add22b0c739f4f4b273",
                                            "unit_type": "page"
                                        },
                                        {
                                            "_id": "68fe1edeac2359ccbc6b05b3",
                                            "transaction_id": "TXN-30FEF6D8FF",
                                            "user_id": "user@company.com",
                                            "original_file_url": "https://docs.google.com/document/d/2XYZabc456/edit",
                                            "translated_file_url": "https://docs.google.com/document/d/3XYZabc789/edit",
                                            "source_language": "es",
                                            "target_language": "de",
                                            "file_name": "Document.pdf",
                                            "file_size": 524288,
                                            "units_count": 15,
                                            "price_per_unit": 0.01,
                                            "total_price": 0.15,
                                            "status": "confirmed",
                                            "error_message": "",
                                            "created_at": "2025-10-25T10:30:00.000+00:00",
                                            "updated_at": "2025-10-25T11:00:00.000+00:00",
                                            "company_name": "Iris Trading",
                                            "subscription_id": "68fa6add22b0c739f4f4b273",
                                            "unit_type": "page"
                                        },
                                        {
                                            "_id": "68fe1edeac2359ccbc6b05b4",
                                            "transaction_id": "TXN-40FEF6D8FG",
                                            "user_id": "admin@company.com",
                                            "original_file_url": "https://docs.google.com/document/d/3XYZabc789/edit",
                                            "translated_file_url": "",
                                            "source_language": "fr",
                                            "target_language": "en",
                                            "file_name": "Report.docx",
                                            "file_size": 1048576,
                                            "units_count": 50,
                                            "price_per_unit": 0.01,
                                            "total_price": 0.50,
                                            "status": "pending",
                                            "error_message": "",
                                            "created_at": "2025-10-24T08:00:00.000+00:00",
                                            "updated_at": "2025-10-24T08:30:00.000+00:00",
                                            "company_name": "Iris Trading",
                                            "subscription_id": "68fa6add22b0c739f4f4b273",
                                            "unit_type": "page"
                                        }
                                    ],
                                    "count": 3,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "status": None
                                    }
                                }
                            }
                        },
                        "empty_result": {
                            "summary": "No transactions found",
                            "description": "Response when no transactions match the query filters",
                            "value": {
                                "success": True,
                                "data": {
                                    "transactions": [],
                                    "count": 0,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "status": None
                                    }
                                }
                            }
                        },
                        "filtered_by_status": {
                            "summary": "Filtered by status",
                            "description": "Example showing filtered transactions by confirmed status",
                            "value": {
                                "success": True,
                                "data": {
                                    "transactions": [
                                        {
                                            "_id": "68fe1edeac2359ccbc6b05b3",
                                            "transaction_id": "TXN-30FEF6D8FF",
                                            "user_id": "user@company.com",
                                            "original_file_url": "https://docs.google.com/document/d/2XYZabc456/edit",
                                            "translated_file_url": "https://docs.google.com/document/d/3XYZabc789/edit",
                                            "source_language": "es",
                                            "target_language": "de",
                                            "file_name": "Document.pdf",
                                            "file_size": 524288,
                                            "units_count": 15,
                                            "price_per_unit": 0.01,
                                            "total_price": 0.15,
                                            "status": "confirmed",
                                            "error_message": "",
                                            "created_at": "2025-10-25T10:30:00.000+00:00",
                                            "updated_at": "2025-10-25T11:00:00.000+00:00",
                                            "company_name": "Iris Trading",
                                            "subscription_id": "68fa6add22b0c739f4f4b273",
                                            "unit_type": "page"
                                        }
                                    ],
                                    "count": 1,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "status": "confirmed"
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
                            "summary": "Invalid company_name format",
                            "value": {
                                "detail": "Invalid company identifier format"
                            }
                        },
                        "invalid_status": {
                            "summary": "Invalid status filter",
                            "value": {
                                "detail": "Invalid transaction status. Must be one of: started, confirmed, pending, failed"
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
                        "detail": "Company not found: 68ec42a48ca6a1781d9fe999"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to retrieve company translation transactions: Database connection error"
                    }
                }
            }
        }
    }
)
async def get_company_translation_transactions(
    company_name: str = Path(
        ...,
        description="Company name",
        example="Iris Trading"
    ),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by transaction status. Valid values: started, confirmed, pending, failed",
        example="started",
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
    Get all translation transactions for a company with filtering and pagination.

    Retrieves a list of translation transaction records associated with a specific company name.
    Results can be filtered by transaction status and paginated using limit/skip parameters.

    ## Path Parameters
    - **company_name**: Company name (string)

    ## Query Parameters
    - **status** *(optional)*: Filter transactions by status
        - `started`: Transactions that have been initiated
        - `confirmed`: Transactions that have been confirmed and files moved to Inbox
        - `pending`: Transactions pending processing
        - `failed`: Transactions that encountered errors
    - **limit** *(default: 50)*: Maximum number of records to return (1-100)
    - **skip** *(default: 0)*: Number of records to skip (for pagination)

    ## Response Structure
    Returns a standardized response wrapper containing:
    - **success**: Boolean indicating request success
    - **data**: Object containing:
        - **transactions**: Array of transaction records
        - **count**: Number of transactions in this response
        - **limit**: Limit value used
        - **skip**: Skip value used
        - **filters**: Applied filter values

    ## Transaction Record Fields
    Each transaction record includes:
    - **_id**: MongoDB ObjectId (24-character hex string)
    - **transaction_id**: Unique transaction identifier (e.g., TXN-20FEF6D8FE)
    - **user_id**: User email address
    - **original_file_url**: Google Drive URL of original file
    - **translated_file_url**: Google Drive URL of translated file (empty if not yet translated)
    - **source_language**: Source language code
    - **target_language**: Target language code
    - **file_name**: Original filename
    - **file_size**: File size in bytes
    - **units_count**: Number of translation units (pages or words)
    - **price_per_unit**: Price per translation unit in dollars
    - **total_price**: Total transaction price in dollars
    - **status**: Current transaction status
    - **error_message**: Error message if status is failed
    - **created_at**: Record creation timestamp (ISO 8601)
    - **updated_at**: Record update timestamp (ISO 8601)
    - **company_name**: Company name (for enterprise transactions)
    - **company_name**: Company name (optional, from $lookup)
    - **subscription_id**: Subscription identifier (optional, for enterprise)
    - **unit_type**: Unit type for billing (page or word)

    ## Usage Examples

    ### Get all transactions for a company
    ```bash
    curl -X GET "http://localhost:8000/api/v1/translation-transactions/company/Iris%20Trading"
    ```

    ### Get only started transactions
    ```bash
    curl -X GET "http://localhost:8000/api/v1/translation-transactions/company/Iris%20Trading?status=started"
    ```

    ### Get second page of transactions (pagination)
    ```bash
    curl -X GET "http://localhost:8000/api/v1/translation-transactions/company/Iris%20Trading?skip=20&limit=20"
    ```

    ### Filter by confirmed transactions only
    ```bash
    curl -X GET "http://localhost:8000/api/v1/translation-transactions/company/Iris%20Trading?status=confirmed"
    ```

    ### Get failed transactions with limit
    ```bash
    curl -X GET "http://localhost:8000/api/v1/translation-transactions/company/Iris%20Trading?status=failed&limit=10"
    ```

    ## Notes
    - Returns empty array if no transactions match the criteria
    - All datetime fields are returned in ISO 8601 format
    - Total price and price per unit are in dollars (not cents)
    - Status values are case-sensitive (lowercase)
    - Company name is populated via $lookup from company collection
    """
    try:
        logger.info(f"Fetching translation transactions for company {company_name}, status={status_filter}, limit={limit}, skip={skip}")

        # Validate status filter if provided
        valid_statuses = ["started", "confirmed", "pending", "failed"]
        if status_filter and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid transaction status. Must be one of: {', '.join(valid_statuses)}"
            )

        # Build match stage using company_name
        match_stage = {"company_name": company_name}

        if status_filter:
            match_stage["status"] = status_filter

        # Aggregation pipeline:
        # 1. Match transactions by company_name (and optional status)
        # 2. Skip/limit for pagination
        pipeline = [
            {"$match": match_stage},
            {"$skip": skip},
            {"$limit": limit}
        ]

        # Execute aggregation
        transactions = await database.translation_transactions.aggregate(pipeline).to_list(length=limit)

        # Serialize all transactions (handles nested documents datetime fields)
        transactions = [serialize_translation_transaction_for_json(txn) for txn in transactions]

        logger.info(f"Found {len(transactions)} translation transactions for company {company_name}")

        return JSONResponse(content={
            "success": True,
            "data": {
                "transactions": transactions,
                "count": len(transactions),
                "limit": limit,
                "skip": skip,
                "filters": {
                    "company_name": company_name,
                    "status": status_filter
                }
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve translation transactions for company {company_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve translation transactions: {str(e)}"
        )


@router.get(
    "/companies",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully retrieved unique companies with translation transactions",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "companies": ["Iris Trading", "Tech Solutions", "Global Corp"],
                            "count": 3
                        }
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to retrieve companies: Database connection error"
                    }
                }
            }
        }
    }
)
async def get_companies_with_translations():
    """
    Get all unique company names that have translation transactions.

    Returns a list of unique company names from the translation_transactions collection.
    Only returns companies that have at least one transaction record.

    ## Response Structure
    Returns a standardized response wrapper containing:
    - **success**: Boolean indicating request success
    - **data**: Object containing:
        - **companies**: Array of unique company names (sorted alphabetically)
        - **count**: Number of unique companies

    ## Usage Examples

    ### Get all companies with transactions
    ```bash
    curl -X GET "http://localhost:8000/api/v1/translation-transactions/companies"
    ```

    ## Notes
    - Returns empty array if no transactions exist
    - Company names are sorted alphabetically
    - Only non-null company names are included
    - This endpoint dynamically reflects all companies in the database
    """
    try:
        logger.info("Fetching unique companies with translation transactions")

        # Use MongoDB distinct to get unique company names
        # Filter out null/None values
        companies = await database.translation_transactions.distinct(
            "company_name",
            {"company_name": {"$ne": None}}
        )

        # Sort alphabetically
        companies = sorted(companies)

        logger.info(f"Found {len(companies)} unique companies with translation transactions")

        return JSONResponse(content={
            "success": True,
            "data": {
                "companies": companies,
                "count": len(companies)
            }
        })

    except Exception as e:
        logger.error(f"Failed to retrieve companies: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve companies: {str(e)}"
        )
