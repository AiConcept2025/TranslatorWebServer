"""
Invoice management router for retrieving company invoices.
"""

from fastapi import APIRouter, Path, Query, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional
import logging
import json
from bson import ObjectId

from app.database.mongodb import database
from app.models.invoice import InvoiceListResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/invoices",
    tags=["Invoices"]
)


@router.get(
    "/company/{company_name}",
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
                                            "company_name": "Acme Translation Corp",
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
                                            "company_name": "Acme Translation Corp",
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
                                            "company_name": "Acme Translation Corp",
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
                                        "company_name": "Acme Translation Corp",
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
                                        "company_name": "Unknown Company",
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
                                            "company_name": "Acme Translation Corp",
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
                                        "company_name": "Acme Translation Corp",
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
                        "invalid_company_name": {
                            "summary": "Invalid company_name format",
                            "value": {
                                "detail": "Invalid company name format"
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
                        "detail": "Failed to retrieve company invoices: Database connection error"
                    }
                }
            }
        }
    }
)
async def get_company_invoices(
    company_name: str = Path(
        ...,
        description="Company name (e.g., 'Acme Translation Corp')",
        example="Acme Translation Corp"
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

    Retrieves a list of invoice records associated with a specific company name.
    Results can be filtered by invoice status and paginated using limit/skip parameters.

    ## Path Parameters
    - **company_name**: Company name (e.g., "Acme Translation Corp", "Iris Trading")

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
    - **company_name**: Company name
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
    curl -X GET "http://localhost:8000/api/v1/invoices/company/Acme%20Translation%20Corp"
    ```

    ### Get only sent invoices
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/Acme%20Translation%20Corp?status=sent"
    ```

    ### Get second page of invoices (pagination)
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/Iris%20Trading?skip=20&limit=20"
    ```

    ### Filter by paid invoices only
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/Acme%20Translation%20Corp?status=paid"
    ```

    ### Get overdue invoices with limit
    ```bash
    curl -X GET "http://localhost:8000/api/v1/invoices/company/Acme%20Translation%20Corp?status=overdue&limit=10"
    ```

    ## Notes
    - Returns empty array if no invoices match the criteria
    - All datetime fields are returned in ISO 8601 format
    - Total amount and tax amount are in dollars (not cents)
    - Status values are case-sensitive (lowercase)
    """
    try:
        logger.info(f"[INVOICES DEBUG] ========== START REQUEST ==========")
        logger.info(f"[INVOICES DEBUG] Request params: company_name={company_name}, status={status_filter}, limit={limit}, skip={skip}")

        # Validate status filter if provided
        valid_statuses = ["sent", "paid", "overdue", "cancelled"]
        if status_filter and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid invoice status. Must be one of: {', '.join(valid_statuses)}"
            )

        # Build aggregation pipeline - simplified query using company_name
        match_stage = {"company_name": company_name}
        logger.info(f"[INVOICES DEBUG] Querying for company_name: {company_name}")

        if status_filter:
            match_stage["status"] = status_filter

        logger.info(f"[INVOICES DEBUG] MongoDB match stage: {json.dumps(match_stage, default=str)}")

        # Aggregation pipeline:
        # 1. Match invoices by company_name (and optional status)
        # 2. Apply pagination with skip and limit
        pipeline = [
            {"$match": match_stage},
            {"$skip": skip},
            {"$limit": limit}
        ]

        # Log the complete aggregation pipeline
        logger.info(f"[INVOICES DEBUG] Full aggregation pipeline:")
        for i, stage in enumerate(pipeline):
            logger.info(f"[INVOICES DEBUG]   Stage {i}: {json.dumps(stage, default=str)}")

        # Execute aggregation
        invoices = await database.invoices.aggregate(pipeline).to_list(length=limit)

        logger.info(f"[INVOICES DEBUG] ========== RAW MONGODB RESULTS ==========")
        logger.info(f"[INVOICES DEBUG] MongoDB returned {len(invoices)} documents")

        if invoices:
            logger.info(f"[INVOICES DEBUG] Document _id list: {[str(inv['_id']) for inv in invoices]}")
            logger.info(f"[INVOICES DEBUG] Company names: {[inv.get('company_name', 'N/A') for inv in invoices]}")
            logger.info(f"[INVOICES DEBUG] Invoice numbers: {[inv.get('invoice_number', 'N/A') for inv in invoices]}")
            logger.info(f"[INVOICES DEBUG] Statuses: {[inv.get('status', 'N/A') for inv in invoices]}")

            # Log full raw documents for inspection
            for idx, invoice in enumerate(invoices):
                logger.info(f"[INVOICES DEBUG] === Raw Document {idx + 1} ===")
                # Convert ObjectId fields to string for logging
                log_invoice = {}
                for key, value in invoice.items():
                    if isinstance(value, ObjectId):
                        log_invoice[key] = f"ObjectId('{value}')"
                    else:
                        log_invoice[key] = value
                logger.info(f"[INVOICES DEBUG] {json.dumps(log_invoice, indent=2, default=str)}")
        else:
            logger.warning(f"[INVOICES DEBUG] NO DOCUMENTS RETURNED FROM MONGODB!")

        # Convert ObjectIds and datetime objects to JSON-serializable format
        logger.info(f"[INVOICES DEBUG] ========== STARTING SERIALIZATION ==========")
        for idx, invoice in enumerate(invoices):
            invoice["_id"] = str(invoice["_id"])

            # Convert subscription_id if it's an ObjectId (for legacy data)
            if "subscription_id" in invoice and isinstance(invoice["subscription_id"], ObjectId):
                logger.info(f"[INVOICES DEBUG] Document {idx + 1}: Converting subscription_id from ObjectId to string: {invoice['subscription_id']}")
                invoice["subscription_id"] = str(invoice["subscription_id"])
            elif "subscription_id" in invoice:
                logger.info(f"[INVOICES DEBUG] Document {idx + 1}: subscription_id is already a string: {invoice['subscription_id']} (type: {type(invoice['subscription_id']).__name__})")

            # Convert Decimal128 fields to float (for MongoDB Decimal128 types)
            from bson.decimal128 import Decimal128
            for key, value in list(invoice.items()):
                if isinstance(value, Decimal128):
                    logger.info(f"[INVOICES DEBUG] Document {idx + 1}: Converting {key} from Decimal128 to float")
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

            logger.info(f"[INVOICES DEBUG] Document {idx + 1} serialized successfully")

        logger.info(f"[INVOICES DEBUG] ========== SERIALIZATION COMPLETE ==========")
        logger.info(f"[INVOICES DEBUG] Total invoices after serialization: {len(invoices)}")

        # Build response payload
        response_payload = {
            "success": True,
            "data": {
                "invoices": invoices,
                "count": len(invoices),
                "limit": limit,
                "skip": skip,
                "filters": {
                    "company_name": company_name,
                    "status": status_filter
                }
            }
        }

        logger.info(f"[INVOICES DEBUG] ========== FINAL RESPONSE ==========")
        logger.info(f"[INVOICES DEBUG] Sending {len(invoices)} invoices to client")
        logger.info(f"[INVOICES DEBUG] Response invoice IDs: {[inv['_id'] for inv in invoices]}")
        logger.info(f"[INVOICES DEBUG] Full response JSON:")
        logger.info(f"[INVOICES DEBUG] {json.dumps(response_payload, indent=2, default=str)}")
        logger.info(f"[INVOICES DEBUG] ========== END REQUEST ==========")

        return JSONResponse(content=response_payload)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[INVOICES DEBUG] ========== ERROR OCCURRED ==========")
        logger.error(f"[INVOICES DEBUG] Error retrieving invoices for company {company_name}")
        logger.error(f"[INVOICES DEBUG] Error type: {type(e).__name__}")
        logger.error(f"[INVOICES DEBUG] Error message: {str(e)}")
        logger.error(f"[INVOICES DEBUG] Full traceback:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve invoices: {str(e)}"
        )
