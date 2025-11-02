"""
Orders management router for retrieving corporate order history.

This router provides endpoints for corporate users to view and filter
their translation order history organized by time periods.
"""

from fastapi import APIRouter, Query, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from typing import Literal, Optional
import logging
from datetime import datetime, timezone, timedelta
from calendar import monthrange

from app.database.mongodb import database
from app.models.orders import OrdersResponse, OrderItem, OrderPeriod, OrdersData
from app.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"]
)


# ============================================================================
# Status Mapping
# ============================================================================

# Map backend status values to frontend status values
STATUS_MAP = {
    "started": "processing",
    "confirmed": "delivered",
    "pending": "pending",
    "failed": "failed",
    "cancelled": "cancelled",
    # Direct mappings for already-converted values
    "processing": "processing",
    "delivered": "delivered"
}


# ============================================================================
# Helper Functions
# ============================================================================

def calculate_date_range(period: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Calculate date range based on period parameter.

    Args:
        period: Period filter ("current", "previous", "last-3-months", "last-6-months", "all")

    Returns:
        tuple: (start_date, end_date) or (None, None) for "all"
    """
    now = datetime.now(timezone.utc)

    if period == "all":
        return None, None

    elif period == "current":
        # Current month: from 1st to end of month
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = monthrange(now.year, now.month)[1]
        end_date = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
        return start_date, end_date

    elif period == "previous":
        # Previous month: from 1st to last day of previous month
        if now.month == 1:
            prev_year = now.year - 1
            prev_month = 12
        else:
            prev_year = now.year
            prev_month = now.month - 1

        start_date = datetime(prev_year, prev_month, 1, 0, 0, 0, 0, timezone.utc)
        last_day = monthrange(prev_year, prev_month)[1]
        end_date = datetime(prev_year, prev_month, last_day, 23, 59, 59, 999999, timezone.utc)
        return start_date, end_date

    elif period == "last-3-months":
        # Last 3 months from today
        start_date = now - timedelta(days=90)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_date, end_date

    elif period == "last-6-months":
        # Last 6 months from today
        start_date = now - timedelta(days=180)
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start_date, end_date

    else:
        # Default to current month
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = monthrange(now.year, now.month)[1]
        end_date = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
        return start_date, end_date


def format_language_pair(source_lang: str, target_lang: str) -> str:
    """
    Format language pair for display.

    Args:
        source_lang: Source language code (e.g., "en")
        target_lang: Target language code (e.g., "zh")

    Returns:
        str: Formatted language pair (e.g., "EN → ZH")
    """
    return f"{source_lang.upper()} → {target_lang.upper()}"


def parse_language_filter(language: str) -> Optional[tuple[str, str]]:
    """
    Parse language filter parameter.

    Args:
        language: Language filter (e.g., "en-zh", "any")

    Returns:
        tuple: (source_lang, target_lang) or None for "any"
    """
    if language == "any" or not language:
        return None

    # Parse format like "en-zh"
    parts = language.lower().split("-")
    if len(parts) == 2:
        return parts[0], parts[1]

    return None


def get_period_label(date: datetime, is_current: bool) -> str:
    """
    Generate period label for a date.

    Args:
        date: Date in the period
        is_current: Whether this is the current period

    Returns:
        str: Period label (e.g., "Current Period", "October 2025")
    """
    if is_current:
        return "Current Period"
    return date.strftime("%B %Y")


def get_date_range_string(start_date: datetime, end_date: datetime) -> str:
    """
    Generate human-readable date range string.

    Args:
        start_date: Period start date
        end_date: Period end date

    Returns:
        str: Date range string (e.g., "Oct 1-31, 2025")
    """
    if start_date.year == end_date.year and start_date.month == end_date.month:
        # Same month
        return f"{start_date.strftime('%b %d')}-{end_date.strftime('%d, %Y')}"
    else:
        # Different months
        return f"{start_date.strftime('%b %d, %Y')} - {end_date.strftime('%b %d, %Y')}"


def map_status(backend_status: str) -> str:
    """
    Map backend status to frontend status.

    Args:
        backend_status: Status from database

    Returns:
        str: Mapped status for frontend
    """
    return STATUS_MAP.get(backend_status.lower(), backend_status)


def generate_translated_filename(original_file: str, target_language: str) -> str:
    """
    Generate translated filename if not present.

    Args:
        original_file: Original filename
        target_language: Target language code

    Returns:
        str: Generated translated filename
    """
    # Split filename and extension
    parts = original_file.rsplit(".", 1)
    if len(parts) == 2:
        name, ext = parts
        return f"{name}_{target_language}.{ext}"
    else:
        return f"{original_file}_{target_language}"


# ============================================================================
# Main Endpoint
# ============================================================================

@router.get(
    "",
    response_model=OrdersResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Successfully retrieved orders",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "periods": [
                                {
                                    "id": "period-1",
                                    "date_range": "Oct 1-31, 2025",
                                    "period_label": "Current Period",
                                    "is_current": True,
                                    "orders_count": 128,
                                    "pages_count": 1947,
                                    "orders": [
                                        {
                                            "id": "68fe1edeac2359ccbc6b05b2",
                                            "order_number": "#A10293",
                                            "user": "user@company.com",
                                            "date": "2025-10-28",
                                            "language_pair": "EN → ZH",
                                            "original_file": "contract_v3.pdf",
                                            "translated_file": "contract_v3_zh.pdf",
                                            "translated_file_name": "",
                                            "pages": 12,
                                            "status": "delivered"
                                        }
                                    ]
                                }
                            ],
                            "totalOrders": 128,
                            "totalPages": 1947
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Authorization header missing"
                    }
                }
            }
        },
        404: {
            "description": "Company not found",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Company not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed to retrieve orders"
                    }
                }
            }
        }
    }
)
async def get_orders(
    date_period: Literal["current", "previous", "last-3-months", "last-6-months", "all"] = Query(
        default="current",
        description="Time period filter for orders"
    ),
    language: str = Query(
        default="any",
        description="Language pair filter (e.g., 'en-zh') or 'any' for all languages"
    ),
    status_filter: Literal["delivered", "processing", "pending", "failed", "cancelled", "any"] = Query(
        default="any",
        description="Order status filter",
        alias="status"
    ),
    search: str = Query(
        default="",
        description="Search term for order number, user name, or filenames"
    ),
    current_user: dict = Depends(get_current_user)
):
    """
    Get orders for the authenticated corporate user's company.

    Retrieves translation orders organized by time periods with filtering
    capabilities for date range, language pair, status, and search.

    ## Authentication
    Requires valid corporate authentication token in Authorization header.

    ## Query Parameters
    - **date_period**: Time period filter
        - `current`: Current month (default)
        - `previous`: Previous month
        - `last-3-months`: Last 90 days
        - `last-6-months`: Last 180 days
        - `all`: All time
    - **language**: Language pair filter (e.g., "en-zh") or "any" (default)
    - **status**: Order status filter
        - `delivered`: Completed orders
        - `processing`: Orders in progress
        - `pending`: Orders waiting to start
        - `failed`: Failed orders
        - `cancelled`: Cancelled orders
        - `any`: All statuses (default)
    - **search**: Search term (searches order number, user email, filenames)

    ## Response Structure
    Returns orders grouped by month with period statistics:
    - **periods**: Array of monthly periods, each containing:
        - **id**: Period identifier
        - **date_range**: Human-readable date range
        - **period_label**: Period label (e.g., "Current Period")
        - **is_current**: Whether this is the current month
        - **orders_count**: Number of orders in period
        - **pages_count**: Total pages in period
        - **orders**: Array of order items
    - **totalOrders**: Total orders across all periods
    - **totalPages**: Total pages across all periods

    ## Order Fields
    Each order contains:
    - **id**: MongoDB ObjectId
    - **order_number**: Order number with # prefix
    - **user**: User email address
    - **date**: Order date (YYYY-MM-DD)
    - **language_pair**: Language pair (e.g., "EN → ZH")
    - **original_file**: Original filename
    - **translated_file**: Translated filename
    - **pages**: Number of pages/units
    - **status**: Order status

    ## Usage Examples

    ### Get current month orders
    ```bash
    curl -X GET "http://localhost:8000/api/orders" \\
      -H "Authorization: Bearer {token}"
    ```

    ### Filter by language and status
    ```bash
    curl -X GET "http://localhost:8000/api/orders?language=en-zh&status=delivered" \\
      -H "Authorization: Bearer {token}"
    ```

    ### Search orders
    ```bash
    curl -X GET "http://localhost:8000/api/orders?search=contract" \\
      -H "Authorization: Bearer {token}"
    ```

    ### Get last 6 months
    ```bash
    curl -X GET "http://localhost:8000/api/orders?date_period=last-6-months" \\
      -H "Authorization: Bearer {token}"
    ```
    """
    try:
        # Extract company_name from authenticated user
        company_name = current_user.get("company_name") or current_user.get("company")

        if not company_name:
            logger.error(f"[ORDERS] No company_name found for user: {current_user.get('email')}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is not associated with a company"
            )

        logger.info(
            f"[ORDERS] Fetching orders for company: {company_name}, "
            f"period={date_period}, language={language}, status={status_filter}, search='{search}'"
        )
        print(f"[ORDERS] 🔍 USER INFO: {current_user}")
        print(f"[ORDERS] 🏢 COMPANY: {company_name}")

        # Build MongoDB query filter
        match_stage = {"company_name": company_name}

        # Apply date range filter
        start_date, end_date = calculate_date_range(date_period)
        if start_date and end_date:
            match_stage["created_at"] = {
                "$gte": start_date,
                "$lte": end_date
            }

        # Apply language pair filter
        lang_filter = parse_language_filter(language)
        if lang_filter:
            source_lang, target_lang = lang_filter
            match_stage["source_language"] = source_lang
            match_stage["target_language"] = target_lang

        # Apply status filter
        if status_filter != "any":
            # Map frontend status to backend status values
            backend_statuses = [k for k, v in STATUS_MAP.items() if v == status_filter]
            if backend_statuses:
                if len(backend_statuses) == 1:
                    match_stage["status"] = backend_statuses[0]
                else:
                    match_stage["status"] = {"$in": backend_statuses}

        # Apply search filter (case-insensitive)
        if search:
            # Strip leading # from search query if present (order numbers displayed with # prefix)
            search_term = search.lstrip("#")
            match_stage["$or"] = [
                {"transaction_id": {"$regex": search_term, "$options": "i"}},
                {"user_id": {"$regex": search_term, "$options": "i"}},
                {"file_name": {"$regex": search_term, "$options": "i"}},
                {"translated_file_name": {"$regex": search_term, "$options": "i"}}
            ]

        # Execute query with sorting by created_at descending
        logger.info(f"[ORDERS] Query filter: {match_stage}")
        print(f"[ORDERS] 📊 QUERY FILTER: {match_stage}")
        print(f"[ORDERS] 📅 DATE RANGE: {start_date} to {end_date}")

        transactions = await database.translation_transactions.find(match_stage).sort("created_at", -1).to_list(length=None)

        logger.info(f"[ORDERS] Found {len(transactions)} transactions for company {company_name}")
        print(f"[ORDERS] 📦 FOUND {len(transactions)} transactions")

        # Log first transaction if exists
        if transactions:
            print(f"[ORDERS] 📄 FIRST TRANSACTION: {transactions[0]}")

        # Group transactions by month
        periods_map = {}
        current_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        for transaction in transactions:
            created_at = transaction.get("created_at")
            if not created_at:
                logger.warning(f"[ORDERS] Transaction missing created_at: {transaction.get('_id')}")
                continue

            # Ensure created_at is timezone-aware
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            # Get period key (year-month)
            period_key = created_at.strftime("%Y-%m")

            # Initialize period if not exists
            if period_key not in periods_map:
                # Calculate period start and end
                period_start = created_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                last_day = monthrange(created_at.year, created_at.month)[1]
                period_end = created_at.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)

                # Check if this is the current period
                is_current = period_start.year == current_month.year and period_start.month == current_month.month

                periods_map[period_key] = {
                    "period_start": period_start,
                    "period_end": period_end,
                    "is_current": is_current,
                    "orders": [],
                    "total_pages": 0
                }

            # Map transaction to OrderItem format
            transaction_id = transaction.get("transaction_id", "")
            order_number = transaction_id if transaction_id.startswith("#") else f"#{transaction_id}"

            translated_file = transaction.get("translated_file_name") or transaction.get("translated_file_url")
            if not translated_file:
                # Generate translated filename
                translated_file = generate_translated_filename(
                    transaction.get("file_name", ""),
                    transaction.get("target_language", "")
                )

            order_item = {
                "id": str(transaction.get("_id")),
                "order_number": order_number,
                "user": transaction.get("user_id", ""),
                "date": created_at.strftime("%Y-%m-%d"),
                "language_pair": format_language_pair(
                    transaction.get("source_language", ""),
                    transaction.get("target_language", "")
                ),
                "original_file": transaction.get("file_name", ""),
                "translated_file": translated_file,
                "translated_file_name": transaction.get("translated_file_name", ""),
                "pages": transaction.get("units_count", 0),
                "status": map_status(transaction.get("status", "pending"))
            }

            # Add to period
            periods_map[period_key]["orders"].append(order_item)
            periods_map[period_key]["total_pages"] += order_item["pages"]

        # Convert periods_map to list and sort by date (newest first)
        periods_list = []
        for idx, (period_key, period_data) in enumerate(sorted(periods_map.items(), reverse=True), start=1):
            period = {
                "id": f"period-{idx}",
                "date_range": get_date_range_string(period_data["period_start"], period_data["period_end"]),
                "period_label": get_period_label(period_data["period_start"], period_data["is_current"]),
                "is_current": period_data["is_current"],
                "orders_count": len(period_data["orders"]),
                "pages_count": period_data["total_pages"],
                "orders": period_data["orders"]
            }
            periods_list.append(period)

        # Calculate totals
        total_orders = sum(p["orders_count"] for p in periods_list)
        total_pages = sum(p["pages_count"] for p in periods_list)

        logger.info(
            f"[ORDERS] Returning {len(periods_list)} periods, "
            f"{total_orders} orders, {total_pages} pages for company {company_name}"
        )
        print(f"[ORDERS] 📊 FINAL RESPONSE:")
        print(f"[ORDERS]   - Periods: {len(periods_list)}")
        print(f"[ORDERS]   - Total Orders: {total_orders}")
        print(f"[ORDERS]   - Total Pages: {total_pages}")
        if periods_list:
            print(f"[ORDERS]   - First Period: {periods_list[0]['period_label']} ({periods_list[0]['orders_count']} orders)")

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "periods": periods_list,
                    "totalOrders": total_orders,
                    "totalPages": total_pages
                }
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ORDERS] Failed to retrieve orders: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve orders: {str(e)}"
        )
