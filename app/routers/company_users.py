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
from functools import partial
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from bson import ObjectId
from fastapi import APIRouter, HTTPException, status, Query

from app.models.company_user_models import CompanyUserCreate, CompanyUserResponse
from app.database.mongodb import database
from app.mongodb_models import CompanyUser

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
    request: CompanyUserCreate,
    company_name: str = Query(..., description="Company name to associate the user with")
) -> CompanyUserResponse:
    """
    Create a new company user with password hashing.

    Args:
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
        logger.info(f"[CREATE_COMPANY_USER] Creating user for company: {company_name}")
        logger.info(f"[CREATE_COMPANY_USER] User email: {request.email}")

        # Step 1: Validate company exists
        logger.info(f"[CREATE_COMPANY_USER] Validating company exists...")
        company = await database.company.find_one({"company_name": company_name})

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
        logger.info(f"[CREATE_COMPANY_USER] Inserting user into company_users collection...")
        result = await database.company_users.insert_one(user_doc)

        if not result.inserted_id:
            logger.error(f"[CREATE_COMPANY_USER] Failed to insert user into database")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )

        logger.info(
            f"[CREATE_COMPANY_USER] User created successfully with ID: {result.inserted_id}"
        )

        # Step 7: Return CompanyUserResponse with company_name included
        return CompanyUserResponse(
            user_id=user_id,
            company_name=company_name,
            user_name=request.user_name,
            email=request.email.lower(),
            phone_number=request.phone_number,
            permission_level=request.permission_level.value,
            status=request.status.value,
            created_at=now
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        # Log unexpected errors and return 500
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


# Export router
__all__ = ["router"]
