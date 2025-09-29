"""
File upload API endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import os
import logging

from app.models.requests import FileUploadRequest
from app.models.responses import FileUploadResponse, FileUploadResult
from app.utils.file_validation import file_validator
from app.services.google_drive_service import google_drive_service
from app.services.file_service import file_service
from app.services.page_counter_service import page_counter_service
from app.config import settings
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    google_drive_error_to_http_exception
)

router = APIRouter(prefix="/api", tags=["File Upload"])

@router.post("/upload", response_model=FileUploadResponse)
async def upload_files(
    customer_email: Optional[str] = Form(None, description="Customer email address (uses default if not provided)"),
    target_language: str = Form(..., description="Target language code"),
    files: List[UploadFile] = File(..., description="Files to upload")
):
    """
    Upload files with customer information and target language.
    
    **Supported file types:**
    - **Documents**: PDF (.pdf), Word (.doc, .docx) - Max 100MB each
    - **Images**: JPEG (.jpeg, .jpg), PNG (.png), TIFF (.tiff, .tif) - Max 50MB each
    
    **Security features:**
    - File signature validation (magic numbers)
    - Content type validation
    - Executable file rejection
    - Size limit enforcement
    
    **Workflow:**
    1. Validate customer email and target language
    2. Validate each uploaded file (type, size, signature)
    3. Create Google Drive folder structure: {customer_email}/Temp/
    4. Store files with target language metadata
    5. Return detailed upload results
    """
    # Use default customer email if none provided
    if customer_email is None:
        customer_email = settings.default_customer_email
        print(f"Hello World - Using default customer email: {customer_email}")
    
    print(f"Hello World - New upload endpoint called with {len(files)} files for {customer_email}")
    
    # Validate request parameters using Pydantic model
    try:
        request_data = FileUploadRequest(
            customer_email=customer_email,
            target_language=target_language
        )
        print(f"Hello World - Request validation successful for {request_data.customer_email}")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid request parameters: {str(e)}"
        )
    
    if not files:
        raise HTTPException(
            status_code=400,
            detail="No files provided"
        )
    
    print(f"Hello World - Starting upload process for {len(files)} files")
    
    # Create Google Drive folder structure
    try:
        folder_id = await google_drive_service.create_customer_folder_structure(
            request_data.customer_email
        )
        logging.info(f"Created folder structure: {folder_id}")
    except GoogleDriveError as e:
        logging.error(f"Google Drive error creating folder structure: {e}")
        raise google_drive_error_to_http_exception(e)
    except Exception as e:
        logging.error(f"Unexpected error creating folder structure: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create folder structure: {str(e)}"
        )
    
    # Process each file
    upload_results = []
    successful_uploads = 0
    failed_uploads = 0
    
    for i, file in enumerate(files):
        print(f"Hello World - Processing file {i+1}/{len(files)}: {file.filename}")
        
        result = FileUploadResult(
            filename=file.filename or f"unnamed_file_{i+1}",
            file_id="",
            status="failed",
            message="",
            file_size=0,
            content_type=file.content_type or "unknown",
            google_drive_folder=folder_id
        )
        
        try:
            # Read file content
            content = await file.read()
            result.file_size = len(content)
            
            print(f"Hello World - File content read: {result.file_size} bytes")
            
            # Comprehensive file validation
            is_valid, validation_errors = await file_validator.comprehensive_file_validation(
                content=content,
                filename=result.filename,
                content_type=file.content_type
            )
            
            if not is_valid:
                result.status = "failed"
                result.message = "; ".join(validation_errors)
                print(f"Hello World - File validation failed: {result.message}")
                failed_uploads += 1
                upload_results.append(result)
                continue
            
            print(f"Hello World - File validation passed for: {result.filename}")
            
            # Check if file format supports page counting
            supports_page_counting = page_counter_service.is_supported_format(result.filename)
            result.supports_page_counting = supports_page_counting
            
            if not supports_page_counting:
                result.status = "failed"
                result.message = f"File format not supported for page counting. Supported formats: {', '.join(page_counter_service.get_supported_formats())}"
                print(f"Hello World - Page counting validation failed: {result.message}")
                failed_uploads += 1
                upload_results.append(result)
                continue
            
            # Generate unique file ID
            file_id = str(uuid.uuid4())
            result.file_id = file_id
            
            # Upload to Google Drive/local storage
            try:
                file_info = await google_drive_service.upload_file_to_folder(
                    file_content=content,
                    filename=result.filename,
                    folder_id=folder_id,
                    target_language=request_data.target_language
                )
                
                logging.info(f"File uploaded successfully: {file_info['file_id']}")
                
            except GoogleDriveError as e:
                result.status = "failed"
                result.message = f"Google Drive error: {e.message}"
                logging.error(f"Google Drive error uploading file: {e}")
                failed_uploads += 1
                upload_results.append(result)
                continue
            
            # Update file metadata with target language
            try:
                metadata = {
                    'properties': {
                        'target_language': request_data.target_language,
                        'customer_email': request_data.customer_email,
                        'upload_timestamp': file_info.get('created_at'),
                        'file_size': str(result.file_size),
                        'content_type': result.content_type
                    }
                }
                
                await google_drive_service.update_file_metadata(
                    file_info['file_id'], 
                    metadata
                )
                
                logging.info(f"File metadata updated for: {file_id}")
                
            except GoogleDriveError as e:
                # Metadata update failed, but file upload succeeded
                logging.warning(f"Metadata update failed for {file_info['file_id']}: {e.message}")
                # Continue with success since the file was uploaded
            
            # Count pages in the uploaded file
            try:
                # For stub implementation, we'll simulate page counting based on file extension
                # In real implementation, we'd save the file locally first, then count pages
                file_extension = os.path.splitext(result.filename)[1].lower()
                
                # Simulate page count based on file type (stub implementation)
                if file_extension == '.pdf':
                    page_count = 5  # Simulate 5 pages for PDF
                elif file_extension in ['.doc', '.docx']:
                    page_count = 3  # Simulate 3 pages for Word docs
                elif file_extension == '.txt':
                    page_count = 2  # Simulate 2 pages for text files
                elif file_extension == '.rtf':
                    page_count = 2  # Simulate 2 pages for RTF
                elif file_extension in ['.png', '.jpg', '.jpeg', '.tiff']:
                    page_count = 1  # Images are single page
                else:
                    page_count = 1  # Default
                
                result.page_count = page_count
                print(f"Hello World - Simulated page count for {result.filename}: {page_count}")
            except Exception as e:
                print(f"Hello World - Error counting pages for {result.filename}: {e}")
                result.page_count = -1
            
            # Mark as successful
            result.file_id = file_info['file_id']
            result.status = "success"
            result.message = f"File uploaded successfully. Pages: {result.page_count}"
            successful_uploads += 1
            
        except HTTPException as e:
            result.status = "failed"
            result.message = e.detail
            failed_uploads += 1
            print(f"Hello World - HTTP exception during file processing: {e.detail}")
            
        except Exception as e:
            result.status = "failed"
            result.message = f"Unexpected error: {str(e)}"
            failed_uploads += 1
            print(f"Hello World - Unexpected error during file processing: {e}")
            
        upload_results.append(result)
    
    # Create response
    response = FileUploadResponse(
        success=successful_uploads > 0,
        message=f"Upload completed: {successful_uploads} successful, {failed_uploads} failed",
        customer_email=request_data.customer_email,
        target_language=request_data.target_language,
        total_files=len(files),
        successful_uploads=successful_uploads,
        failed_uploads=failed_uploads,
        results=upload_results,
        google_drive_folder_path=folder_id
    )
    
    print(f"Hello World - Upload process completed: {successful_uploads}/{len(files)} files successful")
    
    # Return appropriate HTTP status
    if successful_uploads == 0:
        # All uploads failed
        raise HTTPException(
            status_code=400,
            detail=response.dict()
        )
    elif failed_uploads > 0:
        # Partial success - return 207 Multi-Status
        return JSONResponse(
            status_code=207,
            content=response.dict()
        )
    else:
        # All successful - return 200
        return response


# Keep the old endpoint for backward compatibility
@router.post("/upload/legacy")
async def upload_files_legacy(files: List[UploadFile] = File(...)):
    """
    Legacy upload endpoint - DEPRECATED.
    Use /api/upload with customer_email and target_language parameters instead.
    """
    print(f"Hello World - Legacy upload endpoint called with {len(files)} files")
    
    # Supported file types
    supported_types = {
        'application/pdf': 100 * 1024 * 1024,  # 100MB
        'application/msword': 100 * 1024 * 1024,  # 100MB
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 100 * 1024 * 1024,  # 100MB
        'image/jpeg': 50 * 1024 * 1024,  # 50MB
        'image/jpg': 50 * 1024 * 1024,   # 50MB
        'image/png': 50 * 1024 * 1024,   # 50MB
        'image/tiff': 50 * 1024 * 1024,  # 50MB
        'image/tif': 50 * 1024 * 1024    # 50MB
    }
    
    file_ids = []
    
    for file in files:
        # Validate file type
        if file.content_type not in supported_types:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type: {file.content_type}"
            )
        
        # Validate file size
        content = await file.read()
        file_size = len(content)
        max_size = supported_types[file.content_type]
        
        if file_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size} bytes. Maximum allowed: {max_size} bytes"
            )
        
        # Validate file extension
        if file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            valid_extensions = ['.pdf', '.doc', '.docx', '.jpg', '.jpeg', '.png', '.tiff', '.tif']
            if ext not in valid_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file extension: {ext}"
                )
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        file_ids.append(file_id)
        
        print(f"Hello World - Processing file: {file.filename}, Size: {file_size}, ID: {file_id}")
    
    return JSONResponse(
        content={
            "success": True,
            "data": file_ids,
            "error": None,
            "deprecated": True,
            "message": "This endpoint is deprecated. Use /api/upload with customer_email and target_language parameters."
        }
    )


