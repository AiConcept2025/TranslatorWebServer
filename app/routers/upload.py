"""
File upload API endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import List
import uuid
import os

router = APIRouter(prefix="/api", tags=["File Upload"])

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    Upload files for translation - STUB IMPLEMENTATION.
    Supports PDF, Word, JPEG, PNG, TIFF files.
    """
    print(f"Hello World - Upload endpoint called with {len(files)} files")
    
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
            "error": None
        }
    )