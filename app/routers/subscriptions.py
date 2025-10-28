"""
Subscription management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging

from app.services.subscription_service import subscription_service, SubscriptionError
from app.models.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    UsagePeriodCreate,
    UsageUpdate,
    SubscriptionResponse,
    SubscriptionSummary
)
from app.middleware.auth_middleware import get_current_user, get_admin_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


@router.post("/", response_model=dict)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    admin: dict = Depends(get_admin_user)
):
    """
    Create a new subscription (Admin only).

    Request:
    ```json
    {
        "company_name": "Acme Translation Corp",
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        "price_per_unit": 0.10,
        "promotional_units": 100,
        "discount": 0.9,
        "subscription_price": 90.00,
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-12-31T23:59:59Z",
        "status": "active"
    }
    ```
    """
    logger.info(f"[API] Creating subscription for company: {subscription_data.company_name}")

    try:
        subscription = await subscription_service.create_subscription(subscription_data)

        return JSONResponse(
            content={
                "success": True,
                "message": "Subscription created successfully",
                "data": {
                    "subscription_id": str(subscription["_id"]),
                    "company_name": subscription["company_name"],
                    "subscription_unit": subscription["subscription_unit"],
                    "units_per_subscription": subscription["units_per_subscription"],
                    "status": subscription["status"]
                }
            },
            status_code=201
        )

    except SubscriptionError as e:
        logger.error(f"[API] Subscription creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[API] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.get("/{subscription_id}")
async def get_subscription(
    subscription_id: str
):
    """
    Get subscription details by ID.
    """
    logger.info(f"[API] Fetching subscription: {subscription_id}")

    subscription = await subscription_service.get_subscription(subscription_id)

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "subscription_id": str(subscription["_id"]),
                "company_name": subscription["company_name"],
                "subscription_unit": subscription["subscription_unit"],
                "units_per_subscription": subscription["units_per_subscription"],
                "price_per_unit": subscription["price_per_unit"],
                "promotional_units": subscription["promotional_units"],
                "discount": subscription["discount"],
                "subscription_price": subscription["subscription_price"],
                "start_date": subscription["start_date"].isoformat(),
                "end_date": subscription["end_date"].isoformat() if subscription.get("end_date") else None,
                "status": subscription["status"],
                "usage_periods": subscription.get("usage_periods", []),
                "created_at": subscription["created_at"].isoformat(),
                "updated_at": subscription["updated_at"].isoformat()
            }
        }
    )


@router.get("/company/{company_name}")
async def get_company_subscriptions(
    company_name: str,
    status: Optional[str] = None,
    active_only: bool = False
):
    """
    Get all subscriptions for a company.

    Query parameters:
    - status: Filter by status (active, inactive, expired)
    - active_only: Only return active subscriptions (true/false)
    """
    logger.info(f"[API] Fetching subscriptions for company: {company_name}")

    subscriptions = await subscription_service.get_company_subscriptions(
        company_name, status=status, active_only=active_only
    )

    return JSONResponse(
        content={
            "success": True,
            "data": {
                "company_name": company_name,
                "count": len(subscriptions),
                "subscriptions": [
                    {
                        "_id": str(sub["_id"]),
                        "company_name": sub.get("company_name", company_name),
                        "subscription_unit": sub["subscription_unit"],
                        "units_per_subscription": sub["units_per_subscription"],
                        "price_per_unit": sub["price_per_unit"],
                        "promotional_units": sub.get("promotional_units", 0),
                        "discount": sub.get("discount", 1.0),
                        "subscription_price": sub["subscription_price"],
                        "status": sub["status"],
                        "start_date": sub["start_date"].isoformat(),
                        "end_date": sub["end_date"].isoformat() if sub.get("end_date") else None,
                        "usage_periods": sub.get("usage_periods", []),
                        "created_at": sub["created_at"].isoformat(),
                        "updated_at": sub["updated_at"].isoformat()
                    }
                    for sub in subscriptions
                ]
            }
        }
    )


@router.patch("/{subscription_id}")
async def update_subscription(
    subscription_id: str,
    update_data: SubscriptionUpdate,
    admin: dict = Depends(get_admin_user)
):
    """
    Update subscription details (Admin only).
    """
    logger.info(f"[API] Updating subscription: {subscription_id}")

    try:
        subscription = await subscription_service.update_subscription(subscription_id, update_data)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return JSONResponse(
            content={
                "success": True,
                "message": "Subscription updated successfully",
                "data": {
                    "subscription_id": str(subscription["_id"]),
                    "status": subscription["status"],
                    "updated_at": subscription["updated_at"].isoformat()
                }
            }
        )

    except SubscriptionError as e:
        logger.error(f"[API] Update failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[API] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update subscription")


@router.post("/{subscription_id}/usage-periods")
async def add_usage_period(
    subscription_id: str,
    period_data: UsagePeriodCreate,
    admin: dict = Depends(get_admin_user)
):
    """
    Add a new usage period to a subscription (Admin only).

    Request:
    ```json
    {
        "period_start": "2025-01-01T00:00:00Z",
        "period_end": "2025-01-31T23:59:59Z",
        "units_allocated": 1000
    }
    ```
    """
    logger.info(f"[API] Adding usage period to subscription: {subscription_id}")

    try:
        subscription = await subscription_service.add_usage_period(subscription_id, period_data)

        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        return JSONResponse(
            content={
                "success": True,
                "message": "Usage period added successfully",
                "data": {
                    "subscription_id": str(subscription["_id"]),
                    "usage_periods_count": len(subscription.get("usage_periods", []))
                }
            },
            status_code=201
        )

    except SubscriptionError as e:
        logger.error(f"[API] Add usage period failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[API] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to add usage period")


@router.post("/{subscription_id}/record-usage")
async def record_usage(
    subscription_id: str,
    usage_data: UsageUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Record usage for a subscription.

    Request:
    ```json
    {
        "units_to_add": 50,
        "use_promotional_units": false
    }
    ```
    """
    logger.info(f"[API] Recording usage for subscription: {subscription_id}")

    # Verify subscription belongs to user's company
    subscription = await subscription_service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Check company name (migrated from company_id)
    user_company_name = current_user.get("company_name") or current_user.get("company")
    if user_company_name and subscription.get("company_name") != user_company_name:
        if current_user.get("permission_level") != "admin":
            raise HTTPException(status_code=403, detail="Access denied")

    try:
        updated_subscription = await subscription_service.record_usage(subscription_id, usage_data)

        return JSONResponse(
            content={
                "success": True,
                "message": "Usage recorded successfully",
                "data": {
                    "subscription_id": str(updated_subscription["_id"]),
                    "units_recorded": usage_data.units_to_add,
                    "updated_at": updated_subscription["updated_at"].isoformat()
                }
            }
        )

    except SubscriptionError as e:
        logger.error(f"[API] Record usage failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[API] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record usage")


@router.get("/{subscription_id}/summary")
async def get_subscription_summary(
    subscription_id: str
):
    """
    Get subscription usage summary.
    """
    logger.info(f"[API] Fetching subscription summary: {subscription_id}")

    # Verify subscription exists
    subscription = await subscription_service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    summary = await subscription_service.get_subscription_summary(subscription_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return JSONResponse(
        content={
            "success": True,
            "data": summary.model_dump(mode='json')
        }
    )


@router.post("/expire-subscriptions")
async def expire_subscriptions(admin: dict = Depends(get_admin_user)):
    """
    Manually trigger expiration of subscriptions (Admin only).
    """
    logger.info("[API] Expiring subscriptions")

    count = await subscription_service.expire_subscriptions()

    return JSONResponse(
        content={
            "success": True,
            "message": f"Expired {count} subscriptions",
            "data": {
                "expired_count": count
            }
        }
    )
