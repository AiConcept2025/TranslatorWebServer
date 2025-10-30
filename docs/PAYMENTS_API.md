# Payments API - Comprehensive Documentation

**Version:** 2.0.0
**Last Updated:** October 30, 2025
**Base URL:** `http://localhost:8000/api/v1/payments`
**API Prefix:** `/api/v1/payments`

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Authentication & Authorization](#authentication--authorization)
4. [Payment Data Model](#payment-data-model)
5. [API Endpoints](#api-endpoints)
   - [Admin Endpoints](#admin-endpoints)
   - [Company Endpoints](#company-endpoints)
   - [Query Endpoints](#query-endpoints)
   - [Transaction Endpoints](#transaction-endpoints)
   - [Statistics Endpoints](#statistics-endpoints)
6. [Request/Response Patterns](#requestresponse-patterns)
7. [Error Handling](#error-handling)
8. [Usage Scenarios](#usage-scenarios)
9. [Integration Guide](#integration-guide)
10. [Testing Guide](#testing-guide)
11. [Best Practices](#best-practices)

---

## Overview

### Purpose

The Payments API manages **subscription payment records** for the translation service platform. This API is specifically designed for:

- **Subscription-based payments** (NOT per-transaction payments)
- Recording payment events from Square payment processor
- Tracking payment history and status
- Processing refunds
- Generating payment statistics and reports
- Providing admin and company-level payment visibility

### Key Characteristics

**What This API Does:**
- Stores subscription payment records in MongoDB
- Links payments to companies and subscriptions
- Tracks refund history
- Provides payment reporting and analytics
- Supports multi-company payment management

**What This API Does NOT Do:**
- Process actual payment transactions (handled by Square)
- Handle per-document translation charges
- Manage subscription creation/modification
- Store credit card information (PCI compliance)

### Technology Stack

- **Backend Framework:** FastAPI (Python 3.11+)
- **Database:** MongoDB (Motor async driver)
- **Payment Processor:** Square Payments API
- **Authentication:** JWT Bearer tokens (admin/user roles)
- **Data Validation:** Pydantic v2

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Payment Management Flow                   │
└─────────────────────────────────────────────────────────────┘

External Services          FastAPI Application         Database
─────────────────         ──────────────────────       ────────

┌──────────┐              ┌──────────────────┐        ┌──────────┐
│  Square  │              │  Payments Router │        │ MongoDB  │
│ Payment  │──webhook────▶│  /api/v1/payments│◀──────▶│ payments │
│   API    │              └──────────────────┘        │collection│
└──────────┘                      │                   └──────────┘
                                  │
                          ┌───────┴────────┐
                          │                │
                    ┌─────▼─────┐   ┌─────▼──────┐
                    │  Payment  │   │   Auth     │
                    │Repository │   │Middleware  │
                    └───────────┘   └────────────┘
```

### Data Flow

**1. Subscription Payment Creation (Admin)**
```
Admin User → POST /api/v1/payments/subscription
    ↓
Auth Middleware (validates admin token)
    ↓
Validate subscription exists and matches company
    ↓
Create payment record in MongoDB
    ↓
Return payment confirmation
```

**2. Company Viewing Payments**
```
Company User → GET /api/v1/payments/company/{company_name}
    ↓
Fetch payments filtered by company_name
    ↓
Apply status filter (optional)
    ↓
Return paginated payment list
```

**3. Refund Processing**
```
POST /api/v1/payments/{square_payment_id}/refund
    ↓
Validate payment exists
    ↓
Check refund amount ≤ payment amount
    ↓
Add refund to refunds array
    ↓
Update payment status to REFUNDED
    ↓
Return updated payment with refund details
```

### Database Schema

**Collection:** `payments`

```javascript
{
  _id: ObjectId("68fad3c2a0f41c24037c4810"),

  // Square Integration
  square_payment_id: "sq_payment_e59858fff0794614",      // Unique Square ID
  square_order_id: "sq_order_e4dce86988a847b1",          // Optional
  square_customer_id: "sq_customer_c7b478ddc7b04f99",    // Optional

  // Company & User
  company_name: "Acme Translation Corp",                  // Owner company
  subscription_id: "690023c7eb2bceb90e274133",           // ObjectId string
  user_id: "user_9db5a0fbe769442d",                      // Optional
  user_email: "admin@acme.com",                          // Payment initiator

  // Payment Details
  amount: 9000,                                           // Cents (90.00 USD)
  currency: "USD",                                        // ISO 4217
  payment_status: "COMPLETED",                            // Status enum
  payment_date: ISODate("2025-10-28T11:18:04.213Z"),

  // Payment Method (Optional)
  payment_method: "card",
  card_brand: "VISA",
  card_last_4: "1234",
  receipt_url: "https://squareup.com/receipt/preview/...",

  // Refunds
  refunds: [
    {
      refund_id: "rfn_01J2M9ABCD",
      amount: 500,                                        // Cents
      currency: "USD",
      status: "COMPLETED",
      idempotency_key: "rfd_7e6df9c2-5f7c-43f9-...",
      created_at: ISODate("2025-10-29T10:00:00.000Z")
    }
  ],

  // Timestamps
  created_at: ISODate("2025-10-28T11:18:04.213Z"),
  updated_at: ISODate("2025-10-28T11:18:04.213Z")
}
```

### Indexes

```javascript
// Recommended indexes for optimal performance
db.payments.createIndex({ "square_payment_id": 1 }, { unique: true })
db.payments.createIndex({ "company_name": 1, "payment_date": -1 })
db.payments.createIndex({ "user_email": 1, "payment_date": -1 })
db.payments.createIndex({ "payment_status": 1 })
db.payments.createIndex({ "subscription_id": 1 })
```

---

## Authentication & Authorization

### Authentication Methods

**1. Admin Authentication**
- Required for: Create subscription payments, view all payments
- Header: `Authorization: Bearer <admin_jwt_token>`
- Validation: `get_admin_user` dependency
- Permissions: Full access to all payment records

**2. User Authentication** (Future Enhancement)
- Required for: User-specific payment queries
- Header: `Authorization: Bearer <user_jwt_token>`
- Validation: `get_current_user` dependency
- Permissions: Access to own company's payments only

**3. No Authentication** (Limited Endpoints)
- Some query endpoints may not require authentication
- Read-only access
- Limited to specific use cases

### Permission Matrix

| Endpoint | Admin | User | Public |
|----------|-------|------|--------|
| `GET /payments` | ✅ | ❌ | ❌ |
| `POST /payments/subscription` | ✅ | ❌ | ❌ |
| `GET /payments/company/{name}` | ✅ | ✅* | ❌ |
| `GET /payments/{id}` | ✅ | ✅* | ❌ |
| `POST /payments/{id}/refund` | ✅ | ❌ | ❌ |
| `GET /payments/company/{name}/stats` | ✅ | ✅* | ❌ |

*Users can only access their own company's data

### Obtaining Authentication Tokens

**Admin Token:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/admin/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin_password"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "email": "admin@example.com",
    "role": "admin"
  }
}
```

---

## Payment Data Model

### Payment Record Structure

```python
class Payment(BaseModel):
    """Complete payment record in MongoDB"""

    # Identifiers
    _id: ObjectId                          # MongoDB auto-generated ID
    square_payment_id: str                 # Square payment identifier (unique)
    square_order_id: Optional[str]         # Square order identifier
    square_customer_id: Optional[str]      # Square customer identifier

    # Ownership
    company_name: str                      # Company that owns subscription
    subscription_id: str                   # Related subscription ObjectId
    user_id: Optional[str]                 # User who made payment
    user_email: EmailStr                   # User email address

    # Payment Information
    amount: int                            # Amount in cents (e.g., 1299 = $12.99)
    currency: str = "USD"                  # Currency code (ISO 4217)
    payment_status: str                    # COMPLETED | PENDING | FAILED | REFUNDED
    payment_date: datetime                 # When payment was processed

    # Payment Method (Optional)
    payment_method: Optional[str]          # "card", "ach", etc.
    card_brand: Optional[str]              # "VISA", "MASTERCARD", etc.
    card_last_4: Optional[str]             # Last 4 digits
    receipt_url: Optional[str]             # Square receipt URL

    # Refunds
    refunds: List[RefundSchema] = []       # Array of refund objects

    # Timestamps
    created_at: datetime                   # Record creation time
    updated_at: datetime                   # Last modification time
```

### Refund Schema

```python
class RefundSchema(BaseModel):
    """Refund object in payment's refunds array"""

    refund_id: str                         # Square refund identifier
    amount: int                            # Refund amount in cents
    currency: str = "USD"                  # Currency code
    status: str                            # COMPLETED | PENDING | FAILED
    idempotency_key: str                   # Unique key for Square API
    created_at: datetime                   # Refund creation timestamp
```

### Payment Status Values

| Status | Description | Use Case |
|--------|-------------|----------|
| `COMPLETED` | Payment successfully processed | Normal successful payment |
| `PENDING` | Payment awaiting confirmation | Initial state, webhook pending |
| `FAILED` | Payment processing failed | Card declined, insufficient funds |
| `REFUNDED` | Payment has refunds | Full or partial refund processed |

### Amount Handling

**Important:** All monetary amounts are stored in **cents** (integer) to avoid floating-point precision issues.

**Examples:**
- $12.99 → `1299` cents
- $90.00 → `9000` cents
- $0.50 → `50` cents

**Conversion:**
```python
# Cents to dollars
dollars = cents / 100

# Dollars to cents
cents = int(dollars * 100)
```

---

## API Endpoints

### Admin Endpoints

#### GET /api/v1/payments

**Purpose:** Retrieve all payments across all companies (admin dashboard view)

**Authentication:** Admin token required

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | None | Filter by payment status |
| `company_name` | string | No | None | Filter by company name |
| `limit` | integer | No | 50 | Results per page (1-100) |
| `skip` | integer | No | 0 | Results to skip (pagination) |
| `sort_by` | string | No | "payment_date" | Field to sort by |
| `sort_order` | string | No | "desc" | "asc" or "desc" |

**Valid Status Values:** `COMPLETED`, `PENDING`, `FAILED`, `REFUNDED`

**Request Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED&limit=20&skip=0" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Response Example:**
```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "_id": "68fad3c2a0f41c24037c4810",
        "company_name": "Acme Health LLC",
        "user_email": "test5@yahoo.com",
        "square_payment_id": "payment_sq_1761244600756",
        "amount": 1299,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": "2025-10-24T01:17:54.544Z",
        "created_at": "2025-10-24T01:17:54.544Z",
        "updated_at": "2025-10-24T01:17:54.544Z"
      }
    ],
    "count": 1,
    "total": 125,
    "limit": 20,
    "skip": 0,
    "filters": {
      "status": "COMPLETED",
      "company_name": null
    }
  }
}
```

**Status Codes:**
- `200` - Success
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (not admin)
- `400` - Invalid parameters
- `500` - Server error

---

#### POST /api/v1/payments/subscription

**Purpose:** Manually create a subscription payment record (admin use)

**Authentication:** Admin token required

**Use Case:** Recording subscription payments received through Square

**Request Body:**
```json
{
  "company_name": "Acme Translation Corp",
  "subscription_id": "690023c7eb2bceb90e274133",
  "square_payment_id": "sq_payment_e59858fff0794614",
  "square_order_id": "sq_order_e4dce86988a847b1",
  "square_customer_id": "sq_customer_c7b478ddc7b04f99",
  "user_email": "admin@acme.com",
  "user_id": "user_9db5a0fbe769442d",
  "amount": 9000,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "payment_method": "card",
  "card_brand": "VISA",
  "card_last_4": "1234",
  "receipt_url": "https://squareup.com/receipt/preview/b05a59b993294167"
}
```

**Required Fields:**
- `company_name` - Must match subscription's company
- `subscription_id` - Must be valid ObjectId of existing subscription
- `square_payment_id` - Unique Square payment identifier
- `user_email` - Email of payment initiator
- `amount` - Amount in cents (positive integer)

**Optional Fields:**
- `square_order_id`, `square_customer_id`, `user_id`
- `currency` (default: "USD")
- `payment_status` (default: "COMPLETED")
- `payment_method` (default: "card")
- `card_brand`, `card_last_4`, `receipt_url`
- `payment_date` (default: current time)

**Validation Rules:**

1. **Subscription Validation:**
   - Subscription must exist in `subscriptions` collection
   - Subscription's `company_name` must match provided `company_name`
   - Subscription ID must be valid 24-character ObjectId

2. **Amount Validation:**
   - Must be positive integer (> 0)
   - Represents cents (no decimals)

3. **Square ID Uniqueness:**
   - `square_payment_id` must be unique
   - Prevents duplicate payment records

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Translation Corp",
    "subscription_id": "690023c7eb2bceb90e274133",
    "square_payment_id": "sq_payment_e59858fff0794614",
    "user_email": "admin@acme.com",
    "amount": 9000
  }'
```

**Success Response (201):**
```json
{
  "success": true,
  "message": "Subscription payment created successfully",
  "data": {
    "_id": "690023c7eb2bceb90e274140",
    "square_payment_id": "sq_payment_e59858fff0794614",
    "square_order_id": "sq_order_e4dce86988a847b1",
    "square_customer_id": "sq_customer_c7b478ddc7b04f99",
    "company_name": "Acme Translation Corp",
    "subscription_id": "690023c7eb2bceb90e274133",
    "user_id": "user_9db5a0fbe769442d",
    "user_email": "admin@acme.com",
    "amount": 9000,
    "currency": "USD",
    "payment_status": "COMPLETED",
    "payment_date": "2025-10-28T11:18:04.213Z",
    "payment_method": "card",
    "card_brand": "VISA",
    "card_last_4": "1234",
    "receipt_url": "https://squareup.com/receipt/preview/b05a59b993294167",
    "refunds": [],
    "created_at": "2025-10-30T12:00:00.000Z",
    "updated_at": "2025-10-30T12:00:00.000Z"
  }
}
```

**Error Responses:**

**400 - Invalid Subscription ID:**
```json
{
  "detail": "Invalid subscription_id format: must be a valid 24-character ObjectId"
}
```

**400 - Subscription Not Found:**
```json
{
  "detail": "Subscription not found with ID: 690023c7eb2bceb90e274133"
}
```

**400 - Company Mismatch:**
```json
{
  "detail": "Company name mismatch: provided 'Wrong Company' but subscription belongs to 'Acme Translation Corp'"
}
```

**401 - Unauthorized:**
```json
{
  "detail": "Authorization header missing"
}
```

**403 - Forbidden:**
```json
{
  "detail": "Admin permissions required"
}
```

---

### Company Endpoints

#### GET /api/v1/payments/company/{company_name}

**Purpose:** Get all payments for a specific company

**Authentication:** User or admin token (company access control)

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | Yes | Company name (URL encoded) |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | None | Filter by payment status |
| `limit` | integer | No | 50 | Results per page (1-100) |
| `skip` | integer | No | 0 | Results to skip (pagination) |

**Request Example:**
```bash
# Get all payments for Acme Health LLC
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC"

# Get completed payments only
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED"

# Pagination (second page, 20 per page)
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?limit=20&skip=20"
```

**Response Example:**
```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "_id": "68fad3c2a0f41c24037c4810",
        "company_name": "Acme Health LLC",
        "user_email": "test5@yahoo.com",
        "square_payment_id": "payment_sq_1761244600756",
        "amount": 1299,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": "2025-10-24T01:17:54.544Z",
        "created_at": "2025-10-24T01:17:54.544Z",
        "updated_at": "2025-10-24T01:17:54.544Z"
      },
      {
        "_id": "68fad3c2a0f41c24037c4811",
        "company_name": "Acme Health LLC",
        "user_email": "admin@acmehealth.com",
        "square_payment_id": "payment_sq_1761268674",
        "amount": 2499,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": "2025-10-24T02:30:15.123Z",
        "created_at": "2025-10-24T02:30:15.123Z",
        "updated_at": "2025-10-24T02:30:15.123Z"
      }
    ],
    "count": 2,
    "limit": 50,
    "skip": 0,
    "filters": {
      "company_name": "Acme Health LLC",
      "status": null
    }
  }
}
```

**Empty Result:**
```json
{
  "success": true,
  "data": {
    "payments": [],
    "count": 0,
    "limit": 50,
    "skip": 0,
    "filters": {
      "company_name": "Unknown Company",
      "status": null
    }
  }
}
```

**Status Codes:**
- `200` - Success (even if empty)
- `400` - Invalid company name or parameters
- `404` - Company not found
- `500` - Server error

---

### Query Endpoints

#### GET /api/v1/payments/{payment_id}

**Purpose:** Get a single payment by MongoDB ObjectId

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `payment_id` | string | Yes | MongoDB ObjectId (24 hex chars) |

**Request Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/68fad3c2a0f41c24037c4810"
```

**Response Example:**
```json
{
  "_id": "68fad3c2a0f41c24037c4810",
  "company_name": "Acme Health LLC",
  "user_email": "test5@yahoo.com",
  "square_payment_id": "payment_sq_1761244600756",
  "amount": 1299,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "refunds": [],
  "payment_date": "2025-10-24T01:17:54.544Z",
  "created_at": "2025-10-24T01:17:54.544Z",
  "updated_at": "2025-10-24T01:17:54.544Z"
}
```

**Status Codes:**
- `200` - Payment found
- `400` - Invalid ObjectId format
- `404` - Payment not found
- `500` - Server error

---

#### GET /api/v1/payments/square/{square_payment_id}

**Purpose:** Get a payment by Square payment ID

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `square_payment_id` | string | Yes | Square payment identifier |

**Request Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/sq_payment_abc123"
```

**Response:** Same as GET by ObjectId

**Status Codes:**
- `200` - Payment found
- `404` - Payment not found
- `500` - Server error

---

#### GET /api/v1/payments/email/{email}

**Purpose:** Get all payments by user email

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email` | string | Yes | User email address |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 50 | Results per page (1-100) |
| `skip` | integer | No | 0 | Results to skip (pagination) |

**Request Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/email/user@example.com"
```

**Response Example:**
```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "_id": "68fad3c2a0f41c24037c4810",
        "company_name": "Acme Health LLC",
        "user_email": "user@example.com",
        "square_payment_id": "payment_sq_1761244600756",
        "amount": 1299,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": "2025-10-24T01:17:54.544Z",
        "created_at": "2025-10-24T01:17:54.544Z",
        "updated_at": "2025-10-24T01:17:54.544Z"
      }
    ],
    "count": 1,
    "limit": 50,
    "skip": 0,
    "email": "user@example.com"
  }
}
```

**Status Codes:**
- `200` - Success (even if empty)
- `422` - Invalid email format
- `500` - Server error

---

### Transaction Endpoints

#### POST /api/v1/payments

**Purpose:** Create a generic payment record

**Authentication:** May require authentication (depends on implementation)

**Request Body:**
```json
{
  "company_name": "Acme Health LLC",
  "user_email": "test5@yahoo.com",
  "square_payment_id": "payment_sq_1761244600756",
  "amount": 1299,
  "currency": "USD",
  "payment_status": "COMPLETED"
}
```

**Required Fields:**
- `company_name`
- `user_email`
- `square_payment_id`
- `amount` (in cents)

**Optional Fields:**
- `currency` (default: "USD")
- `payment_status` (default: "PENDING")
- `payment_date` (default: current time)

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Health LLC",
    "user_email": "test5@yahoo.com",
    "square_payment_id": "payment_sq_1761244600756",
    "amount": 1299
  }'
```

**Response (201):**
```json
{
  "_id": "68fad3c2a0f41c24037c4810",
  "company_name": "Acme Health LLC",
  "user_email": "test5@yahoo.com",
  "square_payment_id": "payment_sq_1761244600756",
  "amount": 1299,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "refunds": [],
  "created_at": "2025-10-24T01:17:54.544Z",
  "updated_at": "2025-10-24T01:17:54.544Z",
  "payment_date": "2025-10-24T01:17:54.544Z"
}
```

**Status Codes:**
- `201` - Payment created
- `400` - Invalid payment data
- `500` - Server error

---

#### POST /api/v1/payments/{square_payment_id}/refund

**Purpose:** Process a payment refund

**Authentication:** Admin token recommended

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `square_payment_id` | string | Yes | Square payment identifier |

**Request Body:**
```json
{
  "refund_id": "rfn_01J2M9ABCD",
  "amount": 500,
  "currency": "USD",
  "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
}
```

**Required Fields:**
- `refund_id` - Square refund identifier
- `amount` - Refund amount in cents (must be > 0 and ≤ payment amount)
- `idempotency_key` - Unique key for idempotent refund processing

**Optional Fields:**
- `currency` (default: "USD")

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/payment_sq_1761268674/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_01J2M9ABCD",
    "amount": 500,
    "currency": "USD",
    "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
  }'
```

**Response (200):**
```json
{
  "success": true,
  "message": "Refund processed: 500 cents",
  "data": {
    "payment": {
      "_id": "68fad3c2a0f41c24037c4810",
      "company_name": "Acme Health LLC",
      "user_email": "test5@yahoo.com",
      "square_payment_id": "payment_sq_1761268674",
      "amount": 1299,
      "currency": "USD",
      "payment_status": "REFUNDED",
      "refunds": [
        {
          "refund_id": "rfn_01J2M9ABCD",
          "amount": 500,
          "currency": "USD",
          "status": "COMPLETED",
          "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62",
          "created_at": "2025-10-24T01:15:43.453Z"
        }
      ],
      "created_at": "2025-10-24T01:17:54.544Z",
      "updated_at": "2025-10-24T01:17:54.544Z",
      "payment_date": "2025-10-24T01:17:54.544Z"
    },
    "refund": {
      "refund_id": "rfn_01J2M9ABCD",
      "amount": 500,
      "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
    }
  }
}
```

**Validation Rules:**
1. Payment must exist
2. Refund amount must be > 0
3. Refund amount must be ≤ original payment amount
4. Refund is added to `refunds` array (not replacing)
5. Payment status updated to `REFUNDED`

**Error Responses:**

**400 - Refund exceeds payment:**
```json
{
  "detail": "Refund amount (1500) exceeds payment amount (1299)"
}
```

**400 - Invalid amount:**
```json
{
  "detail": "Refund amount must be greater than 0"
}
```

**404 - Payment not found:**
```json
{
  "detail": "Payment not found: payment_sq_invalid"
}
```

**Status Codes:**
- `200` - Refund processed
- `400` - Invalid refund parameters
- `404` - Payment not found
- `500` - Server error

---

### Statistics Endpoints

#### GET /api/v1/payments/company/{company_name}/stats

**Purpose:** Get payment statistics for a company

**Path Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `company_name` | string | Yes | Company name (URL encoded) |

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | None | Start date (ISO 8601) |
| `end_date` | string | No | None | End date (ISO 8601) |

**Request Example:**
```bash
# All-time stats
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats"

# Stats for date range
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats?start_date=2025-01-01T00:00:00Z&end_date=2025-12-31T23:59:59Z"
```

**Response Example:**
```json
{
  "success": true,
  "data": {
    "company_name": "Acme Health LLC",
    "total_payments": 125,
    "total_amount_cents": 1325000,
    "total_amount_dollars": 13250.00,
    "total_refunded_cents": 21200,
    "total_refunded_dollars": 212.00,
    "completed_payments": 120,
    "failed_payments": 5,
    "success_rate": 96.0,
    "date_range": {
      "start_date": "2025-01-01T00:00:00Z",
      "end_date": "2025-10-22T00:00:00Z"
    }
  }
}
```

**Statistics Calculated:**
- `total_payments` - Total number of payment records
- `total_amount_cents` - Sum of all payment amounts (cents)
- `total_amount_dollars` - Sum of all payment amounts (dollars)
- `completed_payments` - Count of COMPLETED payments
- `failed_payments` - Count of FAILED payments
- `success_rate` - Percentage of successful payments

**Status Codes:**
- `200` - Statistics retrieved
- `400` - Invalid date format
- `500` - Server error

---

## Request/Response Patterns

### Standard Response Wrapper

**Success Response:**
```json
{
  "success": true,
  "data": {
    // Actual response data
  }
}
```

**Success with Message:**
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Actual response data
  }
}
```

### Pagination Pattern

**Request:**
```
GET /api/v1/payments?limit=20&skip=40
```

**Response:**
```json
{
  "success": true,
  "data": {
    "payments": [...],
    "count": 20,        // Items in this response
    "total": 125,       // Total matching items
    "limit": 20,        // Requested limit
    "skip": 40          // Requested skip
  }
}
```

**Pagination Calculation:**
```python
# Page 1: skip=0,  limit=20
# Page 2: skip=20, limit=20
# Page 3: skip=40, limit=20

total_pages = math.ceil(total / limit)
current_page = (skip / limit) + 1
```

### Filtering Pattern

**Request:**
```
GET /api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED
```

**Response:**
```json
{
  "success": true,
  "data": {
    "payments": [...],
    "count": 15,
    "filters": {
      "company_name": "Acme Health LLC",
      "status": "COMPLETED"
    }
  }
}
```

### Date/Time Format

**All dates in ISO 8601 format:**
```
2025-10-24T01:17:54.544Z
```

**Python datetime conversion:**
```python
from datetime import datetime

# Parse ISO 8601
dt = datetime.fromisoformat("2025-10-24T01:17:54.544+00:00")

# Generate ISO 8601
iso_string = datetime.utcnow().isoformat() + "Z"
```

---

## Error Handling

### Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid parameters, validation failure |
| 401 | Unauthorized | Missing or invalid authentication token |
| 403 | Forbidden | Insufficient permissions (not admin) |
| 404 | Not Found | Resource doesn't exist |
| 422 | Unprocessable Entity | Invalid data format (e.g., bad email) |
| 500 | Internal Server Error | Server-side error |

### Common Error Scenarios

**1. Invalid ObjectId:**
```json
{
  "detail": "Invalid payment ID format: invalid_id"
}
```

**2. Subscription Not Found:**
```json
{
  "detail": "Subscription not found with ID: 690023c7eb2bceb90e274133"
}
```

**3. Company Mismatch:**
```json
{
  "detail": "Company name mismatch: provided 'Wrong Company' but subscription belongs to 'Acme Translation Corp'"
}
```

**4. Invalid Payment Status:**
```json
{
  "detail": "Invalid payment status. Must be one of: COMPLETED, PENDING, FAILED, REFUNDED"
}
```

**5. Refund Exceeds Payment:**
```json
{
  "detail": "Refund amount (1500) exceeds payment amount (1299)"
}
```

**6. Unauthorized Access:**
```json
{
  "detail": "Authorization header missing"
}
```

**7. Admin Required:**
```json
{
  "detail": "Admin permissions required"
}
```

---

## Usage Scenarios

### Scenario 1: Admin Views All Company Payments

**Goal:** Administrator wants to see all payments across all companies

**Steps:**

1. **Obtain admin token:**
```bash
TOKEN=$(curl -X POST "http://localhost:8000/api/v1/auth/admin/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"password"}' \
  | jq -r '.access_token')
```

2. **Request all payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?limit=50&skip=0" \
  -H "Authorization: Bearer $TOKEN"
```

3. **Filter by status:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED&limit=100" \
  -H "Authorization: Bearer $TOKEN"
```

4. **Filter by company:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?company_name=Acme%20Health%20LLC" \
  -H "Authorization: Bearer $TOKEN"
```

---

### Scenario 2: Company Views Their Payment History

**Goal:** Company admin wants to see their company's payment history

**Steps:**

1. **Get company payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC"
```

2. **Filter by completed payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED"
```

3. **Paginate through results:**
```bash
# Page 1
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?limit=20&skip=0"

# Page 2
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?limit=20&skip=20"
```

---

### Scenario 3: Recording a Subscription Payment

**Goal:** Admin records a new subscription payment after receiving Square webhook

**Steps:**

1. **Validate subscription exists:**
```bash
# Check subscription in database
mongo translation --eval 'db.subscriptions.findOne({_id: ObjectId("690023c7eb2bceb90e274133")})'
```

2. **Create payment record:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Translation Corp",
    "subscription_id": "690023c7eb2bceb90e274133",
    "square_payment_id": "sq_payment_e59858fff0794614",
    "square_order_id": "sq_order_e4dce86988a847b1",
    "user_email": "admin@acme.com",
    "amount": 9000,
    "payment_status": "COMPLETED",
    "card_brand": "VISA",
    "card_last_4": "1234"
  }'
```

3. **Verify payment created:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/sq_payment_e59858fff0794614"
```

---

### Scenario 4: Processing a Refund

**Goal:** Admin processes a refund for a customer

**Steps:**

1. **Find the payment:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/payment_sq_1761268674"
```

2. **Verify payment details:**
```json
{
  "_id": "68fad3c2a0f41c24037c4810",
  "amount": 1299,
  "payment_status": "COMPLETED",
  "refunds": []
}
```

3. **Process refund (partial):**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/payment_sq_1761268674/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_01J2M9ABCD",
    "amount": 500,
    "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
  }'
```

4. **Verify refund applied:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/payment_sq_1761268674"
```

5. **Expected result:**
```json
{
  "_id": "68fad3c2a0f41c24037c4810",
  "amount": 1299,
  "payment_status": "REFUNDED",
  "refunds": [
    {
      "refund_id": "rfn_01J2M9ABCD",
      "amount": 500,
      "status": "COMPLETED",
      "created_at": "2025-10-24T01:15:43.453Z"
    }
  ]
}
```

---

### Scenario 5: Generating Payment Statistics

**Goal:** Generate payment statistics for a company

**Steps:**

1. **Get all-time stats:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats"
```

2. **Get stats for specific period:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats?start_date=2025-01-01T00:00:00Z&end_date=2025-10-31T23:59:59Z"
```

3. **Analyze results:**
```json
{
  "success": true,
  "data": {
    "company_name": "Acme Health LLC",
    "total_payments": 125,
    "total_amount_dollars": 13250.00,
    "completed_payments": 120,
    "failed_payments": 5,
    "success_rate": 96.0
  }
}
```

---

## Integration Guide

### Integrating with Square Webhooks

**1. Square Webhook Configuration:**

Configure Square to send payment webhooks to your endpoint:
```
https://your-domain.com/api/v1/webhooks/square
```

**2. Webhook Handler (pseudo-code):**

```python
@router.post("/api/v1/webhooks/square")
async def handle_square_webhook(request: Request):
    """Handle Square payment webhooks"""

    # Verify webhook signature
    signature = request.headers.get("x-square-signature")
    payload = await request.body()

    if not verify_square_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse event
    event = await request.json()
    event_type = event.get("type")

    if event_type == "payment.updated":
        payment_data = event["data"]["object"]["payment"]

        # Extract payment details
        square_payment_id = payment_data["id"]
        amount = payment_data["amount_money"]["amount"]
        status = payment_data["status"]

        # Create payment record
        await create_payment_from_webhook(
            square_payment_id=square_payment_id,
            amount=amount,
            status=status,
            payment_data=payment_data
        )

    return {"status": "processed"}
```

**3. Create Payment from Webhook:**

```python
async def create_payment_from_webhook(
    square_payment_id: str,
    amount: int,
    status: str,
    payment_data: dict
):
    """Create payment record from Square webhook data"""

    # Map Square status to our status
    status_map = {
        "COMPLETED": "COMPLETED",
        "PENDING": "PENDING",
        "FAILED": "FAILED",
        "CANCELED": "FAILED"
    }

    # Create payment record
    payment_create = PaymentCreate(
        company_name=extract_company_from_metadata(payment_data),
        user_email=extract_email_from_metadata(payment_data),
        square_payment_id=square_payment_id,
        amount=amount,
        currency="USD",
        payment_status=status_map.get(status, "PENDING"),
        payment_date=datetime.fromisoformat(payment_data["created_at"])
    )

    await payment_repository.create_payment(payment_create)
```

### Linking Payments to Subscriptions

**1. Subscription Payment Flow:**

```python
async def record_subscription_payment(
    subscription_id: str,
    square_payment_id: str,
    amount: int,
    user_email: str
):
    """Record a subscription payment"""

    # Get subscription
    subscription = await database.subscriptions.find_one(
        {"_id": ObjectId(subscription_id)}
    )

    if not subscription:
        raise ValueError(f"Subscription not found: {subscription_id}")

    # Create payment record
    payment = SubscriptionPaymentCreate(
        company_name=subscription["company_name"],
        subscription_id=subscription_id,
        square_payment_id=square_payment_id,
        user_email=user_email,
        amount=amount,
        payment_status="COMPLETED"
    )

    # Save payment
    result = await database.payments.insert_one(payment.dict())

    # Update subscription last_payment_date
    await database.subscriptions.update_one(
        {"_id": ObjectId(subscription_id)},
        {"$set": {"last_payment_date": datetime.utcnow()}}
    )

    return str(result.inserted_id)
```

### Payment Status Lifecycle

```
PENDING ──────────────────┐
   │                      │
   │ (payment successful) │ (payment failed)
   ▼                      ▼
COMPLETED ────────────▶ FAILED
   │
   │ (refund processed)
   ▼
REFUNDED
```

**State Transitions:**

1. **PENDING → COMPLETED**
   - Payment successfully processed by Square
   - Webhook confirms payment

2. **PENDING → FAILED**
   - Payment declined
   - Insufficient funds
   - Card error

3. **COMPLETED → REFUNDED**
   - Refund processed (full or partial)
   - Refund added to `refunds` array

4. **Terminal States:**
   - `COMPLETED` (can transition to REFUNDED)
   - `FAILED` (terminal)
   - `REFUNDED` (terminal)

---

## Testing Guide

### Testing with cURL

**1. Set environment variables:**
```bash
export API_URL="http://localhost:8000"
export ADMIN_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**2. Test admin endpoints:**
```bash
# Get all payments
curl -X GET "$API_URL/api/v1/payments" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Create subscription payment
curl -X POST "$API_URL/api/v1/payments/subscription" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d @test_data/subscription_payment.json
```

**3. Test company endpoints:**
```bash
# Get company payments
curl -X GET "$API_URL/api/v1/payments/company/Acme%20Health%20LLC"

# Get with filters
curl -X GET "$API_URL/api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED&limit=10"
```

**4. Test refund processing:**
```bash
curl -X POST "$API_URL/api/v1/payments/payment_sq_123/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_test_123",
    "amount": 500,
    "idempotency_key": "test_refund_key_1"
  }'
```

### Testing with Python

**1. Setup test client:**
```python
import requests
from datetime import datetime

class PaymentsAPIClient:
    def __init__(self, base_url: str, admin_token: str):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }

    def get_all_payments(self, status=None, limit=50, skip=0):
        """Get all payments (admin)"""
        params = {"limit": limit, "skip": skip}
        if status:
            params["status"] = status

        response = requests.get(
            f"{self.base_url}/api/v1/payments",
            headers=self.headers,
            params=params
        )
        return response.json()

    def create_subscription_payment(self, payment_data: dict):
        """Create subscription payment"""
        response = requests.post(
            f"{self.base_url}/api/v1/payments/subscription",
            headers=self.headers,
            json=payment_data
        )
        return response.json()

    def get_company_payments(self, company_name: str, status=None):
        """Get payments for a company"""
        params = {}
        if status:
            params["status"] = status

        response = requests.get(
            f"{self.base_url}/api/v1/payments/company/{company_name}",
            params=params
        )
        return response.json()

    def process_refund(self, square_payment_id: str, refund_data: dict):
        """Process a refund"""
        response = requests.post(
            f"{self.base_url}/api/v1/payments/{square_payment_id}/refund",
            headers=self.headers,
            json=refund_data
        )
        return response.json()
```

**2. Example test:**
```python
# Initialize client
client = PaymentsAPIClient(
    base_url="http://localhost:8000",
    admin_token="your_admin_token_here"
)

# Test: Get all completed payments
result = client.get_all_payments(status="COMPLETED", limit=10)
print(f"Found {result['data']['count']} completed payments")

# Test: Create subscription payment
payment_data = {
    "company_name": "Test Company",
    "subscription_id": "690023c7eb2bceb90e274133",
    "square_payment_id": f"test_payment_{int(datetime.utcnow().timestamp())}",
    "user_email": "test@example.com",
    "amount": 5000
}
result = client.create_subscription_payment(payment_data)
print(f"Payment created: {result['data']['_id']}")

# Test: Get company payments
result = client.get_company_payments("Test Company")
print(f"Company has {result['data']['count']} payments")
```

### Sample Test Data

**1. Subscription Payment (valid):**
```json
{
  "company_name": "Test Company Inc",
  "subscription_id": "690023c7eb2bceb90e274133",
  "square_payment_id": "sq_payment_test_001",
  "user_email": "admin@testcompany.com",
  "amount": 9000,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "payment_method": "card",
  "card_brand": "VISA",
  "card_last_4": "4242"
}
```

**2. Generic Payment:**
```json
{
  "company_name": "Test Company Inc",
  "user_email": "user@testcompany.com",
  "square_payment_id": "payment_sq_test_002",
  "amount": 1299,
  "currency": "USD",
  "payment_status": "COMPLETED"
}
```

**3. Refund Request:**
```json
{
  "refund_id": "rfn_test_001",
  "amount": 500,
  "currency": "USD",
  "idempotency_key": "rfd_unique_key_001"
}
```

### Expected Test Results

**1. Create Payment → Success:**
- Status: 201 Created
- Response contains `_id`, timestamps
- Payment retrievable by ID

**2. Get Payments → Success:**
- Status: 200 OK
- Returns array of payments
- Pagination works correctly

**3. Process Refund → Success:**
- Status: 200 OK
- Refund added to `refunds` array
- Payment status changed to `REFUNDED`

**4. Invalid Subscription → Error:**
- Status: 400 Bad Request
- Error: "Subscription not found"

**5. Refund Exceeds Payment → Error:**
- Status: 400 Bad Request
- Error: "Refund amount exceeds payment amount"

---

## Best Practices

### 1. Amount Handling

**Always use cents (integers):**
```python
# ✅ Good
amount = 1299  # $12.99

# ❌ Bad
amount = 12.99  # Floating point precision issues
```

**Convert for display:**
```python
def format_amount(cents: int, currency: str = "USD") -> str:
    """Format cents as currency string"""
    dollars = cents / 100
    return f"${dollars:.2f} {currency}"

# Example
print(format_amount(1299))  # "$12.99 USD"
```

### 2. Idempotency

**Use unique idempotency keys for refunds:**
```python
import uuid

idempotency_key = f"rfd_{uuid.uuid4()}"
```

**Check for existing refunds before processing:**
```python
async def safe_process_refund(payment_id: str, refund_data: dict):
    """Process refund with duplicate check"""

    # Check if refund already exists
    payment = await payment_repository.get_payment_by_square_id(payment_id)

    for refund in payment.get("refunds", []):
        if refund["idempotency_key"] == refund_data["idempotency_key"]:
            # Refund already processed
            return refund

    # Process new refund
    return await payment_repository.process_refund(payment_id, refund_data)
```

### 3. Error Handling

**Wrap API calls in try-except:**
```python
try:
    result = await client.create_subscription_payment(payment_data)
except HTTPException as e:
    if e.status_code == 400:
        # Handle validation errors
        logger.error(f"Validation error: {e.detail}")
    elif e.status_code == 404:
        # Handle not found
        logger.error(f"Resource not found: {e.detail}")
    else:
        # Handle other errors
        logger.error(f"API error: {e.status_code} - {e.detail}")
    raise
```

### 4. Pagination

**Iterate through all pages:**
```python
async def get_all_company_payments(company_name: str):
    """Get all payments for a company (all pages)"""
    all_payments = []
    skip = 0
    limit = 100

    while True:
        result = await client.get_company_payments(
            company_name=company_name,
            limit=limit,
            skip=skip
        )

        payments = result["data"]["payments"]
        all_payments.extend(payments)

        # Check if there are more pages
        if len(payments) < limit:
            break

        skip += limit

    return all_payments
```

### 5. Date Filtering

**Use ISO 8601 format for date filters:**
```python
from datetime import datetime, timezone

# Generate date range
start_date = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
end_date = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc).isoformat()

# Query with date range
result = await client.get_payment_stats(
    company_name="Acme Health LLC",
    start_date=start_date,
    end_date=end_date
)
```

### 6. Company Name Handling

**URL encode company names:**
```python
from urllib.parse import quote

company_name = "Acme Health LLC"
encoded_name = quote(company_name)  # "Acme%20Health%20LLC"

url = f"/api/v1/payments/company/{encoded_name}"
```

### 7. Validation Before Creating Payments

**Validate subscription before creating payment:**
```python
async def create_payment_with_validation(payment_data: dict):
    """Create payment with pre-validation"""

    # Validate subscription exists
    subscription = await database.subscriptions.find_one({
        "_id": ObjectId(payment_data["subscription_id"])
    })

    if not subscription:
        raise ValueError("Subscription not found")

    # Validate company match
    if subscription["company_name"] != payment_data["company_name"]:
        raise ValueError("Company name mismatch")

    # Create payment
    return await payment_repository.create_payment(payment_data)
```

### 8. Refund Validation

**Validate refund amount:**
```python
def validate_refund_amount(payment_amount: int, refund_amount: int, existing_refunds: list):
    """Validate refund amount is valid"""

    # Calculate total refunded
    total_refunded = sum(r["amount"] for r in existing_refunds)

    # Check remaining amount
    remaining = payment_amount - total_refunded

    if refund_amount > remaining:
        raise ValueError(
            f"Refund amount ({refund_amount}) exceeds remaining amount ({remaining})"
        )

    if refund_amount <= 0:
        raise ValueError("Refund amount must be positive")
```

### 9. Logging

**Log important payment events:**
```python
import logging

logger = logging.getLogger(__name__)

async def create_payment(payment_data):
    logger.info(
        f"Creating payment: company={payment_data.company_name}, "
        f"amount={payment_data.amount}, "
        f"square_id={payment_data.square_payment_id}"
    )

    try:
        result = await payment_repository.create_payment(payment_data)
        logger.info(f"Payment created successfully: {result}")
        return result
    except Exception as e:
        logger.error(f"Failed to create payment: {e}", exc_info=True)
        raise
```

### 10. Monitoring

**Track key metrics:**
```python
# Track payment creation rate
payments_created_counter.inc()

# Track refund processing
refunds_processed_counter.inc()

# Track errors
payment_errors_counter.labels(error_type="validation").inc()

# Track payment amounts
payment_amount_histogram.observe(payment_data.amount / 100)
```

---

## Appendix

### Glossary

| Term | Definition |
|------|------------|
| **Payment** | A financial transaction record for a subscription |
| **Refund** | A return of funds to the customer |
| **Square Payment ID** | Unique identifier from Square payment processor |
| **Subscription** | Recurring payment plan for translation services |
| **Idempotency Key** | Unique key ensuring operation runs once only |
| **ObjectId** | MongoDB's 24-character hexadecimal identifier |
| **Cents** | Monetary amount in smallest currency unit (1/100 dollar) |

### Related Documentation

- [Subscriptions API](./SUBSCRIPTIONS_API.md)
- [User Transactions API](./USER_TRANSACTIONS_API.md)
- [Admin Setup Guide](./ADMIN_SETUP.md)
- [MongoDB Integration](./MONGODB_INTEGRATION.md)

### API Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2025-10-30 | Complete documentation rewrite, added subscription payment endpoint |
| 1.1.0 | 2025-10-24 | Added admin all-payments endpoint, improved pagination |
| 1.0.0 | 2025-10-15 | Initial payments API release |

### Support

For issues or questions:
- GitHub Issues: https://github.com/your-org/translation-service/issues
- Email: support@example.com
- Slack: #translation-api-support

---

**End of Documentation**
