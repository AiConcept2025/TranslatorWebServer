# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TranslatorWebServer - A FastAPI-based translation service with **STUB IMPLEMENTATIONS** for development and demonstration purposes.

**Important**: This is a fully implemented FastAPI project with stub functions that use "Hello World" print statements instead of actual translation, file processing, and payment functionality.

## Development Commands

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
```

### Running the Application
```bash
# Run with Python
python -m app.main

# Or run with uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Testing
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

### Code Quality
```bash
# Format code
black app/

# Lint code
flake8 app/

# Type checking
mypy app/
```

## Project Architecture

### Technology Stack
- **Framework**: FastAPI (Python async web framework)
- **Validation**: Pydantic models for request/response validation
- **Configuration**: Environment-based configuration with pydantic-settings
- **File Upload**: Multipart file handling with aiofiles
- **Middleware**: Custom logging and rate limiting middleware
- **Health Checks**: Comprehensive health monitoring
- **Documentation**: Auto-generated OpenAPI/Swagger documentation

### Project Structure
```
TranslatorWebServer/
├── app/
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py              # Configuration management
│   ├── models/                # Pydantic models
│   │   ├── requests.py        # Request models with validation
│   │   └── responses.py       # Response models
│   ├── routers/               # API route handlers
│   │   ├── translate.py       # Translation endpoints (STUBBED)
│   │   ├── upload.py          # File upload endpoints (STUBBED)
│   │   ├── languages.py       # Language endpoints (STUBBED)
│   │   └── payment.py         # Payment endpoints (STUBBED)
│   ├── services/              # Business logic services
│   │   ├── translation_service.py  # Translation service (STUBBED)
│   │   ├── file_service.py         # File handling service (STUBBED)
│   │   └── payment_service.py      # Payment processing (STUBBED)
│   ├── middleware/            # Custom middleware
│   │   ├── logging.py         # Request/response logging (FUNCTIONAL)
│   │   └── rate_limiting.py   # Rate limiting (FUNCTIONAL)
│   └── utils/                 # Utility functions
│       └── health.py          # Health check utilities (STUBBED)
├── uploads/                   # File upload directory
├── requirements.txt           # Python dependencies
├── .env.example              # Environment configuration template
├── .gitignore                # Git ignore rules
└── README.md                 # Project documentation
```

## Implementation Status

### ✅ Fully Implemented (Functional)
- FastAPI application setup and configuration
- Request/response models with validation
- API routing and endpoint structure
- Middleware (logging, rate limiting, CORS)
- Health check endpoints
- Environment configuration management
- OpenAPI/Swagger documentation
- Error handling and exception management

### 🔄 Stub Implementations (Print "Hello World")
- **Translation Services**: Google Translate, DeepL, Azure Translator
- **File Processing**: Text extraction from DOC, DOCX, PDF, RTF, ODT
- **Payment Processing**: Stripe integration and webhooks
- **Language Detection**: Automatic language identification
- **File Upload**: Actual file storage and metadata
- **Database Operations**: User history and persistent storage

## Key Features

### API Endpoints
- **Translation**: `/api/v1/translate/*` - Text and file translation (stubbed)
- **File Upload**: `/api/v1/files/*` - File upload and management (stubbed)
- **Languages**: `/api/v1/languages/*` - Language support and detection (stubbed)
- **Payments**: `/api/v1/payments/*` - Payment processing (stubbed)
- **Health**: `/health` - Application health monitoring (functional with stub metrics)

### Middleware Features
- **Request Logging**: Comprehensive request/response logging with sanitization
- **Rate Limiting**: Configurable rate limiting with different limits per endpoint
- **CORS Support**: Cross-origin request handling
- **Error Handling**: Consistent error responses with request IDs

### Configuration
- Environment-based configuration with validation
- Support for multiple translation service API keys
- Configurable file upload limits and storage paths
- Rate limiting configuration
- Logging configuration

## Working with Stubs

### Understanding Stub Behavior
All stub functions:
1. Print "Hello World" messages to console with operation details
2. Return realistic-looking response data
3. Don't perform actual external API calls
4. Don't process real files or payments

### Replacing Stubs with Real Implementation
To replace stubs with real functionality:
1. **Translation Services**: Implement actual API calls to Google, DeepL, Azure
2. **File Processing**: Add real text extraction using libraries like PyPDF2, python-docx
3. **Payment Processing**: Implement actual Stripe API calls
4. **Database**: Add SQLAlchemy models and database operations
5. **Storage**: Implement real file storage and metadata persistence

### Example Stub Pattern
```python
async def translate_text(text: str, target_lang: str) -> str:
    print(f"Hello World - Translation stub: '{text[:30]}...' to {target_lang}")
    return f"[STUB] Translated '{text[:30]}...' to {target_lang}"
```

## Development Guidelines

### When Extending Functionality
1. Follow the existing pattern of separating routers, services, and models
2. Add proper request/response validation using Pydantic
3. Include appropriate error handling
4. Add logging for debugging
5. Update health checks if adding external dependencies
6. Maintain the stub pattern for non-essential services during development

### Testing Strategy
- Test API endpoints for proper request/response handling
- Test validation logic in Pydantic models
- Test middleware functionality
- Mock external services for unit tests
- Use stub responses for integration tests

### Performance Considerations
- Use async/await throughout for I/O operations
- Implement proper connection pooling when adding real database/API clients
- Consider caching strategies for translation results
- Monitor memory usage with file uploads
- Implement proper cleanup for temporary files

## Deployment Notes

For production deployment (after implementing real functionality):
1. Set `DEBUG=False` and `ENVIRONMENT=production`
2. Configure proper secret keys and API credentials
3. Set up PostgreSQL or other production database
4. Configure Redis for caching and session storage
5. Use proper logging configuration (structured logging)
6. Implement monitoring and alerting
7. Use a production ASGI server like Gunicorn with Uvicorn workers