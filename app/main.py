"""
Main FastAPI application for the Translation Web Server.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
import uvicorn
from contextlib import asynccontextmanager
import logging
import time

# Import configuration
from app.config import settings

# Import routers
from app.routers import languages, upload, translate, payment

# Import middleware and utilities (will create these next)
from app.middleware.rate_limiting import RateLimitMiddleware
from app.middleware.logging import LoggingMiddleware
from app.utils.health import health_checker


# Application lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # Startup
    logging.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Initialize services
    await initialize_services()
    
    # Create required directories
    settings.ensure_directories()
    
    yield
    
    # Shutdown
    logging.info(f"Shutting down {settings.app_name}")
    await cleanup_services()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A comprehensive translation web service supporting multiple languages and file formats",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=["*"] if settings.cors_headers == "*" else settings.cors_headers.split(',')
)

# Add custom middleware
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(languages.router)
app.include_router(upload.router)
app.include_router(translate.router)
app.include_router(payment.router)

# Compatibility redirects for old endpoints
@app.post("/translate", tags=["Compatibility"])
async def translate_redirect():
    """Redirect old /translate endpoint to new /api/translate endpoint."""
    logging.warning("DEPRECATED: /translate endpoint called. Use /api/translate instead.")
    raise HTTPException(
        status_code=308,  # Permanent redirect
        detail="This endpoint has moved to /api/translate",
        headers={"Location": "/api/translate"}
    )

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "healthy",
        "environment": settings.environment,
        "documentation": "/docs" if settings.debug else "Documentation disabled in production",
        "endpoints": {
            "languages": "/api/languages",
            "upload": "/api/upload",
            "translate": "/api/translate", 
            "payment": "/api/payment/create-intent",
            "health": "/health"
        }
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    try:
        health_status = await health_checker.check_health()
        
        if health_status["status"] == "healthy":
            return JSONResponse(
                content=health_status,
                status_code=200
            )
        else:
            return JSONResponse(
                content=health_status,
                status_code=503
            )
    
    except Exception as e:
        return JSONResponse(
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            },
            status_code=503
        )


# API version endpoint
@app.get("/api/v1", tags=["API Info"])
async def api_info():
    """API version information."""
    return {
        "api_version": "v1",
        "app_version": settings.app_version,
        "features": {},
        "supported_formats": settings.allowed_file_extensions,
        "max_file_size_mb": round(settings.max_file_size / (1024 * 1024), 2)
    }


# Custom exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error response format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_error"
            },
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with error logging."""
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if settings.debug:
        error_detail = str(exc)
    else:
        error_detail = "Internal server error"
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": 500,
                "message": error_detail,
                "type": "internal_error"
            },
            "timestamp": time.time(),
            "path": str(request.url)
        }
    )


# Request timeout middleware
@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Add request timeout handling."""
    import asyncio
    
    try:
        # Set timeout based on endpoint
        if "/files/upload" in str(request.url):
            timeout = 300  # 5 minutes for file uploads
        elif "/translate" in str(request.url):
            timeout = 120  # 2 minutes for translations
        else:
            timeout = 30   # 30 seconds for other requests
        
        response = await asyncio.wait_for(call_next(request), timeout=timeout)
        return response
    
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=408,
            content={
                "success": False,
                "error": {
                    "code": 408,
                    "message": "Request timeout",
                    "type": "timeout_error"
                },
                "timestamp": time.time()
            }
        )


# Custom OpenAPI schema
def custom_openapi():
    """Generate custom OpenAPI schema with additional information."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        description="""
        ## Translation Web Server API
        
        A comprehensive translation service supporting multiple languages, file formats, and payment processing.
        
        ### Features
        - **Text Translation**: Translate text strings using multiple services
        - **File Translation**: Support for various document formats
        - **Batch Processing**: Handle multiple translations simultaneously
        - **Language Detection**: Automatic language identification
        - **Payment Integration**: Stripe-powered payment processing
        - **Rate Limiting**: Built-in request rate limiting
        - **File Upload**: Secure file handling and storage
        
        ### Supported Services
        - Google Translate (Free & Paid)
        - DeepL
        - Azure Translator
        
        ### Authentication
        API key authentication required for production usage.
        
        ### Rate Limits
        - Free tier: 100 requests per hour
        - Paid tiers: Higher limits based on subscription
        """,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key"
        },
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer"
        }
    }
    
    # Add example servers
    openapi_schema["servers"] = [
        {
            "url": f"http://localhost:{settings.port}",
            "description": "Development server"
        },
        {
            "url": "https://api.translator.example.com",
            "description": "Production server"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Startup and shutdown functions
async def initialize_services():
    """Initialize application services."""
    logging.info("Initializing services...")
    
    # Initialize translation services
    from app.services.translation_service import translation_service
    logging.info(f"Translation services available: {list(translation_service.services.keys())}")
    
    # Initialize payment service
    from app.services.payment_service import payment_service
    if payment_service.stripe_enabled:
        logging.info("Stripe payment service initialized")
    else:
        logging.warning("Stripe payment service not configured")
    
    # Initialize file service
    from app.services.file_service import file_service
    logging.info("File service initialized")
    
    logging.info("All services initialized successfully")


async def cleanup_services():
    """Cleanup services on shutdown."""
    logging.info("Cleaning up services...")
    
    # Cleanup temporary files
    from app.services.file_service import file_service
    try:
        deleted_count = await file_service.cleanup_temp_files(1)  # Clean files older than 1 hour
        logging.info(f"Cleaned up {deleted_count} temporary files")
    except Exception as e:
        logging.error(f"Error cleaning up temporary files: {e}")
    
    logging.info("Service cleanup completed")


# Development server runner
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run the server
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True
    )