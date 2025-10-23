"""
Payment repository for Square payment operations.

This module provides database operations for the payments collection,
including creating, retrieving, updating, and querying payment records.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection

from app.database.mongodb import database
from app.models.payment import Payment, PaymentCreate, PaymentUpdate


class PaymentRepository:
    """Repository for payment operations in MongoDB."""

    @property
    def collection(self) -> AsyncIOMotorCollection:
        """Get the payments collection."""
        return database.payments

    async def create_payment(self, payment_data: PaymentCreate) -> str:
        """
        Create a new payment record.

        Args:
            payment_data: Payment creation data

        Returns:
            str: The created payment's ID

        Example:
            >>> payment = PaymentCreate(
            ...     user_email="john.doe@acme.com",
            ...     square_payment_id="sq_payment_123",
            ...     amount=10600,
            ...     payment_status="completed"
            ... )
            >>> payment_id = await repo.create_payment(payment)
        """
        payment_dict = payment_data.model_dump(exclude_unset=True)
        payment_dict['created_at'] = datetime.utcnow()
        payment_dict['updated_at'] = datetime.utcnow()
        payment_dict['payment_date'] = payment_dict.get('payment_date', datetime.utcnow())

        result = await self.collection.insert_one(payment_dict)
        return str(result.inserted_id)

    async def get_payment_by_id(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a payment by its MongoDB _id.

        Args:
            payment_id: MongoDB ObjectId as string

        Returns:
            Payment document or None if not found
        """
        try:
            result = await self.collection.find_one({"_id": ObjectId(payment_id)})
            return result
        except Exception:
            return None

    async def get_payment_by_square_id(self, square_payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a payment by Square payment ID.

        Args:
            square_payment_id: Square payment ID

        Returns:
            Payment document or None if not found
        """
        return await self.collection.find_one({"square_payment_id": square_payment_id})

    async def get_payments_by_company(
        self,
        company_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get payments for a company.

        Args:
            company_id: Company ObjectId as string
            status: Optional payment status filter
            limit: Maximum number of results
            skip: Number of results to skip (for pagination)

        Returns:
            List of payment documents
        """
        query = {"company_id": company_id}
        if status:
            query["payment_status"] = status

        cursor = self.collection.find(query).sort("payment_date", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_payments_by_user(
        self,
        user_id: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get payments for a user.

        Args:
            user_id: User ObjectId as string
            limit: Maximum number of results
            skip: Number of results to skip (for pagination)

        Returns:
            List of payment documents
        """
        cursor = self.collection.find({"user_id": user_id}).sort("payment_date", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_payments_by_email(
        self,
        email: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get payments by user email.

        Args:
            email: User email address
            limit: Maximum number of results
            skip: Number of results to skip (for pagination)

        Returns:
            List of payment documents
        """
        cursor = self.collection.find({"user_email": email}).sort("payment_date", -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def update_payment(
        self,
        square_payment_id: str,
        update_data: PaymentUpdate
    ) -> bool:
        """
        Update a payment record.

        Args:
            square_payment_id: Square payment ID
            update_data: Payment update data

        Returns:
            True if updated, False otherwise
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict['updated_at'] = datetime.utcnow()

        result = await self.collection.update_one(
            {"square_payment_id": square_payment_id},
            {"$set": update_dict}
        )
        return result.modified_count > 0

    async def process_refund(
        self,
        square_payment_id: str,
        refund_id: str,
        refund_amount: int,
        refund_reason: Optional[str] = None
    ) -> bool:
        """
        Process a refund for a payment.

        Args:
            square_payment_id: Square payment ID
            refund_id: Square refund ID
            refund_amount: Refund amount in cents
            refund_reason: Optional refund reason

        Returns:
            True if refund processed, False otherwise
        """
        update_data = {
            "refund_id": refund_id,
            "refund_date": datetime.utcnow(),
            "refund_reason": refund_reason,
            "refunded_amount": refund_amount,
            "payment_status": "refunded",
            "updated_at": datetime.utcnow()
        }

        result = await self.collection.update_one(
            {"square_payment_id": square_payment_id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def get_payment_stats_by_company(
        self,
        company_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get payment statistics for a company.

        Args:
            company_id: Company ObjectId as string
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with payment statistics
        """
        match_query: Dict[str, Any] = {"company_id": company_id}

        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            match_query["payment_date"] = date_query

        pipeline = [
            {"$match": match_query},
            {
                "$group": {
                    "_id": None,
                    "total_payments": {"$sum": 1},
                    "total_amount": {"$sum": "$amount"},
                    "total_refunded": {"$sum": "$refunded_amount"},
                    "completed_payments": {
                        "$sum": {"$cond": [{"$eq": ["$payment_status", "completed"]}, 1, 0]}
                    },
                    "failed_payments": {
                        "$sum": {"$cond": [{"$eq": ["$payment_status", "failed"]}, 1, 0]}
                    }
                }
            }
        ]

        result = await self.collection.aggregate(pipeline).to_list(length=1)

        if result:
            stats = result[0]
            return {
                "total_payments": stats.get("total_payments", 0),
                "total_amount_cents": stats.get("total_amount", 0),
                "total_amount_dollars": stats.get("total_amount", 0) / 100,
                "total_refunded_cents": stats.get("total_refunded", 0),
                "total_refunded_dollars": stats.get("total_refunded", 0) / 100,
                "completed_payments": stats.get("completed_payments", 0),
                "failed_payments": stats.get("failed_payments", 0)
            }

        return {
            "total_payments": 0,
            "total_amount_cents": 0,
            "total_amount_dollars": 0.0,
            "total_refunded_cents": 0,
            "total_refunded_dollars": 0.0,
            "completed_payments": 0,
            "failed_payments": 0
        }


# Global repository instance
payment_repository = PaymentRepository()
