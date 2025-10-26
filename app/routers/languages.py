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
