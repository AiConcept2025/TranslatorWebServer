"""
JWT-based authentication service - NO DATABASE LOOKUPS NEEDED!

This replaces MongoDB session lookups with self-contained JWT tokens.
Token verification is INSTANT - no database queries.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)


class JWTService:
    """JWT token generation and verification service."""

    # Use a strong secret key from settings (no fallback - fail fast if not configured)
    SECRET_KEY = settings.secret_key  # Will raise AttributeError if not set
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS = 8  # Match session expiration

    def create_access_token(
        self,
        user_data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token with user data embedded.

        NO DATABASE STORAGE - Token is self-contained!

        Args:
            user_data: User information to embed in token
                {
                    "user_id": str,
                    "email": str,
                    "user_name": str,
                    "company_name": str,
                    "permission_level": str
                }
            expires_delta: Optional custom expiration time

        Returns:
            str: JWT token string
        """
        to_encode = user_data.copy()

        # Calculate expiration
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(hours=self.ACCESS_TOKEN_EXPIRE_HOURS)

        # Add standard JWT claims
        to_encode.update({
            "exp": expire,  # Expiration time
            "iat": datetime.now(timezone.utc),  # Issued at
            "sub": user_data["user_id"],  # Subject (user identifier)
            "type": "access_token"
        })

        # Create JWT token
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)

        logger.info(f"[JWT] Created access token for user: {user_data['email']}")
        logger.info(f"[JWT]   Expires: {expire.isoformat()}")
        logger.info(f"[JWT]   Token length: {len(encoded_jwt)} chars")

        return encoded_jwt

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify JWT token and extract user data.

        NO DATABASE LOOKUP - Token contains all user data!
        Verification is INSTANT.

        Args:
            token: JWT token string

        Returns:
            dict: User data if valid, None if invalid/expired
        """
        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.SECRET_KEY,
                algorithms=[self.ALGORITHM]
            )

            # Extract user data
            user_data = {
                "user_id": payload.get("user_id"),
                "email": payload.get("email"),
                "user_name": payload.get("user_name"),
                "company_name": payload.get("company_name"),
                "permission_level": payload.get("permission_level", "user")
            }

            # Verify all required fields are present
            if not all([user_data["user_id"], user_data["email"]]):
                logger.warning("[JWT] Token missing required fields")
                return None

            logger.info(f"[JWT] Token verified successfully for: {user_data['email']}")
            return user_data

        except JWTError as e:
            logger.warning(f"[JWT] Token verification failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"[JWT] Unexpected error during token verification: {str(e)}")
            return None

    def decode_token_without_verification(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode token WITHOUT verification (for debugging only).

        Args:
            token: JWT token string

        Returns:
            dict: Token payload if decodable, None otherwise
        """
        try:
            # Decode without verification
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
            return payload
        except Exception as e:
            logger.error(f"[JWT] Failed to decode token: {str(e)}")
            return None


# Global JWT service instance
jwt_service = JWTService()
