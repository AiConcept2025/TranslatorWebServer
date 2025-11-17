"""
Dashboard API endpoints for admin metrics and statistics.
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status

from app.database import database

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"]
)


@router.get("/metrics")
async def get_dashboard_metrics() -> Dict[str, Any]:
    """
    Get overview metrics for admin dashboard.

    Returns dashboard statistics including:
    - total_revenue: Sum of all COMPLETED payments (in dollars)
    - active_subscriptions: Count of subscriptions with status="active"
    - total_transactions: Count of all translation_transactions + user_transactions
    - active_companies: Count of distinct companies with active subscriptions

    Returns:
        dict: Dashboard metrics

    Example response:
        {
            "success": true,
            "data": {
                "total_revenue": 24567.00,
                "active_subscriptions": 142,
                "total_transactions": 1248,
                "active_companies": 38
            }
        }
    """
    try:
        logger.info("Fetching dashboard metrics...")

        # 1. Total Revenue - sum all COMPLETED payments
        revenue_pipeline = [
            {"$match": {"payment_status": "COMPLETED"}},
            {"$group": {
                "_id": None,
                "total": {"$sum": "$amount"}
            }}
        ]

        revenue_result = await database.payments.aggregate(revenue_pipeline).to_list(length=1)
        total_revenue_cents = revenue_result[0]["total"] if revenue_result else 0
        total_revenue_dollars = total_revenue_cents / 100.0

        logger.info(f"Total revenue: ${total_revenue_dollars:.2f} (from {total_revenue_cents} cents)")

        # 2. Active Subscriptions - count active subscriptions
        active_subscriptions = await database.subscriptions.count_documents({"status": "active"})
        logger.info(f"Active subscriptions: {active_subscriptions}")

        # 3. Total Transactions - count all translation_transactions + user_transactions
        translation_txn_count = await database.translation_transactions.count_documents({})
        user_txn_count = await database.user_transactions.count_documents({})
        total_transactions = translation_txn_count + user_txn_count
        logger.info(f"Total transactions: {total_transactions} (translation: {translation_txn_count}, user: {user_txn_count})")

        # 4. Active Companies - count distinct companies with active subscriptions
        active_companies_pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {"_id": "$company_name"}},
            {"$count": "total"}
        ]

        active_companies_result = await database.subscriptions.aggregate(active_companies_pipeline).to_list(length=1)
        active_companies = active_companies_result[0]["total"] if active_companies_result else 0
        logger.info(f"Active companies: {active_companies}")

        # Prepare response
        metrics = {
            "total_revenue": round(total_revenue_dollars, 2),
            "active_subscriptions": active_subscriptions,
            "total_transactions": total_transactions,
            "active_companies": active_companies
        }

        logger.info(f"Dashboard metrics successfully fetched: {metrics}")

        return {
            "success": True,
            "data": metrics
        }

    except Exception as e:
        logger.error(f"Error fetching dashboard metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch dashboard metrics: {str(e)}"
        )
