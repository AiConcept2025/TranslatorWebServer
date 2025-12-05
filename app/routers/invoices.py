"""
Invoice management router for retrieving company invoices.
"""

from fastapi import APIRouter, Path, Query, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import logging
import json
from bson import ObjectId

from app.database.mongodb import database
from app.models.invoice import (
    InvoiceListResponse,
    InvoiceCreate,
    InvoiceUpdate,
    InvoiceCreateResponse,
    InvoiceUpdateResponse,
    InvoiceListItem
)
from app.middleware.auth_middleware import get_admin_user
from app.services.invoice_generation_service import invoice_generation_service, InvoiceGenerationError

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


@router.post(
    "",
    response_model=InvoiceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Invoice created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Invoice created successfully",
                        "data": {
                            "_id": "671b2bc25c62a0b61c084b34",
                            "invoice_id": None,
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
                    }
                }
            }
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_status": {
                            "summary": "Invalid status value",
                            "value": {
                                "detail": "Invalid invoice status. Must be one of: sent, paid, overdue, cancelled"
                            }
                        },
                        "duplicate_invoice": {
                            "summary": "Duplicate invoice number",
                            "value": {
                                "detail": "Invoice number already exists: INV-2025-001"
                            }
                        }
                    }
                }
            }
        },
        404: {
            "description": "Company or subscription not found",
            "content": {
                "application/json": {
                    "examples": {
                        "company_not_found": {
                            "summary": "Company not found",
                            "value": {
                                "detail": "Company not found: Unknown Company"
                            }
                        },
                        "subscription_not_found": {
                            "summary": "Subscription not found",
                            "value": {
                                "detail": "Subscription not found: sub_invalid"
                            }
                        }
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "total_amount"],
                                "msg": "ensure this value is greater than or equal to 0",
                                "type": "value_error.number.not_ge"
                            }
                        ]
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to create invoice: Database connection error"
                    }
                }
            }
        }
    }
)
async def create_invoice(invoice_data: InvoiceCreate):
    """
    Create a new invoice.

    Creates a new invoice record in the invoices collection with the provided data.
    Validates that the company and subscription exist before creating the invoice.

    ## Request Body
    - **company_name**: Company name (must exist in companies collection)
    - **subscription_id**: Subscription identifier (must exist in subscriptions collection)
    - **invoice_number**: Unique invoice number (e.g., INV-2025-001)
    - **invoice_date**: Invoice date in ISO 8601 format
    - **due_date**: Payment due date in ISO 8601 format
    - **total_amount**: Total amount in dollars (must be >= 0)
    - **tax_amount**: Tax amount in dollars (must be >= 0)
    - **status**: Invoice status (sent | paid | overdue | cancelled)
    - **pdf_url** *(optional)*: URL to the invoice PDF document

    ## Response
    Returns the created invoice with all fields including the generated MongoDB _id.

    ## Usage Examples

    ### Create a new sent invoice
    ```bash
    curl -X POST "http://localhost:8000/api/v1/invoices" \\
      -H "Content-Type: application/json" \\
      -d '{
        "company_name": "Acme Health LLC",
        "subscription_id": "sub_abc123",
        "invoice_number": "INV-2025-001",
        "invoice_date": "2025-10-08T00:07:00.396Z",
        "due_date": "2025-11-07T00:07:00.396Z",
        "total_amount": 106.00,
        "tax_amount": 6.00,
        "status": "sent",
        "pdf_url": "https://storage.example.com/invoices/INV-2025-001.pdf"
      }'
    ```

    ### Create invoice without PDF URL
    ```bash
    curl -X POST "http://localhost:8000/api/v1/invoices" \\
      -H "Content-Type: application/json" \\
      -d '{
        "company_name": "Acme Health LLC",
        "subscription_id": "sub_abc123",
        "invoice_number": "INV-2025-002",
        "invoice_date": "2025-11-08T00:07:00.396Z",
        "due_date": "2025-12-08T00:07:00.396Z",
        "total_amount": 200.00,
        "tax_amount": 12.00,
        "status": "sent"
      }'
    ```

    ## Notes
    - Invoice number must be unique across all invoices
    - Company and subscription must exist in their respective collections
    - Status values are case-sensitive (lowercase)
    - All datetime fields must be in ISO 8601 format
    - Total amount and tax amount are in dollars (not cents)
    """
    from datetime import datetime, timezone
    from bson.decimal128 import Decimal128

    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] POST /api/v1/invoices - START")
        logger.info(f"📥 Request Data: company_name={invoice_data.company_name}, "
                   f"invoice_number={invoice_data.invoice_number}, "
                   f"subscription_id={invoice_data.subscription_id}, "
                   f"total_amount={invoice_data.total_amount}, status={invoice_data.status}")

        # Validate status
        valid_statuses = ["sent", "paid", "overdue", "cancelled"]
        if invoice_data.status not in valid_statuses:
            logger.warning(f"❌ Invalid status: {invoice_data.status}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid invoice status. Must be one of: {', '.join(valid_statuses)}"
            )

        # Check if company exists
        logger.info(f"🔄 Checking if company exists: {invoice_data.company_name}")
        company = await database.company.find_one({"company_name": invoice_data.company_name})
        if not company:
            logger.warning(f"❌ Company not found: {invoice_data.company_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Company not found: {invoice_data.company_name}"
            )
        logger.info(f"✅ Company found: {invoice_data.company_name}")

        # Check if subscription exists (can be ObjectId or string)
        logger.info(f"🔄 Checking if subscription exists: {invoice_data.subscription_id}")
        try:
            # Try as ObjectId first
            subscription_query = {"_id": ObjectId(invoice_data.subscription_id)}
        except Exception:
            # Fall back to string comparison if not a valid ObjectId
            subscription_query = {"_id": invoice_data.subscription_id}

        subscription = await database.subscriptions.find_one(subscription_query)
        if not subscription:
            logger.warning(f"❌ Subscription not found: {invoice_data.subscription_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription not found: {invoice_data.subscription_id}"
            )
        logger.info(f"✅ Subscription found: {invoice_data.subscription_id}")

        # Check if invoice number already exists
        logger.info(f"🔄 Checking for duplicate invoice number: {invoice_data.invoice_number}")
        existing_invoice = await database.invoices.find_one({"invoice_number": invoice_data.invoice_number})
        if existing_invoice:
            logger.warning(f"❌ Duplicate invoice number: {invoice_data.invoice_number}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice number already exists: {invoice_data.invoice_number}"
            )

        # Prepare invoice document for MongoDB
        created_at = datetime.now(timezone.utc)
        invoice_doc = {
            "company_name": invoice_data.company_name,
            "subscription_id": invoice_data.subscription_id,
            "invoice_number": invoice_data.invoice_number,
            "invoice_date": datetime.fromisoformat(invoice_data.invoice_date.replace("Z", "+00:00")),
            "due_date": datetime.fromisoformat(invoice_data.due_date.replace("Z", "+00:00")),
            "total_amount": invoice_data.total_amount,
            "tax_amount": invoice_data.tax_amount,
            "status": invoice_data.status,
            "pdf_url": invoice_data.pdf_url,
            "payment_applications": [],
            "created_at": created_at
        }

        # Insert invoice into database
        logger.info(f"🔄 Inserting invoice into database...")
        result = await database.invoices.insert_one(invoice_doc)
        logger.info(f"✅ Invoice created: _id={result.inserted_id}")

        # Fetch the created invoice
        created_invoice = await database.invoices.find_one({"_id": result.inserted_id})

        # Serialize for JSON response
        created_invoice["_id"] = str(created_invoice["_id"])

        # Convert datetime fields to ISO format
        datetime_fields = ["invoice_date", "due_date", "created_at"]
        for field in datetime_fields:
            if field in created_invoice and hasattr(created_invoice[field], "isoformat"):
                created_invoice[field] = created_invoice[field].isoformat()

        # Convert datetime in payment_applications array
        if "payment_applications" in created_invoice and isinstance(created_invoice["payment_applications"], list):
            for payment_app in created_invoice["payment_applications"]:
                if "applied_date" in payment_app and hasattr(payment_app["applied_date"], "isoformat"):
                    payment_app["applied_date"] = payment_app["applied_date"].isoformat()

        # Convert Decimal128 if present
        for key, value in list(created_invoice.items()):
            if isinstance(value, Decimal128):
                created_invoice[key] = float(value.to_decimal())

        response_payload = {
            "success": True,
            "message": "Invoice created successfully",
            "data": created_invoice
        }

        logger.info(f"📤 Response: success=True, invoice_id={created_invoice['_id']}, "
                   f"invoice_number={created_invoice['invoice_number']}")

        return JSONResponse(content=response_payload, status_code=status.HTTP_201_CREATED)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create invoice:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create invoice: {str(e)}"
        )


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceUpdateResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Invoice updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Invoice updated successfully",
                        "data": {
                            "_id": "671b2bc25c62a0b61c084b34",
                            "invoice_id": None,
                            "company_name": "Acme Health LLC",
                            "subscription_id": "sub_abc123",
                            "invoice_number": "INV-2025-001",
                            "invoice_date": "2025-10-08T00:07:00.396Z",
                            "due_date": "2025-11-07T00:07:00.396Z",
                            "total_amount": 106.00,
                            "tax_amount": 6.00,
                            "status": "paid",
                            "pdf_url": "https://storage.example.com/invoices/INV-2025-001.pdf",
                            "payment_applications": [],
                            "created_at": "2025-10-08T00:07:00.396Z"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request data",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid invoice status. Must be one of: sent, paid, overdue, cancelled"
                    }
                }
            }
        },
        404: {
            "description": "Invoice not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invoice not found: 671b2bc25c62a0b61c084b34"
                    }
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "total_amount"],
                                "msg": "ensure this value is greater than or equal to 0",
                                "type": "value_error.number.not_ge"
                            }
                        ]
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to update invoice: Database connection error"
                    }
                }
            }
        }
    }
)
async def update_invoice(
    invoice_id: str = Path(
        ...,
        description="MongoDB ObjectId of the invoice to update",
        example="671b2bc25c62a0b61c084b34"
    ),
    update_data: InvoiceUpdate = ...
):
    """
    Update an existing invoice.

    Updates invoice fields. Only provided fields will be updated.
    Note: company_name, subscription_id, and invoice_number are immutable and cannot be changed.

    ## Path Parameters
    - **invoice_id**: MongoDB ObjectId of the invoice (24-character hex string)

    ## Request Body (all fields optional)
    - **status**: Invoice status (sent | paid | overdue | cancelled)
    - **invoice_date**: Invoice date in ISO 8601 format
    - **due_date**: Payment due date in ISO 8601 format
    - **total_amount**: Total amount in dollars (must be >= 0)
    - **tax_amount**: Tax amount in dollars (must be >= 0)
    - **pdf_url**: URL to the invoice PDF document

    ## Response
    Returns the updated invoice with all fields.

    ## Usage Examples

    ### Update invoice status to paid
    ```bash
    curl -X PATCH "http://localhost:8000/api/v1/invoices/671b2bc25c62a0b61c084b34" \\
      -H "Content-Type: application/json" \\
      -d '{"status": "paid"}'
    ```

    ### Update PDF URL
    ```bash
    curl -X PATCH "http://localhost:8000/api/v1/invoices/671b2bc25c62a0b61c084b34" \\
      -H "Content-Type: application/json" \\
      -d '{"pdf_url": "https://storage.example.com/invoices/INV-2025-001-updated.pdf"}'
    ```

    ### Update multiple fields
    ```bash
    curl -X PATCH "http://localhost:8000/api/v1/invoices/671b2bc25c62a0b61c084b34" \\
      -H "Content-Type: application/json" \\
      -d '{
        "status": "paid",
        "total_amount": 110.00,
        "tax_amount": 10.00
      }'
    ```

    ## Notes
    - Invoice number, company_name, and subscription_id are immutable
    - Status values are case-sensitive (lowercase)
    - All datetime fields must be in ISO 8601 format
    - Total amount and tax amount are in dollars (not cents)
    - Only fields present in the request will be updated
    """
    from datetime import datetime, timezone
    from bson.decimal128 import Decimal128

    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] PATCH /api/v1/invoices/{invoice_id} - START")
        logger.info(f"📥 Request Parameters: invoice_id={invoice_id}")

        # Get only fields that were actually set in the request
        update_dict = update_data.model_dump(exclude_unset=True)
        logger.info(f"📨 Update Data: {update_dict}")

        # Validate ObjectId
        try:
            obj_id = ObjectId(invoice_id)
        except Exception:
            logger.warning(f"❌ Invalid ObjectId format: {invoice_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid invoice ID format: {invoice_id}"
            )

        # Check if invoice exists
        logger.info(f"🔄 Checking if invoice exists: {invoice_id}")
        existing_invoice = await database.invoices.find_one({"_id": obj_id})
        if not existing_invoice:
            logger.warning(f"❌ Invoice not found: {invoice_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice not found: {invoice_id}"
            )
        logger.info(f"✅ Invoice found: {invoice_id}")

        # If no fields to update, return current invoice
        if not update_dict:
            logger.info(f"⚠️ No fields to update")
            # Serialize and return existing invoice
            existing_invoice["_id"] = str(existing_invoice["_id"])
            datetime_fields = ["invoice_date", "due_date", "created_at"]
            for field in datetime_fields:
                if field in existing_invoice and hasattr(existing_invoice[field], "isoformat"):
                    existing_invoice[field] = existing_invoice[field].isoformat()
            for key, value in list(existing_invoice.items()):
                if isinstance(value, Decimal128):
                    existing_invoice[key] = float(value.to_decimal())

            return JSONResponse(content={
                "success": True,
                "message": "Invoice updated successfully",
                "data": existing_invoice
            })

        # Validate status if provided
        if "status" in update_dict:
            valid_statuses = ["sent", "paid", "overdue", "cancelled"]
            if update_dict["status"] not in valid_statuses:
                logger.warning(f"❌ Invalid status: {update_dict['status']}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid invoice status. Must be one of: {', '.join(valid_statuses)}"
                )

        # Convert ISO date strings to datetime objects if present
        if "invoice_date" in update_dict and update_dict["invoice_date"]:
            update_dict["invoice_date"] = datetime.fromisoformat(
                update_dict["invoice_date"].replace("Z", "+00:00")
            )
        if "due_date" in update_dict and update_dict["due_date"]:
            update_dict["due_date"] = datetime.fromisoformat(
                update_dict["due_date"].replace("Z", "+00:00")
            )

        # Update invoice in database
        logger.info(f"🔄 Updating invoice in database...")
        logger.info(f"📨 Final update data keys: {list(update_dict.keys())}")
        result = await database.invoices.update_one(
            {"_id": obj_id},
            {"$set": update_dict}
        )

        if result.modified_count == 0:
            logger.warning(f"⚠️ No changes made to invoice: {invoice_id}")
        else:
            logger.info(f"✅ Invoice updated: modified_count={result.modified_count}")

        # Fetch updated invoice
        updated_invoice = await database.invoices.find_one({"_id": obj_id})

        # Serialize for JSON response
        updated_invoice["_id"] = str(updated_invoice["_id"])

        # Convert datetime fields to ISO format
        datetime_fields = ["invoice_date", "due_date", "created_at"]
        for field in datetime_fields:
            if field in updated_invoice and hasattr(updated_invoice[field], "isoformat"):
                updated_invoice[field] = updated_invoice[field].isoformat()

        # Convert datetime in payment_applications array
        if "payment_applications" in updated_invoice and isinstance(updated_invoice["payment_applications"], list):
            for payment_app in updated_invoice["payment_applications"]:
                if "applied_date" in payment_app and hasattr(payment_app["applied_date"], "isoformat"):
                    payment_app["applied_date"] = payment_app["applied_date"].isoformat()

        # Convert Decimal128 if present
        for key, value in list(updated_invoice.items()):
            if isinstance(value, Decimal128):
                updated_invoice[key] = float(value.to_decimal())

        response_payload = {
            "success": True,
            "message": "Invoice updated successfully",
            "data": updated_invoice
        }

        logger.info(f"📤 Response: success=True, invoice_id={updated_invoice['_id']}, "
                   f"invoice_number={updated_invoice['invoice_number']}")

        # Verify all fields are serializable before returning
        logger.info(f"🔍 Final serialization check before response...")
        for key, value in updated_invoice.items():
            logger.info(f"   {key}: {type(value).__name__} = {value}")

        return JSONResponse(content=response_payload)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to update invoice:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Invoice ID: {invoice_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update invoice: {str(e)}"
        )


@router.post(
    "/generate-quarterly",
    response_model=InvoiceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Quarterly Invoice",
    description="Generate a quarterly invoice for a subscription with line items (Admin only)",
    responses={
        201: {
            "description": "Invoice generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Q1 invoice generated successfully",
                        "data": {
                            "_id": "674e1234567890abcdef1234",
                            "company_name": "Acme Corporation",
                            "subscription_id": "674a1234567890abcdef5678",
                            "invoice_number": "INV-2025-Q1-def567",
                            "invoice_date": "2025-04-01T00:00:00Z",
                            "due_date": "2025-05-01T00:00:00Z",
                            "total_amount": 323.30,
                            "tax_amount": 18.30,
                            "status": "sent",
                            "billing_period": {
                                "period_numbers": [1, 2, 3],
                                "period_start": "2025-01-01T00:00:00Z",
                                "period_end": "2025-03-31T23:59:59Z"
                            },
                            "line_items": [
                                {
                                    "description": "Base Subscription - Q1",
                                    "period_numbers": [1, 2, 3],
                                    "quantity": 3,
                                    "unit_price": 100.00,
                                    "amount": 300.00
                                },
                                {
                                    "description": "Overage - Period 1",
                                    "period_numbers": [1],
                                    "quantity": 50,
                                    "unit_price": 0.10,
                                    "amount": 5.00
                                }
                            ],
                            "subtotal": 305.00,
                            "amount_paid": 0.0,
                            "created_at": "2025-04-01T00:00:00Z"
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid quarter or subscription not found"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin only)"},
        500: {"description": "Internal server error"}
    }
)
async def generate_quarterly_invoice(
    subscription_id: str = Query(..., description="Subscription ID"),
    quarter: int = Query(..., ge=1, le=4, description="Quarter number (1-4)"),
    admin: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Generate a quarterly invoice with line items for a subscription.

    **Admin Only**

    This endpoint creates an invoice for a specific quarter (Q1-Q4) of a subscription,
    including:
    - Base subscription charges (monthly price × 3 months)
    - Overage charges (units used beyond allocation)
    - Billing period information
    - Itemized line items

    Args:
        subscription_id: Subscription ObjectId
        quarter: Quarter number (1=Q1/Jan-Mar, 2=Q2/Apr-Jun, 3=Q3/Jul-Sep, 4=Q4/Oct-Dec)
        admin: Admin user (injected by auth middleware)

    Returns:
        InvoiceCreateResponse with generated invoice data

    Raises:
        HTTPException 400: If subscription not found or quarter invalid
        HTTPException 401: If not authenticated
        HTTPException 403: If not admin
        HTTPException 500: If invoice generation fails
    """
    logger.info(f"[API] Admin {admin.get('email')} generating Q{quarter} invoice for subscription {subscription_id}")

    try:
        # Generate invoice using service
        invoice_doc = await invoice_generation_service.generate_quarterly_invoice(
            subscription_id=subscription_id,
            quarter=quarter
        )

        logger.info(f"[API] Invoice generated: {invoice_doc.get('invoice_number')}")

        # Serialize for JSON response
        invoice_doc["_id"] = str(invoice_doc["_id"])

        # Convert datetime fields to ISO format
        datetime_fields = ["invoice_date", "due_date", "created_at", "updated_at"]
        for field in datetime_fields:
            if field in invoice_doc and hasattr(invoice_doc[field], "isoformat"):
                invoice_doc[field] = invoice_doc[field].isoformat()

        # Convert billing_period datetimes
        if "billing_period" in invoice_doc and invoice_doc["billing_period"]:
            bp = invoice_doc["billing_period"]
            if "period_start" in bp and hasattr(bp["period_start"], "isoformat"):
                bp["period_start"] = bp["period_start"].isoformat()
            if "period_end" in bp and hasattr(bp["period_end"], "isoformat"):
                bp["period_end"] = bp["period_end"].isoformat()

        # Create InvoiceListItem for response
        invoice_item = InvoiceListItem(**invoice_doc)

        response_payload = {
            "success": True,
            "message": f"Q{quarter} invoice generated successfully",
            "data": invoice_item
        }

        logger.info(f"[API] Returning invoice: {invoice_doc['invoice_number']}")

        return InvoiceCreateResponse(**response_payload)

    except InvoiceGenerationError as e:
        logger.error(f"[API] Invoice generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"[API] Unexpected error generating invoice:", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate invoice: {str(e)}"
        )
