"""
Translate User Router - Individual user translation endpoint.

This endpoint is designed for non-enterprise individual users who pay per translation.
Key differences from /translate endpoint:
- No enterprise/subscription logic
- No company association
- Uses user_transactions collection instead of translation_transactions
- Fixed pricing ($0.10 per page)
- Uses Square transaction IDs (format: sqt_{20_random_chars})
- Requires userName field
"""

import base64
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    google_drive_error_to_http_exception,
)
from app.services.google_drive_service import google_drive_service
from app.utils.user_transaction_helper import create_user_transaction

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


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


class TranslateUserRequest(BaseModel):
    """Request model for individual user translation."""

    files: List[UserFileInfo]
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
async def translate_user_files(request: TranslateUserRequest = Body(...)):
    """
    Individual user translation endpoint (non-enterprise).

    This endpoint handles file uploads and translation requests for individual users
    who pay per translation (no subscription model).

    Workflow:
    1. Validate email, languages, and files
    2. Create Google Drive folder structure: {user_email}/Temp/
    3. Upload files to Temp folder
    4. Estimate page count for pricing
    5. Create user transaction records with Square transaction IDs
    6. Return pricing and file metadata for payment processing

    Key differences from /translate:
    - No enterprise/subscription logic
    - Uses user_transactions collection
    - Fixed pricing: $0.10 per page
    - Square transaction IDs (sqt_{20_chars})
    - Requires userName field

    Args:
        request: Translation request with files, languages, email, userName

    Returns:
        JSONResponse with file metadata, pricing, and Square transaction IDs

    Raises:
        HTTPException: For validation errors or upload failures
    """
    # Initialize timing tracker
    request_start_time = time.time()

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

    stored_files = []
    total_units = 0
    square_transaction_ids = []
    cost_per_unit = 0.10  # Fixed pricing for individual users

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

            # Update file metadata
            log_step(f"FILE {i} METADATA UPDATE", "Setting file properties")
            await google_drive_service.update_file_properties(
                file_id=file_result["file_id"],
                properties={
                    "customer_email": request.email,
                    "user_name": request.userName,
                    "source_language": request.sourceLanguage,
                    "target_language": request.targetLanguage,
                    "page_count": str(page_count),
                    "unit_type": unit_type,
                    "status": "awaiting_payment",
                    "upload_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "original_filename": file_info.name,
                },
            )

            # Create user transaction record
            square_tx_id = generate_square_transaction_id()
            log_step(
                f"FILE {i} TRANSACTION CREATE", f"Square ID: {square_tx_id}"
            )

            # Build documents array (single file per transaction)
            documents = [{
                "file_name": file_info.name,
                "file_size": file_info.size,
                "original_url": file_result.get("google_drive_url", ""),
                "translated_url": None,
                "translated_name": None,
                "status": "uploaded",
                "uploaded_at": datetime.now(timezone.utc),
                "translated_at": None,
                "processing_started_at": None,
                "processing_duration": None,
            }]

            tx_id = await create_user_transaction(
                user_name=request.userName,
                user_email=request.email,
                documents=documents,
                number_of_units=page_count,
                unit_type=unit_type,
                cost_per_unit=cost_per_unit,
                source_language=request.sourceLanguage,
                target_language=request.targetLanguage,
                square_transaction_id=square_tx_id,
                date=datetime.now(timezone.utc),
                status="processing",
            )

            if tx_id:
                square_transaction_ids.append(square_tx_id)
                log_step(f"FILE {i} TRANSACTION CREATED", f"TX ID: {square_tx_id}")
            else:
                log_step(f"FILE {i} TRANSACTION FAILED", "Transaction creation failed")

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
                    "square_transaction_id": square_tx_id,
                }
            )
            print(
                f"   Successfully uploaded: '{file_info.name}' -> "
                f"Google Drive ID: {file_result['file_id']}, "
                f"{page_count} {unit_type}s, Square TX: {square_tx_id}"
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
    # SUMMARY AND RESPONSE
    # ========================================================================
    successful_uploads = len([f for f in stored_files if f["status"] == "stored"])
    failed_uploads = len([f for f in stored_files if f["status"] == "failed"])

    print(f"UPLOAD COMPLETE: {successful_uploads} successful, {failed_uploads} failed")
    print(f"Total units for pricing: {total_units}")
    print(f"Total amount: ${total_units * cost_per_unit:.2f}")
    print(f"Customer: {request.userName} ({request.email})")
    print(f"Square transaction IDs: {len(square_transaction_ids)}")

    total_amount = total_units * cost_per_unit
    amount_cents = int(total_amount * 100)

    log_step(
        "RESPONSE PREPARE",
        f"Success: {successful_uploads}/{len(request.files)} files, "
        f"{total_units} units, ${total_amount:.2f}",
    )

    response_data = {
        "success": True,
        "data": {
            "id": storage_id,
            "status": "stored",
            "progress": 100,
            "message": "Files uploaded successfully. Ready for payment.",
            # Pricing information (frontend expects these exact field names)
            "pricing": {
                "total_pages": total_units,  # Changed from total_units to match frontend
                "price_per_page": cost_per_unit,  # Changed from cost_per_unit to match frontend
                "total_amount": total_amount,
                "currency": "usd",  # Lowercase to match frontend expectations
                "customer_type": "individual",  # Added for frontend
                "transaction_ids": square_transaction_ids,  # Moved from data level to pricing
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
