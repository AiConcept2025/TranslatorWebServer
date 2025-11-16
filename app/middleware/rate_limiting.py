"""
Rate limiting middleware.
"""

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Optional
import time
import asyncio
from collections import defaultdict, deque

from app.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using sliding window algorithm."""
    
    def __init__(self, app):
        super().__init__(app)
        # In-memory storage (should use Redis in production)
        self.client_requests: Dict[str, deque] = defaultdict(lambda: deque())
        self.cleanup_task = None
        
        # Rate limit settings
        self.requests_per_window = settings.rate_limit_requests
        self.window_seconds = settings.rate_limit_window
        
        # Different limits for different endpoints
        self.endpoint_limits = {
            '/api/v1/translate': {'requests': 50, 'window': 3600},  # 50 per hour
            '/api/v1/files/upload': {'requests': 20, 'window': 3600},  # 20 per hour
            '/api/v1/languages': {'requests': 200, 'window': 3600},  # 200 per hour
            '/api/v1/payments': {'requests': 30, 'window': 3600},  # 30 per hour
            '/login/admin': {'requests': 5, 'window': 900},  # 5 attempts per 15 minutes (brute force protection)
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process the request with rate limiting - WITH STUB ENHANCEMENTS."""
        # Skip rate limiting if disabled (e.g., for tests)
        if not settings.rate_limiting_enabled:
            return await call_next(request)

        print(f"Hello World - Rate limiting middleware processing: {request.method} {request.url.path}")

        # Get client identifier
        client_id = self._get_client_id(request)

        # Check if rate limited
        if await self._is_rate_limited(client_id, request):
            return await self._create_rate_limit_response(client_id, request)

        # Record the request
        await self._record_request(client_id, request)

        # Process the request
        response = await call_next(request)

        # Add rate limit headers
        await self._add_rate_limit_headers(response, client_id, request)

        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Priority order: API key > JWT token > IP address
        
        # Check for API key
        api_key = request.headers.get('X-API-Key')
        if api_key:
            return f"api_key:{api_key}"
        
        # Check for Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            return f"bearer:{token}"
        
        # Fall back to IP address
        client_ip = request.client.host
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        
        return f"ip:{client_ip}"
    
    async def _is_rate_limited(self, client_id: str, request: Request) -> bool:
        """Check if the client is rate limited."""
        now = time.time()
        requests = self.client_requests[client_id]
        
        # Get rate limits for this endpoint
        limits = self._get_endpoint_limits(request.url.path)
        
        # Remove old requests outside the window
        while requests and requests[0]['timestamp'] < now - limits['window']:
            requests.popleft()
        
        # Check if limit exceeded
        return len(requests) >= limits['requests']
    
    async def _record_request(self, client_id: str, request: Request):
        """Record a request for rate limiting."""
        now = time.time()
        self.client_requests[client_id].append({
            'timestamp': now,
            'path': request.url.path,
            'method': request.method
        })
    
    def _get_endpoint_limits(self, path: str) -> Dict[str, int]:
        """Get rate limits for a specific endpoint."""
        # Check for specific endpoint limits
        for endpoint_pattern, limits in self.endpoint_limits.items():
            if path.startswith(endpoint_pattern):
                return limits
        
        # Default limits
        return {
            'requests': self.requests_per_window,
            'window': self.window_seconds
        }
    
    async def _create_rate_limit_response(self, client_id: str, request: Request) -> Response:
        """Create rate limit exceeded response."""
        limits = self._get_endpoint_limits(request.url.path)
        requests = self.client_requests[client_id]
        
        # Calculate reset time
        if requests:
            oldest_request = requests[0]['timestamp']
            reset_time = oldest_request + limits['window']
        else:
            reset_time = time.time() + limits['window']
        
        # Create error response
        error_content = {
            "success": False,
            "error": {
                "code": 429,
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "details": {
                    "limit": limits['requests'],
                    "window_seconds": limits['window'],
                    "reset_time": reset_time,
                    "retry_after": int(reset_time - time.time())
                }
            },
            "timestamp": time.time()
        }
        
        from fastapi.responses import JSONResponse
        response = JSONResponse(
            content=error_content,
            status_code=429
        )
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limits['requests'])
        response.headers["X-RateLimit-Remaining"] = "0"
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        response.headers["Retry-After"] = str(int(reset_time - time.time()))
        
        return response
    
    async def _add_rate_limit_headers(self, response: Response, client_id: str, request: Request):
        """Add rate limit headers to the response."""
        limits = self._get_endpoint_limits(request.url.path)
        requests = self.client_requests[client_id]
        
        now = time.time()
        
        # Count requests in current window
        current_requests = sum(1 for req in requests if req['timestamp'] > now - limits['window'])
        remaining = max(0, limits['requests'] - current_requests)
        
        # Calculate reset time
        if requests:
            oldest_in_window = min(
                req['timestamp'] for req in requests 
                if req['timestamp'] > now - limits['window']
            )
            reset_time = oldest_in_window + limits['window']
        else:
            reset_time = now + limits['window']
        
        # Add headers
        response.headers["X-RateLimit-Limit"] = str(limits['requests'])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time))
        response.headers["X-RateLimit-Window"] = str(limits['window'])
    
    async def _start_cleanup_task(self):
        """Start background task to clean up old rate limit data."""
        if self.cleanup_task is not None:
            return
        
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(300)  # Clean up every 5 minutes
                    await self._cleanup_old_data()
                except Exception as e:
                    # Log error but don't stop the cleanup task
                    print(f"Rate limit cleanup error: {e}")
        
        self.cleanup_task = asyncio.create_task(cleanup_loop())
    
    async def _cleanup_old_data(self):
        """Clean up old rate limit data to prevent memory leaks."""
        now = time.time()
        max_window = max(limits['window'] for limits in self.endpoint_limits.values())
        cutoff_time = now - max_window * 2  # Keep data for 2x the longest window
        
        clients_to_remove = []
        for client_id, requests in self.client_requests.items():
            # Remove old requests
            while requests and requests[0]['timestamp'] < cutoff_time:
                requests.popleft()
            
            # Mark empty clients for removal
            if not requests:
                clients_to_remove.append(client_id)
        
        # Remove empty clients
        for client_id in clients_to_remove:
            del self.client_requests[client_id]