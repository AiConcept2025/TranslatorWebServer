"""
Translation API endpoints.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from app.models.requests import (
    TextTranslationRequest,
    BatchTextTranslationRequest,
    FileTranslationRequest,
    BatchFileTranslationRequest,
    CostEstimationRequest,
    TranslationHistoryRequest
)
from app.models.responses import (
    TranslationResponse,
    BatchTranslationResponse,
    CostEstimateResponse,
    TranslationHistoryResponse,
    BaseResponse
)
from app.services.translation_service import translation_service

router = APIRouter(prefix="/api/v1/translate", tags=["Translation"])


@router.post(
    "/text",
    response_model=TranslationResponse,
    summary="Translate text",
    description="Translate a text string to target language"
)
async def translate_text(request: TextTranslationRequest):
    """
    Translate text to target language - WITH STUB IMPLEMENTATION.
    
    - **text**: Text to translate (max 5000 characters)
    - **target_language**: Target language code (e.g., 'en', 'es', 'fr')
    - **source_language**: Source language code (auto-detect if not provided)
    - **service**: Translation service to use (auto, google, deepl, azure)
    - **preserve_formatting**: Whether to preserve text formatting
    
    Returns task ID for tracking translation progress.
    """
    print(f"Hello World - Translate text endpoint called: '{request.text[:50]}...' to {request.target_language}")
    try:
        task_id = await translation_service.translate_text(
            text=request.text,
            target_language=request.target_language,
            source_language=request.source_language,
            service=request.service
        )
        
        return TranslationResponse(
            task_id=task_id,
            status="pending",
            message="Translation task created successfully"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Translation request failed: {str(e)}"
        )


@router.post(
    "/text/batch",
    response_model=BatchTranslationResponse,
    summary="Batch translate texts",
    description="Translate multiple text strings in a single request"
)
async def batch_translate_text(request: BatchTextTranslationRequest):
    """
    Translate multiple texts to target language - WITH STUB IMPLEMENTATION.
    
    - **texts**: List of texts to translate (max 100 texts, 50k total characters)
    - **target_language**: Target language code
    - **source_language**: Source language code (auto-detect if not provided)
    - **service**: Translation service to use
    - **preserve_formatting**: Whether to preserve text formatting
    
    Returns batch ID and individual task IDs for tracking.
    """
    print(f"Hello World - Batch translate text endpoint called: {len(request.texts)} texts to {request.target_language}")
    try:
        import uuid
        
        batch_id = str(uuid.uuid4())
        task_ids = []
        
        # Create individual translation tasks
        for text in request.texts:
            task_id = await translation_service.translate_text(
                text=text,
                target_language=request.target_language,
                source_language=request.source_language,
                service=request.service
            )
            task_ids.append(task_id)
        
        return BatchTranslationResponse(
            batch_id=batch_id,
            task_ids=task_ids,
            total_tasks=len(task_ids),
            message=f"Created batch translation with {len(task_ids)} tasks"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch translation request failed: {str(e)}"
        )


@router.post(
    "/file",
    response_model=TranslationResponse,
    summary="Translate file",
    description="Translate content of an uploaded file"
)
async def translate_file(request: FileTranslationRequest):
    """
    Translate content of an uploaded file - WITH STUB IMPLEMENTATION.
    
    - **file_id**: ID of previously uploaded file
    - **target_language**: Target language code
    - **source_language**: Source language code (auto-detect if not provided)
    - **service**: Translation service to use
    - **preserve_formatting**: Whether to preserve document formatting
    - **output_format**: Desired output format (if different from input)
    
    Returns task ID for tracking translation progress.
    """
    print(f"Hello World - Translate file endpoint called: file {request.file_id} to {request.target_language}")
    try:
        task_id = await translation_service.translate_file(
            file_id=request.file_id,
            target_language=request.target_language,
            source_language=request.source_language,
            service=request.service
        )
        
        return TranslationResponse(
            task_id=task_id,
            status="pending",
            message="File translation task created successfully"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File translation request failed: {str(e)}"
        )


@router.post(
    "/file/batch",
    response_model=BatchTranslationResponse,
    summary="Batch translate files",
    description="Translate multiple files in a single request"
)
async def batch_translate_files(request: BatchFileTranslationRequest):
    """
    Translate multiple files to target language.
    
    - **file_ids**: List of uploaded file IDs (max 10 files)
    - **target_language**: Target language code
    - **source_language**: Source language code (auto-detect if not provided)
    - **service**: Translation service to use
    - **preserve_formatting**: Whether to preserve document formatting
    
    Returns batch ID and individual task IDs for tracking.
    """
    try:
        import uuid
        
        batch_id = str(uuid.uuid4())
        task_ids = []
        
        # Create individual file translation tasks
        for file_id in request.file_ids:
            task_id = await translation_service.translate_file(
                file_id=file_id,
                target_language=request.target_language,
                source_language=request.source_language,
                service=request.service
            )
            task_ids.append(task_id)
        
        return BatchTranslationResponse(
            batch_id=batch_id,
            task_ids=task_ids,
            total_tasks=len(task_ids),
            message=f"Created batch file translation with {len(task_ids)} tasks"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch file translation request failed: {str(e)}"
        )


@router.get(
    "/task/{task_id}",
    summary="Get translation task status",
    description="Get status and result of a translation task"
)
async def get_translation_task(task_id: str):
    """
    Get translation task status and result - WITH STUB IMPLEMENTATION.
    
    - **task_id**: Translation task identifier
    
    Returns current status, progress, and result if completed.
    """
    print(f"Hello World - Get translation task status called for: {task_id}")
    try:
        task_info = await translation_service.get_task_status(task_id)
        
        return JSONResponse(
            content={
                'success': True,
                **task_info,
                'message': f"Retrieved status for task '{task_id}'"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}"
        )


@router.post(
    "/estimate",
    response_model=CostEstimateResponse,
    summary="Estimate translation cost",
    description="Get cost estimation for translation"
)
async def estimate_translation_cost(request: CostEstimationRequest):
    """
    Estimate cost for translation - WITH STUB IMPLEMENTATION.
    
    - **text**: Text to estimate cost for (either text or file_id required)
    - **file_id**: File ID to estimate cost for (either text or file_id required)
    - **target_language**: Target language code
    - **service**: Translation service to use
    
    Returns cost estimation with character count and pricing details.
    """
    print(f"Hello World - Cost estimation endpoint called for {request.target_language}")
    try:
        # Determine text to analyze
        if request.text:
            text = request.text
        elif request.file_id:
            # Extract text from file for estimation
            from app.services.file_service import file_service
            text = await file_service.extract_text(request.file_id)
        else:
            raise HTTPException(
                status_code=400,
                detail="Either text or file_id must be provided"
            )
        
        # Get cost estimation
        estimation = await translation_service.estimate_cost(
            text=text,
            target_language=request.target_language,
            service=request.service
        )
        
        return CostEstimateResponse(
            estimate={
                'characters_count': estimation['characters_count'],
                'word_count': estimation['word_count'],
                'estimated_cost': estimation['estimated_cost'],
                'currency': estimation['currency'],
                'tier': estimation.get('service', 'basic')
            },
            message="Cost estimation completed successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cost estimation failed: {str(e)}"
        )


@router.get(
    "/history",
    response_model=TranslationHistoryResponse,
    summary="Get translation history",
    description="Get paginated translation history with filtering"
)
async def get_translation_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    source_language: Optional[str] = Query(None, description="Filter by source language"),
    target_language: Optional[str] = Query(None, description="Filter by target language"),
    status: Optional[str] = Query(None, description="Filter by status"),
    service: Optional[str] = Query(None, description="Filter by translation service")
):
    """
    Get translation history with pagination and filtering.
    
    - **page**: Page number (starting from 1)
    - **page_size**: Items per page (1-100)
    - **source_language**: Filter by source language code
    - **target_language**: Filter by target language code
    - **status**: Filter by translation status
    - **service**: Filter by translation service
    
    Returns paginated list of translation history.
    """
    try:
        # This would typically fetch from a database
        # For now, return an empty result as placeholder
        return TranslationHistoryResponse(
            translations=[],
            total_count=0,
            page=page,
            page_size=page_size,
            message="Translation history retrieved (placeholder implementation)"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve translation history: {str(e)}"
        )


@router.delete(
    "/task/{task_id}",
    response_model=BaseResponse,
    summary="Cancel translation task",
    description="Cancel a pending or processing translation task"
)
async def cancel_translation_task(task_id: str):
    """
    Cancel a translation task.
    
    - **task_id**: Translation task identifier
    
    Only pending or processing tasks can be cancelled.
    """
    try:
        # Get current task status
        task_info = await translation_service.get_task_status(task_id)
        
        if task_info['status'] in ['completed', 'failed', 'cancelled']:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel task with status '{task_info['status']}'"
            )
        
        # Cancel the task (this would update the task status in the database)
        # For now, this is a placeholder implementation
        return BaseResponse(
            message=f"Translation task '{task_id}' has been cancelled"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel task: {str(e)}"
        )


@router.get(
    "/services/status",
    summary="Get translation services status",
    description="Get current status of all translation services"
)
async def get_services_status():
    """
    Get current status of all translation services.
    
    Returns health status and response times for each service.
    """
    try:
        # This would check the actual status of each translation service
        # For now, return a placeholder response
        services = [
            {
                'service': 'google_free',
                'name': 'Google Translate (Free)',
                'status': 'online',
                'response_time_ms': 150,
                'available': True
            },
            {
                'service': 'google_paid',
                'name': 'Google Translate (Paid)',
                'status': 'online' if translation_service.services.get('google_paid') else 'unavailable',
                'response_time_ms': 120,
                'available': bool(translation_service.services.get('google_paid'))
            },
            {
                'service': 'deepl',
                'name': 'DeepL',
                'status': 'online' if translation_service.services.get('deepl') else 'unavailable',
                'response_time_ms': 200,
                'available': bool(translation_service.services.get('deepl'))
            },
            {
                'service': 'azure',
                'name': 'Azure Translator',
                'status': 'online' if translation_service.services.get('azure') else 'unavailable',
                'response_time_ms': 180,
                'available': bool(translation_service.services.get('azure'))
            }
        ]
        
        overall_status = 'healthy' if any(s['available'] for s in services) else 'degraded'
        
        return JSONResponse(
            content={
                'success': True,
                'overall_status': overall_status,
                'services': services,
                'available_services': len([s for s in services if s['available']]),
                'total_services': len(services),
                'message': "Translation services status retrieved"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get services status: {str(e)}"
        )


@router.get(
    "/stats",
    summary="Get translation statistics",
    description="Get translation usage statistics"
)
async def get_translation_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days for statistics")
):
    """
    Get translation usage statistics.
    
    - **days**: Number of days to include in statistics (1-365)
    
    Returns translation volume, language usage, and service usage statistics.
    """
    try:
        # This would typically query a database for actual statistics
        # For now, return placeholder data
        stats = {
            'period_days': days,
            'total_translations': 0,
            'total_characters': 0,
            'total_files': 0,
            'average_translation_time': 0.0,
            'popular_language_pairs': [],
            'service_usage': {
                'google_free': 0,
                'google_paid': 0,
                'deepl': 0,
                'azure': 0
            },
            'daily_volume': []
        }
        
        return JSONResponse(
            content={
                'success': True,
                'statistics': stats,
                'message': f"Translation statistics for last {days} days retrieved"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get translation statistics: {str(e)}"
        )