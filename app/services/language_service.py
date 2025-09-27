"""
Language service for parsing supported languages from file.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LanguageService:
    """Service for handling language-related operations."""
    
    def __init__(self):
        self.languages_file = Path("supported_languages.txt")
        self._cached_languages: Optional[List[Dict[str, str]]] = None
        
    async def get_supported_languages(self) -> List[Dict[str, str]]:
        """
        Parse and return supported languages from supported_languages.txt file.
        
        Returns:
            List of dictionaries with 'code' and 'name' keys
            
        Raises:
            FileNotFoundError: If supported_languages.txt file is not found
            Exception: If there's an error parsing the file
        """
        # Return cached languages if available
        if self._cached_languages is not None:
            logger.debug("Returning cached languages")
            return self._cached_languages
        
        try:
            # Check if file exists
            if not self.languages_file.exists():
                logger.error(f"Languages file not found: {self.languages_file}")
                raise FileNotFoundError(f"Supported languages file not found: {self.languages_file}")
            
            logger.info(f"Reading supported languages from {self.languages_file}")
            
            languages = []
            with open(self.languages_file, 'r', encoding='utf-8') as file:
                lines = file.readlines()
            
            # Process each line
            for line_number, line in enumerate(lines, 1):
                line = line.strip()
                
                # Skip empty lines and header line
                if not line or line.startswith('Language') or 'ISO-639' in line:
                    continue
                
                # Parse language entry by splitting on last whitespace
                # This handles multi-word language names correctly
                parts = line.split()
                if len(parts) < 2:
                    logger.warning(f"Skipping invalid line {line_number}: '{line}'")
                    continue
                
                # Everything before the last part is the name, last part is the code
                code = parts[-1]
                name = ' '.join(parts[:-1])
                
                # Clean up any extra formatting
                code = code.strip()
                name = name.strip()
                
                # Skip if code or name is empty
                if not code or not name:
                    logger.warning(f"Skipping line {line_number} with empty code or name: '{line}'")
                    continue
                
                languages.append({
                    "code": code,
                    "name": name
                })
            
            logger.info(f"Successfully parsed {len(languages)} languages from file")
            
            # Cache the results
            self._cached_languages = languages
            
            return languages
            
        except FileNotFoundError:
            logger.error("Supported languages file not found")
            raise
        except Exception as e:
            logger.error(f"Error parsing supported languages file: {e}")
            raise Exception(f"Failed to parse supported languages: {str(e)}")
    
    def clear_cache(self):
        """Clear the cached languages to force reload from file."""
        logger.info("Clearing languages cache")
        self._cached_languages = None
    
    async def reload_languages(self) -> List[Dict[str, str]]:
        """Force reload languages from file by clearing cache first."""
        self.clear_cache()
        return await self.get_supported_languages()


# Global language service instance
language_service = LanguageService()