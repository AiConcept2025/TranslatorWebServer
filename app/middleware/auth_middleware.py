"""
Authentication middleware for protecting routes.

Provides FastAPI dependencies to extract and verify session tokens
from Authorization headers for route protection.
"""

from fastapi import Header, HTTPException, Depends
from typing import Optional, Dict, Any
import logging

from app.services.auth_service import auth_service

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    # DEBUG: Print immediately when dependency is invoked
    print("🟢 DEBUG: get_current_user() INVOKED - FastAPI dependency system working")
    print(f"🟢 DEBUG: Authorization header present: {bool(authorization)}")
    """
    Dependency to extract and verify session token from Authorization header.

    This dependency enforces authentication and returns the current user data.
    If authentication fails, it raises a 401 HTTPException.

    Usage:
        ```python
        from app.middleware.auth_middleware import get_current_user

        @router.get("/protected")
        async def protected_route(current_user: dict = Depends(get_current_user)):
            return {
                "message": f"Hello {current_user['user_name']}",
                "user": current_user
            }
        ```

    Args:
        authorization: Authorization header value (e.g., "Bearer {token}")

    Returns:
        dict: User data with keys: user_id, user_name, email, company_name, permission_level

    Raises:
        HTTPException: 401 if authentication fails or token is invalid/missing
    """
    import time
    start_time = time.time()

    def log_timing(step: str):
        elapsed = time.time() - start_time
        msg = f"[AUTH MIDDLEWARE {elapsed:6.2f}s] {step}"
        logger.info(msg)
        print(msg)

    log_timing("START - get_current_user called")
    log_timing(f"AUTH HEADER: {authorization[:50] if authorization else 'NONE'}...")

    if not authorization:
        log_timing("FAILED - No authorization header")
        logger.warning("[AUTH MIDDLEWARE] Authorization header missing")
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not authorization.startswith("Bearer "):
        log_timing(f"FAILED - Invalid format: {authorization[:20]}")
        logger.warning(f"[AUTH MIDDLEWARE] Invalid authorization header format: {authorization[:20]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected: Bearer {token}",
            headers={"WWW-Authenticate": "Bearer"}
        )

    session_token = authorization.replace("Bearer ", "")
    log_timing(f"TOKEN EXTRACTED: {session_token[:8]}...{session_token[-8:]}")
    logger.info(f"[AUTH MIDDLEWARE] Verifying token: {session_token[:8]}...{session_token[-8:]}")

    # Verify session with auth service
    log_timing("CALLING auth_service.verify_session...")
    user_data = await auth_service.verify_session(session_token)
    log_timing("RETURNED from auth_service.verify_session")

    if not user_data:
        log_timing("FAILED - Session verification failed")
        logger.warning("[AUTH MIDDLEWARE] Session verification failed - invalid or expired token")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"}
        )

    log_timing(f"SUCCESS - User authenticated: {user_data.get('email')}")
    logger.info(f"[AUTH MIDDLEWARE] Authentication successful - User: {user_data['email']}")

    return user_data


async def get_optional_user(
    authorization: Optional[str] = Header(None)
) -> Optional[Dict[str, Any]]:
    """
    Optional authentication dependency.

    Returns user data if authenticated, None otherwise.
    Does not raise exceptions for missing/invalid tokens.

    Usage:
        ```python
        from app.middleware.auth_middleware import get_optional_user

        @router.get("/optional-auth")
        async def optional_auth_route(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user['user_name']}", "authenticated": True}
            else:
                return {"message": "Hello guest", "authenticated": False}
        ```

    Args:
        authorization: Authorization header value (e.g., "Bearer {token}")

    Returns:
        dict: User data if authenticated, None otherwise
    """
    if not authorization or not authorization.startswith("Bearer "):
        logger.debug("[AUTH MIDDLEWARE] No valid authorization header for optional auth")
        return None

    session_token = authorization.replace("Bearer ", "")
    logger.info(f"[AUTH MIDDLEWARE] Optional auth - verifying token: {session_token[:8]}...{session_token[-8:]}")

    # Verify session with auth service
    user_data = await auth_service.verify_session(session_token)

    if user_data:
        logger.info(f"[AUTH MIDDLEWARE] Optional auth successful - User: {user_data['email']}")
    else:
        logger.debug("[AUTH MIDDLEWARE] Optional auth - token invalid or expired")

    return user_data


async def get_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Dependency to enforce admin-level permissions.

    Requires authentication AND admin permission level.

    Usage:
        ```python
        from app.middleware.auth_middleware import get_admin_user

        @router.post("/admin/settings")
        async def admin_only_route(admin_user: dict = Depends(get_admin_user)):
            return {
                "message": "Admin access granted",
                "user": admin_user
            }
        ```

    Args:
        current_user: User data from get_current_user dependency

    Returns:
        dict: User data (only if user is admin)

    Raises:
        HTTPException: 403 if user does not have admin permissions
    """
    permission_level = current_user.get("permission_level", "user")

    if permission_level != "admin":
        logger.warning(
            f"[AUTH MIDDLEWARE] Admin access denied - "
            f"User: {current_user['email']}, Permission: {permission_level}"
        )
        raise HTTPException(
            status_code=403,
            detail="Admin permissions required"
        )

    logger.info(f"[AUTH MIDDLEWARE] Admin access granted - User: {current_user['email']}")

    return current_user


# Example of custom permission check
def require_permission(required_permission: str):
    """
    Factory function to create custom permission dependencies.

    Usage:
        ```python
        from app.middleware.auth_middleware import require_permission

        @router.delete("/translations/{translation_id}")
        async def delete_translation(
            translation_id: str,
            user: dict = Depends(require_permission("admin"))
        ):
            return {"message": "Translation deleted"}
        ```

    Args:
        required_permission: Permission level required (e.g., "admin", "user")

    Returns:
        Dependency function that checks for the required permission
    """
    async def permission_checker(
        current_user: Dict[str, Any] = Depends(get_current_user)
    ) -> Dict[str, Any]:
        permission_level = current_user.get("permission_level", "user")

        if permission_level != required_permission:
            logger.warning(
                f"[AUTH MIDDLEWARE] Permission denied - "
                f"Required: {required_permission}, User has: {permission_level}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{required_permission}' required"
            )

        logger.info(
            f"[AUTH MIDDLEWARE] Permission check passed - "
            f"User: {current_user['email']}, Permission: {permission_level}"
        )

        return current_user

    return permission_checker
