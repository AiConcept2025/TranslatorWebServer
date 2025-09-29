"""
Page Counter Service for the Translation Web Server.
Integrates the PageCounter submodule functionality.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Add the PageCounter submodule to the Python path
page_counter_path = Path(__file__).parent.parent / "app-counter"
if str(page_counter_path) not in sys.path:
    sys.path.append(str(page_counter_path))

from page_count import selector


class PageCounterService:
    """Service for counting pages in various document formats."""
    
    def __init__(self):
        """Initialize the PageCounter service."""
        self.supported_extensions = {
            '.pdf', '.doc', '.docx', '.txt', '.rtf', 
            '.tiff', '.png', '.jpg', '.jpeg'
        }
    
    async def count_pages(self, file_path: str) -> int:
        """
        Count pages in a document file.
        
        Args:
            file_path: Path to the file to count pages for
            
        Returns:
            Number of pages in the document, -1 if error or unsupported format
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return -1
            
            # Get file extension
            _, extension = os.path.splitext(file_path)
            extension = extension.lower()
            
            # Check if format is supported
            if extension not in self.supported_extensions:
                return -1
            
            # Use the PageCounter selector function
            page_count = selector(file_path)
            return page_count
            
        except Exception as e:
            print(f"Error counting pages for {file_path}: {e}")
            return -1
    
    async def count_pages_by_file_id(self, file_id: str, upload_dir: str) -> int:
        """
        Count pages for a file by its ID.
        
        Args:
            file_id: The file identifier
            upload_dir: Directory where uploaded files are stored
            
        Returns:
            Number of pages in the document, -1 if error or file not found
        """
        try:
            upload_path = Path(upload_dir)
            
            # Try to find the file with any supported extension
            for ext in self.supported_extensions:
                file_path = upload_path / f"{file_id}{ext}"
                if file_path.exists():
                    return await self.count_pages(str(file_path))
            
            # File not found
            return -1
            
        except Exception as e:
            print(f"Error counting pages for file_id {file_id}: {e}")
            return -1
    
    def is_supported_format(self, filename: str) -> bool:
        """
        Check if a file format is supported for page counting.
        
        Args:
            filename: Name of the file to check
            
        Returns:
            True if format is supported, False otherwise
        """
        _, extension = os.path.splitext(filename)
        return extension.lower() in self.supported_extensions
    
    def get_supported_formats(self) -> list[str]:
        """
        Get list of supported file formats.
        
        Returns:
            List of supported file extensions (including the dot)
        """
        return sorted(list(self.supported_extensions))


# Global page counter service instance
page_counter_service = PageCounterService()