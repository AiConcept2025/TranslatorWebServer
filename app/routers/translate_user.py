"""
Translate User Router - User translation endpoint (individual + enterprise).

This endpoint handles translation requests for both individual and enterprise users.
It automatically detects authenticated enterprise users and updates their subscriptions.

Key features:
- Individual users (no auth): Pay per translation with Square payment IDs
- Enterprise users (with auth): Subscription usage automatically tracked
- Uses user_transactions collection
- Tiered pricing based on pricing service
- Uses Square transaction IDs (format: sqt_{20_random_chars})
- Requires userName field
"""

import base64
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Literal

from fastapi import APIRouter, Body, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    google_drive_error_to_http_exception,
)
from app.middleware.auth_middleware import get_optional_user
from app.services.google_drive_service import google_drive_service
from app.services.pricing_service import pricing_service
from app.services.subscription_service import subscription_service
from app.models.subscription import UsageUpdate
from app.utils.user_transaction_helper import create_user_transaction

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Module load marker - will appear in server logs when module is loaded
logger.warning("🔄 TRANSLATE_USER MODULE LOADED WITH CUSTOMER TYPE FIX - v3.0")


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class UserFileInfo(BaseModel):
    """File information from client (with base64 content)."""

    id: str
    name: str
    size: int
    type: str
    content: str  # Base64-encoded file content


# Per-file translation mode info (for file-level mode selection)
class FileTranslationModeInfo(BaseModel):
    """Per-file translation mode specification."""
    fileName: str
    translationMode: Literal['automatic', 'human', 'formats', 'handwriting'] = 'automatic'


class TranslateUserRequest(BaseModel):
    """Request model for individual user translation."""

    files: List[UserFileInfo]
    fileTranslationModes: Optional[List[FileTranslationModeInfo]] = None  # Per-file translation modes
    sourceLanguage: str
    targetLanguage: str
    email: EmailStr
    userName: str  # Required for user transactions
    paymentIntentId: Optional[str] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def generate_square_transaction_id() -> str:
    """
    Generate Square-compatible transaction ID.

    Format: sqt_{20_random_chars}
    Uses UUID hex to ensure uniqueness.
    """
    random_chars = uuid.uuid4().hex[:20]
    return f"sqt_{random_chars}"


def estimate_page_count(filename: str, file_size: int) -> int:
    """
    Estimate page count based on file type and size.

    Args:
        filename: Name of the file
        file_size: Size of file in bytes

    Returns:
        Estimated page count (minimum 1)
    """
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        # PDF: ~50KB per page
        return max(1, file_size // 50000)
    elif filename_lower.endswith((".doc", ".docx")):
        # Word docs: ~25KB per page
        return max(1, file_size // 25000)
    elif filename_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp")):
        # Images: 1 page per image
        return 1
    else:
        # Default: estimate conservatively
        return max(1, file_size // 50000)


def get_unit_type(filename: str) -> str:
    """
    Determine unit type based on file extension.

    Args:
        filename: Name of the file

    Returns:
        Unit type: "page"
    """
    # For this endpoint, all files use "page" as unit type
    return "page"


def validate_email_format(email: str) -> None:
    """
    Validate email format (additional validation beyond EmailStr).

    Args:
        email: Email address to validate

    Raises:
        HTTPException: If email format is invalid
    """
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if not email_pattern.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")


def validate_email_domain(email: str) -> None:
    """
    Check for disposable email domains.

    Args:
        email: Email address to validate

    Raises:
        HTTPException: If email is from disposable domain
    """
    disposable_domains = ["tempmail.org", "10minutemail.com", "guerrillamail.com"]
    email_domain = email.split("@")[1].lower()
    if email_domain in disposable_domains:
        raise HTTPException(
            status_code=400, detail="Disposable email addresses are not allowed"
        )


def validate_language_code(language: str, language_type: str) -> None:
    """
    Validate language code against supported languages.

    Args:
        language: Language code to validate
        language_type: "source" or "target" for error messaging

    Raises:
        HTTPException: If language code is invalid
    """
    valid_languages = [
        "en",
        "es",
        "fr",
        "de",
        "it",
        "pt",
        "ru",
        "zh",
        "ja",
        "ko",
        "ar",
        "hi",
        "nl",
        "pl",
        "tr",
        "sv",
        "da",
        "no",
        "fi",
        "th",
        "vi",
        "uk",
        "cs",
        "hu",
        "ro",
    ]

    if language not in valid_languages:
        raise HTTPException(
            status_code=400, detail=f"Invalid {language_type} language: {language}"
        )


# ============================================================================
# ENDPOINT
# ============================================================================


@router.post("/translate-user", tags=["Translation"])
async def translate_user_files(
    request: TranslateUserRequest = Body(...),
    current_user: Optional[Dict] = Depends(get_optional_user)
):
    """
    User translation endpoint for both individual and enterprise users.

    This endpoint handles file uploads and translation requests. It automatically
    detects if the user is authenticated as an enterprise user and updates their
    subscription accordingly.

    Workflow:
    1. Validate email, languages, and files
    2. Create Google Drive folder structure: {user_email}/Temp/
    3. Upload files to Temp folder
    4. Estimate page count for pricing
    5. Create user transaction records with Square transaction IDs
    6. **NEW**: If enterprise user (authenticated), update subscription usage
    7. Return pricing and file metadata for payment processing

    Authentication (optional):
    - If Authorization header present with valid token → enterprise user
    - Enterprise users: subscription usage automatically updated
    - Individual users (no auth): pay per translation

    Args:
        request: Translation request with files, languages, email, userName
        current_user: Optional authenticated user data (from Authorization header)

    Returns:
        JSONResponse with file metadata, pricing, and Square transaction IDs

    Raises:
        HTTPException: For validation errors or upload failures
    """
    # Initialize timing tracker
    request_start_time = time.time()

    # DEBUG: Log authentication status immediately
    logger.info(f"🔐 AUTHENTICATION DEBUG: current_user present={current_user is not None}")
    if current_user:
        logger.info(f"   User email: {current_user.get('email')}")
        logger.info(f"   Company: {current_user.get('company_name')}")
        logger.info(f"   Permission: {current_user.get('permission_level')}")
    else:
        logger.warning(f"   ⚠️  No authentication (current_user is None)")

    def log_step(step_name: str, details: str = ""):
        """Log step with timing."""
        elapsed = time.time() - request_start_time
        msg = f"[TRANSLATE-USER {elapsed:6.2f}s] {step_name}"
        if details:
            msg += f" - {details}"
        logging.info(msg)
        print(msg)

    # ========================================================================
    # RAW INCOMING DATA
    # ========================================================================
    print("=" * 100)
    print("[RAW INCOMING DATA] /translate-user ENDPOINT REACHED")
    print(f"[RAW INCOMING DATA] Request Data:")
    print(f"[RAW INCOMING DATA]   - User Name: {request.userName}")
    print(f"[RAW INCOMING DATA]   - User Email: {request.email}")
    print(f"[RAW INCOMING DATA]   - Source Language: {request.sourceLanguage}")
    print(f"[RAW INCOMING DATA]   - Target Language: {request.targetLanguage}")
    print(f"[RAW INCOMING DATA]   - File Translation Modes: {len(request.fileTranslationModes) if request.fileTranslationModes else 0} entries")
    if request.fileTranslationModes:
        for mode_info in request.fileTranslationModes:
            print(f"[RAW INCOMING DATA]     - {mode_info.fileName}: {mode_info.translationMode}")
    print(f"[RAW INCOMING DATA]   - Number of Files: {len(request.files)}")
    print(
        f"[RAW INCOMING DATA]   - Payment Intent ID: {request.paymentIntentId or 'None'}"
    )
    print(f"[RAW INCOMING DATA] Files Details:")
    for i, file_info in enumerate(request.files, 1):
        print(
            f"[RAW INCOMING DATA]   File {i}: '{file_info.name}' | "
            f"{file_info.size:,} bytes | Type: {file_info.type} | ID: {file_info.id}"
        )
    print("=" * 100)

    log_step("REQUEST RECEIVED", f"User: {request.userName} ({request.email})")
    log_step(
        "REQUEST DETAILS",
        f"{request.sourceLanguage} -> {request.targetLanguage}, Files: {len(request.files)}",
    )

    # ========================================================================
    # VALIDATION
    # ========================================================================
    log_step("VALIDATION START", "Validating request data")

    # Validate email format
    try:
        validate_email_format(request.email)
        validate_email_domain(request.email)
    except HTTPException as e:
        log_step("VALIDATION FAILED", f"Email validation: {e.detail}")
        raise

    # Validate language codes
    try:
        validate_language_code(request.sourceLanguage, "source")
        validate_language_code(request.targetLanguage, "target")
    except HTTPException as e:
        log_step("VALIDATION FAILED", f"Language validation: {e.detail}")
        raise

    if request.sourceLanguage == request.targetLanguage:
        log_step("VALIDATION FAILED", "Source and target languages are the same")
        raise HTTPException(
            status_code=400, detail="Source and target languages cannot be the same"
        )

    log_step(
        "VALIDATION PASSED",
        f"Languages: {request.sourceLanguage} -> {request.targetLanguage}",
    )

    # Validate files
    if not request.files:
        log_step("VALIDATION FAILED", "No files provided")
        raise HTTPException(status_code=400, detail="At least one file is required")

    if len(request.files) > 10:
        log_step("VALIDATION FAILED", f"Too many files: {len(request.files)}")
        raise HTTPException(
            status_code=400, detail="Maximum 10 files allowed per request"
        )

    log_step("VALIDATION COMPLETE", f"{len(request.files)} file(s) validated")

    # ========================================================================
    # GOOGLE DRIVE FOLDER CREATION
    # ========================================================================
    log_step("FOLDER CREATE START", f"Creating structure for: {request.email}")

    try:
        # Individual user: user_email/Temp/
        print(f"Creating individual folder structure: {request.email}/Temp/")
        folder_id = await google_drive_service.create_customer_folder_structure(
            customer_email=request.email, company_name=None
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
            status_code=500, detail=f"Failed to create folder structure: {str(e)}"
        )

    # ========================================================================
    # FILE UPLOAD AND PROCESSING
    # ========================================================================
    storage_id = f"store_{uuid.uuid4().hex[:10]}"
    print(f"Created storage job: {storage_id}")
    print(f"Target folder: {request.email}/Temp/ (ID: {folder_id})")
    print(f"Starting file uploads to Google Drive...")

    # ✅ FIX: Generate ONE transaction ID for entire batch (not per file)
    batch_square_tx_id = generate_square_transaction_id()
    log_step("BATCH TRANSACTION ID", f"Generated batch Square ID: {batch_square_tx_id}")
    print(f"Generated batch Square transaction ID: {batch_square_tx_id}")

    stored_files = []
    all_documents = []  # ✅ FIX: Accumulate all documents for single transaction
    total_units = 0
    # Pricing will be calculated after we know total_units (pricing varies by tier)
    cost_per_unit = 0.0  # Initialize to avoid undefined variable errors
    total_amount = 0.0

    # Determine customer type based on authentication
    customer_type = "enterprise" if (current_user and current_user.get("company_name")) else "individual"
    log_step("CUSTOMER TYPE", f"Detected as: {customer_type}")
    print(f"Customer type: {customer_type}")

    # Build file-level translation modes dict from request
    file_translation_modes: Dict[str, str] = {}
    if request.fileTranslationModes:
        for mode_info in request.fileTranslationModes:
            file_translation_modes[mode_info.fileName] = mode_info.translationMode
        log_step("FILE MODES", f"Per-file translation modes: {file_translation_modes}")
    else:
        log_step("FILE MODES", "No per-file modes specified, using default (automatic)")

    for i, file_info in enumerate(request.files, 1):
        try:
            log_step(
                f"FILE {i} UPLOAD START",
                f"'{file_info.name}' ({file_info.size:,} bytes)",
            )
            print(
                f"   Uploading file {i}/{len(request.files)}: '{file_info.name}'"
            )

            # Decode base64 content
            try:
                file_content = base64.b64decode(file_info.content)
                log_step(f"FILE {i} BASE64 DECODED", f"Decoded {len(file_content):,} bytes")
            except Exception as e:
                log_step(f"FILE {i} DECODE FAILED", f"Error: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to decode file content for '{file_info.name}': {str(e)}",
                )

            # Estimate page count
            page_count = estimate_page_count(file_info.name, file_info.size)
            unit_type = get_unit_type(file_info.name)
            total_units += page_count
            log_step(f"FILE {i} PAGE COUNT", f"{page_count} {unit_type}s estimated")

            # Upload to Google Drive
            log_step(f"FILE {i} GDRIVE UPLOAD", f"Uploading to folder {folder_id}")
            file_result = await google_drive_service.upload_file_to_folder(
                file_content=file_content,
                filename=file_info.name,
                folder_id=folder_id,
                target_language=request.targetLanguage,
            )
            log_step(f"FILE {i} GDRIVE UPLOADED", f"File ID: {file_result['file_id']}")

            # Get translation mode for this specific file (default to automatic)
            file_mode = file_translation_modes.get(file_info.name, "automatic")

            # Update file metadata (initial properties)
            log_step(f"FILE {i} METADATA UPDATE", "Setting initial file properties")
            initial_properties = {
                "customer_email": request.email,
                "user_name": request.userName,
                "source_language": request.sourceLanguage,
                "target_language": request.targetLanguage,
                "page_count": str(page_count),
                "unit_type": unit_type,
                "status": "awaiting_payment",
                "upload_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "original_filename": file_info.name,
                "translation_mode": file_mode,  # Add translation mode to metadata
            }
            await google_drive_service.update_file_properties(
                file_id=file_result["file_id"],
                properties=initial_properties,
            )

            # Log all metadata values being set
            print(f"   📋 File Metadata Set on Google Drive:")
            for key, value in initial_properties.items():
                print(f"      • {key}: {value}")

            # ✅ FIX: Accumulate document in batch array (don't create transaction yet)
            all_documents.append({
                "file_name": file_info.name,
                "file_size": file_info.size,
                "page_count": page_count,  # Include page count for logging
                "original_url": file_result.get("google_drive_url", ""),
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None,
                "translation_mode": file_mode,  # Per-file translation mode
            })
            log_step(f"FILE {i} ADDED TO BATCH", f"Document added to batch transaction")

            log_step(
                f"FILE {i} COMPLETE",
                f"URL: {file_result.get('google_drive_url', 'N/A')}",
            )

            stored_files.append(
                {
                    "file_id": file_result["file_id"],
                    "filename": file_info.name,
                    "status": "stored",
                    "page_count": page_count,
                    "unit_type": unit_type,
                    "size": file_info.size,
                    "google_drive_url": file_result.get("google_drive_url"),
                    "square_transaction_id": batch_square_tx_id,  # ✅ FIX: Use batch ID
                }
            )
            print(
                f"   Successfully uploaded: '{file_info.name}' -> "
                f"Google Drive ID: {file_result['file_id']}, "
                f"{page_count} {unit_type}s"
            )

        except Exception as e:
            log_step(f"FILE {i} FAILED", f"Error: {str(e)}")
            print(f"   Failed to upload '{file_info.name}': {e}")
            stored_files.append(
                {
                    "file_id": None,
                    "filename": file_info.name,
                    "status": "failed",
                    "page_count": 0,
                    "unit_type": "page",
                    "size": file_info.size,
                    "error": str(e),
                }
            )

    # ========================================================================
    # CREATE BATCH TRANSACTION RECORD (ONCE for all files)
    # ========================================================================
    batch_transaction_id = None
    if all_documents:  # Only create if we have successfully uploaded documents
        log_step("BATCH TRANSACTION CREATE", f"Creating transaction with {len(all_documents)} documents")
        print(f"\n💾 Creating batch transaction record...")
        print(f"   Documents: {len(all_documents)}")
        print(f"   Total units: {total_units}")
        print(f"   Square TX ID: {batch_square_tx_id}")

        try:
            # Determine unit_type from first document (all should be same type)
            first_file = stored_files[0] if stored_files else {}
            unit_type = first_file.get("unit_type", "page")

            # Calculate pricing using pricing service
            # For enterprise users: pricing is informational (they use subscription units)
            # For individual users: pricing determines actual payment amount
            total_price_decimal = pricing_service.calculate_price(total_units, customer_type, "default")
            total_amount = float(total_price_decimal)
            # Back-calculate average cost per unit for database storage
            cost_per_unit = total_amount / total_units if total_units > 0 else 0
            log_step("PRICING CALCULATED",
                    f"Customer: {customer_type}, Total: ${total_amount:.2f} ({total_units} units @ avg ${cost_per_unit:.4f}/unit)")

            batch_transaction_id = await create_user_transaction(
                user_name=request.userName,
                user_email=request.email,
                documents=all_documents,  # ✅ FIX: All documents in one transaction
                number_of_units=total_units,
                unit_type=unit_type,
                cost_per_unit=cost_per_unit,
                source_language=request.sourceLanguage,
                target_language=request.targetLanguage,
                square_transaction_id=batch_square_tx_id,  # ✅ FIX: Single Square ID
                date=datetime.now(timezone.utc),
                status="processing",
            )

            if batch_transaction_id:
                log_step("BATCH TRANSACTION CREATED", f"TX ID: {batch_transaction_id}")
                print(f"   ✅ Batch transaction created: {batch_transaction_id}")

                # Update all files' metadata with the same transaction_id
                for file_info in stored_files:
                    if file_info.get("status") == "stored" and file_info.get("file_id"):
                        try:
                            await google_drive_service.update_file_properties(
                                file_id=file_info["file_id"],
                                properties={"transaction_id": batch_transaction_id},
                            )
                            print(f"   ✅ Updated {file_info['filename']} with transaction_id")
                        except Exception as e:
                            print(f"   ⚠️  Failed to update {file_info['filename']} metadata: {e}")
            else:
                log_step("BATCH TRANSACTION FAILED", "Transaction creation returned None")
                print(f"   ❌ Batch transaction creation failed")
        except Exception as e:
            log_step("BATCH TRANSACTION ERROR", f"Error: {str(e)}")
            print(f"   ❌ Error creating batch transaction: {e}")

    # ========================================================================
    # ENTERPRISE SUBSCRIPTION UPDATE (if authenticated user)
    # ========================================================================
    if current_user and total_units > 0:
        company_name = current_user.get("company_name")
        user_email = current_user.get("email")

        if company_name:
            log_step("ENTERPRISE USER DETECTED", f"Company: {company_name}, User: {user_email}")
            print(f"\n🏢 Enterprise user detected: {company_name}")
            print(f"   User: {user_email}")
            print(f"   Units to record: {total_units}")

            try:
                # Find active subscription for this company
                from app.database.mongodb import database
                subscription = await database.subscriptions.find_one({
                    "company_name": company_name,
                    "status": "active"
                })

                if subscription:
                    subscription_id = str(subscription["_id"])
                    log_step("SUBSCRIPTION FOUND", f"ID: {subscription_id}")
                    print(f"   Found active subscription: {subscription_id}")

                    # Record usage using subscription service
                    usage_data = UsageUpdate(
                        units_to_add=total_units,
                        use_promotional_units=False
                    )

                    log_step("RECORDING USAGE", f"Adding {total_units} units to subscription")
                    updated_subscription = await subscription_service.record_usage(
                        subscription_id,
                        usage_data
                    )

                    if updated_subscription:
                        # Find current active period (same logic as record_usage)
                        usage_periods = updated_subscription.get("usage_periods", [])
                        now = datetime.now(timezone.utc)
                        current_period = None
                        current_period_idx = None

                        for idx, period in enumerate(usage_periods):
                            period_start = period["period_start"]
                            period_end = period["period_end"]

                            # Handle timezone-aware comparison
                            if not period_start.tzinfo:
                                period_start = period_start.replace(tzinfo=timezone.utc)
                            if not period_end.tzinfo:
                                period_end = period_end.replace(tzinfo=timezone.utc)

                            if period_start <= now <= period_end:
                                current_period = period
                                current_period_idx = idx
                                break

                        if current_period:
                            units_used = current_period["units_used"]
                            units_allocated = current_period["units_allocated"]
                            promotional = current_period.get("promotional_units", 0)
                            remaining = units_allocated + promotional - units_used

                            log_step("SUBSCRIPTION UPDATED",
                                    f"Period {current_period_idx}: Units used: {units_used}, Remaining: {remaining}")
                            print(f"   ✅ Subscription updated successfully")
                            print(f"      Current period: {current_period_idx}")
                            print(f"      Units used: {units_used}")
                            print(f"      Units remaining: {remaining}")
                        else:
                            log_step("SUBSCRIPTION WARNING", "No current period found to display")
                            print(f"   ⚠️  No current active period found")
                    else:
                        log_step("SUBSCRIPTION UPDATE FAILED", "Service returned None")
                        print(f"   ⚠️  Subscription update returned None")
                else:
                    log_step("NO SUBSCRIPTION", f"No active subscription for {company_name}")
                    print(f"   ⚠️  No active subscription found for company: {company_name}")

            except Exception as e:
                log_step("SUBSCRIPTION UPDATE ERROR", f"Error: {str(e)}")
                print(f"   ⚠️  Failed to update subscription: {e}")
                logger.warning(f"Failed to update subscription for {company_name}: {e}")
                # Don't fail the request - subscription update is supplementary
        else:
            log_step("INDIVIDUAL USER", f"No company_name in user data")
            print(f"\n👤 Individual user (no company association)")
    else:
        if not current_user:
            log_step("NO AUTHENTICATION", "Request not authenticated")
            print(f"\n🔓 Unauthenticated request (individual user)")
        elif total_units == 0:
            log_step("NO UNITS", "No units to record")
            print(f"\n⚠️  No units to record")

    # ========================================================================
    # SUMMARY AND RESPONSE
    # ========================================================================
    successful_uploads = len([f for f in stored_files if f["status"] == "stored"])
    failed_uploads = len([f for f in stored_files if f["status"] == "failed"])

    print(f"\nUPLOAD COMPLETE: {successful_uploads} successful, {failed_uploads} failed")
    print(f"Total units for pricing: {total_units}")
    print(f"Total amount: ${total_amount:.2f}")
    print(f"Customer: {request.userName} ({request.email})")
    print(f"Batch transaction ID: {batch_transaction_id}")

    amount_cents = int(total_amount * 100)

    log_step(
        "RESPONSE PREPARE",
        f"Success: {successful_uploads}/{len(request.files)} files, "
        f"{total_units} units, ${total_amount:.2f}",
    )

    # Extract file_ids for easy access by frontend (for payment confirmation)
    uploaded_file_ids = [f["file_id"] for f in stored_files if f["status"] == "stored" and f["file_id"]]

    response_data = {
        "success": True,
        "data": {
            "id": storage_id,
            "status": "stored",
            "progress": 100,
            "message": "Files uploaded successfully. Ready for payment.",
            # File IDs for payment confirmation (frontend sends these to /confirm)
            "uploaded_file_ids": uploaded_file_ids,
            # Pricing information (frontend expects these exact field names)
            "pricing": {
                "total_pages": total_units,  # Changed from total_units to match frontend
                "price_per_page": cost_per_unit,  # Changed from cost_per_unit to match frontend
                "total_amount": total_amount,
                "currency": "usd",  # Lowercase to match frontend expectations
                "customer_type": customer_type,  # enterprise or individual based on authentication
                "transaction_ids": [batch_transaction_id] if batch_transaction_id else [],  # ✅ Database transaction ID (USER######), not Square ID
            },
            # File information
            "files": {
                "total_files": len(request.files),
                "successful_uploads": successful_uploads,
                "failed_uploads": failed_uploads,
                "stored_files": stored_files,
            },
            # Customer information
            "customer": {
                "email": request.email,
                "source_language": request.sourceLanguage,  # Added for frontend
                "target_language": request.targetLanguage,  # Added for frontend
            },
            # Payment information
            "payment": {
                "required": True,
                "amount_cents": amount_cents,
                "customer_email": request.email,
            },
            # User information (added for frontend)
            "user": {
                "permission_level": "user",
                "email": request.email,
                "full_name": request.userName,
            },
        },
        "error": None,
    }

    # ========================================================================
    # RAW OUTGOING DATA
    # ========================================================================
    print("=" * 100)
    print("[RAW OUTGOING DATA] /translate-user RESPONSE")
    print(f"[RAW OUTGOING DATA] Success: {response_data['success']}")
    print(f"[RAW OUTGOING DATA] Storage ID: {response_data['data']['id']}")
    print(f"[RAW OUTGOING DATA] Status: {response_data['data']['status']}")
    print(f"[RAW OUTGOING DATA] Message: {response_data['data']['message']}")
    print(f"[RAW OUTGOING DATA] Pricing:")
    print(
        f"[RAW OUTGOING DATA]   - Total Pages: {response_data['data']['pricing']['total_pages']}"
    )
    print(
        f"[RAW OUTGOING DATA]   - Price Per Page: ${response_data['data']['pricing']['price_per_page']}"
    )
    print(
        f"[RAW OUTGOING DATA]   - Total Amount: ${response_data['data']['pricing']['total_amount']:.2f}"
    )
    print(
        f"[RAW OUTGOING DATA]   - Currency: {response_data['data']['pricing']['currency']}"
    )
    print(
        f"[RAW OUTGOING DATA]   - Customer Type: {response_data['data']['pricing']['customer_type']}"
    )
    print(f"[RAW OUTGOING DATA] Files:")
    print(
        f"[RAW OUTGOING DATA]   - Total: {response_data['data']['files']['total_files']}"
    )
    print(
        f"[RAW OUTGOING DATA]   - Successful: {response_data['data']['files']['successful_uploads']}"
    )
    print(
        f"[RAW OUTGOING DATA]   - Failed: {response_data['data']['files']['failed_uploads']}"
    )
    print(
        f"[RAW OUTGOING DATA] Transaction IDs ({len(response_data['data']['pricing']['transaction_ids'])}): "
        f"{response_data['data']['pricing']['transaction_ids']}"
    )
    print(f"[RAW OUTGOING DATA] Customer: {request.userName} ({request.email})")
    print(
        f"[RAW OUTGOING DATA] Payment Required: {response_data['data']['payment']['required']}"
    )
    print(
        f"[RAW OUTGOING DATA] Payment Amount (cents): {response_data['data']['payment']['amount_cents']}"
    )
    print("=" * 100)

    log_step("RESPONSE SENDING", "Returning response to client")

    return JSONResponse(content=response_data, status_code=200)
