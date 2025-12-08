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

    # Clean ONLY test-specific collections
    # CRITICAL: NEVER delete production collections
    collections_cleaned = 0
    for collection_name in ["sessions", "users_login"]:
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

    # Create test admin user in iris-admins collection
    admin_password_hash = bcrypt.hashpw(
        "TestPassword123!".encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    test_admin = {
        "user_email": "test-admin@test.com",
        "user_name": "Test Admin",
        "password": admin_password_hash,
        "permission_level": "admin",
        "status": "active",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "last_login": None
    }

    # Insert test admin (replace if exists)
    await database.db["iris-admins"].replace_one(
        {"user_email": test_admin["user_email"]},
        test_admin,
        upsert=True
    )

    # Create test companies if they don't exist
    test_companies = [
        {
            "company_name": "Acme Corporation",
            "industry": "Technology",
            "contact_email": "contact@acme.test.com",
            "contact_phone": "+1-555-0100",
            "address": "123 Tech Street, Silicon Valley, CA 94000",
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "company_name": "Global Translation Inc",
            "industry": "Translation Services",
            "contact_email": "info@globaltrans.test.com",
            "contact_phone": "+1-555-0200",
            "address": "456 Language Ave, New York, NY 10001",
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "company_name": "TechDocs Ltd",
            "industry": "Documentation",
            "contact_email": "hello@techdocs.test.com",
            "contact_phone": "+1-555-0300",
            "address": "789 Documentation Blvd, Austin, TX 78701",
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]

    companies_created = []
    for company_data in test_companies:
        # Insert company (replace if exists)
        result = await database.db.company.replace_one(
            {"company_name": company_data["company_name"]},
            company_data,
            upsert=True
        )
        companies_created.append(company_data["company_name"])

    return {
        "message": "Test data seeded successfully",
        "test_user": {
            "email": test_user_login["user_email"],
            "name": test_user_login["user_name"],
            "password": "testpass123"  # Only return in test mode!
        },
        "test_admin": {
            "email": test_admin["user_email"],
            "name": test_admin["user_name"],
            "password": "TestPassword123!"  # Only return in test mode!
        },
        "companies_created": companies_created,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/seed-subscriptions", response_model=Dict[str, Any])
async def seed_subscription_data():
    """
    Seed test subscription data for EXISTING companies

    **ONLY AVAILABLE IN TEST/DEV MODE**

    Creates ONE subscription for each existing company in the database.
    This provides consistent test data for subscription-related tests.

    Returns:
        message: Success message
        subscriptions_created: Number of subscriptions created
    """
    check_test_environment()

    if database.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not connected"
        )

    # CRITICAL: Use EXISTING companies from the database, do NOT create new ones
    # Get all companies from the database
    companies = await database.db.company.find({}).to_list(length=10)

    if len(companies) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No companies found in database. Cannot create subscriptions."
        )

    # Create subscription templates for each company based on their index
    # This works with ANY existing companies in the database
    subscription_templates = [
        {
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            "price_per_unit": 0.10,
            "promotional_units": 100,
            "discount": 0.9,
            "subscription_price": 90.00,
            "start_date": datetime(2025, 1, 1),
            "end_date": datetime(2025, 12, 31),
            "billing_frequency": "quarterly",
            "payment_terms_days": 30,
            "status": "active"
        },
        {
            "subscription_unit": "page",
            "units_per_subscription": 2000,
            "price_per_unit": 0.12,
            "promotional_units": 200,
            "discount": 0.88,
            "subscription_price": 211.20,
            "start_date": datetime(2025, 1, 15),
            "end_date": datetime(2025, 12, 31),
            "billing_frequency": "monthly",
            "payment_terms_days": 45,
            "status": "active"
        }
    ]

    created_count = 0
    updated_count = 0
    companies_processed = []

    # For each company, create or update ONE subscription
    for idx, company in enumerate(companies):
        # Get company_name
        company_name = company.get("company_name", "Unknown")
        companies_processed.append(company_name)

        # Use template based on index (cycle through templates if more companies than templates)
        template = subscription_templates[idx % len(subscription_templates)]

        # Delete ALL existing subscriptions for this company (to handle duplicates)
        delete_result = await database.db.subscriptions.delete_many({"company_name": company_name})
        deleted_count = delete_result.deleted_count

        # Create exactly ONE subscription
        subscription_data = {
            "company_name": company_name,
            **template,
            "usage_periods": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        await database.db.subscriptions.insert_one(subscription_data)
        created_count += 1

        if deleted_count > 0:
            updated_count += 1

    return {
        "message": "Subscription test data seeded successfully (ONE per company)",
        "subscriptions_created": created_count,
        "subscriptions_updated": updated_count,
        "companies_processed": companies_processed,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/seed-translation-transactions", response_model=Dict[str, Any])
async def seed_translation_transactions():
    """
    Seed translation transaction test data for EXISTING companies

    **ONLY AVAILABLE IN TEST/DEV MODE**

    Creates 5-10 realistic translation_transaction records for each existing company.
    This provides consistent test data for translation transaction UI testing.

    Returns:
        message: Success message
        transactions_created: Number of transactions created per company
        total_created: Total number of transactions created
    """
    check_test_environment()

    if database.db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not connected"
        )

    import random
    import uuid
    from datetime import timedelta

    # CRITICAL: Use EXISTING companies from the database, do NOT use hardcoded fake IDs
    companies = await database.db.company.find({}).to_list(length=10)

    if len(companies) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No companies found in database. Cannot create transactions."
        )

    # Build company mapping from actual database records
    company_data = []
    for company in companies:
        company_data.append({
            "id": company["_id"],
            "name": company.get("company_name", "Unknown Company")
        })

    # Language pairs for variety
    language_pairs = [
        ("en", "es"), ("en", "fr"), ("en", "de"), ("en", "ja"), ("en", "zh"),
        ("es", "en"), ("fr", "en"), ("de", "en"), ("ja", "en"), ("zh", "en"),
        ("es", "fr"), ("fr", "de"), ("de", "es")
    ]

    # File types and names
    file_templates = [
        ("Contract_{}.pdf", "application/pdf"),
        ("Report_{}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("Presentation_{}.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        ("Manual_{}.pdf", "application/pdf"),
        ("Agreement_{}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("Proposal_{}.pdf", "application/pdf"),
        ("Invoice_{}.pdf", "application/pdf"),
        ("Specification_{}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    ]

    # Statuses with realistic distribution
    statuses = ["started", "started", "confirmed", "confirmed", "confirmed", "pending", "failed"]

    # User emails
    user_emails = [
        "user@company.com", "admin@company.com", "translator@company.com",
        "manager@company.com", "analyst@company.com"
    ]

    transactions_created = {}
    all_transactions = []

    # Create transactions for each EXISTING company
    for company in company_data:
        company_name = company["name"]
        num_transactions = random.randint(5, 10)
        company_transactions = []

        for i in range(num_transactions):
            # Generate unique transaction ID
            transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"

            # Random language pair
            source_lang, target_lang = random.choice(language_pairs)

            # Random file
            file_template, file_type = random.choice(file_templates)
            file_name = file_template.format(random.randint(1000, 9999))

            # Random file size (100KB to 10MB)
            file_size = random.randint(100000, 10000000)

            # Random units count (pages: 1-100)
            units_count = random.randint(1, 100)

            # Price per unit (0.01 to 0.15 per page)
            price_per_unit = round(random.uniform(0.01, 0.15), 2)

            # Total price
            total_price = round(units_count * price_per_unit, 2)

            # Random status
            status_value = random.choice(statuses)

            # Random user
            user_id = random.choice(user_emails)

            # Generate timestamps (within last 30 days)
            days_ago = random.randint(0, 30)
            created_at = datetime.utcnow() - timedelta(days=days_ago, hours=random.randint(0, 23))
            updated_at = created_at + timedelta(hours=random.randint(0, 48))

            # Google Drive URLs (mock)
            original_file_url = f"https://docs.google.com/document/d/{uuid.uuid4().hex[:20]}/edit"
            translated_file_url = "" if status_value in ["started", "pending"] else f"https://docs.google.com/document/d/{uuid.uuid4().hex[:20]}/edit"

            # Error message for failed transactions
            error_message = ""
            if status_value == "failed":
                error_messages = [
                    "Translation service timeout",
                    "Unsupported file format",
                    "File too large for processing",
                    "Invalid source language detection"
                ]
                error_message = random.choice(error_messages)

            # Subscription ID (some transactions might not have one)
            subscription_id = f"68fa6add22b0c739f4f4b{random.randint(100, 999)}" if random.random() > 0.2 else None

            transaction = {
                "transaction_id": transaction_id,
                "user_id": user_id,
                "original_file_url": original_file_url,
                "translated_file_url": translated_file_url,
                "source_language": source_lang,
                "target_language": target_lang,
                "file_name": file_name,
                "file_size": file_size,
                "units_count": units_count,
                "price_per_unit": price_per_unit,
                "total_price": total_price,
                "status": status_value,
                "error_message": error_message,
                "created_at": created_at,
                "updated_at": updated_at,
                "company_name": company_name,
                "subscription_id": subscription_id,
                "unit_type": "page"
            }

            company_transactions.append(transaction)

        # Insert transactions for this company
        if company_transactions:
            await database.db.translation_transactions.insert_many(company_transactions)
            transactions_created[company_name] = len(company_transactions)
            all_transactions.extend(company_transactions)

    return {
        "message": "Translation transaction test data seeded successfully",
        "transactions_created": transactions_created,
        "total_created": len(all_transactions),
        "companies": [c['name'] for c in company_data],
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
