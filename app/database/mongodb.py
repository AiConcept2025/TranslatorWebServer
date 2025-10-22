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
        try:
            logger.info("[MongoDB] Creating database indexes...")

            # Companies collection indexes
            companies_indexes = [
                IndexModel([("company_name", ASCENDING)], unique=True, name="company_name_unique"),
                IndexModel([("company_id", ASCENDING)], unique=True, name="company_id_unique"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.companies.create_indexes(companies_indexes)
            logger.info("[MongoDB] Companies indexes created")

            # Users collection indexes
            users_indexes = [
                IndexModel([("user_id", ASCENDING)], unique=True, name="user_id_unique"),
                IndexModel([("email", ASCENDING)], name="email_idx"),
                IndexModel([("company_id", ASCENDING)], name="company_id_idx"),
                IndexModel([("email", ASCENDING), ("company_id", ASCENDING)], name="email_company_idx"),
                IndexModel([("status", ASCENDING)], name="status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.users.create_indexes(users_indexes)
            logger.info("[MongoDB] Users indexes created")

            # Company users collection indexes (for enterprise/corporate users)
            company_users_indexes = [
                IndexModel([("user_id", ASCENDING)], unique=True, name="user_id_unique"),
                IndexModel([("email", ASCENDING)], name="email_idx"),
                IndexModel([("company_id", ASCENDING)], name="company_id_idx"),
                IndexModel([("email", ASCENDING), ("company_id", ASCENDING)], name="email_company_idx"),
                IndexModel([("status", ASCENDING)], name="status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.company_users.create_indexes(company_users_indexes)
            logger.info("[MongoDB] Company users indexes created")

            # Sessions collection indexes
            # COMMENTED OUT - Short-term solution: Sessions table updates disabled
            # sessions_indexes = [
            #     IndexModel([("session_token", ASCENDING)], unique=True, name="session_token_unique"),
            #     IndexModel([("user_id", ASCENDING)], name="user_id_idx"),
            #     IndexModel([("expires_at", ASCENDING)], name="expires_at_idx"),
            #     IndexModel([("is_active", ASCENDING)], name="is_active_idx"),
            #     IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            # ]
            # await self.db.sessions.create_indexes(sessions_indexes)
            # logger.info("[MongoDB] Sessions indexes created")
            logger.info("[MongoDB] Sessions indexes SKIPPED (commented out for short-term solution)")

            # TTL index creation removed - conflicted with existing expires_at_idx
            # MongoDB will handle expiration based on expires_at field

            # Subscriptions collection indexes
            subscriptions_indexes = [
                IndexModel([("company_id", ASCENDING)], name="company_id_idx"),
                IndexModel([("status", ASCENDING)], name="status_idx"),
                IndexModel([("start_date", ASCENDING)], name="start_date_idx"),
                IndexModel([("end_date", ASCENDING)], name="end_date_idx"),
                IndexModel([("company_id", ASCENDING), ("status", ASCENDING)], name="company_status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.subscriptions.create_indexes(subscriptions_indexes)
            logger.info("[MongoDB] Subscriptions indexes created")

            # Users login collection indexes (for simple user auth)
            users_login_indexes = [
                IndexModel([("user_email", ASCENDING)], unique=True, name="user_email_unique"),
                IndexModel([("user_name", ASCENDING)], unique=True, name="user_name_unique"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.users_login.create_indexes(users_login_indexes)
            logger.info("[MongoDB] Users login indexes created")

            # Translation transactions collection indexes
            translation_transactions_indexes = [
                IndexModel([("transaction_id", ASCENDING)], unique=True, name="transaction_id_unique"),
                IndexModel([("company_id", ASCENDING), ("status", ASCENDING)], name="company_status_idx"),
                IndexModel([("created_at", ASCENDING)], name="created_at_asc")
            ]
            await self.db.translation_transactions.create_indexes(translation_transactions_indexes)
            logger.info("[MongoDB] Translation transactions indexes created")

            # User transactions collection indexes (for individual users)
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

            logger.info("[MongoDB] All indexes created successfully")

        except OperationFailure as e:
            logger.warning(f"[MongoDB] Index creation warning (may already exist): {e}")
        except Exception as e:
            logger.error(f"[MongoDB] Error creating indexes: {e}", exc_info=True)

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connected

    # Collection accessors
    @property
    def companies(self):
        """Get companies collection."""
        # Check both 'companies' (plural) and 'company' (singular) collections
        # Prefer 'company' if it exists, fallback to 'companies'
        if self.db is not None:
            return self.db.company  # Actual collection name in database
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


# Global database instance
database = MongoDB()
