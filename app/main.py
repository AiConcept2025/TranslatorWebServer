"""
Main FastAPI application for the Translation Web Server.
"""

from fastapi import FastAPI, Request, HTTPException, Depends, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import uvicorn
from contextlib import asynccontextmanager
import logging
import time
import asyncio
import json

# Import configuration
from app.config import settings

# Import routers
from app.routers import languages, upload, auth, subscriptions, translate_user, payments, test_helpers, user_transactions, invoices, translation_transactions, company_users, orders, companies, submit, email_test
from app.routers import payment_simplified as payment

# Import middleware and utilities
# RateLimitMiddleware removed - causes file upload failures with BaseHTTPMiddleware
# Using slowapi for endpoint-specific rate limiting instead
from app.middleware.logging import LoggingMiddleware
from app.middleware.encoding_fix import EncodingFixMiddleware
from app.middleware.auth_middleware import get_current_user, get_optional_user
from app.utils.health import health_checker

# Import slowapi for endpoint-specific rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


# Application lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # Configure logging FIRST (before any logging calls)
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True  # Override any existing configuration
    )

    # Startup
    logging.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize services
    await initialize_services()

    # Create required directories
    settings.ensure_directories()

    yield

    # Shutdown
    logging.info(f"Shutting down {settings.app_name}")
    await cleanup_services()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A comprehensive translation web service supporting multiple languages and file formats",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan
)

# Initialize slowapi rate limiter (endpoint-specific, not global middleware)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============================================================================
# MIDDLEWARE CONFIGURATION - ORDER MATTERS!
# ============================================================================
# FastAPI processes middleware in REVERSE order of addition:
# - Middleware added FIRST executes LAST (closest to endpoint)
# - Middleware added LAST executes FIRST (outermost layer)
#
# Current execution order (request flow):
# 1. timeout_middleware (decorator - outermost)
# 2. LoggingMiddleware
# 3. EncodingFixMiddleware
# 4. RequestBodyDebugMiddleware (for payment endpoints debugging)
# 5. CORSMiddleware (innermost - adds headers last)
# 6. Endpoint
#
# IMPORTANT: CORSMiddleware must be innermost so it processes responses
# from ALL sources including timeout errors from outer middleware
# ============================================================================

# Add custom middleware FIRST (so they execute in the middle)
# DISABLED: RequestBodyDebugMiddleware causes body stream corruption
# app.add_middleware(RequestBodyDebugMiddleware)
app.add_middleware(EncodingFixMiddleware)
app.add_middleware(LoggingMiddleware)
# REMOVED: RateLimitMiddleware - causes file upload failures with BaseHTTPMiddleware
# Using slowapi decorators on specific endpoints instead (see auth.py)

# Add CORS middleware LAST (so it's closest to the endpoint and processes ALL responses)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=["*"] if settings.cors_headers == "*" else settings.cors_headers.split(','),
    expose_headers=["X-Request-ID", "X-Process-Time"]  # Allow frontend to read custom headers
)

# Include routers
app.include_router(languages.router)
app.include_router(upload.router)
app.include_router(submit.router)  # File submission endpoint
app.include_router(payment.router)  # Simplified payment webhooks
app.include_router(payments.router)  # Payment management API
app.include_router(user_transactions.router)  # User transaction payment API
app.include_router(invoices.router)  # Invoice management API
app.include_router(translation_transactions.router)  # Translation transaction management API
app.include_router(company_users.router)  # Company user management API
app.include_router(companies.router)  # Company management API
app.include_router(orders.router)  # Orders management API
app.include_router(auth.router)
app.include_router(subscriptions.router)
app.include_router(translate_user.router)

# Include test helper endpoints only in test/dev mode
if settings.environment.lower() in ["test", "development"]:
    app.include_router(test_helpers.router)
    app.include_router(email_test.router)
    print("⚠️  Test helper endpoints enabled (test/dev mode only)")
    print("⚠️  Email diagnostic endpoints enabled (test/dev mode only)")

# Import models for /translate endpoint
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any

class FileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str
    content: str  # Base64-encoded file content from client

class TranslateRequest(BaseModel):
    files: List[FileInfo]
    sourceLanguage: str
    targetLanguage: str
    email: EmailStr
    paymentIntentId: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================
def serialize_transaction_for_json(txn: dict) -> dict:
    """
    Convert MongoDB transaction document to JSON-serializable dict.

    Handles:
    - ObjectId → string
    - Decimal128 → float
    - datetime → ISO 8601 string (top-level and nested in documents array)

    Args:
        txn: Transaction document from MongoDB

    Returns:
        JSON-serializable dict
    """
    from bson import Decimal128

    # Convert ObjectId
    if "_id" in txn:
        txn["_id"] = str(txn["_id"])

    # Convert Decimal128 fields to float
    for key, value in list(txn.items()):
        if isinstance(value, Decimal128):
            txn[key] = float(value.to_decimal())

    # Convert top-level datetime fields to ISO format strings
    datetime_fields = ["date", "created_at", "updated_at", "payment_date"]
    for field in datetime_fields:
        if field in txn and hasattr(txn[field], "isoformat"):
            txn[field] = txn[field].isoformat()

    # Convert datetime fields in documents array
    if "documents" in txn and isinstance(txn["documents"], list):
        for doc in txn["documents"]:
            doc_datetime_fields = ["uploaded_at", "translated_at", "processing_started_at"]
            for field in doc_datetime_fields:
                if field in doc and doc[field] is not None and hasattr(doc[field], "isoformat"):
                    doc[field] = doc[field].isoformat()

    return txn


# ============================================================================
# Transaction Helper Functions
# ============================================================================
async def create_transaction_record(
    file_info: dict,
    user_data: dict,
    request_data: TranslateRequest,
    subscription: Optional[dict],
    company_name: Optional[str],
    price_per_page: float
) -> Optional[str]:
    """
    Create transaction record for a single file upload.

    STRUCTURE: Uses nested documents[] array instead of flat file fields.
    Each transaction represents one upload session with potentially multiple documents.

    Args:
        file_info: Dict with file_id, filename, size, page_count, google_drive_url
        user_data: Current authenticated user data
        request_data: Original TranslateRequest
        subscription: Enterprise subscription (or None for individual)
        company_name: Enterprise company name (or None for individual)
        price_per_page: Calculated pricing (subscription or default)

    Returns:
        transaction_id if successful, None if failed
    """
    from app.database import database
    from bson import ObjectId
    from datetime import datetime, timezone
    import uuid

    try:
        # Generate unique transaction ID
        transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"

        # Build transaction document with NESTED structure
        # IMPORTANT: Store actual email, not generated user_id
        transaction_doc = {
            # Transaction-level fields
            "transaction_id": transaction_id,
            "user_id": request_data.email,  # Use actual email for folder lookup
            "source_language": request_data.sourceLanguage,
            "target_language": request_data.targetLanguage,
            "units_count": file_info.get("page_count", 1),
            "price_per_unit": price_per_page,
            "total_price": file_info.get("page_count", 1) * price_per_page,
            "status": "started",
            "error_message": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),

            # NESTED documents array - one document per file
            "documents": [
                {
                    "file_id": file_info.get("file_id", ""),  # ← CRITICAL FIX: Add file_id from Google Drive upload
                    "file_name": file_info.get("filename", ""),
                    "file_size": file_info.get("size", 0),
                    "original_url": file_info.get("google_drive_url", ""),
                    "translated_url": None,
                    "translated_name": None,
                    "status": "uploaded",
                    "uploaded_at": datetime.now(timezone.utc),
                    "translated_at": None,
                    "processing_started_at": None,
                    "processing_duration": None
                }
            ],

            # Email batching counters - initialized on transaction creation
            # Note: This function creates 1 transaction per file, so total is always 1
            "total_documents": 1,  # Single file per transaction
            "completed_documents": 0,  # No documents translated yet
            "batch_email_sent": False  # Email not sent yet
        }

        # Add enterprise-specific fields if applicable
        if company_name and subscription:
            transaction_doc["company_name"] = company_name  # Store company name for folder lookup
            transaction_doc["user_name"] = user_data.get("user_name", "Unknown") if user_data else "Unknown"
            transaction_doc["subscription_id"] = ObjectId(str(subscription["_id"]))
            transaction_doc["unit_type"] = subscription.get("subscription_unit", "page")
        else:
            # Individual customer (no company or subscription)
            transaction_doc["company_name"] = None
            transaction_doc["user_name"] = None
            transaction_doc["subscription_id"] = None
            transaction_doc["unit_type"] = "page"

        # Insert into database
        await database.translation_transactions.insert_one(transaction_doc)

        logging.info(f"[TRANSACTION] Created {transaction_id} for file: {file_info.get('filename')}")
        print(f"[TRANSACTION] Created {transaction_id} for file: {file_info.get('filename')}")
        return transaction_id

    except Exception as e:
        logging.error(f"[TRANSACTION] Failed to create transaction for {file_info.get('filename')}: {e}")
        print(f"[TRANSACTION] Failed to create transaction for {file_info.get('filename')}: {e}")
        return None


async def create_batch_transaction_record(
    files_info: list[dict],
    user_data: dict,
    request_data: TranslateRequest,
    subscription: Optional[dict],
    company_name: Optional[str],
    price_per_page: float,
    transaction_id: str  # ✅ FIX: Accept pre-generated transaction_id
) -> Optional[str]:
    """
    Create a SINGLE transaction record for MULTIPLE file uploads (batch).

    This is the ROOT CAUSE FIX for the "7 emails for 3 documents" problem.
    Instead of creating separate transactions per file (which triggers separate emails),
    this creates ONE transaction with ALL files in the documents[] array.

    STRUCTURE: Uses nested documents[] array with all files.
    One transaction represents one batch upload session with multiple documents.

    Args:
        files_info: List of file dicts with file_id, filename, size, page_count, google_drive_url
        user_data: Current authenticated user data
        request_data: Original TranslateRequest
        subscription: Enterprise subscription (or None for individual)
        company_name: Enterprise company name (or None for individual)
        price_per_page: Calculated pricing (subscription or default)

    Returns:
        transaction_id if successful, None if failed
    """
    from app.database import database
    from bson import ObjectId
    from datetime import datetime, timezone
    import uuid

    try:
        logging.info(f"[BATCH-TRANSACTION] ===== BATCH TRANSACTION CREATE START =====")
        logging.info(f"[BATCH-TRANSACTION] Files count: {len(files_info)}")
        logging.info(f"[BATCH-TRANSACTION] Company: {company_name or 'Individual'}")
        logging.info(f"[BATCH-TRANSACTION] User email: {request_data.email}")

        # ✅ FIX: Use pre-generated transaction_id (passed as parameter)
        # Transaction ID was already generated BEFORE file uploads and set in file metadata
        logging.info(f"[BATCH-TRANSACTION] Using pre-generated transaction_id: {transaction_id}")

        # Calculate total units and price across ALL files
        total_units = sum(file.get("page_count", 1) for file in files_info)
        total_price = total_units * price_per_page
        logging.info(f"[BATCH-TRANSACTION] Total units: {total_units}, Price per unit: ${price_per_page}, Total price: ${total_price}")

        # Build documents array with ALL files
        documents = []
        for idx, file_info in enumerate(files_info):
            file_id = file_info.get("file_id", "")
            file_name = file_info.get("filename", "")
            original_url = file_info.get("google_drive_url", "")

            logging.info(f"[BATCH-TRANSACTION] Building document #{idx}: file_name={file_name}, file_id={file_id}")

            documents.append({
                "file_id": file_id,  # ← CRITICAL FIX: Add file_id from Google Drive upload
                "file_name": file_name,
                "file_size": file_info.get("size", 0),
                "original_url": original_url,
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None
            })

        # Build batch transaction document
        transaction_doc = {
            # Transaction-level fields
            "transaction_id": transaction_id,
            "user_id": request_data.email,  # Use actual email for folder lookup
            "source_language": request_data.sourceLanguage,
            "target_language": request_data.targetLanguage,
            "units_count": total_units,
            "price_per_unit": price_per_page,
            "total_price": total_price,
            "status": "started",
            "error_message": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),

            # NESTED documents array - ALL files in this batch
            "documents": documents,

            # Email batching counters - CRITICAL FIX
            # total_documents = number of files in batch (prevents multiple transactions)
            "total_documents": len(files_info),  # Total files in batch
            "completed_documents": 0,  # No documents translated yet
            "batch_email_sent": False  # Email not sent yet
        }

        # Add enterprise-specific fields if applicable
        if company_name and subscription:
            transaction_doc["company_name"] = company_name
            transaction_doc["user_name"] = user_data.get("user_name", "Unknown") if user_data else "Unknown"
            transaction_doc["subscription_id"] = ObjectId(str(subscription["_id"]))
            transaction_doc["unit_type"] = subscription.get("subscription_unit", "page")
        else:
            # Individual customer (no company or subscription)
            transaction_doc["company_name"] = None
            transaction_doc["user_name"] = None
            transaction_doc["subscription_id"] = None
            transaction_doc["unit_type"] = "page"

        # Log transaction data before insertion
        logging.info(f"[BATCH-TRANSACTION] Transaction data to be stored:")
        logging.info(f"[BATCH-TRANSACTION] {json.dumps(serialize_transaction_for_json(transaction_doc.copy()), indent=2, default=str)}")
        logging.info(f"[BATCH-TRANSACTION] Documents count: {len(transaction_doc.get('documents', []))}")

        # Validate all documents have file_id
        documents = transaction_doc.get("documents", [])
        missing_file_ids = [doc.get("file_name") for doc in documents if not doc.get("file_id")]

        if missing_file_ids:
            logging.error(f"[BATCH-TRANSACTION] CRITICAL: Documents missing file_id: {missing_file_ids}")
            raise Exception(f"Failed to store file IDs for: {', '.join(missing_file_ids)}")

        logging.info(f"[BATCH-TRANSACTION] Validation passed: All {len(documents)} documents have file_id")

        # Log each document's file_id
        for idx, doc in enumerate(documents):
            logging.info(f"[BATCH-TRANSACTION] Document #{idx}: file_id={doc.get('file_id')}, file_name={doc.get('file_name')}")

        # Insert into database
        await database.translation_transactions.insert_one(transaction_doc)

        logging.info(
            f"[BATCH TRANSACTION] Created {transaction_id} for {len(files_info)} files: "
            f"{', '.join(f.get('filename', '') for f in files_info)}"
        )
        logging.info(f"[BATCH-TRANSACTION] ===== BATCH TRANSACTION CREATE COMPLETE =====")
        print(
            f"✅ [BATCH TRANSACTION] Created {transaction_id}\n"
            f"   Files: {len(files_info)}\n"
            f"   Total pages: {total_units}\n"
            f"   Total price: ${total_price:.2f}\n"
            f"   Documents: {', '.join(f.get('filename', '') for f in files_info)}"
        )
        return transaction_id

    except Exception as e:
        logging.error(f"[BATCH TRANSACTION] Failed to create batch transaction: {e}")
        print(f"❌ [BATCH TRANSACTION] Failed to create batch transaction: {e}")
        return None


# Direct translate endpoint (Google Drive upload)
@app.post("/translate", tags=["Translation"])
async def translate_files(
    request: TranslateRequest = Body(...),
    current_user: Optional[dict] = Depends(get_optional_user)
):
    # DEBUG: This line should appear immediately after Pydantic validation succeeds
    print("🔵 DEBUG: Endpoint function STARTED - Pydantic validation PASSED")
    print(f"🔵 DEBUG: Received {len(request.files)} files")
    print(f"🔵 DEBUG: First file name: {request.files[0].name if request.files else 'NO FILES'}")
    """
    SIMPLIFIED TRANSLATE ENDPOINT:
    1. Upload files to Google Drive {customer_email}/Temp/ folder
    2. Store metadata linking customer to files (no payment sessions)
    3. Return page count for pricing calculation
    4. Frontend processes payment with customer_email
    5. Payment webhook moves files from Temp/ to Inbox/
    """
    # ============================================================================
    # RAW INCOMING DATA - Logged immediately after Pydantic validation
    # ============================================================================
    print("=" * 100)
    print("[RAW INCOMING DATA] /translate ENDPOINT REACHED - Pydantic validation passed")
    print(f"[RAW INCOMING DATA] Authenticated User: {current_user.get('email', 'N/A') if current_user else 'None (Individual User)'}")
    print(f"[RAW INCOMING DATA] Company Name: {current_user.get('company_name', 'N/A') if current_user else 'None (Individual User)'}")
    print(f"[RAW INCOMING DATA] Permission: {current_user.get('permission_level', 'N/A') if current_user else 'None (Individual User)'}")
    print(f"[RAW INCOMING DATA] Request Data:")
    print(f"[RAW INCOMING DATA]   - Customer Email: {request.email}")
    print(f"[RAW INCOMING DATA]   - Source Language: {request.sourceLanguage}")
    print(f"[RAW INCOMING DATA]   - Target Language: {request.targetLanguage}")
    print(f"[RAW INCOMING DATA]   - Number of Files: {len(request.files)}")
    print(f"[RAW INCOMING DATA]   - Payment Intent ID: {request.paymentIntentId or 'None'}")
    print(f"[RAW INCOMING DATA] Files Details:")
    for i, file_info in enumerate(request.files, 1):
        print(f"[RAW INCOMING DATA]   File {i}: '{file_info.name}' | {file_info.size:,} bytes | Type: {file_info.type} | ID: {file_info.id}")
    print("=" * 100)

    # Initialize timing tracker
    request_start_time = time.time()

    def log_step(step_name: str, details: str = ""):
        """Log step with timing"""
        elapsed = time.time() - request_start_time
        msg = f"[TRANSLATE {elapsed:6.2f}s] {step_name}"
        if details:
            msg += f" - {details}"
        logging.info(msg)
        print(msg)

    log_step("REQUEST RECEIVED", f"User: {current_user.get('email') if current_user else 'Individual'}, Company: {current_user.get('company_name') if current_user else 'None'}")
    log_step("REQUEST DETAILS", f"Email: {request.email}, {request.sourceLanguage} -> {request.targetLanguage}, Files: {len(request.files)}")

    # Log request payload
    for i, file_info in enumerate(request.files, 1):
        log_step(f"FILE {i} INPUT", f"'{file_info.name}' ({file_info.size:,} bytes, {file_info.type})")

    print(f"TRANSLATE REQUEST RECEIVED")
    print(f"Customer: {request.email}")
    print(f"Translation: {request.sourceLanguage} -> {request.targetLanguage}")
    print(f"Files to process: {len(request.files)}")
    for i, file_info in enumerate(request.files, 1):
        print(f"   File {i}: '{file_info.name}' ({file_info.size:,} bytes, {file_info.type})")

    # Validate email format (additional validation beyond EmailStr)
    log_step("VALIDATION START", "Validating email format")
    import re
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(request.email):
        log_step("VALIDATION FAILED", f"Invalid email format: {request.email}")
        raise HTTPException(
            status_code=400,
            detail="Invalid email format"
        )

    # Check for disposable email domains (stub check)
    disposable_domains = ['tempmail.org', '10minutemail.com', 'guerrillamail.com']
    email_domain = request.email.split('@')[1].lower()
    if email_domain in disposable_domains:
        raise HTTPException(
            status_code=400,
            detail="Disposable email addresses are not allowed"
        )

    # Validate language codes
    valid_languages = [
        'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko',
        'ar', 'hi', 'nl', 'pl', 'tr', 'sv', 'da', 'no', 'fi', 'th',
        'vi', 'uk', 'cs', 'hu', 'ro'
    ]

    if request.sourceLanguage not in valid_languages:
        log_step("VALIDATION FAILED", f"Invalid source language: {request.sourceLanguage}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source language: {request.sourceLanguage}"
        )

    if request.targetLanguage not in valid_languages:
        log_step("VALIDATION FAILED", f"Invalid target language: {request.targetLanguage}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target language: {request.targetLanguage}"
        )

    if request.sourceLanguage == request.targetLanguage:
        log_step("VALIDATION FAILED", "Source and target languages are the same")
        raise HTTPException(
            status_code=400,
            detail="Source and target languages cannot be the same"
        )

    log_step("VALIDATION PASSED", f"Languages: {request.sourceLanguage} -> {request.targetLanguage}")

    # Validate files
    if not request.files:
        log_step("VALIDATION FAILED", "No files provided")
        raise HTTPException(
            status_code=400,
            detail="At least one file is required"
        )

    if len(request.files) > 10:
        log_step("VALIDATION FAILED", f"Too many files: {len(request.files)}")
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 files allowed per request"
        )

    log_step("VALIDATION COMPLETE", f"{len(request.files)} file(s) validated")

    # Import Google Drive service
    from app.services.google_drive_service import google_drive_service
    from app.exceptions.google_drive_exceptions import GoogleDriveError, google_drive_error_to_http_exception

    # Detect customer type (enterprise with company_name vs individual without)
    # IMPORTANT: Do this BEFORE creating folders so we know which structure to create
    company_name = current_user.get("company_name") if current_user else None
    is_enterprise = company_name is not None and company_name != ""

    # Enhanced customer type logging
    log_step("CUSTOMER TYPE DETECTED", f"{'Enterprise' if is_enterprise else 'Individual'} (company: {company_name})")
    logging.info(f"[CUSTOMER TYPE] {'✓ Enterprise' if is_enterprise else '○ Individual'}")
    logging.info(f"[CUSTOMER TYPE]   User Email: {request.email}")
    if current_user:
        logging.info(f"[CUSTOMER TYPE]   User ID: {current_user.get('user_id')}")
        logging.info(f"[CUSTOMER TYPE]   User Name: {current_user.get('user_name', 'N/A')}")
    logging.info(f"[CUSTOMER TYPE]   Company Name: {company_name if company_name else 'N/A (individual customer)'}")

    print(f"\n👤 Customer Type: {'Enterprise' if is_enterprise else 'Individual'}")
    if is_enterprise:
        print(f"   Company: {company_name}")
    print(f"   User: {current_user.get('user_name', 'N/A')} ({request.email})")

    # For enterprise users, validate company exists in database
    # CRITICAL: Enforce referential integrity - REJECT if company doesn't exist
    if is_enterprise:
        from app.database import database
        try:
            company_doc = await database.company.find_one({"company_name": company_name})
            if not company_doc:
                # REJECT: Company doesn't exist in database
                log_step("VALIDATION FAILED", f"Company does not exist: {company_name}")
                logging.error(f"[VALIDATION] REJECTED: Company '{company_name}' does not exist in database")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid company: Company '{company_name}' does not exist in database. Cannot create translation for non-existent company."
                )

            log_step("COMPANY VALIDATED", f"Enterprise: {company_name}")
            print(f"Enterprise company validated: {company_name}")
        except HTTPException:
            raise  # Re-raise HTTP exceptions
        except Exception as e:
            log_step("COMPANY LOOKUP FAILED", f"Error: {e}")
            logging.error(f"[VALIDATION] Database error while validating company: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Database error while validating company: {str(e)}"
            )

    # Create Google Drive folder structure with proper hierarchy
    log_step("FOLDER CREATE START", f"Creating structure for: {request.email}")
    try:
        if is_enterprise and company_name:
            # Enterprise: CompanyName/user_email/Temp/
            print(f"Creating enterprise folder structure: {company_name}/{request.email}/Temp/")
            folder_id = await google_drive_service.create_customer_folder_structure(
                customer_email=request.email,
                company_name=company_name
            )
            log_step("FOLDER CREATED", f"{company_name}/{request.email}/Temp/ (ID: {folder_id})")
            print(f"Google Drive folder created: {company_name}/{request.email}/Temp/ (ID: {folder_id})")
        else:
            # Individual: user_email/Temp/
            print(f"Creating individual folder structure: {request.email}/Temp/")
            folder_id = await google_drive_service.create_customer_folder_structure(
                customer_email=request.email,
                company_name=None
            )
            log_step("FOLDER CREATED", f"{request.email}/Temp/ (ID: {folder_id})")
            print(f"Google Drive folder created: {request.email}/Temp/ (ID: {folder_id})")
    except GoogleDriveError as e:
        log_step("FOLDER CREATE FAILED", f"Google Drive error: {str(e)}")
        print(f"Google Drive error creating folder: {e}")
        raise google_drive_error_to_http_exception(e)
    except Exception as e:
        log_step("FOLDER CREATE FAILED", f"Unexpected error: {str(e)}")
        print(f"Unexpected error creating folder: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create folder structure: {str(e)}"
        )

    # Initialize pricing variables
    price_per_page = 0.10  # Default for individual customers
    subscription = None

    # Generate storage ID
    import uuid
    storage_id = f"store_{uuid.uuid4().hex[:10]}"

    # ✅ FIX: Generate transaction_id BEFORE file uploads
    # This ensures transaction_id can be set in file metadata
    transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
    log_step("TRANSACTION ID GENERATED", f"{transaction_id}")
    logging.info(f"[TRANSLATE] Pre-generated transaction_id: {transaction_id}")
    print(f"Generated transaction ID: {transaction_id} (will be set in file metadata)")

    print(f"Created storage job: {storage_id}")
    if is_enterprise and company_name:
        print(f"Target folder: {company_name}/{request.email}/Temp/ (ID: {folder_id})")
    else:
        print(f"Target folder: {request.email}/Temp/ (ID: {folder_id})")
    print(f"Starting file uploads to Google Drive...")

    # Store files with enhanced metadata (no sessions)
    stored_files = []
    total_pages = 0

    for i, file_info in enumerate(request.files, 1):
        try:
            log_step(f"FILE {i} UPLOAD START", f"'{file_info.name}' ({file_info.size:,} bytes)")
            print(f"   Uploading file {i}/{len(request.files)}: '{file_info.name}'")

            # Decode base64 content from client
            import base64
            try:
                file_content = base64.b64decode(file_info.content)
                log_step(f"FILE {i} BASE64 DECODED", f"Decoded {len(file_content):,} bytes")
            except Exception as e:
                log_step(f"FILE {i} DECODE FAILED", f"Error: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to decode file content for '{file_info.name}': {str(e)}"
                )

            # Count pages for pricing (stub implementation)
            page_count = 1  # Default page count
            if file_info.name.lower().endswith('.pdf'):
                page_count = max(1, file_info.size // 50000)  # Estimate: 50KB per page
            elif file_info.name.lower().endswith(('.doc', '.docx')):
                page_count = max(1, file_info.size // 25000)  # Estimate: 25KB per page

            total_pages += page_count
            log_step(f"FILE {i} PAGE COUNT", f"{page_count} pages estimated")

            # Upload to Google Drive with metadata for customer linking (no sessions)
            log_step(f"FILE {i} GDRIVE UPLOAD", f"Uploading to folder {folder_id}")
            file_result = await google_drive_service.upload_file_to_folder(
                file_content=file_content,  # Use decoded base64 content
                filename=file_info.name,
                folder_id=folder_id,
                target_language=request.targetLanguage
            )
            log_step(f"FILE {i} GDRIVE UPLOADED", f"File ID: {file_result['file_id']}")

            # Update file with enhanced metadata for payment linking
            log_step(f"FILE {i} METADATA UPDATE", "Setting file properties")
            await google_drive_service.update_file_properties(
                file_id=file_result['file_id'],
                properties={
                    'customer_email': request.email,
                    'transaction_id': transaction_id,  # ✅ FIX: Add pre-generated transaction_id
                    'source_language': request.sourceLanguage,
                    'target_language': request.targetLanguage,
                    'page_count': str(page_count),
                    'status': 'awaiting_payment',
                    'upload_timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'original_filename': file_info.name
                }
            )
            log_step(f"FILE {i} COMPLETE", f"URL: {file_result.get('google_drive_url', 'N/A')}")

            stored_files.append({
                "file_id": file_result['file_id'],
                "filename": file_info.name,
                "status": "stored",
                "page_count": page_count,
                "size": file_info.size,
                "google_drive_url": file_result.get('google_drive_url')
            })
            print(f"   Successfully uploaded: '{file_info.name}' -> Google Drive ID: {file_result['file_id']}, Pages: {page_count}")

        except Exception as e:
            log_step(f"FILE {i} FAILED", f"Error: {str(e)}")
            print(f"   Failed to upload '{file_info.name}': {e}")
            stored_files.append({
                "file_id": None,
                "filename": file_info.name,
                "status": "failed",
                "page_count": 0,
                "size": file_info.size,
                "error": str(e)
            })

    # Summary of operation
    successful_uploads = len([f for f in stored_files if f["status"] == "stored"])
    failed_uploads = len([f for f in stored_files if f["status"] == "failed"])

    print(f"UPLOAD COMPLETE: {successful_uploads} successful, {failed_uploads} failed")
    print(f"Total pages for pricing: {total_pages}")
    print(f"Customer: {request.email} (no session needed)")
    print(f"Next step: Process payment, then webhook will move files from Temp to Inbox")

    # For enterprise customers, get subscription pricing
    transaction_ids = []  # Changed from transaction_id to transaction_ids (array)
    if is_enterprise:
        log_step("SUBSCRIPTION QUERY", f"Querying for company: {company_name}")
        logging.info(f"Querying subscription for company: {company_name}")
        from app.services.subscription_service import subscription_service
        from bson import ObjectId
        from datetime import datetime, timezone

        subscriptions = await subscription_service.get_company_subscriptions(
            company_name,
            active_only=True
        )

        if subscriptions and len(subscriptions) > 0:
            subscription = subscriptions[0]
            # Convert MongoDB Decimal128 to float (handles BSON decimal type)
            price_value = subscription.get("price_per_unit", 0.10)
            if hasattr(price_value, 'to_decimal'):  # It's a Decimal128 from MongoDB
                price_per_page = float(price_value.to_decimal())
            else:
                price_per_page = float(price_value)

            # Enhanced subscription logging - Find current active period
            # Database schema: subscription_units, used_units, promotional_units
            # Formula: total_remaining = (subscription_units + promotional_units) - used_units
            usage_periods = subscription.get("usage_periods", [])
            subscription_unit = subscription.get("subscription_unit", "page")
            status = subscription.get("status", "unknown")

            # Find current active period (same logic as subscription_service.py)
            now = datetime.now(timezone.utc)
            current_period = None
            current_period_idx = None

            for idx, period in enumerate(usage_periods):
                period_start = period.get("period_start")
                period_end = period.get("period_end")

                # Handle timezone-aware comparison
                if period_start and not period_start.tzinfo:
                    period_start = period_start.replace(tzinfo=timezone.utc)
                if period_end and not period_end.tzinfo:
                    period_end = period_end.replace(tzinfo=timezone.utc)

                if period_start and period_end and period_start <= now <= period_end:
                    current_period = period
                    current_period_idx = idx
                    break

            # Calculate availability from current active period only
            if current_period:
                subscription_units = current_period.get("subscription_units", 0)
                used_units = current_period.get("used_units", 0)
                promotional_units = current_period.get("promotional_units", 0)
                total_allocated = subscription_units + promotional_units
                total_used = used_units
                total_remaining = total_allocated - used_units
            else:
                # No active period found - cannot use subscription
                total_allocated = 0
                total_used = 0
                total_remaining = 0

            log_step("SUBSCRIPTION FOUND", f"Status: {status}, Price: ${price_per_page} per {subscription_unit}")
            logging.info(f"[SUBSCRIPTION] ✓ Active subscription found for company {company_name}")
            logging.info(f"[SUBSCRIPTION]   Subscription ID: {subscription.get('_id')}")
            logging.info(f"[SUBSCRIPTION]   Status: {status}")
            logging.info(f"[SUBSCRIPTION]   Price: ${price_per_page} per {subscription_unit}")

            if current_period:
                logging.info(f"[SUBSCRIPTION]   Current Period: {current_period_idx}")
                logging.info(f"[SUBSCRIPTION]   Period Start: {current_period.get('period_start')}")
                logging.info(f"[SUBSCRIPTION]   Period End: {current_period.get('period_end')}")
                logging.info(f"[SUBSCRIPTION]   Subscription Units: {subscription_units}")
                logging.info(f"[SUBSCRIPTION]   Promotional Units: {promotional_units}")
                logging.info(f"[SUBSCRIPTION]   Total Allocated: {total_allocated} {subscription_unit}s")
                logging.info(f"[SUBSCRIPTION]   Used Units: {total_used} {subscription_unit}s")
                logging.info(f"[SUBSCRIPTION]   Remaining Units: {total_remaining} {subscription_unit}s")

                print(f"\n📊 Current Subscription Period:")
                print(f"   Status: {status}")
                print(f"   Period: {current_period_idx} ({current_period.get('period_start')} to {current_period.get('period_end')})")
                print(f"   Subscription Units: {subscription_units} {subscription_unit}s")
                print(f"   Promotional Units: {promotional_units} {subscription_unit}s")
                print(f"   Total Allocated: {total_allocated} {subscription_unit}s")
                print(f"   Used Units: {total_used} {subscription_unit}s")
                print(f"   Remaining Units: {total_remaining} {subscription_unit}s")
                print(f"   Price: ${price_per_page} per {subscription_unit}")
            else:
                logging.warning(f"[SUBSCRIPTION] ⚠ No active period found for current date")
                print(f"\n⚠️  No active usage period for current date")
                print(f"   Total usage periods: {len(usage_periods)}")
        else:
            log_step("SUBSCRIPTION NOT FOUND", f"Using default pricing for company {company_name}")
            logging.warning(f"[SUBSCRIPTION] ⚠ No active subscription found for company {company_name}, using default pricing")
            print(f"\n⚠️  No active subscription found - will require payment")
            # Set default values for when subscription doesn't exist
            total_remaining = 0

    # Determine if payment is required based on enterprise subscription
    payment_required = True
    if is_enterprise and subscription:
        # Check if enterprise has enough units
        if total_remaining >= total_pages:
            payment_required = False
            log_step("PAYMENT BYPASS", f"Enterprise has {total_remaining} units remaining (needs {total_pages})")
            logging.info(f"[PAYMENT] ✓ Payment NOT required - using subscription units")
            logging.info(f"[PAYMENT]   Required: {total_pages} {subscription_unit}s")
            logging.info(f"[PAYMENT]   Available: {total_remaining} {subscription_unit}s")
            print(f"\n✅ Payment NOT required - using subscription units")
            print(f"   Required: {total_pages} {subscription_unit}s")
            print(f"   Available: {total_remaining} {subscription_unit}s")
        else:
            log_step("PAYMENT REQUIRED", f"Insufficient units: {total_remaining} remaining, {total_pages} needed")
            logging.warning(f"[PAYMENT] ⚠ Payment required - insufficient subscription units")
            logging.warning(f"[PAYMENT]   Required: {total_pages} {subscription_unit}s")
            logging.warning(f"[PAYMENT]   Available: {total_remaining} {subscription_unit}s")
            logging.warning(f"[PAYMENT]   Shortfall: {total_pages - total_remaining} {subscription_unit}s")
            print(f"\n⚠️  Payment required - insufficient subscription units")
            print(f"   Required: {total_pages} {subscription_unit}s")
            print(f"   Available: {total_remaining} {subscription_unit}s")
            print(f"   Shortfall: {total_pages - total_remaining} {subscription_unit}s")
    else:
        log_step("PAYMENT REQUIRED", "Individual customer or no subscription")
        logging.info(f"[PAYMENT] Payment required for {'individual customer' if not is_enterprise else 'enterprise without subscription'}")
        print(f"\n💳 Payment required: {'Individual customer' if not is_enterprise else 'Enterprise without subscription'}")

    # Create SINGLE BATCH transaction record for ALL uploaded files
    # ROOT CAUSE FIX: Instead of creating separate transactions per file (which caused 7 emails),
    # create ONE transaction with all files in documents[] array
    successful_stored_files = [f for f in stored_files if f["status"] == "stored"]

    if successful_stored_files:
        log_step(
            "BATCH TRANSACTION CREATE START",
            f"Creating SINGLE batch transaction for {len(successful_stored_files)} file(s)"
        )

        # Call batch function with ALL files at once
        # ✅ FIX: Pass pre-generated transaction_id (already set in file metadata)
        batch_transaction_id = await create_batch_transaction_record(
            files_info=successful_stored_files,
            user_data=current_user,
            request_data=request,
            subscription=subscription if is_enterprise else None,
            company_name=company_name if is_enterprise else None,
            price_per_page=price_per_page,
            transaction_id=transaction_id  # Use the same ID that's in file metadata
        )

        if batch_transaction_id:
            transaction_ids.append(batch_transaction_id)
            log_step(
                "BATCH TRANSACTION CREATED",
                f"ID: {batch_transaction_id} with {len(successful_stored_files)} document(s)"
            )
        else:
            log_step("BATCH TRANSACTION FAILED", "Failed to create batch transaction")

    log_step("TRANSACTION CREATE COMPLETE", f"Created {len(transaction_ids)} batch transaction(s)")

    # CRITICAL ASSERTION: Batch architecture creates exactly 1 transaction for N files
    # This ensures all files in the batch share the same transaction_id
    assert len(transaction_ids) == 1, (
        f"Batch transaction creation failed: Expected 1 transaction for {len(successful_stored_files)} files, "
        f"but got {len(transaction_ids)} transaction(s). This indicates a critical bug in create_batch_transaction_record()."
    )

    # Extract user information from JWT token (if authenticated)
    user_info = None
    if current_user:
        user_info = {
            "permission_level": current_user.get("permission_level", "user"),
            "email": current_user.get("email", request.email),
            "full_name": current_user.get("fullName") or current_user.get("user_name", "Unknown User")
        }
        log_step("USER INFO", f"Permission: {user_info['permission_level']}, Email: {user_info['email']}, Name: {user_info['full_name']}")
    else:
        # Individual user (not authenticated via corporate login)
        user_info = {
            "permission_level": "user",
            "email": request.email,
            "full_name": "Individual User"
        }
        log_step("USER INFO", "Individual user (no corporate authentication)")

    # Prepare and log response
    log_step("RESPONSE PREPARE", f"Success: {successful_uploads}/{len(request.files)} files, {total_pages} pages, ${total_pages * price_per_page:.2f}")

    # Extract uploaded file IDs for payment confirmation (frontend needs these)
    uploaded_file_ids = [f["file_id"] for f in stored_files if f["status"] == "stored" and f.get("file_id")]

    response_data = {
        "success": True,
        "data": {
            "id": storage_id,
            "status": "stored",
            "progress": 100,
            "message": f"Files uploaded successfully. Ready for payment.",
            # File IDs for payment confirmation (frontend sends these to /confirm)
            "uploaded_file_ids": uploaded_file_ids,

                # Pricing information
                "pricing": {
                    "total_pages": total_pages,
                    "price_per_page": price_per_page,  # Dynamic: subscription or default
                    "total_amount": total_pages * price_per_page,  # Dynamic calculation
                    "currency": "USD",
                    "customer_type": "enterprise" if is_enterprise else "individual",
                    "transaction_ids": transaction_ids  # Transaction IDs for all files
                },

                # File information
                "files": {
                    "total_files": len(request.files),
                    "successful_uploads": successful_uploads,
                    "failed_uploads": failed_uploads,
                    "stored_files": stored_files
                },

                # Customer information (used by payment webhook)
                "customer": {
                    "email": request.email,
                    "source_language": request.sourceLanguage,
                    "target_language": request.targetLanguage,
                    "temp_folder_id": folder_id
                },

                # Payment information
                "payment": {
                    "required": payment_required,  # Dynamic: based on subscription units
                    "amount_cents": int(total_pages * price_per_page * 100) if payment_required else 0,  # 0 if using subscription
                    "description": f"Translation service: {successful_uploads} files, {total_pages} pages",
                    "customer_email": request.email
                },

                # User information (permission level and identity)
                "user": user_info
            },
            "error": None
        }

    log_step("RESPONSE SENDING", "Returning response to client")

    # ============================================================================
    # RAW OUTGOING DATA - Logged before sending response
    # ============================================================================
    print("=" * 100)
    print("[RAW OUTGOING DATA] /translate RESPONSE - Sending to client")
    print(f"[RAW OUTGOING DATA] Success: {response_data['success']}")
    print(f"[RAW OUTGOING DATA] Storage ID: {response_data['data']['id']}")
    print(f"[RAW OUTGOING DATA] Status: {response_data['data']['status']}")
    print(f"[RAW OUTGOING DATA] Progress: {response_data['data']['progress']}%")
    print(f"[RAW OUTGOING DATA] Message: {response_data['data']['message']}")
    print(f"[RAW OUTGOING DATA] Pricing:")
    print(f"[RAW OUTGOING DATA]   - Total Pages: {response_data['data']['pricing']['total_pages']}")
    print(f"[RAW OUTGOING DATA]   - Price Per Page: ${response_data['data']['pricing']['price_per_page']}")
    print(f"[RAW OUTGOING DATA]   - Total Amount: ${response_data['data']['pricing']['total_amount']:.2f}")
    print(f"[RAW OUTGOING DATA]   - Currency: {response_data['data']['pricing']['currency']}")
    print(f"[RAW OUTGOING DATA]   - Customer Type: {response_data['data']['pricing']['customer_type']}")
    print(f"[RAW OUTGOING DATA]   - Transaction IDs ({len(response_data['data']['pricing']['transaction_ids'])}): {response_data['data']['pricing']['transaction_ids']}")
    print(f"[RAW OUTGOING DATA] Files:")
    print(f"[RAW OUTGOING DATA]   - Total Files: {response_data['data']['files']['total_files']}")
    print(f"[RAW OUTGOING DATA]   - Successful: {response_data['data']['files']['successful_uploads']}")
    print(f"[RAW OUTGOING DATA]   - Failed: {response_data['data']['files']['failed_uploads']}")
    for i, file in enumerate(response_data['data']['files']['stored_files'], 1):
        print(f"[RAW OUTGOING DATA]   File {i}: '{file['filename']}' | Status: {file['status']} | Pages: {file['page_count']} | GDrive: {file.get('google_drive_url', 'N/A')[:50]}...")
    print(f"[RAW OUTGOING DATA] Customer: {response_data['data']['customer']['email']}")
    print(f"[RAW OUTGOING DATA] Payment Required: {response_data['data']['payment']['required']}")
    print(f"[RAW OUTGOING DATA] Payment Amount (cents): {response_data['data']['payment']['amount_cents']}")
    print(f"[RAW OUTGOING DATA] User Information:")
    print(f"[RAW OUTGOING DATA]   - Permission Level: {response_data['data']['user']['permission_level']}")
    print(f"[RAW OUTGOING DATA]   - Email: {response_data['data']['user']['email']}")
    print(f"[RAW OUTGOING DATA]   - Full Name: {response_data['data']['user']['full_name']}")
    print("=" * 100)

    return JSONResponse(content=response_data)


# ============================================================================
# Transaction Confirmation/Decline Models
# ============================================================================
class TransactionConfirmRequest(BaseModel):
    """Request body for confirming Square payment - client sends payment info AND file_ids"""
    square_transaction_id: Optional[str] = Field(
        None,
        description="Square payment ID (optional reference) or 'NONE' if payment failed",
        example="sqt_3030c9a6c8c94a5180e2"
    )
    status: bool = Field(
        default=True,
        description="True if payment approved, False if failed"
    )
    transaction_id: Optional[str] = Field(
        None,
        description="Transaction ID from /translate-user (Individual flow only)",
        example="USER123456"
    )
    file_ids: List[str] = Field(
        default=[],
        description="List of Google Drive file IDs to process (from upload response). If empty, falls back to search (enterprise flow)",
        example=["1abc2def3ghi", "4jkl5mno6pqr"]
    )
    # NOTE:
    # - Individual flow: Client sends file_ids from upload response - server processes only those files
    # - Enterprise flow: Empty array - server falls back to search by email + status


class TransactionActionRequest(BaseModel):
    transaction_ids: List[str]


class EnterpriseConfirmRequest(BaseModel):
    """Enterprise confirmation - uses transaction_id only, no file search"""
    transaction_id: str = Field(..., description="Transaction ID from upload response")
    status: bool = Field(default=True, description="True=confirm, False=cancel")


class IndividualConfirmRequest(BaseModel):
    """Individual confirmation - includes payment info and file_ids from upload"""
    transaction_id: str = Field(..., description="Transaction ID from upload response")
    square_transaction_id: Optional[str] = Field(None, description="Square payment transaction ID")
    file_ids: List[str] = Field(..., description="File IDs from upload response - NO SEARCH")
    status: bool = Field(default=True, description="True=confirm, False=cancel")


# ============================================================================
# Background Task for Transaction Confirmation
# ============================================================================
async def process_transaction_confirmation_background(
    transaction_ids: List[str],
    customer_email: str,
    company_name: Optional[str],
    file_ids: List[str]
):
    """
    Background task to move files from Temp to Inbox and update transaction status.
    Runs asynchronously without blocking HTTP response.

    CRITICAL RACE CONDITION FIX:
    - Step 1 MUST add transaction_id metadata BEFORE moving files
    - GoogleTranslator watches Inbox and sends webhooks when files appear
    - If transaction_id is missing when files are moved, webhooks fail Pydantic validation
    - Solution: Add metadata first, then move files
    """
    import time
    task_start = time.time()

    try:
        from app.database import database
        from app.services.google_drive_service import google_drive_service
        from app.services.subscription_service import subscription_service
        from app.models.subscription import UsageUpdate
        from datetime import datetime, timezone

        print("\n" + "=" * 80)
        print("🔄 BACKGROUND TASK STARTED - Transaction Confirmation")
        print("=" * 80)
        print(f"⏱️  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📋 Task Details:")
        print(f"   Customer: {customer_email}")
        print(f"   Company: {company_name or 'Individual'}")
        print(f"   Transactions: {len(transaction_ids)}")
        print(f"   Files to move: {len(file_ids)}")
        print("=" * 80)

        # CRITICAL FIX: Add transaction_id metadata BEFORE moving files to Inbox
        # This prevents race condition where GoogleTranslator sends webhooks with missing transaction_id
        print(f"\n📝 Step 1: Adding transaction IDs to file metadata (BEFORE moving to Inbox)...")
        metadata_start = time.time()
        metadata_updates_successful = 0

        if transaction_ids:
            # Use the single batch transaction for all files
            batch_transaction_id = transaction_ids[0]
            print(f"   Using batch transaction ID: {batch_transaction_id}")

            for i, file_id in enumerate(file_ids):
                try:
                    # All files get the SAME batch transaction_id (not transaction_ids[i])
                    await google_drive_service.update_file_properties(
                        file_id=file_id,
                        properties={
                            'transaction_id': batch_transaction_id,
                            'status': 'confirmed',
                            'confirmation_timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')
                        }
                    )
                    metadata_updates_successful += 1
                    print(f"   ✓ File {file_id[:20]}...: Added transaction_id={batch_transaction_id}")
                except Exception as e:
                    print(f"   ⚠️  Failed to update metadata for file {file_id[:20]}...: {e}")
                    # Continue processing other files even if one fails
        else:
            print(f"   ⚠️  No batch transaction IDs found - skipping metadata update")

        metadata_elapsed = (time.time() - metadata_start) * 1000
        print(f"⏱️  Metadata update completed in {metadata_elapsed:.2f}ms")
        print(f"✅ Updated: {metadata_updates_successful}/{len(file_ids)} files")

        # NOW move files from Temp to Inbox (files now have transaction_id metadata)
        print(f"\n📁 Step 2: Moving files from Temp to Inbox (files now have transaction_id)...")
        move_start = time.time()
        move_result = await google_drive_service.move_files_to_inbox_on_payment_success(
            customer_email=customer_email,
            file_ids=file_ids,
            company_name=company_name
        )
        move_time = (time.time() - move_start) * 1000
        print(f"⏱️  File move completed in {move_time:.2f}ms")
        print(f"✅ Moved: {move_result['moved_successfully']}/{move_result['total_files']} files")

        # Verify files in Inbox
        print(f"\n🔍 Step 3: Verifying files in Inbox...")
        inbox_folder_id = move_result['inbox_folder_id']
        verified_count = 0

        for moved_file in move_result.get('moved_files', []):
            file_id = moved_file['file_id']
            try:
                file_info_raw = await asyncio.to_thread(
                    lambda: google_drive_service.service.files().get(
                        fileId=file_id,
                        fields='id,name,parents'
                    ).execute()
                )
                current_parents = file_info_raw.get('parents', [])
                is_in_inbox = inbox_folder_id in current_parents

                if is_in_inbox:
                    verified_count += 1
                    print(f"   ✅ File {file_id[:20]}... verified in Inbox")
                else:
                    print(f"   ⚠️  File {file_id[:20]}... NOT in Inbox")

            except Exception as e:
                print(f"   ❌ Failed to verify file {file_id[:20]}...: {e}")

        print(f"✅ Verified: {verified_count}/{len(move_result.get('moved_files', []))} files")

        # Update transaction status
        print(f"\n🔄 Step 4: Updating transaction status...")
        for txn_id in transaction_ids:
            await database.translation_transactions.update_one(
                {"transaction_id": txn_id},
                {
                    "$set": {
                        "status": "confirmed",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            print(f"   ✓ Transaction {txn_id} confirmed")

        # Update subscription usage
        print(f"\n💳 Step 5: Updating subscription usage...")
        transactions = []
        for txn_id in transaction_ids:
            txn = await database.translation_transactions.find_one({"transaction_id": txn_id})
            if txn:
                transactions.append(txn)

        subscription_updates = {}
        for txn in transactions:
            subscription_id = txn.get("subscription_id")
            units_count = txn.get("units_count", 0)

            if subscription_id and units_count > 0:
                sub_id_str = str(subscription_id)
                if sub_id_str not in subscription_updates:
                    subscription_updates[sub_id_str] = 0
                subscription_updates[sub_id_str] += units_count

        if subscription_updates:
            for subscription_id_str, total_units in subscription_updates.items():
                try:
                    usage_update = UsageUpdate(
                        units_to_add=total_units,
                        use_promotional_units=False
                    )
                    await subscription_service.record_usage(
                        subscription_id=subscription_id_str,
                        usage_data=usage_update
                    )
                    print(f"   ✅ Subscription {subscription_id_str}: +{total_units} units")
                except Exception as e:
                    print(f"   ⚠️  Subscription update failed for {subscription_id_str}: {e}")
        else:
            print(f"   ℹ️  No subscription updates needed (individual customer)")

        total_time = (time.time() - task_start) * 1000
        print(f"\n✅ BACKGROUND TASK COMPLETE")
        print(f"⏱️  TOTAL TASK TIME: {total_time:.2f}ms")
        print(f"📊 Results: {verified_count}/{len(file_ids)} files verified in Inbox")
        print("=" * 80 + "\n")

        logging.info(f"Background task completed for {customer_email}: {verified_count}/{len(file_ids)} files verified in {total_time:.2f}ms")

    except Exception as e:
        total_time = (time.time() - task_start) * 1000
        print(f"\n❌ BACKGROUND TASK ERROR")
        print(f"⏱️  Failed after: {total_time:.2f}ms")
        print(f"💥 Error type: {type(e).__name__}")
        print(f"💥 Error message: {str(e)}")
        print("=" * 80 + "\n")
        logging.error(f"Background confirmation error for {customer_email}: {e}", exc_info=True)


# ============================================================================
# Transaction Confirmation Endpoint
# ============================================================================
@app.post("/api/transactions/confirm", tags=["Transactions"])
async def confirm_transactions(
    request: TransactionConfirmRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    @deprecated Use /api/transactions/confirm-enterprise or /api/transactions/confirm-individual

    Confirm Square payment and update existing transaction OR delete files on failure.

    This endpoint:
    - IF payment succeeded (status=True):
      1. Find customer's files in Temp folder
      2. Find existing USER###### transaction by Square transaction ID
      3. Update transaction status to 'processing'
      4. Update file metadata with transaction_id
      5. Move files from Temp/ to Inbox/
      6. Return success with transaction_id (no duplicate creation)

    - IF payment failed (status=False):
      1. Find customer's files in Temp folder
      2. Delete all files
      3. Return failure message
    """
    logging.warning("DEPRECATED: Use /confirm-enterprise or /confirm-individual based on flow type")
    from datetime import datetime, timezone
    from app.utils.transaction_id_generator import generate_translation_transaction_id

    # ========== REQUEST VALIDATION LOGGING ==========
    print("\n" + "=" * 80)
    print("🔔 CONFIRM ENDPOINT - REQUEST RECEIVED")
    print("=" * 80)
    logging.info(f"[CONFIRM ENDPOINT] Request received at /api/transactions/confirm")

    print(f"✅ Pydantic body parsing completed successfully!")
    logging.info(f"[CONFIRM ENDPOINT] Pydantic validation passed")

    # ========== CLIENT REQUEST BODY VERIFICATION ==========
    print(f"\n📥 CLIENT REQUEST BODY (RAW):")
    request_dict = request.model_dump()
    print(f"   {request_dict}")

    # Detailed field verification
    print(f"\n🔍 FIELD VERIFICATION:")
    print(f"   transaction_id in request: {'YES ✅' if 'transaction_id' in request_dict and request_dict['transaction_id'] else 'NO ❌ MISSING!'}")
    print(f"   transaction_id value: {request_dict.get('transaction_id', 'NOT PROVIDED')}")
    print(f"   square_transaction_id: {request_dict.get('square_transaction_id', 'NOT PROVIDED')}")
    print(f"   file_ids: {request_dict.get('file_ids', 'NOT PROVIDED')}")
    print(f"   status: {request_dict.get('status', 'NOT PROVIDED')}")

    logging.info(f"[CONFIRM ENDPOINT] Client sent: {request_dict}")
    logging.info(f"[CONFIRM ENDPOINT] transaction_id present: {'YES' if request_dict.get('transaction_id') else 'NO'}")

    print(f"\n📋 Request Details:")
    print(f"   Square Transaction ID: {request.square_transaction_id}")
    print(f"   Payment Status: {'APPROVED ✅' if request.status else 'FAILED ❌'}")
    print(f"   Request Type: {type(request).__name__}")
    print(f"   Status Type: {type(request.status).__name__} = {request.status}")
    logging.info(f"[CONFIRM ENDPOINT] square_transaction_id={request.square_transaction_id}, status={request.status}")

    print(f"👤 Current User:")
    print(f"   Email: {current_user.get('email')}")
    print(f"   User ID: {current_user.get('sub', 'N/A')}")
    print("=" * 80 + "\n")
    logging.info(f"[CONFIRM ENDPOINT] Authenticated user: {current_user.get('email')}")

    from app.database import database
    from app.services.google_drive_service import google_drive_service

    customer_email = current_user.get("email")

    try:
        # ========== SUCCESS FLOW: Payment Approved ==========
        if request.status:
            print("\n" + "=" * 80)
            print("✅ SUCCESS FLOW - Payment Approved")
            print("=" * 80)
            print(f"📧 Customer Email: {customer_email}")
            print(f"💳 Square Transaction ID: {request.square_transaction_id}")
            logging.info(f"[CONFIRM] Payment APPROVED for {customer_email}, square_txn={request.square_transaction_id}")

            # 1. Fetch files: either by ID (Individual) or by search (Enterprise)
            if request.file_ids:
                # INDIVIDUAL FLOW: Fetch specific files by ID (from upload response)
                print(f"\n📁 Step 1/6: Fetching files by ID (Individual flow)...")
                print(f"   File IDs to process: {request.file_ids}")
                logging.info(f"[CONFIRM] Individual flow: Fetching {len(request.file_ids)} files by ID for {customer_email}")

                files_in_temp = []
                for i, file_id in enumerate(request.file_ids, 1):
                    try:
                        print(f"   Fetching file {i}/{len(request.file_ids)}: {file_id}...")
                        file_info = await google_drive_service.get_file_by_id(file_id)

                        # Security: Verify file belongs to this user
                        if file_info.get('customer_email') != customer_email:
                            error_msg = f"File {file_id} does not belong to you"
                            print(f"   🚫 SECURITY VIOLATION: {error_msg}")
                            logging.error(f"[CONFIRM] Security violation: {error_msg}")
                            raise HTTPException(
                                status_code=403,
                                detail=error_msg
                            )

                        # Verify file is awaiting payment
                        file_status = file_info.get('status')
                        if file_status != 'awaiting_payment':
                            error_msg = f"File {file_id} is not awaiting payment (status: {file_status})"
                            print(f"   ❌ INVALID STATUS: {error_msg}")
                            logging.error(f"[CONFIRM] Invalid file status: {error_msg}")
                            raise HTTPException(
                                status_code=400,
                                detail=error_msg
                            )

                        files_in_temp.append(file_info)
                        print(f"   ✅ File {i}: {file_info.get('filename')}")
                        logging.info(f"[CONFIRM] File {i} fetched: {file_info.get('filename')}")
                    except HTTPException:
                        raise
                    except Exception as e:
                        error_msg = f"Failed to fetch file {file_id}: {str(e)}"
                        print(f"   ❌ ERROR: {error_msg}")
                        logging.error(f"[CONFIRM] File fetch error: {error_msg}", exc_info=True)
                        raise HTTPException(
                            status_code=500,
                            detail=error_msg
                        )

                print(f"   ✅ Successfully fetched {len(files_in_temp)} file(s)")
                for i, file_info in enumerate(files_in_temp, 1):
                    print(f"      File {i}: {file_info.get('filename')} (ID: {file_info.get('file_id', 'N/A')[:20]}...)")
                logging.info(f"[CONFIRM] All files fetched: {[f.get('filename') for f in files_in_temp]}")

            else:
                # ENTERPRISE FLOW: Search by email + status (backward compatible)
                print(f"\n📁 Step 1/6: Searching for files (Enterprise flow)...")
                print(f"   Searching for: customer_email={customer_email}, status=awaiting_payment")
                logging.info(f"[CONFIRM] Enterprise flow: Searching Temp folder for {customer_email} with status=awaiting_payment")

                try:
                    files_in_temp = await google_drive_service.find_files_by_customer_email(
                        customer_email=customer_email,
                        status="awaiting_payment"
                    )
                    print(f"   ✅ Search completed successfully")
                    logging.info(f"[CONFIRM] File search completed, found {len(files_in_temp) if files_in_temp else 0} files")
                except Exception as e:
                    print(f"   ❌ File search failed: {e}")
                    logging.error(f"[CONFIRM] File search error: {e}", exc_info=True)
                    raise

                if not files_in_temp:
                    print(f"   ❌ No files found in Temp folder for {customer_email}")
                    logging.warning(f"[CONFIRM] No files found in Temp for {customer_email}")
                    raise HTTPException(
                        status_code=404,
                        detail=f"No files found in Temp folder for customer {customer_email}"
                    )

                print(f"   ✅ Found {len(files_in_temp)} file(s) in Temp folder")
                for i, file_info in enumerate(files_in_temp, 1):
                    print(f"      File {i}: {file_info.get('filename')} (ID: {file_info.get('file_id', 'N/A')[:20]}...)")
                logging.info(f"[CONFIRM] Found {len(files_in_temp)} files: {[f.get('filename') for f in files_in_temp]}")

            # 2. Get transaction_id from request (UNIFIED - Both Individual and Enterprise)
            print(f"\n🔍 Step 2/6: Getting transaction ID...")
            from bson.decimal128 import Decimal128
            from decimal import Decimal

            # Validate authentication
            if not current_user:
                error_msg = "Authentication required: current_user is None"
                print(f"   ❌ CRITICAL: {error_msg}")
                logging.error(f"[CONFIRM] {error_msg}. This should not happen - check auth middleware.")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required. Please log in again."
                )

            # Validate customer_email exists
            customer_email = current_user.get("email")
            if not customer_email:
                error_msg = "Invalid JWT: missing email field"
                print(f"   ❌ CRITICAL: {error_msg}")
                logging.error(f"[CONFIRM] {error_msg}. JWT: {current_user}")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication token. Please log in again."
                )

            print(f"   ✅ Authenticated user: {customer_email}")
            logging.info(f"[CONFIRM] User authenticated: {customer_email}")

            # transaction_id is REQUIRED - frontend must send it from stored state
            if not request.transaction_id:
                error_msg = (
                    "transaction_id is required. Frontend must send the transaction_id "
                    "that was returned from /translate-user and stored in browser state."
                )
                print(f"   ❌ {error_msg}")
                logging.error(f"[CONFIRM] {error_msg}")
                raise HTTPException(
                    status_code=400,
                    detail="transaction_id is required"
                )

            transaction_id = request.transaction_id
            print(f"   ✅ Using transaction_id from request: {transaction_id}")
            logging.info(f"[CONFIRM] Using transaction_id from request: {transaction_id}")

            # Determine flow type and collection based on company_name in JWT
            company_name = current_user.get("company_name")
            is_enterprise = company_name is not None and company_name != ""

            if is_enterprise:
                # Verify company exists in database
                company_doc = await database.company.find_one({"company_name": company_name})

                if not company_doc:
                    error_msg = f"Invalid company '{company_name}' in JWT token"
                    print(f"   🚫 SECURITY: {error_msg}")
                    logging.error(f"[CONFIRM] {error_msg} for user {customer_email}")
                    raise HTTPException(
                        status_code=403,
                        detail="Invalid company credentials. Please re-authenticate."
                    )

                print(f"   ✅ Company validated: {company_name}")
                logging.info(f"[CONFIRM] Company validation passed: {company_name}")

                collection = database.translation_transactions
                flow_type = "Enterprise"
                print(f"   Flow: {flow_type} (Company: {company_name})")
                logging.info(f"[CONFIRM] Enterprise flow detected: {company_name}")
            else:
                collection = database.user_transactions
                flow_type = "Individual"
                print(f"   Flow: {flow_type}")
                logging.info(f"[CONFIRM] Individual flow detected")

            # Find existing transaction in appropriate collection
            existing_transaction = await collection.find_one({
                "transaction_id": transaction_id
            })

            if not existing_transaction:
                error_msg = f"No transaction found with transaction_id={transaction_id} in {collection.name}"
                print(f"   ❌ {error_msg}")
                logging.error(f"[CONFIRM] {error_msg}")
                raise HTTPException(
                    status_code=404,
                    detail=error_msg
                )

            print(f"   ✅ Found transaction in {collection.name}")
            logging.info(f"[CONFIRM] Found transaction {transaction_id} in {collection.name}")

            # Authorization check: Verify user has permission to access this transaction
            print(f"\n🔒 Verifying authorization...")

            if is_enterprise:
                # Enterprise: Verify transaction belongs to user's company
                txn_company = existing_transaction.get("company_name")

                if txn_company != company_name:
                    error_msg = (
                        f"Authorization denied: User from company '{company_name}' "
                        f"attempted to access transaction from company '{txn_company}'"
                    )
                    print(f"   🚫 {error_msg}")
                    logging.error(f"[CONFIRM] SECURITY VIOLATION: {error_msg}. User: {customer_email}, Transaction: {transaction_id}")
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have permission to access this transaction"
                    )

                print(f"   ✅ Authorization passed: Company '{company_name}' owns transaction")
                logging.info(f"[CONFIRM] Authorization verified: {company_name} accessing {transaction_id}")

            else:
                # Individual: Verify transaction belongs to current user
                txn_user = (existing_transaction.get("user_id") or existing_transaction.get("user_email") or "").lower()
                current_email = (customer_email or "").lower()

                if not txn_user or txn_user != current_email:
                    error_msg = (
                        f"Authorization denied: User '{customer_email}' "
                        f"attempted to access transaction from user '{txn_user}'"
                    )
                    print(f"   🚫 {error_msg}")
                    logging.error(f"[CONFIRM] SECURITY VIOLATION: {error_msg}. Transaction: {transaction_id}")
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have permission to access this transaction"
                    )

                print(f"   ✅ Authorization passed: User '{customer_email}' owns transaction")
                logging.info(f"[CONFIRM] Authorization verified: {customer_email} accessing {transaction_id}")

            # Extract metadata with explicit flow-based field access
            if is_enterprise:
                total_units = existing_transaction.get("units_count")
                total_price_raw = existing_transaction.get("total_price")
                units_field = "units_count"
                price_field = "total_price"
            else:
                total_units = existing_transaction.get("number_of_units")
                total_price_raw = existing_transaction.get("total_cost")
                units_field = "number_of_units"
                price_field = "total_cost"

            # Validate required fields exist
            if total_units is None:
                error_msg = f"Transaction {transaction_id} missing required field '{units_field}'"
                print(f"   ❌ {error_msg}")
                logging.error(f"[CONFIRM] {error_msg}. Flow: {flow_type}, Collection: {collection.name}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Transaction data incomplete: missing {units_field}"
                )

            if total_price_raw is None:
                error_msg = f"Transaction {transaction_id} missing required field '{price_field}'"
                print(f"   ❌ {error_msg}")
                logging.error(f"[CONFIRM] {error_msg}. Flow: {flow_type}, Collection: {collection.name}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Transaction data incomplete: missing {price_field}"
                )

            # Convert Decimal128 to float (handle MongoDB numeric type)
            total_price = float(total_price_raw) if isinstance(total_price_raw, Decimal128) else float(total_price_raw)

            print(f"   Transaction details:")
            print(f"      Transaction ID: {transaction_id}")
            print(f"      Total Units: {total_units} (field: {units_field})")
            print(f"      Total Price: ${total_price} (field: {price_field})")
            logging.info(
                f"[CONFIRM] Transaction details: id={transaction_id}, units={total_units}, "
                f"price=${total_price}, flow={flow_type}, fields=({units_field}, {price_field})"
            )

            # 3. Update transaction with payment/approval confirmation
            print(f"\n💾 Step 3/6: Updating transaction ({flow_type})...")
            try:
                update_fields = {
                    "status": "processing",
                    "updated_at": datetime.now(timezone.utc)
                }

                # Add payment/approval fields based on flow type
                if is_enterprise:
                    update_fields["approval_status"] = "APPROVED"
                    update_fields["approved_at"] = datetime.now(timezone.utc)
                    print(f"   Setting approval_status=APPROVED")
                else:
                    update_fields["square_payment_id"] = request.square_transaction_id
                    update_fields["payment_status"] = "COMPLETED"
                    update_fields["payment_date"] = datetime.now(timezone.utc)
                    print(f"   Setting payment_status=COMPLETED, square_payment_id={request.square_transaction_id}")

                update_result = await collection.update_one(
                    {"transaction_id": transaction_id},
                    {"$set": update_fields}
                )

                if update_result.modified_count > 0:
                    print(f"   ✅ Transaction updated")
                    logging.info(f"[CONFIRM] Transaction {transaction_id} updated successfully")
                else:
                    print(f"   ⚠️  Transaction not updated (may already be updated)")
                    logging.warning(f"[CONFIRM] Transaction {transaction_id} not modified")

            except Exception as e:
                print(f"   ❌ Failed to update transaction: {e}")
                logging.error(f"[CONFIRM] Transaction update error: {e}", exc_info=True)
                # Don't raise - continue with file operations

            # 4. Update file metadata
            print(f"\n🏷️  Step 4/6: Updating file metadata...")
            metadata_success_count = 0
            metadata_fail_count = 0

            for i, file_info in enumerate(files_in_temp, 1):
                file_id = file_info.get('file_id')
                filename = file_info.get('filename', 'unknown')

                if file_id:
                    try:
                        print(f"   Updating file {i}/{len(files_in_temp)}: {filename[:40]}...")
                        metadata = {
                            'transaction_id': transaction_id,
                            'status': 'processing'
                        }

                        # Add flow-specific timestamp
                        if is_enterprise:
                            metadata['approved_at'] = datetime.now(timezone.utc).isoformat()
                        else:
                            metadata['payment_date'] = datetime.now(timezone.utc).isoformat()

                        await google_drive_service.update_file_metadata(
                            file_id=file_id,
                            metadata=metadata
                        )
                        metadata_success_count += 1
                        print(f"   ✓ Metadata updated for {filename[:40]}")
                    except Exception as e:
                        metadata_fail_count += 1
                        print(f"   ✗ Failed to update metadata for {filename[:40]}: {e}")
                        logging.error(f"[CONFIRM] Metadata update failed for {file_id}: {e}")

            print(f"   ✅ Updated {metadata_success_count}/{len(files_in_temp)} files")
            logging.info(f"[CONFIRM] Metadata updates: {metadata_success_count}/{len(files_in_temp)} succeeded")

            # 5. Move files from Temp to Inbox
            print(f"\n📂 Step 5/6: Moving files from Temp to Inbox...")
            file_ids_to_move = [file_info.get('file_id') for file_info in files_in_temp if file_info.get('file_id')]

            print(f"   Files to move: {len(file_ids_to_move)}")
            moved_count = 0
            if file_ids_to_move:
                try:
                    move_result = await google_drive_service.move_files_to_inbox_on_payment_success(
                        customer_email=customer_email,
                        file_ids=file_ids_to_move,
                        company_name=company_name if is_enterprise else None
                    )

                    moved_count = move_result.get('moved_successfully', 0)
                    failed_count = move_result.get('failed_moves', 0)

                    print(f"   ✅ Files moved: {moved_count} succeeded, {failed_count} failed")
                    logging.info(f"[CONFIRM] File movement: {moved_count}/{len(file_ids_to_move)} succeeded")

                    if failed_count > 0:
                        print(f"   ⚠️  WARNING: {failed_count} files failed to move")
                        logging.warning(f"[CONFIRM] {failed_count} files failed to move")
                except Exception as e:
                    print(f"   ❌ File movement failed: {e}")
                    logging.error(f"[CONFIRM] File movement error: {e}", exc_info=True)
                    raise

            print(f"\n✅ CONFIRMATION COMPLETE ({flow_type})")
            print(f"   Transaction ID: {transaction_id}")
            print(f"   Files processed: {len(files_in_temp)}")
            print(f"   Total amount: ${total_price}")
            if is_enterprise:
                print(f"   Company: {company_name}")
            print("=" * 80 + "\n")

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Transaction confirmed successfully",
                    "data": {
                        "transaction_id": transaction_id,
                        "confirmed_transactions": 1,
                        "moved_files": moved_count,
                        "total_amount": total_price,
                        "company_name": company_name,
                        "customer_email": customer_email,
                        "flow_type": flow_type
                    }
                }
            )

        # ========== FAILURE FLOW: Payment Failed ==========
        else:
            print("\n" + "=" * 80)
            print("❌ FAILURE FLOW - Payment Failed")
            print("=" * 80)
            print(f"📧 Customer Email: {customer_email}")
            print(f"💳 Square Transaction ID: {request.square_transaction_id}")
            logging.info(f"[CONFIRM] Payment FAILED for {customer_email}, square_txn={request.square_transaction_id}")

            # Find and delete files in Temp folder
            print(f"\n🗑️  Searching for files to delete...")
            try:
                files_in_temp = await google_drive_service.find_files_by_customer_email(
                    customer_email=customer_email,
                    status="awaiting_payment"
                )
                print(f"   Found {len(files_in_temp) if files_in_temp else 0} files to delete")
            except Exception as e:
                print(f"   ❌ File search failed: {e}")
                logging.error(f"[CONFIRM] File search error: {e}", exc_info=True)
                raise

            if files_in_temp:
                file_ids_to_delete = [f.get('file_id') for f in files_in_temp if f.get('file_id')]
                print(f"   Deleting {len(file_ids_to_delete)} files...")

                try:
                    delete_result = await google_drive_service.delete_files_on_payment_failure(
                        customer_email=customer_email,
                        file_ids=file_ids_to_delete
                    )
                    deleted_count = delete_result.get('deleted_successfully', 0)
                    print(f"   ✅ Deleted {deleted_count} files")
                    logging.info(f"[CONFIRM] Deleted {deleted_count} files after payment failure")
                except Exception as e:
                    print(f"   ❌ File deletion failed: {e}")
                    logging.error(f"[CONFIRM] File deletion error: {e}", exc_info=True)

            print("\n❌ PAYMENT FAILED - Files deleted")
            print("=" * 80 + "\n")

            return JSONResponse(
                status_code=200,
                content={
                    "success": False,
                    "message": "Payment failed. Files have been deleted.",
                    "data": {
                        "deleted_files": len(files_in_temp) if files_in_temp else 0,
                        "customer_email": customer_email
                    }
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        logging.error(f"[CONFIRM] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# Enterprise Transaction Confirmation Endpoint
# ============================================================================
@app.post("/api/transactions/confirm-enterprise", tags=["Transactions"])
async def confirm_enterprise_transaction(
    request: EnterpriseConfirmRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Confirm Enterprise transaction (no payment, no file search).

    This endpoint:
    - Validates user is Enterprise (has company_name in JWT)
    - Finds transaction by transaction_id in translation_transactions collection
    - Verifies transaction belongs to user's company
    - Gets file_ids from transaction.documents field (NO SEARCH)
    - If status=True: Moves files Temp → Inbox, updates transaction to 'processing'
    - If status=False: Deletes files from Temp, updates transaction to 'cancelled'
    """
    from app.database import database
    from app.services.google_drive_service import google_drive_service
    from datetime import datetime, timezone

    logging.info(f"[CONFIRM-ENTERPRISE] Request received for transaction {request.transaction_id}")

    # Extract user info from JWT
    user_email = current_user.get("email")
    company_name = current_user.get("company_name")

    # Validate user is Enterprise
    if not company_name:
        logging.error(f"[CONFIRM-ENTERPRISE] User {user_email} is not Enterprise (no company_name)")
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only for Enterprise users"
        )

    logging.info(f"[CONFIRM-ENTERPRISE] User {user_email}, Company {company_name}")

    try:
        # Find transaction by transaction_id
        transaction = await database.translation_transactions.find_one({
            "transaction_id": request.transaction_id
        })

        if not transaction:
            logging.error(f"[CONFIRM-ENTERPRISE] Transaction {request.transaction_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Transaction {request.transaction_id} not found"
            )

        # Verify transaction belongs to user's company
        if transaction.get("company_name") != company_name:
            logging.error(
                f"[CONFIRM-ENTERPRISE] Transaction {request.transaction_id} belongs to "
                f"{transaction.get('company_name')}, not {company_name}"
            )
            raise HTTPException(
                status_code=403,
                detail="Transaction does not belong to your company"
            )

        # Get file_ids from transaction.documents (NO SEARCH)
        documents = transaction.get("documents", [])

        logging.info(f"[CONFIRM-ENTERPRISE] Transaction raw data: {json.dumps(serialize_transaction_for_json(transaction.copy()), indent=2, default=str)}")
        logging.info(f"[CONFIRM-ENTERPRISE] Documents array: {json.dumps(documents, indent=2, default=str)}")

        if not documents:
            logging.error(f"[CONFIRM-ENTERPRISE] Transaction has no documents array")
            logging.error(f"[CONFIRM-ENTERPRISE] Available keys: {list(transaction.keys())}")
            raise HTTPException(
                status_code=400,
                detail="Transaction has no documents"
            )

        file_ids = [doc.get("file_id") for doc in documents if doc.get("file_id")]

        logging.info(f"[CONFIRM-ENTERPRISE] Extracted file_ids: {file_ids}")
        logging.info(f"[CONFIRM-ENTERPRISE] File_ids count: {len(file_ids)}")

        if not file_ids:
            logging.error(f"[CONFIRM-ENTERPRISE] No file_ids found in documents")
            logging.error(f"[CONFIRM-ENTERPRISE] Documents structure: {json.dumps(documents, indent=2, default=str)}")

            # Check if original_url exists as fallback
            original_urls = [doc.get("original_url") for doc in documents if doc.get("original_url")]

            if original_urls:
                logging.warning(f"[CONFIRM-ENTERPRISE] Found {len(original_urls)} original_urls, attempting to extract file_ids")

                # Extract file_ids from URLs
                import re
                extracted_count = 0
                for doc in documents:
                    url = doc.get("original_url", "")
                    if url and not doc.get("file_id"):
                        # URL format: https://docs.google.com/document/d/FILE_ID/...
                        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
                        if match:
                            extracted_file_id = match.group(1)
                            doc["file_id"] = extracted_file_id  # Add to document
                            file_ids.append(extracted_file_id)
                            extracted_count += 1
                            logging.info(f"[CONFIRM-ENTERPRISE] Extracted file_id {extracted_file_id} from URL: {url}")

                if file_ids:
                    # Update transaction with extracted file_ids
                    await database.translation_transactions.update_one(
                        {"transaction_id": request.transaction_id},
                        {"$set": {"documents": documents}}
                    )
                    logging.info(f"[CONFIRM-ENTERPRISE] Updated transaction with {extracted_count} extracted file_ids")
                    logging.info(f"[CONFIRM-ENTERPRISE] Final file_ids list: {file_ids}")

            if not file_ids:
                logging.error(f"[CONFIRM-ENTERPRISE] Failed to extract any file_ids from URLs")
                raise HTTPException(
                    status_code=400,
                    detail="Transaction documents have no file_ids and cannot extract from URLs"
                )

        logging.info(f"[CONFIRM-ENTERPRISE] Found {len(file_ids)} files in transaction")

        # ========== SUCCESS FLOW: Confirm ==========
        if request.status:
            logging.info(f"[CONFIRM-ENTERPRISE] Confirming transaction {request.transaction_id}")

            # Update transaction status to 'processing'
            await database.translation_transactions.update_one(
                {"transaction_id": request.transaction_id},
                {
                    "$set": {
                        "status": "processing",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logging.info(f"[CONFIRM-ENTERPRISE] Updated transaction status to 'processing'")

            # Update file metadata with transaction_id
            for file_id in file_ids:
                try:
                    await google_drive_service.update_file_metadata(
                        file_id=file_id,
                        metadata={"transaction_id": request.transaction_id}
                    )
                    logging.info(f"[CONFIRM-ENTERPRISE] Updated metadata for file {file_id}")
                except Exception as e:
                    logging.error(f"[CONFIRM-ENTERPRISE] Failed to update metadata for {file_id}: {e}")

            # Move files from Temp to Inbox
            try:
                customer_email = transaction.get("user_id")  # user_id contains the email address
                move_result = await google_drive_service.move_files_to_inbox_on_payment_success(
                    customer_email=customer_email,
                    file_ids=file_ids,
                    company_name=company_name
                )

                moved_count = move_result.get('moved_successfully', 0)
                failed_count = move_result.get('failed_moves', 0)

                logging.info(f"[CONFIRM-ENTERPRISE] Moved {moved_count}/{len(file_ids)} files successfully")

                if failed_count > 0:
                    logging.warning(f"[CONFIRM-ENTERPRISE] {failed_count} files failed to move")

                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Enterprise transaction confirmed successfully",
                        "data": {
                            "transaction_id": request.transaction_id,
                            "moved_files": moved_count,
                            "failed_files": failed_count,
                            "total_files": len(file_ids),
                            "company_name": company_name
                        }
                    }
                )

            except Exception as e:
                logging.error(f"[CONFIRM-ENTERPRISE] File movement failed: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to move files: {str(e)}"
                )

        # ========== CANCEL FLOW: Delete files ==========
        else:
            logging.info(f"[CONFIRM-ENTERPRISE] Cancelling transaction {request.transaction_id}")

            # Update transaction status to 'cancelled'
            await database.translation_transactions.update_one(
                {"transaction_id": request.transaction_id},
                {
                    "$set": {
                        "status": "cancelled",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logging.info(f"[CONFIRM-ENTERPRISE] Updated transaction status to 'cancelled'")

            # Delete files from Temp
            deleted_count = 0
            for file_id in file_ids:
                try:
                    await google_drive_service.delete_file(file_id)
                    deleted_count += 1
                    logging.info(f"[CONFIRM-ENTERPRISE] Deleted file {file_id}")
                except Exception as e:
                    logging.error(f"[CONFIRM-ENTERPRISE] Failed to delete file {file_id}: {e}")

            logging.info(f"[CONFIRM-ENTERPRISE] Deleted {deleted_count}/{len(file_ids)} files")

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Enterprise transaction cancelled, files deleted",
                    "data": {
                        "transaction_id": request.transaction_id,
                        "deleted_files": deleted_count,
                        "total_files": len(file_ids),
                        "company_name": company_name
                    }
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[CONFIRM-ENTERPRISE] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# Individual Transaction Confirmation Endpoint
# ============================================================================
@app.post("/api/transactions/confirm-individual", tags=["Transactions"])
async def confirm_individual_transaction(
    request: IndividualConfirmRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Confirm Individual transaction with payment (no file search).

    This endpoint:
    - Validates user is Individual (no company_name in JWT)
    - Finds transaction by transaction_id in user_transactions collection
    - Verifies transaction belongs to current user
    - Uses file_ids from request (NO SEARCH)
    - If status=True: Stores square_transaction_id, moves files Temp → Inbox, updates transaction to 'completed'
    - If status=False: Deletes files from Temp, updates transaction to 'cancelled'
    """
    from app.database import database
    from app.services.google_drive_service import google_drive_service
    from datetime import datetime, timezone

    logging.info(f"[CONFIRM-INDIVIDUAL] Request received for transaction {request.transaction_id}")

    # Extract user info from JWT
    user_email = current_user.get("email")
    company_name = current_user.get("company_name")

    # Validate user is Individual (no company_name)
    if company_name:
        logging.error(f"[CONFIRM-INDIVIDUAL] User {user_email} is Enterprise (has company_name: {company_name})")
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only for Individual users"
        )

    logging.info(f"[CONFIRM-INDIVIDUAL] User {user_email}")

    try:
        # Find transaction by transaction_id
        transaction = await database.user_transactions.find_one({
            "transaction_id": request.transaction_id
        })

        if not transaction:
            logging.error(f"[CONFIRM-INDIVIDUAL] Transaction {request.transaction_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Transaction {request.transaction_id} not found"
            )

        # Verify transaction belongs to current user
        if transaction.get("user_email") != user_email:
            logging.error(
                f"[CONFIRM-INDIVIDUAL] Transaction {request.transaction_id} belongs to "
                f"{transaction.get('user_email')}, not {user_email}"
            )
            raise HTTPException(
                status_code=403,
                detail="Transaction does not belong to your account"
            )

        # Use file_ids from request (NO SEARCH)
        file_ids = request.file_ids
        if not file_ids:
            logging.error(f"[CONFIRM-INDIVIDUAL] No file_ids provided in request")
            raise HTTPException(
                status_code=400,
                detail="file_ids are required"
            )

        logging.info(f"[CONFIRM-INDIVIDUAL] Processing {len(file_ids)} files from request")

        # ========== SUCCESS FLOW: Confirm with payment ==========
        if request.status:
            logging.info(f"[CONFIRM-INDIVIDUAL] Confirming transaction {request.transaction_id}")

            # Update transaction with square_transaction_id and status
            update_data = {
                "status": "completed",
                "updated_at": datetime.now(timezone.utc)
            }
            if request.square_transaction_id:
                update_data["square_transaction_id"] = request.square_transaction_id
                logging.info(f"[CONFIRM-INDIVIDUAL] Storing Square transaction ID: {request.square_transaction_id}")

            await database.user_transactions.update_one(
                {"transaction_id": request.transaction_id},
                {"$set": update_data}
            )
            logging.info(f"[CONFIRM-INDIVIDUAL] Updated transaction status to 'completed'")

            # Update file metadata with transaction_id
            for file_id in file_ids:
                try:
                    await google_drive_service.update_file_metadata(
                        file_id=file_id,
                        metadata={"transaction_id": request.transaction_id}
                    )
                    logging.info(f"[CONFIRM-INDIVIDUAL] Updated metadata for file {file_id}")
                except Exception as e:
                    logging.error(f"[CONFIRM-INDIVIDUAL] Failed to update metadata for {file_id}: {e}")

            # Move files from Temp to Inbox
            try:
                move_result = await google_drive_service.move_files_to_inbox_on_payment_success(
                    customer_email=user_email,
                    file_ids=file_ids,
                    company_name=None  # Individual users have no company
                )

                moved_count = move_result.get('moved_successfully', 0)
                failed_count = move_result.get('failed_moves', 0)

                logging.info(f"[CONFIRM-INDIVIDUAL] Moved {moved_count}/{len(file_ids)} files successfully")

                if failed_count > 0:
                    logging.warning(f"[CONFIRM-INDIVIDUAL] {failed_count} files failed to move")

                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": "Individual transaction confirmed successfully",
                        "data": {
                            "transaction_id": request.transaction_id,
                            "square_transaction_id": request.square_transaction_id,
                            "moved_files": moved_count,
                            "failed_files": failed_count,
                            "total_files": len(file_ids)
                        }
                    }
                )

            except Exception as e:
                logging.error(f"[CONFIRM-INDIVIDUAL] File movement failed: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to move files: {str(e)}"
                )

        # ========== CANCEL FLOW: Delete files ==========
        else:
            logging.info(f"[CONFIRM-INDIVIDUAL] Cancelling transaction {request.transaction_id}")

            # Update transaction status to 'cancelled'
            await database.user_transactions.update_one(
                {"transaction_id": request.transaction_id},
                {
                    "$set": {
                        "status": "cancelled",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logging.info(f"[CONFIRM-INDIVIDUAL] Updated transaction status to 'cancelled'")

            # Delete files from Temp
            deleted_count = 0
            for file_id in file_ids:
                try:
                    await google_drive_service.delete_file(file_id)
                    deleted_count += 1
                    logging.info(f"[CONFIRM-INDIVIDUAL] Deleted file {file_id}")
                except Exception as e:
                    logging.error(f"[CONFIRM-INDIVIDUAL] Failed to delete file {file_id}: {e}")

            logging.info(f"[CONFIRM-INDIVIDUAL] Deleted {deleted_count}/{len(file_ids)} files")

            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Individual transaction cancelled, files deleted",
                    "data": {
                        "transaction_id": request.transaction_id,
                        "deleted_files": deleted_count,
                        "total_files": len(file_ids)
                    }
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[CONFIRM-INDIVIDUAL] Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ============================================================================
# Transaction Decline Endpoint
# ============================================================================
@app.post("/api/transactions/decline", tags=["Transactions"])
async def decline_transactions(
    request: TransactionActionRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Decline transactions and delete files from Temp/.

    This endpoint:
    1. Updates transaction status from "started" to "declined"
    2. Deletes files from customer_email/Temp/ folder
    3. Returns count of successfully deleted files
    """
    from app.database import database
    from app.services.google_drive_service import google_drive_service
    from datetime import datetime, timezone

    logging.info(f"[DECLINE] User {current_user.get('email')} declining {len(request.transaction_ids)} transactions")
    print(f"[DECLINE] Declining transactions: {request.transaction_ids}")

    if not request.transaction_ids:
        raise HTTPException(status_code=400, detail="No transaction IDs provided")

    try:
        # Fetch all transactions
        transactions = []
        for txn_id in request.transaction_ids:
            txn = await database.translation_transactions.find_one({"transaction_id": txn_id})
            if txn:
                transactions.append(txn)
            else:
                logging.warning(f"[DECLINE] Transaction {txn_id} not found")

        if not transactions:
            raise HTTPException(status_code=404, detail="No valid transactions found")

        # Extract customer email from first transaction
        first_txn = transactions[0]
        customer_email = first_txn.get("user_id", "")  # user_id contains email

        # Get file IDs from documents array (post-migration) or original_file_url (pre-migration fallback)
        file_ids = []
        for txn in transactions:
            # Try nested structure first (post-migration)
            documents = txn.get("documents", [])

            if documents:
                # Process all documents in the transaction
                for doc in documents:
                    url = doc.get("original_url", "")
                    # Extract file ID from Google Drive URL - handles multiple formats:
                    # - Google Docs: https://docs.google.com/document/d/{file_id}/edit
                    # - Google Sheets: https://docs.google.com/spreadsheets/d/{file_id}/edit
                    # - Google Drive: https://drive.google.com/file/d/{file_id}/view
                    file_id = None
                    if "/document/d/" in url:
                        file_id = url.split("/document/d/")[1].split("/")[0]
                    elif "/spreadsheets/d/" in url:
                        file_id = url.split("/spreadsheets/d/")[1].split("/")[0]
                    elif "/file/d/" in url:
                        file_id = url.split("/file/d/")[1].split("/")[0]

                    if file_id:
                        file_ids.append(file_id)
            else:
                # Fallback to flat structure (pre-migration - should not happen but defensive coding)
                url = txn.get("original_file_url", "")
                file_id = None
                if "/document/d/" in url:
                    file_id = url.split("/document/d/")[1].split("/")[0]
                elif "/spreadsheets/d/" in url:
                    file_id = url.split("/spreadsheets/d/")[1].split("/")[0]
                elif "/file/d/" in url:
                    file_id = url.split("/file/d/")[1].split("/")[0]

                if file_id:
                    file_ids.append(file_id)

        logging.info(f"[DECLINE] Deleting {len(file_ids)} files from Temp/ for {customer_email}")
        print(f"[DECLINE] Deleting {len(file_ids)} files from Temp/")

        # Delete files using existing Google Drive service function
        deleted_count = await google_drive_service.delete_files_on_payment_failure(
            customer_email=customer_email,
            file_ids=file_ids
        )

        # Update transaction status to "declined"
        for txn_id in request.transaction_ids:
            await database.translation_transactions.update_one(
                {"transaction_id": txn_id},
                {
                    "$set": {
                        "status": "declined",
                        "error_message": "User declined the transaction",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logging.info(f"[DECLINE] Transaction {txn_id} status updated to 'declined'")
            print(f"[DECLINE] Transaction {txn_id} declined")

        response = {
            "success": True,
            "message": f"Successfully declined {len(request.transaction_ids)} transaction(s)",
            "data": {
                "declined_transactions": len(request.transaction_ids),
                "deleted_files": deleted_count
            }
        }

        logging.info(f"[DECLINE] Success: {len(request.transaction_ids)} transactions declined, {deleted_count} files deleted")
        print(f"[DECLINE] Complete: {len(request.transaction_ids)} transactions declined, {deleted_count} files deleted")

        return JSONResponse(content=response)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[DECLINE] Failed to decline transactions: {e}", exc_info=True)
        print(f"[DECLINE] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to decline transactions: {str(e)}"
        )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "healthy",
        "environment": settings.environment,
        "documentation": "/docs" if settings.debug else "Documentation disabled in production",
        "endpoints": {
            "languages": "/api/v1/languages",
            "translate": "/translate",
            "payment_create": "/api/payment/create-intent",
            "payment_success": "/api/payment/success",
            "health": "/health"
        }
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    try:
        from app.database import database

        # Simple MongoDB connection check
        if database.is_connected:
            # Quick ping to verify connection is alive
            await database.client.admin.command('ping')
            return JSONResponse(
                content={
                    "status": "healthy",
                    "database": "connected",
                    "timestamp": time.time()
                },
                status_code=200
            )
        else:
            return JSONResponse(
                content={
                    "status": "unhealthy",
                    "database": "disconnected",
                    "timestamp": time.time()
                },
                status_code=503
            )
    except Exception as e:
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            },
            status_code=503
        )


# API version endpoint
@app.get("/api/v1", tags=["API Info"])
async def api_info():
    """API version information."""
    return {
        "api_version": "v1",
        "app_version": settings.app_version,
        "features": {},
        "supported_formats": settings.allowed_file_extensions,
        "max_file_size_mb": round(settings.max_file_size / (1024 * 1024), 2)
    }


# Custom exception handlers
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with safe encoding handling."""
    # DEBUG: Print validation errors immediately
    print("🔴 DEBUG: PYDANTIC VALIDATION ERROR!")
    print(f"🔴 DEBUG: Path: {request.url.path}")
    print(f"🔴 DEBUG: Errors: {exc.errors()}")

    # ===================================================================
    # ENHANCED LOGGING FOR /submit ENDPOINT (GoogleTranslator debugging)
    # ===================================================================
    # NOTE: Raw body capture is now handled in EncodingFixMiddleware
    # (before Pydantic validation) to avoid stream consumption issues
    if request.url.path == "/submit":
        print("=" * 80)
        print("🔍 VALIDATION ERROR ON /submit")
        print("=" * 80)
        print(f"📍 Method: {request.method}")
        print(f"📍 URL: {request.url}")
        print(f"📍 Client: {request.client.host if request.client else 'Unknown'}")
        print(f"📍 Validation Errors: {exc.errors()}")
        print("=" * 80)
        print("ℹ️  Raw request body was captured in EncodingFixMiddleware (see logs above)")
        print("=" * 80)
        logging.error(
            f"[SUBMIT VALIDATION ERROR] GoogleTranslator sent invalid request. "
            f"Errors: {exc.errors()}"
        )

    try:
        # Safely serialize validation errors to avoid Unicode decode issues
        safe_errors = []
        for error in exc.errors():
            safe_error = {}
            for key, value in error.items():
                if isinstance(value, bytes):
                    # Handle bytes values that might contain non-UTF-8 data
                    try:
                        safe_error[key] = value.decode('utf-8')
                    except UnicodeDecodeError:
                        # Try alternative encodings
                        for encoding in ['latin1', 'cp1252', 'iso-8859-1']:
                            try:
                                safe_error[key] = f"<{encoding}> {value.decode(encoding)}"
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            safe_error[key] = f"<hex> {value.hex()}"
                elif isinstance(value, str):
                    # Ensure string values are properly handled
                    safe_error[key] = value
                else:
                    safe_error[key] = str(value)
            safe_errors.append(safe_error)

        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": 422,
                    "message": "Request validation failed",
                    "type": "validation_error",
                    "details": safe_errors
                },
                "timestamp": time.time(),
                "path": str(request.url)
            }
        )
    except Exception as e:
        # Fallback error handling if validation error processing fails
        logging.error(f"Error processing validation error: {e}", exc_info=True)
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": 422,
                    "message": "Request validation failed - encoding error",
                    "type": "validation_error_with_encoding_issue",
                    "raw_error": str(exc)
                },
                "timestamp": time.time(),
                "path": str(request.url)
            }
        )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_error"
            },
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with error logging."""
    logging.error(f"Unhandled exception: {exc}", exc_info=True)

    if settings.debug:
        error_detail = str(exc)
    else:
        error_detail = "Internal server error"

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": error_detail,
                "type": "internal_error"
            },
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


# ============================================================================
# TIMEOUT MIDDLEWARE - MUST BE OUTERMOST TO CATCH ALL TIMEOUTS
# ============================================================================
# This middleware is added via decorator AFTER all add_middleware calls,
# making it the outermost layer that executes first and catches timeouts.
#
# CRITICAL FIX: Timeout responses must manually add CORS headers because
# they bypass the CORSMiddleware by being created at the outermost layer.
# ============================================================================
@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Add request timeout handling with proper CORS headers."""
    import asyncio
    import time as time_module

    # DETAILED TIMING LOG
    start_time = time_module.time()
    print(f"[TIMEOUT MIDDLEWARE] START: {request.method} {request.url.path}")

    try:
        # Set timeout based on endpoint
        if "/files/upload" in str(request.url):
            timeout = 300  # 5 minutes for file uploads
        elif "/translate" in str(request.url):
            timeout = 120  # 2 minutes for translations
        elif "/api/payment/" in str(request.url):
            timeout = 90   # 90 seconds for payment processing (Google Drive operations)
        elif "/login/" in str(request.url):
            timeout = 60   # 1 minute for authentication
        else:
            timeout = 30   # 30 seconds for other requests

        print(f"[TIMEOUT MIDDLEWARE] Timeout set to {timeout}s, calling next middleware...")
        response = await asyncio.wait_for(call_next(request), timeout=timeout)
        elapsed = time_module.time() - start_time
        print(f"[TIMEOUT MIDDLEWARE] COMPLETE: {elapsed:.2f}s - {request.method} {request.url.path}")
        return response

    except asyncio.TimeoutError:
        elapsed = time_module.time() - start_time
        print(f"[TIMEOUT MIDDLEWARE] TIMEOUT FIRED: {elapsed:.2f}s - {request.method} {request.url.path}")
        # CRITICAL: Manually add CORS headers to timeout responses
        # because they bypass CORSMiddleware
        response = JSONResponse(
            status_code=408,
            content={
                "success": False,
                "error": {
                    "code": 408,
                    "message": "Request timeout",
                    "type": "timeout_error"
                },
                "timestamp": time.time()
            }
        )

        # Add CORS headers manually using settings
        origin = request.headers.get("origin")
        if origin:
            # Check if origin is allowed
            allowed_origins = settings.cors_origins
            if origin in allowed_origins or "*" in allowed_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = str(settings.cors_credentials).lower()
                response.headers["Access-Control-Allow-Methods"] = ", ".join(settings.cors_methods)
                response.headers["Access-Control-Allow-Headers"] = "*"
                response.headers["Access-Control-Expose-Headers"] = "X-Request-ID, X-Process-Time"

        logging.warning(f"Request timeout: {request.method} {request.url.path} (>{timeout}s)")
        return response


# Custom OpenAPI schema
def custom_openapi():
    """Generate custom OpenAPI schema with additional information."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        ## Translation Web Server API

        A comprehensive translation service supporting multiple languages, file formats, and payment processing.

        ### Features
        - **Text Translation**: Translate text strings using multiple services
        - **File Translation**: Support for various document formats
        - **Batch Processing**: Handle multiple translations simultaneously
        - **Language Detection**: Automatic language identification
        - **Payment Integration**: Stripe-powered payment processing
        - **Rate Limiting**: Built-in request rate limiting
        - **File Upload**: Secure file handling and storage

        ### Supported Services
        - Google Translate (Free & Paid)
        - DeepL
        - Azure Translator

        ### Authentication
        API key authentication required for production usage.

        ### Rate Limits
        - Free tier: 100 requests per hour
        - Paid tiers: Higher limits based on subscription
        """,
        routes=app.routes,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        },
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer"
        }
    }

    # Add example servers
    openapi_schema["servers"] = [
        {
            "url": f"http://localhost:{settings.port}",
            "description": "Development server"
        },
        {
            "url": "https://api.translator.example.com",
            "description": "Production server"
        }
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Startup and shutdown functions
async def initialize_services():
    """Initialize application services."""
    logging.info("Initializing services...")

    # Initialize MongoDB database connection
    from app.database import database
    mongodb_connected = await database.connect()
    if mongodb_connected:
        logging.info("MongoDB database connection established")
    else:
        logging.warning("MongoDB database connection failed - continuing without database")

    # Initialize translation services
    from app.services.translation_service import translation_service
    logging.info(f"Translation services available: {list(translation_service.services.keys())}")

    # Initialize payment service
    from app.services.payment_service import payment_service
    if payment_service.stripe_enabled:
        logging.info("Stripe payment service initialized")
    else:
        logging.warning("Stripe payment service not configured")

    # Initialize file service
    try:
        from app.services.file_service import file_service
        logging.info("File service initialized")
    except ImportError:
        logging.info("File service not available (stub implementation)")

    logging.info("All services initialized successfully")


async def cleanup_services():
    """Cleanup services on shutdown."""
    logging.info("Cleaning up services...")

    # Disconnect from MongoDB
    from app.database import database
    await database.disconnect()

    # Cleanup temporary files would go here in real implementation
    logging.info("No cleanup needed in stub implementation")

    logging.info("Service cleanup completed")


# Development server runner
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run the server
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True
    )
