"""
MongoDB database connection and utility functions.
Provides async Motor client for FastAPI and sync PyMongo client for scripts.
"""

import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from app.config import settings


logger = logging.getLogger(__name__)


class Database:
    """MongoDB database connection manager."""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._sync_client: Optional[MongoClient] = None

    async def connect(self):
        """Connect to MongoDB using Motor (async driver)."""
        try:
            # MongoDB connection string from settings
            mongodb_uri = settings.mongodb_uri
            database_name = settings.mongodb_database

            logger.info(f"Connecting to MongoDB: {mongodb_uri.split('@')[1]}")  # Log without credentials

            # Create async Motor client
            self.client = AsyncIOMotorClient(
                mongodb_uri,
                serverSelectionTimeoutMS=5000,  # 5 second timeout
                connectTimeoutMS=10000,  # 10 second connection timeout
                maxPoolSize=50,  # Max connection pool size
                minPoolSize=10   # Min connection pool size
            )

            # Get database
            self.db = self.client[database_name]

            # Test connection
            await self.client.admin.command('ping')

            # Get collection count
            collections = await self.db.list_collection_names()
            logger.info(f"✓ Connected to MongoDB successfully")
            logger.info(f"✓ Database 'translation' has {len(collections)} collections")

            # Log available collections
            if collections:
                logger.info(f"✓ Collections: {', '.join(sorted(collections)[:5])}{'...' if len(collections) > 5 else ''}")

            return True

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            logger.warning("Application will start without database connection")
            self.client = None
            self.db = None
            return False

        except Exception as e:
            logger.error(f"Unexpected error connecting to MongoDB: {e}", exc_info=True)
            self.client = None
            self.db = None
            return False

    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            logger.info("Disconnecting from MongoDB...")
            self.client.close()
            self.client = None
            self.db = None
            logger.info("✓ Disconnected from MongoDB")

    def get_sync_client(self) -> MongoClient:
        """
        Get synchronous PyMongo client for scripts and testing.
        Should not be used in async FastAPI endpoints.
        """
        if not self._sync_client:
            mongodb_uri = settings.mongodb_uri
            self._sync_client = MongoClient(mongodb_uri)
        return self._sync_client

    def close_sync_client(self):
        """Close synchronous client."""
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self.client is not None and self.db is not None

    async def health_check(self) -> dict:
        """
        Check MongoDB health status.
        Returns dict with status and details.
        """
        if not self.is_connected():
            return {
                "status": "disconnected",
                "healthy": False,
                "message": "No database connection"
            }

        try:
            # Ping server
            await self.client.admin.command('ping')

            # Get server info
            server_info = await self.client.server_info()

            # Get database stats
            stats = await self.db.command('dbStats')

            return {
                "status": "connected",
                "healthy": True,
                "mongodb_version": server_info.get('version', 'unknown'),
                "database": settings.mongodb_database,
                "collections": stats.get('collections', 0),
                "data_size": stats.get('dataSize', 0),
                "storage_size": stats.get('storageSize', 0),
                "indexes": stats.get('indexes', 0)
            }

        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return {
                "status": "error",
                "healthy": False,
                "message": str(e)
            }

    # Collection getters for easy access
    @property
    def companies(self):
        """Get company collection."""
        return self.db.company if self.db else None

    @property
    def company_users(self):
        """Get company_users collection."""
        return self.db.company_users if self.db else None

    @property
    def subscriptions(self):
        """Get subscriptions collection."""
        return self.db.subscriptions if self.db else None

    @property
    def invoices(self):
        """Get invoices collection."""
        return self.db.invoices if self.db else None

    @property
    def payments(self):
        """Get payments collection."""
        return self.db.payments if self.db else None

    @property
    def translation_transactions(self):
        """Get translation_transactions collection."""
        return self.db.translation_transactions if self.db else None


# Global database instance
database = Database()


def get_database() -> Database:
    """
    Dependency injection function for FastAPI endpoints.

    Usage:
        @app.get("/example")
        async def example(db: Database = Depends(get_database)):
            result = await db.companies.find_one({"_id": company_id})
    """
    return database


async def get_db() -> AsyncIOMotorDatabase:
    """
    FastAPI dependency to get database instance.

    Usage:
        @app.get("/example")
        async def example(db = Depends(get_db)):
            result = await db.company.find_one({"_id": company_id})
    """
    if database.db is None:
        raise RuntimeError("Database not connected")
    return database.db
