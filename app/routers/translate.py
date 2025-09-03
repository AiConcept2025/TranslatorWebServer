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
async def create_translation(request: TranslateRequest):
    """
    Initiate translation process - STUB IMPLEMENTATION.
    Validates email, files, and creates translation job.
    """
    print(f"Hello World - Translate endpoint called for {len(request.files)} files")
    print(f"Hello World - Translation: {request.sourceLanguage} -> {request.targetLanguage}")
    print(f"Hello World - Email: {request.email}")
    
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
            detail="Maximum 10 files allowed per translation"
        )
    
    # Generate translation ID
    translation_id = f"trans_{uuid.uuid4().hex[:10]}"
    
    print(f"Hello World - Created translation job: {translation_id}")
    
    # Stub: In real implementation, this would queue the translation job
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "id": translation_id,
                "status": "pending",
                "progress": 0,
                "message": "Translation queued"
            },
            "error": None
        }
    )