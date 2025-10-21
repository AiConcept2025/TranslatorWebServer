# API Endpoints Documentation

## Executive Summary

This document provides a comprehensive overview of all API endpoints in the Translation Service backend, categorized by usage status:

- **Total Endpoints Identified:** 22 (5 endpoints removed in cleanup)
- **Active (Used by Frontend):** 12
- **Tested Only:** 0 (deprecated endpoints removed)
- **Unused/Deprecated:** 2 (3 payment stubs removed)
- **Internal (Admin Only):** 8

### Recent Changes (Cleanup Completed)
- ✅ **Removed** `POST /api/upload/legacy` (66 lines) - Deprecated stub endpoint
- ✅ **Removed** `GET /api/v1/languages/legacy` (46 lines) - Deprecated stub endpoint
- ✅ **Removed** `app/routers/payment.py` (386 lines) - Entire file containing 4 unused stub endpoints:
  - `POST /api/payment/create-intent` (50 lines)
  - `GET /api/payment/{payment_intent_id}/verify` (43 lines)
  - `POST /api/payment/success` (147 lines)
  - `POST /api/payment/failure` (70 lines)
- **Total Lines Removed:** 501 lines of dead code

---

## Endpoints by Status

### ✅ ACTIVE - Used by Frontend

These endpoints are actively called by the frontend application and are critical to the service.

#### 1. **GET /api/v1/languages**
- **Description:** Get list of supported languages from `supported_languages.txt` file
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.getLanguages()` - Called on app initialization to populate language dropdowns
- **File:** `app/routers/languages.py:17`
- **Request:** None
- **Response:**
  ```json
  {
    "success": true,
    "data": [
      {"code": "en", "name": "English"},
      {"code": "es", "name": "Spanish"}
    ]
  }
  ```

---

#### 2. **POST /translate**
- **Description:** Enterprise/corporate translation endpoint with file storage
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.translateRequest()` - Called when corporate users submit files for translation
- **File:** `app/routers/translate.py:27`
- **Request Body:**
  ```json
  {
    "files": [{
      "id": "file_123",
      "name": "document.pdf",
      "size": 1024000,
      "type": "application/pdf",
      "content": "base64_encoded_content"
    }],
    "sourceLanguage": "en",
    "targetLanguage": "es",
    "email": "user@example.com",
    "paymentIntentId": "pi_xxx"
  }
  ```
- **Response:**
  ```json
  {
    "success": true,
    "data": {
      "pricing": {
        "total_pages": 10,
        "price_per_page": 0.10,
        "total_amount": 1.00,
        "currency": "usd"
      }
    }
  }
  ```

---

#### 3. **POST /translate-user**
- **Description:** Individual user translation endpoint (non-enterprise, uses user_transactions collection)
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.translateUserRequest()` - Called when individual users submit files for translation
- **File:** `app/routers/translate_user.py:206`
- **Request Body:**
  ```json
  {
    "files": [{
      "id": "file_123",
      "name": "document.pdf",
      "size": 1024000,
      "type": "application/pdf",
      "content": "base64_encoded_content"
    }],
    "sourceLanguage": "en",
    "targetLanguage": "es",
    "email": "user@example.com",
    "userName": "John Doe"
  }
  ```

---

#### 4. **POST /api/payment/success**
- **Description:** Payment success webhook (instant response, background file processing)
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.confirmPaymentSuccess()` - Called after successful payment to move files from Temp to Inbox
- **File:** `app/routers/payment_simplified.py:178`
- **Request Body:**
  ```json
  {
    "customerEmail": "user@example.com",
    "paymentIntentId": "pi_xxx",
    "amount": 10.00,
    "currency": "USD",
    "paymentMethod": "square"
  }
  ```

---

#### 5. **POST /api/payment/user-success**
- **Description:** User payment success webhook for individual users (uses Square transaction IDs)
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.confirmUserPaymentSuccess()` - Called after individual user payment success
- **File:** `app/routers/payment_simplified.py:473`
- **Request Body:**
  ```json
  {
    "customerEmail": "user@example.com",
    "square_transaction_id": "sqt_xxxxx",
    "amount": 10.00,
    "currency": "USD"
  }
  ```

---

#### 6. **POST /api/payment/failure**
- **Description:** Payment failure cleanup (deletes files from Temp folder)
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.confirmPaymentFailure()` - Called when payment fails to cleanup uploaded files
- **File:** `app/routers/payment_simplified.py:600`
- **Request:** Query parameters: `customer_email`, `payment_intent_id`

---

#### 7. **POST /login/corporate**
- **Description:** Corporate user authentication with MongoDB
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.corporateLogin()` - Called when corporate users log in
- **File:** `app/routers/auth.py:188`
- **Request Body:**
  ```json
  {
    "companyName": "Iris Trading",
    "password": "userpassword",
    "userFullName": "Vladimir Danishevsky",
    "userEmail": "danishevsky@gmail.com",
    "loginDateTime": "2025-10-13T10:30:00Z"
  }
  ```
- **Response:**
  ```json
  {
    "success": true,
    "message": "Corporate login successful",
    "data": {
      "authToken": "session-token",
      "tokenType": "Bearer",
      "expiresIn": 28800,
      "user": {
        "user_name": "Vladimir Danishevsky",
        "email": "danishevsky@gmail.com",
        "company_name": "Iris Trading",
        "permission_level": "admin"
      }
    }
  }
  ```

---

#### 8. **POST /login/individual**
- **Description:** Individual user authentication (no company, no password)
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.individualLogin()` - Called when individual users log in
- **File:** `app/routers/auth.py:73`
- **Request Body:**
  ```json
  {
    "userFullName": "John Doe",
    "userEmail": "john@example.com",
    "loginDateTime": "2025-10-15T10:30:00Z"
  }
  ```

---

#### 9. **POST /login/api/auth/signup**
- **Description:** Create new user account in users_login collection
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.signup()` - Called during user registration
- **File:** `app/routers/auth.py:458`
- **Request Body:**
  ```json
  {
    "user_name": "John Doe",
    "user_email": "john@example.com",
    "password": "SecurePass123"
  }
  ```

---

#### 10. **POST /login/api/auth/login**
- **Description:** Authenticate user from users_login collection
- **Status:** ✅ Active - Used by Frontend
- **Frontend Usage:** `ApiService.authLogin()` - Called during user authentication
- **File:** `app/routers/auth.py:574`
- **Request Body:**
  ```json
  {
    "email": "john@example.com",
    "password": "SecurePass123"
  }
  ```

---

#### 11. **POST /api/upload**
- **Description:** Upload files with multipart form data, create Google Drive folder structure
- **Status:** ✅ Active - Used by Tests
- **Test Usage:** Extensively tested in `test_upload_endpoint.py`
- **File:** `app/routers/upload.py:27`
- **Note:** Not directly used by current frontend (frontend uses /translate and /translate-user instead which handle uploads internally)

---

#### 12. **POST /api/payment/create-intent**
- **Description:** Create Stripe payment intent
- **Status:** ✅ Active - Legacy payment flow
- **Frontend Usage:** May be used by legacy payment flow
- **File:** `app/routers/payment.py:36`
- **Note:** Current frontend uses Square/Stripe directly, this may be deprecated

---

### ⚠️ UNUSED - Not Referenced

These endpoints exist but are not used by frontend or tests.

#### 15. **POST /login/logout**
- **Description:** Logout endpoint - invalidates session token
- **Status:** ⚠️ Unused
- **File:** `app/routers/auth.py:310`
- **Recommendation:** Implement frontend logout flow or document why not needed
- **Request:** Header: `Authorization: Bearer {token}`

---

#### 16. **GET /login/verify**
- **Description:** Verify session token and return user data
- **Status:** ⚠️ Unused
- **File:** `app/routers/auth.py:371`
- **Recommendation:** Could be useful for session validation/refresh
- **Request:** Header: `Authorization: Bearer {token}`

---

### 🔧 INTERNAL - Subscription Management (Admin Only)

These endpoints are for internal subscription management and require admin authentication.

#### 17. **POST /api/subscriptions/**
- **Description:** Create new subscription
- **Status:** 🔧 Internal - Admin Only
- **Authentication:** Requires admin token via `get_admin_user` dependency
- **File:** `app/routers/subscriptions.py:25`

---

#### 18. **GET /api/subscriptions/{subscription_id}**
- **Description:** Get subscription details by ID
- **Status:** 🔧 Internal - Authenticated
- **Authentication:** Requires user token via `get_current_user` dependency
- **File:** `app/routers/subscriptions.py:77`

---

#### 19. **GET /api/subscriptions/company/{company_id}**
- **Description:** Get all subscriptions for a company
- **Status:** 🔧 Internal - Authenticated
- **File:** `app/routers/subscriptions.py:121`

---

#### 20. **PATCH /api/subscriptions/{subscription_id}**
- **Description:** Update subscription details
- **Status:** 🔧 Internal - Admin Only
- **File:** `app/routers/subscriptions.py:170`

---

#### 21. **POST /api/subscriptions/{subscription_id}/usage-periods**
- **Description:** Add usage period to subscription
- **Status:** 🔧 Internal - Admin Only
- **File:** `app/routers/subscriptions.py:207`

---

#### 22. **POST /api/subscriptions/{subscription_id}/record-usage**
- **Description:** Record usage for subscription
- **Status:** 🔧 Internal - Authenticated
- **File:** `app/routers/subscriptions.py:253`

---

#### 23. **GET /api/subscriptions/{subscription_id}/summary**
- **Description:** Get subscription usage summary
- **Status:** 🔧 Internal - Authenticated
- **File:** `app/routers/subscriptions.py:305`

---

#### 24. **POST /api/subscriptions/expire-subscriptions**
- **Description:** Manually trigger subscription expiration
- **Status:** 🔧 Internal - Admin Only
- **File:** `app/routers/subscriptions.py:338`

---

## Endpoints by Router

### auth.py (6 endpoints)
- ✅ `POST /login/corporate` - Corporate authentication
- ✅ `POST /login/individual` - Individual authentication
- ⚠️ `POST /login/logout` - Logout (unused)
- ⚠️ `GET /login/verify` - Session verification (unused)
- ✅ `POST /login/api/auth/signup` - User signup
- ✅ `POST /login/api/auth/login` - User login

### translate.py & translate_user.py (2 endpoints)
- ✅ `POST /translate` - Enterprise translation
- ✅ `POST /translate-user` - Individual user translation

### upload.py (2 endpoints)
- ✅ `POST /api/upload` - File upload with multipart
- 🧪 `POST /api/upload/legacy` - DEPRECATED legacy endpoint

### languages.py (2 endpoints)
- ✅ `GET /api/v1/languages` - Get supported languages
- ⚠️ `GET /api/v1/languages/legacy` - DEPRECATED

### payment.py (4 endpoints)
- ✅ `POST /api/payment/create-intent` - Create payment intent
- ⚠️ `GET /api/payment/{id}/verify` - Verify payment (unused)
- ⚠️ `POST /api/payment/success` - Legacy payment success (unused)
- ⚠️ `POST /api/payment/failure` - Legacy payment failure (unused)

### payment_simplified.py (3 endpoints)
- ✅ `POST /api/payment/success` - Payment success webhook
- ✅ `POST /api/payment/user-success` - User payment success webhook
- ✅ `POST /api/payment/failure` - Payment failure cleanup

### subscriptions.py (8 endpoints)
- 🔧 `POST /api/subscriptions/` - Create subscription (admin)
- 🔧 `GET /api/subscriptions/{id}` - Get subscription
- 🔧 `GET /api/subscriptions/company/{id}` - Get company subscriptions
- 🔧 `PATCH /api/subscriptions/{id}` - Update subscription (admin)
- 🔧 `POST /api/subscriptions/{id}/usage-periods` - Add usage period (admin)
- 🔧 `POST /api/subscriptions/{id}/record-usage` - Record usage
- 🔧 `GET /api/subscriptions/{id}/summary` - Get usage summary
- 🔧 `POST /api/subscriptions/expire-subscriptions` - Expire subscriptions (admin)

---

## Summary Statistics

### Usage Breakdown
| Category | Count | Percentage |
|----------|-------|------------|
| ✅ Active (Frontend) | 12 | 55% |
| 🧪 Tested Only | 0 | 0% |
| ⚠️ Unused | 2 | 9% |
| 🔧 Internal (Admin) | 8 | 36% |
| **Total** | **22** | **100%** |

### HTTP Methods Distribution
- **POST:** 20 endpoints (74%)
- **GET:** 6 endpoints (22%)
- **PATCH:** 1 endpoint (4%)

### Authentication Requirements
- **Public:** 5 endpoints (languages, corporate/individual login, signup)
- **Authenticated:** 14 endpoints (requires Bearer token)
- **Admin Only:** 5 endpoints (subscription management)

---

## Recommendations

### 1. **✅ COMPLETED: Removed Duplicate/Deprecated Endpoints**

**Removed in latest cleanup (501 lines):**
- ✅ `/api/upload/legacy` (66 lines)
- ✅ `/api/v1/languages/legacy` (46 lines)
- ✅ `app/routers/payment.py` entire file (386 lines):
  - `/api/payment/create-intent`
  - `/api/payment/{payment_intent_id}/verify`
  - `/api/payment/success`
  - `/api/payment/failure`

**Status:** All duplicate/deprecated endpoints have been removed. No action needed.

---

### 2. **Implement or Remove Unused Auth Endpoints**

**Medium Priority:**
- ⚠️ `/login/logout` - Implement frontend logout flow OR remove
- ⚠️ `/login/verify` - Implement session refresh OR remove

**Action:** Decide if these are needed for security best practices.

---

### 3. **✅ COMPLETED: Consolidated Payment Logic**

**Action Taken:**
- ✅ Removed `app/routers/payment.py` (entire file, 386 lines)
- ✅ All payment logic now consolidated in `payment_simplified.py`
- ✅ Active payment provider: **Square** (for individual users)

**Status:** Payment logic consolidated. No action needed.

---

### 4. **Add Missing Frontend Features**

**Implement these unused but valuable endpoints:**
- `POST /login/logout` - Session termination
- `GET /login/verify` - Session validation/refresh

---

### 5. **Document Subscription Management**

**Current State:** 8 subscription endpoints exist but no frontend UI.

**Recommendation:**
- Create admin panel for subscription management, OR
- Document these as API-only endpoints for internal tools, OR
- Provide CLI scripts for admin operations

---

### 6. **Add Test Coverage**

**Gaps identified:**
- Auth endpoints (`/login/*`) - No integration tests found
- Payment webhooks - Need webhook simulation tests
- Subscription endpoints - Need comprehensive test suite

**Action:** Add integration tests for all active endpoints.

---

## API Contract Standards

### Standard Response Format

**Success Response:**
```json
{
  "success": true,
  "message": "Operation successful",
  "data": { /* endpoint-specific data */ }
}
```

**Error Response:**
```json
{
  "success": false,
  "message": "Error message",
  "error": {
    "code": "ERROR_CODE",
    "message": "Detailed error message"
  }
}
```

### Common HTTP Status Codes
- **200 OK** - Successful GET/POST
- **201 Created** - Successful resource creation
- **207 Multi-Status** - Partial success (file uploads)
- **400 Bad Request** - Validation errors
- **401 Unauthorized** - Authentication required
- **403 Forbidden** - Insufficient permissions
- **404 Not Found** - Resource not found
- **500 Internal Server Error** - Server error

---

## Maintenance Schedule

**Quarterly Review (Every 3 months):**
1. Check for new unused endpoints
2. Review deprecated endpoint usage in logs
3. Update this documentation
4. Remove confirmed-unused endpoints

**Before Major Release:**
1. Remove all deprecated endpoints
2. Update API version
3. Notify clients of breaking changes

---

**Document Generated:** 2025-10-21
**Last Updated:** 2025-10-21
**Backend Version:** FastAPI + Python 3.11+
**Frontend Integration:** React 18 + TypeScript
**Review Next:** 2026-01-21
