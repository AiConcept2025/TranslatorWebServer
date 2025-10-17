"""
Authentication service with MongoDB and passlib.

Handles user authentication, session management, and password verification
for enterprise users with company validation.
"""

import logging
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from bson import ObjectId

from app.database.mongodb import database
from app.config import settings

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Base authentication error."""
    pass


class AuthService:
    """Authentication service for enterprise users."""

    SESSION_EXPIRATION_HOURS = 8

    async def authenticate_user(
        self,
        company_name: str,
        password: str,
        user_name: str,
        email: str
    ) -> Dict[str, Any]:
        """
        Authenticate user with company validation and password verification.

        Args:
            company_name: Company name to authenticate against
            password: User password (plain text)
            user_name: Full name of the user
            email: User email address

        Returns:
            dict: {session_token, user_data, expires_at}

        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("=" * 80)
        logger.info(f"[AUTH] {datetime.now(timezone.utc).isoformat()} - Login attempt")
        logger.info(f"[AUTH] Company: {company_name}")
        logger.info(f"[AUTH] Email: {email}")
        logger.info(f"[AUTH] User Name: {user_name}")
        logger.info("=" * 80)

        # Check database connection
        if not database.is_connected:
            logger.error("[AUTH] FAILED - MongoDB not connected")
            raise AuthenticationError("Service temporarily unavailable")

        # Step 1: Find company by company_name
        logger.info(f"[AUTH] Step 1: Looking up company '{company_name}'...")
        company = await database.companies.find_one({"company_name": company_name})
        if not company:
            logger.warning(f"[AUTH] FAILED - Company not found: {company_name}")
            raise AuthenticationError("Invalid credentials")

        company_id = company["_id"]
        logger.info(f"[AUTH] SUCCESS - Company found")
        logger.info(f"[AUTH]   Company ID: {company_id}")
        logger.info(f"[AUTH]   Company Name: {company.get('company_name')}")

        # Step 2: Find user by email, company_id, and user_name
        logger.info(f"[AUTH] Step 2: Looking up user in database...")
        logger.info(f"[AUTH]   Searching with:")
        logger.info(f"[AUTH]     - email: {email}")
        logger.info(f"[AUTH]     - company_id: {company_id}")
        logger.info(f"[AUTH]     - user_name: {user_name}")

        # Try 'users' collection first
        user = await database.users.find_one({
            "email": email,
            "company_id": company_id,
            "user_name": user_name
        })

        collection_used = "users"

        # Fallback to 'company_users' collection if users collection doesn't have the user
        if not user and database.db is not None:
            logger.info(f"[AUTH]   User not found in 'users' collection, trying 'company_users'...")
            user = await database.db.company_users.find_one({
                "email": email,
                "company_id": company_id,
                "user_name": user_name
            })
            collection_used = "company_users"

        if not user:
            logger.warning(f"[AUTH] FAILED - User not found")
            logger.warning(f"[AUTH]   Email: {email}")
            logger.warning(f"[AUTH]   User Name: {user_name}")
            logger.warning(f"[AUTH]   Company ID: {company_id}")
            raise AuthenticationError("Invalid credentials")

        logger.info(f"[AUTH] SUCCESS - User found in '{collection_used}' collection")
        logger.info(f"[AUTH]   User ID: {user.get('user_id')}")
        logger.info(f"[AUTH]   User Name: {user.get('user_name')}")
        logger.info(f"[AUTH]   Email: {user.get('email')}")
        logger.info(f"[AUTH]   Status: {user.get('status')}")
        logger.info(f"[AUTH]   Permission Level: {user.get('permission_level')}")

        # Step 3: Check user status
        logger.info(f"[AUTH] Step 3: Checking user status...")
        if user.get("status") != "active":
            logger.warning(f"[AUTH] FAILED - User account is not active")
            logger.warning(f"[AUTH]   Current status: {user.get('status')}")
            raise AuthenticationError("User account is not active")

        logger.info(f"[AUTH] SUCCESS - User status is active")

        # Step 4: Verify password with bcrypt
        logger.info(f"[AUTH] Step 4: Verifying password...")
        password_hash = user.get("password_hash")
        if not password_hash:
            logger.error(f"[AUTH] FAILED - No password hash found for user")
            raise AuthenticationError("Invalid credentials")

        try:
            # Verify password with bcrypt - run in thread pool to avoid blocking event loop
            # IMPORTANT: bcrypt has a 72-byte limit, so we truncate if needed
            import asyncio
            from functools import partial

            password_bytes = password.encode('utf-8')[:72]  # Truncate to 72 bytes (bcrypt limit)

            loop = asyncio.get_event_loop()
            password_valid = await loop.run_in_executor(
                None,  # Use default ThreadPoolExecutor
                partial(
                    bcrypt.checkpw,
                    password_bytes,
                    password_hash.encode('utf-8')
                )
            )
            logger.info(f"[AUTH] Password verification completed (non-blocking)")
        except Exception as e:
            logger.error(f"[AUTH] FAILED - Error verifying password: {e}")
            raise AuthenticationError("Invalid credentials")

        if not password_valid:
            logger.warning(f"[AUTH] FAILED - Password verification failed")
            raise AuthenticationError("Invalid credentials")

        logger.info(f"[AUTH] SUCCESS - Password verified with bcrypt")

        # Step 5: Create JWT token (NO DATABASE STORAGE - self-contained!)
        logger.info(f"[AUTH] Step 5: Creating JWT access token...")
        from app.services.jwt_service import jwt_service
        from datetime import timedelta

        user_token_data = {
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "user_name": user.get("user_name"),
            "company_id": str(company_id),
            "company_name": company_name,
            "permission_level": user.get("permission_level", "user")
        }

        # Create JWT token with 8-hour expiration
        expires_delta = timedelta(hours=self.SESSION_EXPIRATION_HOURS)
        access_token = jwt_service.create_access_token(user_token_data, expires_delta)

        expires_at = datetime.now(timezone.utc) + expires_delta

        logger.info(f"[AUTH] SUCCESS - JWT token created")
        logger.info(f"[AUTH]   Token type: JWT (self-contained, NO database lookup needed)")
        logger.info(f"[AUTH]   Token: {access_token[:16]}...{access_token[-8:]}")
        logger.info(f"[AUTH]   Expires: {expires_at.isoformat()}")

        # Step 6: Update last_login
        logger.info(f"[AUTH] Step 6: Updating last_login timestamp...")
        now = datetime.now(timezone.utc)

        # Update in the correct collection
        if collection_used == "users":
            await database.users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "last_login": now,
                        "updated_at": now
                    }
                }
            )
        else:
            await database.db.company_users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "last_login": now,
                        "updated_at": now
                    }
                }
            )

        logger.info(f"[AUTH] SUCCESS - Last login updated to {now.isoformat()}")

        # Prepare user data response (exclude sensitive fields)
        user_data = {
            "user_id": user.get("user_id"),
            "user_name": user.get("user_name"),
            "email": user.get("email"),
            "company_name": company_name,
            "permission_level": user.get("permission_level", "user")
        }

        logger.info("=" * 80)
        logger.info(f"[AUTH] AUTHENTICATION SUCCESSFUL")
        logger.info(f"[AUTH] User: {email}")
        logger.info(f"[AUTH] Company: {company_name}")
        logger.info(f"[AUTH] Token expires: {expires_at.isoformat()}")
        logger.info(f"[AUTH] Token type: JWT (NO database queries on subsequent requests!)")
        logger.info("=" * 80)

        return {
            "session_token": access_token,  # JWT token
            "user": user_token_data,
            "expires_at": expires_at.isoformat()
        }

    async def create_session(
        self,
        user_object_id: ObjectId,
        company_id: ObjectId,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Create secure session and store in MongoDB.

        Args:
            user_object_id: MongoDB ObjectId of the user
            company_id: MongoDB ObjectId of the company
            user_id: User's string ID

        Returns:
            dict: {session_token, expires_at}
        """
        # Generate cryptographically secure token (32 bytes = 43 characters base64)
        session_token = secrets.token_urlsafe(32)

        # Calculate expiration
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(hours=self.SESSION_EXPIRATION_HOURS)

        # Create session document
        session_doc = {
            "session_token": session_token,
            "user_id": user_id,
            "user_object_id": user_object_id,
            "company_id": company_id,
            "created_at": created_at,
            "expires_at": expires_at,
            "is_active": True
        }

        # Store in MongoDB sessions collection
        await database.sessions.insert_one(session_doc)

        logger.info(f"[AUTH] Session document created in MongoDB")
        logger.info(f"[AUTH]   Session token: {session_token[:8]}...{session_token[-8:]}")
        logger.info(f"[AUTH]   User ID: {user_id}")
        logger.info(f"[AUTH]   Created: {created_at.isoformat()}")
        logger.info(f"[AUTH]   Expires: {expires_at.isoformat()}")
        logger.info(f"[AUTH]   Duration: {self.SESSION_EXPIRATION_HOURS} hours")

        return {
            "session_token": session_token,
            "expires_at": expires_at.isoformat()
        }

    async def verify_session(self, session_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and return user data if valid.

        NO DATABASE QUERIES - Token is self-contained!
        Verification is INSTANT.

        Args:
            session_token: The JWT token to verify

        Returns:
            dict: User data if valid, None otherwise
        """
        logger.info(f"[AUTH] Verifying JWT token: {session_token[:8]}...{session_token[-8:]}")

        # Verify JWT token (NO DATABASE LOOKUP!)
        from app.services.jwt_service import jwt_service

        user_data = jwt_service.verify_token(session_token)

        if not user_data:
            logger.warning(f"[AUTH] JWT token verification failed (invalid or expired)")
            return None

        logger.info(f"[AUTH] JWT token verified successfully - NO DATABASE QUERIES!")
        logger.info(f"[AUTH]   User: {user_data.get('email')}")
        logger.info(f"[AUTH]   Company: {user_data.get('company_name')}")
        logger.info(f"[AUTH]   Permission: {user_data.get('permission_level')}")

        return user_data

    async def invalidate_session(self, session_token: str) -> bool:
        """
        Invalidate (logout) a session.

        Args:
            session_token: The session token to invalidate

        Returns:
            bool: True if session was invalidated, False otherwise
        """
        logger.info(f"[AUTH] Invalidating session: {session_token[:8]}...{session_token[-8:]}")

        result = await database.sessions.update_one(
            {"session_token": session_token},
            {"$set": {"is_active": False}}
        )

        if result.modified_count > 0:
            logger.info(f"[AUTH] Session invalidated successfully")
            logger.info(f"[AUTH]   Documents modified: {result.modified_count}")
            return True

        logger.warning(f"[AUTH] Session not found for invalidation")
        logger.warning(f"[AUTH]   Token: {session_token[:8]}...{session_token[-8:]}")
        return False

    async def authenticate_individual_user(
        self,
        user_name: str,
        email: str
    ) -> Dict[str, Any]:
        """
        Authenticate individual user (no company, no password).
        Creates user if doesn't exist.

        Args:
            user_name: Full name of the user
            email: User email address

        Returns:
            dict: {session_token, user_data, expires_at}

        Raises:
            AuthenticationError: If authentication fails
        """
        logger.info("=" * 80)
        logger.info(f"[AUTH INDIVIDUAL] {datetime.now(timezone.utc).isoformat()} - Individual login attempt")
        logger.info(f"[AUTH INDIVIDUAL] Email: {email}")
        logger.info(f"[AUTH INDIVIDUAL] User Name: {user_name}")
        logger.info("=" * 80)

        # Check database connection
        if not database.is_connected:
            logger.error("[AUTH INDIVIDUAL] FAILED - MongoDB not connected")
            raise AuthenticationError("Service temporarily unavailable")

        # Step 1: Find or create individual user
        logger.info(f"[AUTH INDIVIDUAL] Step 1: Looking up individual user by email...")
        user = await database.users.find_one({
            "email": email,
            "company_id": None  # Individual users have no company
        })

        if user:
            logger.info(f"[AUTH INDIVIDUAL] SUCCESS - Existing user found")
            logger.info(f"[AUTH INDIVIDUAL]   User ID: {user.get('user_id')}")
            logger.info(f"[AUTH INDIVIDUAL]   User Name: {user.get('user_name')}")
            logger.info(f"[AUTH INDIVIDUAL]   Email: {user.get('email')}")
            logger.info(f"[AUTH INDIVIDUAL]   Status: {user.get('status')}")

            # Update user name if changed
            if user.get('user_name') != user_name:
                logger.info(f"[AUTH INDIVIDUAL] Updating user name: {user.get('user_name')} -> {user_name}")
                now = datetime.now(timezone.utc)
                await database.users.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "user_name": user_name,
                            "last_login": now,
                            "updated_at": now
                        }
                    }
                )
                user["user_name"] = user_name
            else:
                # Just update last_login
                now = datetime.now(timezone.utc)
                await database.users.update_one(
                    {"_id": user["_id"]},
                    {
                        "$set": {
                            "last_login": now,
                            "updated_at": now
                        }
                    }
                )
        else:
            # Create new individual user
            logger.info(f"[AUTH INDIVIDUAL] User not found - Creating new individual user...")
            import uuid
            now = datetime.now(timezone.utc)
            user_id = f"user_{uuid.uuid4().hex[:16]}"

            user_doc = {
                "user_id": user_id,
                "user_name": user_name,
                "email": email,
                "company_id": None,  # No company for individual users
                "permission_level": "user",  # Individual users are regular users
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "last_login": now
            }

            result = await database.users.insert_one(user_doc)
            user_doc["_id"] = result.inserted_id
            user = user_doc

            logger.info(f"[AUTH INDIVIDUAL] SUCCESS - New user created")
            logger.info(f"[AUTH INDIVIDUAL]   User ID: {user_id}")
            logger.info(f"[AUTH INDIVIDUAL]   Email: {email}")
            logger.info(f"[AUTH INDIVIDUAL]   Status: active")

        # Step 2: Check user status
        logger.info(f"[AUTH INDIVIDUAL] Step 2: Checking user status...")
        if user.get("status") != "active":
            logger.warning(f"[AUTH INDIVIDUAL] FAILED - User account is not active")
            logger.warning(f"[AUTH INDIVIDUAL]   Current status: {user.get('status')}")
            raise AuthenticationError("User account is not active")

        logger.info(f"[AUTH INDIVIDUAL] SUCCESS - User status is active")

        # Step 3: Create JWT token (NO DATABASE STORAGE - self-contained!)
        logger.info(f"[AUTH INDIVIDUAL] Step 3: Creating JWT access token...")
        from app.services.jwt_service import jwt_service
        from datetime import timedelta

        user_token_data = {
            "user_id": user.get("user_id"),
            "email": user.get("email"),
            "user_name": user.get("user_name"),
            "company_id": None,  # No company for individual users
            "company_name": None,  # No company for individual users
            "permission_level": "user"  # Individual users are regular users
        }

        # Create JWT token with 8-hour expiration
        expires_delta = timedelta(hours=self.SESSION_EXPIRATION_HOURS)
        access_token = jwt_service.create_access_token(user_token_data, expires_delta)

        expires_at = datetime.now(timezone.utc) + expires_delta

        logger.info(f"[AUTH INDIVIDUAL] SUCCESS - JWT token created")
        logger.info(f"[AUTH INDIVIDUAL]   Token type: JWT (self-contained, NO database lookup needed)")
        logger.info(f"[AUTH INDIVIDUAL]   Token: {access_token[:16]}...{access_token[-8:]}")
        logger.info(f"[AUTH INDIVIDUAL]   Expires: {expires_at.isoformat()}")

        # Prepare user data response (exclude sensitive fields)
        user_data = {
            "user_id": user.get("user_id"),
            "user_name": user.get("user_name"),
            "email": user.get("email"),
            "company_name": None,  # Individual users have no company
            "permission_level": "user"
        }

        logger.info("=" * 80)
        logger.info(f"[AUTH INDIVIDUAL] AUTHENTICATION SUCCESSFUL")
        logger.info(f"[AUTH INDIVIDUAL] User: {email}")
        logger.info(f"[AUTH INDIVIDUAL] User Type: Individual (no company)")
        logger.info(f"[AUTH INDIVIDUAL] Token expires: {expires_at.isoformat()}")
        logger.info(f"[AUTH INDIVIDUAL] Token type: JWT (NO database queries on subsequent requests!)")
        logger.info("=" * 80)

        return {
            "session_token": access_token,  # JWT token
            "user": user_token_data,
            "expires_at": expires_at.isoformat()
        }


# Global auth service instance
auth_service = AuthService()
