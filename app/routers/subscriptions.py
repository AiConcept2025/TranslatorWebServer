"""
Subscription management API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from typing import Optional, List
import logging
from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
from bson.errors import InvalidId
from decimal import Decimal

from app.database.mongodb import database
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


@router.post("", response_model=dict)
async def create_subscription(
    subscription_data: SubscriptionCreate,
    admin: dict = Depends(get_admin_user)
):
    """
    Create a new subscription (Admin only).

    **IMPORTANT:** Company must exist in the database before creating a subscription.
    If the company does not exist, the request will fail with HTTP 400.

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

    Responses:
    - **201 Created**: Subscription created successfully
    - **400 Bad Request**: Company does not exist in database
    - **401 Unauthorized**: Admin authentication required
    - **422 Unprocessable Entity**: Validation error (invalid data)

    Error Example (Company Not Found):
    ```json
    {
        "detail": "Cannot create subscription: Company 'Acme Translation Corp' does not exist in database"
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

        subscription_id = str(subscription["_id"])
        response_data = {
            "success": True,
            "message": "Subscription created successfully",
            "subscription_id": subscription_id,  # Backward compatibility - at root level
            "data": {
                "subscription_id": subscription_id,
                "company_name": subscription["company_name"],
                "subscription_unit": subscription["subscription_unit"],
                "units_per_subscription": subscription["units_per_subscription"],
                "status": subscription["status"],
                "billing_frequency": subscription.get("billing_frequency", "quarterly"),
                "payment_terms_days": subscription.get("payment_terms_days", 30)
            }
        }
        logger.info(f"📤 Response: {response_data}")

        return JSONResponse(content=response_data, status_code=201)

    except SubscriptionError as e:
        logger.error(f"❌ Subscription creation failed: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateKeyError as e:
        logger.warning(f"⚠️ Duplicate subscription attempted for company '{subscription_data.company_name}': {e}")
        raise HTTPException(
            status_code=409,
            detail=f"Subscription already exists for company '{subscription_data.company_name}'. Only one subscription per company is allowed."
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create subscription")


@router.get("/{subscription_id}")
async def get_subscription(
    subscription_id: str
):
    """
    Get subscription details by ID (ObjectId or subscription_id field).
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"🔍 [{timestamp}] GET /api/subscriptions/{subscription_id} - START")
    logger.info(f"📥 Request Param: subscription_id={subscription_id}")

    try:
        subscription = await subscription_service.get_subscription(subscription_id)

        if not subscription:
            logger.warning(f"❌ Subscription not found: id={subscription_id}")
            raise HTTPException(status_code=404, detail="Subscription not found")

    except SubscriptionError as e:
        logger.error(f"❌ Database error: {e}")
        raise HTTPException(status_code=500, detail="Database error")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    logger.info(f"✅ Subscription found: company={subscription.get('company_name')}, "
               f"status={subscription.get('status')}, "
               f"usage_periods={len(subscription.get('usage_periods', []))}")

    # Helper function to serialize usage periods
    def serialize_usage_period(period):
        """Convert datetime objects in usage period to ISO format and calculate derived fields."""
        units_allocated = period.get("units_allocated", 0)
        units_used = period.get("units_used", 0)
        promotional_units = period.get("promotional_units", 0)

        # Calculate total allocated units (base + promotional)
        total_allocated = units_allocated + promotional_units

        # Calculate remaining units
        units_remaining = total_allocated - units_used

        return {
            # Database fields
            "units_allocated": units_allocated,
            "units_used": units_used,
            "promotional_units": promotional_units,
            "price_per_unit": period.get("price_per_unit", 0.0),
            "period_start": period["period_start"].isoformat() if period.get("period_start") else None,
            "period_end": period["period_end"].isoformat() if period.get("period_end") else None,
            # Calculated fields
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
            "promotional_units": subscription.get("promotional_units", 0),
            "discount": subscription.get("discount", 1.0),
            "subscription_price": subscription["subscription_price"],
            "start_date": subscription["start_date"].isoformat(),
            "end_date": subscription["end_date"].isoformat() if subscription.get("end_date") else None,
            "status": subscription["status"],
            "billing_frequency": subscription.get("billing_frequency", "quarterly"),
            "payment_terms_days": subscription.get("payment_terms_days", 30),
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
        units_allocated = period.get("units_allocated", 0)
        units_used = period.get("units_used", 0)
        promotional_units = period.get("promotional_units", 0)

        # Calculate total allocated units (base + promotional)
        total_allocated = units_allocated + promotional_units

        # Calculate remaining units
        units_remaining = total_allocated - units_used

        return {
            # Database fields
            "units_allocated": units_allocated,
            "units_used": units_used,
            "promotional_units": promotional_units,
            "price_per_unit": period.get("price_per_unit", 0.0),
            "period_start": period["period_start"].isoformat() if period.get("period_start") else None,
            "period_end": period["period_end"].isoformat() if period.get("period_end") else None,
            # Calculated fields
            "units_remaining": units_remaining,
            "last_updated": period.get("updated_at", period.get("period_end")).isoformat() if period.get("updated_at") or period.get("period_end") else None
        }

    # Serialize subscriptions list
    subscriptions_list = [
        {
            "_id": str(sub["_id"]),
            "subscription_id": sub.get("subscription_id", str(sub["_id"])),
            "company_name": sub.get("company_name", company_name),
            "subscription_unit": sub["subscription_unit"],
            "units_per_subscription": sub["units_per_subscription"],
            "price_per_unit": sub["price_per_unit"],
            "promotional_units": sub.get("promotional_units", 0),
            "discount": sub.get("discount", 1.0),
            "subscription_price": sub["subscription_price"],
            "status": sub["status"],
            "billing_frequency": sub.get("billing_frequency", "quarterly"),
            "payment_terms_days": sub.get("payment_terms_days", 30),
            "start_date": sub["start_date"].isoformat(),
            "end_date": sub["end_date"].isoformat() if sub.get("end_date") else None,
            "usage_periods": [serialize_usage_period(period) for period in sub.get("usage_periods", [])],
            "created_at": sub["created_at"].isoformat(),
            "updated_at": sub["updated_at"].isoformat()
        }
        for sub in subscriptions
    ]

    # Return nested structure matching frontend expectations:
    # response.data.data gives us {company_name, count, subscriptions: [...]}
    response_data = {
        "company_name": company_name,
        "count": len(subscriptions_list),
        "subscriptions": subscriptions_list
    }

    logger.info(f"📤 Response: nested structure with data wrapper, count={len(subscriptions)}, "
               f"company_name={company_name}")
    return JSONResponse(content={"data": response_data})


@router.options("/{subscription_id}")
async def options_subscription(subscription_id: str, request: Request):
    """
    Handle CORS preflight requests for subscription updates.

    This endpoint doesn't require authentication because it's just a CORS preflight check.
    The actual PATCH request will require authentication.
    """
    # ENTRY POINT - This proves the handler was reached
    logger.info(f"🎯 OPTIONS HANDLER REACHED - subscription_id={subscription_id}")

    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] OPTIONS /api/subscriptions/{subscription_id} - START")

        # Log ALL request headers
        logger.info(f"📥 Request Headers:")
        for header_name, header_value in request.headers.items():
            logger.info(f"   - {header_name}: {header_value}")

        # Log specific CORS headers
        logger.info(f"🌐 CORS Headers:")
        logger.info(f"   - Origin: {request.headers.get('origin', 'NOT_SET')}")
        logger.info(f"   - Access-Control-Request-Method: {request.headers.get('access-control-request-method', 'NOT_SET')}")
        logger.info(f"   - Access-Control-Request-Headers: {request.headers.get('access-control-request-headers', 'NOT_SET')}")

        # Prepare response
        logger.info(f"🔄 Preparing CORS preflight response...")
        response_headers = {
            "Access-Control-Allow-Methods": "GET, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
        logger.info(f"📤 Response Headers:")
        for header_name, header_value in response_headers.items():
            logger.info(f"   - {header_name}: {header_value}")

        logger.info(f"✅ CORS preflight response prepared successfully")
        logger.info(f"📤 Returning 200 OK with CORS headers")

        return JSONResponse(
            content={"success": True},
            status_code=200,
            headers=response_headers
        )

    except Exception as e:
        logger.error(f"❌ OPTIONS handler failed:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - subscription_id: {subscription_id}")
        raise


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

    # ============================================================
    # STEP 1: Pydantic Validation Logging
    # ============================================================
    # NOTE: FastAPI automatically validates the request body against the SubscriptionUpdate
    # Pydantic model BEFORE this function is called. If validation fails, FastAPI returns
    # a 422 Unprocessable Entity response with detailed error messages.
    # If we reach this point, validation has already succeeded.
    # Validation errors are automatically logged by FastAPI's exception handlers.
    logger.info(f"🔍 Validating request with Pydantic SubscriptionUpdate model...")

    # Get all fields from the Pydantic model
    all_fields = set(SubscriptionUpdate.model_fields.keys())

    # Get only fields that were actually set in the request
    update_dict = update_data.model_dump(exclude_unset=True)
    set_fields = set(update_dict.keys())
    unset_fields = all_fields - set_fields

    logger.info(f"✅ Pydantic validation passed")

    # ============================================================
    # STEP 3: Field-by-Field Logging (Type + Value + Set Status)
    # ============================================================
    logger.info(f"📋 Parsed Fields (Set={len(set_fields)}, Unset={len(unset_fields)}):")

    # Log each SET field with type and value
    for key, value in update_dict.items():
        value_type = type(value).__name__
        # Truncate long values for logging
        value_display = str(value) if len(str(value)) < 100 else f"{str(value)[:97]}..."
        logger.info(f"  ✓ {key}: {value_display} (type: {value_type})")

    # Log unset fields
    if unset_fields:
        logger.info(f"❌ Unset Fields: {', '.join(sorted(unset_fields))}")
    else:
        logger.info(f"❌ Unset Fields: None (all fields provided)")

    logger.info(f"📦 Request Body (update_data):")

    # Log full request body with all fields
    for key, value in update_dict.items():
        logger.info(f"   - {key}: {value}")

    logger.info(f"📋 Full Update Payload: {update_dict}")

    try:
        # Try to update by ObjectId first
        logger.info(f"🔄 Calling subscription_service.update_subscription()...")
        try:
            subscription = await subscription_service.update_subscription(subscription_id, update_data)
            logger.info(f"🔎 Database Update Result (by ObjectId): found={subscription is not None}")
        except InvalidId:
            # Not a valid ObjectId, will try subscription_id field below
            logger.info(f"🔎 subscription_id is not a valid ObjectId, trying subscription_id field...")
            subscription = None

        # If not found by ObjectId, try by subscription_id field
        if not subscription:
            logger.info(f"🔎 Not found by ObjectId, trying update by subscription_id field...")

            # Get only fields that were actually set in the request
            update_dict = update_data.model_dump(exclude_unset=True)

            if update_dict:
                # Convert Decimal to float for MongoDB
                for key, value in update_dict.items():
                    if isinstance(value, Decimal):
                        update_dict[key] = float(value)

                update_dict["updated_at"] = datetime.now(timezone.utc)

                subscription = await database.subscriptions.find_one_and_update(
                    {"subscription_id": subscription_id},
                    {"$set": update_dict},
                    return_document=ReturnDocument.AFTER
                )
                logger.info(f"🔎 Database Update Result (by subscription_id): found={subscription is not None}")

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
                "billing_frequency": subscription.get("billing_frequency", "quarterly"),
                "payment_terms_days": subscription.get("payment_terms_days", 30),
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
