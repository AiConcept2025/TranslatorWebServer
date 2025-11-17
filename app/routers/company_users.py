"""
Company Users Router
====================

API endpoints for managing company users (authorized users per company).

This router handles:
- Creating new company users with password hashing
- Email uniqueness validation within company scope
- Company existence validation
- User ID generation

Security:
- Passwords are hashed using bcrypt with 12 rounds
- Plain text passwords are never logged or stored
- Email uniqueness is enforced per company
"""

import logging
import uuid
import asyncio
import re
from functools import partial
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from bson import ObjectId
from fastapi import APIRouter, HTTPException, status, Query, Request
from pydantic import EmailStr

from app.models.company_user_models import CompanyUserCreate, CompanyUserUpdate, CompanyUserResponse
from app.database.mongodb import database
from app.mongodb_models import CompanyUser, PermissionLevel, UserStatus

# Configure logger
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(
    prefix="/api/company-users",
    tags=["Company Users"],
    responses={
        400: {"description": "Bad Request - Company not found or email already exists"},
        422: {"description": "Validation Error - Invalid request data"},
        500: {"description": "Internal Server Error"}
    }
)


@router.post(
    "",
    response_model=CompanyUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Company User",
    description="""
    Create a new user for a specific company.

    **Requirements:**
    - Company must exist (identified by company_name query parameter)
    - Email must be unique within the company
    - Password must meet complexity requirements (min 6 chars, letter + number)

    **Security:**
    - Password is hashed using bcrypt with 12 rounds
    - Plain text password is never stored
    - Unique user_id is generated automatically

    **Example Request:**
    ```
    POST /api/company-users?company_name=Acme%20Corporation
    {
      "user_name": "John Doe",
      "email": "john.doe@company.com",
      "phone_number": "+1-555-0123",
      "password": "SecurePass123",
      "permission_level": "user",
      "status": "active"
    }
    ```

    **Example Success Response (201):**
    ```json
    {
      "user_id": "user_a1b2c3d4e5f6g7h8",
      "company_name": "Acme Corporation",
      "user_name": "John Doe",
      "email": "john.doe@company.com",
      "phone_number": "+1-555-0123",
      "permission_level": "user",
      "status": "active",
      "created_at": "2025-01-15T10:30:00Z"
    }
    ```

    **Error Responses:**
    - 400: Company not found
    - 400: Email already exists for this company
    - 422: Validation error (weak password, invalid email, etc.)
    - 500: Database or unexpected error
    """
)
async def create_company_user(
    http_request: Request,
    request: CompanyUserCreate,
    company_name: str = Query(..., description="Company name to associate the user with")
) -> CompanyUserResponse:
    """
    Create a new company user with password hashing.

    Args:
        http_request: FastAPI Request object for accessing raw body
        request: Company user creation request with user details
        company_name: Name of the company to associate the user with
        db: MongoDB database connection

    Returns:
        CompanyUserResponse: Created user details (excluding password_hash)

    Raises:
        HTTPException 400: If company not found or email already exists
        HTTPException 422: If validation fails
        HTTPException 500: If database operation fails
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info(f"🔍 [{timestamp}] POST /api/company-users - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - company_name (query param): {company_name}")

        # Log raw request body
        try:
            raw_body = await http_request.body()
            raw_body_str = raw_body.decode('utf-8') if raw_body else "{}"
            logger.info(f"📨 Raw Request Body: {raw_body_str}")
        except Exception as e:
            logger.error(f"❌ Failed to read raw request body: {e}")

        logger.info(f"🔍 Validating with CompanyUserCreate model...")
        logger.info(f"📋 Parsed Fields:")
        logger.info(f"   - user_name: {request.user_name}")
        logger.info(f"   - email: {request.email}")
        logger.info(f"   - phone_number: {request.phone_number}")
        logger.info(f"   - permission_level: {request.permission_level}")
        logger.info(f"   - status: {request.status}")
        logger.info(f"✅ Pydantic validation passed")

        logger.info(f"[CREATE_COMPANY_USER] Creating user for company: {company_name}")
        logger.info(f"[CREATE_COMPANY_USER] User email: {request.email}")

        # Step 1: Validate company exists
        logger.info(f"🔄 Calling database.company.find_one()...")
        logger.info(f"[CREATE_COMPANY_USER] Validating company exists...")
        company = await database.company.find_one({"company_name": company_name})
        logger.info(f"🔎 Database Result: found={company is not None}")

        if not company:
            logger.warning(f"[CREATE_COMPANY_USER] Company not found: {company_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Company not found: {company_name}"
            )

        logger.info(f"[CREATE_COMPANY_USER] Company found: {company_name}")

        # Step 2: Check email uniqueness within company (case-insensitive)
        logger.info(f"[CREATE_COMPANY_USER] Checking email uniqueness within company...")
        existing_user = await database.company_users.find_one({
            "company_name": company_name,
            "email": {"$regex": f"^{request.email}$", "$options": "i"}
        })

        if existing_user:
            logger.warning(
                f"[CREATE_COMPANY_USER] Email already exists for company: {request.email}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email already exists for this company: {request.email}"
            )

        logger.info(f"[CREATE_COMPANY_USER] Email is unique within company")

        # Step 3: Hash password using bcrypt (12 rounds, async executor)
        logger.info(f"[CREATE_COMPANY_USER] Hashing password with bcrypt (12 rounds)...")
        password_bytes = request.password.encode('utf-8')[:72]  # bcrypt 72-byte limit

        # Run bcrypt in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        salt = await loop.run_in_executor(None, bcrypt.gensalt, 12)
        password_hash = await loop.run_in_executor(
            None,
            partial(bcrypt.hashpw, password_bytes, salt)
        )
        password_hash_str = password_hash.decode('utf-8')
        logger.info(f"[CREATE_COMPANY_USER] Password hashed successfully")

        # Step 4: Generate unique user_id
        user_id = f"user_{uuid.uuid4().hex[:16]}"
        logger.info(f"[CREATE_COMPANY_USER] Generated user_id: {user_id}")

        # Step 5: Create CompanyUser document
        now = datetime.now(timezone.utc)
        user_doc = {
            "user_id": user_id,
            "company_name": company_name,
            "user_name": request.user_name,
            "email": request.email.lower(),  # Store normalized email
            "phone_number": request.phone_number,
            "permission_level": request.permission_level.value,
            "status": request.status.value,
            "password_hash": password_hash_str,
            "last_login": None,
            "created_at": now,
            "updated_at": now
        }

        # Step 6: Insert into company_users collection
        logger.info(f"🔄 Calling database.company_users.insert_one()...")
        logger.info(f"[CREATE_COMPANY_USER] Inserting user into company_users collection...")
        result = await database.company_users.insert_one(user_doc)
        logger.info(f"🔎 Database Insert Result: inserted_id={result.inserted_id}")

        if not result.inserted_id:
            logger.error(f"❌ Failed to insert user into database")
            logger.error(f"[CREATE_COMPANY_USER] Failed to insert user into database")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )

        logger.info(f"✅ User created successfully:")
        logger.info(f"   - user_id: {user_id}")
        logger.info(f"   - company_name: {company_name}")
        logger.info(f"   - email: {request.email}")
        logger.info(f"   - MongoDB _id: {result.inserted_id}")
        logger.info(
            f"[CREATE_COMPANY_USER] User created successfully with ID: {result.inserted_id}"
        )

        # Step 7: Return CompanyUserResponse with company_name included
        response_data = CompanyUserResponse(
            user_id=user_id,
            company_name=company_name,
            user_name=request.user_name,
            email=request.email.lower(),
            phone_number=request.phone_number,
            permission_level=request.permission_level.value,
            status=request.status.value,
            created_at=now
        )
        logger.info(f"📤 Response: user_id={user_id}, email={request.email}")

        return response_data

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Log unexpected errors and return 500
        logger.error(f"❌ Unexpected error creating user:", exc_info=True)
        logger.error(f"   - Error: {str(e)}")
        logger.error(f"   - Error type: {type(e).__name__}")
        logger.error(f"   - Company: {company_name}")
        logger.error(f"   - Email: {request.email}")
        logger.error(
            f"[CREATE_COMPANY_USER] Unexpected error creating user: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "",
    response_model=list[CompanyUserResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Company Users",
    description="""
    Fetch all users for a specific company or all company users.

    **Query Parameters:**
    - company_name: Optional filter to get users for specific company only

    **Returns:**
    - Array of company users

    **Logging:**
    - Log incoming request with parameters
    - Log database query
    - Log results count
    - Log each user being returned

    **Example Requests:**
    ```
    GET /api/company-users → All company users
    GET /api/company-users?company_name=Iris%20Trading → Users for Iris Trading only
    ```

    **Example Success Response (200):**
    ```json
    [
      {
        "user_id": "user_a1b2c3d4e5f6g7h8",
        "company_name": "Iris Trading",
        "user_name": "John Doe",
        "email": "john.doe@iristrading.com",
        "phone_number": "+1-555-0123",
        "permission_level": "admin",
        "status": "active",
        "created_at": "2025-01-15T10:30:00Z"
      }
    ]
    ```

    **Error Responses:**
    - 400: Company not found (when filtering by company_name)
    - 500: Database or unexpected error
    """
)
async def get_company_users(
    company_name: Optional[str] = Query(None, description="Optional: filter by company name")
) -> list[CompanyUserResponse]:
    """
    Retrieve company users from MongoDB.

    Args:
        company_name: Optional filter to get users for specific company only

    Returns:
        list[CompanyUserResponse]: Array of company users

    Raises:
        HTTPException 400: If company not found (when filtering)
        HTTPException 500: If database operation fails
    """
    try:
        logger.info("=" * 80)
        logger.info(f"[GET_COMPANY_USERS] === INCOMING REQUEST ===")
        logger.info(f"[GET_COMPANY_USERS] company_name filter: {company_name or 'None (fetch all)'}")
        logger.info("=" * 80)

        # Build query based on company_name filter
        query = {}
        if company_name:
            # Validate company exists first
            logger.info(f"[GET_COMPANY_USERS] Validating company exists: {company_name}")
            company = await database.company.find_one({"company_name": company_name})

            if not company:
                logger.warning(f"[GET_COMPANY_USERS] Company not found: {company_name}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Company not found: {company_name}"
                )

            query = {"company_name": company_name}
            logger.info(f"[GET_COMPANY_USERS] Fetching for company_name: {company_name}")
        else:
            logger.info(f"[GET_COMPANY_USERS] Fetching ALL company users (no filter)")

        # Execute database query
        logger.info(f"[GET_COMPANY_USERS] === DATABASE QUERY ===")
        logger.info(f"[GET_COMPANY_USERS] Query: {query}")

        users = await database.company_users.find(query).to_list(None)

        logger.info(f"[GET_COMPANY_USERS] === QUERY RESULTS ===")
        logger.info(f"[GET_COMPANY_USERS] Found {len(users)} users in database")

        for idx, user in enumerate(users, 1):
            logger.info(
                f"[GET_COMPANY_USERS] User {idx}: {user.get('user_name')} "
                f"({user.get('email')})"
            )

        # Convert to response models
        result = []
        for user in users:
            # Use company_name directly from user document
            company_name_str = user.get("company_name", "Unknown")

            user_response = CompanyUserResponse(
                user_id=user["user_id"],
                company_name=company_name_str,
                user_name=user["user_name"],
                email=user["email"],
                phone_number=user.get("phone_number"),
                permission_level=user["permission_level"],
                status=user["status"],
                created_at=user["created_at"]
            )
            result.append(user_response)

        # Log outgoing response
        logger.info("=" * 80)
        logger.info(f"[GET_COMPANY_USERS] === OUTGOING RESPONSE ===")
        logger.info(f"[GET_COMPANY_USERS] Returning {len(result)} users")

        for idx, user in enumerate(result, 1):
            logger.info(
                f"[GET_COMPANY_USERS] Response {idx}: {user.user_name} "
                f"({user.email}) - {user.company_name}"
            )

        logger.info("=" * 80)

        return result

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Log unexpected errors and return 500
        logger.error("=" * 80)
        logger.error(f"[GET_COMPANY_USERS] === ERROR ===")
        logger.error(f"[GET_COMPANY_USERS] Error type: {type(e).__name__}")
        logger.error(f"[GET_COMPANY_USERS] Error message: {str(e)}")
        logger.error("=" * 80, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/{user_id}",
    response_model=CompanyUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Company User by ID",
    description="""
    Fetch a single company user by their user_id.

    **Path Parameters:**
    - user_id: Unique user identifier (e.g., "user_abc123")

    **Returns:**
    - Company user details

    **Example Request:**
    ```
    GET /api/company-users/user_abc123
    ```

    **Example Success Response (200):**
    ```json
    {
      "user_id": "user_abc123",
      "company_name": "Acme Corporation",
      "user_name": "John Doe",
      "email": "john.doe@company.com",
      "phone_number": "+1-555-0123",
      "permission_level": "admin",
      "status": "active",
      "created_at": "2025-01-15T10:30:00Z"
    }
    ```

    **Error Responses:**
    - 404: User not found
    - 500: Database or unexpected error
    """
)
async def get_company_user(user_id: str) -> CompanyUserResponse:
    """
    Retrieve a single company user by user_id.

    Args:
        user_id: Unique user identifier

    Returns:
        CompanyUserResponse: Company user details

    Raises:
        HTTPException 404: If user not found
        HTTPException 500: If database operation fails
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("=" * 80)
        logger.info(f"🔍 [{timestamp}] GET /api/company-users/{user_id} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - user_id (path param): {user_id}")
        logger.info("=" * 80)

        # Query database
        logger.info(f"[GET_COMPANY_USER] Fetching user from database...")
        logger.info(f"🔄 Calling database.company_users.find_one()...")
        logger.info(f"   - Query: {{'user_id': '{user_id}'}}")

        user = await database.company_users.find_one({"user_id": user_id})

        logger.info(f"🔎 Database Result: found={user is not None}")

        if not user:
            logger.warning("=" * 80)
            logger.warning(f"⚠️ [{timestamp}] User not found: {user_id}")
            logger.warning("=" * 80)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {user_id}"
            )

        logger.info(f"[GET_COMPANY_USER] User found:")
        logger.info(f"   - user_name: {user.get('user_name')}")
        logger.info(f"   - email: {user.get('email')}")
        logger.info(f"   - company_name: {user.get('company_name')}")
        logger.info(f"   - permission_level: {user.get('permission_level')}")
        logger.info(f"   - status: {user.get('status')}")

        # Convert to response model
        user_response = CompanyUserResponse(
            user_id=user["user_id"],
            company_name=user.get("company_name", "Unknown"),
            user_name=user["user_name"],
            email=user["email"],
            phone_number=user.get("phone_number"),
            permission_level=user["permission_level"],
            status=user["status"],
            created_at=user["created_at"]
        )

        logger.info("=" * 80)
        logger.info(f"✅ [{timestamp}] User retrieved successfully: {user_id}")
        logger.info(f"📤 Response: {user_response.user_name} ({user_response.email})")
        logger.info("=" * 80)

        return user_response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Log unexpected errors and return 500
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.error("=" * 80)
        logger.error(f"❌ [{timestamp}] GET /api/company-users/{user_id} - ERROR")
        logger.error(f"[GET_COMPANY_USER] Error type: {type(e).__name__}")
        logger.error(f"[GET_COMPANY_USER] Error message: {str(e)}")
        logger.error("=" * 80, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.patch(
    "/{user_id}",
    response_model=CompanyUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Company User",
    description="""
    Update an existing company user (partial update).

    **Path Parameters:**
    - user_id: Unique user identifier

    **Updatable Fields:**
    - user_name: User's full name
    - email: User's email (must be unique within company)
    - phone_number: User's phone number
    - password: New password (will be hashed)
    - permission_level: admin or user
    - status: active, inactive, or suspended

    **Example Request:**
    ```
    PATCH /api/company-users/user_abc123
    {
      "user_name": "Jane Doe",
      "permission_level": "admin",
      "status": "active"
    }
    ```

    **Example Success Response (200):**
    ```json
    {
      "user_id": "user_abc123",
      "company_name": "Acme Corporation",
      "user_name": "Jane Doe",
      "email": "jane.doe@company.com",
      "phone_number": "+1-555-0123",
      "permission_level": "admin",
      "status": "active",
      "created_at": "2025-01-15T10:30:00Z"
    }
    ```

    **Error Responses:**
    - 400: Email already exists (when changing email)
    - 404: User not found
    - 422: Validation error
    - 500: Database or unexpected error
    """
)
async def update_company_user(
    user_id: str,
    update_data: CompanyUserUpdate
) -> CompanyUserResponse:
    """
    Update an existing company user with partial updates.

    Args:
        user_id: User identifier
        update_data: Fields to update (all optional)

    Returns:
        CompanyUserResponse: Updated user details

    Raises:
        HTTPException 400: If email already exists
        HTTPException 404: If user not found
        HTTPException 422: If validation fails
        HTTPException 500: If database operation fails
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("=" * 80)
        logger.info(f"🔍 [{timestamp}] PATCH /api/company-users/{user_id} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - user_id (path param): {user_id}")
        logger.info(f"📨 Request Body: {update_data.dict(exclude_none=True, exclude={'password'})}")
        if update_data.password is not None:
            logger.info(f"   - password: [REDACTED] (will be hashed)")
        logger.info("=" * 80)

        # Step 1: Fetch existing user
        logger.info(f"[UPDATE_COMPANY_USER] Fetching existing user...")
        logger.info(f"🔄 Calling database.company_users.find_one()...")
        existing_user = await database.company_users.find_one({"user_id": user_id})
        logger.info(f"🔎 Database Result: found={existing_user is not None}")

        if not existing_user:
            logger.warning("=" * 80)
            logger.warning(f"⚠️ [{timestamp}] User not found: {user_id}")
            logger.warning("=" * 80)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {user_id}"
            )

        logger.info(f"[UPDATE_COMPANY_USER] Existing user found:")
        logger.info(f"   - user_name: {existing_user.get('user_name')}")
        logger.info(f"   - email: {existing_user.get('email')}")
        logger.info(f"   - company_name: {existing_user.get('company_name')}")

        # Step 2: Build update document
        update_doc = {}

        if update_data.user_name is not None:
            update_doc["user_name"] = update_data.user_name
            logger.info(f"[UPDATE_COMPANY_USER] Updating user_name: {update_data.user_name}")

        if update_data.email is not None:
            # Check email uniqueness within company (excluding current user)
            normalized_email = update_data.email
            logger.info(f"[UPDATE_COMPANY_USER] Checking email uniqueness: {normalized_email}")

            existing_email = await database.company_users.find_one({
                "company_name": existing_user["company_name"],
                "email": {"$regex": f"^{normalized_email}$", "$options": "i"},
                "user_id": {"$ne": user_id}  # Exclude current user
            })

            if existing_email:
                logger.warning(f"[UPDATE_COMPANY_USER] Email already exists: {normalized_email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email already exists for this company: {normalized_email}"
                )

            update_doc["email"] = normalized_email
            logger.info(f"[UPDATE_COMPANY_USER] Email is unique, updating to: {normalized_email}")

        if update_data.phone_number is not None:
            update_doc["phone_number"] = update_data.phone_number
            logger.info(f"[UPDATE_COMPANY_USER] Updating phone_number: {update_data.phone_number}")

        if update_data.password is not None:
            # Password validation already done by Pydantic model
            # Hash password
            logger.info(f"[UPDATE_COMPANY_USER] Hashing new password with bcrypt (12 rounds)...")
            password_bytes = update_data.password.encode('utf-8')[:72]  # bcrypt 72-byte limit
            loop = asyncio.get_event_loop()
            salt = await loop.run_in_executor(None, bcrypt.gensalt, 12)
            password_hash = await loop.run_in_executor(
                None,
                partial(bcrypt.hashpw, password_bytes, salt)
            )
            update_doc["password_hash"] = password_hash.decode('utf-8')
            logger.info(f"[UPDATE_COMPANY_USER] Password hashed successfully")

        if update_data.permission_level is not None:
            update_doc["permission_level"] = update_data.permission_level.value
            logger.info(f"[UPDATE_COMPANY_USER] Updating permission_level: {update_data.permission_level.value}")

        if update_data.status is not None:
            update_doc["status"] = update_data.status.value
            logger.info(f"[UPDATE_COMPANY_USER] Updating status: {update_data.status.value}")

        # Always update updated_at timestamp
        update_doc["updated_at"] = datetime.now(timezone.utc)

        if not update_doc or update_doc == {"updated_at": update_doc["updated_at"]}:
            logger.warning(f"[UPDATE_COMPANY_USER] No fields to update, returning existing user")
            # Return existing user without update
            return CompanyUserResponse(
                user_id=existing_user["user_id"],
                company_name=existing_user.get("company_name", "Unknown"),
                user_name=existing_user["user_name"],
                email=existing_user["email"],
                phone_number=existing_user.get("phone_number"),
                permission_level=existing_user["permission_level"],
                status=existing_user["status"],
                created_at=existing_user["created_at"]
            )

        # Step 3: Update user in database
        logger.info(f"[UPDATE_COMPANY_USER] Updating user in database...")
        logger.info(f"🔄 Calling database.company_users.update_one()...")
        logger.info(f"   - Filter: {{'user_id': '{user_id}'}}")
        logger.info(f"   - Update: {{'$set': {list(update_doc.keys())}}}")

        result = await database.company_users.update_one(
            {"user_id": user_id},
            {"$set": update_doc}
        )

        logger.info(f"🔎 Database Update Result:")
        logger.info(f"   - matched_count: {result.matched_count}")
        logger.info(f"   - modified_count: {result.modified_count}")

        if result.matched_count == 0:
            logger.error(f"❌ User not found during update: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {user_id}"
            )

        # Step 4: Fetch updated user
        logger.info(f"[UPDATE_COMPANY_USER] Fetching updated user...")
        updated_user = await database.company_users.find_one({"user_id": user_id})

        if not updated_user:
            logger.error(f"❌ Failed to fetch updated user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch updated user"
            )

        logger.info(f"✅ User updated successfully:")
        logger.info(f"   - user_id: {user_id}")
        logger.info(f"   - user_name: {updated_user.get('user_name')}")
        logger.info(f"   - email: {updated_user.get('email')}")
        logger.info(f"   - permission_level: {updated_user.get('permission_level')}")
        logger.info(f"   - status: {updated_user.get('status')}")

        # Step 5: Return updated user
        response_data = CompanyUserResponse(
            user_id=updated_user["user_id"],
            company_name=updated_user.get("company_name", "Unknown"),
            user_name=updated_user["user_name"],
            email=updated_user["email"],
            phone_number=updated_user.get("phone_number"),
            permission_level=updated_user["permission_level"],
            status=updated_user["status"],
            created_at=updated_user["created_at"]
        )

        logger.info("=" * 80)
        logger.info(f"✅ [{timestamp}] PATCH /api/company-users/{user_id} - SUCCESS")
        logger.info(f"📤 Response: {response_data.user_name} ({response_data.email})")
        logger.info("=" * 80)

        return response_data

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Log unexpected errors and return 500
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.error("=" * 80)
        logger.error(f"❌ [{timestamp}] PATCH /api/company-users/{user_id} - ERROR")
        logger.error(f"[UPDATE_COMPANY_USER] Error type: {type(e).__name__}")
        logger.error(f"[UPDATE_COMPANY_USER] Error message: {str(e)}")
        logger.error("=" * 80, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Company User",
    description="""
    Delete a company user by user_id.

    **Path Parameters:**
    - user_id: Unique user identifier

    **Example Request:**
    ```
    DELETE /api/company-users/user_abc123
    ```

    **Success Response:**
    - 204 No Content (successful deletion)

    **Error Responses:**
    - 404: User not found
    - 500: Database or unexpected error
    """
)
async def delete_company_user(user_id: str):
    """
    Delete a company user by user_id.

    Args:
        user_id: User identifier

    Returns:
        None (204 No Content)

    Raises:
        HTTPException 404: If user not found
        HTTPException 500: If database operation fails
    """
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.info("=" * 80)
        logger.info(f"🔍 [{timestamp}] DELETE /api/company-users/{user_id} - START")
        logger.info(f"📥 Request Parameters:")
        logger.info(f"   - user_id (path param): {user_id}")
        logger.info("=" * 80)

        # Step 1: Check if user exists
        logger.info(f"[DELETE_COMPANY_USER] Checking if user exists...")
        logger.info(f"🔄 Calling database.company_users.find_one()...")
        existing_user = await database.company_users.find_one({"user_id": user_id})
        logger.info(f"🔎 Database Result: found={existing_user is not None}")

        if not existing_user:
            logger.warning("=" * 80)
            logger.warning(f"⚠️ [{timestamp}] User not found: {user_id}")
            logger.warning("=" * 80)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {user_id}"
            )

        logger.info(f"[DELETE_COMPANY_USER] User found:")
        logger.info(f"   - user_name: {existing_user.get('user_name')}")
        logger.info(f"   - email: {existing_user.get('email')}")
        logger.info(f"   - company_name: {existing_user.get('company_name')}")

        # Step 2: Delete user
        logger.info(f"[DELETE_COMPANY_USER] Deleting user from database...")
        logger.info(f"🔄 Calling database.company_users.delete_one()...")
        logger.info(f"   - Filter: {{'user_id': '{user_id}'}}")

        result = await database.company_users.delete_one({"user_id": user_id})

        logger.info(f"🔎 Database Delete Result:")
        logger.info(f"   - deleted_count: {result.deleted_count}")

        if result.deleted_count == 0:
            logger.error(f"❌ Failed to delete user: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )

        logger.info("=" * 80)
        logger.info(f"✅ [{timestamp}] DELETE /api/company-users/{user_id} - SUCCESS")
        logger.info(f"📤 User deleted: {existing_user.get('user_name')} ({existing_user.get('email')})")
        logger.info("=" * 80)

        return None  # 204 No Content

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Log unexpected errors and return 500
        timestamp = datetime.now(timezone.utc).isoformat()
        logger.error("=" * 80)
        logger.error(f"❌ [{timestamp}] DELETE /api/company-users/{user_id} - ERROR")
        logger.error(f"[DELETE_COMPANY_USER] Error type: {type(e).__name__}")
        logger.error(f"[DELETE_COMPANY_USER] Error message: {str(e)}")
        logger.error("=" * 80, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


# Export router
__all__ = ["router"]
