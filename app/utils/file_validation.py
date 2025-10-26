"""
File validation utilities including file signature (magic number) validation.
"""

from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException
import io
import logging

# File signatures (magic numbers) for supported file types
FILE_SIGNATURES = {
    # PDF files
    'pdf': [
        b'\x25\x50\x44\x46',  # %PDF
    ],
    
    # Microsoft Word Documents
    'doc': [
        b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1',  # OLE2 compound document (legacy .doc)
        b'\x50\x4b\x03\x04',  # ZIP-based Office documents (modern .doc saved as .docx format)
    ],
    
    # Microsoft Word OOXML Documents
    'docx': [
        b'\x50\x4b\x03\x04',  # ZIP signature (DOCX is ZIP-based)
        b'\x50\x4b\x05\x06',  # Empty ZIP archive
        b'\x50\x4b\x07\x08',  # Spanned ZIP archive
    ],
    
    # JPEG Images
    'jpeg': [
        b'\xff\xd8\xff\xe0',  # JPEG with JFIF
        b'\xff\xd8\xff\xe1',  # JPEG with EXIF
        b'\xff\xd8\xff\xe2',  # JPEG with EXIF extension
        b'\xff\xd8\xff\xe3',  # JPEG
        b'\xff\xd8\xff\xe8',  # JPEG
        b'\xff\xd8\xff\xdb',  # JPEG raw
    ],
    
    'jpg': [  # Same as JPEG
        b'\xff\xd8\xff\xe0',
        b'\xff\xd8\xff\xe1',
        b'\xff\xd8\xff\xe2',
        b'\xff\xd8\xff\xe3',
        b'\xff\xd8\xff\xe8',
        b'\xff\xd8\xff\xdb',
    ],
    
    # PNG Images
    'png': [
        b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a',  # PNG signature
    ],
    
    # TIFF Images
    'tiff': [
        b'\x49\x49\x2a\x00',  # Little-endian TIFF
        b'\x4d\x4d\x00\x2a',  # Big-endian TIFF
    ],
    
    'tif': [  # Same as TIFF
        b'\x49\x49\x2a\x00',
        b'\x4d\x4d\x00\x2a',
    ],
    
    # Text files (no specific signature, will validate by content)
    'txt': [],
}

# Dangerous file signatures to reject
DANGEROUS_SIGNATURES = {
    'exe': [
        b'\x4d\x5a',  # Windows Executable (MZ)
    ],
    'elf': [
        b'\x7f\x45\x4c\x46',  # Linux Executable (ELF)
    ],
    'mach_o': [
        b'\xfe\xed\xfa\xce',  # Mach-O 32-bit
        b'\xfe\xed\xfa\xcf',  # Mach-O 64-bit
        b'\xca\xfe\xba\xbe',  # Universal binary
    ],
    'script': [
        b'\x23\x21',  # Shebang (#!)
    ],
    'batch': [
        b'\x40\x65\x63\x68\x6f\x20\x6f\x66\x66',  # @echo off
    ],
}

class FileValidator:
    """File validation service for uploaded files."""
    
    def __init__(self):
        self.max_document_size = 100 * 1024 * 1024  # 100MB
        self.max_image_size = 50 * 1024 * 1024      # 50MB
        
        self.document_types = {'pdf', 'doc', 'docx', 'txt'}
        self.image_types = {'jpeg', 'jpg', 'png', 'tiff', 'tif'}
        self.supported_types = self.document_types | self.image_types
    
    def validate_file_signature(self, content: bytes, expected_extension: str) -> bool:
        """
        Validate file signature (magic numbers) against expected file type.
        
        Args:
            content: First few bytes of the file
            expected_extension: Expected file extension (without dot)
            
        Returns:
            True if signature matches, False otherwise
            
        Raises:
            HTTPException: If file has dangerous signature
        """
        logging.debug(f"Validating file signature for extension: {expected_extension}")
        
        # Check for dangerous signatures first
        self._check_dangerous_signatures(content)
        
        # Normalize extension
        ext = expected_extension.lower().strip('.')
        
        if ext not in self.supported_types:
            return False
        
        # Special handling for text files (no magic signature)
        if ext == 'txt':
            # Validate that content is mostly printable text
            if self._is_text_content(content):
                logging.debug(f"Text file content validated for {ext}")
                return True
            else:
                logging.warning(f"Invalid text file content for {ext}")
                return False
        
        # Get expected signatures for this file type
        expected_signatures = FILE_SIGNATURES.get(ext, [])
        
        # Check if content matches any expected signature
        for signature in expected_signatures:
            if content.startswith(signature):
                logging.debug(f"File signature validated successfully for {ext}")
                return True
        
        # Special handling for Office documents (DOCX can have DOC signatures)
        if ext in ['doc', 'docx']:
            # Check all Office-related signatures
            office_sigs = FILE_SIGNATURES['doc'] + FILE_SIGNATURES['docx']
            for signature in office_sigs:
                if content.startswith(signature):
                    logging.debug(f"Office document signature validated for {ext}")
                    return True
        
        logging.warning(f"File signature validation failed for {ext}")
        return False
    
    def _check_dangerous_signatures(self, content: bytes) -> None:
        """
        Check if file has dangerous signatures and reject if found.
        
        Args:
            content: File content to check
            
        Raises:
            HTTPException: If dangerous signature detected
        """
        for file_type, signatures in DANGEROUS_SIGNATURES.items():
            for signature in signatures:
                if content.startswith(signature):
                    logging.error(f"🚨 SECURITY: Dangerous file signature detected: {file_type}")
                    raise HTTPException(
                        status_code=400,
                        detail=f"File rejected: Executable or script files are not allowed"
                    )
    
    def _is_text_content(self, content: bytes) -> bool:
        """
        Check if content appears to be valid text.
        
        Args:
            content: File content to check
            
        Returns:
            True if content appears to be text, False otherwise
        """
        try:
            # Try to decode as UTF-8
            text = content.decode('utf-8')
            
            # Check if content is mostly printable characters
            printable_chars = sum(1 for c in text if c.isprintable() or c.isspace())
            total_chars = len(text)
            
            if total_chars == 0:
                return True  # Empty files are valid
            
            # Allow up to 5% non-printable characters
            printable_ratio = printable_chars / total_chars
            return printable_ratio >= 0.95
            
        except UnicodeDecodeError:
            # Try other common encodings
            for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    text = content.decode(encoding)
                    printable_chars = sum(1 for c in text if c.isprintable() or c.isspace())
                    total_chars = len(text)
                    
                    if total_chars == 0:
                        return True
                    
                    printable_ratio = printable_chars / total_chars
                    if printable_ratio >= 0.95:
                        return True
                except UnicodeDecodeError:
                    continue
            
            return False
    
    def validate_file_size(self, size: int, file_extension: str) -> bool:
        """
        Validate file size based on file type.
        
        Args:
            size: File size in bytes
            file_extension: File extension (with or without dot)
            
        Returns:
            True if size is valid, False otherwise
        """
        ext = file_extension.lower().strip('.')
        
        if ext in self.document_types:
            max_size = self.max_document_size
        elif ext in self.image_types:
            max_size = self.max_image_size
        else:
            return False
        
        is_valid = size <= max_size
        logging.debug(f"File size validation for {ext}: {size} bytes (max: {max_size}) - {'Valid' if is_valid else 'Invalid'}")
        return is_valid
    
    def validate_file_extension(self, filename: str) -> bool:
        """
        Validate file extension against supported types.
        
        Args:
            filename: Original filename
            
        Returns:
            True if extension is supported, False otherwise
        """
        if not filename or '.' not in filename:
            return False
        
        ext = filename.split('.')[-1].lower()
        is_supported = ext in self.supported_types
        
        logging.debug(f"File extension validation: {ext} - {'Supported' if is_supported else 'Not supported'}")
        return is_supported
    
    def get_expected_content_type(self, extension: str) -> str:
        """
        Get expected MIME content type for file extension.
        
        Args:
            extension: File extension (with or without dot)
            
        Returns:
            Expected MIME type
        """
        ext = extension.lower().strip('.')
        
        content_types = {
            'pdf': 'application/pdf',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'jpeg': 'image/jpeg',
            'jpg': 'image/jpeg',
            'png': 'image/png',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
            'txt': 'text/plain',
        }
        
        return content_types.get(ext, 'application/octet-stream')
    
    def validate_content_type(self, provided_type: str, expected_type: str) -> bool:
        """
        Validate provided content type against expected type.
        
        Args:
            provided_type: Content type from the upload
            expected_type: Expected content type based on extension
            
        Returns:
            True if types match or are compatible, False otherwise
        """
        # Normalize types
        provided = provided_type.lower() if provided_type else ''
        expected = expected_type.lower()
        
        # Direct match
        if provided == expected:
            return True
        
        # Handle common variations
        variations = {
            'image/jpg': 'image/jpeg',
            'image/tif': 'image/tiff',
            'application/x-tiff': 'image/tiff',
        }
        
        normalized_provided = variations.get(provided, provided)
        is_valid = normalized_provided == expected
        
        logging.debug(f"Content type validation: '{provided}' vs '{expected}' - {'Valid' if is_valid else 'Invalid'}")
        return is_valid
    
    async def comprehensive_file_validation(
        self, 
        content: bytes, 
        filename: str, 
        content_type: Optional[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Perform comprehensive file validation.
        
        Args:
            content: File content bytes
            filename: Original filename
            content_type: Provided content type
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        logging.info(f"Starting comprehensive file validation for: {filename}")
        
        errors = []
        
        # 1. Validate file extension
        if not self.validate_file_extension(filename):
            errors.append(f"Unsupported file extension. Supported: {', '.join(self.supported_types)}")
        
        # 2. Validate file size
        file_size = len(content)
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if not self.validate_file_size(file_size, ext):
            max_size_mb = (self.max_document_size if ext in self.document_types 
                          else self.max_image_size) // (1024 * 1024)
            errors.append(f"File too large. Maximum allowed: {max_size_mb}MB for {ext} files")
        
        # 3. Validate file signature
        try:
            if not self.validate_file_signature(content, ext):
                errors.append(f"Invalid file signature. File may be corrupted or not a valid {ext} file")
        except HTTPException as e:
            errors.append(e.detail)
        
        # 4. Validate content type if provided
        if content_type:
            expected_type = self.get_expected_content_type(ext)
            if not self.validate_content_type(content_type, expected_type):
                errors.append(f"Content type mismatch. Expected: {expected_type}, got: {content_type}")
        
        is_valid = len(errors) == 0
        if is_valid:
            logging.info(f"✅ File validation successful for: {filename}")
        else:
            logging.warning(f"❌ File validation failed for: {filename} - {len(errors)} errors: {'; '.join(errors)}")
        
        return is_valid, errors


# Global file validator instance
file_validator = FileValidator()