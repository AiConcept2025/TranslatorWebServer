# Translation Service API Documentation

**Version:** 1.0.0
**Base URL:** `http://localhost:8000`
**Generated:** 2025-10-19

---

## Table of Contents

1. [Root & Health Endpoints](#root--health-endpoints)
2. [Authentication Endpoints](#authentication-endpoints)
3. [Translation Endpoints](#translation-endpoints)
4. [File Upload Endpoints](#file-upload-endpoints)
5. [Language Endpoints](#language-endpoints)
6. [Payment Endpoints](#payment-endpoints)
7. [Subscription Endpoints](#subscription-endpoints)
8. [Transaction Management Endpoints](#transaction-management-endpoints)

---

## Root & Health Endpoints

### GET `/`

**Description:** Root endpoint providing API information and available endpoints.

**Incoming Parameters:** None

**Outgoing Parameters:**
```json
{
  "name": "string",
  "version": "string",
  "status": "string",
  "environment": "string",
  "documentation": "string",
  "endpoints": {
    "languages": "string",
    "translate": "string",
    "payment_create": "string",
    "payment_success": "string",
    "health": "string"
  }
}
```

**Errors:** None

---

### GET `/health`

**Description:** Health check endpoint for monitoring and load balancers. Checks application and database health.

**Incoming Parameters:** None

**Outgoing Parameters:**
```json
{
  "status": "healthy | unhealthy",
  "database": {
    "healthy": "boolean",
    "latency": "number"
  },
  "timestamp": "number"
}
```

**Errors:**
- **503 Service Unavailable** - Service is unhealthy

---

### GET `/api/v1`

**Description:** API version information and supported features.

**Incoming Parameters:** None

**Outgoing Parameters:**
```json
{
  "api_version": "string",
  "app_version": "string",
  "features": {},
  "supported_formats": ["string"],
  "max_file_size_mb": "number"
}
```

**Errors:** None

---

## Authentication Endpoints

### POST `/login/individual`

**Description:** Individual user login (no company, no password). Creates user if doesn't exist.

**Incoming Parameters:**
```json
{
  "userFullName": "string",
  "userEmail": "string (email format)",
  "loginDateTime": "string (ISO 8601)"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Individual login successful",
  "data": {
    "authToken": "string (JWT)",
    "tokenType": "Bearer",
    "expiresIn": 28800,
    "expiresAt": "string (ISO 8601)",
    "user": {
      "user_id": "string",
      "user_name": "string",
      "email": "string",
      "company_name": null,
      "permission_level": "user"
    },
    "loginDateTime": "string"
  }
}
```

**Errors:**
- **401 Unauthorized** - Authentication failed
- **500 Internal Server Error** - Login processing failed

---

### POST `/login/corporate`

**Description:** Corporate login with MongoDB authentication. Validates company and user credentials.

**Incoming Parameters:**
```json
{
  "companyName": "string",
  "password": "string (min 6 chars)",
  "userFullName": "string",
  "userEmail": "string (email format)",
  "loginDateTime": "string (ISO 8601)"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Corporate login successful",
  "data": {
    "authToken": "string (session token)",
    "tokenType": "Bearer",
    "expiresIn": 28800,
    "expiresAt": "string (ISO 8601)",
    "user": {
      "user_id": "string",
      "user_name": "string",
      "email": "string",
      "company_name": "string",
      "permission_level": "admin | user"
    },
    "loginDateTime": "string"
  }
}
```

**Errors:**
- **401 Unauthorized** - Invalid company name, password, or user not found
- **500 Internal Server Error** - Login processing failed

---

### POST `/login/logout`

**Description:** Invalidate session token and logout user.

**Incoming Parameters:**
- **Header:** `Authorization: Bearer {token}`

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

**Errors:**
- **401 Unauthorized** - Missing or invalid authorization header
- **404 Not Found** - Session not found
- **500 Internal Server Error** - Logout failed

---

### GET `/login/verify`

**Description:** Verify session token validity and return user data.

**Incoming Parameters:**
- **Header:** `Authorization: Bearer {token}`

**Outgoing Parameters:**
```json
{
  "success": true,
  "valid": true,
  "user": {
    "user_id": "string",
    "user_name": "string",
    "email": "string",
    "company_name": "string",
    "permission_level": "string"
  }
}
```

**Errors:**
- **401 Unauthorized** - Invalid or expired session
- **500 Internal Server Error** - Verification failed

---

### POST `/login/api/auth/signup`

**Description:** Create new user account in users_login collection.

**Incoming Parameters:**
```json
{
  "user_name": "string",
  "user_email": "string (email format)",
  "password": "string"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "User created successfully",
  "data": {
    "user_id": "string",
    "user_name": "string",
    "user_email": "string",
    "created_at": "string (ISO 8601)"
  }
}
```

**Errors:**
- **400 Bad Request** - Email/username already exists, validation errors
- **500 Internal Server Error** - Signup failed

---

### POST `/login/api/auth/login`

**Description:** Authenticate user from users_login collection with password.

**Incoming Parameters:**
```json
{
  "email": "string (email format)",
  "password": "string"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "user_id": "string",
    "user_name": "string",
    "user_email": "string",
    "session_token": "string",
    "token_type": "Bearer",
    "expires_in": 28800,
    "expires_at": "string (ISO 8601)"
  }
}
```

**Errors:**
- **401 Unauthorized** - Invalid credentials
- **500 Internal Server Error** - Login failed

---

## Translation Endpoints

### POST `/translate`

**Description:** Upload files to Google Drive and prepare for translation. Creates transaction records and calculates pricing.

**Incoming Parameters:**
```json
{
  "files": [
    {
      "id": "string",
      "name": "string",
      "size": "number",
      "type": "string",
      "content": "string (base64-encoded)"
    }
  ],
  "sourceLanguage": "string (language code)",
  "targetLanguage": "string (language code)",
  "email": "string (email format)",
  "paymentIntentId": "string | null"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "data": {
    "id": "string (storage_id)",
    "status": "stored",
    "progress": 100,
    "message": "string",
    "pricing": {
      "total_pages": "number",
      "price_per_page": "number",
      "total_amount": "number",
      "currency": "USD",
      "customer_type": "enterprise | individual",
      "transaction_ids": ["string"]
    },
    "files": {
      "total_files": "number",
      "successful_uploads": "number",
      "failed_uploads": "number",
      "stored_files": [
        {
          "file_id": "string",
          "filename": "string",
          "status": "stored | failed",
          "page_count": "number",
          "size": "number",
          "google_drive_url": "string"
        }
      ]
    },
    "customer": {
      "email": "string",
      "source_language": "string",
      "target_language": "string",
      "temp_folder_id": "string"
    },
    "payment": {
      "required": "boolean",
      "amount_cents": "number",
      "description": "string",
      "customer_email": "string"
    },
    "user": {
      "permission_level": "string",
      "email": "string",
      "full_name": "string"
    }
  },
  "error": null
}
```

**Errors:**
- **400 Bad Request** - Invalid email, language codes, file validation errors, or disposable email
- **408 Request Timeout** - Request exceeded 120 seconds
- **500 Internal Server Error** - File upload or processing failed

**Notes:**
- Maximum 10 files per request
- Files stored in Google Drive: `{company}/{email}/Temp/` (enterprise) or `{email}/Temp/` (individual)
- Subscription-based pricing for enterprise customers
- Creates transaction records for tracking

---

## File Upload Endpoints

### POST `/api/upload`

**Description:** Upload files with customer information and target language. Validates files, counts pages, and stores in Google Drive.

**Incoming Parameters:**
- **Form Data:**
  - `customer_email` (optional): Customer email (uses default if not provided)
  - `target_language` (required): Target language code
  - `files` (required): List of files to upload

**Outgoing Parameters:**
```json
{
  "success": "boolean",
  "message": "string",
  "customer_email": "string",
  "target_language": "string",
  "total_files": "number",
  "successful_uploads": "number",
  "failed_uploads": "number",
  "results": [
    {
      "filename": "string",
      "file_id": "string",
      "status": "success | failed",
      "message": "string",
      "file_size": "number",
      "content_type": "string",
      "google_drive_folder": "string",
      "page_count": "number | null",
      "supports_page_counting": "boolean | null"
    }
  ],
  "google_drive_folder_path": "string"
}
```

**Errors:**
- **400 Bad Request** - No files, validation errors, unsupported formats
- **207 Multi-Status** - Partial success (some files failed)
- **415 Unsupported Media Type** - Invalid file type
- **500 Internal Server Error** - Upload processing failed

**Supported Formats:**
- Documents: PDF, Word (.doc, .docx) - Max 100MB
- Images: JPEG, PNG, TIFF - Max 50MB

---

### POST `/api/upload/legacy`

**Description:** Legacy upload endpoint (DEPRECATED). Use `/api/upload` instead.

**Incoming Parameters:**
- **Form Data:** `files` - List of files

**Outgoing Parameters:**
```json
{
  "success": true,
  "data": ["string (file IDs)"],
  "error": null,
  "deprecated": true,
  "message": "string"
}
```

**Errors:**
- **400 Bad Request** - Invalid file extension
- **413 Payload Too Large** - File exceeds size limit
- **415 Unsupported Media Type** - Unsupported file type

---

## Language Endpoints

### GET `/api/v1/languages`

**Description:** Get supported languages from `supported_languages.txt` file.

**Incoming Parameters:** None

**Outgoing Parameters:**
```json
{
  "success": true,
  "data": [
    {
      "code": "string (2-letter code)",
      "name": "string"
    }
  ]
}
```

**Errors:**
- **404 Not Found** - Languages file not found
- **500 Internal Server Error** - Failed to load languages

---

### GET `/api/v1/languages/legacy`

**Description:** Legacy endpoint returning hardcoded language list (DEPRECATED).

**Incoming Parameters:** None

**Outgoing Parameters:**
```json
{
  "success": true,
  "data": [
    {
      "code": "string",
      "name": "string",
      "nativeName": "string",
      "isPopular": "boolean"
    }
  ],
  "error": null
}
```

**Errors:** None

---

## Payment Endpoints

### POST `/api/payment/success`

**Description:** Payment success webhook. Returns immediately and processes files in background.

**Incoming Parameters:**
```json
{
  "customerEmail": "string (email format)",
  "paymentIntentId": "string",
  "amount": "number (optional)",
  "currency": "string (default: USD)",
  "paymentMethod": "string (optional)",
  "timestamp": "string (optional)",
  "metadata": {
    "status": "string",
    "cardBrand": "string",
    "last4": "string",
    "receiptNumber": "string",
    "created": "string",
    "simulated": "boolean",
    "customer_email": "string"
  }
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Payment confirmed. Files are being processed in the background.",
  "data": {
    "customer_email": "string",
    "payment_intent_id": "string",
    "status": "processing",
    "processing_time_ms": "number"
  }
}
```

**Errors:**
- **400 Bad Request** - Missing customer_email or payment_intent_id
- **408 Request Timeout** - Request exceeded 90 seconds
- **500 Internal Server Error** - Payment processing failed

**Background Tasks:**
1. Find files with status "awaiting_payment"
2. Move files from `Temp/` to `Inbox/`
3. Update file status to "payment_confirmed"

---

### POST `/api/payment/failure`

**Description:** Payment failure handler. Deletes files from Temp folder.

**Incoming Parameters:**
```json
{
  "customer_email": "string (email format)",
  "payment_intent_id": "string"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "string",
  "data": {
    "customer_email": "string",
    "payment_intent_id": "string",
    "total_files": "number",
    "deleted_successfully": "number",
    "workflow": "simplified_no_sessions"
  }
}
```

**Errors:**
- **500 Internal Server Error** - File deletion failed

---

## Subscription Endpoints

### POST `/api/subscriptions/`

**Description:** Create new subscription (Admin only).

**Incoming Parameters:**
```json
{
  "company_id": "string (ObjectId)",
  "subscription_unit": "string (e.g., 'page')",
  "units_per_subscription": "number",
  "price_per_unit": "number",
  "promotional_units": "number",
  "discount": "number",
  "subscription_price": "number",
  "start_date": "string (ISO 8601)",
  "end_date": "string (ISO 8601)",
  "status": "string"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Subscription created successfully",
  "data": {
    "subscription_id": "string",
    "company_id": "string",
    "subscription_unit": "string",
    "units_per_subscription": "number",
    "status": "string"
  }
}
```

**Errors:**
- **400 Bad Request** - Validation error
- **401 Unauthorized** - Not authenticated
- **403 Forbidden** - Not admin
- **500 Internal Server Error** - Creation failed

---

### GET `/api/subscriptions/{subscription_id}`

**Description:** Get subscription details by ID.

**Incoming Parameters:**
- **Path:** `subscription_id` (string)

**Outgoing Parameters:**
```json
{
  "success": true,
  "data": {
    "subscription_id": "string",
    "company_id": "string",
    "subscription_unit": "string",
    "units_per_subscription": "number",
    "price_per_unit": "number",
    "promotional_units": "number",
    "discount": "number",
    "subscription_price": "number",
    "start_date": "string (ISO 8601)",
    "end_date": "string (ISO 8601) | null",
    "status": "string",
    "usage_periods": ["array"],
    "created_at": "string (ISO 8601)",
    "updated_at": "string (ISO 8601)"
  }
}
```

**Errors:**
- **401 Unauthorized** - Not authenticated
- **403 Forbidden** - Access denied
- **404 Not Found** - Subscription not found

---

### GET `/api/subscriptions/company/{company_id}`

**Description:** Get all subscriptions for a company.

**Incoming Parameters:**
- **Path:** `company_id` (string)
- **Query:**
  - `status` (optional): Filter by status
  - `active_only` (optional): Return only active subscriptions

**Outgoing Parameters:**
```json
{
  "success": true,
  "data": {
    "company_id": "string",
    "count": "number",
    "subscriptions": [
      {
        "subscription_id": "string",
        "subscription_unit": "string",
        "units_per_subscription": "number",
        "status": "string",
        "start_date": "string (ISO 8601)",
        "end_date": "string (ISO 8601) | null",
        "created_at": "string (ISO 8601)"
      }
    ]
  }
}
```

**Errors:**
- **401 Unauthorized** - Not authenticated
- **403 Forbidden** - Access denied

---

### PATCH `/api/subscriptions/{subscription_id}`

**Description:** Update subscription details (Admin only).

**Incoming Parameters:**
- **Path:** `subscription_id` (string)
- **Body:** Partial subscription update data

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Subscription updated successfully",
  "data": {
    "subscription_id": "string",
    "status": "string",
    "updated_at": "string (ISO 8601)"
  }
}
```

**Errors:**
- **400 Bad Request** - Validation error
- **401 Unauthorized** - Not authenticated
- **403 Forbidden** - Not admin
- **404 Not Found** - Subscription not found
- **500 Internal Server Error** - Update failed

---

### POST `/api/subscriptions/{subscription_id}/usage-periods`

**Description:** Add new usage period to subscription (Admin only).

**Incoming Parameters:**
- **Path:** `subscription_id` (string)
- **Body:**
```json
{
  "period_start": "string (ISO 8601)",
  "period_end": "string (ISO 8601)",
  "units_allocated": "number"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Usage period added successfully",
  "data": {
    "subscription_id": "string",
    "usage_periods_count": "number"
  }
}
```

**Errors:**
- **400 Bad Request** - Validation error
- **401 Unauthorized** - Not authenticated
- **403 Forbidden** - Not admin
- **404 Not Found** - Subscription not found
- **500 Internal Server Error** - Add failed

---

### POST `/api/subscriptions/{subscription_id}/record-usage`

**Description:** Record usage for a subscription.

**Incoming Parameters:**
- **Path:** `subscription_id` (string)
- **Body:**
```json
{
  "units_to_add": "number",
  "use_promotional_units": "boolean"
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Usage recorded successfully",
  "data": {
    "subscription_id": "string",
    "units_recorded": "number",
    "updated_at": "string (ISO 8601)"
  }
}
```

**Errors:**
- **400 Bad Request** - Validation error
- **401 Unauthorized** - Not authenticated
- **403 Forbidden** - Access denied
- **404 Not Found** - Subscription not found
- **500 Internal Server Error** - Record failed

---

### GET `/api/subscriptions/{subscription_id}/summary`

**Description:** Get subscription usage summary.

**Incoming Parameters:**
- **Path:** `subscription_id` (string)

**Outgoing Parameters:**
```json
{
  "success": true,
  "data": {
    "subscription_id": "string",
    "status": "string",
    "total_allocated": "number",
    "total_used": "number",
    "total_remaining": "number",
    "promotional_used": "number",
    "promotional_remaining": "number"
  }
}
```

**Errors:**
- **401 Unauthorized** - Not authenticated
- **403 Forbidden** - Access denied
- **404 Not Found** - Subscription not found

---

### POST `/api/subscriptions/expire-subscriptions`

**Description:** Manually trigger expiration of subscriptions (Admin only).

**Incoming Parameters:** None

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Expired N subscriptions",
  "data": {
    "expired_count": "number"
  }
}
```

**Errors:**
- **401 Unauthorized** - Not authenticated
- **403 Forbidden** - Not admin

---

## Transaction Management Endpoints

### POST `/api/transactions/confirm`

**Description:** Confirm transactions and move files from Temp/ to Inbox/. Returns immediately and processes in background.

**Incoming Parameters:**
```json
{
  "transaction_ids": ["string"]
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Transactions confirmed. Files are being moved to Inbox in the background.",
  "data": {
    "confirmed_transactions": "number",
    "total_files": "number",
    "status": "processing",
    "customer_email": "string",
    "company_name": "string | null",
    "processing_note": "string"
  }
}
```

**Errors:**
- **400 Bad Request** - No transaction IDs provided
- **401 Unauthorized** - Not authenticated
- **404 Not Found** - No valid transactions found
- **500 Internal Server Error** - Confirmation failed

**Background Tasks:**
1. Move files from Temp/ to Inbox/
2. Update transaction status to "confirmed"
3. Update subscription usage

---

### POST `/api/transactions/decline`

**Description:** Decline transactions and delete files from Temp/.

**Incoming Parameters:**
```json
{
  "transaction_ids": ["string"]
}
```

**Outgoing Parameters:**
```json
{
  "success": true,
  "message": "Successfully declined N transaction(s)",
  "data": {
    "declined_transactions": "number",
    "deleted_files": "number"
  }
}
```

**Errors:**
- **400 Bad Request** - No transaction IDs provided
- **401 Unauthorized** - Not authenticated
- **404 Not Found** - No valid transactions found
- **500 Internal Server Error** - Decline failed

---

## Error Response Format

All endpoints return errors in the following format:

```json
{
  "success": false,
  "error": {
    "code": "number (HTTP status code)",
    "message": "string (error description)",
    "type": "string (error type)",
    "details": "object (optional validation details)"
  },
  "timestamp": "number (Unix timestamp)",
  "path": "string (request path)"
}
```

---

## Authentication

Most endpoints require authentication via JWT token or session token:

**Header Format:**
```
Authorization: Bearer {token}
```

**Token Types:**
1. **JWT Token** - Individual users (expires in 8 hours)
2. **Session Token** - Corporate users (expires in 8 hours)

**Permission Levels:**
- `user` - Standard user access
- `admin` - Administrative access (required for subscription management)

---

## Rate Limits

- Default timeout: 30 seconds
- File upload timeout: 300 seconds (5 minutes)
- Translation timeout: 120 seconds (2 minutes)
- Payment timeout: 90 seconds
- Authentication timeout: 60 seconds

---

## File Storage Structure

**Individual Customers:**
```
{customer_email}/
  ├── Temp/          # Files awaiting payment
  └── Inbox/         # Paid files ready for processing
```

**Enterprise Customers:**
```
{company_name}/
  └── {customer_email}/
      ├── Temp/      # Files awaiting payment confirmation
      └── Inbox/     # Confirmed files ready for processing
```

---

## Notes

1. **Background Processing:** Payment and transaction endpoints use background tasks for file operations to ensure fast response times (< 1 second)
2. **Subscription Pricing:** Enterprise customers with active subscriptions receive dynamic pricing based on subscription terms
3. **Transaction Tracking:** All file uploads create transaction records for audit and tracking purposes
4. **Page Counting:** Automatic page counting for supported formats (PDF, Word, images)
5. **CORS:** Configured for cross-origin requests with credentials support

---

**End of Documentation**
