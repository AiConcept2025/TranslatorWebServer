# Translation Web Server API Reference

A comprehensive API reference for the Translation Web Server - a simplified 3-step workflow for file translation with payment processing.

## Overview

The Translation Web Server provides a streamlined workflow:
1. **Upload files** → Files stored in temporary folder with pricing calculation
2. **Process payment** → Handle payment with customer email
3. **Payment confirmation** → Files automatically moved to customer inbox

---

## 📤 File Upload & Translation

### POST `/translate`

Upload files for translation and receive pricing information.

#### Parameters

**Request Body** (JSON):
```json
{
  "files": [
    {
      "id": "string",
      "name": "string", 
      "size": number,
      "type": "string"
    }
  ],
  "sourceLanguage": "string",
  "targetLanguage": "string",
  "email": "string",
  "paymentIntentId": "string (optional)"
}
```

#### Return Values

**Success Response (200)**:
```json
{
  "success": true,
  "data": {
    "pricing": {
      "total_pages": number,
      "price_per_page": 0.10,
      "total_amount": number,
      "currency": "USD"
    },
    "files": {
      "total_files": number,
      "successful_uploads": number,
      "failed_uploads": number
    },
    "customer": {
      "email": "string",
      "source_language": "string",
      "target_language": "string"
    },
    "payment": {
      "required": true,
      "amount_cents": number,
      "customer_email": "string"
    }
  }
}
```

#### Errors

- **400 Bad Request**: Invalid email format, disposable email domains, invalid language codes, same source/target languages
- **422 Unprocessable Entity**: File validation errors (no files, too many files >10)
- **500 Internal Server Error**: Google Drive folder creation failed, file upload errors

---

## 🌐 Languages

### GET `/api/v1/languages`

Retrieve list of supported languages for translation.

#### Parameters

**Query Parameters**: None

#### Return Values

**Success Response (200)**:
```json
{
  "success": true,
  "data": {
    "languages": [
      {
        "code": "string",
        "name": "string",
        "native_name": "string"
      }
    ],
    "total_count": number
  }
}
```

#### Errors

- **500 Internal Server Error**: Language service unavailable

---

## 🔐 Authentication

### POST `/login/corporate`

Authenticate corporate users and receive an authentication token.

#### Request Body

**All Fields (camelCase recommended):**
```json
{
  "companyName": "Acme Corp",
  "password": "securepass123",
  "userFullName": "John Doe",
  "userEmail": "john.doe@acme.com",
  "loginDateTime": "2025-10-10T12:34:56.789Z"
}
```

**Field Requirements:**
- `companyName` (string, required): Company name, minimum 1 character
- `password` (string, required): User password, minimum 6 characters
- `userFullName` (string, required): User's full name, minimum 1 character
- `userEmail` (string, required): Valid email address
- `loginDateTime` (string, required): Login timestamp in ISO 8601 format

**Note:** The endpoint accepts both camelCase (recommended) and snake_case field names.

#### Response

**Success (200):**
```json
{
  "success": true,
  "message": "Corporate login successful",
  "data": {
    "authToken": "d4e5f6a7b8c9...authentication_token_hash",
    "tokenType": "Bearer",
    "expiresIn": 86400,
    "expiresAt": "2025-10-11T12:34:56.789Z",
    "user": {
      "fullName": "John Doe",
      "email": "john.doe@acme.com",
      "company": "Acme Corp"
    },
    "loginDateTime": "2025-10-10T12:34:56.789Z"
  }
}
```

**Response Fields:**
- `authToken`: SHA256 authentication token (64 characters hex)
- `tokenType`: Always "Bearer"
- `expiresIn`: Token lifetime in seconds (86400 = 24 hours)
- `expiresAt`: ISO 8601 timestamp when token expires
- `user`: User information echoed from request
- `loginDateTime`: Login timestamp echoed from request

#### Errors

- **400 Bad Request**: Invalid request format or malformed JSON
- **422 Unprocessable Entity**: Validation errors (missing fields, invalid email, password too short)
- **500 Internal Server Error**: Token generation or processing failed

**Error Response Example:**
```json
{
  "success": false,
  "error": {
    "code": 422,
    "message": "Field required",
    "type": "validation_error"
  }
}
```

#### Authentication Token

The authentication token is generated using:
- User email
- Company name
- Login timestamp
- Secure random bytes (URL-safe)
- SHA256 hashing

Token characteristics:
- **Length**: 64 hexadecimal characters
- **Lifetime**: 24 hours from generation
- **Type**: Bearer token (use in Authorization header)
- **Usage**: `Authorization: Bearer {authToken}`

#### Usage Example

```bash
# Login request
curl -X POST http://localhost:8000/login/corporate \
  -H "Content-Type: application/json" \
  -d '{
    "companyName": "Acme Corp",
    "password": "securepass123",
    "userFullName": "John Doe",
    "userEmail": "john.doe@acme.com",
    "loginDateTime": "2025-10-10T12:34:56.789Z"
  }'

# Use token in subsequent requests
curl -X GET http://localhost:8000/api/v1/languages \
  -H "Authorization: Bearer d4e5f6a7b8c9..."
```

---

## 💳 Payment Success Webhook

### POST `/api/payment/success`

Confirms payment and moves customer files from Temp to Inbox folder.

#### Request Body

**Required:**
- `paymentIntentId` (string): Payment transaction ID
- Customer email (string): Can be provided in two ways:
  - At root level: `customerEmail` or `customer_email`
  - Inside `metadata.customer_email`

**All Fields:**
```json
{
  "paymentIntentId": "payment_sq_1760060540428_wq00qen6d",
  "amount": 0.1,
  "currency": "USD",
  "paymentMethod": "square",
  "metadata": {
    "status": "COMPLETED",
    "cardBrand": "VISA",
    "last4": "5220",
    "receiptNumber": "PAYMENT_SQ_1760060540428_WQ00QEN6D",
    "created": "2025-10-10T01:42:20.429Z",
    "simulated": true,
    "customer_email": "user@example.com"
  },
  "timestamp": "2025-10-10T01:42:20.430Z"
}
```

**Minimal Example:**
```json
{
  "paymentIntentId": "payment_sq_1234567890",
  "metadata": {
    "customer_email": "user@example.com"
  }
}
```

#### Response

**Success (200):**
```json
{
  "success": true,
  "message": "Payment confirmed. 3 files moved to Inbox.",
  "data": {
    "customer_email": "user@example.com",
    "payment_intent_id": "payment_sq_1234567890",
    "total_files": 3,
    "moved_successfully": 3,
    "inbox_folder_id": "google_drive_folder_id"
  }
}
```

**No Files (200):**
```json
{
  "success": true,
  "message": "Payment confirmed but no pending files found",
  "data": {
    "customer_email": "user@example.com",
    "payment_intent_id": "payment_sq_1234567890",
    "files_moved": 0
  }
}
```

#### Errors

- **422** - Invalid email format or missing required fields
- **500** - Server error during file operations

---

## ❌ Payment Failure

### POST `/api/payment/failure`

Handle payment failure and clean up temporary files.

#### Parameters

**Query Parameters**:
- `customer_email` (required): Customer email address
- `payment_intent_id` (required): Payment intent ID

#### Return Values

**Success Response (200)**:
```json
{
  "success": true,
  "message": "Payment failed. N files deleted from Temp folder.",
  "data": {
    "customer_email": "string",
    "payment_intent_id": "string",
    "total_files": number,
    "deleted_successfully": number,
    "workflow": "simplified_no_sessions"
  }
}
```

#### Errors

- **500 Internal Server Error**: File cleanup failed

---

## ❤️ Health Check

### GET `/health`

Check application health status and service availability.

#### Parameters

**Query Parameters**: None

#### Return Values

**Healthy Response (200)**:
```json
{
  "status": "healthy",
  "timestamp": number,
  "services": {
    "google_drive": "available",
    "translation": "available"
  }
}
```

**Unhealthy Response (503)**:
```json
{
  "status": "unhealthy",
  "timestamp": number,
  "services": {
    "google_drive": "unavailable",
    "translation": "error"
  }
}
```

#### Errors

- **503 Service Unavailable**: Application unhealthy, services unavailable

---

## 📋 Application Info

### GET `/`

Get basic application information and available endpoints.

#### Parameters

**Query Parameters**: None

#### Return Values

**Success Response (200)**:
```json
{
  "name": "Translation Web Server",
  "version": "string",
  "status": "healthy",
  "environment": "string",
  "endpoints": {
    "languages": "/api/v1/languages",
    "translate": "/translate",
    "payment_success": "/api/payment/success",
    "health": "/health"
  }
}
```

#### Errors

None

---

## 🔧 API Information

### GET `/api/v1`

Get API version information and supported features.

#### Parameters

**Query Parameters**: None

#### Return Values

**Success Response (200)**:
```json
{
  "api_version": "v1",
  "app_version": "string",
  "features": {},
  "supported_formats": ["txt", "doc", "docx", "pdf", "rtf", "odt"],
  "max_file_size_mb": number
}
```

#### Errors

None

---

## 🚨 Common Error Format

All error responses follow this consistent format:

```json
{
  "success": false,
  "error": {
    "code": number,
    "message": "string",
    "type": "string"
  },
  "timestamp": number,
  "path": "string"
}
```

### HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid request parameters
- **408 Request Timeout**: Request timeout (file uploads: 5min, translations: 2min, others: 30s)
- **422 Unprocessable Entity**: Validation errors
- **500 Internal Server Error**: Server-side errors
- **503 Service Unavailable**: Health check failures

---

## 🔐 Rate Limiting

Rate limiting is applied to all endpoints:
- Configurable per endpoint
- Default limits vary by operation type
- Rate limit headers included in responses

## 📝 Notes

- All file operations use Google Drive for storage
- Files are organized by customer email: `{customer}/Inbox/`, `{customer}/Temp/`, `{customer}/Completed/`
- Payment processing requires customer email linkage
- No session management - files linked via metadata
- All timestamps in ISO 8601 format
- File size estimates used for page count calculation