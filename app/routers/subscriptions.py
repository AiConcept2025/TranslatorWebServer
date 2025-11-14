"""
Subscription management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging
from datetime import datetime, timezone

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
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] POST /api/subscriptions - START")
    logger.info(f"📥 Request Data: company_name={subscription_data.company_name}, "
                f"subscription_unit={subscription_data.subscription_unit}, "
                f"units={subscription_data.units_per_subscription}, "
                f"price={subscription_data.subscription_price}")
    logger.info(f"👤 Admin User: {admin.get('email', 'unknown')}")

    try:
        subscription = await subscription_service.create_subscription(subscription_data)
        logger.info(f"✅ Subscription created: id={subscription['_id']}, "
                   f"company={subscription['company_name']}, status={subscription['status']}")

        response_data = {
            "success": True,
            "message": "Subscription created successfully",
            "data": {
                "subscription_id": str(subscription["_id"]),
                "company_name": subscription["company_name"],
                "subscription_unit": subscription["subscription_unit"],
                "units_per_subscription": subscription["units_per_subscription"],
                "status": subscription["status"]
            }
        }
        logger.info(f"📤 Response: {response_data}")

        return JSONResponse(content=response_data, status_code=201)

    except SubscriptionError as e:
        logger.error(f"❌ Subscription creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.get("/{subscription_id}")
async def get_subscription(
    subscription_id: str
):
    """
    Get subscription details by ID.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] GET /api/subscriptions/{subscription_id} - START")
    logger.info(f"📥 Request Param: subscription_id={subscription_id}")

    subscription = await subscription_service.get_subscription(subscription_id)
    logger.info(f"🔎 Database Query Result: found={subscription is not None}")

    if not subscription:
        logger.warning(f"❌ Subscription not found: id={subscription_id}")
        raise HTTPException(status_code=404, detail="Subscription not found")

    logger.info(f"✅ Subscription found: company={subscription.get('company_name')}, "
               f"status={subscription.get('status')}, "
               f"usage_periods={len(subscription.get('usage_periods', []))}")

    # Helper function to serialize usage periods
    def serialize_usage_period(period):
        """Convert datetime objects in usage period to ISO format and calculate derived fields."""
        subscription_units = period.get("subscription_units", 0)
        used_units = period.get("used_units", 0)
        promotional_units = period.get("promotional_units", 0)

        # Calculate total allocated units (subscription + promotional)
        units_allocated = subscription_units + promotional_units

        # Calculate remaining units
        units_remaining = units_allocated - used_units

        return {
            # Backend fields
            "subscription_units": subscription_units,
            "used_units": used_units,
            "promotional_units": promotional_units,
            "price_per_unit": period.get("price_per_unit", 0.0),
            "period_start": period["period_start"].isoformat() if period.get("period_start") else None,
            "period_end": period["period_end"].isoformat() if period.get("period_end") else None,
            # Frontend compatibility fields
            "units_allocated": units_allocated,
            "units_used": used_units,
            "units_remaining": units_remaining,
            "last_updated": period.get("updated_at", period.get("period_end")).isoformat() if period.get("updated_at") or period.get("period_end") else None
        }

    response_data = {
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
            "usage_periods": [serialize_usage_period(period) for period in subscription.get("usage_periods", [])],
            "created_at": subscription["created_at"].isoformat(),
            "updated_at": subscription["updated_at"].isoformat()
        }
    }
    logger.info(f"📤 Response: success=True, data keys={list(response_data['data'].keys())}")
    return JSONResponse(content=response_data)


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
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] GET /api/subscriptions/company/{company_name} - START")
    logger.info(f"📥 Request Params: company_name={company_name}, status={status}, active_only={active_only}")
    logger.info(f"🔎 Query Filters: company_name={company_name}, status_filter={status}, active_only={active_only}")

    subscriptions = await subscription_service.get_company_subscriptions(
        company_name, status=status, active_only=active_only
    )
    logger.info(f"🔎 Database Query Result: count={len(subscriptions)}")
    if subscriptions:
        sample_sub = subscriptions[0]
        logger.info(f"📊 Sample Subscription: id={sample_sub.get('_id')}, "
                   f"company={sample_sub.get('company_name')}, status={sample_sub.get('status')}")

    # Helper function to serialize usage periods
    def serialize_usage_period(period):
        """Convert datetime objects in usage period to ISO format and calculate derived fields."""
        subscription_units = period.get("subscription_units", 0)
        used_units = period.get("used_units", 0)
        promotional_units = period.get("promotional_units", 0)

        # Calculate total allocated units (subscription + promotional)
        units_allocated = subscription_units + promotional_units

        # Calculate remaining units
        units_remaining = units_allocated - used_units

        return {
            # Backend fields
            "subscription_units": subscription_units,
            "used_units": used_units,
            "promotional_units": promotional_units,
            "price_per_unit": period.get("price_per_unit", 0.0),
            "period_start": period["period_start"].isoformat() if period.get("period_start") else None,
            "period_end": period["period_end"].isoformat() if period.get("period_end") else None,
            # Frontend compatibility fields
            "units_allocated": units_allocated,
            "units_used": used_units,
            "units_remaining": units_remaining,
            "last_updated": period.get("updated_at", period.get("period_end")).isoformat() if period.get("updated_at") or period.get("period_end") else None
        }

    response_data = {
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
                    "usage_periods": [serialize_usage_period(period) for period in sub.get("usage_periods", [])],
                    "created_at": sub["created_at"].isoformat(),
                    "updated_at": sub["updated_at"].isoformat()
                }
                for sub in subscriptions
            ]
        }
    }
    logger.info(f"📤 Response: success=True, count={len(subscriptions)}, "
               f"company_name={company_name}")
    return JSONResponse(content=response_data)


@router.options("/{subscription_id}")
async def options_subscription(subscription_id: str):
    """
    Handle CORS preflight requests for subscription updates.

    This endpoint doesn't require authentication because it's just a CORS preflight check.
    The actual PATCH request will require authentication.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] OPTIONS /api/subscriptions/{subscription_id} - CORS Preflight")
    return JSONResponse(
        content={"success": True},
        status_code=200,
        headers={
            "Access-Control-Allow-Methods": "GET, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
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
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] PATCH /api/subscriptions/{subscription_id} - START")
    logger.info(f"📥 Request Parameters:")
    logger.info(f"   - subscription_id: {subscription_id}")
    logger.info(f"   - Admin User: {admin.get('email', 'unknown')}")
    logger.info(f"📦 Request Body (update_data):")

    # Log full request body with all fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        logger.info(f"   - {key}: {value}")

    logger.info(f"📋 Full Update Payload: {update_dict}")

    try:
        logger.info(f"🔄 Calling subscription_service.update_subscription()...")
        subscription = await subscription_service.update_subscription(subscription_id, update_data)
        logger.info(f"🔎 Database Update Result: found={subscription is not None}")

        if not subscription:
            logger.warning(f"❌ Subscription not found for update: id={subscription_id}")
            raise HTTPException(status_code=404, detail="Subscription not found")

        logger.info(f"✅ Subscription updated successfully:")
        logger.info(f"   - _id: {subscription['_id']}")
        logger.info(f"   - company_name: {subscription.get('company_name')}")
        logger.info(f"   - status: {subscription['status']}")
        logger.info(f"   - updated_at: {subscription['updated_at']}")

        response_data = {
            "success": True,
            "message": "Subscription updated successfully",
            "data": {
                "subscription_id": str(subscription["_id"]),
                "status": subscription["status"],
                "updated_at": subscription["updated_at"].isoformat()
            }
        }
        logger.info(f"📤 Response Data: {response_data}")
        return JSONResponse(content=response_data)

    except SubscriptionError as e:
        logger.error(f"❌ SubscriptionError during update:", exc_info=True)
        logger.error(f"   - Error message: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error during subscription update:", exc_info=True)
        logger.error(f"   - Error message: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Subscription ID: {subscription_id}")
        logger.error(f"   - Update data: {update_dict}")
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
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] POST /api/subscriptions/{subscription_id}/usage-periods - START")
    logger.info(f"📥 Request Data: subscription_id={subscription_id}, "
               f"period_start={period_data.period_start}, period_end={period_data.period_end}, "
               f"units_allocated={period_data.units_allocated}")
    logger.info(f"👤 Admin User: {admin.get('email', 'unknown')}")

    try:
        subscription = await subscription_service.add_usage_period(subscription_id, period_data)
        logger.info(f"🔎 Database Update Result: found={subscription is not None}")

        if not subscription:
            logger.warning(f"❌ Subscription not found: id={subscription_id}")
            raise HTTPException(status_code=404, detail="Subscription not found")

        logger.info(f"✅ Usage period added: subscription_id={subscription['_id']}, "
                   f"periods_count={len(subscription.get('usage_periods', []))}")

        response_data = {
            "success": True,
            "message": "Usage period added successfully",
            "data": {
                "subscription_id": str(subscription["_id"]),
                "usage_periods_count": len(subscription.get("usage_periods", []))
            }
        }
        logger.info(f"📤 Response: {response_data}")
        return JSONResponse(content=response_data, status_code=201)

    except SubscriptionError as e:
        logger.error(f"❌ Add usage period failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
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
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] POST /api/subscriptions/{subscription_id}/record-usage - START")
    logger.info(f"📥 Request Data: subscription_id={subscription_id}, "
               f"units_to_add={usage_data.units_to_add}, "
               f"use_promotional={usage_data.use_promotional_units}")
    logger.info(f"👤 User: {current_user.get('email', 'unknown')}, "
               f"company={current_user.get('company_name') or current_user.get('company')}")

    # Verify subscription belongs to user's company
    subscription = await subscription_service.get_subscription(subscription_id)
    logger.info(f"🔎 Subscription Lookup: found={subscription is not None}")

    if not subscription:
        logger.warning(f"❌ Subscription not found: id={subscription_id}")
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Check company name
    user_company_name = current_user.get("company_name") or current_user.get("company")
    subscription_company = subscription.get("company_name")
    logger.info(f"🔐 Access Check: user_company={user_company_name}, "
               f"subscription_company={subscription_company}, "
               f"user_permission={current_user.get('permission_level')}")

    if user_company_name and subscription_company != user_company_name:
        if current_user.get("permission_level") != "admin":
            logger.warning(f"❌ Access denied: user company mismatch")
            raise HTTPException(status_code=403, detail="Access denied")

    try:
        updated_subscription = await subscription_service.record_usage(subscription_id, usage_data)
        logger.info(f"✅ Usage recorded: subscription_id={updated_subscription['_id']}, "
                   f"units_added={usage_data.units_to_add}")

        response_data = {
            "success": True,
            "message": "Usage recorded successfully",
            "data": {
                "subscription_id": str(updated_subscription["_id"]),
                "units_recorded": usage_data.units_to_add,
                "updated_at": updated_subscription["updated_at"].isoformat()
            }
        }
        logger.info(f"📤 Response: {response_data}")
        return JSONResponse(content=response_data)

    except SubscriptionError as e:
        logger.error(f"❌ Record usage failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to record usage")


@router.get("/{subscription_id}/summary")
async def get_subscription_summary(
    subscription_id: str
):
    """
    Get subscription usage summary.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] GET /api/subscriptions/{subscription_id}/summary - START")
    logger.info(f"📥 Request Param: subscription_id={subscription_id}")

    # Verify subscription exists
    subscription = await subscription_service.get_subscription(subscription_id)
    logger.info(f"🔎 Subscription Lookup: found={subscription is not None}")

    if not subscription:
        logger.warning(f"❌ Subscription not found: id={subscription_id}")
        raise HTTPException(status_code=404, detail="Subscription not found")

    summary = await subscription_service.get_subscription_summary(subscription_id)
    logger.info(f"🔎 Summary Generation: success={summary is not None}")

    if not summary:
        logger.warning(f"❌ Failed to generate summary for subscription: id={subscription_id}")
        raise HTTPException(status_code=404, detail="Subscription not found")

    logger.info(f"✅ Summary generated: subscription_id={subscription_id}, "
               f"status={summary.status}, units_remaining={summary.units_remaining}")

    response_data = {
        "success": True,
        "data": summary.model_dump(mode='json')
    }
    logger.info(f"📤 Response: success=True, data keys={list(response_data['data'].keys())}")
    return JSONResponse(content=response_data)


@router.post("/expire-subscriptions")
async def expire_subscriptions(admin: dict = Depends(get_admin_user)):
    """
    Manually trigger expiration of subscriptions (Admin only).
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] POST /api/subscriptions/expire-subscriptions - START")
    logger.info(f"👤 Admin User: {admin.get('email', 'unknown')}")

    count = await subscription_service.expire_subscriptions()
    logger.info(f"🔎 Expiration Process: expired_count={count}")

    logger.info(f"✅ Subscriptions expired: count={count}")

    response_data = {
        "success": True,
        "message": f"Expired {count} subscriptions",
        "data": {
            "expired_count": count
        }
    }
    logger.info(f"📤 Response: {response_data}")
    return JSONResponse(content=response_data)
