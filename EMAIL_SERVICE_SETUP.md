# Email Service Setup Guide

This guide explains how to configure and test the email service for translation notifications.

## Overview

The email service sends translation notification emails to users when their documents are ready. It supports two types of templates:
- **Individual Customer Template** (company_name = "Ind")
- **Corporate Customer Template** (company_name != "Ind")

## Yahoo SMTP Configuration

### Step 1: Generate App-Specific Password

Yahoo requires app-specific passwords for SMTP authentication:

1. Go to Yahoo Account Security: https://login.yahoo.com/account/security
2. Enable **Two-Step Verification** (if not already enabled)
3. Navigate to "Generate app password"
4. Select "Other App" and give it a name (e.g., "Translation Server")
5. Copy the generated 16-character password
6. **IMPORTANT**: Save this password securely - you can't view it again

### Step 2: Configure Environment Variables

Add these variables to your `.env` file:

```bash
# Email Configuration (Yahoo SMTP)
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USERNAME=your.email@yahoo.com
SMTP_PASSWORD=your_app_specific_password_here
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT=30
EMAIL_FROM=your.email@yahoo.com
EMAIL_FROM_NAME=Iris Solutions Translation Services
EMAIL_REPLY_TO=your.email@yahoo.com  # Optional
EMAIL_ENABLED=true
TRANSLATION_SERVICE_COMPANY=Iris Solutions
```

### Step 3: Verify Configuration

Test the SMTP connection:

```python
from app.services.email_service import email_service

# Test connection
result = email_service.test_connection()
print(result)
```

Expected output if successful:
```json
{
    "success": true,
    "message": "SMTP connection successful",
    "details": {
        "host": "smtp.mail.yahoo.com",
        "port": 587,
        "username": "your.email@yahoo.com",
        "tls": true,
        "ssl": false
    }
}
```

## Testing Email Functionality

### 1. Unit Tests (Mocked SMTP)

Run unit tests with mocked SMTP connections:

```bash
pytest tests/unit/test_email_service.py -v
pytest tests/unit/test_template_service.py -v
```

These tests verify email logic without actually sending emails.

### 2. Integration Tests

Run integration tests with the server running:

```bash
# Start the server in one terminal
uvicorn app.main:app --reload --port 8000

# Run integration tests in another terminal
pytest tests/integration/test_submit_api.py -v
```

### 3. Manual Test with cURL

Test the `/submit` endpoint with real email sending:

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "test_document.pdf",
    "file_url": "https://drive.google.com/file/d/test123/view",
    "user_email": "recipient@example.com",
    "company_name": "Ind",
    "transaction_id": "txn_test_001"
  }'
```

### 4. Test Individual Customer Email

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "personal_document.docx",
    "file_url": "https://drive.google.com/file/d/abc123/view",
    "user_email": "john.doe@example.com",
    "company_name": "Ind"
  }'
```

Expected email:
- Subject: "Your translated documents are ready for download"
- Friendly, informal tone
- Green color scheme

### 5. Test Corporate Customer Email

```bash
curl -X POST http://localhost:8000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "file_name": "corporate_report.xlsx",
    "file_url": "https://drive.google.com/file/d/xyz789/view",
    "user_email": "alice.johnson@company.com",
    "company_name": "Acme Corporation"
  }'
```

Expected email:
- Subject: "Translated documents are now available for download"
- Professional, formal tone
- Purple gradient color scheme

## Email Templates

Templates are located in `app/templates/email/`:

- `individual_notification.html` - HTML version for individual customers
- `individual_notification.txt` - Plain text version for individual customers
- `corporate_notification.html` - HTML version for corporate customers
- `corporate_notification.txt` - Plain text version for corporate customers

### Customizing Templates

Templates use Jinja2 syntax. Available variables:

```python
{
    "user_name": "John Doe",
    "company_name": "Ind" or "Company Name",
    "documents": [
        {
            "document_name": "file.pdf",
            "original_url": "https://...",
            "translated_url": "https://..."
        }
    ],
    "translation_service_company": "Iris Solutions"
}
```

Example template snippet:
```jinja2
<p>Hi {{ user_name }},</p>

{% for document in documents %}
<div>
    <strong>{{ document.document_name }}</strong>
    <a href="{{ document.translated_url }}">Download</a>
</div>
{% endfor %}
```

## Troubleshooting

### SMTP Authentication Failed

**Error**: `SMTPAuthenticationError: (535, 'Authentication failed')`

**Solutions**:
1. Verify you're using an **app-specific password**, not your regular Yahoo password
2. Ensure Two-Step Verification is enabled on your Yahoo account
3. Check that `SMTP_USERNAME` matches your Yahoo email exactly
4. Regenerate the app-specific password if needed

### Connection Timeout

**Error**: `TimeoutError` or `SMTPConnectError`

**Solutions**:
1. Check your internet connection
2. Verify firewall isn't blocking port 587
3. Try increasing `SMTP_TIMEOUT` in configuration
4. Ensure Yahoo SMTP servers are accessible: `telnet smtp.mail.yahoo.com 587`

### Email Not Received

**Possible causes**:
1. Check spam/junk folder
2. Verify recipient email address is correct
3. Check Yahoo's sending limits (500 emails/day for free accounts)
4. Review server logs for email sending errors

### Template Not Found

**Error**: `TemplateNotFound: Template 'xxx.html' not found`

**Solutions**:
1. Verify template files exist in `app/templates/email/`
2. Check file permissions
3. Ensure `EMAIL_TEMPLATE_DIR` in config is correct
4. Restart the server after adding new templates

## Alternative SMTP Providers

### Gmail SMTP

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=your_app_password  # Generate at https://myaccount.google.com/apppasswords
```

### SendGrid SMTP

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=your_sendgrid_api_key
```

### Office 365 SMTP

```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USERNAME=your.email@company.com
SMTP_PASSWORD=your_password
```

## Production Considerations

### Rate Limiting

- **Yahoo Free**: 500 emails/day
- **Gmail Free**: 500 emails/day (100 external)
- **SendGrid Free**: 100 emails/day
- **SendGrid Paid**: Starting at 40,000 emails/month

### Email Queue

For high-volume production use, consider implementing an email queue:

```python
from fastapi import BackgroundTasks

@app.post("/submit")
async def submit_file(request: SubmitRequest, background_tasks: BackgroundTasks):
    # Process submission immediately
    result = await submit_service.process_submission(...)

    # Send email in background (non-blocking)
    background_tasks.add_task(
        email_service.send_translation_notification,
        documents=[...],
        user_name=user_name,
        user_email=user_email,
        company_name=company_name
    )

    return result
```

### Monitoring

Monitor email sending with logging:

```python
import logging

logger = logging.getLogger(__name__)

# All email operations are automatically logged
# Check logs for:
# - Email sent successfully
# - Email failed: <error message>
# - SMTP connection errors
```

### Security Best Practices

1. **Never commit SMTP credentials** to version control
2. Use environment variables or secure secrets management
3. Enable TLS for SMTP connections
4. Rotate app-specific passwords regularly
5. Monitor for unauthorized email sending
6. Validate all email addresses before sending
7. Sanitize template inputs to prevent injection

## API Reference

### EmailService.send_translation_notification()

```python
result = email_service.send_translation_notification(
    documents=[
        DocumentInfo(
            document_name="file.pdf",
            original_url="https://...",
            translated_url="https://..."
        )
    ],
    user_name="John Doe",
    user_email="john@example.com",
    company_name="Ind"  # or "Company Name"
)

# Returns EmailSendResult:
# {
#     "success": bool,
#     "message": str,
#     "error": str | None,
#     "recipient": str,
#     "sent_at": str | None
# }
```

### SubmitService.process_submission()

```python
result = await submit_service.process_submission(
    file_name="document.pdf",
    file_url="https://drive.google.com/...",
    user_email="user@example.com",
    company_name="Ind",
    transaction_id="txn_123"  # Optional
)

# Returns:
# {
#     "status": "processed",
#     "message": "File submission received...",
#     "email_sent": bool,
#     "email_error": str | None  # If email failed
# }
```

## Support

For issues or questions:
1. Check logs: `tail -f logs/translator.log`
2. Review this documentation
3. Test SMTP connection with `email_service.test_connection()`
4. Verify environment variables are loaded correctly
5. Contact system administrator for production issues
