"""
Enterprise documents router for viewing translated documents.
"""

from fastapi import APIRouter, Query, Depends, HTTPException, status
from typing import Optional, Dict, Any
import logging
import time

from app.database.mongodb import database
from app.middleware.auth_middleware import get_current_user, get_admin_user
from app.utils.serialization import serialize_for_json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/enterprise",
    tags=["Enterprise Documents"]
)


@router.get("/documents")
async def get_documents(
    search: Optional[str] = Query(None, description="Search by document name"),
    sort_by: str = Query("date", description="Sort by date or user"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all documents for the user's company with pagination, search, and sorting.

    Documents are unwound from the translation_transactions collection's documents array.
    Each document in the array becomes a separate row in the result.
    """
    start_time = time.time()
    company_name = current_user.get("company_name")
    user_email = current_user.get("email", "unknown")

    # Log request start with all parameters
    logger.info(
        f"[ENTERPRISE_DOCS_REQUEST] user={user_email} company={company_name} "
        f"search={search or 'none'} sort_by={sort_by} sort_order={sort_order} "
        f"skip={skip} limit={limit}"
    )

    if not company_name:
        logger.warning(f"[ENTERPRISE_DOCS_ERROR] Missing company_name for user {user_email}")
        raise HTTPException(status_code=403, detail="Corporate user required")

    # Build aggregation pipeline
    pipeline = []

    # Match by company
    pipeline.append({"$match": {"company_name": company_name}})

    # Unwind documents array (each document becomes a separate row)
    pipeline.append({"$unwind": "$documents"})

    # Search filter (if provided)
    if search:
        pipeline.append({
            "$match": {
                "documents.file_name": {"$regex": search, "$options": "i"}
            }
        })

    # Sort mapping
    sort_field = "created_at" if sort_by == "date" else "user_id"
    sort_direction = -1 if sort_order == "desc" else 1

    # Project fields for output
    pipeline.append({
        "$project": {
            "_id": 1,
            "file_name": "$documents.file_name",
            "original_link": "$documents.original_url",
            "translated_link": "$documents.translated_url",
            "status": "$documents.status",
            "created_at": "$created_at",
            "user_email": "$user_id",
            "transaction_id": "$transaction_id"
        }
    })

    # Sort
    pipeline.append({"$sort": {sort_field: sort_direction}})

    try:
        # Count total documents matching the query
        count_start = time.time()
        count_pipeline = pipeline.copy()
        count_pipeline.append({"$count": "total"})
        count_result = await database.translation_transactions.aggregate(count_pipeline).to_list(length=1)
        total = count_result[0]["total"] if count_result else 0
        count_duration = time.time() - count_start

        logger.debug(f"[ENTERPRISE_DOCS_COUNT] company={company_name} total={total} duration={count_duration:.3f}s")

        # Add pagination
        pipeline.append({"$skip": skip})
        pipeline.append({"$limit": limit})

        # Execute aggregation
        query_start = time.time()
        documents = await database.translation_transactions.aggregate(pipeline).to_list(length=limit)
        query_duration = time.time() - query_start

        logger.debug(f"[ENTERPRISE_DOCS_QUERY] company={company_name} retrieved={len(documents)} duration={query_duration:.3f}s")

        # Performance warning for slow queries
        if query_duration > 1.0:
            logger.warning(
                f"[ENTERPRISE_DOCS_SLOW_QUERY] company={company_name} duration={query_duration:.3f}s "
                f"search={search} sort_by={sort_by} skip={skip} limit={limit}"
            )

        # Serialize
        serialize_start = time.time()
        serialized_docs = [serialize_for_json(doc) for doc in documents]
        serialize_duration = time.time() - serialize_start

        total_duration = time.time() - start_time

        logger.info(
            f"[ENTERPRISE_DOCS_SUCCESS] company={company_name} user={user_email} "
            f"returned={len(serialized_docs)} total={total} "
            f"query_time={query_duration:.3f}s total_time={total_duration:.3f}s"
        )

        return {
            "success": True,
            "data": {
                "documents": serialized_docs,
                "total": total,
                "page": (skip // limit) + 1,
                "page_size": limit
            }
        }
    except Exception as e:
        error_duration = time.time() - start_time
        logger.error(
            f"[ENTERPRISE_DOCS_ERROR] company={company_name} user={user_email} "
            f"error={str(e)} error_type={type(e).__name__} duration={error_duration:.3f}s",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve documents: {str(e)}"
        )


@router.get("/invoices")
async def get_invoices(
    search: Optional[str] = Query(None, description="Search by invoice number"),
    sort_by: str = Query("date", description="Sort by date, amount, or due_date"),
    sort_order: str = Query("desc", description="asc or desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get all invoices for the user's company with pagination, search, and sorting.

    Returns a list of invoices filtered by company_name from the authenticated user.
    """
    start_time = time.time()
    company_name = current_user.get("company_name")
    user_email = current_user.get("email", "unknown")

    # Log request start with all parameters
    logger.info(
        f"[ENTERPRISE_INVOICES_REQUEST] user={user_email} company={company_name} "
        f"search={search or 'none'} sort_by={sort_by} sort_order={sort_order} "
        f"page={page} page_size={page_size}"
    )

    if not company_name:
        logger.warning(f"[ENTERPRISE_INVOICES_ERROR] Missing company_name for user {user_email}")
        raise HTTPException(status_code=403, detail="Corporate user required")

    try:
        # Build query filter
        query_filter = {"company_name": company_name}

        # Add search filter if provided
        if search:
            query_filter["invoice_number"] = {"$regex": search, "$options": "i"}

        # Sort mapping
        sort_field_map = {
            "date": "invoice_date",
            "amount": "total_amount",
            "due_date": "due_date"
        }
        sort_field = sort_field_map.get(sort_by, "invoice_date")
        sort_direction = -1 if sort_order == "desc" else 1

        # Count total invoices
        count_start = time.time()
        total = await database.invoices.count_documents(query_filter)
        count_duration = time.time() - count_start

        logger.debug(f"[ENTERPRISE_INVOICES_COUNT] company={company_name} total={total} duration={count_duration:.3f}s")

        # Calculate skip value for pagination
        skip = (page - 1) * page_size

        # Query invoices with pagination and sorting
        query_start = time.time()
        invoices = await database.invoices.find(query_filter) \
            .sort(sort_field, sort_direction) \
            .skip(skip) \
            .limit(page_size) \
            .to_list(length=page_size)
        query_duration = time.time() - query_start

        logger.debug(f"[ENTERPRISE_INVOICES_QUERY] company={company_name} retrieved={len(invoices)} duration={query_duration:.3f}s")

        # Performance warning for slow queries
        if query_duration > 1.0:
            logger.warning(
                f"[ENTERPRISE_INVOICES_SLOW_QUERY] company={company_name} duration={query_duration:.3f}s "
                f"search={search} sort_by={sort_by} page={page} page_size={page_size}"
            )

        # Serialize invoices
        serialize_start = time.time()
        serialized_invoices = [serialize_for_json(invoice) for invoice in invoices]
        serialize_duration = time.time() - serialize_start

        total_duration = time.time() - start_time

        logger.info(
            f"[ENTERPRISE_INVOICES_SUCCESS] company={company_name} user={user_email} "
            f"returned={len(serialized_invoices)} total={total} "
            f"query_time={query_duration:.3f}s total_time={total_duration:.3f}s"
        )

        return {
            "success": True,
            "data": {
                "invoices": serialized_invoices,
                "total": total,
                "page": page,
                "page_size": page_size
            }
        }
    except Exception as e:
        error_duration = time.time() - start_time
        logger.error(
            f"[ENTERPRISE_INVOICES_ERROR] company={company_name} user={user_email} "
            f"error={str(e)} error_type={type(e).__name__} duration={error_duration:.3f}s",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve invoices: {str(e)}"
        )


@router.get("/invoice/unpaid")
async def get_unpaid_invoice(
    admin_user: Dict[str, Any] = Depends(get_admin_user)
):
    """
    Get the latest unpaid invoice for the admin's company.

    Admin only endpoint - returns 403 if user is not admin.
    """
    start_time = time.time()
    company_name = admin_user.get("company_name")
    admin_email = admin_user.get("email", "unknown")

    # Log request start
    logger.info(
        f"[ENTERPRISE_INVOICE_REQUEST] admin={admin_email} company={company_name}"
    )

    if not company_name:
        logger.warning(f"[ENTERPRISE_INVOICE_ERROR] Missing company_name for admin {admin_email}")
        raise HTTPException(status_code=403, detail="Admin user required")

    try:
        # Query for unpaid invoice with timing
        query_start = time.time()
        invoice = await database.invoices.find_one(
            {
                "company_name": company_name,
                "status": {"$in": ["sent", "overdue", "pending"]}
            },
            sort=[("due_date", 1)]  # Earliest first
        )
        query_duration = time.time() - query_start

        logger.debug(
            f"[ENTERPRISE_INVOICE_QUERY] company={company_name} "
            f"found={'yes' if invoice else 'no'} duration={query_duration:.3f}s"
        )

        # Serialize if found
        serialize_start = time.time()
        serialized = serialize_for_json(invoice) if invoice else None
        serialize_duration = time.time() - serialize_start

        total_duration = time.time() - start_time

        logger.info(
            f"[ENTERPRISE_INVOICE_SUCCESS] company={company_name} admin={admin_email} "
            f"invoice_found={'yes' if invoice else 'no'} "
            f"query_time={query_duration:.3f}s total_time={total_duration:.3f}s"
        )

        return {
            "success": True,
            "data": {
                "invoice": serialized
            }
        }
    except Exception as e:
        error_duration = time.time() - start_time
        logger.error(
            f"[ENTERPRISE_INVOICE_ERROR] company={company_name} admin={admin_email} "
            f"error={str(e)} error_type={type(e).__name__} duration={error_duration:.3f}s",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve invoice: {str(e)}"
        )
