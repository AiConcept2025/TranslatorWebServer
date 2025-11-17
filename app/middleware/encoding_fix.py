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

        # Log entry for debugging - CHANGED TO INFO to ensure visibility
        logger.info(f"[ENCODING FIX] Processing: {request.method} {request.url.path}")
        print(f"[ENCODING FIX] Processing: {request.method} {request.url.path}")

        # ===================================================================
        # SPECIAL HANDLING FOR /submit ENDPOINT (GoogleTranslator debugging)
        # ===================================================================
        # Capture raw request body BEFORE Pydantic validation for debugging
        if request.url.path == "/submit":
            try:
                # Read and cache the body for logging
                body = await request.body()

                print("=" * 80)
                print("🔍 /submit REQUEST - RAW BODY CAPTURE (BEFORE VALIDATION)")
                print("=" * 80)
                print(f"📦 Content-Length: {len(body)} bytes")
                print(f"📦 Content-Type: {request.headers.get('content-type', 'unknown')}")

                # Decode and log the body
                try:
                    body_str = body.decode('utf-8')
                    print(f"\n📦 Raw Body (UTF-8):")
                    print(body_str)

                    # Try to parse as JSON for pretty printing
                    try:
                        import json
                        body_json = json.loads(body_str)
                        print(f"\n📦 Parsed JSON:")
                        print(json.dumps(body_json, indent=2))

                        # Highlight the transaction_id value
                        transaction_id = body_json.get('transaction_id')
                        print(f"\n🎯 TRANSACTION_ID VALUE: {repr(transaction_id)}")
                        print(f"🎯 TRANSACTION_ID TYPE: {type(transaction_id).__name__}")

                        if transaction_id is None:
                            print("❌ ISSUE CONFIRMED: transaction_id is null/None in request!")
                        elif not transaction_id:
                            print(f"❌ ISSUE: transaction_id is empty: {repr(transaction_id)}")
                        else:
                            print(f"✅ transaction_id looks valid: {transaction_id}")

                    except json.JSONDecodeError as e:
                        print(f"⚠️  JSON parsing failed: {e}")
                except UnicodeDecodeError:
                    print(f"⚠️  Body is not UTF-8: {body.hex()[:200]}")

                print("=" * 80)

                # IMPORTANT: Re-wrap body in a new stream for Pydantic to consume
                # This prevents the "body already consumed" issue
                from io import BytesIO

                async def receive():
                    return {"type": "http.request", "body": body}

                # Create a new request scope with cached body
                request._receive = receive

            except Exception as e:
                print(f"⚠️  Error capturing /submit body: {e}")
                logger.error(f"Error capturing /submit request body: {e}", exc_info=True)

        # CRITICAL FIX: DO NOT consume request body in middleware for other endpoints
        # BaseHTTPMiddleware + body reading causes stream corruption and ClientDisconnect errors
        # FastAPI/Pydantic handles encoding perfectly - this middleware is unnecessary
        #
        # Previous behavior: Tried to read body to fix encoding issues
        # Problem: Consuming body stream causes it to be unavailable to endpoints
        # Result: FastAPI waits indefinitely for body data, causing 90s timeouts
        #
        # Solution: Skip body processing entirely, let FastAPI handle it (except /submit above)

        if request.url.path != "/submit":
            logger.info(f"[ENCODING FIX] Skipping body processing for: {request.url.path}")
            print(f"[ENCODING FIX] SKIPPING {request.url.path} - Body NOT consumed (middleware disabled)")

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