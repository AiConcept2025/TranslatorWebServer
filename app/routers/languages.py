"""
Language-related API endpoints.
"""

import logging
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.models.responses import SupportedLanguagesResponse, SimpleLanguage
from app.services.language_service import language_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Languages"])

@router.get("/languages", response_model=SupportedLanguagesResponse)
async def get_supported_languages():
    """
    Get supported languages from supported_languages.txt file.
    
    Returns a list of languages with their codes and names parsed from the file.
    Each line in the file is expected to have format: "Language Name    code"
    """
    logger.info("Request received for supported languages")
    
    try:
        # Get languages from service
        languages_data = await language_service.get_supported_languages()
        
        # Convert to simple dictionaries for JSON serialization
        languages = [{"code": lang["code"], "name": lang["name"]} for lang in languages_data]
        
        response_data = {
            "success": True,
            "data": languages
        }
        
        logger.info(f"Response sent with {len(languages)} supported languages")
        
        return JSONResponse(content=response_data)
        
    except FileNotFoundError as e:
        logger.error(f"Languages file not found: {e}")
        raise HTTPException(
            status_code=404,
            detail="Supported languages file not found"
        )
    except Exception as e:
        logger.error(f"Error getting supported languages: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to load supported languages"
        )


@router.get("/languages/legacy")
async def get_languages():
    """
    LEGACY ENDPOINT: Get available languages for translation - STUB IMPLEMENTATION.
    Returns at least 20 common languages with popular flags.
    
    This endpoint is kept for backward compatibility.
    Use /api/v1/languages instead for the actual supported languages from file.
    """
    print("Hello World - Languages legacy endpoint called")
    
    languages = [
        {"code": "en", "name": "English", "nativeName": "English", "isPopular": True},
        {"code": "es", "name": "Spanish", "nativeName": "Español", "isPopular": True},
        {"code": "fr", "name": "French", "nativeName": "Français", "isPopular": True},
        {"code": "de", "name": "German", "nativeName": "Deutsch", "isPopular": True},
        {"code": "it", "name": "Italian", "nativeName": "Italiano", "isPopular": True},
        {"code": "pt", "name": "Portuguese", "nativeName": "Português", "isPopular": True},
        {"code": "ru", "name": "Russian", "nativeName": "Русский", "isPopular": True},
        {"code": "zh", "name": "Chinese", "nativeName": "中文", "isPopular": True},
        {"code": "ja", "name": "Japanese", "nativeName": "日本語", "isPopular": True},
        {"code": "ko", "name": "Korean", "nativeName": "한국어", "isPopular": True},
        {"code": "ar", "name": "Arabic", "nativeName": "العربية", "isPopular": False},
        {"code": "hi", "name": "Hindi", "nativeName": "हिन्दी", "isPopular": False},
        {"code": "nl", "name": "Dutch", "nativeName": "Nederlands", "isPopular": False},
        {"code": "pl", "name": "Polish", "nativeName": "Polski", "isPopular": False},
        {"code": "tr", "name": "Turkish", "nativeName": "Türkçe", "isPopular": False},
        {"code": "sv", "name": "Swedish", "nativeName": "Svenska", "isPopular": False},
        {"code": "da", "name": "Danish", "nativeName": "Dansk", "isPopular": False},
        {"code": "no", "name": "Norwegian", "nativeName": "Norsk", "isPopular": False},
        {"code": "fi", "name": "Finnish", "nativeName": "Suomi", "isPopular": False},
        {"code": "th", "name": "Thai", "nativeName": "ไทย", "isPopular": False},
        {"code": "vi", "name": "Vietnamese", "nativeName": "Tiếng Việt", "isPopular": False},
        {"code": "uk", "name": "Ukrainian", "nativeName": "Українська", "isPopular": False},
        {"code": "cs", "name": "Czech", "nativeName": "Čeština", "isPopular": False},
        {"code": "hu", "name": "Hungarian", "nativeName": "Magyar", "isPopular": False},
        {"code": "ro", "name": "Romanian", "nativeName": "Română", "isPopular": False}
    ]
    
    return JSONResponse(
        content={
            "success": True,
            "data": languages,
            "error": None
        }
    )