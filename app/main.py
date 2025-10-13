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
from app.routers import languages, upload, auth
from app.routers import payment_simplified as payment

# Import middleware and utilities (will create these next)
from app.middleware.rate_limiting import RateLimitMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.encoding_fix import EncodingFixMiddleware
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

# Add custom middleware (order matters - encoding fix should be first)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(EncodingFixMiddleware)

# Include routers
app.include_router(languages.router)
app.include_router(upload.router)
app.include_router(payment.router)
app.include_router(auth.router)

# Import models for /translate endpoint
from pydantic import BaseModel, EmailStr
from typing import List, Optional

class FileInfo(BaseModel):
    id: str
    name: str
    size: int
    type: str

class TranslateRequest(BaseModel):
    files: List[FileInfo]
    sourceLanguage: str
    targetLanguage: str
    email: EmailStr
    paymentIntentId: Optional[str] = None

# Direct translate endpoint (Google Drive upload)
@app.post("/translate", tags=["Translation"])
async def translate_files(request: TranslateRequest):
    """
    SIMPLIFIED TRANSLATE ENDPOINT:
    1. Upload files to Google Drive {customer_email}/Temp/ folder
    2. Store metadata linking customer to files (no payment sessions)
    3. Return page count for pricing calculation
    4. Frontend processes payment with customer_email
    5. Payment webhook moves files from Temp/ to Inbox/
    """
    print(f"TRANSLATE REQUEST RECEIVED")
    print(f"Customer: {request.email}")
    print(f"Translation: {request.sourceLanguage} -> {request.targetLanguage}")
    print(f"Files to process: {len(request.files)}")
    for i, file_info in enumerate(request.files, 1):
        print(f"   File {i}: '{file_info.name}' ({file_info.size:,} bytes, {file_info.type})")
    
    # Validate email format (additional validation beyond EmailStr)
    import re
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(request.email):
        raise HTTPException(
            status_code=400,
            detail="Invalid email format"
        )
    
    # Check for disposable email domains (stub check)
    disposable_domains = ['tempmail.org', '10minutemail.com', 'guerrillamail.com']
    email_domain = request.email.split('@')[1].lower()
    if email_domain in disposable_domains:
        raise HTTPException(
            status_code=400,
            detail="Disposable email addresses are not allowed"
        )
    
    # Validate language codes
    valid_languages = [
        'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko',
        'ar', 'hi', 'nl', 'pl', 'tr', 'sv', 'da', 'no', 'fi', 'th',
        'vi', 'uk', 'cs', 'hu', 'ro'
    ]
    
    if request.sourceLanguage not in valid_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source language: {request.sourceLanguage}"
        )
    
    if request.targetLanguage not in valid_languages:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target language: {request.targetLanguage}"
        )
    
    if request.sourceLanguage == request.targetLanguage:
        raise HTTPException(
            status_code=400,
            detail="Source and target languages cannot be the same"
        )
    
    # Validate files
    if not request.files:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required"
        )
    
    if len(request.files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximum 10 files allowed per request"
        )
    
    # Import Google Drive service
    from app.services.google_drive_service import google_drive_service
    from app.exceptions.google_drive_exceptions import GoogleDriveError, google_drive_error_to_http_exception
    
    # Create Google Drive folder structure
    try:
        print(f"Creating Google Drive folder structure for: {request.email}")
        folder_id = await google_drive_service.create_customer_folder_structure(request.email)
        print(f"Google Drive folder created: {request.email}/Temp/ (ID: {folder_id})")
    except GoogleDriveError as e:
        print(f"Google Drive error creating folder: {e}")
        raise google_drive_error_to_http_exception(e)
    except Exception as e:
        print(f"Unexpected error creating folder: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create folder structure: {str(e)}"
        )
    
    # Generate storage ID
    import uuid
    storage_id = f"store_{uuid.uuid4().hex[:10]}"
    
    print(f"Created storage job: {storage_id}")
    print(f"Target folder: {request.email}/Temp/ (ID: {folder_id})")
    print(f"Starting file uploads to Google Drive...")
    
    # Store files with enhanced metadata (no sessions)
    stored_files = []
    total_pages = 0
    
    for i, file_info in enumerate(request.files, 1):
        try:
            print(f"   Uploading file {i}/{len(request.files)}: '{file_info.name}'")
            
            # Store dummy content (in real implementation this would be actual file content)
            dummy_content = f"File data for {file_info.name} ({file_info.size} bytes)".encode('utf-8')
            
            # Count pages for pricing (stub implementation)
            page_count = 1  # Default page count
            if file_info.name.lower().endswith('.pdf'):
                page_count = max(1, file_info.size // 50000)  # Estimate: 50KB per page
            elif file_info.name.lower().endswith(('.doc', '.docx')):
                page_count = max(1, file_info.size // 25000)  # Estimate: 25KB per page
            
            total_pages += page_count
            
            # Upload to Google Drive with metadata for customer linking (no sessions)
            file_result = await google_drive_service.upload_file_to_folder(
                file_content=dummy_content,
                filename=file_info.name,
                folder_id=folder_id,
                target_language=request.targetLanguage
            )
            
            # Update file with enhanced metadata for payment linking
            await google_drive_service.update_file_properties(
                file_id=file_result['file_id'],
                properties={
                    'customer_email': request.email,
                    'source_language': request.sourceLanguage,
                    'target_language': request.targetLanguage,
                    'page_count': str(page_count),
                    'status': 'awaiting_payment',
                    'upload_timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    'original_filename': file_info.name
                }
            )
            
            stored_files.append({
                "file_id": file_result['file_id'],
                "filename": file_info.name,
                "status": "stored",
                "page_count": page_count,
                "size": file_info.size,
                "google_drive_url": file_result.get('google_drive_url')
            })
            print(f"   Successfully uploaded: '{file_info.name}' -> Google Drive ID: {file_result['file_id']}, Pages: {page_count}")
            
        except Exception as e:
            print(f"   Failed to upload '{file_info.name}': {e}")
            stored_files.append({
                "file_id": None,
                "filename": file_info.name,
                "status": "failed",
                "page_count": 0,
                "size": file_info.size,
                "error": str(e)
            })
    
    # Summary of operation
    successful_uploads = len([f for f in stored_files if f["status"] == "stored"])
    failed_uploads = len([f for f in stored_files if f["status"] == "failed"])
    
    print(f"UPLOAD COMPLETE: {successful_uploads} successful, {failed_uploads} failed")
    print(f"Total pages for pricing: {total_pages}")
    print(f"Customer: {request.email} (no session needed)")
    print(f"Next step: Process payment, then webhook will move files from Temp to Inbox")
    
    return JSONResponse(
        content={
            "success": True,
            "data": {
                "id": storage_id,
                "status": "stored",
                "progress": 100,
                "message": f"Files uploaded successfully. Ready for payment.",
                
                # Pricing information
                "pricing": {
                    "total_pages": total_pages,
                    "price_per_page": 0.10,  # $0.10 per page
                    "total_amount": total_pages * 0.10,
                    "currency": "USD"
                },
                
                # File information
                "files": {
                    "total_files": len(request.files),
                    "successful_uploads": successful_uploads,
                    "failed_uploads": failed_uploads,
                    "stored_files": stored_files
                },
                
                # Customer information (used by payment webhook)
                "customer": {
                    "email": request.email,
                    "source_language": request.sourceLanguage,
                    "target_language": request.targetLanguage,
                    "temp_folder_id": folder_id
                },
                
                # Payment information
                "payment": {
                    "required": True,
                    "amount_cents": int(total_pages * 10),  # Convert to cents
                    "description": f"Translation service: {successful_uploads} files, {total_pages} pages",
                    "customer_email": request.email
                }
            },
            "error": None
        }
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
            "languages": "/api/v1/languages",
            "translate": "/translate",
            "payment_create": "/api/payment/create-intent",
            "payment_success": "/api/payment/success",
            "health": "/health"
        }
    }


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    try:
        # Get general health status
        health_status = await health_checker.check_health()

        # Add MongoDB health check
        from app.database import database
        mongodb_health = await database.health_check()
        health_status["database"] = mongodb_health

        # Overall health status
        overall_healthy = (
            health_status["status"] == "healthy" and
            mongodb_health.get("healthy", False)
        )

        if overall_healthy:
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
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with safe encoding handling."""
    try:
        # Safely serialize validation errors to avoid Unicode decode issues
        safe_errors = []
        for error in exc.errors():
            safe_error = {}
            for key, value in error.items():
                if isinstance(value, bytes):
                    # Handle bytes values that might contain non-UTF-8 data
                    try:
                        safe_error[key] = value.decode('utf-8')
                    except UnicodeDecodeError:
                        # Try alternative encodings
                        for encoding in ['latin1', 'cp1252', 'iso-8859-1']:
                            try:
                                safe_error[key] = f"<{encoding}> {value.decode(encoding)}"
                                break
                            except UnicodeDecodeError:
                                continue
                        else:
                            safe_error[key] = f"<hex> {value.hex()}"
                elif isinstance(value, str):
                    # Ensure string values are properly handled
                    safe_error[key] = value
                else:
                    safe_error[key] = str(value)
            safe_errors.append(safe_error)
        
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": 422,
                    "message": "Request validation failed",
                    "type": "validation_error",
                    "details": safe_errors
                },
                "timestamp": time.time(),
                "path": str(request.url)
            }
        )
    except Exception as e:
        # Fallback error handling if validation error processing fails
        logging.error(f"Error processing validation error: {e}", exc_info=True)
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": 422,
                    "message": "Request validation failed - encoding error",
                    "type": "validation_error_with_encoding_issue",
                    "raw_error": str(exc)
                },
                "timestamp": time.time(),
                "path": str(request.url)
            }
        )

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

    # Initialize MongoDB database connection
    from app.database import database
    mongodb_connected = await database.connect()
    if mongodb_connected:
        logging.info("MongoDB database connection established")
    else:
        logging.warning("MongoDB database connection failed - continuing without database")

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
    try:
        from app.services.file_service import file_service
        logging.info("File service initialized")
    except ImportError:
        logging.info("File service not available (stub implementation)")

    logging.info("All services initialized successfully")


async def cleanup_services():
    """Cleanup services on shutdown."""
    logging.info("Cleaning up services...")

    # Disconnect from MongoDB
    from app.database import database
    await database.disconnect()

    # Cleanup temporary files would go here in real implementation
    logging.info("No cleanup needed in stub implementation")

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