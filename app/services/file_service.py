"""
File handling service for the Translation Web Server.
"""

import os
import uuid
import json
import aiofiles
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, BinaryIO
from fastapi import UploadFile, HTTPException
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models.responses import FileInfo, FileType
from app.services.page_counter_service import page_counter_service


class FileService:
    """Service for handling file operations."""
    
    def __init__(self):
        self.upload_dir = Path(settings.upload_dir)
        self.temp_dir = Path(settings.temp_dir)
        self.max_file_size = settings.max_file_size
        self.allowed_extensions = settings.allowed_file_extensions
        
        # Ensure directories exist
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def upload_file(self, file: UploadFile, metadata: Optional[Dict[str, Any]] = None) -> Tuple[str, FileInfo]:
        """
        Upload and validate a file - STUB IMPLEMENTATION.
        
        Args:
            file: The uploaded file
            metadata: Optional metadata for the file
            
        Returns:
            Tuple of file_id and FileInfo
            
        Raises:
            HTTPException: If file validation fails
        """
        print(f"Hello World - File upload stub for: {file.filename}")
        
        # Generate stub file ID
        file_id = str(uuid.uuid4())
        
        # Create stub file info
        file_info = FileInfo(
            filename=file.filename or "stub_file.txt",
            size=1024,  # Stub size
            content_type="text/plain",
            file_type=FileType.TXT,
            checksum="stub_checksum_123456789"
        )
        
        print(f"Hello World - Generated stub file_id: {file_id}")
        return file_id, file_info
    
    async def get_file_content(self, file_id: str) -> bytes:
        """
        Get file content by ID - STUB IMPLEMENTATION.
        
        Args:
            file_id: The file identifier
            
        Returns:
            File content as bytes
            
        Raises:
            HTTPException: If file not found
        """
        print(f"Hello World - Getting file content stub for: {file_id}")
        
        # Return stub content
        return f"Hello World - Stub file content for {file_id}".encode('utf-8')
    
    async def get_file_info(self, file_id: str) -> FileInfo:
        """
        Get file information by ID - STUB IMPLEMENTATION.
        
        Args:
            file_id: The file identifier
            
        Returns:
            FileInfo object
            
        Raises:
            HTTPException: If file not found
        """
        print(f"Hello World - Getting file info stub for: {file_id}")
        
        # Return stub file info
        return FileInfo(
            filename=f"stub_file_{file_id[:8]}.txt",
            size=1024,
            content_type="text/plain",
            file_type=FileType.TXT,
            checksum=f"stub_checksum_{file_id[:8]}"
        )
    
    async def delete_file(self, file_id: str) -> bool:
        """
        Delete a file and its metadata.
        
        Args:
            file_id: The file identifier
            
        Returns:
            True if file was deleted, False if not found
        """
        try:
            # Get file path
            file_path = await self._get_file_path(file_id)
            metadata_path = self.upload_dir / f"{file_id}.json"
            
            # Delete file
            if file_path.exists():
                file_path.unlink()
            
            # Delete metadata
            if metadata_path.exists():
                metadata_path.unlink()
            
            return True
        except Exception:
            return False
    
    async def list_files(
        self, 
        page: int = 1, 
        page_size: int = 20,
        file_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List uploaded files with pagination - STUB IMPLEMENTATION.
        
        Args:
            page: Page number
            page_size: Items per page
            file_type: Filter by file type
            search: Search in filename
            
        Returns:
            Dictionary with files list and pagination info
        """
        print(f"Hello World - File listing stub - page {page}, size {page_size}, type: {file_type}, search: {search}")
        
        # Return stub file list
        stub_files = [
            {
                'file_id': 'stub-file-1',
                'filename': 'stub_document.txt',
                'size': 1024,
                'file_type': 'txt',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'checksum': 'stub_checksum_123'
            },
            {
                'file_id': 'stub-file-2',
                'filename': 'stub_document.pdf',
                'size': 2048,
                'file_type': 'pdf',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'checksum': 'stub_checksum_456'
            }
        ]
        
        return {
            'files': stub_files[:page_size],
            'total_count': len(stub_files),
            'page': page,
            'page_size': page_size,
            'total_pages': 1
        }
    
    async def extract_text(self, file_id: str) -> str:
        """
        Extract text from a file - STUB IMPLEMENTATION.
        
        Args:
            file_id: The file identifier
            
        Returns:
            Extracted text content
            
        Raises:
            HTTPException: If file not found or text extraction fails
        """
        print(f"Hello World - Text extraction stub for file: {file_id}")
        
        # Return stub extracted text
        return f"Hello World - This is stub extracted text content from file {file_id}. This would normally contain the actual file content ready for translation."
    
    async def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """
        Clean up temporary files older than specified hours - STUB IMPLEMENTATION.
        
        Args:
            max_age_hours: Maximum age of files to keep
            
        Returns:
            Number of files deleted
        """
        print(f"Hello World - Cleanup temp files stub - max age: {max_age_hours} hours")
        
        # Return stub deleted count
        stub_deleted_count = 3
        print(f"Hello World - Stubbed cleanup deleted {stub_deleted_count} files")
        return stub_deleted_count
    
    async def get_page_count(self, file_id: str) -> int:
        """
        Get page count for a file by its ID.
        
        Args:
            file_id: The file identifier
            
        Returns:
            Number of pages in the document, -1 if error or unsupported format
        """
        try:
            return await page_counter_service.count_pages_by_file_id(
                file_id, str(self.upload_dir)
            )
        except Exception as e:
            print(f"Error getting page count for file {file_id}: {e}")
            return -1
    
    async def get_file_info_with_pages(self, file_id: str) -> Dict[str, Any]:
        """
        Get file information with page count by ID.
        
        Args:
            file_id: The file identifier
            
        Returns:
            Dictionary with file info and page count
            
        Raises:
            HTTPException: If file not found
        """
        file_info = await self.get_file_info(file_id)
        page_count = await self.get_page_count(file_id)
        
        return {
            'file_info': file_info.dict(),
            'page_count': page_count,
            'supports_page_counting': page_counter_service.is_supported_format(file_info.filename)
        }
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        total_files = 0
        total_size = 0
        file_types = {}
        
        for file_path in self.upload_dir.glob("*"):
            if file_path.suffix != '.json':  # Skip metadata files
                try:
                    stat = file_path.stat()
                    total_files += 1
                    total_size += stat.st_size
                    
                    # Count by file type
                    file_ext = file_path.suffix.lower().lstrip('.')
                    file_types[file_ext] = file_types.get(file_ext, 0) + 1
                
                except Exception:
                    continue
        
        return {
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'file_types': file_types,
            'storage_limit_mb': round(settings.max_file_size / (1024 * 1024), 2)
        }
    
    # Private methods
    
    async def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        # Check file size
        if file.size and file.size > self.max_file_size:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size: {self.max_file_size} bytes"
            )
        
        # Check file extension
        file_extension = self._get_file_extension(file.filename).lower().lstrip('.')
        if file_extension not in self.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(self.allowed_extensions)}"
            )
    
    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename."""
        if not filename or '.' not in filename:
            return ''
        return '.' + filename.split('.')[-1].lower()
    
    def _detect_file_type(self, content: bytes, filename: str) -> FileType:
        """Detect file type from content and filename - STUB IMPLEMENTATION."""
        print(f"Hello World - File type detection stub for: {filename}")
        
        # Simple stub - just use file extension
        extension = self._get_file_extension(filename).lower().lstrip('.')
        try:
            return FileType(extension)
        except ValueError:
            return FileType.TXT  # Default fallback
    
    async def _get_file_path(self, file_id: str) -> Path:
        """Get file path for given file ID."""
        # Try to find file with any supported extension
        for ext in self.allowed_extensions:
            file_path = self.upload_dir / f"{file_id}.{ext}"
            if file_path.exists():
                return file_path
        
        # If not found, return path with most common extension
        return self.upload_dir / f"{file_id}.txt"
    
    async def _save_file_metadata(
        self, 
        file_id: str, 
        file_info: FileInfo, 
        metadata: Optional[Dict[str, Any]]
    ) -> None:
        """Save file metadata to JSON file."""
        metadata_data = {
            'file_id': file_id,
            'file_info': file_info.dict(),
            'metadata': metadata or {},
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        metadata_path = self.upload_dir / f"{file_id}.json"
        async with aiofiles.open(metadata_path, 'w') as f:
            await f.write(json.dumps(metadata_data, indent=2))
    
    # Text extraction methods - STUB IMPLEMENTATIONS
    
    async def _extract_text_from_txt(self, file_path: Path) -> str:
        """Extract text from TXT file - STUB IMPLEMENTATION."""
        print(f"Hello World - TXT text extraction stub for: {file_path}")
        return f"Hello World - Stub TXT content from {file_path.name}"
    
    async def _extract_text_from_doc(self, file_path: Path) -> str:
        """Extract text from DOC file - STUB IMPLEMENTATION."""
        print(f"Hello World - DOC text extraction stub for: {file_path}")
        return f"Hello World - Stub DOC content from {file_path.name}"
    
    async def _extract_text_from_docx(self, file_path: Path) -> str:
        """Extract text from DOCX file - STUB IMPLEMENTATION."""
        print(f"Hello World - DOCX text extraction stub for: {file_path}")
        return f"Hello World - Stub DOCX content from {file_path.name}"
    
    async def _extract_text_from_pdf(self, file_path: Path) -> str:
        """Extract text from PDF file - STUB IMPLEMENTATION."""
        print(f"Hello World - PDF text extraction stub for: {file_path}")
        return f"Hello World - Stub PDF content from {file_path.name}"
    
    async def _extract_text_from_rtf(self, file_path: Path) -> str:
        """Extract text from RTF file - STUB IMPLEMENTATION."""
        print(f"Hello World - RTF text extraction stub for: {file_path}")
        return f"Hello World - Stub RTF content from {file_path.name}"
    
    async def _extract_text_from_odt(self, file_path: Path) -> str:
        """Extract text from ODT file - STUB IMPLEMENTATION."""
        print(f"Hello World - ODT text extraction stub for: {file_path}")
        return f"Hello World - Stub ODT content from {file_path.name}"


# Global file service instance
file_service = FileService()