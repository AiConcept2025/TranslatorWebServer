"""
Logging middleware for request/response tracking.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging
import uuid
from typing import Dict, Any
import json

from app.config import settings


# Configure logger
logger = logging.getLogger("translator.middleware")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    def __init__(self, app):
        super().__init__(app)
        self.sensitive_headers = {
            'authorization', 'x-api-key', 'cookie', 'x-auth-token'
        }
        self.log_request_body = settings.debug
        self.log_response_body = settings.debug
    
    async def dispatch(self, request: Request, call_next):
        """Process request with logging - WITH STUB ENHANCEMENTS."""
        print(f"Hello World - Logging middleware processing: {request.method} {request.url.path}")
        
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Log request
        await self._log_request(request, request_id)
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log response
            await self._log_response(request, response, request_id, process_time)
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"
            
            return response
            
        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            await self._log_error(request, e, request_id, process_time)
            raise
    
    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request."""
        
        # Get client info
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        
        user_agent = request.headers.get('User-Agent', 'Unknown')
        
        # Prepare log data
        log_data = {
            'request_id': request_id,
            'method': request.method,
            'url': str(request.url),
            'path': request.url.path,
            'query_params': dict(request.query_params),
            'client_ip': client_ip,
            'user_agent': user_agent,
            'headers': self._sanitize_headers(dict(request.headers)),
            'timestamp': time.time()
        }
        
        # Add request body if enabled and appropriate
        if (self.log_request_body and 
            request.method in ['POST', 'PUT', 'PATCH'] and
            self._should_log_body(request)):
            try:
                body = await self._get_request_body(request)
                if body:
                    log_data['body'] = body
            except Exception as e:
                log_data['body_error'] = str(e)
        
        # Log request
        if settings.is_development:
            logger.info(f"Incoming request: {request.method} {request.url.path}")
            logger.debug(f"Request details: {json.dumps(log_data, default=str, indent=2)}")
        else:
            logger.info(
                f"Request - {request_id} - {request.method} {request.url.path} - {client_ip}",
                extra={'request_data': log_data}
            )
    
    async def _log_response(self, request: Request, response, request_id: str, process_time: float):
        """Log outgoing response."""
        
        log_data = {
            'request_id': request_id,
            'status_code': response.status_code,
            'process_time': process_time,
            'response_headers': dict(response.headers),
            'timestamp': time.time()
        }
        
        # Add response body if enabled and appropriate
        if (self.log_response_body and 
            self._should_log_response_body(response)):
            try:
                body = await self._get_response_body(response)
                if body:
                    log_data['body'] = body
            except Exception as e:
                log_data['body_error'] = str(e)
        
        # Determine log level based on status code
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO
        
        # Log response
        if settings.is_development:
            logger.log(
                log_level,
                f"Response: {response.status_code} - {process_time:.4f}s - {request.method} {request.url.path}"
            )
            if log_level >= logging.WARNING:
                logger.debug(f"Response details: {json.dumps(log_data, default=str, indent=2)}")
        else:
            logger.log(
                log_level,
                f"Response - {request_id} - {response.status_code} - {process_time:.4f}s",
                extra={'response_data': log_data}
            )
    
    async def _log_error(self, request: Request, error: Exception, request_id: str, process_time: float):
        """Log request processing error."""
        
        log_data = {
            'request_id': request_id,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'process_time': process_time,
            'method': request.method,
            'path': request.url.path,
            'timestamp': time.time()
        }
        
        logger.error(
            f"Request error - {request_id} - {type(error).__name__}: {str(error)}",
            extra={'error_data': log_data},
            exc_info=True
        )
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Remove sensitive information from headers."""
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized
    
    def _should_log_body(self, request: Request) -> bool:
        """Determine if request body should be logged."""
        content_type = request.headers.get('Content-Type', '').lower()
        
        # Don't log file uploads or binary content
        if ('multipart/form-data' in content_type or
            'application/octet-stream' in content_type or
            'image/' in content_type or
            'video/' in content_type or
            'audio/' in content_type):
            return False
        
        # Don't log very large bodies
        content_length = request.headers.get('Content-Length')
        if content_length and int(content_length) > 10000:  # 10KB limit
            return False
        
        return True
    
    def _should_log_response_body(self, response) -> bool:
        """Determine if response body should be logged."""
        content_type = response.headers.get('Content-Type', '').lower()
        
        # Only log JSON responses
        if 'application/json' not in content_type:
            return False
        
        # Don't log large responses
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > 10000:  # 10KB limit
            return False
        
        return True
    
    async def _get_request_body(self, request: Request) -> Any:
        """Get request body for logging with robust encoding handling."""
        try:
            content_type = request.headers.get('Content-Type', '').lower()
            
            if 'application/json' in content_type:
                body = await request.json()
                return self._sanitize_body(body)
            elif 'application/x-www-form-urlencoded' in content_type:
                form = await request.form()
                return dict(form)
            else:
                body = await request.body()
                if len(body) < 1000:  # Only log small text bodies
                    return self._safe_decode_body(body)
                else:
                    return f"<binary data: {len(body)} bytes>"
        except Exception as e:
            return f"<body read error: {str(e)}>"
    
    def _safe_decode_body(self, body: bytes) -> str:
        """Safely decode request body with multiple encoding attempts."""
        if not body:
            return ""
        
        # Try multiple encodings in order of likelihood
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                decoded = body.decode(encoding)
                # Validate the decoded text doesn't contain replacement characters
                if '\ufffd' not in decoded:
                    return f"<{encoding}> {decoded}"
                elif encoding == 'utf-8':
                    # If UTF-8 fails, log the problematic bytes for debugging
                    try:
                        # Find the first problematic byte
                        body.decode('utf-8')  # This will raise UnicodeDecodeError
                    except UnicodeDecodeError as e:
                        logger.warning(f"UTF-8 decode error: {e}")
            except UnicodeDecodeError:
                continue
        
        # If all encodings fail, return hex representation
        return f"<hex> {body.hex()[:200]}..." if len(body) > 100 else f"<hex> {body.hex()}"
    
    async def _get_response_body(self, response) -> Any:
        """Get response body for logging."""
        # This is complex because response body might already be consumed
        # In production, you might want to use a more sophisticated approach
        return None
    
    def _sanitize_body(self, body: Any) -> Any:
        """Remove sensitive information from request/response body."""
        if isinstance(body, dict):
            sanitized = {}
            sensitive_fields = {
                'password', 'token', 'api_key', 'secret', 'private_key',
                'credit_card', 'ssn', 'social_security'
            }
            
            for key, value in body.items():
                if any(sensitive_field in key.lower() for sensitive_field in sensitive_fields):
                    sanitized[key] = "[REDACTED]"
                elif isinstance(value, (dict, list)):
                    sanitized[key] = self._sanitize_body(value)
                else:
                    sanitized[key] = value
            
            return sanitized
        
        elif isinstance(body, list):
            return [self._sanitize_body(item) for item in body]
        
        else:
            return body