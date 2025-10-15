"""
Subscription service for managing customer subscriptions and usage tracking.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId
from decimal import Decimal

from app.database.mongodb import database
from app.models.subscription import (
    SubscriptionCreate,
    SubscriptionUpdate,
    UsagePeriodCreate,
    UsageUpdate,
    SubscriptionResponse,
    SubscriptionSummary,
    UsagePeriod
)

logger = logging.getLogger(__name__)


class SubscriptionError(Exception):
    """Base subscription error."""
    pass


class SubscriptionService:
    """Service for managing subscriptions."""

    async def create_subscription(self, subscription_data: SubscriptionCreate) -> Dict[str, Any]:
        """
        Create a new subscription for a company.

        Args:
            subscription_data: Subscription creation data

        Returns:
            dict: Created subscription document

        Raises:
            SubscriptionError: If creation fails
        """
        logger.info(f"[SUBSCRIPTION] Creating subscription for company: {subscription_data.company_id}")

        # Verify company exists
        company = await database.companies.find_one({"_id": ObjectId(subscription_data.company_id)})
        if not company:
            raise SubscriptionError(f"Company not found: {subscription_data.company_id}")

        now = datetime.now(timezone.utc)

        # Create subscription document
        subscription_doc = {
            "company_id": ObjectId(subscription_data.company_id),
            "subscription_unit": subscription_data.subscription_unit,
            "units_per_subscription": subscription_data.units_per_subscription,
            "price_per_unit": float(subscription_data.price_per_unit),
            "promotional_units": subscription_data.promotional_units,
            "discount": float(subscription_data.discount),
            "subscription_price": float(subscription_data.subscription_price),
            "start_date": subscription_data.start_date,
            "end_date": subscription_data.end_date,
            "status": subscription_data.status,
            "usage_periods": [],
            "created_at": now,
            "updated_at": now
        }

        # Insert into MongoDB
        result = await database.subscriptions.insert_one(subscription_doc)
        subscription_doc["_id"] = result.inserted_id

        logger.info(f"[SUBSCRIPTION] Created subscription ID: {result.inserted_id}")

        return subscription_doc

    async def get_subscription(self, subscription_id: str) -> Optional[Dict[str, Any]]:
        """
        Get subscription by ID.

        Args:
            subscription_id: Subscription ID

        Returns:
            dict: Subscription document or None
        """
        try:
            subscription = await database.subscriptions.find_one({"_id": ObjectId(subscription_id)})
            return subscription
        except Exception as e:
            logger.error(f"[SUBSCRIPTION] Error fetching subscription {subscription_id}: {e}")
            return None

    async def get_company_subscriptions(
        self,
        company_id: str,
        status: Optional[str] = None,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all subscriptions for a company.

        Args:
            company_id: Company ID
            status: Filter by status (active, inactive, expired)
            active_only: Only return active subscriptions

        Returns:
            list: List of subscription documents
        """
        query = {"company_id": ObjectId(company_id)}

        if active_only:
            query["status"] = "active"
        elif status:
            query["status"] = status

        subscriptions = await database.subscriptions.find(query).sort("created_at", -1).to_list(length=100)

        logger.info(f"[SUBSCRIPTION] Found {len(subscriptions)} subscriptions for company {company_id}")

        return subscriptions

    async def update_subscription(
        self,
        subscription_id: str,
        update_data: SubscriptionUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        Update subscription details.

        Args:
            subscription_id: Subscription ID
            update_data: Update data

        Returns:
            dict: Updated subscription or None
        """
        update_dict = update_data.model_dump(exclude_unset=True)

        if not update_dict:
            return await self.get_subscription(subscription_id)

        # Convert Decimal to float for MongoDB
        for key, value in update_dict.items():
            if isinstance(value, Decimal):
                update_dict[key] = float(value)

        update_dict["updated_at"] = datetime.now(timezone.utc)

        result = await database.subscriptions.find_one_and_update(
            {"_id": ObjectId(subscription_id)},
            {"$set": update_dict},
            return_document=True
        )

        if result:
            logger.info(f"[SUBSCRIPTION] Updated subscription {subscription_id}")

        return result

    async def add_usage_period(
        self,
        subscription_id: str,
        period_data: UsagePeriodCreate
    ) -> Optional[Dict[str, Any]]:
        """
        Add a new usage period to a subscription.

        Args:
            subscription_id: Subscription ID
            period_data: Usage period data

        Returns:
            dict: Updated subscription or None

        Raises:
            SubscriptionError: If subscription not found or validation fails
        """
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription not found: {subscription_id}")

        # Create usage period
        usage_period = {
            "period_start": period_data.period_start,
            "period_end": period_data.period_end,
            "units_allocated": period_data.units_allocated,
            "units_used": 0,
            "units_remaining": period_data.units_allocated,
            "promotional_units_used": 0,
            "last_updated": datetime.now(timezone.utc)
        }

        # Add to subscription
        result = await database.subscriptions.find_one_and_update(
            {"_id": ObjectId(subscription_id)},
            {
                "$push": {"usage_periods": usage_period},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            },
            return_document=True
        )

        logger.info(f"[SUBSCRIPTION] Added usage period to subscription {subscription_id}")

        return result

    async def record_usage(
        self,
        subscription_id: str,
        usage_data: UsageUpdate
    ) -> Optional[Dict[str, Any]]:
        """
        Record usage for the current period.

        Args:
            subscription_id: Subscription ID
            usage_data: Usage update data

        Returns:
            dict: Updated subscription or None

        Raises:
            SubscriptionError: If no active period or insufficient units
        """
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            raise SubscriptionError(f"Subscription not found: {subscription_id}")

        # Find current active period
        usage_periods = subscription.get("usage_periods", [])
        if not usage_periods:
            raise SubscriptionError("No usage periods defined")

        now = datetime.now(timezone.utc)
        current_period_idx = None

        for idx, period in enumerate(usage_periods):
            period_start = period["period_start"]
            period_end = period["period_end"]

            # Handle timezone-aware comparison
            if not period_start.tzinfo:
                period_start = period_start.replace(tzinfo=timezone.utc)
            if not period_end.tzinfo:
                period_end = period_end.replace(tzinfo=timezone.utc)

            if period_start <= now <= period_end:
                current_period_idx = idx
                break

        if current_period_idx is None:
            raise SubscriptionError("No active usage period found")

        current_period = usage_periods[current_period_idx]
        units_to_add = usage_data.units_to_add

        # Check if using promotional units
        if usage_data.use_promotional_units:
            promotional_available = subscription.get("promotional_units", 0) - current_period.get("promotional_units_used", 0)

            if promotional_available >= units_to_add:
                # Use promotional units only
                update_query = {
                    f"usage_periods.{current_period_idx}.promotional_units_used": current_period.get("promotional_units_used", 0) + units_to_add,
                    f"usage_periods.{current_period_idx}.last_updated": now,
                    "updated_at": now
                }
            else:
                # Use all promotional units, then regular units
                remaining_to_use = units_to_add - promotional_available
                if current_period["units_remaining"] < remaining_to_use:
                    raise SubscriptionError(f"Insufficient units. Need {remaining_to_use}, have {current_period['units_remaining']}")

                update_query = {
                    f"usage_periods.{current_period_idx}.promotional_units_used": subscription.get("promotional_units", 0),
                    f"usage_periods.{current_period_idx}.units_used": current_period["units_used"] + remaining_to_use,
                    f"usage_periods.{current_period_idx}.units_remaining": current_period["units_remaining"] - remaining_to_use,
                    f"usage_periods.{current_period_idx}.last_updated": now,
                    "updated_at": now
                }
        else:
            # Use regular units
            if current_period["units_remaining"] < units_to_add:
                raise SubscriptionError(f"Insufficient units. Need {units_to_add}, have {current_period['units_remaining']}")

            update_query = {
                f"usage_periods.{current_period_idx}.units_used": current_period["units_used"] + units_to_add,
                f"usage_periods.{current_period_idx}.units_remaining": current_period["units_remaining"] - units_to_add,
                f"usage_periods.{current_period_idx}.last_updated": now,
                "updated_at": now
            }

        # Update subscription
        result = await database.subscriptions.find_one_and_update(
            {"_id": ObjectId(subscription_id)},
            {"$set": update_query},
            return_document=True
        )

        logger.info(f"[SUBSCRIPTION] Recorded {units_to_add} units usage for subscription {subscription_id}")

        return result

    async def get_subscription_summary(self, subscription_id: str) -> Optional[SubscriptionSummary]:
        """
        Get summary of subscription usage.

        Args:
            subscription_id: Subscription ID

        Returns:
            SubscriptionSummary or None
        """
        subscription = await self.get_subscription(subscription_id)
        if not subscription:
            return None

        usage_periods = subscription.get("usage_periods", [])

        # Calculate totals
        total_allocated = sum(p["units_allocated"] for p in usage_periods)
        total_used = sum(p["units_used"] for p in usage_periods)
        total_remaining = sum(p["units_remaining"] for p in usage_periods)
        total_promo_used = sum(p.get("promotional_units_used", 0) for p in usage_periods)

        # Find current period
        now = datetime.now(timezone.utc)
        current_period = None

        for period in usage_periods:
            period_start = period["period_start"]
            period_end = period["period_end"]

            if not period_start.tzinfo:
                period_start = period_start.replace(tzinfo=timezone.utc)
            if not period_end.tzinfo:
                period_end = period_end.replace(tzinfo=timezone.utc)

            if period_start <= now <= period_end:
                current_period = UsagePeriod(**period)
                break

        return SubscriptionSummary(
            subscription_id=str(subscription["_id"]),
            company_id=str(subscription["company_id"]),
            subscription_unit=subscription["subscription_unit"],
            total_units_allocated=total_allocated,
            total_units_used=total_used,
            total_units_remaining=total_remaining,
            promotional_units_available=subscription.get("promotional_units", 0),
            promotional_units_used=total_promo_used,
            current_period=current_period,
            status=subscription["status"],
            expires_at=subscription.get("end_date")
        )

    async def expire_subscriptions(self) -> int:
        """
        Mark expired subscriptions as expired.

        Returns:
            int: Number of subscriptions expired
        """
        now = datetime.now(timezone.utc)

        result = await database.subscriptions.update_many(
            {
                "end_date": {"$lt": now},
                "status": {"$ne": "expired"}
            },
            {
                "$set": {
                    "status": "expired",
                    "updated_at": now
                }
            }
        )

        logger.info(f"[SUBSCRIPTION] Expired {result.modified_count} subscriptions")

        return result.modified_count


# Global subscription service instance
subscription_service = SubscriptionService()
