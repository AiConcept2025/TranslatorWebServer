"""
Encoding fix middleware to handle malformed UTF-8 requests.
This middleware intercepts requests and fixes encoding issues before they reach validation.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("translator.encoding_fix")


class EncodingFixMiddleware(BaseHTTPMiddleware):
    """Middleware to fix encoding issues in incoming requests."""
    
    def __init__(self, app):
        super().__init__(app)
        self.content_types_to_fix = {
            'application/json',
            'application/x-www-form-urlencoded',
            'text/plain'
        }
    
    async def dispatch(self, request: Request, call_next):
        """Fix encoding issues in request before processing."""
        
        # Only process specific content types
        content_type = request.headers.get('Content-Type', '').lower().split(';')[0]
        
        if content_type in self.content_types_to_fix:
            try:
                # Read the raw request body
                body = await request.body()
                
                if body:
                    # Fix encoding issues in the body
                    fixed_body = self._fix_body_encoding(body, content_type)
                    
                    if fixed_body != body:
                        # Create a new request with the fixed body
                        logger.info(f"Fixed encoding issues in {content_type} request")
                        request = self._create_request_with_fixed_body(request, fixed_body)
            
            except Exception as e:
                logger.error(f"Error fixing request encoding: {e}")
                # Continue with original request if fixing fails
                pass
        
        return await call_next(request)
    
    def _fix_body_encoding(self, body: bytes, content_type: str) -> bytes:
        """Fix encoding issues in request body."""
        
        if content_type == 'application/json':
            return self._fix_json_encoding(body)
        elif content_type == 'application/x-www-form-urlencoded':
            return self._fix_form_encoding(body)
        elif content_type == 'text/plain':
            return self._fix_text_encoding(body)
        
        return body
    
    def _fix_json_encoding(self, body: bytes) -> bytes:
        """Fix encoding issues in JSON body."""
        try:
            # Try to decode and re-encode as UTF-8
            text = self._safe_decode(body)
            
            # Parse and re-serialize JSON to ensure it's valid
            data = json.loads(text)
            fixed_text = json.dumps(data, ensure_ascii=False)
            
            return fixed_text.encode('utf-8')
            
        except (json.JSONDecodeError, UnicodeError) as e:
            logger.warning(f"Could not fix JSON encoding: {e}")
            return body
    
    def _fix_form_encoding(self, body: bytes) -> bytes:
        """Fix encoding issues in form data."""
        try:
            text = self._safe_decode(body)
            return text.encode('utf-8')
        except UnicodeError:
            logger.warning("Could not fix form encoding")
            return body
    
    def _fix_text_encoding(self, body: bytes) -> bytes:
        """Fix encoding issues in plain text."""
        try:
            text = self._safe_decode(body)
            return text.encode('utf-8')
        except UnicodeError:
            logger.warning("Could not fix text encoding")
            return body
    
    def _safe_decode(self, body: bytes) -> str:
        """Safely decode bytes with multiple encoding attempts."""
        if not body:
            return ""
        
        # Try multiple encodings in order of likelihood
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                decoded = body.decode(encoding)
                
                # For UTF-8, check for replacement characters
                if encoding == 'utf-8' and '\ufffd' in decoded:
                    continue
                    
                return decoded
                
            except UnicodeDecodeError:
                continue
        
        # If all fail, use utf-8 with error replacement
        return body.decode('utf-8', errors='replace')
    
    def _create_request_with_fixed_body(self, original_request: Request, fixed_body: bytes) -> Request:
        """Create a new request with the fixed body."""
        # This is a simplified approach. In a real implementation,
        # you might need to use more sophisticated request reconstruction
        
        # For now, we'll modify the request's internal state
        # Note: This is a workaround and might not work in all cases
        original_request._body = fixed_body
        
        return original_request


# Helper function to check if text contains problematic characters
def contains_problematic_encoding(text: str) -> bool:
    """Check if text contains characters that suggest encoding issues."""
    
    # Common problematic characters from Windows-1252 in UTF-8 context
    problematic_chars = {
        '\u0092',  # Smart quote (byte 0x92 in Windows-1252)
        '\u0093',  # Smart quote open
        '\u0094',  # Smart quote close
        '\u0096',  # En dash
        '\u0097',  # Em dash
        '\ufffd'   # Unicode replacement character
    }
    
    return any(char in text for char in problematic_chars)


# Utility function for safe JSON parsing
def safe_json_loads(text: str) -> Optional[Dict[Any, Any]]:
    """Safely parse JSON with encoding fix attempts."""
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try fixing common encoding issues
        
        # Replace smart quotes with regular quotes
        fixed_text = text.replace('\u0092', "'").replace('\u0093', '"').replace('\u0094', '"')
        
        try:
            return json.loads(fixed_text)
        except json.JSONDecodeError:
            return None