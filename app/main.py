"""
Main FastAPI application for the Translation Web Server.
"""

from fastapi import FastAPI, Request, HTTPException, Depends, Body
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
from app.routers import languages, upload, auth, subscriptions
from app.routers import payment_simplified as payment

# Import middleware and utilities (will create these next)
# Rate limiting removed per user request
from app.middleware.logging import LoggingMiddleware
from app.middleware.encoding_fix import EncodingFixMiddleware
from app.middleware.auth_middleware import get_current_user
from app.utils.health import health_checker


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
# 4. CORSMiddleware (innermost - adds headers last)
# 5. Endpoint
#
# IMPORTANT: CORSMiddleware must be innermost so it processes responses
# from ALL sources including timeout errors from outer middleware
# ============================================================================

# Add custom middleware FIRST (so they execute in the middle)
app.add_middleware(EncodingFixMiddleware)
app.add_middleware(LoggingMiddleware)

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
app.include_router(payment.router)
app.include_router(auth.router)
app.include_router(subscriptions.router)

# Import models for /translate endpoint
from pydantic import BaseModel, EmailStr
from typing import List, Optional

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
# Transaction Helper Function
# ============================================================================
async def create_transaction_record(
    file_info: dict,
    user_data: dict,
    request_data: TranslateRequest,
    subscription: Optional[dict],
    company_id: Optional[str],
    company_name: Optional[str],
    price_per_page: float
) -> Optional[str]:
    """
    Create transaction record for a single file upload.

    Args:
        file_info: Dict with file_id, filename, size, page_count, google_drive_url
        user_data: Current authenticated user data
        request_data: Original TranslateRequest
        subscription: Enterprise subscription (or None for individual)
        company_id: Enterprise company_id (or None for individual)
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

        # Build transaction document
        # IMPORTANT: Store actual email, not generated user_id
        transaction_doc = {
            "transaction_id": transaction_id,
            "user_id": request_data.email,  # Use actual email for folder lookup
            "original_file_url": file_info.get("google_drive_url", ""),
            "translated_file_url": "",  # Empty initially
            "source_language": request_data.sourceLanguage,
            "target_language": request_data.targetLanguage,
            "file_name": file_info.get("filename", ""),
            "file_size": file_info.get("size", 0),
            "units_count": file_info.get("page_count", 1),
            "price_per_unit": price_per_page,
            "total_price": file_info.get("page_count", 1) * price_per_page,
            "status": "started",
            "error_message": "",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        # Add enterprise-specific fields if applicable
        if company_id and subscription:
            transaction_doc["company_id"] = ObjectId(company_id)
            transaction_doc["company_name"] = company_name  # Store company name for folder lookup
            transaction_doc["subscription_id"] = ObjectId(str(subscription["_id"]))
            transaction_doc["unit_type"] = subscription.get("subscription_unit", "page")
        else:
            # Individual customer (no company or subscription)
            transaction_doc["company_id"] = None
            transaction_doc["company_name"] = None
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


# Direct translate endpoint (Google Drive upload)
@app.post("/translate", tags=["Translation"])
async def translate_files(
    request: TranslateRequest = Body(...),
    current_user: dict = Depends(get_current_user)
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
    print(f"[RAW INCOMING DATA] Authenticated User: {current_user.get('email', 'N/A')}")
    print(f"[RAW INCOMING DATA] Company ID: {current_user.get('company_id', 'N/A')}")
    print(f"[RAW INCOMING DATA] Permission: {current_user.get('permission_level', 'N/A')}")
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

    log_step("REQUEST RECEIVED", f"User: {current_user.get('email')}, Company: {current_user.get('company_id')}")
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

    # Detect customer type (enterprise with company_id vs individual without)
    # IMPORTANT: Do this BEFORE creating folders so we know which structure to create
    company_id = current_user.get("company_id")
    is_enterprise = company_id is not None
    company_name = None
    log_step("CUSTOMER TYPE DETECTED", f"{'Enterprise' if is_enterprise else 'Individual'} (company_id: {company_id})")
    logging.info(f"Customer type: {'enterprise' if is_enterprise else 'individual'}, company_id: {company_id}")

    # For enterprise users, get company name from database
    if is_enterprise:
        from app.database import database
        from bson import ObjectId
        try:
            company_doc = await database.companies.find_one({"_id": ObjectId(company_id)})
            if company_doc:
                company_name = company_doc.get("company_name", "Unknown Company")
                log_step("COMPANY NAME", f"Enterprise: {company_name}")
                print(f"Enterprise company: {company_name}")
            else:
                log_step("COMPANY NOT FOUND", f"Using company_id as fallback: {company_id}")
                company_name = f"Company_{company_id}"
        except Exception as e:
            log_step("COMPANY LOOKUP FAILED", f"Error: {e}")
            company_name = f"Company_{company_id}"

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
        log_step("SUBSCRIPTION QUERY", f"Querying for company_id: {company_id}")
        logging.info(f"Querying subscription for company_id: {company_id}")
        from app.services.subscription_service import subscription_service
        from bson import ObjectId
        from datetime import datetime, timezone

        subscriptions = await subscription_service.get_company_subscriptions(
            str(company_id),
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
            log_step("SUBSCRIPTION FOUND", f"Price: ${price_per_page} per {subscription.get('subscription_unit')}")
            logging.info(f"Using subscription pricing: ${price_per_page} per {subscription.get('subscription_unit')}")
        else:
            log_step("SUBSCRIPTION NOT FOUND", f"Using default pricing for company {company_id}")
            logging.warning(f"No active subscription found for company {company_id}, using default pricing")

    # Create transaction records for ALL uploaded files (enterprise + individual)
    successful_stored_files = [f for f in stored_files if f["status"] == "stored"]
    log_step("TRANSACTION CREATE START", f"Creating records for {len(successful_stored_files)} successful uploads")

    for stored_file in stored_files:
        if stored_file["status"] == "stored":
            transaction_id = await create_transaction_record(
                file_info=stored_file,
                user_data=current_user,
                request_data=request,
                subscription=subscription if is_enterprise else None,
                company_id=company_id if is_enterprise else None,
                company_name=company_name if is_enterprise else None,
                price_per_page=price_per_page
            )

            if transaction_id:
                transaction_ids.append(transaction_id)
                log_step("TRANSACTION CREATED", f"ID: {transaction_id} for {stored_file['filename']}")

    log_step("TRANSACTION CREATE COMPLETE", f"Created {len(transaction_ids)} transaction(s)")

    # Prepare and log response
    log_step("RESPONSE PREPARE", f"Success: {successful_uploads}/{len(request.files)} files, {total_pages} pages, ${total_pages * price_per_page:.2f}")

    response_data = {
        "success": True,
        "data": {
            "id": storage_id,
            "status": "stored",
            "progress": 100,
            "message": f"Files uploaded successfully. Ready for payment.",

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
                    "required": True,
                    "amount_cents": int(total_pages * price_per_page * 100),  # Dynamic: Convert to cents
                    "description": f"Translation service: {successful_uploads} files, {total_pages} pages",
                    "customer_email": request.email
                }
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
    print("=" * 100)

    return JSONResponse(content=response_data)


# ============================================================================
# Transaction Confirmation/Decline Models
# ============================================================================
class TransactionActionRequest(BaseModel):
    transaction_ids: List[str]


# ============================================================================
# Transaction Confirmation Endpoint
# ============================================================================
@app.post("/api/transactions/confirm", tags=["Transactions"])
async def confirm_transactions(
    request: TransactionActionRequest = Body(...),
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
        print(f"[CONFIRM DEBUG] Fetching {len(request.transaction_ids)} transaction(s) from database...")
        for txn_id in request.transaction_ids:
            txn = await database.translation_transactions.find_one({"transaction_id": txn_id})
            if txn:
                transactions.append(txn)
                print(f"[CONFIRM DEBUG] Found transaction {txn_id}")
                print(f"[CONFIRM DEBUG]   - user_id: {txn.get('user_id', 'MISSING')}")
                print(f"[CONFIRM DEBUG]   - original_file_url: {txn.get('original_file_url', 'MISSING')}")
                print(f"[CONFIRM DEBUG]   - file_name: {txn.get('file_name', 'MISSING')}")
                print(f"[CONFIRM DEBUG]   - status: {txn.get('status', 'MISSING')}")
            else:
                logging.warning(f"[CONFIRM] Transaction {txn_id} not found")
                print(f"[CONFIRM DEBUG] ❌ Transaction {txn_id} NOT FOUND in database")

        if not transactions:
            raise HTTPException(status_code=404, detail="No valid transactions found")

        # Extract customer email and company name from first transaction
        first_txn = transactions[0]
        customer_email = first_txn.get("user_id", "")  # user_id contains email
        company_name = first_txn.get("company_name")  # company_name for enterprise customers
        print(f"[CONFIRM DEBUG] Customer email extracted: {customer_email}")
        print(f"[CONFIRM DEBUG] Company name extracted: {company_name or 'None (individual customer)'}")

        # Get file IDs from original_file_url (Google Drive URLs contain file ID)
        file_ids = []
        print(f"[CONFIRM DEBUG] Extracting file IDs from {len(transactions)} transaction(s)...")
        for i, txn in enumerate(transactions, 1):
            url = txn.get("original_file_url", "")
            print(f"[CONFIRM DEBUG] Transaction {i}/{len(transactions)}: URL = '{url}'")

            # Extract file ID from Google Drive URL - handles multiple formats:
            # - Google Docs: https://docs.google.com/document/d/{file_id}/edit
            # - Google Sheets: https://docs.google.com/spreadsheets/d/{file_id}/edit
            # - Google Drive: https://drive.google.com/file/d/{file_id}/view
            file_id = None
            if "/document/d/" in url:
                file_id = url.split("/document/d/")[1].split("/")[0]
                print(f"[CONFIRM DEBUG]   ✅ Extracted file_id from /document/d/ pattern: {file_id}")
            elif "/spreadsheets/d/" in url:
                file_id = url.split("/spreadsheets/d/")[1].split("/")[0]
                print(f"[CONFIRM DEBUG]   ✅ Extracted file_id from /spreadsheets/d/ pattern: {file_id}")
            elif "/file/d/" in url:
                file_id = url.split("/file/d/")[1].split("/")[0]
                print(f"[CONFIRM DEBUG]   ✅ Extracted file_id from /file/d/ pattern: {file_id}")
            else:
                print(f"[CONFIRM DEBUG]   ❌ URL does not match any known Google Drive pattern - SKIPPED")

            if file_id:
                file_ids.append(file_id)

        print(f"[CONFIRM DEBUG] Total file IDs extracted: {len(file_ids)}")
        print(f"[CONFIRM DEBUG] File IDs: {file_ids}")

        if company_name:
            logging.info(f"[CONFIRM] Moving {len(file_ids)} files from {company_name}/{customer_email}/Temp/ to {company_name}/{customer_email}/Inbox/")
            print(f"[CONFIRM] Moving {len(file_ids)} files from {company_name}/{customer_email}/Temp/ to Inbox/")
        else:
            logging.info(f"[CONFIRM] Moving {len(file_ids)} files from {customer_email}/Temp/ to {customer_email}/Inbox/")
            print(f"[CONFIRM] Moving {len(file_ids)} files from {customer_email}/Temp/ to Inbox/")

        # Move files using existing Google Drive service function
        move_result = await google_drive_service.move_files_to_inbox_on_payment_success(
            customer_email=customer_email,
            file_ids=file_ids,
            company_name=company_name
        )

        # Verify files are actually in the Inbox folder
        print(f"[CONFIRM VERIFY] Verifying {len(move_result['moved_files'])} files in Inbox...")
        inbox_folder_id = move_result['inbox_folder_id']
        verified_files = []

        for moved_file in move_result['moved_files']:
            file_id = moved_file['file_id']
            try:
                # Query Google Drive to verify file is in Inbox
                file_info_raw = await asyncio.to_thread(
                    lambda: google_drive_service.service.files().get(
                        fileId=file_id,
                        fields='id,name,parents,webViewLink,webContentLink'
                    ).execute()
                )

                current_parents = file_info_raw.get('parents', [])
                is_in_inbox = inbox_folder_id in current_parents

                file_url = file_info_raw.get('webViewLink', f"https://drive.google.com/file/d/{file_id}/view")

                verified_files.append({
                    'file_id': file_id,
                    'file_name': moved_file.get('file_name', file_info_raw.get('name', 'Unknown')),
                    'status': 'verified_in_inbox' if is_in_inbox else 'move_reported_but_not_verified',
                    'google_drive_url': file_url,
                    'direct_link': file_url,
                    'is_in_inbox': is_in_inbox,
                    'current_parents': current_parents
                })

                if is_in_inbox:
                    print(f"[CONFIRM VERIFY] ✅ File {file_id} VERIFIED in Inbox")
                    print(f"[CONFIRM VERIFY]    URL: {file_url}")
                else:
                    print(f"[CONFIRM VERIFY] ⚠️ File {file_id} NOT in Inbox (parents: {current_parents})")

            except Exception as e:
                print(f"[CONFIRM VERIFY] ❌ Failed to verify file {file_id}: {e}")
                verified_files.append({
                    'file_id': file_id,
                    'file_name': moved_file.get('file_name', 'Unknown'),
                    'status': 'verification_failed',
                    'error': str(e)
                })

        # Update transaction status to "confirmed"
        for txn_id in request.transaction_ids:
            await database.translation_transactions.update_one(
                {"transaction_id": txn_id},
                {
                    "$set": {
                        "status": "confirmed",
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            logging.info(f"[CONFIRM] Transaction {txn_id} status updated to 'confirmed'")
            print(f"[CONFIRM] Transaction {txn_id} confirmed")

        verified_count = len([f for f in verified_files if f.get('is_in_inbox', False)])

        response = {
            "success": True,
            "message": f"Successfully confirmed {len(request.transaction_ids)} transaction(s)",
            "data": {
                "confirmed_transactions": len(request.transaction_ids),
                "total_files": len(file_ids),
                "moved_files": move_result['moved_successfully'],
                "verified_in_inbox": verified_count,
                "failed_moves": move_result['failed_moves'],
                "inbox_folder_id": inbox_folder_id,
                "inbox_folder_url": f"https://drive.google.com/drive/folders/{inbox_folder_id}",
                "files": verified_files,
                "move_details": move_result
            }
        }

        logging.info(f"[CONFIRM] Success: {len(request.transaction_ids)} transactions confirmed, {verified_count}/{len(file_ids)} files verified in Inbox")
        print(f"[CONFIRM] Complete: {len(request.transaction_ids)} transactions confirmed, {verified_count}/{len(file_ids)} files VERIFIED in Inbox")
        print(f"[CONFIRM] Inbox URL: https://drive.google.com/drive/folders/{inbox_folder_id}")

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
        # Get general health status
        health_status = await health_checker.check_health()

        # Add MongoDB health check
        from app.database import database
        mongodb_health = await database.health_check()
        health_status["database"] = mongodb_health

        # Overall health status
        overall_healthy = (
            health_status["status"] == "healthy" and
            mongodb_health.get("healthy", False)
        )

        if overall_healthy:
            return JSONResponse(
                content=health_status,
                status_code=200
            )
        else:
            return JSONResponse(
                content=health_status,
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
