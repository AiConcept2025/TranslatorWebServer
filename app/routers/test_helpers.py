"""
Test Helper Endpoints

These endpoints are ONLY available when running in test mode (environment != "production").
They provide a clean API for frontend E2E tests to manage test data without direct DB access.

Security: Protected by environment check - returns 404 in production.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from datetime import datetime
import bcrypt

from app.database import database
from app.config import settings

router = APIRouter(prefix="/api/test", tags=["testing"])


def check_test_environment():
    """Ensure these endpoints are only available in test mode"""
    if settings.environment.lower() not in ["test", "development"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found"
        )


@router.post("/reset", response_model=Dict[str, Any])
async def reset_test_data():
    """
    Reset all test data - clean all collections

    **ONLY AVAILABLE IN TEST/DEV MODE**

    This endpoint cleans all collections to provide a fresh test environment.
    Use this in global-setup.ts to ensure test isolation.

    Returns:
        message: Success message
        collections_cleaned: Number of collections cleaned
    """
    check_test_environment()

    if database.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not connected"
        )

    # Clean all test collections
    collections_cleaned = 0
    for collection_name in ["users", "translations", "payments", "subscriptions", "sessions", "users_login", "company_users", "user_transactions", "translation_transactions"]:
        try:
            result = await database.db[collection_name].delete_many({})
            collections_cleaned += 1
        except Exception as e:
            # Continue even if a collection doesn't exist
            print(f"Warning: Could not clean collection {collection_name}: {e}")

    return {
        "message": "Test data reset successfully",
        "collections_cleaned": collections_cleaned,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/seed", response_model=Dict[str, Any])
async def seed_test_data():
    """
    Seed standard test data

    **ONLY AVAILABLE IN TEST/DEV MODE**

    Creates a standard test user that frontend tests can use.
    This provides consistent test data across test runs.

    Returns:
        message: Success message
        test_user: Created test user details
    """
    check_test_environment()

    if database.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not connected"
        )

    # Hash password for test user
    password_hash = bcrypt.hashpw(
        "testpass123".encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    # Create standard test user in users_login collection (for simple user auth)
    test_user_login = {
        "user_email": "test@example.com",
        "user_name": "Test User",
        "user_password": password_hash,
        "created_at": datetime.utcnow(),
        "is_active": True,
        "email_verified": True
    }

    # Insert test user (replace if exists)
    await database.db.users_login.replace_one(
        {"user_email": test_user_login["user_email"]},
        test_user_login,
        upsert=True
    )

    return {
        "message": "Test data seeded successfully",
        "test_user": {
            "email": test_user_login["user_email"],
            "name": test_user_login["user_name"],
            "password": "testpass123"  # Only return in test mode!
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health", response_model=Dict[str, str])
async def test_health():
    """
    Test-specific health check

    **ONLY AVAILABLE IN TEST/DEV MODE**

    Verifies that the test environment is properly configured.
    """
    check_test_environment()

    return {
        "status": "healthy",
        "environment": settings.environment,
        "message": "Test endpoints are available"
    }
