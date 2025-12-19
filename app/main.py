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

# Import configuration
from app.config import settings

# Import routers
from app.routers import languages, upload, auth, subscriptions, translate_user, payments, test_helpers, user_transactions, invoices, translation_transactions, company_users, orders, companies, submit, dashboard, webhooks, enterprise_documents, contact
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
app.include_router(webhooks.router)  # Stripe webhooks API
app.include_router(user_transactions.router)  # User transaction payment API
app.include_router(invoices.router)  # Invoice management API
app.include_router(translation_transactions.router)  # Translation transaction management API
app.include_router(company_users.router)  # Company user management API
app.include_router(companies.router)  # Company management API
app.include_router(orders.router)  # Orders management API
app.include_router(dashboard.router)  # Dashboard metrics API
app.include_router(enterprise_documents.router)  # Enterprise documents portal API
app.include_router(contact.router)  # Contact form API
app.include_router(auth.router)
app.include_router(subscriptions.router)
app.include_router(translate_user.router)

# Include test helper endpoints only in test/dev mode
if settings.environment.lower() in ["test", "development"]:
    app.include_router(test_helpers.router)
    print("⚠️  Test helper endpoints enabled (test/dev mode only)")

# Import models for /translate endpoint
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any

from app.mongodb_models import TranslationMode

class FileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str
    content: str  # Base64-encoded file content from client

# Per-file translation mode info (for file-level mode selection)
class FileTranslationModeInfo(BaseModel):
    fileName: str
    translationMode: TranslationMode = TranslationMode.AUTOMATIC

class TranslateRequest(BaseModel):
    files: List[FileInfo]
    fileTranslationModes: Optional[List[FileTranslationModeInfo]] = None  # Per-file translation modes
    sourceLanguage: str
    targetLanguage: str
    email: EmailStr
    paymentIntentId: Optional[str] = None


# ============================================================================
# Transaction Helper Function
# ============================================================================
async def create_transaction_record(
    files_info: List[dict],
    user_data: dict,
    request_data: TranslateRequest,
    subscription: Optional[dict],
    company_name: Optional[str],
    price_per_page: float,
    file_translation_modes: Optional[Dict[str, TranslationMode]] = None  # Per-file translation modes (fileName -> mode)
) -> Optional[str]:
    """
    Create ONE transaction record for MULTIPLE file uploads.

    IMPORTANT: This creates a SINGLE transaction with ALL files in the documents[] array.
    This is the correct behavior - one transaction per upload request, not per file.

    Uses nested documents[] array structure (TranslationDocumentEmbedded model).

    Args:
        files_info: List of dicts, each with file_id, filename, size, page_count, google_drive_url
        user_data: Current authenticated user data
        request_data: Original TranslateRequest
        subscription: Enterprise subscription (or None for individual)
        company_name: Enterprise company name (or None for individual)
        price_per_page: Calculated pricing (subscription or default)
        file_translation_modes: Dict mapping fileName to TranslationMode (per-file modes)

    Returns:
        transaction_id if successful, None if failed
    """
    from app.database import database
    from bson import ObjectId
    from datetime import datetime, timezone
    import uuid

    if not files_info:
        logging.warning("[TRANSACTION] No files provided - skipping transaction creation")
        return None

    try:
        # Generate unique transaction ID
        transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"

        # ====================================================================
        # SINGLE TRANSACTION WITH MULTIPLE DOCUMENTS
        # ====================================================================
        logging.info(f"[TRANSACTION] ========== CREATING SINGLE TRANSACTION ==========")
        logging.info(f"[TRANSACTION] Transaction ID: {transaction_id}")
        logging.info(f"[TRANSACTION] Number of files: {len(files_info)}")
        print(f"\n📦 [TRANSACTION] Creating SINGLE transaction {transaction_id} with {len(files_info)} document(s)")

        # Build documents array with ALL files
        documents = []
        total_pages = 0
        file_names = []

        for idx, file_info in enumerate(files_info):
            # Get translation mode for this specific file (default to automatic)
            filename = file_info.get("filename", "")
            file_mode = TranslationMode.AUTOMATIC
            if file_translation_modes and filename in file_translation_modes:
                file_mode = file_translation_modes[filename]

            document_entry = {
                "file_name": filename,
                "file_size": file_info.get("size", 0),
                "original_url": file_info.get("google_drive_url", ""),
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None,
                "file_id": file_info.get("file_id"),  # Google Drive file ID for confirm endpoint
                "translation_mode": file_mode.value  # Per-file translation mode
            }
            documents.append(document_entry)
            total_pages += file_info.get("page_count", 1)
            file_names.append(filename or f"file_{idx}")

            logging.info(f"[TRANSACTION]   Document {idx + 1}: {filename} ({file_info.get('page_count', 1)} pages, file_id: {file_info.get('file_id')}, mode: {file_mode.value})")
            print(f"   📄 Document {idx + 1}: {filename} ({file_info.get('page_count', 1)} pages, mode: {file_mode.value})")

        # Log transaction-level translation_mode summary
        mode_summary = {}
        for doc in documents:
            mode = doc.get("translation_mode", "automatic")
            mode_summary[mode] = mode_summary.get(mode, 0) + 1
        logging.info(f"[TRANSACTION] Translation mode summary: {mode_summary}")
        print(f"   🎯 Translation modes: {mode_summary}")

        # Build transaction document with nested documents[] array
        # IMPORTANT: Store actual email, not generated user_id
        # NOTE: translation_mode is now per-file (stored in each document entry), not per-transaction
        transaction_doc = {
            "transaction_id": transaction_id,
            "user_id": request_data.email,  # Use actual email for folder lookup
            "source_language": request_data.sourceLanguage,
            "target_language": request_data.targetLanguage,
            "units_count": total_pages,
            "price_per_unit": price_per_page,
            "total_price": total_pages * price_per_page,
            "status": "started",
            "error_message": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            # NESTED documents[] array - ALL files in ONE transaction (each with translation_mode)
            "documents": documents,
            # Email batching counters
            "total_documents": len(documents),
            "completed_documents": 0,
            "batch_email_sent": False
        }

        # Add enterprise-specific fields if applicable
        if company_name and subscription:
            transaction_doc["company_name"] = company_name  # Store company name for folder lookup
            transaction_doc["subscription_id"] = ObjectId(str(subscription["_id"]))
            transaction_doc["unit_type"] = subscription.get("subscription_unit", "page")
            logging.info(f"[TRANSACTION] Enterprise: {company_name}, Subscription: {subscription.get('_id')}")
        else:
            # Individual customer (no company or subscription)
            transaction_doc["company_name"] = None
            transaction_doc["subscription_id"] = None
            transaction_doc["unit_type"] = "page"
            logging.info(f"[TRANSACTION] Individual customer (no company)")

        # Log the full transaction document before insertion
        import json
        logging.info(f"[TRANSACTION] ========== FULL TRANSACTION DOCUMENT ==========")
        # Create a serializable copy for logging (handle datetime and ObjectId)
        log_doc = {}
        for key, value in transaction_doc.items():
            if key == "documents":
                # Log documents separately with translation_mode highlighted
                log_doc["documents"] = []
                for doc in value:
                    doc_copy = {}
                    for dk, dv in doc.items():
                        if hasattr(dv, 'isoformat'):
                            doc_copy[dk] = dv.isoformat()
                        else:
                            doc_copy[dk] = dv
                    log_doc["documents"].append(doc_copy)
            elif hasattr(value, 'isoformat'):
                log_doc[key] = value.isoformat()
            elif hasattr(value, '__str__') and 'ObjectId' in str(type(value)):
                log_doc[key] = str(value)
            else:
                log_doc[key] = value

        # Print formatted transaction document
        print(f"\n   📋 FULL TRANSACTION DOCUMENT:")
        print(f"   {json.dumps(log_doc, indent=6, default=str)}")
        logging.info(f"[TRANSACTION] Document: {json.dumps(log_doc, default=str)}")
        logging.info(f"[TRANSACTION] ================================================")

        # Insert into appropriate collection based on user type
        if company_name:
            # Enterprise user -> translation_transactions collection
            await database.translation_transactions.insert_one(transaction_doc)
            logging.info(f"[TRANSACTION] 📝 Inserted into ENTERPRISE collection: translation_transactions")
            print(f"   📝 Collection: translation_transactions (Enterprise)")
        else:
            # Individual user -> user_transactions collection
            await database.user_transactions.insert_one(transaction_doc)
            logging.info(f"[TRANSACTION] 📝 Inserted into INDIVIDUAL collection: user_transactions")
            print(f"   📝 Collection: user_transactions (Individual)")

        logging.info(f"[TRANSACTION] ✅ SUCCESS: Created {transaction_id}")
        logging.info(f"[TRANSACTION]   Total documents: {len(documents)}")
        logging.info(f"[TRANSACTION]   Total pages: {total_pages}")
        logging.info(f"[TRANSACTION]   Total price: ${total_pages * price_per_page:.2f}")
        logging.info(f"[TRANSACTION]   Files: {', '.join(file_names)}")
        logging.info(f"[TRANSACTION] =================================================")

        print(f"   ✅ Transaction {transaction_id} created with {len(documents)} document(s), {total_pages} total pages")
        print(f"   💰 Total price: ${total_pages * price_per_page:.2f}")

        return transaction_id

    except Exception as e:
        import traceback
        error_type = type(e).__name__
        error_msg = str(e)
        stack_trace = traceback.format_exc()

        logging.error(f"[TRANSACTION] ❌ FAILED to create transaction")
        logging.error(f"[TRANSACTION] Error Type: {error_type}")
        logging.error(f"[TRANSACTION] Error Message: {error_msg}")
        logging.error(f"[TRANSACTION] Stack Trace:\n{stack_trace}")

        print(f"   ❌ [TRANSACTION] Failed to create transaction")
        print(f"   ❌ Error Type: {error_type}")
        print(f"   ❌ Error Message: {error_msg}")
        print(f"   ❌ See logs for full stack trace")

        return None


# Direct translate endpoint (Google Drive upload)
@app.post("/translate", tags=["Translation"])
async def translate_files(
    request: TranslateRequest = Body(...),
    current_user: Optional[dict] = Depends(get_optional_user)
):
    """
    SIMPLIFIED TRANSLATE ENDPOINT:
    1. Upload files to Google Drive {customer_email}/Temp/ folder
    2. Store metadata linking customer to files (no payment sessions)
    3. Return page count for pricing calculation
    4. Frontend processes payment with customer_email
    5. Payment webhook moves files from Temp/ to Inbox/
    """
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
    is_enterprise = company_name is not None

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
    user_name = current_user.get('user_name', 'N/A') if current_user else 'N/A'
    print(f"   User: {user_name} ({request.email})")

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

    print(f"Created storage job: {storage_id}")
    if is_enterprise and company_name:
        print(f"Target folder: {company_name}/{request.email}/Temp/ (ID: {folder_id})")
    else:
        print(f"Target folder: {request.email}/Temp/ (ID: {folder_id})")
    print(f"Starting file uploads to Google Drive...")

    # Store files with enhanced metadata (no sessions)
    stored_files = []
    total_pages = 0

    # Pre-build translation modes dict for file upload logging
    upload_file_modes: Dict[str, str] = {}
    if request.fileTranslationModes:
        for mode_info in request.fileTranslationModes:
            upload_file_modes[mode_info.fileName] = mode_info.translationMode.value

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

            # Get translation_mode for this file BEFORE metadata update (default to automatic)
            # Valid values: automatic, human, formats, handwriting
            file_translation_mode = upload_file_modes.get(file_info.name, "automatic")
            logging.info(f"[FILE {i}] Translation mode assignment: '{file_info.name}' -> '{file_translation_mode}'")

            # Update file with enhanced metadata for payment linking
            log_step(f"FILE {i} METADATA UPDATE", f"Setting file properties (translation_mode: {file_translation_mode})")
            file_metadata = {
                'customer_email': request.email,
                'source_language': request.sourceLanguage,
                'target_language': request.targetLanguage,
                'page_count': str(page_count),
                'status': 'awaiting_payment',
                'upload_timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'original_filename': file_info.name,
                'translation_mode': file_translation_mode  # Added translation_mode to file metadata
            }
            logging.info(f"[FILE {i}] Metadata to be set: {file_metadata}")
            await google_drive_service.update_file_properties(
                file_id=file_result['file_id'],
                properties=file_metadata
            )
            logging.info(f"[FILE {i}] ✅ Metadata SET successfully with translation_mode='{file_translation_mode}'")
            log_step(f"FILE {i} COMPLETE", f"URL: {file_result.get('google_drive_url', 'N/A')}")

            stored_files.append({
                "file_id": file_result['file_id'],
                "filename": file_info.name,
                "status": "stored",
                "page_count": page_count,
                "size": file_info.size,
                "google_drive_url": file_result.get('google_drive_url'),
                "translation_mode": file_translation_mode
            })
            print(f"   Successfully uploaded: '{file_info.name}' -> Google Drive ID: {file_result['file_id']}, Pages: {page_count}, Mode: {file_translation_mode}")

        except Exception as e:
            log_step(f"FILE {i} FAILED", f"Error: {str(e)}")
            print(f"   Failed to upload '{file_info.name}': {e}")
            # Get translation_mode for failed file too (for logging consistency)
            file_translation_mode = upload_file_modes.get(file_info.name, "automatic")
            stored_files.append({
                "file_id": None,
                "filename": file_info.name,
                "status": "failed",
                "page_count": 0,
                "size": file_info.size,
                "error": str(e),
                "translation_mode": file_translation_mode
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
            # Database schema: units_allocated, units_used, promotional_units
            # Formula: total_remaining = (units_allocated + promotional_units) - units_used
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
                # Debug: Log period structure
                logging.debug(f"[SUBSCRIPTION] Period keys: {list(current_period.keys())}")

                units_allocated = current_period.get("units_allocated", 0)
                units_used = current_period.get("units_used", 0)
                promotional_units = current_period.get("promotional_units", 0)

                # Validation: Warn if critical fields are missing
                if units_allocated == 0 and "units_allocated" not in current_period:
                    logging.warning(
                        f"[SUBSCRIPTION] ⚠️ units_allocated field not found in period! "
                        f"Available keys: {list(current_period.keys())}"
                    )

                total_allocated = units_allocated + promotional_units
                total_used = units_used
                total_remaining = total_allocated - units_used
            else:
                # No active period found - cannot use subscription
                units_allocated = 0
                promotional_units = 0
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
                logging.info(f"[SUBSCRIPTION]   Units Allocated: {units_allocated}")
                logging.info(f"[SUBSCRIPTION]   Promotional Units: {promotional_units}")
                logging.info(f"[SUBSCRIPTION]   Total Allocated: {total_allocated} {subscription_unit}s")
                logging.info(f"[SUBSCRIPTION]   Used Units: {total_used} {subscription_unit}s")
                logging.info(f"[SUBSCRIPTION]   Remaining Units: {total_remaining} {subscription_unit}s")

                print(f"\n📊 Current Subscription Period:")
                print(f"   Status: {status}")
                print(f"   Period: {current_period_idx} ({current_period.get('period_start')} to {current_period.get('period_end')})")
                print(f"   Units Allocated: {units_allocated} {subscription_unit}s")
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
            # REJECT: Enterprise user must have an active subscription
            log_step("VALIDATION FAILED", f"No active subscription for company: {company_name}")
            logging.error(f"[SUBSCRIPTION] REJECTED: No active subscription found for company '{company_name}'")
            raise HTTPException(
                status_code=403,
                detail=f"No active subscription found for company '{company_name}'. Enterprise users must have an active subscription to submit translations. Please contact your administrator."
            )

    # Determine if payment is required based on enterprise subscription
    payment_required = True
    overdraft_detected = False
    overdraft_amount = 0
    exceeds_soft_limit = False
    subscription_info_dict = None

    if is_enterprise and subscription:
        # Record subscription usage per file with individual translation modes
        try:
            # Import UsageUpdate model for type-safe usage recording
            from app.models.subscription import UsageUpdate

            # Build a map of fileName → translationMode from request
            mode_map = {}
            if request.fileTranslationModes:
                mode_map = {
                    mode_info.fileName: mode_info.translationMode.value
                    for mode_info in request.fileTranslationModes
                }
                log_step("TRANSLATION MODES", f"Received modes for {len(mode_map)} files")

            # Record usage for each file separately (per-file pricing)
            updated_subscription = None
            for file_info in stored_files:
                # Only process successfully stored files
                if file_info.get("status") != "stored":
                    continue

                file_name = file_info.get("filename")
                pages = file_info.get("page_count", 1)
                mode = mode_map.get(file_name, "default")

                usage_update = UsageUpdate(
                    units_to_add=pages,
                    translation_mode=mode,
                    use_promotional_units=False
                )

                # Record usage for THIS file
                updated_subscription = await subscription_service.record_usage(
                    subscription_id=str(subscription["_id"]),
                    usage_data=usage_update
                )

                log_step("FILE USAGE RECORDED", f"'{file_name}': {pages} units (mode: {mode})")

            # Extract overdraft information from final subscription state
            if updated_subscription:
                overdraft_detected = updated_subscription.get("overdraft", False)
                overdraft_amount = updated_subscription.get("overdraft_amount", 0)
                exceeds_soft_limit = updated_subscription.get("exceeds_soft_limit", False)

                # Enterprise users don't require payment (using subscription, even if overdraft)
                payment_required = False

                # Get current period from usage_periods array
                usage_periods = updated_subscription.get("usage_periods", [])

                if not usage_periods:
                    log_step("SUBSCRIPTION ERROR", "No usage periods found in subscription")
                    raise HTTPException(
                        status_code=500,
                        detail="Subscription has no usage periods configured. Contact administrator."
                    )

                # Get current period and validate by date comparison
                now = datetime.now(timezone.utc)
                current_period = None

                for period in usage_periods:
                    period_start = period.get("period_start")
                    period_end = period.get("period_end")

                    # Ensure datetime objects have timezone info
                    if period_start and not period_start.tzinfo:
                        period_start = period_start.replace(tzinfo=timezone.utc)
                    if period_end and not period_end.tzinfo:
                        period_end = period_end.replace(tzinfo=timezone.utc)

                    # Validate: today's date must fall within period
                    if period_start and period_end and period_start <= now <= period_end:
                        current_period = period
                        log_step(
                            "CURRENT PERIOD FOUND",
                            f"Period: {period_start.date()} to {period_end.date()}, "
                            f"Allocated: {period.get('units_allocated', 0)}, "
                            f"Used: {period.get('units_used', 0)}, "
                            f"Remaining: {period.get('units_remaining', 0)}"
                        )
                        break

                if not current_period:
                    log_step("SUBSCRIPTION ERROR", "No valid period found for current date")
                    raise HTTPException(
                        status_code=500,
                        detail="No active subscription period found for current date. Contact administrator."
                    )

                # Extract subscription data from validated current period
                subscription_info_dict = {
                    "units_allocated": current_period.get("units_allocated", 0),
                    "units_used": current_period.get("units_used", 0),
                    "units_remaining": current_period.get("units_remaining", 0),
                    "promotional_units": current_period.get("promotional_units", 0),
                    "subscription_unit": subscription_unit
                }
            else:
                # Fallback if no files were processed
                log_step("SUBSCRIPTION WARNING", "No files processed, skipping usage recording")
                payment_required = True

            if overdraft_detected:
                log_step("OVERDRAFT DETECTED", f"Overdraft: {overdraft_amount} units, Soft limit exceeded: {exceeds_soft_limit}")
                logging.warning(f"[OVERDRAFT] ⚠ Subscription overdraft detected")
                logging.warning(f"[OVERDRAFT]   Required: {total_pages} {subscription_unit}s")
                logging.warning(f"[OVERDRAFT]   Available: {total_remaining} {subscription_unit}s")
                logging.warning(f"[OVERDRAFT]   Overdraft: {overdraft_amount} {subscription_unit}s")
                logging.warning(f"[OVERDRAFT]   Exceeds soft limit: {exceeds_soft_limit}")
                print(f"\n⚠️  Subscription overdraft")
                print(f"   Required: {total_pages} {subscription_unit}s")
                print(f"   Available: {total_remaining} {subscription_unit}s")
                print(f"   Overdraft: {overdraft_amount} {subscription_unit}s")
                if exceeds_soft_limit:
                    print(f"   ⚠️  Exceeds soft limit (-100 pages)")
            else:
                log_step("SUBSCRIPTION USAGE", f"Using {total_pages} of {total_remaining} units available")
                logging.info(f"[PAYMENT] ✓ Using subscription units (no overdraft)")
                logging.info(f"[PAYMENT]   Required: {total_pages} {subscription_unit}s")
                logging.info(f"[PAYMENT]   Available: {total_remaining} {subscription_unit}s")
                print(f"\n✅ Using subscription units")
                print(f"   Required: {total_pages} {subscription_unit}s")
                print(f"   Available: {total_remaining} {subscription_unit}s")
        except Exception as e:
            log_step("SUBSCRIPTION ERROR", f"Error recording usage: {e}")
            logging.error(f"[SUBSCRIPTION] Error recording usage: {e}")
            # Fall back to requiring payment
            payment_required = True
    else:
        log_step("PAYMENT REQUIRED", "Individual customer or no subscription")
        logging.info(f"[PAYMENT] Payment required for {'individual customer' if not is_enterprise else 'enterprise without subscription'}")
        print(f"\n💳 Payment required: {'Individual customer' if not is_enterprise else 'Enterprise without subscription'}")

    # ========================================================================
    # CREATE SINGLE TRANSACTION FOR ALL FILES
    # ========================================================================
    # IMPORTANT: One transaction per upload request, NOT one per file!
    # All files are stored in the documents[] array of a single transaction.
    successful_stored_files = [f for f in stored_files if f["status"] == "stored"]

    log_step("TRANSACTION CREATE START", f"Creating SINGLE transaction for {len(successful_stored_files)} file(s)")
    logging.info(f"[TRANSLATE] ========== TRANSACTION CREATION ==========")
    logging.info(f"[TRANSLATE] Creating ONE transaction with {len(successful_stored_files)} document(s)")
    logging.info(f"[TRANSLATE] Files: {[f['filename'] for f in successful_stored_files]}")

    # Build file-level translation modes dict from request
    file_translation_modes: Dict[str, TranslationMode] = {}
    if request.fileTranslationModes:
        for mode_info in request.fileTranslationModes:
            file_translation_modes[mode_info.fileName] = mode_info.translationMode
        logging.info(f"[TRANSLATE] Per-file translation modes: {[(k, v.value) for k, v in file_translation_modes.items()]}")
    else:
        logging.info(f"[TRANSLATE] No per-file modes specified, using default (automatic)")

    if successful_stored_files:
        # Create a SINGLE transaction with ALL files in documents[] array
        transaction_id = await create_transaction_record(
            files_info=successful_stored_files,  # Pass ALL files at once
            user_data=current_user,
            request_data=request,
            subscription=subscription if is_enterprise else None,
            company_name=company_name if is_enterprise else None,
            price_per_page=price_per_page,
            file_translation_modes=file_translation_modes if file_translation_modes else None
        )

        if transaction_id:
            transaction_ids = [transaction_id]  # Single transaction ID
            log_step("TRANSACTION CREATED", f"SINGLE transaction {transaction_id} with {len(successful_stored_files)} document(s)")
            logging.info(f"[TRANSLATE] ✅ SINGLE transaction created: {transaction_id}")

            # Update all uploaded files with transaction_id in their metadata
            log_step("FILE METADATA UPDATE", f"Adding transaction_id to {len(successful_stored_files)} file(s)")
            for file_info in successful_stored_files:
                file_id = file_info.get("file_id")
                if file_id:
                    try:
                        await google_drive_service.update_file_properties(
                            file_id=file_id,
                            properties={"transaction_id": transaction_id}
                        )
                        logging.info(f"[FILE {file_id[:20]}...] ✅ Added transaction_id={transaction_id}")
                    except Exception as e:
                        logging.error(f"[FILE {file_id[:20]}...] ❌ Failed to add transaction_id: {e}")
            log_step("FILE METADATA UPDATED", f"All files now have transaction_id={transaction_id}")
        else:
            # CRITICAL: Transaction creation failed - cannot proceed
            log_step("TRANSACTION FAILED", "Transaction creation returned None - cannot process files")
            logging.error(f"[TRANSLATE] ❌ CRITICAL: Failed to create transaction record")
            logging.error(f"[TRANSLATE] Files uploaded but cannot be processed without transaction record")
            raise HTTPException(
                status_code=500,
                detail="Failed to create transaction record. Files were uploaded but cannot be processed. Please contact support."
            )

    logging.info(f"[TRANSLATE] ==============================================")
    log_step("TRANSACTION CREATE COMPLETE", f"Created {len(transaction_ids)} transaction(s) with {len(successful_stored_files)} total document(s)")

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

    response_data = {
        "success": True,
        "data": {
            "id": storage_id,
            "status": "stored",
            "progress": 100,
            "message": f"Files uploaded successfully. Ready for payment.",

                # Pricing information (conditionally include payment fields)
                "pricing": {
                    "total_pages": total_pages,
                    "price_per_page": None if is_enterprise else price_per_page,
                    "total_amount": None if is_enterprise else (total_pages * price_per_page),
                    "currency": None if is_enterprise else "USD",
                    "customer_type": "enterprise" if is_enterprise else "individual",
                    "transaction_ids": transaction_ids,  # Transaction IDs for all files
                    # Overdraft fields (for enterprise subscriptions)
                    "overdraft": overdraft_detected,
                    "overdraft_amount": overdraft_amount,
                    "exceeds_soft_limit": exceeds_soft_limit,
                    "available_units": total_remaining if is_enterprise and subscription else 0,
                    "requested_units": total_pages
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

                # Subscription information (enterprise only) - Use updated values if available
                "subscription": subscription_info_dict if subscription_info_dict else ({
                    "units_allocated": units_allocated if is_enterprise and subscription else 0,
                    "units_used": total_used if is_enterprise and subscription else 0,
                    "units_remaining": total_remaining if is_enterprise and subscription else 0,
                    "promotional_units": promotional_units if is_enterprise and subscription else 0,
                    "subscription_unit": subscription_unit if is_enterprise and subscription else "page"
                } if is_enterprise and subscription else None),

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

    # Handle None values for enterprise users
    price_per_page = response_data['data']['pricing']['price_per_page']
    total_amount = response_data['data']['pricing']['total_amount']
    currency = response_data['data']['pricing']['currency']

    if price_per_page is not None:
        print(f"[RAW OUTGOING DATA]   - Price Per Page: ${price_per_page:.2f}")
    else:
        print(f"[RAW OUTGOING DATA]   - Price Per Page: N/A (using subscription)")

    if total_amount is not None:
        print(f"[RAW OUTGOING DATA]   - Total Amount: ${total_amount:.2f}")
    else:
        print(f"[RAW OUTGOING DATA]   - Total Amount: N/A (using subscription)")

    if currency is not None:
        print(f"[RAW OUTGOING DATA]   - Currency: {currency}")
    else:
        print(f"[RAW OUTGOING DATA]   - Currency: N/A (using subscription)")

    print(f"[RAW OUTGOING DATA]   - Customer Type: {response_data['data']['pricing']['customer_type']}")
    print(f"[RAW OUTGOING DATA]   - Transaction IDs ({len(response_data['data']['pricing']['transaction_ids'])}): {response_data['data']['pricing']['transaction_ids']}")
    print(f"[RAW OUTGOING DATA] Files:")
    print(f"[RAW OUTGOING DATA]   - Total Files: {response_data['data']['files']['total_files']}")
    print(f"[RAW OUTGOING DATA]   - Successful: {response_data['data']['files']['successful_uploads']}")
    print(f"[RAW OUTGOING DATA]   - Failed: {response_data['data']['files']['failed_uploads']}")
    for i, file in enumerate(response_data['data']['files']['stored_files'], 1):
        print(f"[RAW OUTGOING DATA]   File {i}: '{file['filename']}' | Status: {file['status']} | Pages: {file['page_count']} | Mode: {file.get('translation_mode', 'automatic')} | GDrive: {file.get('google_drive_url', 'N/A')[:50]}...")
    print(f"[RAW OUTGOING DATA] Customer: {response_data['data']['customer']['email']}")
    print(f"[RAW OUTGOING DATA] Payment Required: {response_data['data']['payment']['required']}")
    print(f"[RAW OUTGOING DATA] Payment Amount (cents): {response_data['data']['payment']['amount_cents']}")
    if response_data['data'].get('subscription'):
        print(f"[RAW OUTGOING DATA] Subscription Information:")
        print(f"[RAW OUTGOING DATA]   - Units Allocated: {response_data['data']['subscription']['units_allocated']}")
        print(f"[RAW OUTGOING DATA]   - Units Used: {response_data['data']['subscription']['units_used']}")
        print(f"[RAW OUTGOING DATA]   - Units Remaining: {response_data['data']['subscription']['units_remaining']}")
        print(f"[RAW OUTGOING DATA]   - Promotional Units: {response_data['data']['subscription']['promotional_units']}")
        print(f"[RAW OUTGOING DATA]   - Subscription Unit: {response_data['data']['subscription']['subscription_unit']}")
    print(f"[RAW OUTGOING DATA] User Information:")
    print(f"[RAW OUTGOING DATA]   - Permission Level: {response_data['data']['user']['permission_level']}")
    print(f"[RAW OUTGOING DATA]   - Email: {response_data['data']['user']['email']}")
    print(f"[RAW OUTGOING DATA]   - Full Name: {response_data['data']['user']['full_name']}")
    print("=" * 100)

    return JSONResponse(content=response_data)


# ============================================================================
# Transaction Confirmation/Decline Models
# ============================================================================
class TransactionActionRequest(BaseModel):
    transaction_ids: List[str]


class EnterpriseConfirmRequest(BaseModel):
    """Enterprise confirmation - uses transaction_id only, no file search"""
    transaction_id: str = Field(..., description="Transaction ID from upload response")
    status: bool = Field(default=True, description="True=confirm, False=cancel")


class IndividualConfirmRequest(BaseModel):
    """Individual confirmation - includes payment info and file_ids from upload"""
    transaction_id: str = Field(..., description="Transaction ID from upload response")
    stripe_checkout_session_id: Optional[str] = Field(None, description="Square payment transaction ID")
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

        # Move files from Temp to Inbox
        print(f"\n📁 Step 1: Moving files from Temp to Inbox...")
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
        print(f"\n🔍 Step 2: Verifying files in Inbox...")
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

        # Step 5: Update file properties with transaction_id
        print(f"\n📝 Step 5: Adding transaction IDs to file metadata...")
        metadata_start = time.time()
        metadata_updates_successful = 0

        for i, file_id in enumerate(file_ids):
            try:
                transaction_id = transaction_ids[i]
                await google_drive_service.update_file_properties(
                    file_id=file_id,
                    properties={
                        'transaction_id': transaction_id,
                        'status': 'confirmed',
                        'confirmation_timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')
                    }
                )
                metadata_updates_successful += 1
                print(f"   ✓ File {file_id[:20]}...: Added transaction_id={transaction_id}")
            except Exception as e:
                print(f"   ⚠️  Failed to update metadata for file {file_id[:20]}...: {e}")
                # Continue processing other files even if one fails

        metadata_elapsed = (time.time() - metadata_start) * 1000
        print(f"⏱️  Metadata update completed in {metadata_elapsed:.2f}ms")
        print(f"✅ Updated: {metadata_updates_successful}/{len(file_ids)} files")

        # Update transaction status
        print(f"\n🔄 Step 3: Updating transaction status...")
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
        print(f"\n💳 Step 4: Updating subscription usage...")
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
                    # Batch operations: mark as "mixed" since multiple transactions may have different modes
                    usage_update = UsageUpdate(
                        units_to_add=total_units,
                        use_promotional_units=False,
                        translation_mode="mixed"  # Batch aggregation
                    )
                    await subscription_service.record_usage(
                        subscription_id=subscription_id_str,
                        usage_data=usage_update
                    )
                    print(f"   ✅ Subscription {subscription_id_str}: +{total_units} units (batch mode: mixed)")
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
    request: TransactionActionRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Confirm transactions and move files from Temp/ to Inbox/.

    This endpoint:
    1. Updates transaction status from "started" to "confirmed"
    2. Moves files from customer_email/Temp/ to customer_email/Inbox/
    3. Returns count of successfully moved files
    """
    print(f"[CONFIRM ENDPOINT] ✅ REACHED! Pydantic body parsing completed successfully!")
    print(f"[CONFIRM ENDPOINT] Transaction IDs: {request.transaction_ids}")
    print(f"[CONFIRM ENDPOINT] Current user: {current_user.get('email')}")

    from app.database import database
    from app.services.google_drive_service import google_drive_service
    from datetime import datetime, timezone

    logging.info(f"[CONFIRM] User {current_user.get('email')} confirming {len(request.transaction_ids)} transactions")
    print(f"[CONFIRM] Confirming transactions: {request.transaction_ids}")

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
                logging.warning(f"[CONFIRM] Transaction {txn_id} not found")

        if not transactions:
            raise HTTPException(status_code=404, detail="No valid transactions found")

        # Extract customer email and company name from first transaction
        first_txn = transactions[0]
        customer_email = first_txn.get("user_id", "")  # user_id contains email
        company_name = first_txn.get("company_name")  # company_name for enterprise customers

        # Get file IDs from original_file_url (Google Drive URLs contain file ID)
        file_ids = []
        for txn in transactions:
            url = txn.get("original_file_url", "")

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

        # Log what we're about to do (fast - logging only)
        if company_name:
            logging.info(f"[CONFIRM] Scheduling background task to move {len(file_ids)} files from {company_name}/{customer_email}/Temp/ to Inbox/")
            print(f"[CONFIRM] Scheduling background task: {len(file_ids)} files from {company_name}/{customer_email}/Temp/ to Inbox/")
        else:
            logging.info(f"[CONFIRM] Scheduling background task to move {len(file_ids)} files from {customer_email}/Temp/ to Inbox/")
            print(f"[CONFIRM] Scheduling background task: {len(file_ids)} files from {customer_email}/Temp/ to Inbox/")

        # Schedule background task for file move, verification, and updates
        print(f"[CONFIRM] Adding background task to queue...")
        background_tasks.add_task(
            process_transaction_confirmation_background,
            transaction_ids=request.transaction_ids,
            customer_email=customer_email,
            company_name=company_name,
            file_ids=file_ids
        )
        print(f"[CONFIRM] ✅ Background task scheduled successfully")

        # Return IMMEDIATELY (< 1 second) - background task will handle everything else
        response = {
            "success": True,
            "message": f"Transactions confirmed. Files are being moved to Inbox in the background.",
            "data": {
                "confirmed_transactions": len(request.transaction_ids),
                "total_files": len(file_ids),
                "status": "processing",
                "customer_email": customer_email,
                "company_name": company_name if company_name else None,
                "processing_note": "Files are being moved and verified in the background. This may take 30-90 seconds to complete."
            }
        }

        logging.info(f"[CONFIRM] Immediate response sent: {len(request.transaction_ids)} transactions scheduled for processing")
        print(f"[CONFIRM] ⚡ INSTANT RESPONSE: {len(request.transaction_ids)} transactions scheduled (background processing started)")

        return JSONResponse(content=response)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[CONFIRM] Failed to confirm transactions: {e}", exc_info=True)
        print(f"[CONFIRM] Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to confirm transactions: {str(e)}"
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

        # Get file IDs from original_file_url (Google Drive URLs contain file ID)
        file_ids = []
        for txn in transactions:
            url = txn.get("original_file_url", "")
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
    import json
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

        logging.info(f"[CONFIRM-ENTERPRISE] Transaction ID: {transaction.get('transaction_id')}, Status: {transaction.get('status')}")
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
            raise HTTPException(
                status_code=400,
                detail="Transaction documents have no file_ids"
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

                # NOTE: Subscription usage is already recorded during upload (per-file)
                # No need to record usage again here - would cause double-charging
                logging.info(f"[CONFIRM-ENTERPRISE] Subscription usage already recorded during upload")

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
    - If status=True: Stores stripe_checkout_session_id, moves files Temp → Inbox, updates transaction to 'completed'
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

            # Update transaction with stripe_checkout_session_id and status
            update_data = {
                "status": "completed",
                "updated_at": datetime.now(timezone.utc)
            }
            if request.stripe_checkout_session_id:
                update_data["stripe_checkout_session_id"] = request.stripe_checkout_session_id
                logging.info(f"[CONFIRM-INDIVIDUAL] Storing Square transaction ID: {request.stripe_checkout_session_id}")

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
                            "stripe_checkout_session_id": request.stripe_checkout_session_id,
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
            "url": settings.api_url if settings.api_url else "https://api.example.com",
            "description": "Production server"
        }
    ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Startup and shutdown functions
async def initialize_stripe():
    """
    Initialize Stripe SDK with global configuration.

    Phase 1 Migration: Stripe SDK v8.2.0
    - Sets global API key for all Stripe operations
    - Pins API version to prevent breaking changes from account defaults
    - Adds app info for Stripe telemetry

    Called during application startup (lifespan).
    """
    import stripe

    # Skip initialization if Stripe API key not configured
    if not settings.stripe_secret_key:
        logging.warning("[STRIPE] Stripe API key not configured - skipping Stripe SDK initialization")
        return

    # Set global API key
    stripe.api_key = settings.stripe_secret_key

    # Pin API version for stability (prevents breaking changes when Stripe updates defaults)
    # Version: 2025-11-17.clover (Stripe SDK v13.x default - latest)
    # Breaking changes in v12.x: List.total_count removed (not used in our code)
    # Breaking changes in v13.x: InvoiceLineItem.modify signature changed (not used in our code)
    # Migration note: Reviewed and safe - webhook API stable, no breaking change usage
    stripe.api_version = "2025-11-17.clover"

    # Set app info for Stripe telemetry (helps Stripe support identify our integration)
    stripe.app_info = {
        "name": "TranslationService",
        "version": settings.app_version,
        "url": settings.api_url if settings.api_url else 'https://api.example.com'
    }

    logging.info(f"[STRIPE] Initialized Stripe SDK v{stripe.VERSION} with API version {stripe.api_version}")


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

    # Initialize Stripe SDK (Phase 1: v8.2.0 migration)
    await initialize_stripe()

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
