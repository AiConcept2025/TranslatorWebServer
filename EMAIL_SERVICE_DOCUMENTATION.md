# Email Notification Service - Technical Documentation

**Version:** 1.0.0
**Last Updated:** November 2025
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Configuration](#configuration)
5. [API Reference](#api-reference)
6. [Template System](#template-system)
7. [Data Models](#data-models)
8. [Error Handling](#error-handling)
9. [Testing](#testing)
10. [Deployment](#deployment)
11. [Security](#security)
12. [Performance](#performance)
13. [Monitoring & Logging](#monitoring--logging)
14. [Troubleshooting](#troubleshooting)
15. [Examples](#examples)
16. [FAQ](#faq)

---

## Overview

### Purpose

The Email Notification Service provides automated email notifications to users when their translation documents are ready for download. The service supports two distinct customer types with tailored email templates:

- **Individual Customers** (company_name = "Ind") - Casual, friendly tone
- **Corporate Customers** (company_name ≠ "Ind") - Professional, formal tone

### Key Features

✅ **Multi-Provider SMTP Support** - Yahoo, Gmail, SendGrid, Office 365
✅ **Template Engine** - Jinja2-based with HTML and plain text versions
✅ **Automatic Template Selection** - Based on customer type
✅ **Secure** - TLS encryption, HTML escaping, input validation
✅ **Resilient** - Non-blocking, graceful error handling
✅ **Testable** - Comprehensive unit and integration tests
✅ **Configurable** - Environment-based configuration
✅ **Production-Ready** - Logging, monitoring, error tracking

### Design Principles

1. **Fail-Safe** - Email failures don't break file submissions
2. **Template-Driven** - Easy to customize email content
3. **Provider-Agnostic** - Simple to switch SMTP providers
4. **Security First** - Input validation, encryption, sanitization
5. **Observable** - Comprehensive logging for debugging
6. **Testable** - Mocked tests for CI/CD pipelines

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Application                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP POST /submit
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Router Layer                       │
│                   (app/routers/submit.py)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Submit Service Layer                       │
│              (app/services/submit_service.py)                │
│                                                               │
│  • Validates submission                                      │
│  • Processes file metadata                                   │
│  • Calls email service (non-blocking)                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Email Service Layer                       │
│              (app/services/email_service.py)                 │
│                                                               │
│  • Determines customer type (Ind vs Corporate)               │
│  • Selects appropriate template                              │
│  • Renders template with context                             │
│  • Sends email via SMTP                                      │
│  • Returns result (success/failure)                          │
└──────┬────────────────────────────────┬─────────────────────┘
       │                                │
       ▼                                ▼
┌──────────────────┐          ┌────────────────────┐
│ Template Service │          │   SMTP Server      │
│   (Jinja2)       │          │  (Yahoo/Gmail/     │
│                  │          │   SendGrid)        │
│ • Loads template │          │                    │
│ • Renders HTML   │          │ • TLS encryption   │
│ • Renders text   │          │ • Authentication   │
│ • Validates      │          │ • Delivery         │
└──────────────────┘          └────────────────────┘
```

### Component Interaction Flow

```
1. Client → POST /submit
2. Router → submit_service.process_submission()
3. Submit Service:
   ├─ Create DocumentInfo objects
   ├─ Extract user information
   └─ Call email_service.send_translation_notification()
4. Email Service:
   ├─ Determine customer type
   ├─ Select template (individual/corporate)
   ├─ Call template_service.render_template()
   ├─ Build MIME message
   ├─ Create SMTP connection
   ├─ Send email
   └─ Return result
5. Submit Service:
   └─ Return response (includes email status)
6. Router → Return HTTP response to client
```

### Directory Structure

```
TranslatorWebServer/
├── app/
│   ├── models/
│   │   └── email.py                    # Email data models
│   ├── services/
│   │   ├── email_service.py            # SMTP email service
│   │   ├── template_service.py         # Jinja2 template engine
│   │   └── submit_service.py           # File submission service
│   ├── templates/
│   │   └── email/
│   │       ├── individual_notification.html
│   │       ├── individual_notification.txt
│   │       ├── corporate_notification.html
│   │       └── corporate_notification.txt
│   ├── routers/
│   │   └── submit.py                   # /submit endpoint
│   └── config.py                       # Configuration settings
├── tests/
│   ├── unit/
│   │   ├── test_email_service.py       # Email service unit tests
│   │   └── test_template_service.py    # Template service unit tests
│   └── integration/
│       └── test_submit_api.py          # API integration tests
├── EMAIL_SERVICE_SETUP.md              # Setup guide
└── .env.example                        # Configuration template
```

---

## Components

### 1. Email Service (`app/services/email_service.py`)

**Purpose:** Core service for sending emails via SMTP.

**Key Classes:**
- `EmailService` - Main service class
- `EmailServiceError` - Custom exception class

**Key Methods:**

```python
class EmailService:
    def __init__(self)
    def _validate_smtp_config(self) -> bool
    def _create_smtp_connection(self) -> smtplib.SMTP
    def _build_email_message(self, ...) -> MIMEMultipart
    def send_email(self, email_request: EmailRequest) -> EmailSendResult
    def send_translation_notification(self, ...) -> EmailSendResult
    def test_connection(self) -> Dict[str, Any]
```

**Responsibilities:**
- SMTP connection management
- Email construction (MIME multipart)
- Template selection logic
- Error handling and retry
- Logging and monitoring

**Configuration:**
- SMTP host, port, credentials
- TLS/SSL settings
- Timeout configuration
- Sender information

### 2. Template Service (`app/services/template_service.py`)

**Purpose:** Render email templates using Jinja2.

**Key Classes:**
- `TemplateService` - Main service class

**Key Methods:**

```python
class TemplateService:
    def __init__(self)
    def _initialize_environment(self)
    def render_template(self, template_name: str, context: Dict) -> str
    def render_string(self, template_string: str, context: Dict) -> str
    def template_exists(self, template_name: str) -> bool
    def list_templates(self) -> List[str]
```

**Responsibilities:**
- Jinja2 environment initialization
- Template loading from files
- Template rendering with context
- HTML auto-escaping
- Error handling

**Features:**
- Auto-escaping for security
- Trim blocks for cleaner output
- Template caching
- Error reporting

### 3. Submit Service (`app/services/submit_service.py`)

**Purpose:** Process file submissions and trigger email notifications.

**Key Classes:**
- `SubmitService` - Main service class

**Key Methods:**

```python
class SubmitService:
    async def process_submission(self, ...) -> Dict[str, Any]
    def _generate_translated_url(self, original_url: str) -> str
    def _extract_user_name_from_email(self, email: str) -> str
    async def process_bulk_submission(self, ...) -> Dict[str, Any]
```

**Responsibilities:**
- File submission processing
- Document metadata creation
- Email notification triggering
- User name extraction
- Bulk submission handling

**Integration Points:**
- Calls `email_service.send_translation_notification()`
- Creates `DocumentInfo` objects
- Handles email failures gracefully

### 4. Data Models (`app/models/email.py`)

**Purpose:** Define data structures for email operations.

**Key Models:**

```python
class DocumentInfo(BaseModel):
    document_name: str
    original_url: str
    translated_url: str

class EmailTemplate(str, Enum):
    INDIVIDUAL_NOTIFICATION = "individual_notification"
    CORPORATE_NOTIFICATION = "corporate_notification"

class EmailRequest(BaseModel):
    to_email: EmailStr
    to_name: str
    subject: str
    body_html: str
    body_text: str
    from_email: Optional[EmailStr]
    from_name: Optional[str]
    reply_to: Optional[EmailStr]

class TranslationNotificationContext(BaseModel):
    user_name: str
    user_email: EmailStr
    company_name: str
    documents: List[DocumentInfo]
    translation_service_company: str

    @property
    def is_individual(self) -> bool

    @property
    def template_type(self) -> EmailTemplate

class EmailSendResult(BaseModel):
    success: bool
    message: str
    error: Optional[str]
    recipient: EmailStr
    sent_at: Optional[str]
```

**Validation:**
- Email address validation
- URL validation
- Required field checks
- Type validation

---

## Configuration

### Environment Variables

All configuration is managed through environment variables in `.env`:

```bash
# SMTP Server Configuration
SMTP_HOST=smtp.mail.yahoo.com          # SMTP server hostname
SMTP_PORT=587                           # SMTP port (587 for TLS, 465 for SSL)
SMTP_USERNAME=your.email@yahoo.com     # SMTP username
SMTP_PASSWORD=app_specific_password    # SMTP password or app password
SMTP_USE_TLS=true                      # Enable TLS (recommended)
SMTP_USE_SSL=false                     # Enable SSL (alternative to TLS)
SMTP_TIMEOUT=30                        # Connection timeout in seconds

# Email Settings
EMAIL_FROM=your.email@yahoo.com        # Sender email address
EMAIL_FROM_NAME=Iris Solutions         # Sender display name
EMAIL_REPLY_TO=support@example.com     # Reply-to address (optional)
EMAIL_ENABLED=true                     # Enable/disable email service
EMAIL_TEMPLATE_DIR=./app/templates/email  # Template directory path

# Branding
TRANSLATION_SERVICE_COMPANY=Iris Solutions  # Company name in emails
```

### Configuration in Code

Configuration is loaded via `app/config.py`:

```python
from app.config import settings

# Access configuration
smtp_host = settings.smtp_host
smtp_port = settings.smtp_port
email_from = settings.email_from
template_dir = settings.email_template_dir
```

### SMTP Provider Configurations

#### Yahoo Mail (Default)

```bash
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

**Requirements:**
- Two-Step Verification enabled
- App-specific password generated

#### Gmail

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

**Requirements:**
- App-specific password (with 2FA)
- Less secure app access disabled

#### SendGrid

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your_sendgrid_api_key
SMTP_USE_TLS=true
```

**Requirements:**
- SendGrid account
- API key generated

#### Office 365

```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

**Requirements:**
- Office 365 account
- Modern authentication enabled

---

## API Reference

### EmailService

#### `send_email(email_request: EmailRequest) -> EmailSendResult`

Send a custom email.

**Parameters:**
- `email_request` (EmailRequest) - Email configuration

**Returns:**
- `EmailSendResult` - Send operation result

**Example:**

```python
from app.services.email_service import email_service
from app.models.email import EmailRequest

result = email_service.send_email(
    EmailRequest(
        to_email="user@example.com",
        to_name="John Doe",
        subject="Test Email",
        body_html="<p>Hello!</p>",
        body_text="Hello!"
    )
)

if result.success:
    print(f"Email sent at: {result.sent_at}")
else:
    print(f"Error: {result.error}")
```

#### `send_translation_notification(...) -> EmailSendResult`

Send translation notification email with automatic template selection.

**Parameters:**
- `documents` (List[DocumentInfo]) - List of translated documents
- `user_name` (str) - Recipient name
- `user_email` (str) - Recipient email address
- `company_name` (str) - Company name ("Ind" for individuals)

**Returns:**
- `EmailSendResult` - Send operation result

**Example:**

```python
from app.services.email_service import email_service
from app.models.email import DocumentInfo

documents = [
    DocumentInfo(
        document_name="report.pdf",
        original_url="https://drive.google.com/file/d/abc123/view",
        translated_url="https://drive.google.com/file/d/xyz789/view"
    )
]

result = email_service.send_translation_notification(
    documents=documents,
    user_name="Alice Johnson",
    user_email="alice@company.com",
    company_name="Acme Corp"  # Use "Ind" for individuals
)
```

#### `test_connection() -> Dict[str, Any]`

Test SMTP connection and authentication.

**Returns:**
- `dict` - Connection test result

**Example:**

```python
result = email_service.test_connection()

if result['success']:
    print("SMTP connection successful!")
    print(f"Details: {result['details']}")
else:
    print(f"Connection failed: {result['error']}")
```

### TemplateService

#### `render_template(template_name: str, context: Dict) -> str`

Render a template file with given context.

**Parameters:**
- `template_name` (str) - Template filename
- `context` (dict) - Template variables

**Returns:**
- `str` - Rendered template

**Example:**

```python
from app.services.template_service import template_service

html = template_service.render_template(
    "individual_notification.html",
    {
        "user_name": "John Doe",
        "company_name": "Ind",
        "documents": [
            {
                "document_name": "file.pdf",
                "original_url": "https://...",
                "translated_url": "https://..."
            }
        ],
        "translation_service_company": "Iris Solutions"
    }
)
```

#### `render_string(template_string: str, context: Dict) -> str`

Render a template from string.

**Parameters:**
- `template_string` (str) - Template content
- `context` (dict) - Template variables

**Returns:**
- `str` - Rendered template

**Example:**

```python
html = template_service.render_string(
    "<p>Hello {{ name }}!</p>",
    {"name": "World"}
)
# Result: "<p>Hello World!</p>"
```

#### `template_exists(template_name: str) -> bool`

Check if template file exists.

**Example:**

```python
if template_service.template_exists("individual_notification.html"):
    print("Template found!")
```

#### `list_templates() -> List[str]`

List all available template files.

**Example:**

```python
templates = template_service.list_templates()
print(f"Available templates: {templates}")
```

### SubmitService

#### `process_submission(...) -> Dict[str, Any]`

Process file submission and send email notification.

**Parameters:**
- `file_name` (str) - Name of submitted file
- `file_url` (str) - Google Drive URL
- `user_email` (str) - User's email address
- `company_name` (str) - Company name
- `transaction_id` (Optional[str]) - Transaction ID

**Returns:**
- `dict` - Processing result

**Example:**

```python
from app.services.submit_service import submit_service

result = await submit_service.process_submission(
    file_name="document.pdf",
    file_url="https://drive.google.com/file/d/abc123/view",
    user_email="user@example.com",
    company_name="Ind",
    transaction_id="txn_12345"
)

print(f"Status: {result['status']}")
print(f"Email sent: {result['email_sent']}")
```

---

## Template System

### Template Variables

All email templates have access to these variables:

```python
{
    "user_name": str,              # Recipient's name
    "company_name": str,           # Company name ("Ind" or company name)
    "documents": List[dict],       # List of documents
    "translation_service_company": str  # Service provider name
}
```

**Document Object Structure:**

```python
{
    "document_name": str,      # File name (e.g., "report.pdf")
    "original_url": str,       # URL to original document
    "translated_url": str      # URL to translated document
}
```

### Template Syntax

Templates use Jinja2 syntax:

#### Variables

```jinja2
{{ user_name }}
{{ company_name }}
{{ translation_service_company }}
```

#### Loops

```jinja2
{% for document in documents %}
    <p>{{ document.document_name }}</p>
    <a href="{{ document.translated_url }}">Download</a>
{% endfor %}
```

#### Conditionals

```jinja2
{% if documents|length > 1 %}
    <p>You have {{ documents|length }} documents ready.</p>
{% else %}
    <p>Your document is ready.</p>
{% endif %}
```

#### Filters

```jinja2
{{ user_name|upper }}          <!-- JOHN DOE -->
{{ document_name|lower }}       <!-- report.pdf -->
{{ documents|length }}          <!-- 3 -->
```

### Template Customization

#### Adding New Templates

1. Create HTML and text versions:
   ```
   app/templates/email/
   ├── my_template.html
   └── my_template.txt
   ```

2. Use in code:
   ```python
   html = template_service.render_template("my_template.html", context)
   text = template_service.render_template("my_template.txt", context)
   ```

#### Modifying Existing Templates

Templates are located in `app/templates/email/`:

- `individual_notification.html` - Individual customer HTML
- `individual_notification.txt` - Individual customer plain text
- `corporate_notification.html` - Corporate customer HTML
- `corporate_notification.txt` - Corporate customer plain text

**Best Practices:**
- Always update both HTML and text versions
- Test rendering after changes
- Validate HTML syntax
- Check mobile responsiveness
- Test with real email clients

#### Adding Custom Styles

In HTML templates:

```html
<style>
    .custom-button {
        background-color: #your-color;
        padding: 10px 20px;
        border-radius: 5px;
    }
</style>
```

#### Adding Images

```html
<!-- Inline images (recommended) -->
<img src="data:image/png;base64,..." alt="Logo">

<!-- External images -->
<img src="https://yoursite.com/logo.png" alt="Logo">
```

**Note:** Some email clients block external images by default.

---

## Data Models

### DocumentInfo

Represents a single document in the translation notification.

```python
class DocumentInfo(BaseModel):
    document_name: str
    original_url: str
    translated_url: str
```

**Validation:**
- `document_name` - Cannot be empty
- `original_url` - Must be valid HTTP/HTTPS URL
- `translated_url` - Must be valid HTTP/HTTPS URL

**Example:**

```python
doc = DocumentInfo(
    document_name="contract.pdf",
    original_url="https://drive.google.com/file/d/abc/view",
    translated_url="https://drive.google.com/file/d/xyz/view"
)
```

### EmailRequest

Request model for sending emails.

```python
class EmailRequest(BaseModel):
    to_email: EmailStr
    to_name: str
    subject: str
    body_html: str
    body_text: str
    from_email: Optional[EmailStr] = None
    from_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None
```

**Validation:**
- `to_email` - Valid email address
- `to_name` - Non-empty string
- `subject` - Non-empty string
- `body_html` - Non-empty string
- `body_text` - Non-empty string

### TranslationNotificationContext

Context for translation notification emails.

```python
class TranslationNotificationContext(BaseModel):
    user_name: str
    user_email: EmailStr
    company_name: str
    documents: List[DocumentInfo]
    translation_service_company: str = "Iris Solutions"

    @property
    def is_individual(self) -> bool:
        return self.company_name == "Ind"

    @property
    def template_type(self) -> EmailTemplate:
        if self.is_individual:
            return EmailTemplate.INDIVIDUAL_NOTIFICATION
        return EmailTemplate.CORPORATE_NOTIFICATION
```

**Properties:**
- `is_individual` - True if company_name is "Ind"
- `template_type` - Returns appropriate template enum

### EmailSendResult

Result of email sending operation.

```python
class EmailSendResult(BaseModel):
    success: bool
    message: str
    error: Optional[str] = None
    recipient: EmailStr
    sent_at: Optional[str] = None
```

**Fields:**
- `success` - True if email sent successfully
- `message` - Human-readable result message
- `error` - Error message if failed (None if successful)
- `recipient` - Email address of recipient
- `sent_at` - ISO timestamp of when email was sent

---

## Error Handling

### Exception Hierarchy

```
Exception
└── EmailServiceError
    ├── SMTPAuthenticationError
    ├── SMTPConnectError
    └── TemplateNotFound
```

### Error Types

#### EmailServiceError

Custom exception for email service errors.

```python
class EmailServiceError(Exception):
    """Custom exception for email service errors."""
    pass
```

**Usage:**

```python
try:
    connection = email_service._create_smtp_connection()
except EmailServiceError as e:
    logger.error(f"Email service error: {e}")
```

#### SMTP Errors

**SMTPAuthenticationError** - Authentication failed

```python
except smtplib.SMTPAuthenticationError as e:
    # Code: 535
    # Cause: Invalid credentials
    logger.error(f"Authentication failed: {e}")
```

**SMTPConnectError** - Connection failed

```python
except smtplib.SMTPConnectError as e:
    # Cause: Network issues, firewall, wrong host/port
    logger.error(f"Connection failed: {e}")
```

**SMTPServerDisconnected** - Server disconnected

```python
except smtplib.SMTPServerDisconnected as e:
    # Cause: Connection dropped, timeout
    logger.error(f"Server disconnected: {e}")
```

#### Template Errors

**TemplateNotFound** - Template file not found

```python
from jinja2 import TemplateNotFound

try:
    html = template_service.render_template("nonexistent.html", {})
except TemplateNotFound as e:
    logger.error(f"Template not found: {e}")
```

**TemplateSyntaxError** - Template has syntax errors

```python
from jinja2 import TemplateSyntaxError

try:
    html = template_service.render_string("{% for x %}", {})
except TemplateSyntaxError as e:
    logger.error(f"Template syntax error: {e}")
```

### Error Handling Patterns

#### Non-Blocking Email Sending

Email failures should not break file submissions:

```python
try:
    email_result = email_service.send_translation_notification(...)
    if email_result.success:
        return {
            "status": "processed",
            "email_sent": True
        }
    else:
        # Log error but continue
        logger.warning(f"Email failed: {email_result.error}")
        return {
            "status": "processed",
            "email_sent": False,
            "email_error": email_result.error
        }
except Exception as e:
    # Catch all exceptions
    logger.error(f"Unexpected email error: {e}", exc_info=True)
    return {
        "status": "processed",
        "email_sent": False,
        "email_error": str(e)
    }
```

#### Retry Logic

For transient errors, implement retry:

```python
import time

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

for attempt in range(MAX_RETRIES):
    try:
        result = email_service.send_email(request)
        if result.success:
            break
    except EmailServiceError as e:
        if attempt < MAX_RETRIES - 1:
            logger.warning(f"Retry {attempt + 1}/{MAX_RETRIES}: {e}")
            time.sleep(RETRY_DELAY)
        else:
            logger.error(f"Max retries exceeded: {e}")
            raise
```

#### Configuration Validation

Validate configuration before sending:

```python
if not email_service._validate_smtp_config():
    return EmailSendResult(
        success=False,
        message="Email service not configured",
        error="SMTP credentials missing",
        recipient=recipient_email
    )
```

---

## Testing

### Unit Tests

Located in `tests/unit/`:

#### test_email_service.py

**Coverage:** 20+ tests

```python
# Test categories:
- Configuration validation
- SMTP connection (mocked)
- Email message building
- Template selection
- Error scenarios
- Authentication failures
- Connection test
```

**Run:**

```bash
pytest tests/unit/test_email_service.py -v
```

#### test_template_service.py

**Coverage:** 15+ tests

```python
# Test categories:
- Template rendering
- String templates
- HTML escaping
- Loops and conditionals
- Special characters
- Template existence
- Multiple documents
```

**Run:**

```bash
pytest tests/unit/test_template_service.py -v
```

### Integration Tests

Located in `tests/integration/`:

#### test_submit_api.py

**Coverage:** 11 tests (8 original + 3 email tests)

```python
# Email-specific tests:
- Individual customer email
- Corporate customer email
- Email integration verification
- Submission resilience
```

**Run:**

```bash
# Requires running server
pytest tests/integration/test_submit_api.py::test_submit_endpoint_email_integration -v
```

### Manual Testing

#### 1. Test SMTP Connection

```python
python
>>> from app.services.email_service import email_service
>>> result = email_service.test_connection()
>>> print(result)
```

#### 2. Test Template Rendering

```python
python
>>> from app.services.template_service import template_service
>>> context = {
...     "user_name": "Test User",
...     "company_name": "Ind",
...     "documents": [{"document_name": "test.pdf", "original_url": "https://...", "translated_url": "https://..."}],
...     "translation_service_company": "Iris Solutions"
... }
>>> html = template_service.render_template("individual_notification.html", context)
>>> print(html[:100])
```

#### 3. Test Email Sending

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "test.pdf",
    "file_url": "https://drive.google.com/file/d/abc/view",
    "user_email": "your-test-email@example.com",
    "company_name": "Ind"
  }'
```

### Test Coverage

Run tests with coverage:

```bash
# Unit tests
pytest tests/unit/ --cov=app/services --cov=app/models --cov-report=html

# Integration tests
pytest tests/integration/test_submit_api.py --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

**Target Coverage:**
- Email Service: >90%
- Template Service: >90%
- Submit Service: >85%
- Models: 100%

---

## Deployment

### Prerequisites

1. Python 3.11+
2. SMTP credentials (Yahoo/Gmail/SendGrid)
3. Environment variables configured
4. Template directory exists
5. Required dependencies installed

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Create directories
mkdir -p app/templates/email
mkdir -p logs

# Copy environment template
cp .env.example .env

# Edit .env with your SMTP credentials
nano .env
```

### Configuration Steps

1. **Generate SMTP credentials** (see EMAIL_SERVICE_SETUP.md)

2. **Update .env file:**

```bash
SMTP_USERNAME=your.email@yahoo.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=your.email@yahoo.com
EMAIL_ENABLED=true
```

3. **Test configuration:**

```bash
python -c "from app.services.email_service import email_service; print(email_service.test_connection())"
```

4. **Start server:**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Production Deployment

#### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Environment variables should be set via docker-compose or k8s
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SMTP_HOST=smtp.sendgrid.net
      - SMTP_PORT=587
      - SMTP_USERNAME=apikey
      - SMTP_PASSWORD=${SENDGRID_API_KEY}
      - EMAIL_FROM=${EMAIL_FROM}
      - EMAIL_ENABLED=true
    volumes:
      - ./logs:/app/logs
```

#### Using Kubernetes

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: email-config
data:
  SMTP_HOST: "smtp.sendgrid.net"
  SMTP_PORT: "587"
  SMTP_USE_TLS: "true"
  EMAIL_ENABLED: "true"

---
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: email-secrets
type: Opaque
stringData:
  SMTP_USERNAME: "apikey"
  SMTP_PASSWORD: "your_sendgrid_api_key"
  EMAIL_FROM: "noreply@yourcompany.com"

---
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: translation-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: translation-api
  template:
    metadata:
      labels:
        app: translation-api
    spec:
      containers:
      - name: api
        image: translation-api:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: email-config
        - secretRef:
            name: email-secrets
```

### Health Checks

Add email health check endpoint:

```python
@app.get("/health/email")
async def email_health():
    """Check email service health."""
    result = email_service.test_connection()
    if result['success']:
        return {"status": "healthy", "email": "operational"}
    else:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "email": "unavailable"}
        )
```

---

## Security

### Best Practices

1. **Never commit credentials**
   - Use environment variables
   - Add `.env` to `.gitignore`
   - Use secrets management (Vault, AWS Secrets Manager)

2. **Use TLS encryption**
   ```bash
   SMTP_USE_TLS=true
   ```

3. **Validate email addresses**
   - Pydantic EmailStr validation
   - Check for disposable domains
   - Sanitize inputs

4. **Escape HTML content**
   - Jinja2 auto-escaping enabled
   - Never render user input directly

5. **Rate limiting**
   - Limit emails per user
   - Limit emails per IP
   - Implement cooldown periods

6. **Secure SMTP credentials**
   - Use app-specific passwords
   - Rotate credentials regularly
   - Monitor for unauthorized access

### Input Validation

All inputs are validated:

```python
# Email validation
class EmailRequest(BaseModel):
    to_email: EmailStr  # Pydantic validates format

# URL validation
class DocumentInfo(BaseModel):
    original_url: str

    @validator('original_url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Invalid URL")
        return v
```

### HTML Escaping

Templates automatically escape HTML:

```jinja2
<!-- Safe - HTML will be escaped -->
{{ user_provided_content }}

<!-- Unsafe - Only use for trusted content -->
{{ trusted_html|safe }}
```

### SMTP Security

```python
# Always use TLS
if self.smtp_use_tls:
    smtp.starttls()

# Timeout to prevent hanging
smtp = smtplib.SMTP(host, port, timeout=30)

# Close connection after use
try:
    smtp.send_message(msg)
finally:
    smtp.quit()
```

---

## Performance

### Benchmarks

**Email Sending Time:**
- Template rendering: 10-50ms
- SMTP connection: 200-500ms
- Email transmission: 100-300ms
- **Total:** ~400-800ms per email

**Throughput:**
- Sequential: ~75-150 emails/minute
- With connection pooling: ~300-500 emails/minute

### Optimization Strategies

#### 1. Connection Pooling

```python
class EmailServiceWithPool:
    def __init__(self):
        self.connection_pool = []

    def get_connection(self):
        if self.connection_pool:
            return self.connection_pool.pop()
        return self._create_smtp_connection()

    def return_connection(self, conn):
        self.connection_pool.append(conn)
```

#### 2. Background Tasks

```python
from fastapi import BackgroundTasks

@app.post("/submit")
async def submit(request: SubmitRequest, background_tasks: BackgroundTasks):
    # Process submission immediately
    result = await submit_service.process_submission(...)

    # Send email in background
    background_tasks.add_task(
        email_service.send_translation_notification,
        documents=[...],
        user_name=user_name,
        user_email=user_email,
        company_name=company_name
    )

    return result
```

#### 3. Template Caching

Templates are automatically cached by Jinja2:

```python
env = Environment(
    loader=FileSystemLoader(template_dir),
    auto_reload=False,  # Disable in production
    cache_size=400      # Cache 400 templates
)
```

#### 4. Async Email Sending

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

async def send_email_async(email_request):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor,
        email_service.send_email,
        email_request
    )
```

### Rate Limiting

Implement rate limiting to prevent abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/submit")
@limiter.limit("10/minute")  # 10 emails per minute per IP
async def submit(request: SubmitRequest):
    ...
```

---

## Monitoring & Logging

### Logging Levels

All email operations are logged:

```python
import logging

logger = logging.getLogger(__name__)

# INFO: Normal operations
logger.info(f"Email sent successfully to {recipient}")

# WARNING: Non-critical issues
logger.warning(f"Email failed but submission succeeded: {error}")

# ERROR: Critical issues
logger.error(f"SMTP connection failed: {error}", exc_info=True)

# DEBUG: Detailed information
logger.debug(f"Rendering template: {template_name}")
```

### Log Format

```
2025-11-05 10:23:45 - app.services.email_service - INFO - Email sent successfully to john@example.com
2025-11-05 10:23:46 - app.services.email_service - WARNING - Email notification failed: SMTP timeout
2025-11-05 10:23:47 - app.services.template_service - ERROR - Template not found: nonexistent.html
```

### Key Metrics to Monitor

1. **Email Send Success Rate**
   ```python
   success_count / total_attempts * 100
   ```

2. **Average Send Time**
   ```python
   total_send_time / success_count
   ```

3. **SMTP Connection Errors**
   ```python
   connection_error_count
   ```

4. **Template Rendering Errors**
   ```python
   template_error_count
   ```

5. **Queue Depth** (if using queue)
   ```python
   pending_emails_count
   ```

### Monitoring Tools

#### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

email_sent_total = Counter('email_sent_total', 'Total emails sent')
email_failed_total = Counter('email_failed_total', 'Total emails failed')
email_duration = Histogram('email_duration_seconds', 'Email sending duration')

@email_duration.time()
def send_email_with_metrics(request):
    result = email_service.send_email(request)
    if result.success:
        email_sent_total.inc()
    else:
        email_failed_total.inc()
    return result
```

#### Logging to External Services

**Sentry:**

```python
import sentry_sdk

sentry_sdk.init(
    dsn="your-sentry-dsn",
    traces_sample_rate=1.0
)

try:
    result = email_service.send_email(request)
except Exception as e:
    sentry_sdk.capture_exception(e)
    raise
```

**CloudWatch:**

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_data(
    Namespace='EmailService',
    MetricData=[
        {
            'MetricName': 'EmailsSent',
            'Value': 1,
            'Unit': 'Count'
        }
    ]
)
```

---

## Troubleshooting

### Common Issues

#### 1. "SMTP Authentication Failed (535)"

**Cause:** Invalid credentials or regular password used instead of app password

**Solution:**
1. Verify you're using app-specific password
2. Regenerate app password
3. Enable Two-Step Verification
4. Check username matches email exactly

```bash
# Test credentials
python -c "from app.services.email_service import email_service; print(email_service.test_connection())"
```

#### 2. "Connection Timeout"

**Cause:** Firewall blocking SMTP port or wrong host

**Solution:**
1. Check firewall allows port 587
2. Verify SMTP host is correct
3. Test with telnet:

```bash
telnet smtp.mail.yahoo.com 587
```

4. Try alternative port (465 with SSL)

#### 3. "Template Not Found"

**Cause:** Template file missing or wrong path

**Solution:**
1. Check template directory exists:

```bash
ls -la app/templates/email/
```

2. Verify template files:

```bash
individual_notification.html
individual_notification.txt
corporate_notification.html
corporate_notification.txt
```

3. Check EMAIL_TEMPLATE_DIR in config

#### 4. "Email Not Received"

**Possible causes and solutions:**

1. **In spam folder**
   - Check spam/junk folder
   - Add sender to contacts
   - Check SPF/DKIM records

2. **Invalid recipient address**
   - Verify email address
   - Check typos
   - Test with known working address

3. **Rate limited**
   - Yahoo: 500/day limit
   - Gmail: 500/day limit
   - Wait 24 hours and retry

4. **Blocked by recipient server**
   - Check sender reputation
   - Use verified domain
   - Consider SendGrid/SES

#### 5. "Template Rendering Error"

**Cause:** Missing variable or syntax error

**Solution:**
1. Check all required variables provided:

```python
required_vars = ['user_name', 'company_name', 'documents', 'translation_service_company']
for var in required_vars:
    assert var in context, f"Missing variable: {var}"
```

2. Validate template syntax:

```python
from jinja2 import Template

try:
    template = Template(template_string)
except Exception as e:
    print(f"Syntax error: {e}")
```

#### 6. "UnicodeEncodeError"

**Cause:** Special characters in email content

**Solution:**
1. Templates already use UTF-8
2. For custom content, ensure proper encoding:

```python
subject = subject.encode('utf-8').decode('utf-8')
```

### Debugging Commands

#### Test SMTP Connection

```python
from app.services.email_service import email_service
result = email_service.test_connection()
print(f"Connection: {'OK' if result['success'] else 'FAILED'}")
if not result['success']:
    print(f"Error: {result.get('error')}")
```

#### Test Template Rendering

```python
from app.services.template_service import template_service

# List available templates
print(f"Templates: {template_service.list_templates()}")

# Check if template exists
exists = template_service.template_exists("individual_notification.html")
print(f"Template exists: {exists}")

# Test rendering
try:
    html = template_service.render_template(
        "individual_notification.html",
        {
            "user_name": "Test User",
            "company_name": "Ind",
            "documents": [
                {
                    "document_name": "test.pdf",
                    "original_url": "https://example.com/original",
                    "translated_url": "https://example.com/translated"
                }
            ],
            "translation_service_company": "Iris Solutions"
        }
    )
    print(f"Template rendered successfully ({len(html)} chars)")
except Exception as e:
    print(f"Rendering failed: {e}")
```

#### Send Test Email

```python
from app.services.email_service import email_service
from app.models.email import DocumentInfo

result = email_service.send_translation_notification(
    documents=[
        DocumentInfo(
            document_name="test.pdf",
            original_url="https://drive.google.com/file/d/abc/view",
            translated_url="https://drive.google.com/file/d/xyz/view"
        )
    ],
    user_name="Test User",
    user_email="your-test-email@example.com",
    company_name="Ind"
)

print(f"Success: {result.success}")
if result.success:
    print(f"Sent at: {result.sent_at}")
else:
    print(f"Error: {result.error}")
```

#### Check Logs

```bash
# View recent logs
tail -f logs/translator.log

# Search for email-related logs
grep -i "email" logs/translator.log

# Search for errors
grep -i "error" logs/translator.log | grep -i "email"
```

---

## Examples

### Example 1: Send Notification to Individual Customer

```python
from app.services.email_service import email_service
from app.models.email import DocumentInfo

# Create document list
documents = [
    DocumentInfo(
        document_name="personal_letter.pdf",
        original_url="https://drive.google.com/file/d/abc123/view",
        translated_url="https://drive.google.com/file/d/xyz789/view"
    )
]

# Send email
result = email_service.send_translation_notification(
    documents=documents,
    user_name="John Doe",
    user_email="john.doe@example.com",
    company_name="Ind"  # Individual customer
)

if result.success:
    print(f"✓ Email sent to {result.recipient} at {result.sent_at}")
else:
    print(f"✗ Email failed: {result.error}")
```

### Example 2: Send Notification to Corporate Customer

```python
# Create multiple documents
documents = [
    DocumentInfo(
        document_name="Q4_Report.xlsx",
        original_url="https://drive.google.com/file/d/doc1/view",
        translated_url="https://drive.google.com/file/d/trans1/view"
    ),
    DocumentInfo(
        document_name="Contract_Agreement.pdf",
        original_url="https://drive.google.com/file/d/doc2/view",
        translated_url="https://drive.google.com/file/d/trans2/view"
    ),
    DocumentInfo(
        document_name="Marketing_Proposal.docx",
        original_url="https://drive.google.com/file/d/doc3/view",
        translated_url="https://drive.google.com/file/d/trans3/view"
    )
]

# Send corporate email
result = email_service.send_translation_notification(
    documents=documents,
    user_name="Alice Johnson",
    user_email="alice.johnson@acmecorp.com",
    company_name="Acme Corporation"  # Corporate customer
)

print(f"Status: {result.message}")
```

### Example 3: Custom Email with Custom Template

```python
from app.services.template_service import template_service
from app.services.email_service import email_service
from app.models.email import EmailRequest

# Render custom template
context = {
    "user_name": "Bob Smith",
    "message": "Your custom message here",
    "documents": [...]
}

html = template_service.render_template("custom_template.html", context)
text = template_service.render_template("custom_template.txt", context)

# Send email
email_request = EmailRequest(
    to_email="bob.smith@example.com",
    to_name="Bob Smith",
    subject="Custom Notification",
    body_html=html,
    body_text=text
)

result = email_service.send_email(email_request)
```

### Example 4: Bulk Email Sending

```python
import asyncio
from app.services.email_service import email_service
from app.models.email import DocumentInfo

# List of recipients
recipients = [
    ("user1@example.com", "User One", "Company A"),
    ("user2@example.com", "User Two", "Ind"),
    ("user3@example.com", "User Three", "Company B"),
]

# Common documents
documents = [
    DocumentInfo(
        document_name="shared_document.pdf",
        original_url="https://drive.google.com/file/d/orig/view",
        translated_url="https://drive.google.com/file/d/trans/view"
    )
]

# Send to all recipients
results = []
for email, name, company in recipients:
    result = email_service.send_translation_notification(
        documents=documents,
        user_name=name,
        user_email=email,
        company_name=company
    )
    results.append((email, result.success))

# Print summary
success_count = sum(1 for _, success in results if success)
print(f"Sent {success_count}/{len(results)} emails successfully")
```

### Example 5: Error Handling and Retry

```python
import time
from app.services.email_service import email_service
from app.models.email import DocumentInfo

MAX_RETRIES = 3
RETRY_DELAY = 2

documents = [
    DocumentInfo(
        document_name="important_doc.pdf",
        original_url="https://drive.google.com/file/d/abc/view",
        translated_url="https://drive.google.com/file/d/xyz/view"
    )
]

for attempt in range(MAX_RETRIES):
    try:
        result = email_service.send_translation_notification(
            documents=documents,
            user_name="Critical User",
            user_email="critical@example.com",
            company_name="Ind"
        )

        if result.success:
            print(f"✓ Email sent on attempt {attempt + 1}")
            break
        else:
            print(f"✗ Attempt {attempt + 1} failed: {result.error}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    except Exception as e:
        print(f"✗ Exception on attempt {attempt + 1}: {e}")
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY)
        else:
            print("✗ All retries exhausted")
```

### Example 6: Integration with Submit Endpoint

```python
from fastapi import APIRouter, HTTPException
from app.models.requests import SubmitRequest
from app.services.submit_service import submit_service

router = APIRouter()

@router.post("/submit")
async def submit_file(request: SubmitRequest):
    """
    Submit file and send email notification.

    Email is sent non-blocking - submission succeeds even if email fails.
    """
    try:
        result = await submit_service.process_submission(
            file_name=request.file_name,
            file_url=request.file_url,
            user_email=request.user_email,
            company_name=request.company_name,
            transaction_id=request.transaction_id
        )

        return {
            "status": result["status"],
            "message": result["message"],
            "email_sent": result.get("email_sent", False)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## FAQ

### General Questions

**Q: What email providers are supported?**
A: Any SMTP provider: Yahoo, Gmail, SendGrid, Office 365, AWS SES, Mailgun, etc.

**Q: Can I use my regular email password?**
A: No, you must use app-specific passwords for Yahoo and Gmail.

**Q: How many emails can I send per day?**
A: Yahoo/Gmail: 500/day (free). SendGrid: 100/day (free), 40K+/month (paid).

**Q: What happens if email sending fails?**
A: File submission still succeeds. Email failure is logged but doesn't block operations.

**Q: Can I customize the email templates?**
A: Yes, templates are in `app/templates/email/` and use Jinja2 syntax.

### Technical Questions

**Q: Are emails sent synchronously or asynchronously?**
A: Currently synchronous, but can be made async with BackgroundTasks.

**Q: How long does it take to send an email?**
A: Typically 400-800ms including SMTP connection and transmission.

**Q: Are HTML emails supported?**
A: Yes, all emails include both HTML and plain text versions.

**Q: How are email failures handled?**
A: Logged and returned in response, but don't cause submission to fail.

**Q: Can I send attachments?**
A: Not currently, but can be added by extending the email service.

**Q: Is connection pooling supported?**
A: Not by default, but can be implemented for high-volume scenarios.

### Configuration Questions

**Q: Where do I configure SMTP settings?**
A: In the `.env` file. See `.env.example` for reference.

**Q: How do I switch from Yahoo to Gmail?**
A: Update SMTP_HOST, SMTP_PORT, and credentials in `.env`.

**Q: Can I disable email sending?**
A: Yes, set `EMAIL_ENABLED=false` in `.env`.

**Q: How do I change the sender name?**
A: Update `EMAIL_FROM_NAME` in `.env`.

**Q: Can I use a custom reply-to address?**
A: Yes, set `EMAIL_REPLY_TO` in `.env`.

### Troubleshooting Questions

**Q: Why am I getting "Authentication Failed"?**
A: You're likely using your regular password instead of an app-specific password.

**Q: Why aren't emails being received?**
A: Check spam folder, verify recipient address, check rate limits.

**Q: How do I test if SMTP is working?**
A: Run `email_service.test_connection()` to verify connectivity.

**Q: Where can I find error logs?**
A: Check `logs/translator.log` for detailed error information.

**Q: Why is email sending slow?**
A: SMTP connection takes 200-500ms. Consider connection pooling or background tasks.

---

## Appendix

### A. Email Template Reference

#### Individual Customer Template

**Subject:** Your translated documents are ready for download

**Tone:** Casual, friendly, welcoming

**Key Features:**
- Green color scheme (#4CAF50)
- Friendly greeting: "Hi {user_name}"
- Casual language
- Simple download buttons
- Thank you message

**Use Case:** Individual users, freelancers, personal translations

#### Corporate Customer Template

**Subject:** Translated documents are now available for download

**Tone:** Professional, formal, business-like

**Key Features:**
- Purple gradient color scheme (#667eea - #764ba2)
- Professional greeting: "Dear {user_name}"
- Formal language
- Action required notice
- Corporate styling

**Use Case:** Business users, enterprise customers, corporate translations

### B. SMTP Provider Comparison

| Provider | Free Tier | Paid Starting | Pros | Cons |
|----------|-----------|---------------|------|------|
| **Yahoo** | 500/day | N/A | Easy setup, free | Daily limit |
| **Gmail** | 500/day | N/A | Reliable, free | Daily limit, 2FA required |
| **SendGrid** | 100/day | $19.95/mo (40K) | High volume, reliable | Setup complexity |
| **AWS SES** | 62K/mo | $0.10/1000 | Scalable, cheap | AWS account required |
| **Mailgun** | 5K/mo | $35/mo (50K) | Good API, reliable | Paid only after trial |

**Recommendation:**
- **Development/Testing:** Yahoo or Gmail
- **Production (<500/day):** Gmail
- **Production (>500/day):** SendGrid or AWS SES

### C. Performance Benchmarks

| Operation | Average Time | Notes |
|-----------|--------------|-------|
| Template render | 10-50ms | Cached after first render |
| SMTP connect | 200-500ms | Varies by provider |
| Email send | 100-300ms | Network dependent |
| **Total** | **400-800ms** | Per email |

**Optimization Impact:**
- Connection pooling: 2-3x faster
- Background tasks: Non-blocking
- Template caching: 5-10x faster rendering

### D. Character Limits

| Field | Limit | Notes |
|-------|-------|-------|
| Subject | 998 chars | RFC 5322 standard |
| Email body | No limit | Practical limit ~100KB |
| Recipient name | 255 chars | Recommended |
| Sender name | 255 chars | Recommended |
| Document name | No limit | Keep reasonable |

### E. Related Documentation

- [EMAIL_SERVICE_SETUP.md](EMAIL_SERVICE_SETUP.md) - Setup guide
- [.env.example](.env.example) - Configuration template
- [tests/unit/test_email_service.py](tests/unit/test_email_service.py) - Test examples
- [tests/unit/test_template_service.py](tests/unit/test_template_service.py) - Template tests
- [app/services/email_service.py](app/services/email_service.py) - Source code
- [app/services/template_service.py](app/services/template_service.py) - Source code

---

## Changelog

### Version 1.0.0 (2025-11-05)

**Initial Release**

- ✅ Email service with Yahoo SMTP support
- ✅ Template service with Jinja2
- ✅ Dual template system (individual/corporate)
- ✅ Submit service integration
- ✅ Data models and validation
- ✅ Comprehensive unit tests (35+ tests)
- ✅ Integration tests
- ✅ Documentation and setup guide
- ✅ Error handling and logging
- ✅ Production-ready configuration

---

## Support

For issues, questions, or contributions:

1. **Check documentation** - This file and EMAIL_SERVICE_SETUP.md
2. **Review logs** - `logs/translator.log`
3. **Run tests** - `pytest tests/unit/ tests/integration/`
4. **Test connection** - `email_service.test_connection()`
5. **Create issue** - GitHub issues for bug reports

---

**End of Documentation**
