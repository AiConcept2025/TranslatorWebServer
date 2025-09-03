"""
Language-related API endpoints.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["Languages"])

@router.get("/languages")
async def get_languages():
    """
    Get available languages for translation - STUB IMPLEMENTATION.
    Returns at least 20 common languages with popular flags.
    """
    print("Hello World - Languages endpoint called")
    
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