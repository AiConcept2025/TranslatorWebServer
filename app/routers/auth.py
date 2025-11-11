"""
Authentication API endpoints with MongoDB integration.

Provides corporate login, logout, and session verification endpoints
with full MongoDB database authentication.

Also provides simple user signup and login endpoints for users_login collection.
"""

from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import logging
import bcrypt
import asyncio
from functools import partial
from datetime import datetime, timezone

from app.services.auth_service import auth_service, AuthenticationError
from app.models.auth_models import (
    UserSignupRequest,
    UserSignupResponse,
    UserLoginRequest,
    UserLoginResponse,
    AdminLoginRequest,
    AdminLoginResponse
)
from app.database.mongodb import database

# Import slowapi for rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/login", tags=["Authentication"])

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


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


class IndividualLoginRequest(BaseModel):
    """Individual login request model (no company, no password)."""
    user_full_name: str = Field(..., alias='userFullName', min_length=1)
    user_email: EmailStr = Field(..., alias='userEmail')
    login_date_time: str = Field(..., alias='loginDateTime')

    model_config = {
        'populate_by_name': True
    }


class IndividualLoginResponse(BaseModel):
    """Individual login response model."""
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[dict] = None


@router.post("/admin", response_model=AdminLoginResponse)
@limiter.limit("10/5minutes")  # Brute force protection: 10 attempts per 5 minutes
async def admin_login(req: AdminLoginRequest, request: Request):
    """
    Admin login endpoint with MongoDB authentication.

    Authenticates against iris-admins collection with email + password.
    Returns JWT token with permission_level="admin".

    Request body:
    ```json
    {
        "email": "admin@example.com",
        "password": "adminpassword"
    }
    ```

    Response:
    ```json
    {
        "success": true,
        "message": "Admin login successful",
        "data": {
            "authToken": "jwt-token-here",
            "tokenType": "Bearer",
            "expiresIn": 28800,
            "expiresAt": "2025-10-15T18:30:00Z",
            "user": {
                "user_id": "admin_XXXXXXXX",
                "user_name": "Admin Name",
                "email": "admin@example.com",
                "permission_level": "admin"
            }
        }
    }
    ```
    """
    logger.info("=" * 80)
    logger.info(f"🔑 ADMIN LOGIN REQUEST")
    logger.info("=" * 80)
    logger.info(f"  Email: {req.email}")
    logger.info("=" * 80)

    try:
        # Authenticate admin user via MongoDB iris-admins collection
        auth_result = await auth_service.authenticate_admin(
            email=req.email,
            password=req.password
        )

        # Prepare successful response
        response_content = {
            "success": True,
            "message": "Admin login successful",
            "data": {
                "authToken": auth_result["session_token"],
                "tokenType": "Bearer",
                "expiresIn": 28800,  # 8 hours in seconds
                "expiresAt": auth_result["expires_at"],
                "user": auth_result["user"]
            }
        }

        logger.info("=" * 80)
        logger.info("✅ ADMIN LOGIN SUCCESSFUL")
        logger.info("=" * 80)
        logger.info(f"  Admin: {auth_result['user']['email']}")
        logger.info(f"  Permission: {auth_result['user']['permission_level']}")
        logger.info(f"  Token expires: {auth_result['expires_at']}")
        logger.info("=" * 80)

        return JSONResponse(content=response_content)

    except AuthenticationError as e:
        logger.warning("=" * 80)
        logger.warning(f"❌ ADMIN AUTHENTICATION FAILED")
        logger.warning("=" * 80)
        logger.warning(f"  Reason: {str(e)}")
        logger.warning(f"  Email: {req.email}")
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
        logger.error(f"💥 ADMIN LOGIN UNEXPECTED ERROR")
        logger.error("=" * 80)
        logger.error(f"  Error: {e}", exc_info=True)
        logger.error("=" * 80)

        error_response = {
            "success": False,
            "message": "Login processing failed",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred during admin login"
            }
        }

        raise HTTPException(status_code=500, detail="Admin login processing failed")


@router.post("/individual", response_model=IndividualLoginResponse)
async def individual_login(request: IndividualLoginRequest):
    """
    Individual user login endpoint (no company, no password).

    Creates user if doesn't exist. Returns JWT token.

    Request body:
    ```json
    {
        "userFullName": "John Doe",
        "userEmail": "john@example.com",
        "loginDateTime": "2025-10-15T10:30:00Z"
    }
    ```

    Response:
    ```json
    {
        "success": true,
        "message": "Individual login successful",
        "data": {
            "authToken": "jwt-token-here",
            "tokenType": "Bearer",
            "expiresIn": 28800,
            "expiresAt": "2025-10-15T18:30:00Z",
            "user": {
                "user_id": "user_XXXXXXXX",
                "user_name": "John Doe",
                "email": "john@example.com",
                "company_name": null,
                "permission_level": "user"
            },
            "loginDateTime": "2025-10-15T10:30:00Z"
        }
    }
    ```
    """
    logger.info("=" * 80)
    logger.info(f"👤 INDIVIDUAL LOGIN REQUEST")
    logger.info("=" * 80)
    logger.info(f"  Email: {request.user_email}")
    logger.info(f"  User: {request.user_full_name}")
    logger.info(f"  Login Time: {request.login_date_time}")
    logger.info("=" * 80)

    try:
        # Authenticate individual user via MongoDB (creates if doesn't exist)
        auth_result = await auth_service.authenticate_individual_user(
            user_name=request.user_full_name,
            email=request.user_email
        )

        # Prepare successful response
        response_content = {
            "success": True,
            "message": "Individual login successful",
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
        logger.info("✅ INDIVIDUAL LOGIN SUCCESSFUL")
        logger.info("=" * 80)
        logger.info(f"  User: {auth_result['user']['email']}")
        logger.info(f"  User Type: Individual (no company)")
        logger.info(f"  Token expires: {auth_result['expires_at']}")
        logger.info("=" * 80)

        return JSONResponse(content=response_content)

    except AuthenticationError as e:
        logger.warning("=" * 80)
        logger.warning(f"❌ AUTHENTICATION FAILED")
        logger.warning("=" * 80)
        logger.warning(f"  Reason: {str(e)}")
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


@router.post("/corporate", response_model=CorporateLoginResponse)
@limiter.limit("20/5minutes")  # Brute force protection: 20 attempts per 5 minutes
async def corporate_login(req: CorporateLoginRequest, request: Request):
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
    logger.info(f"  Company: {req.company_name}")
    logger.info(f"  Email: {req.user_email}")
    logger.info(f"  User: {req.user_full_name}")
    logger.info(f"  Login Time: {req.login_date_time}")
    logger.info("=" * 80)

    try:
        # Authenticate user via MongoDB
        auth_result = await auth_service.authenticate_user(
            company_name=req.company_name,
            password=req.password,
            user_name=req.user_full_name,
            email=req.user_email
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
                "loginDateTime": req.login_date_time
            }
        }

        logger.info("=" * 80)
        logger.info("✅ LOGIN SUCCESSFUL")
        logger.info("=" * 80)
        logger.info(f"  User: {auth_result['user']['email']}")
        logger.info(f"  Company: {auth_result['user']['company']}")
        logger.info(f"  Token expires: {auth_result['expires_at']}")
        logger.info("=" * 80)

        return JSONResponse(content=response_content)

    except AuthenticationError as e:
        logger.warning("=" * 80)
        logger.warning(f"❌ AUTHENTICATION FAILED")
        logger.warning("=" * 80)
        logger.warning(f"  Reason: {str(e)}")
        logger.warning(f"  Company: {req.company_name}")
        logger.warning(f"  Email: {req.user_email}")
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


# ============================================================================
# Simple User Authentication Endpoints (users_login collection)
# ============================================================================

@router.post("/api/auth/signup", response_model=UserSignupResponse, tags=["User Auth"])
async def user_signup(request: UserSignupRequest):
    """
    Create new user account in users_login collection.

    **Request Body:**
    ```json
    {
        "user_name": "John Doe",
        "user_email": "john@example.com",
        "password": "SecurePass123"
    }
    ```

    **Response (201 Created):**
    ```json
    {
        "success": true,
        "message": "User created successfully",
        "user": {
            "user_name": "John Doe",
            "user_email": "john@example.com"
        }
    }
    ```

    **Error Responses:**
    - 400: Email/username already exists, validation errors
    - 500: Server error
    """
    logger.info("=" * 80)
    logger.info(f"🆕 USER SIGNUP REQUEST")
    logger.info("=" * 80)
    logger.info(f"  Email: {request.user_email}")
    logger.info(f"  Username: {request.user_name}")
    logger.info("=" * 80)

    try:
        # Check database connection
        if not database.is_connected:
            logger.error("[SIGNUP] MongoDB not connected")
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Check if user already exists (by email or username)
        logger.info(f"[SIGNUP] Checking if user exists...")
        existing_user_email = await database.users_login.find_one({"user_email": request.user_email})
        if existing_user_email:
            logger.warning(f"[SIGNUP] User with email {request.user_email} already exists")
            raise HTTPException(status_code=400, detail="Email already registered")

        existing_user_name = await database.users_login.find_one({"user_name": request.user_name})
        if existing_user_name:
            logger.warning(f"[SIGNUP] User with username {request.user_name} already exists")
            raise HTTPException(status_code=400, detail="Username already taken")

        # Hash password with bcrypt (12 rounds)
        logger.info(f"[SIGNUP] Hashing password with bcrypt (12 rounds)...")
        password_bytes = request.password.encode('utf-8')[:72]  # bcrypt limit is 72 bytes

        # Run bcrypt in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        salt = await loop.run_in_executor(None, bcrypt.gensalt, 12)
        password_hash = await loop.run_in_executor(
            None,
            partial(bcrypt.hashpw, password_bytes, salt)
        )
        password_hash_str = password_hash.decode('utf-8')
        logger.info(f"[SIGNUP] Password hashed successfully")

        # Create user document
        now = datetime.now(timezone.utc)
        user_doc = {
            "user_name": request.user_name,
            "user_email": request.user_email,
            "password": password_hash_str,  # Store hashed password
            "created_at": now,
            "updated_at": now,
            "last_login": None  # Will be set on first login
        }

        # Insert into database
        logger.info(f"[SIGNUP] Inserting user into users_login collection...")
        result = await database.users_login.insert_one(user_doc)
        logger.info(f"[SIGNUP] User created with ID: {result.inserted_id}")

        # Prepare response with data structure matching frontend expectations (exclude password)
        response_data = {
            "success": True,
            "message": "User created successfully",
            "data": {
                "user_id": str(result.inserted_id),
                "user_name": request.user_name,
                "user_email": request.user_email,
                "created_at": now.isoformat()
            }
        }

        logger.info("=" * 80)
        logger.info("✅ USER SIGNUP SUCCESSFUL")
        logger.info("=" * 80)
        logger.info(f"  Email: {request.user_email}")
        logger.info(f"  Username: {request.user_name}")
        logger.info(f"  User ID: {str(result.inserted_id)}")
        logger.info("=" * 80)

        return JSONResponse(content=response_data, status_code=201)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"💥 SIGNUP ERROR: {e}", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")


@router.post("/api/auth/login", response_model=UserLoginResponse, tags=["User Auth"])
async def user_login(request: UserLoginRequest):
    """
    Authenticate user from users_login collection.

    **Request Body:**
    ```json
    {
        "email": "john@example.com",
        "password": "SecurePass123"
    }
    ```

    **Response (200 OK):**
    ```json
    {
        "success": true,
        "message": "Login successful",
        "user": {
            "user_name": "John Doe",
            "user_email": "john@example.com",
            "last_login": "2025-10-18T12:00:00Z"
        }
    }
    ```

    **Error Responses:**
    - 401: Invalid credentials
    - 500: Server error
    """
    logger.info("=" * 80)
    logger.info(f"🔐 USER LOGIN REQUEST")
    logger.info("=" * 80)
    logger.info(f"  Email: {request.email}")
    logger.info("=" * 80)

    try:
        # Check database connection
        if not database.is_connected:
            logger.error("[LOGIN] MongoDB not connected")
            raise HTTPException(status_code=500, detail="Service temporarily unavailable")

        # Find user by email
        logger.info(f"[LOGIN] Looking up user by email...")
        user = await database.users_login.find_one({"user_email": request.email})

        if not user:
            logger.warning(f"[LOGIN] User not found: {request.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        logger.info(f"[LOGIN] User found: {user.get('user_name')}")

        # Verify password with bcrypt
        logger.info(f"[LOGIN] Verifying password...")
        password_hash = user.get("password")
        if not password_hash:
            logger.error(f"[LOGIN] No password hash found for user")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        try:
            # Run bcrypt verification in thread pool
            password_bytes = request.password.encode('utf-8')[:72]
            loop = asyncio.get_event_loop()
            password_valid = await loop.run_in_executor(
                None,
                partial(bcrypt.checkpw, password_bytes, password_hash.encode('utf-8'))
            )
            logger.info(f"[LOGIN] Password verification completed")
        except Exception as e:
            logger.error(f"[LOGIN] Password verification error: {e}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not password_valid:
            logger.warning(f"[LOGIN] Invalid password for user: {request.email}")
            raise HTTPException(status_code=401, detail="Invalid credentials")

        logger.info(f"[LOGIN] Password verified successfully")

        # Update last_login timestamp
        now = datetime.now(timezone.utc)
        logger.info(f"[LOGIN] Updating last_login timestamp...")
        await database.users_login.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": now, "updated_at": now}}
        )
        logger.info(f"[LOGIN] Last login updated")

        # Generate JWT token (matches other login endpoints - corporate/individual/admin)
        logger.info(f"[LOGIN] Creating JWT access token...")
        from app.services.jwt_service import jwt_service
        from datetime import timedelta

        # Create user data for JWT (self-contained token, no database storage)
        user_token_data = {
            "user_id": str(user["_id"]),
            "email": user.get("user_email"),
            "fullName": user.get("user_name"),  # Frontend expects this
            "company_name": None,  # Individual users have no company
            "permission_level": "user"
        }

        # Create JWT token with 8-hour expiration
        expires_delta = timedelta(hours=8)
        session_token = jwt_service.create_access_token(user_token_data, expires_delta)

        expires_at = now + expires_delta
        expires_in = 28800  # 8 hours in seconds

        logger.info(f"[LOGIN] JWT token created successfully")
        logger.info(f"[LOGIN]   Token type: JWT (self-contained, stateless)")
        logger.info(f"[LOGIN]   Token preview: {session_token[:16]}...{session_token[-8:]}")

        # Prepare response with data structure matching frontend expectations
        response_data = {
            "success": True,
            "message": "Login successful",
            "data": {
                "user_id": str(user["_id"]),
                "user_name": user.get("user_name"),
                "user_email": user.get("user_email"),
                "session_token": session_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "expires_at": expires_at.isoformat()
            }
        }

        logger.info("=" * 80)
        logger.info("✅ USER LOGIN SUCCESSFUL")
        logger.info("=" * 80)
        logger.info(f"  Email: {request.email}")
        logger.info(f"  Username: {user.get('user_name')}")
        logger.info(f"  User ID: {str(user['_id'])}")
        logger.info(f"  Session token: {session_token[:16]}...")
        logger.info(f"  Expires at: {expires_at.isoformat()}")
        logger.info("=" * 80)

        return JSONResponse(content=response_data, status_code=200)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"💥 LOGIN ERROR: {e}", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
