"""
Invoice management router for retrieving company invoices.
"""

from fastapi import APIRouter, Path, Query, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional
import logging
from bson import ObjectId

from app.database.mongodb import database
from app.models.invoice import InvoiceListResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/invoices",
    tags=["Invoices"]
)


@router.get(
    "/company/{company_id}",
    response_model=InvoiceListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully retrieved company invoices",
            "content": {
                "application/json": {
                    "examples": {
                        "multiple_invoices": {
                            "summary": "Multiple invoices",
                            "description": "Example response with multiple invoices for a company",
                            "value": {
                                "success": True,
                                "data": {
                                    "invoices": [
                                        {
                                            "_id": "671b2bc25c62a0b61c084b34",
                                            "invoice_id": "inv_001",
                                            "company_id": "cmp_00123",
                                            "company_name": "Acme Health LLC",
                                            "subscription_id": "sub_abc123",
                                            "invoice_number": "INV-2025-001",
                                            "invoice_date": "2025-10-08T00:07:00.396Z",
                                            "due_date": "2025-11-07T00:07:00.396Z",
                                            "total_amount": 106.00,
                                            "tax_amount": 6.00,
                                            "status": "sent",
                                            "pdf_url": "https://storage.example.com/invoices/INV-2025-001.pdf",
                                            "payment_applications": [],
                                            "created_at": "2025-10-08T00:07:00.396Z"
                                        },
                                        {
                                            "_id": "671b2bc25c62a0b61c084b35",
                                            "invoice_id": "inv_002",
                                            "company_id": "cmp_00123",
                                            "company_name": "Acme Health LLC",
                                            "subscription_id": "sub_abc123",
                                            "invoice_number": "INV-2025-002",
                                            "invoice_date": "2025-09-08T00:07:00.396Z",
                                            "due_date": "2025-10-08T00:07:00.396Z",
                                            "total_amount": 212.00,
                                            "tax_amount": 12.00,
                                            "status": "paid",
                                            "pdf_url": "https://storage.example.com/invoices/INV-2025-002.pdf",
                                            "payment_applications": [],
                                            "created_at": "2025-09-08T00:07:00.396Z"
                                        },
                                        {
                                            "_id": "671b2bc25c62a0b61c084b36",
                                            "invoice_id": "inv_003",
                                            "company_id": "cmp_00123",
                                            "company_name": "Acme Health LLC",
                                            "subscription_id": "sub_abc123",
                                            "invoice_number": "INV-2025-003",
                                            "invoice_date": "2025-08-08T00:07:00.396Z",
                                            "due_date": "2025-09-08T00:07:00.396Z",
                                            "total_amount": 318.00,
                                            "tax_amount": 18.00,
                                            "status": "overdue",
                                            "pdf_url": "https://storage.example.com/invoices/INV-2025-003.pdf",
                                            "payment_applications": [],
                                            "created_at": "2025-08-08T00:07:00.396Z"
                                        }
                                    ],
                                    "count": 3,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "company_id": "cmp_00123",
                                        "status": None
                                    }
                                }
                            }
                        },
                        "empty_result": {
                            "summary": "No invoices found",
                            "description": "Response when no invoices match the query filters",
                            "value": {
                                "success": True,
                                "data": {
                                    "invoices": [],
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
                        "filtered_by_status": {
                            "summary": "Filtered by status",
                            "description": "Example showing filtered invoices by status",
                            "value": {
                                "success": True,
                                "data": {
                                    "invoices": [
                                        {
                                            "_id": "671b2bc25c62a0b61c084b34",
                                            "invoice_id": "inv_001",
                                            "company_id": "cmp_00123",
                                            "company_name": "Acme Health LLC",
                                            "subscription_id": "sub_abc123",
                                            "invoice_number": "INV-2025-001",
                                            "invoice_date": "2025-10-08T00:07:00.396Z",
                                            "due_date": "2025-11-07T00:07:00.396Z",
                                            "total_amount": 106.00,
                                            "tax_amount": 6.00,
                                            "status": "sent",
                                            "pdf_url": "https://storage.example.com/invoices/INV-2025-001.pdf",
                                            "payment_applications": [],
                                            "created_at": "2025-10-08T00:07:00.396Z"
                                        }
                                    ],
                                    "count": 1,
                                    "limit": 50,
                                    "skip": 0,
                                    "filters": {
                                        "company_id": "cmp_00123",
                                        "status": "sent"
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
                                "detail": "Invalid invoice status. Must be one of: sent, paid, overdue, cancelled"
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
                        "detail": "Failed to retrieve company invoices: Database connection error"
                    }
                }
            }
        }
    }
)
async def get_company_invoices(
    company_id: str = Path(
        ...,
        description="Company identifier (e.g., cmp_00123)",
        example="cmp_00123"
    ),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by invoice status. Valid values: sent, paid, overdue, cancelled",
        example="sent",
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
    Get all invoices for a company with filtering and pagination.

    Retrieves a list of invoice records associated with a specific company ID.
    Results can be filtered by invoice status and paginated using limit/skip parameters.

    ## Path Parameters
    - **company_id**: Company identifier (format: cmp_XXXXX)

    ## Query Parameters
    - **status** *(optional)*: Filter invoices by status
        - `sent`: Invoices that have been sent to the customer
        - `paid`: Invoices that have been paid
        - `overdue`: Invoices past their due date
        - `cancelled`: Cancelled invoices
    - **limit** *(default: 50)*: Maximum number of records to return (1-100)
    - **skip** *(default: 0)*: Number of records to skip (for pagination)

    ## Response Structure
    Returns a standardized response wrapper containing:
    - **success**: Boolean indicating request success
    - **data**: Object containing:
        - **invoices**: Array of invoice records
        - **count**: Number of invoices in this response
        - **limit**: Limit value used
        - **skip**: Skip value used
        - **filters**: Applied filter values

    ## Invoice Record Fields
    Each invoice record includes:
    - **_id**: MongoDB ObjectId (24-character hex string)
    - **invoice_id**: Legacy invoice ID (optional)
    - **company_id**: Company identifier
    - **company_name**: Full company name (optional)
    - **subscription_id**: Subscription identifier
    - **invoice_number**: Unique invoice number (e.g., INV-2025-001)
    - **invoice_date**: Invoice date (ISO 8601)
    - **due_date**: Payment due date (ISO 8601)
    - **total_amount**: Total amount in dollars (e.g., 106.00)
    - **tax_amount**: Tax amount in dollars (e.g., 6.00)
    - **status**: Current invoice status
    - **pdf_url**: URL to invoice PDF (optional)
    - **payment_applications**: Array of payment applications
    - **created_at**: Record creation timestamp (ISO 8601)

    ## Usage Examples

    ### Get all invoices for a company
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/cmp_00123"
    ```

    ### Get only sent invoices
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/cmp_00123?status=sent"
    ```

    ### Get second page of invoices (pagination)
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/cmp_00123?skip=20&limit=20"
    ```

    ### Filter by paid invoices only
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/cmp_00123?status=paid"
    ```

    ### Get overdue invoices with limit
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/cmp_00123?status=overdue&limit=10"
    ```

    ## Notes
    - Returns empty array if no invoices match the criteria
    - All datetime fields are returned in ISO 8601 format
    - Total amount and tax amount are in dollars (not cents)
    - Status values are case-sensitive (lowercase)
    """
    try:
        logger.info(f"Fetching invoices for company {company_id}, status={status_filter}, limit={limit}, skip={skip}")

        # Validate status filter if provided
        valid_statuses = ["sent", "paid", "overdue", "cancelled"]
        if status_filter and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid invoice status. Must be one of: {', '.join(valid_statuses)}"
            )

        # Build aggregation pipeline with $lookup to join company data
        # Handle both string and ObjectId company_id formats
        try:
            company_id_obj = ObjectId(company_id)
            match_stage = {"company_id": {"$in": [company_id, company_id_obj]}}
        except:
            # If company_id is not a valid ObjectId, just use string
            match_stage = {"company_id": company_id}

        if status_filter:
            match_stage["status"] = status_filter

        # Aggregation pipeline:
        # 1. Match invoices by company_id (and optional status)
        # 2. Lookup company data from company collection
        # 3. Add company_name field from the joined company document
        pipeline = [
            {"$match": match_stage},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "company",  # Collection name in MongoDB
                    "let": {"invoice_company_id": "$company_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$or": [
                                        {"$eq": ["$_id", "$$invoice_company_id"]},  # Match as ObjectId
                                        {"$eq": [{"$toString": "$_id"}, {"$toString": "$$invoice_company_id"}]}  # Match as string
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "company_data"
                }
            },
            {
                "$addFields": {
                    "company_name": {"$arrayElemAt": ["$company_data.company_name", 0]}
                }
            },
            {
                "$project": {
                    "company_data": 0  # Remove the joined company_data array
                }
            }
        ]

        # Execute aggregation
        invoices = await database.invoices.aggregate(pipeline).to_list(length=limit)

        # Convert ObjectIds and datetime objects to JSON-serializable format
        for invoice in invoices:
            invoice["_id"] = str(invoice["_id"])

            # Convert ObjectId fields to strings (for legacy data)
            objectid_fields = ["company_id", "subscription_id"]
            for field in objectid_fields:
                if field in invoice and isinstance(invoice[field], ObjectId):
                    invoice[field] = str(invoice[field])

            # Convert Decimal128 fields to float (for MongoDB Decimal128 types)
            from bson.decimal128 import Decimal128
            for key, value in list(invoice.items()):
                if isinstance(value, Decimal128):
                    invoice[key] = float(value.to_decimal())

            # Convert datetime fields to ISO format strings
            datetime_fields = ["invoice_date", "due_date", "created_at"]
            for field in datetime_fields:
                if field in invoice and hasattr(invoice[field], "isoformat"):
                    invoice[field] = invoice[field].isoformat()

            # Convert datetime in payment_applications array
            if "payment_applications" in invoice and isinstance(invoice["payment_applications"], list):
                for payment_app in invoice["payment_applications"]:
                    if "applied_date" in payment_app and hasattr(payment_app["applied_date"], "isoformat"):
                        payment_app["applied_date"] = payment_app["applied_date"].isoformat()

        logger.info(f"Found {len(invoices)} invoices for company {company_id}")

        return JSONResponse(content={
            "success": True,
            "data": {
                "invoices": invoices,
                "count": len(invoices),
                "limit": limit,
                "skip": skip,
                "filters": {
                    "company_id": company_id,
                    "status": status_filter
                }
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve invoices for company {company_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve invoices: {str(e)}"
        )
