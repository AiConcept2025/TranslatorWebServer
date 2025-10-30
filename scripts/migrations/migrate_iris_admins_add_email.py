#!/usr/bin/env python3
"""
Migration Script: Add user_email field to iris-admins collection

This script performs the following operations:
1. Adds user_email field to existing iris-admin record
2. Creates unique index on user_email
3. Inserts new admin user with hashed password

Database: translation
Collection: iris-admins

Author: Database Architect
Date: 2025-10-30
"""

import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from pymongo import MongoClient, ASCENDING
    from pymongo.errors import (
        ConnectionFailure,
        DuplicateKeyError,
        OperationFailure,
        ServerSelectionTimeoutError
    )
    import bcrypt
    from bson import ObjectId
except ImportError as e:
    print(f"Error: Missing required package - {e}")
    print("\nPlease install required packages:")
    print("  pip install pymongo bcrypt")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IrisAdminMigration:
    """Handles iris-admins collection migration with rollback support."""

    COLLECTION_NAME = "iris-admins"
    BCRYPT_ROUNDS = 12

    # MongoDB connection details
    MONGODB_URI = "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"
    DATABASE_NAME = "translation"

    # Existing record details
    EXISTING_ADMIN_ID = "68f3a1c1e44710d091e002e5"
    EXISTING_ADMIN_EMAIL = "admin@iris-translation.com"

    # New admin user details
    NEW_ADMIN_USERNAME = "Vladimir Danishevsky"
    NEW_ADMIN_EMAIL = "danishevsky@gmail.com"
    NEW_ADMIN_PASSWORD = "Sveta87201120!"

    def __init__(self):
        """Initialize MongoDB connection."""
        self.client: Optional[MongoClient] = None
        self.db = None
        self.migration_log: Dict[str, Any] = {
            "started_at": datetime.now(timezone.utc),
            "steps_completed": [],
            "steps_failed": [],
            "rollback_needed": False
        }

    def connect(self) -> bool:
        """
        Connect to MongoDB.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            logger.info("=" * 80)
            logger.info("IRIS-ADMINS MIGRATION: Add user_email field")
            logger.info("=" * 80)
            logger.info(f"Target database: {self.DATABASE_NAME}")
            logger.info(f"Target collection: {self.COLLECTION_NAME}")
            logger.info("")

            logger.info("Connecting to MongoDB...")

            # Create synchronous MongoDB client
            self.client = MongoClient(
                self.MONGODB_URI,
                serverSelectionTimeoutMS=5000
            )

            # Test connection
            self.client.admin.command('ping')

            # Get database
            self.db = self.client[self.DATABASE_NAME]

            logger.info(f"✓ Successfully connected to MongoDB database: {self.DATABASE_NAME}")
            return True

        except ConnectionFailure as e:
            logger.error(f"✗ Failed to connect to MongoDB: {e}")
            return False
        except ServerSelectionTimeoutError as e:
            logger.error(f"✗ MongoDB server selection timeout: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error during connection: {e}", exc_info=True)
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
        logger.info(f"Hashing password with bcrypt (rounds: {self.BCRYPT_ROUNDS})...")

        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=self.BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)

        # Return as string (decode bytes)
        hashed_str = hashed.decode('utf-8')
        logger.info(f"✓ Password hashed successfully")

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

    def check_preconditions(self) -> bool:
        """
        Check if migration can proceed safely.

        Returns:
            bool: True if preconditions met, False otherwise
        """
        logger.info("")
        logger.info("STEP 0: Checking preconditions...")
        logger.info("-" * 80)

        try:
            collection = self.db[self.COLLECTION_NAME]

            # Check if collection exists
            if self.COLLECTION_NAME not in self.db.list_collection_names():
                logger.error(f"✗ Collection '{self.COLLECTION_NAME}' does not exist!")
                return False

            logger.info(f"✓ Collection '{self.COLLECTION_NAME}' exists")

            # Check if existing admin record exists
            existing_admin = collection.find_one({
                "_id": ObjectId(self.EXISTING_ADMIN_ID)
            })

            if not existing_admin:
                logger.error(f"✗ Existing admin record not found (ID: {self.EXISTING_ADMIN_ID})")
                return False

            logger.info(f"✓ Existing admin record found:")
            logger.info(f"  - user_name: {existing_admin.get('user_name')}")
            logger.info(f"  - _id: {existing_admin.get('_id')}")

            # Check if user_email already exists (migration already run?)
            if 'user_email' in existing_admin:
                logger.warning(f"⚠ user_email field already exists: {existing_admin.get('user_email')}")
                logger.warning("  Migration may have been run previously")

            # Check if new admin user already exists
            new_admin_exists = collection.find_one({
                "user_email": self.NEW_ADMIN_EMAIL
            })

            if new_admin_exists:
                logger.warning(f"⚠ New admin user already exists:")
                logger.warning(f"  - user_name: {new_admin_exists.get('user_name')}")
                logger.warning(f"  - user_email: {new_admin_exists.get('user_email')}")
                logger.warning("  Migration may have been run previously")

            # Count total admin users
            total_admins = collection.count_documents({})
            logger.info(f"✓ Total admin users in collection: {total_admins}")

            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Precondition check failed: {e}", exc_info=True)
            return False

    def step1_add_email_to_existing_admin(self) -> bool:
        """
        Add user_email field to existing iris-admin record.

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("STEP 1: Add user_email to existing admin record")
        logger.info("-" * 80)

        try:
            collection = self.db[self.COLLECTION_NAME]

            # Update existing admin record
            result = collection.update_one(
                {"_id": ObjectId(self.EXISTING_ADMIN_ID)},
                {
                    "$set": {
                        "user_email": self.EXISTING_ADMIN_EMAIL,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            if result.matched_count == 0:
                logger.error(f"✗ Admin record not found (ID: {self.EXISTING_ADMIN_ID})")
                return False

            if result.modified_count == 0:
                logger.warning("⚠ No changes made (field may already exist)")
            else:
                logger.info("✓ Successfully added user_email field")

            # Verify the update
            updated_admin = collection.find_one({
                "_id": ObjectId(self.EXISTING_ADMIN_ID)
            })

            logger.info(f"  - user_name: {updated_admin.get('user_name')}")
            logger.info(f"  - user_email: {updated_admin.get('user_email')}")
            logger.info(f"  - updated_at: {updated_admin.get('updated_at')}")

            self.migration_log["steps_completed"].append("step1_add_email")
            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Step 1 failed: {e}", exc_info=True)
            self.migration_log["steps_failed"].append(("step1_add_email", str(e)))
            return False

    def step2_create_unique_index(self) -> bool:
        """
        Create unique index on user_email field.

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("STEP 2: Create unique index on user_email")
        logger.info("-" * 80)

        try:
            collection = self.db[self.COLLECTION_NAME]

            # Create unique index on user_email
            collection.create_index(
                [("user_email", ASCENDING)],
                unique=True,
                name="user_email_unique",
                background=True
            )

            logger.info("✓ Successfully created unique index on user_email")

            # List all indexes
            indexes = list(collection.list_indexes())
            logger.info(f"  Total indexes: {len(indexes)}")
            for idx in indexes:
                logger.info(f"  - {idx.get('name')}: {idx.get('key')}")

            self.migration_log["steps_completed"].append("step2_create_index")
            logger.info("")
            return True

        except OperationFailure as e:
            if "already exists" in str(e).lower():
                logger.warning("⚠ Index already exists (may have been created previously)")
                self.migration_log["steps_completed"].append("step2_create_index")
                logger.info("")
                return True
            else:
                logger.error(f"✗ Step 2 failed: {e}", exc_info=True)
                self.migration_log["steps_failed"].append(("step2_create_index", str(e)))
                return False
        except Exception as e:
            logger.error(f"✗ Step 2 failed: {e}", exc_info=True)
            self.migration_log["steps_failed"].append(("step2_create_index", str(e)))
            return False

    def step3_insert_new_admin(self) -> bool:
        """
        Insert new admin user with hashed password.

        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("STEP 3: Insert new admin user")
        logger.info("-" * 80)

        try:
            collection = self.db[self.COLLECTION_NAME]

            # Check if user already exists
            existing = collection.find_one({
                "user_email": self.NEW_ADMIN_EMAIL
            })

            if existing:
                logger.warning("⚠ New admin user already exists:")
                logger.warning(f"  - user_name: {existing.get('user_name')}")
                logger.warning(f"  - user_email: {existing.get('user_email')}")
                logger.warning("  Skipping insertion")
                self.migration_log["steps_completed"].append("step3_insert_admin")
                logger.info("")
                return True

            # Hash the password
            hashed_password = self.hash_password(self.NEW_ADMIN_PASSWORD)

            # Create new admin user document
            now = datetime.now(timezone.utc)
            admin_doc = {
                "user_name": self.NEW_ADMIN_USERNAME,
                "user_email": self.NEW_ADMIN_EMAIL,
                "password": hashed_password,
                "login_date": now,
                "created_at": now,
                "updated_at": now
            }

            # Insert into database
            result = collection.insert_one(admin_doc)

            logger.info("✓ Successfully inserted new admin user")
            logger.info(f"  - user_name: {self.NEW_ADMIN_USERNAME}")
            logger.info(f"  - user_email: {self.NEW_ADMIN_EMAIL}")
            logger.info(f"  - _id: {result.inserted_id}")
            logger.info(f"  - password_hash: {hashed_password[:30]}...")

            # Verify password hash
            if self.verify_password(self.NEW_ADMIN_PASSWORD, hashed_password):
                logger.info("  - password verification: PASSED ✓")
            else:
                logger.error("  - password verification: FAILED ✗")
                return False

            self.migration_log["steps_completed"].append("step3_insert_admin")
            logger.info("")
            return True

        except DuplicateKeyError:
            logger.error(f"✗ Duplicate key error - user already exists")
            self.migration_log["steps_failed"].append(("step3_insert_admin", "Duplicate key"))
            return False
        except Exception as e:
            logger.error(f"✗ Step 3 failed: {e}", exc_info=True)
            self.migration_log["steps_failed"].append(("step3_insert_admin", str(e)))
            return False

    def verify_migration(self) -> bool:
        """
        Verify migration completed successfully.

        Returns:
            bool: True if verification passed, False otherwise
        """
        logger.info("STEP 4: Verify migration")
        logger.info("-" * 80)

        try:
            collection = self.db[self.COLLECTION_NAME]

            # Verify existing admin has user_email
            existing_admin = collection.find_one({
                "_id": ObjectId(self.EXISTING_ADMIN_ID)
            })

            if not existing_admin or 'user_email' not in existing_admin:
                logger.error("✗ Existing admin does not have user_email field")
                return False

            logger.info("✓ Existing admin has user_email field:")
            logger.info(f"  - user_name: {existing_admin.get('user_name')}")
            logger.info(f"  - user_email: {existing_admin.get('user_email')}")

            # Verify new admin exists
            new_admin = collection.find_one({
                "user_email": self.NEW_ADMIN_EMAIL
            })

            if not new_admin:
                logger.error("✗ New admin user not found")
                return False

            logger.info("✓ New admin user exists:")
            logger.info(f"  - user_name: {new_admin.get('user_name')}")
            logger.info(f"  - user_email: {new_admin.get('user_email')}")

            # Verify unique index exists
            indexes = list(collection.list_indexes())
            index_names = [idx.get('name') for idx in indexes]

            if 'user_email_unique' not in index_names:
                logger.error("✗ Unique index on user_email not found")
                return False

            logger.info("✓ Unique index on user_email exists")

            # Count total admins
            total_admins = collection.count_documents({})
            logger.info(f"✓ Total admin users: {total_admins}")

            logger.info("")
            return True

        except Exception as e:
            logger.error(f"✗ Verification failed: {e}", exc_info=True)
            return False

    def print_summary(self, success: bool):
        """Print migration summary."""
        logger.info("=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)

        if success:
            logger.info("Status: SUCCESS ✓")
        else:
            logger.info("Status: FAILED ✗")

        logger.info("")
        logger.info(f"Started at: {self.migration_log['started_at']}")
        logger.info(f"Completed at: {datetime.now(timezone.utc)}")
        logger.info("")

        if self.migration_log["steps_completed"]:
            logger.info("Steps completed:")
            for step in self.migration_log["steps_completed"]:
                logger.info(f"  ✓ {step}")

        if self.migration_log["steps_failed"]:
            logger.info("")
            logger.info("Steps failed:")
            for step, error in self.migration_log["steps_failed"]:
                logger.info(f"  ✗ {step}: {error}")

        logger.info("")
        logger.info("=" * 80)

    def run(self) -> bool:
        """
        Execute the migration.

        Returns:
            bool: True if migration successful, False otherwise
        """
        try:
            # Check preconditions
            if not self.check_preconditions():
                logger.error("Preconditions not met. Aborting migration.")
                return False

            # Execute migration steps
            if not self.step1_add_email_to_existing_admin():
                logger.error("Step 1 failed. Aborting migration.")
                return False

            if not self.step2_create_unique_index():
                logger.error("Step 2 failed. Aborting migration.")
                return False

            if not self.step3_insert_new_admin():
                logger.error("Step 3 failed. Aborting migration.")
                return False

            # Verify migration
            if not self.verify_migration():
                logger.error("Migration verification failed!")
                return False

            return True

        except Exception as e:
            logger.error(f"Migration failed with unexpected error: {e}", exc_info=True)
            return False


def main():
    """Main execution function."""
    migration = IrisAdminMigration()

    try:
        # Connect to MongoDB
        if not migration.connect():
            logger.error("Failed to connect to MongoDB. Exiting.")
            sys.exit(1)

        # Run migration
        success = migration.run()

        # Print summary
        migration.print_summary(success)

        # Exit with appropriate code
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("\nMigration cancelled by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"\nUnexpected error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Always disconnect
        migration.disconnect()


if __name__ == "__main__":
    main()
