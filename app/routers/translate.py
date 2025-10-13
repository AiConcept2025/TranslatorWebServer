"""
Translation API endpoints.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional
import uuid
import re

router = APIRouter(prefix="/api", tags=["Translation"])

class FileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str

class TranslateRequest(BaseModel):
    files: List[FileInfo]
    sourceLanguage: str
    targetLanguage: str
    email: EmailStr
    paymentIntentId: Optional[str] = None

@router.post("/translate")
async def store_files_on_google_drive(request: TranslateRequest):
    """
    Store files on Google Drive temp subdirectory.
    NO translation processing - only file storage.
    """
    print(f"Hello World - Store files endpoint called for {len(request.files)} files")
    print(f"Hello World - Storing files for: {request.sourceLanguage} -> {request.targetLanguage}")
    print(f"Hello World - Customer email: {request.email}")
    
    # Validate email format (additional validation beyond EmailStr)
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(request.email):
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
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source language: {request.sourceLanguage}"
        )
    
    if request.targetLanguage not in valid_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target language: {request.targetLanguage}"
        )
    
    if request.sourceLanguage == request.targetLanguage:
        raise HTTPException(
            status_code=400,
            detail="Source and target languages cannot be the same"
        )
    
    # Validate files
    if not request.files:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required"
        )
    
    if len(request.files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 files allowed per request"
        )
    
    # Import Google Drive service
    from app.services.google_drive_service import google_drive_service
    from app.exceptions.google_drive_exceptions import GoogleDriveError, google_drive_error_to_http_exception
    
    # Create Google Drive folder structure
    try:
        folder_id = await google_drive_service.create_customer_folder_structure(request.email)
        print(f"Hello World - Created Google Drive folder structure: {folder_id}")
    except GoogleDriveError as e:
        print(f"Hello World - Google Drive error: {e}")
        raise google_drive_error_to_http_exception(e)
    except Exception as e:
        print(f"Hello World - Unexpected error creating folder: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create folder structure: {str(e)}"
        )
    
    # Generate storage ID
    storage_id = f"store_{uuid.uuid4().hex[:10]}"
    
    print(f"Hello World - Created storage job: {storage_id}")
    print(f"Hello World - Files will be stored in Google Drive temp folder: {folder_id}")
    
    # Store file metadata in Google Drive (simulated file storage for now)
    stored_files = []
    for file_info in request.files:
        try:
            # Create file metadata for storage
            file_metadata = {
                "filename": file_info.name,
                "size": file_info.size,
                "type": file_info.type,
                "source_language": request.sourceLanguage,
                "target_language": request.targetLanguage,
                "customer_email": request.email
            }
            
            # Store dummy content (in real implementation this would be actual file content)
            dummy_content = f"File data for {file_info.name} ({file_info.size} bytes)".encode('utf-8')
            
            file_result = await google_drive_service.upload_file_to_folder(
                file_content=dummy_content,
                filename=file_info.name,
                folder_id=folder_id,
                target_language=request.targetLanguage
            )
            
            stored_files.append({
                "file_id": file_result['file_id'],
                "filename": file_info.name,
                "status": "stored",
                "google_drive_url": file_result.get('google_drive_url')
            })
            print(f"Hello World - Stored file in Google Drive: {file_info.name}")
            
        except Exception as e:
            print(f"Hello World - Failed to store file {file_info.name}: {e}")
            stored_files.append({
                "file_id": None,
                "filename": file_info.name,
                "status": "failed",
                "error": str(e)
            })
    
    # Calculate total pages for pricing
    total_pages = 0
    for file_info in request.files:
        # Estimate pages based on file size (rough estimate: 2KB per page)
        estimated_pages = max(1, file_info.size // 2048)
        total_pages += estimated_pages
    
    # Calculate pricing
    price_per_page = 0.10  # $0.10 per page
    total_amount = total_pages * price_per_page
    amount_cents = int(total_amount * 100)  # Convert to cents for payment processing
    
    successful_file_ids = [f["file_id"] for f in stored_files if f["status"] == "stored" and f["file_id"]]
    failed_files = [f for f in stored_files if f["status"] == "failed"]
    
    print(f"UPLOAD COMPLETE: {len(successful_file_ids)} successful, {len(failed_files)} failed")
    print(f"Estimated pages: {total_pages}, Total amount: ${total_amount:.2f}")
    print(f"Files stored in Temp folder, awaiting payment")
    
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "pricing": {
                    "total_pages": total_pages,
                    "price_per_page": price_per_page,
                    "total_amount": total_amount,
                    "currency": "USD"
                },
                "customer": {
                    "email": request.email,
                    "temp_folder_id": folder_id
                },
                "payment": {
                    "amount_cents": amount_cents,
                    "customer_email": request.email
                },
                "files": {
                    "successful": len(successful_file_ids),
                    "failed": len(failed_files),
                    "total": len(request.files)
                }
            },
            "error": None
        }
    )