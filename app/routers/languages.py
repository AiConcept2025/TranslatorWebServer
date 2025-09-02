"""
Language-related API endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from app.models.requests import LanguageDetectionRequest
from app.models.responses import (
    LanguageListResponse, 
    LanguageDetectionResponse,
    ErrorResponse,
    Language
)
from app.services.translation_service import translation_service

router = APIRouter(prefix="/api/v1/languages", tags=["Languages"])


@router.get(
    "/",
    response_model=LanguageListResponse,
    summary="Get supported languages",
    description="Retrieve list of all supported languages across all translation services"
)
async def get_supported_languages(
    service: Optional[str] = Query(
        None, 
        description="Filter by specific translation service (google, deepl, azure)"
    )
):
    """
    Get list of supported languages - WITH STUB IMPLEMENTATION.
    
    - **service**: Optional filter by translation service
    
    Returns list of languages with their codes, names, and supporting services.
    """
    print(f"Hello World - Get supported languages endpoint called for service: {service}")
    try:
        languages = await translation_service.get_supported_languages(service)
        
        return LanguageListResponse(
            languages=languages,
            total_count=len(languages),
            message=f"Retrieved {len(languages)} supported languages"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve supported languages: {str(e)}"
        )


@router.get(
    "/by-service/{service_name}",
    response_model=LanguageListResponse,
    summary="Get languages by service",
    description="Get supported languages for a specific translation service"
)
async def get_languages_by_service(service_name: str):
    """
    Get supported languages for a specific translation service.
    
    - **service_name**: Translation service name (google, deepl, azure)
    """
    valid_services = ['google', 'deepl', 'azure']
    if service_name not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Must be one of: {', '.join(valid_services)}"
        )
    
    try:
        languages = await translation_service.get_supported_languages(service_name)
        
        return LanguageListResponse(
            languages=languages,
            total_count=len(languages),
            message=f"Retrieved {len(languages)} languages for {service_name}"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve languages for {service_name}: {str(e)}"
        )


@router.post(
    "/detect",
    response_model=LanguageDetectionResponse,
    summary="Detect language",
    description="Detect the language of provided text"
)
async def detect_language(request: LanguageDetectionRequest):
    """
    Detect the language of provided text - WITH STUB IMPLEMENTATION.
    
    - **text**: Text to analyze for language detection
    
    Returns detected language code with confidence score.
    """
    print(f"Hello World - Language detection endpoint called for text: {request.text[:30]}...")
    try:
        detection = await translation_service.detect_language(request.text)
        
        return LanguageDetectionResponse(
            detected_language=detection['detected_language'],
            confidence=detection.get('confidence', 0.0),
            message="Language detected successfully"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Language detection failed: {str(e)}"
        )


@router.get(
    "/pairs",
    summary="Get supported language pairs",
    description="Get all supported translation language pairs"
)
async def get_supported_language_pairs(
    source_language: Optional[str] = Query(
        None, 
        description="Filter pairs by source language"
    ),
    target_language: Optional[str] = Query(
        None, 
        description="Filter pairs by target language"
    )
):
    """
    Get supported translation language pairs.
    
    - **source_language**: Optional filter by source language
    - **target_language**: Optional filter by target language
    
    Returns list of supported language pairs.
    """
    try:
        # Get all supported languages
        languages = await translation_service.get_supported_languages()
        
        # Generate pairs
        pairs = []
        for source in languages:
            for target in languages:
                if source.code != target.code:  # Don't include same-language pairs
                    # Apply filters if provided
                    if source_language and source.code != source_language:
                        continue
                    if target_language and target.code != target_language:
                        continue
                    
                    # Find common services
                    common_services = list(set(source.supported_by) & set(target.supported_by))
                    
                    if common_services:  # Only include pairs with at least one common service
                        pairs.append({
                            'source_language': {
                                'code': source.code,
                                'name': source.name
                            },
                            'target_language': {
                                'code': target.code,
                                'name': target.name
                            },
                            'supported_by': common_services
                        })
        
        return JSONResponse(
            content={
                'success': True,
                'pairs': pairs,
                'total_count': len(pairs),
                'message': f"Retrieved {len(pairs)} supported language pairs"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve language pairs: {str(e)}"
        )


@router.get(
    "/{language_code}",
    summary="Get language details",
    description="Get detailed information about a specific language"
)
async def get_language_details(language_code: str):
    """
    Get detailed information about a specific language.
    
    - **language_code**: ISO 639-1 language code (e.g., 'en', 'fr', 'es')
    """
    try:
        # Get all languages and find the specific one
        languages = await translation_service.get_supported_languages()
        language = next((lang for lang in languages if lang.code == language_code), None)
        
        if not language:
            raise HTTPException(
                status_code=404,
                detail=f"Language with code '{language_code}' not found"
            )
        
        # Get additional details (this could be extended with more information)
        details = {
            'code': language.code,
            'name': language.name,
            'native_name': language.native_name,
            'supported_by': language.supported_by,
            'is_rtl': language_code in ['ar', 'he', 'fa', 'ur'],  # Right-to-left languages
            'script': _get_language_script(language_code),
            'family': _get_language_family(language_code)
        }
        
        return JSONResponse(
            content={
                'success': True,
                'language': details,
                'message': f"Retrieved details for language '{language.name}'"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve language details: {str(e)}"
        )


@router.get(
    "/popular/top",
    response_model=LanguageListResponse,
    summary="Get popular languages",
    description="Get most popular languages for translation"
)
async def get_popular_languages(
    limit: int = Query(10, ge=1, le=50, description="Number of languages to return")
):
    """
    Get most popular languages for translation.
    
    - **limit**: Maximum number of languages to return (1-50)
    
    Returns list of most commonly used languages.
    """
    try:
        # Get all supported languages
        all_languages = await translation_service.get_supported_languages()
        
        # Define popular languages in order of popularity
        popular_codes = [
            'en',  # English
            'es',  # Spanish
            'fr',  # French
            'de',  # German
            'it',  # Italian
            'pt',  # Portuguese
            'ru',  # Russian
            'ja',  # Japanese
            'ko',  # Korean
            'zh',  # Chinese
            'ar',  # Arabic
            'hi',  # Hindi
            'nl',  # Dutch
            'sv',  # Swedish
            'da',  # Danish
            'no',  # Norwegian
            'fi',  # Finnish
            'pl',  # Polish
            'tr',  # Turkish
            'th'   # Thai
        ]
        
        # Filter and order languages by popularity
        popular_languages = []
        for code in popular_codes:
            language = next((lang for lang in all_languages if lang.code == code), None)
            if language:
                popular_languages.append(language)
            
            if len(popular_languages) >= limit:
                break
        
        return LanguageListResponse(
            languages=popular_languages,
            total_count=len(popular_languages),
            message=f"Retrieved top {len(popular_languages)} popular languages"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve popular languages: {str(e)}"
        )


# Helper functions
def _get_language_script(language_code: str) -> str:
    """Get the writing script for a language."""
    script_mapping = {
        'ar': 'Arabic',
        'zh': 'Chinese',
        'ja': 'Japanese',
        'ko': 'Korean',
        'he': 'Hebrew',
        'hi': 'Devanagari',
        'ru': 'Cyrillic',
        'th': 'Thai',
        'fa': 'Persian',
        'ur': 'Urdu'
    }
    return script_mapping.get(language_code, 'Latin')


def _get_language_family(language_code: str) -> str:
    """Get the language family for a language."""
    family_mapping = {
        'en': 'Germanic',
        'de': 'Germanic',
        'nl': 'Germanic',
        'sv': 'Germanic',
        'da': 'Germanic',
        'no': 'Germanic',
        'es': 'Romance',
        'fr': 'Romance',
        'it': 'Romance',
        'pt': 'Romance',
        'ru': 'Slavic',
        'pl': 'Slavic',
        'zh': 'Sino-Tibetan',
        'ja': 'Japonic',
        'ko': 'Koreanic',
        'ar': 'Semitic',
        'he': 'Semitic',
        'hi': 'Indo-Aryan',
        'ur': 'Indo-Aryan',
        'fa': 'Iranian',
        'th': 'Tai-Kadai',
        'fi': 'Uralic',
        'tr': 'Turkic'
    }
    return family_mapping.get(language_code, 'Unknown')