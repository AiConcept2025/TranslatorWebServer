"""
Authentication API endpoints with MongoDB integration.

Provides corporate login, logout, and session verification endpoints
with full MongoDB database authentication.
"""

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import logging

from app.services.auth_service import auth_service, AuthenticationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/login", tags=["Authentication"])


class CorporateLoginRequest(BaseModel):
    """Corporate login request model."""
    company_name: str = Field(..., alias='companyName', min_length=1)
    password: str = Field(..., min_length=6)
    user_full_name: str = Field(..., alias='userFullName', min_length=1)
    user_email: EmailStr = Field(..., alias='userEmail')
    login_date_time: str = Field(..., alias='loginDateTime')

    model_config = {
        'populate_by_name': True
    }


class CorporateLoginResponse(BaseModel):
    """Corporate login response model."""
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[dict] = None


@router.post("/corporate", response_model=CorporateLoginResponse)
async def corporate_login(request: CorporateLoginRequest):
    """
    Corporate login endpoint with MongoDB authentication.

    Authenticates against MongoDB users and companies collections.
    Returns session token stored in MongoDB sessions collection.

    Request body:
    ```json
    {
        "companyName": "Iris Trading",
        "password": "userpassword",
        "userFullName": "Vladimir Danishevsky",
        "userEmail": "danishevsky@gmail.com",
        "loginDateTime": "2025-10-13T10:30:00Z"
    }
    ```

    Response:
    ```json
    {
        "success": true,
        "message": "Corporate login successful",
        "data": {
            "authToken": "session-token-here",
            "tokenType": "Bearer",
            "expiresIn": 28800,
            "expiresAt": "2025-10-13T18:30:00Z",
            "user": {
                "user_id": "user_XXXXXXXX",
                "user_name": "Vladimir Danishevsky",
                "email": "danishevsky@gmail.com",
                "company_name": "Iris Trading",
                "permission_level": "admin"
            },
            "loginDateTime": "2025-10-13T10:30:00Z"
        }
    }
    ```
    """
    logger.info("=" * 80)
    logger.info(f"🔐 CORPORATE LOGIN REQUEST")
    logger.info("=" * 80)
    logger.info(f"  Company: {request.company_name}")
    logger.info(f"  Email: {request.user_email}")
    logger.info(f"  User: {request.user_full_name}")
    logger.info(f"  Login Time: {request.login_date_time}")
    logger.info("=" * 80)

    try:
        # Authenticate user via MongoDB
        auth_result = await auth_service.authenticate_user(
            company_name=request.company_name,
            password=request.password,
            user_name=request.user_full_name,
            email=request.user_email
        )

        # Prepare successful response
        response_content = {
            "success": True,
            "message": "Corporate login successful",
            "data": {
                "authToken": auth_result["session_token"],
                "tokenType": "Bearer",
                "expiresIn": 28800,  # 8 hours in seconds
                "expiresAt": auth_result["expires_at"],
                "user": auth_result["user"],
                "loginDateTime": request.login_date_time
            }
        }

        logger.info("=" * 80)
        logger.info("✅ LOGIN SUCCESSFUL")
        logger.info("=" * 80)
        logger.info(f"  User: {auth_result['user']['email']}")
        logger.info(f"  Company: {auth_result['user']['company_name']}")
        logger.info(f"  Token expires: {auth_result['expires_at']}")
        logger.info("=" * 80)

        return JSONResponse(content=response_content)

    except AuthenticationError as e:
        logger.warning("=" * 80)
        logger.warning(f"❌ AUTHENTICATION FAILED")
        logger.warning("=" * 80)
        logger.warning(f"  Reason: {str(e)}")
        logger.warning(f"  Company: {request.company_name}")
        logger.warning(f"  Email: {request.user_email}")
        logger.warning("=" * 80)

        error_response = {
            "success": False,
            "message": "Authentication failed",
            "error": {
                "code": "AUTH_FAILED",
                "message": str(e)
            }
        }

        raise HTTPException(status_code=401, detail=str(e))

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"💥 UNEXPECTED ERROR")
        logger.error("=" * 80)
        logger.error(f"  Error: {e}", exc_info=True)
        logger.error("=" * 80)

        error_response = {
            "success": False,
            "message": "Login processing failed",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred during login"
            }
        }

        raise HTTPException(status_code=500, detail="Login processing failed")


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Logout endpoint - invalidates session token.

    Expects: `Authorization: Bearer {token}` header

    Request:
    ```
    POST /login/logout
    Authorization: Bearer session-token-here
    ```

    Response:
    ```json
    {
        "success": true,
        "message": "Logged out successfully"
    }
    ```
    """
    logger.info("=" * 80)
    logger.info("🚪 LOGOUT REQUEST")
    logger.info("=" * 80)

    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("❌ Missing or invalid Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header. Expected: Authorization: Bearer {token}"
        )

    session_token = authorization.replace("Bearer ", "")
    logger.info(f"  Token: {session_token[:8]}...{session_token[-8:]}")

    try:
        success = await auth_service.invalidate_session(session_token)

        if success:
            logger.info("=" * 80)
            logger.info("✅ LOGOUT SUCCESSFUL")
            logger.info("=" * 80)
            return JSONResponse(content={
                "success": True,
                "message": "Logged out successfully"
            })
        else:
            logger.warning("=" * 80)
            logger.warning("❌ LOGOUT FAILED - Session not found")
            logger.warning("=" * 80)
            raise HTTPException(status_code=404, detail="Session not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"💥 LOGOUT ERROR: {e}", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail="Logout failed")


@router.get("/verify")
async def verify_session(authorization: Optional[str] = Header(None)):
    """
    Verify session token and return user data.

    Expects: `Authorization: Bearer {token}` header

    Request:
    ```
    GET /login/verify
    Authorization: Bearer session-token-here
    ```

    Response (success):
    ```json
    {
        "success": true,
        "valid": true,
        "user": {
            "user_id": "user_XXXXXXXX",
            "user_name": "Vladimir Danishevsky",
            "email": "danishevsky@gmail.com",
            "company_name": "Iris Trading",
            "permission_level": "admin"
        }
    }
    ```

    Response (failure):
    ```json
    {
        "success": false,
        "valid": false,
        "error": "Invalid or expired session"
    }
    ```
    """
    logger.info("=" * 80)
    logger.info("🔍 SESSION VERIFICATION REQUEST")
    logger.info("=" * 80)

    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("❌ Missing or invalid Authorization header")
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header. Expected: Authorization: Bearer {token}"
        )

    session_token = authorization.replace("Bearer ", "")
    logger.info(f"  Token: {session_token[:8]}...{session_token[-8:]}")

    try:
        user_data = await auth_service.verify_session(session_token)

        if user_data:
            logger.info("=" * 80)
            logger.info("✅ SESSION VALID")
            logger.info("=" * 80)
            logger.info(f"  User: {user_data['email']}")
            logger.info(f"  Company: {user_data['company_name']}")
            logger.info(f"  Permission: {user_data['permission_level']}")
            logger.info("=" * 80)

            return JSONResponse(content={
                "success": True,
                "valid": True,
                "user": user_data
            })
        else:
            logger.warning("=" * 80)
            logger.warning("❌ SESSION INVALID OR EXPIRED")
            logger.warning("=" * 80)
            raise HTTPException(status_code=401, detail="Invalid or expired session")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"💥 VERIFICATION ERROR: {e}", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail="Verification failed")
