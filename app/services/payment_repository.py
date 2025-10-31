"""
Payment repository for Square payment operations.

This module provides database operations for the payments collection,
including creating, retrieving, updating, and querying payment records.
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
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
            ...     company_name="Acme Health LLC",
            ...     user_email="test5@yahoo.com",
            ...     square_payment_id="payment_sq_1761244600756",
            ...     amount=1299,
            ...     currency="USD",
            ...     payment_status="COMPLETED"
            ... )
            >>> payment_id = await repo.create_payment(payment)
        """
        payment_doc = {
            "company_name": payment_data.company_name,
            "user_email": payment_data.user_email,
            "square_payment_id": payment_data.square_payment_id,
            "amount": payment_data.amount,
            "currency": payment_data.currency,
            "payment_status": payment_data.payment_status,
            "refunds": [],  # Always start with empty array
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "payment_date": payment_data.payment_date or datetime.now(timezone.utc)
        }

        result = await self.collection.insert_one(payment_doc)
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
        company_name: str,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get payments for a company.

        Args:
            company_name: Company name
            status: Optional payment status filter
            limit: Maximum number of results
            skip: Number of results to skip (for pagination)

        Returns:
            List of payment documents
        """
        query = {"company_name": company_name}

        if status:
            query["payment_status"] = status

        cursor = self.collection.find(query).sort("payment_date", -1).skip(skip).limit(limit)
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

    async def get_all_payments(
        self,
        status: Optional[str] = None,
        company_name: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
        sort_by: str = "payment_date",
        sort_order: str = "desc"
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Get all payments with optional filtering and pagination.

        Args:
            status: Optional payment status filter (COMPLETED, PENDING, FAILED, REFUNDED)
            company_name: Optional company name filter
            limit: Maximum number of results to return (1-100)
            skip: Number of results to skip for pagination
            sort_by: Field to sort by (default: payment_date)
            sort_order: Sort order - 'asc' or 'desc' (default: desc)

        Returns:
            Tuple of (List of payment documents, Total count)

        Example:
            >>> payments, total = await repo.get_all_payments(
            ...     status="COMPLETED",
            ...     company_name="Acme Health LLC",
            ...     limit=20,
            ...     skip=0
            ... )
        """
        # Build query filter
        query: Dict[str, Any] = {}

        if status:
            query["payment_status"] = status

        if company_name:
            query["company_name"] = company_name

        # Get total count for pagination
        total_count = await self.collection.count_documents(query)

        # Determine sort direction
        sort_direction = -1 if sort_order == "desc" else 1

        # Execute query with sorting and pagination
        cursor = self.collection.find(query).sort(sort_by, sort_direction).skip(skip).limit(limit)
        payments = await cursor.to_list(length=limit)

        return payments, total_count

    async def update_payment(
        self,
        square_payment_id: str,
        update_data: PaymentUpdate
    ) -> bool:
        """
        Update payment status.

        Args:
            square_payment_id: Square payment ID
            update_data: Payment update data

        Returns:
            True if updated, False otherwise
        """
        update_doc = {"$set": {"updated_at": datetime.now(timezone.utc)}}

        if update_data.payment_status:
            update_doc["$set"]["payment_status"] = update_data.payment_status

        result = await self.collection.update_one(
            {"square_payment_id": square_payment_id},
            update_doc
        )
        return result.modified_count > 0

    async def process_refund(
        self,
        square_payment_id: str,
        refund_id: str,
        refund_amount: int,
        idempotency_key: str,
        refund_reason: Optional[str] = None
    ) -> bool:
        """
        Add a refund to payment's refunds array.

        Args:
            square_payment_id: Square payment ID
            refund_id: Square refund ID
            refund_amount: Refund amount in cents
            idempotency_key: Unique idempotency key for Square API
            refund_reason: Optional refund reason (not stored in refund object)

        Returns:
            True if refund processed, False otherwise
        """
        refund_obj = {
            "refund_id": refund_id,
            "amount": refund_amount,
            "currency": "USD",
            "status": "COMPLETED",
            "idempotency_key": idempotency_key,
            "created_at": datetime.now(timezone.utc)
        }

        result = await self.collection.update_one(
            {"square_payment_id": square_payment_id},
            {
                "$push": {"refunds": refund_obj},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        return result.modified_count > 0

    async def get_payment_stats_by_company(
        self,
        company_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get payment statistics for a company.

        Args:
            company_name: Company name
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with payment statistics
        """
        match_query: Dict[str, Any] = {"company_name": company_name}

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
                    "completed_payments": {
                        "$sum": {"$cond": [{"$eq": ["$payment_status", "COMPLETED"]}, 1, 0]}
                    },
                    "failed_payments": {
                        "$sum": {"$cond": [{"$eq": ["$payment_status", "FAILED"]}, 1, 0]}
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
                "completed_payments": stats.get("completed_payments", 0),
                "failed_payments": stats.get("failed_payments", 0)
            }

        return {
            "total_payments": 0,
            "total_amount_cents": 0,
            "total_amount_dollars": 0.0,
            "completed_payments": 0,
            "failed_payments": 0
        }


# Global repository instance
payment_repository = PaymentRepository()
