"""
File upload API endpoints.
"""

from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.responses import JSONResponse, StreamingResponse
import json

from app.models.requests import FileUploadMetadata, FileListRequest
from app.models.responses import UploadResponse, FileListResponse, BaseResponse
from app.services.file_service import file_service

router = APIRouter(prefix="/api/v1/files", tags=["File Upload"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload file",
    description="Upload a file for translation"
)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    metadata: Optional[str] = None
):
    """
    Upload a file for translation - WITH STUB IMPLEMENTATION.
    
    - **file**: File to upload (supported formats: txt, doc, docx, pdf, rtf, odt)
    - **metadata**: Optional JSON string with file metadata
    
    Returns file ID and information for use in translation requests.
    """
    print(f"Hello World - Upload file endpoint called: {file.filename}")
    try:
        # Parse metadata if provided
        parsed_metadata = None
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid metadata JSON format"
                )
        
        # Upload file
        file_id, file_info = await file_service.upload_file(file, parsed_metadata)
        
        return UploadResponse(
            file_id=file_id,
            file_info=file_info,
            message=f"File '{file_info.filename}' uploaded successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File upload failed: {str(e)}"
        )


@router.post(
    "/upload-multiple",
    summary="Upload multiple files",
    description="Upload multiple files for batch translation"
)
async def upload_multiple_files(
    files: List[UploadFile] = File(..., description="Files to upload"),
    metadata: Optional[str] = None
):
    """
    Upload multiple files for batch translation - WITH STUB IMPLEMENTATION.
    
    - **files**: List of files to upload (max 10 files)
    - **metadata**: Optional JSON string with common metadata for all files
    
    Returns list of file IDs and information.
    """
    print(f"Hello World - Upload multiple files endpoint called: {len(files)} files")
    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 files can be uploaded at once"
        )
    
    try:
        # Parse metadata if provided
        parsed_metadata = None
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid metadata JSON format"
                )
        
        uploaded_files = []
        errors = []
        
        # Upload each file
        for file in files:
            try:
                file_id, file_info = await file_service.upload_file(file, parsed_metadata)
                uploaded_files.append({
                    'file_id': file_id,
                    'file_info': file_info.dict(),
                    'status': 'success'
                })
            except Exception as e:
                errors.append({
                    'filename': file.filename,
                    'error': str(e),
                    'status': 'error'
                })
        
        return JSONResponse(
            content={
                'success': True,
                'uploaded_files': uploaded_files,
                'errors': errors,
                'total_uploaded': len(uploaded_files),
                'total_errors': len(errors),
                'message': f"Uploaded {len(uploaded_files)} files successfully"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Multiple file upload failed: {str(e)}"
        )


@router.get(
    "/",
    response_model=FileListResponse,
    summary="List uploaded files",
    description="Get list of uploaded files with pagination"
)
async def list_files(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    search: Optional[str] = Query(None, description="Search in filename")
):
    """
    List uploaded files with pagination and filtering - WITH STUB IMPLEMENTATION.
    
    - **page**: Page number (starting from 1)
    - **page_size**: Number of items per page (1-100)
    - **file_type**: Filter by file type (txt, doc, docx, pdf, rtf, odt)
    - **search**: Search term to filter filenames
    """
    print(f"Hello World - List files endpoint called: page {page}, size {page_size}")
    try:
        result = await file_service.list_files(page, page_size, file_type, search)
        
        return FileListResponse(
            files=result['files'],
            total_count=result['total_count'],
            page=result['page'],
            page_size=result['page_size'],
            message=f"Retrieved {len(result['files'])} files"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get(
    "/{file_id}/info",
    summary="Get file information",
    description="Get detailed information about an uploaded file"
)
async def get_file_info(file_id: str):
    """
    Get detailed information about an uploaded file.
    
    - **file_id**: Unique file identifier
    """
    try:
        file_info = await file_service.get_file_info(file_id)
        
        return JSONResponse(
            content={
                'success': True,
                'file_info': file_info.dict(),
                'message': f"Retrieved information for file '{file_info.filename}'"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file information: {str(e)}"
        )


@router.get(
    "/{file_id}/download",
    summary="Download file",
    description="Download an uploaded file"
)
async def download_file(file_id: str):
    """
    Download an uploaded file.
    
    - **file_id**: Unique file identifier
    """
    try:
        # Get file info for headers
        file_info = await file_service.get_file_info(file_id)
        
        # Get file content
        content = await file_service.get_file_content(file_id)
        
        # Create streaming response
        def iterfile():
            yield content
        
        return StreamingResponse(
            iterfile(),
            media_type=file_info.content_type or "application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={file_info.filename}"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File download failed: {str(e)}"
        )


@router.get(
    "/{file_id}/text",
    summary="Extract text from file",
    description="Extract text content from an uploaded file"
)
async def extract_text_from_file(file_id: str):
    """
    Extract text content from an uploaded file - WITH STUB IMPLEMENTATION.
    
    - **file_id**: Unique file identifier
    
    Returns extracted text content for preview or processing.
    """
    print(f"Hello World - Extract text endpoint called for file: {file_id}")
    try:
        text_content = await file_service.extract_text(file_id)
        
        # Get file info for additional details
        file_info = await file_service.get_file_info(file_id)
        
        return JSONResponse(
            content={
                'success': True,
                'file_id': file_id,
                'filename': file_info.filename,
                'text_content': text_content,
                'character_count': len(text_content),
                'word_count': len(text_content.split()),
                'message': "Text extracted successfully"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Text extraction failed: {str(e)}"
        )


@router.delete(
    "/{file_id}",
    response_model=BaseResponse,
    summary="Delete file",
    description="Delete an uploaded file"
)
async def delete_file(file_id: str):
    """
    Delete an uploaded file.
    
    - **file_id**: Unique file identifier
    """
    try:
        success = await file_service.delete_file(file_id)
        
        if success:
            return BaseResponse(
                message=f"File with ID '{file_id}' deleted successfully"
            )
        else:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"File deletion failed: {str(e)}"
        )


@router.get(
    "/storage/stats",
    summary="Get storage statistics",
    description="Get storage usage statistics"
)
async def get_storage_stats():
    """
    Get storage usage statistics.
    
    Returns information about total files, storage usage, and file type distribution.
    """
    try:
        stats = await file_service.get_storage_stats()
        
        return JSONResponse(
            content={
                'success': True,
                'storage_stats': stats,
                'message': "Storage statistics retrieved successfully"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get storage statistics: {str(e)}"
        )


@router.post(
    "/cleanup",
    response_model=BaseResponse,
    summary="Cleanup temporary files",
    description="Clean up temporary files older than specified hours"
)
async def cleanup_temp_files(
    max_age_hours: int = Query(24, ge=1, le=168, description="Maximum age in hours (1-168)")
):
    """
    Clean up temporary files older than specified hours.
    
    - **max_age_hours**: Maximum age of files to keep in hours (1-168)
    """
    try:
        deleted_count = await file_service.cleanup_temp_files(max_age_hours)
        
        return BaseResponse(
            message=f"Cleaned up {deleted_count} temporary files older than {max_age_hours} hours"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cleanup failed: {str(e)}"
        )


@router.get(
    "/supported-formats",
    summary="Get supported file formats",
    description="Get list of supported file formats for upload"
)
async def get_supported_formats():
    """
    Get list of supported file formats for upload.
    
    Returns information about supported file types, maximum file size, and format descriptions.
    """
    from app.config import settings
    
    formats = {
        'txt': {
            'name': 'Plain Text',
            'description': 'Simple text files',
            'mime_types': ['text/plain']
        },
        'doc': {
            'name': 'Microsoft Word 97-2003',
            'description': 'Legacy Microsoft Word documents',
            'mime_types': ['application/msword']
        },
        'docx': {
            'name': 'Microsoft Word',
            'description': 'Modern Microsoft Word documents',
            'mime_types': ['application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        },
        'pdf': {
            'name': 'PDF Document',
            'description': 'Portable Document Format files',
            'mime_types': ['application/pdf']
        },
        'rtf': {
            'name': 'Rich Text Format',
            'description': 'Rich Text Format documents',
            'mime_types': ['application/rtf', 'text/rtf']
        },
        'odt': {
            'name': 'OpenDocument Text',
            'description': 'OpenDocument text documents',
            'mime_types': ['application/vnd.oasis.opendocument.text']
        }
    }
    
    return JSONResponse(
        content={
            'success': True,
            'supported_formats': formats,
            'max_file_size_bytes': settings.max_file_size,
            'max_file_size_mb': round(settings.max_file_size / (1024 * 1024), 2),
            'allowed_extensions': settings.allowed_file_extensions,
            'message': "Retrieved supported file formats"
        }
    )