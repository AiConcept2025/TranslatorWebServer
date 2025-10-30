"""
MongoDB database connection and management.
"""

import logging
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, IndexModel
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError

from app.config import settings

logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB database manager with connection pooling and error handling."""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._connected: bool = False

    async def connect(self) -> bool:
        """
        Establish connection to MongoDB.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("[MongoDB] Connecting to MongoDB...")
            logger.info(f"[MongoDB] URI: {settings.mongodb_uri.split('@')[1] if '@' in settings.mongodb_uri else 'localhost'}")

            # Create async MongoDB client with connection pooling
            self.client = AsyncIOMotorClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                maxPoolSize=50,
                minPoolSize=10,
                maxIdleTimeMS=30000
            )

            # Get database
            self.db = self.client[settings.mongodb_database]

            # Test connection
            await self.client.admin.command('ping')

            self._connected = True
            logger.info(f"[MongoDB] Successfully connected to database: {settings.mongodb_database}")

            # Create indexes
            await self._create_indexes()

            return True

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"[MongoDB] Connection failed: {e}")
            self._connected = False
            return False
        except Exception as e:
            logger.error(f"[MongoDB] Unexpected error during connection: {e}", exc_info=True)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close MongoDB connection."""
        if self.client:
            logger.info("[MongoDB] Closing connection...")
            self.client.close()
            self._connected = False
            logger.info("[MongoDB] Connection closed")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check MongoDB health status.

        Returns:
            dict: Health status information
        """
        if not self._connected or not self.client:
            return {
                "healthy": False,
                "status": "disconnected",
                "message": "MongoDB not connected"
            }

        try:
            # Ping database
            await self.client.admin.command('ping')

            # Get server info
            server_info = await self.client.server_info()

            return {
                "healthy": True,
                "status": "connected",
                "database": settings.mongodb_database,
                "version": server_info.get('version'),
                "collections": await self.db.list_collection_names()
            }

        except Exception as e:
            logger.error(f"[MongoDB] Health check failed: {e}")
            return {
                "healthy": False,
                "status": "error",
                "message": str(e)
            }

    async def _create_indexes(self) -> None:
        """Create database indexes for performance."""
        logger.info("[MongoDB] Creating database indexes...")

        # Track creation status for each collection
        success_count = 0
        failed_count = 0

        # CRITICAL FIX: Wrap EACH collection's index creation in its own try-except
        # Previously, if one collection failed, ALL subsequent collections were skipped
        # Now each collection failure is isolated and doesn't block others

        # Company collection indexes (singular collection name)
        try:
            companies_indexes = [
                IndexModel([("company_name", ASCENDING)], unique=True, name="company_name_unique"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.company.create_indexes(companies_indexes)
            logger.info("[MongoDB] Company indexes created")
            success_count += 1
        except (OperationFailure, Exception) as e:
            logger.warning(f"[MongoDB] Company index creation failed: {e}")
            failed_count += 1

        # Users collection indexes
        try:
            users_indexes = [
                IndexModel([("user_id", ASCENDING)], unique=True, name="user_id_unique"),
                IndexModel([("email", ASCENDING)], name="email_idx"),
                IndexModel([("company_name", ASCENDING)], name="company_name_idx"),
                IndexModel([("email", ASCENDING), ("company_name", ASCENDING)], name="email_company_idx"),
                IndexModel([("status", ASCENDING)], name="status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.users.create_indexes(users_indexes)
            logger.info("[MongoDB] Users indexes created")
            success_count += 1
        except (OperationFailure, Exception) as e:
            logger.warning(f"[MongoDB] Users index creation failed: {e}")
            failed_count += 1

        # Company users collection indexes (for enterprise/corporate users)
        try:
            # Drop old indexes if they exist (migration cleanup)
            try:
                await self.db.company_users.drop_index("old_company_idx")
                logger.info("[MongoDB] Dropped old company index")
            except (OperationFailure, Exception):
                pass
            try:
                await self.db.company_users.drop_index("old_email_company_idx")
                logger.info("[MongoDB] Dropped old email_company index")
            except (OperationFailure, Exception):
                pass

            company_users_indexes = [
                IndexModel([("user_id", ASCENDING)], unique=True, name="user_id_unique"),
                IndexModel([("email", ASCENDING)], name="email_idx"),
                IndexModel([("company_name", ASCENDING)], name="company_name_idx"),
                IndexModel([("email", ASCENDING), ("company_name", ASCENDING)], name="email_company_idx"),
                IndexModel([("status", ASCENDING)], name="status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.company_users.create_indexes(company_users_indexes)
            logger.info("[MongoDB] Company users indexes created (company_name migration complete)")
            success_count += 1
        except (OperationFailure, Exception) as e:
            logger.warning(f"[MongoDB] Company users index creation failed: {e}")
            failed_count += 1

        # Sessions collection indexes
        # COMMENTED OUT - Short-term solution: Sessions table updates disabled
        logger.info("[MongoDB] Sessions indexes SKIPPED (commented out for short-term solution)")

        # TTL index creation removed - conflicted with existing expires_at_idx
        # MongoDB will handle expiration based on expires_at field

        # Subscriptions collection indexes
        # UNIQUE constraint: ONE subscription per company (company_name_unique)
        try:
            # Drop old indexes if they exist (migration cleanup)
            try:
                await self.db.subscriptions.drop_index("old_company_idx")
                logger.info("[MongoDB] Dropped old company index")
            except (OperationFailure, Exception):
                pass
            try:
                await self.db.subscriptions.drop_index("old_company_unique")
                logger.info("[MongoDB] Dropped old company unique index")
            except (OperationFailure, Exception):
                pass
            try:
                await self.db.subscriptions.drop_index("old_company_status_idx")
                logger.info("[MongoDB] Dropped old company status index")
            except (OperationFailure, Exception):
                pass

            subscriptions_indexes = [
                IndexModel([("company_name", ASCENDING)], unique=True, name="company_name_unique"),
                IndexModel([("status", ASCENDING)], name="status_idx"),
                IndexModel([("start_date", ASCENDING)], name="start_date_idx"),
                IndexModel([("end_date", ASCENDING)], name="end_date_idx"),
                IndexModel([("company_name", ASCENDING), ("status", ASCENDING)], name="company_status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.subscriptions.create_indexes(subscriptions_indexes)
            logger.info("[MongoDB] Subscriptions indexes created (company_name UNIQUE constraint enforced)")
            success_count += 1
        except (OperationFailure, Exception) as e:
            logger.warning(f"[MongoDB] Subscriptions index creation failed: {e}")
            failed_count += 1

        # Users login collection indexes (for simple user auth)
        try:
            users_login_indexes = [
                IndexModel([("user_email", ASCENDING)], unique=True, name="user_email_unique"),
                IndexModel([("user_name", ASCENDING)], unique=True, name="user_name_unique"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.users_login.create_indexes(users_login_indexes)
            logger.info("[MongoDB] Users login indexes created")
            success_count += 1
        except (OperationFailure, Exception) as e:
            logger.warning(f"[MongoDB] Users login index creation failed: {e}")
            failed_count += 1

        # Translation transactions collection indexes
        try:
            # Drop old indexes if they exist (migration cleanup)
            try:
                await self.db.translation_transactions.drop_index("old_company_status_idx")
                logger.info("[MongoDB] Dropped old company status index")
            except (OperationFailure, Exception):
                pass

            translation_transactions_indexes = [
                IndexModel([("transaction_id", ASCENDING)], unique=True, name="transaction_id_unique"),
                IndexModel([("company_name", ASCENDING), ("status", ASCENDING)], name="company_status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.translation_transactions.create_indexes(translation_transactions_indexes)
            logger.info("[MongoDB] Translation transactions indexes created (company_name migration complete)")
            success_count += 1
        except (OperationFailure, Exception) as e:
            logger.warning(f"[MongoDB] Translation transactions index creation failed: {e}")
            failed_count += 1

        # User transactions collection indexes (for individual users)
        try:
            user_transactions_indexes = [
                IndexModel([("square_transaction_id", ASCENDING)], unique=True, name="square_transaction_id_unique"),
                IndexModel([("user_email", ASCENDING)], name="user_email_idx"),
                IndexModel([("date", ASCENDING)], name="date_desc_idx"),
                IndexModel([("user_email", ASCENDING), ("date", ASCENDING)], name="user_email_date_idx"),
                IndexModel([("status", ASCENDING)], name="status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.user_transactions.create_indexes(user_transactions_indexes)
            logger.info("[MongoDB] User transactions indexes created")
            success_count += 1
        except (OperationFailure, Exception) as e:
            logger.warning(f"[MongoDB] User transactions index creation failed: {e}")
            failed_count += 1

        # Payments collection indexes (for Square payments) - CRITICAL FOR PAYMENT FUNCTIONALITY
        # NOTE: square_payment_id is NOT unique to support stub implementation with hardcoded IDs
        try:
            payments_indexes = [
                IndexModel([("square_payment_id", ASCENDING)], name="square_payment_id_idx"),
                IndexModel([("company_name", ASCENDING)], name="company_name_idx"),
                IndexModel([("subscription_id", ASCENDING)], name="subscription_id_idx"),
                IndexModel([("user_id", ASCENDING)], name="user_id_idx"),
                IndexModel([("payment_status", ASCENDING)], name="payment_status_idx"),
                IndexModel([("payment_date", ASCENDING)], name="payment_date_idx"),
                IndexModel([("user_email", ASCENDING)], name="user_email_idx"),
                IndexModel([("company_name", ASCENDING), ("payment_status", ASCENDING)], name="company_status_idx"),
                IndexModel([("user_id", ASCENDING), ("payment_date", ASCENDING)], name="user_payment_date_idx"),
                IndexModel([("square_order_id", ASCENDING)], name="square_order_id_idx"),
                IndexModel([("square_customer_id", ASCENDING)], name="square_customer_id_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.payments.create_indexes(payments_indexes)
            logger.info("[MongoDB] Payments indexes created")
            success_count += 1
        except (OperationFailure, Exception) as e:
            logger.warning(f"[MongoDB] Payments index creation failed: {e}")
            failed_count += 1

        logger.info(f"[MongoDB] Index creation completed: {success_count} collections successful, {failed_count} collections had issues")

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connected

    # Collection accessors
    @property
    def company(self):
        """Get company collection (singular)."""
        return self.db.company if self.db is not None else None

    @property
    def companies(self):
        """Get companies collection (maps to 'company' singular collection)."""
        if self.db is not None:
            return self.db.company  # Using singular 'company' collection
        return None

    @property
    def users(self):
        """Get users collection (for individual users and new enterprise users)."""
        return self.db.users if self.db is not None else None

    @property
    def company_users(self):
        """Get company_users collection (for enterprise/corporate users)."""
        return self.db.company_users if self.db is not None else None

    @property
    def sessions(self):
        """Get sessions collection."""
        return self.db.sessions if self.db is not None else None

    @property
    def subscriptions(self):
        """Get subscriptions collection."""
        return self.db.subscriptions if self.db is not None else None

    @property
    def translation_transactions(self):
        """Get translation_transactions collection."""
        return self.db.translation_transactions if self.db is not None else None

    @property
    def users_login(self):
        """Get users_login collection for simple user authentication."""
        return self.db.users_login if self.db is not None else None

    @property
    def user_transactions(self):
        """Get user_transactions collection for individual users."""
        return self.db.user_transactions if self.db is not None else None

    @property
    def payments(self):
        """Get payments collection for Square payment tracking."""
        return self.db.payments if self.db is not None else None

    @property
    def invoices(self):
        """Get invoices collection."""
        return self.db.invoices if self.db is not None else None


# Global database instance
database = MongoDB()
