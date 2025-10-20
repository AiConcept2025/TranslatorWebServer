#!/usr/bin/env python3
"""
Create Admin User Script for Translation Service
Creates an iris-admins collection in MongoDB with a secure admin user.

Usage:
    python create_admin_user.py

Security:
    - Uses bcrypt for password hashing
    - Stores only the hashed password, never plain text
    - Configurable salt rounds (default: 12)
"""

import sys
import logging
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

try:
    from pymongo import MongoClient, ASCENDING
    from pymongo.errors import ConnectionFailure, DuplicateKeyError, OperationFailure
    import bcrypt
    from app.config import settings
except ImportError as e:
    print(f"Error: Missing required package - {e}")
    print("\nPlease install required packages:")
    print("  pip install pymongo bcrypt python-dotenv pydantic pydantic-settings")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AdminUserSetup:
    """Handles MongoDB connection and admin user creation."""

    COLLECTION_NAME = "iris-admins"
    BCRYPT_ROUNDS = 12  # Cost factor for bcrypt (higher = more secure but slower)

    def __init__(self):
        """Initialize MongoDB connection."""
        self.client = None
        self.db = None

    def connect(self) -> bool:
        """
        Connect to MongoDB using settings from config.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("Connecting to MongoDB...")
            logger.info(f"Database: {settings.mongodb_database}")

            # Create synchronous MongoDB client
            self.client = MongoClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=5000
            )

            # Test connection
            self.client.admin.command('ping')

            # Get database
            self.db = self.client[settings.mongodb_database]

            logger.info(f"Successfully connected to MongoDB database: {settings.mongodb_database}")
            return True

        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during connection: {e}", exc_info=True)
            return False

    def disconnect(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")

    def hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            str: Hashed password (UTF-8 decoded)
        """
        logger.info("Hashing password with bcrypt...")

        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=self.BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)

        # Return as string (decode bytes)
        hashed_str = hashed.decode('utf-8')
        logger.info(f"Password hashed successfully (salt rounds: {self.BCRYPT_ROUNDS})")

        return hashed_str

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to check against

        Returns:
            bool: True if password matches, False otherwise
        """
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    def create_collection_indexes(self):
        """Create indexes on the iris-admins collection for performance and uniqueness."""
        try:
            collection = self.db[self.COLLECTION_NAME]

            # Create unique index on user_name
            collection.create_index(
                [("user_name", ASCENDING)],
                unique=True,
                name="user_name_unique"
            )

            # Create index on login_date for query performance
            collection.create_index(
                [("login_date", ASCENDING)],
                name="login_date_idx"
            )

            logger.info("Collection indexes created successfully")

        except OperationFailure as e:
            logger.warning(f"Index creation warning (may already exist): {e}")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}", exc_info=True)

    def create_admin_user(self, username: str, password: str) -> bool:
        """
        Create admin user with hashed password.

        Args:
            username: Admin username
            password: Plain text password (will be hashed)

        Returns:
            bool: True if user created successfully, False otherwise
        """
        try:
            # Hash the password
            hashed_password = self.hash_password(password)

            # Create admin user document
            admin_user = {
                "user_name": username,
                "password": hashed_password,
                "login_date": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }

            # Insert into database
            collection = self.db[self.COLLECTION_NAME]
            result = collection.insert_one(admin_user)

            logger.info(f"Admin user created successfully!")
            logger.info(f"  Username: {username}")
            logger.info(f"  Document ID: {result.inserted_id}")
            logger.info(f"  Password hash: {hashed_password[:20]}...")

            # Verify the password hash works
            if self.verify_password(password, hashed_password):
                logger.info("  Password verification: PASSED")
            else:
                logger.warning("  Password verification: FAILED")

            return True

        except DuplicateKeyError:
            logger.error(f"User '{username}' already exists in the database!")
            logger.info("If you want to update the user, delete it first:")
            logger.info(f"  db.{self.COLLECTION_NAME}.deleteOne({{user_name: '{username}'}})")
            return False

        except Exception as e:
            logger.error(f"Error creating admin user: {e}", exc_info=True)
            return False

    def check_existing_user(self, username: str) -> bool:
        """
        Check if a user already exists.

        Args:
            username: Username to check

        Returns:
            bool: True if user exists, False otherwise
        """
        try:
            collection = self.db[self.COLLECTION_NAME]
            existing = collection.find_one({"user_name": username})
            return existing is not None
        except Exception as e:
            logger.error(f"Error checking for existing user: {e}")
            return False

    def list_admin_users(self):
        """List all admin users in the collection."""
        try:
            collection = self.db[self.COLLECTION_NAME]
            users = collection.find({}, {"user_name": 1, "login_date": 1, "created_at": 1})

            user_list = list(users)
            if user_list:
                logger.info(f"\nFound {len(user_list)} admin user(s):")
                for user in user_list:
                    logger.info(f"  - {user.get('user_name')} (created: {user.get('created_at')})")
            else:
                logger.info("No admin users found in the collection")

        except Exception as e:
            logger.error(f"Error listing admin users: {e}")


def main():
    """Main execution function."""
    # Admin user configuration
    ADMIN_USERNAME = "iris-admin"
    ADMIN_PASSWORD = "Sveta87201120!"

    logger.info("=" * 60)
    logger.info("MongoDB Admin User Setup Script")
    logger.info("=" * 60)

    # Create setup instance
    setup = AdminUserSetup()

    try:
        # Connect to MongoDB
        if not setup.connect():
            logger.error("Failed to connect to MongoDB. Exiting.")
            sys.exit(1)

        # Check if user already exists
        if setup.check_existing_user(ADMIN_USERNAME):
            logger.warning(f"\nUser '{ADMIN_USERNAME}' already exists!")
            response = input("Do you want to view existing users? (y/n): ")
            if response.lower() == 'y':
                setup.list_admin_users()
            sys.exit(0)

        # Create collection indexes
        setup.create_collection_indexes()

        # Create admin user
        logger.info("\nCreating admin user...")
        success = setup.create_admin_user(ADMIN_USERNAME, ADMIN_PASSWORD)

        if success:
            logger.info("\n" + "=" * 60)
            logger.info("SUCCESS: Admin user created and configured!")
            logger.info("=" * 60)
            logger.info("\nCollection details:")
            logger.info(f"  Database: {settings.mongodb_database}")
            logger.info(f"  Collection: {setup.COLLECTION_NAME}")
            logger.info(f"  Username: {ADMIN_USERNAME}")
            logger.info(f"  Password: [SECURELY HASHED]")
            logger.info("\nSecurity notes:")
            logger.info(f"  - Password hashed with bcrypt (rounds: {setup.BCRYPT_ROUNDS})")
            logger.info("  - Plain text password is NOT stored in database")
            logger.info("  - Unique index created on user_name field")
            logger.info("\nYou can now use these credentials to authenticate")

            # List all users
            setup.list_admin_users()
        else:
            logger.error("\nFailed to create admin user")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"\nUnexpected error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Always disconnect
        setup.disconnect()


if __name__ == "__main__":
    main()
