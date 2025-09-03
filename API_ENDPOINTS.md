# Translation Service API Specification

## Overview

This document defines the REST API endpoints required to support the professional document translation service frontend. The system follows a simplified no-authentication flow: Upload → Email → Languages → Payment → Translation.

## Base Configuration

```
Base URL: http://localhost:3001/api
Content-Type: application/json (except for file uploads)
```

## API Response Format

All endpoints should return responses in this standard format:

```typescript
{
  "success": boolean,
  "data": T | null,    // Type-specific response data
  "error": {           // Only present when success: false
    "code": string,
    "message": string
  }
}
```

## Endpoints

### 1. GET /api/languages
**Purpose:** Retrieve available languages for translation

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "code": "en",
      "name": "English",
      "nativeName": "English",
      "isPopular": true
    },
    {
      "code": "es",
      "name": "Spanish",
      "nativeName": "Español",
      "isPopular": true
    }
    // ... more languages
  ]
}
```

**Requirements:**
- Return at least 20 common languages
- Include `isPopular` flag for top 10 most-used languages
- Languages should include: English, Spanish, French, German, Italian, Portuguese, Russian, Chinese, Japanese, Korean, Arabic, Hindi, Dutch, Polish, Turkish

---

### 2. POST /api/upload
**Purpose:** Upload files for translation

**Request:**
- Content-Type: `multipart/form-data`
- Field name: `files` (multiple files allowed)

**Supported File Types:**
- PDF (.pdf)
- Word (.doc, .docx)
- JPEG (.jpeg, .jpg)
- PNG (.png)
- TIFF (.tiff, .tif)

**File Validation:**
- Maximum file size: 100MB for documents, 50MB for images
- Validate file signatures (magic numbers) for security
- Reject executables and potentially malicious files

**Response:**
```json
{
  "success": true,
  "data": [
    "file_id_1",
    "file_id_2"
  ]
}
```

**Error Handling:**
- 413: File too large
- 415: Unsupported file type
- 400: Invalid file format or corrupted file

---

### 3. POST /api/translate
**Purpose:** Initiate translation process after payment

**Request:**
```json
{
  "files": [
    {
      "id": "unique_file_id",
      "name": "document.pdf",
      "size": 1048576,
      "type": "application/pdf"
    }
  ],
  "sourceLanguage": "en",
  "targetLanguage": "es",
  "email": "user@example.com",
  "paymentIntentId": "pi_1234567890" // Optional, for payment verification
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "trans_1234567890",
    "status": "pending",
    "progress": 0,
    "message": "Translation queued"
  }
}
```

**Email Validation:**
- Validate email format
- Check for disposable email addresses (optional)
- Sanitize email input to prevent injection attacks

---


**Status Values:**
- `pending`: Translation queued
- `processing`: Translation in progress
- `completed`: Translation finished, download available
- `failed`: Translation failed, error message in `message`

---

### 5. POST /api/payment/create-intent
**Purpose:** Create payment intent for Stripe integration

**Request:**
```json
{
  "amount": 1000,        // Amount in cents (minimum 50)
  "currency": "usd",
  "metadata": {
    "timestamp": "1234567890",
    "userAgent": "Mozilla/5.0..."
  },
  "description": "Translation Service Payment",
  "receipt_email": "user@example.com"
}
```

**Headers:**
- `X-CSRF-Token`: Optional CSRF protection token
- `Idempotency-Key`: Optional key to prevent duplicate charges

**Response:**
```json
{
  "success": true,
  "data": {
    "clientSecret": "pi_1234_secret_5678",
    "paymentIntentId": "pi_1234567890"
  }
}
```

**Validation:**
- Amount must be between 50 cents ($0.50) and $10,000
- Currency must be valid ISO code
- Implement rate limiting to prevent abuse

---

### 6. GET /api/payment/:paymentIntentId/verify
**Purpose:** Verify payment completion (optional webhook alternative)

**Response:**
```json
{
  "success": true,
  "data": {
    "verified": true,
    "status": "succeeded",
    "amount": 1000
  }
}
```

---

## Error Response Codes

Implement consistent HTTP status codes:

- **400** Bad Request - Invalid input data
- **404** Not Found - Resource doesn't exist
- **413** Payload Too Large - File size exceeds limit
- **415** Unsupported Media Type - Invalid file type
- **422** Unprocessable Entity - Valid format but semantic errors
- **429** Too Many Requests - Rate limit exceeded
- **500** Internal Server Error - Server-side error
- **502/503/504** Service Unavailable - Temporary outage

## Security Requirements

1. **Input Validation**
   - Sanitize all user inputs
   - Validate file types by magic numbers, not just extensions
   - Implement file size limits
   - Email validation with XSS prevention

2. **Rate Limiting**
   - Implement per-IP rate limiting
   - Special limits for file uploads (e.g., 10 files per minute)
   - Payment endpoint protection (e.g., 5 attempts per minute)

3. **CORS Configuration**
   - Configure appropriate CORS headers
   - Whitelist frontend domain

4. **File Security**
   - Scan uploaded files for malware (optional)
   - Store files in secure location with unique IDs
   - Implement automatic cleanup of old files

## Pricing Calculation

The frontend expects these pricing parameters:
- Base price: $10.00
- Per file charge: $2.00
- Size charge: $5.00 per MB (for total size over 5MB)
- Minimum charge: $10.00

## Implementation Notes

1. **No Authentication Required**: This API operates without user accounts or JWT tokens
2. **Session Management**: Use session storage or temporary tokens for tracking translation jobs
3. **File Processing**: Implement background job processing for translations
4. **Email Notifications**: Send confirmation and completion emails to users
5. **Payment Integration**: Implement Stripe webhook handling for payment confirmation
6. **Mock Mode**: Consider implementing a mock mode for development/testing

## Development Quick Start

```bash
# Example Express.js setup
npm init -y
npm install express cors multer stripe body-parser helmet rate-limiter-flexible

# Required environment variables
STRIPE_SECRET_KEY=sk_test_...
PAYPAL_CLIENT_SECRET=...
EMAIL_SERVICE_API_KEY=...
FRONTEND_URL=http://localhost:3000
```

## Testing Checklist

- [ ] File upload with various formats and sizes
- [ ] Email validation and sanitization
- [ ] Language endpoint returns expected data
- [ ] Payment flow with test card numbers
- [ ] Translation status polling
- [ ] Error handling for all edge cases
- [ ] Rate limiting functionality
- [ ] CORS configuration
- [ ] File cleanup after processing