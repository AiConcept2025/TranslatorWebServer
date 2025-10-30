# Payment Management API - OpenAPI Documentation

**Version:** 1.0.0
**Base URL:** `/api/v1/payments`
**Tag:** Payment Management

---

## Table of Contents

1. [Overview](#overview)
2. [Payment Schema](#payment-schema)
3. [Endpoints](#endpoints)
   - [GET /api/v1/payments](#get-apiv1payments) - **NEW**
   - [POST /api/v1/payments](#post-apiv1payments)
   - [GET /api/v1/payments/{payment_id}](#get-apiv1paymentspayment_id)
   - [GET /api/v1/payments/square/{square_payment_id}](#get-apiv1paymentssquaresquare_payment_id)
   - [GET /api/v1/payments/company/{company_name}](#get-apiv1paymentscompanycompany_name)
   - [GET /api/v1/payments/email/{email}](#get-apiv1paymentsemailemail)
   - [PATCH /api/v1/payments/{square_payment_id}](#patch-apiv1paymentssquare_payment_id)
   - [POST /api/v1/payments/{square_payment_id}/refund](#post-apiv1paymentssquare_payment_idrefund)
   - [GET /api/v1/payments/company/{company_name}/stats](#get-apiv1paymentscompanycompany_namestats)
4. [Response Codes](#response-codes)
5. [Examples](#examples)

---

## Overview

The Payment Management API provides comprehensive endpoints for managing subscription payments processed through Square. All payment records track individual transactions including amounts, statuses, refunds, and customer information.

### Key Features

- Admin dashboard view of all payments
- Company-specific payment queries
- User email payment history
- Payment status tracking (COMPLETED, PENDING, FAILED, REFUNDED)
- Refund processing and tracking
- Payment statistics aggregation
- Pagination support
- Filter by payment status

### Authentication

**Note:** Authentication requirements depend on endpoint. Admin endpoints require elevated permissions.

---

## Payment Schema

### PaymentResponse

```json
{
  "_id": "string (MongoDB ObjectId)",
  "company_name": "string",
  "user_email": "string (email format)",
  "square_payment_id": "string",
  "amount": "integer (cents)",
  "currency": "string",
  "payment_status": "string (COMPLETED | PENDING | FAILED | REFUNDED)",
  "refunds": [
    {
      "refund_id": "string",
      "amount": "integer (cents)",
      "currency": "string",
      "status": "string (COMPLETED | PENDING | FAILED)",
      "idempotency_key": "string",
      "created_at": "string (ISO 8601)"
    }
  ],
  "payment_date": "string (ISO 8601)",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `_id` | string | MongoDB ObjectId (24-character hex string) |
| `company_name` | string | Full company name (subscription owner) |
| `user_email` | string | Email address of user who initiated payment |
| `square_payment_id` | string | Square payment identifier (unique) |
| `amount` | integer | Payment amount in cents (e.g., 1299 = $12.99) |
| `currency` | string | Currency code (ISO 4217, typically USD) |
| `payment_status` | string | Current payment status |
| `refunds` | array | Array of refund objects (empty if no refunds) |
| `payment_date` | string | Payment processing date (ISO 8601) |
| `created_at` | string | Record creation timestamp (ISO 8601) |
| `updated_at` | string | Last update timestamp (ISO 8601) |

### Payment Status Values

- `COMPLETED` - Payment successfully processed
- `PENDING` - Payment awaiting processing
- `FAILED` - Payment processing failed
- `REFUNDED` - Payment has been fully or partially refunded

---

## Endpoints

---

### GET /api/v1/payments

**NEW ENDPOINT** - Retrieve all subscription payments with filtering and pagination (admin view).

#### Description

Returns a paginated list of ALL payment records across all companies and users. This endpoint is designed for administrative dashboards to monitor all subscription payments in the system.

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | - | Filter by payment status: `COMPLETED`, `PENDING`, `FAILED`, `REFUNDED` |
| `company_name` | string | No | - | Filter by specific company name |
| `limit` | integer | No | 50 | Maximum results to return (1-100) |
| `skip` | integer | No | 0 | Number of results to skip (pagination offset) |
| `start_date` | string | No | - | Filter payments from this date (ISO 8601) |
| `end_date` | string | No | - | Filter payments until this date (ISO 8601) |

#### Response Schema

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
    "limit": 50,
    "skip": 0,
    "filters": {
      "status": "COMPLETED",
      "company_name": null,
      "start_date": null,
      "end_date": null
    },
    "page_info": {
      "current_page": 1,
      "total_pages": 3,
      "has_next": true,
      "has_previous": false
    }
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `payments` | array | Array of payment records |
| `count` | integer | Number of payments in current response |
| `total` | integer | Total number of payments matching filters |
| `limit` | integer | Limit value used |
| `skip` | integer | Skip value used |
| `filters` | object | Applied filter values |
| `page_info` | object | Pagination metadata |

#### Status Codes

- **200 OK** - Successfully retrieved payments
- **400 Bad Request** - Invalid query parameters
- **401 Unauthorized** - Authentication required
- **403 Forbidden** - Insufficient permissions (admin required)
- **500 Internal Server Error** - Server error

#### cURL Examples

**Get all completed payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED&limit=20" \
     -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Get payments for specific company:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?company_name=Acme%20Health%20LLC" \
     -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Get payments within date range:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?start_date=2025-01-01T00:00:00Z&end_date=2025-12-31T23:59:59Z" \
     -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Paginated request (second page):**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?limit=50&skip=50" \
     -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

#### OpenAPI Specification

```yaml
/api/v1/payments:
  get:
    tags:
      - Payment Management
    summary: Get all subscription payments (admin)
    description: |
      Retrieve all payment records across all companies and users with filtering and pagination.

      **Admin Access Required**

      This endpoint provides a comprehensive view of all subscription payments in the system,
      suitable for administrative dashboards and financial reporting.
    operationId: getAllPayments
    parameters:
      - name: status
        in: query
        description: Filter by payment status
        required: false
        schema:
          type: string
          enum: [COMPLETED, PENDING, FAILED, REFUNDED]
        example: COMPLETED
      - name: company_name
        in: query
        description: Filter by company name
        required: false
        schema:
          type: string
        example: "Acme Health LLC"
      - name: limit
        in: query
        description: Maximum number of results (1-100)
        required: false
        schema:
          type: integer
          minimum: 1
          maximum: 100
          default: 50
        example: 50
      - name: skip
        in: query
        description: Number of results to skip for pagination
        required: false
        schema:
          type: integer
          minimum: 0
          default: 0
        example: 0
      - name: start_date
        in: query
        description: Filter payments from this date (ISO 8601)
        required: false
        schema:
          type: string
          format: date-time
        example: "2025-01-01T00:00:00Z"
      - name: end_date
        in: query
        description: Filter payments until this date (ISO 8601)
        required: false
        schema:
          type: string
          format: date-time
        example: "2025-12-31T23:59:59Z"
    responses:
      '200':
        description: Successfully retrieved payments
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PaymentListResponse'
            examples:
              all_payments:
                summary: All payments
                value:
                  success: true
                  data:
                    payments:
                      - _id: "68fad3c2a0f41c24037c4810"
                        company_name: "Acme Health LLC"
                        user_email: "test5@yahoo.com"
                        square_payment_id: "payment_sq_1761244600756"
                        amount: 1299
                        currency: "USD"
                        payment_status: "COMPLETED"
                        refunds: []
                        payment_date: "2025-10-24T01:17:54.544Z"
                        created_at: "2025-10-24T01:17:54.544Z"
                        updated_at: "2025-10-24T01:17:54.544Z"
                      - _id: "68fad3c2a0f41c24037c4811"
                        company_name: "TechCorp Inc"
                        user_email: "admin@techcorp.com"
                        square_payment_id: "payment_sq_1761268674"
                        amount: 2499
                        currency: "USD"
                        payment_status: "COMPLETED"
                        refunds: []
                        payment_date: "2025-10-24T02:30:15.123Z"
                        created_at: "2025-10-24T02:30:15.123Z"
                        updated_at: "2025-10-24T02:30:15.123Z"
                    count: 2
                    total: 125
                    limit: 50
                    skip: 0
                    filters:
                      status: null
                      company_name: null
                      start_date: null
                      end_date: null
                    page_info:
                      current_page: 1
                      total_pages: 3
                      has_next: true
                      has_previous: false
              filtered_completed:
                summary: Filtered by status
                value:
                  success: true
                  data:
                    payments:
                      - _id: "68fad3c2a0f41c24037c4810"
                        company_name: "Acme Health LLC"
                        user_email: "test5@yahoo.com"
                        square_payment_id: "payment_sq_1761244600756"
                        amount: 1299
                        currency: "USD"
                        payment_status: "COMPLETED"
                        refunds: []
                        payment_date: "2025-10-24T01:17:54.544Z"
                        created_at: "2025-10-24T01:17:54.544Z"
                        updated_at: "2025-10-24T01:17:54.544Z"
                    count: 1
                    total: 100
                    limit: 50
                    skip: 0
                    filters:
                      status: "COMPLETED"
                      company_name: null
                      start_date: null
                      end_date: null
                    page_info:
                      current_page: 1
                      total_pages: 2
                      has_next: true
                      has_previous: false
      '400':
        description: Invalid request parameters
        content:
          application/json:
            examples:
              invalid_status:
                summary: Invalid status value
                value:
                  detail: "Invalid payment status. Must be one of: COMPLETED, PENDING, FAILED, REFUNDED"
              invalid_date:
                summary: Invalid date format
                value:
                  detail: "Invalid date format. Use ISO 8601 format (e.g., 2025-01-01T00:00:00Z)"
      '401':
        description: Authentication required
        content:
          application/json:
            example:
              detail: "Not authenticated"
      '403':
        description: Insufficient permissions
        content:
          application/json:
            example:
              detail: "Admin access required"
      '500':
        description: Internal server error
        content:
          application/json:
            example:
              detail: "Failed to retrieve payments: Database connection error"
    security:
      - BearerAuth: []
```

---

### POST /api/v1/payments

Create a new payment record.

#### Description

Creates a payment record in the database with Square payment details. This endpoint is typically called after successful payment processing through Square.

#### Request Body

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

#### Required Fields

- `company_name` - Company name
- `user_email` - User email address
- `square_payment_id` - Square payment ID (must be unique)
- `amount` - Payment amount in cents

#### Optional Fields

- `currency` - Currency code (default: "USD")
- `payment_status` - Payment status (default: "PENDING")
- `payment_date` - Payment date (default: current timestamp)

#### Response

**201 Created**

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

#### Status Codes

- **201 Created** - Payment created successfully
- **400 Bad Request** - Invalid payment data or duplicate square_payment_id
- **500 Internal Server Error** - Database error

#### cURL Example

```bash
curl -X POST "http://localhost:8000/api/v1/payments" \
     -H "Content-Type: application/json" \
     -d '{
       "company_name": "Acme Health LLC",
       "user_email": "test5@yahoo.com",
       "square_payment_id": "payment_sq_1761244600756",
       "amount": 1299,
       "currency": "USD",
       "payment_status": "COMPLETED"
     }'
```

---

### GET /api/v1/payments/{payment_id}

Get payment by MongoDB ObjectId.

#### Description

Retrieves a single payment record using its MongoDB `_id`.

#### Path Parameters

- `payment_id` - MongoDB ObjectId (24-character hex string)

#### Response

**200 OK**

```json
{
  "_id": "68ec42a48ca6a1781d9fe5c2",
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

#### Status Codes

- **200 OK** - Payment found
- **400 Bad Request** - Invalid ObjectId format
- **404 Not Found** - Payment not found
- **500 Internal Server Error** - Server error

#### cURL Example

```bash
curl -X GET "http://localhost:8000/api/v1/payments/68ec42a48ca6a1781d9fe5c2"
```

---

### GET /api/v1/payments/square/{square_payment_id}

Get payment by Square payment ID.

#### Description

Retrieves a payment record using the Square payment identifier. Returns the full payment document with all fields.

#### Path Parameters

- `square_payment_id` - Square payment ID (e.g., "payment_sq_1761244600756")

#### Response

**200 OK** - Returns full payment document (may include additional Square-specific fields)

#### Status Codes

- **200 OK** - Payment found
- **404 Not Found** - Payment not found
- **500 Internal Server Error** - Server error

#### cURL Example

```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/payment_sq_1761244600756"
```

---

### GET /api/v1/payments/company/{company_name}

Get all payments for a company with filtering and pagination.

#### Description

Retrieves payment records for a specific company. Supports filtering by payment status and pagination.

#### Path Parameters

- `company_name` - Company name (e.g., "Acme Health LLC")
  - **Note:** Space characters should be URL-encoded as `%20`

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | - | Filter by status: `COMPLETED`, `PENDING`, `FAILED`, `REFUNDED` |
| `limit` | integer | No | 50 | Maximum results (1-100) |
| `skip` | integer | No | 0 | Results to skip (pagination) |

#### Response

**200 OK**

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
    "limit": 50,
    "skip": 0,
    "filters": {
      "company_name": "Acme Health LLC",
      "status": "COMPLETED"
    }
  }
}
```

#### Status Codes

- **200 OK** - Successfully retrieved payments (may return empty array)
- **400 Bad Request** - Invalid parameters
- **404 Not Found** - Company not found
- **500 Internal Server Error** - Server error

#### cURL Examples

**Get all completed payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED&limit=20"
```

**Get second page of payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?skip=20&limit=20"
```

**Get all payments (no filter):**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC"
```

---

### GET /api/v1/payments/email/{email}

Get all payments by user email.

#### Description

Retrieves payment records associated with a specific email address.

#### Path Parameters

- `email` - User email address (must be valid email format)

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | 50 | Maximum results (1-100) |
| `skip` | integer | No | 0 | Results to skip (pagination) |

#### Response

**200 OK**

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
    "limit": 50,
    "skip": 0,
    "email": "test5@yahoo.com"
  }
}
```

#### Status Codes

- **200 OK** - Successfully retrieved payments (may return empty array)
- **422 Unprocessable Entity** - Invalid email format
- **500 Internal Server Error** - Server error

#### cURL Example

```bash
curl -X GET "http://localhost:8000/api/v1/payments/email/user@example.com"
```

---

### PATCH /api/v1/payments/{square_payment_id}

Update a payment record.

#### Description

Updates payment information such as status, refund details, or notes.

#### Path Parameters

- `square_payment_id` - Square payment ID

#### Request Body

```json
{
  "payment_status": "REFUNDED",
  "notes": "Full refund processed"
}
```

#### Response

**200 OK**

```json
{
  "success": true,
  "message": "Payment updated successfully",
  "data": {
    "_id": "68fad3c2a0f41c24037c4810",
    "company_name": "Acme Health LLC",
    "user_email": "test5@yahoo.com",
    "square_payment_id": "payment_sq_1761244600756",
    "amount": 1299,
    "currency": "USD",
    "payment_status": "REFUNDED",
    "refunds": [],
    "payment_date": "2025-10-24T01:17:54.544Z",
    "created_at": "2025-10-24T01:17:54.544Z",
    "updated_at": "2025-10-24T05:30:00.000Z"
  }
}
```

#### Status Codes

- **200 OK** - Payment updated successfully
- **400 Bad Request** - Invalid update data
- **404 Not Found** - Payment not found
- **500 Internal Server Error** - Server error

#### cURL Example

```bash
curl -X PATCH "http://localhost:8000/api/v1/payments/payment_sq_1761244600756" \
     -H "Content-Type: application/json" \
     -d '{"payment_status":"COMPLETED","notes":"Payment verified"}'
```

---

### POST /api/v1/payments/{square_payment_id}/refund

Process a payment refund.

#### Description

Marks a payment as refunded and records refund details in the refunds array.

#### Path Parameters

- `square_payment_id` - Square payment ID

#### Request Body

```json
{
  "refund_id": "rfn_01J2M9ABCD",
  "amount": 500,
  "currency": "USD",
  "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
}
```

#### Required Fields

- `refund_id` - Square refund ID
- `amount` - Refund amount in cents (must be > 0 and ≤ payment amount)
- `currency` - Currency code (default: "USD")
- `idempotency_key` - Unique idempotency key for Square API

#### Response

**200 OK**

```json
{
  "success": true,
  "message": "Refund processed: 500 cents",
  "data": {
    "payment": {
      "_id": "68fad3c2a0f41c24037c4810",
      "company_name": "Acme Health LLC",
      "user_email": "test5@yahoo.com",
      "square_payment_id": "payment_sq_1761268674_852e5fe3",
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

#### Status Codes

- **200 OK** - Refund processed successfully
- **400 Bad Request** - Invalid refund parameters or amount exceeds payment
- **404 Not Found** - Payment not found
- **500 Internal Server Error** - Server error

#### cURL Example

```bash
curl -X POST "http://localhost:8000/api/v1/payments/payment_sq_1761268674_852e5fe3/refund" \
     -H "Content-Type: application/json" \
     -d '{
       "refund_id": "rfn_01J2M9ABCD",
       "amount": 500,
       "currency": "USD",
       "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
     }'
```

---

### GET /api/v1/payments/company/{company_name}/stats

Get payment statistics for a company.

#### Description

Retrieves aggregated payment statistics including total payments, amounts, refunds, and success/failure rates.

#### Path Parameters

- `company_name` - Company name

#### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_date` | string | No | - | Start date filter (ISO 8601) |
| `end_date` | string | No | - | End date filter (ISO 8601) |

#### Response

**200 OK**

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

#### Status Codes

- **200 OK** - Statistics retrieved successfully
- **400 Bad Request** - Invalid company name or date format
- **500 Internal Server Error** - Server error

#### cURL Examples

**Get all-time stats:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats"
```

**Get stats for date range:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats?start_date=2025-01-01T00:00:00Z&end_date=2025-12-31T23:59:59Z"
```

---

## Response Codes

### Success Codes

| Code | Description |
|------|-------------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |

### Client Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters or data |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 422 | Unprocessable Entity - Validation error |

### Server Error Codes

| Code | Description |
|------|-------------|
| 500 | Internal Server Error - Unexpected server error |

---

## Examples

### Complete Workflow: Create Payment → Query → Refund

#### 1. Create Payment

```bash
curl -X POST "http://localhost:8000/api/v1/payments" \
     -H "Content-Type: application/json" \
     -d '{
       "company_name": "Acme Health LLC",
       "user_email": "test5@yahoo.com",
       "square_payment_id": "payment_sq_12345",
       "amount": 1299,
       "payment_status": "COMPLETED"
     }'
```

**Response:**
```json
{
  "_id": "68fad3c2a0f41c24037c4810",
  "company_name": "Acme Health LLC",
  "user_email": "test5@yahoo.com",
  "square_payment_id": "payment_sq_12345",
  "amount": 1299,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "refunds": [],
  "payment_date": "2025-10-24T01:17:54.544Z",
  "created_at": "2025-10-24T01:17:54.544Z",
  "updated_at": "2025-10-24T01:17:54.544Z"
}
```

#### 2. Query by Company

```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED"
```

#### 3. Process Refund

```bash
curl -X POST "http://localhost:8000/api/v1/payments/payment_sq_12345/refund" \
     -H "Content-Type: application/json" \
     -d '{
       "refund_id": "rfn_ABC123",
       "amount": 500,
       "currency": "USD",
       "idempotency_key": "rfd_unique_key_123"
     }'
```

---

## Additional Notes

### Amount Precision

All monetary amounts are stored and transmitted as **integers in cents**:
- $12.99 = 1299 cents
- $0.50 = 50 cents
- $100.00 = 10000 cents

This prevents floating-point precision errors in financial calculations.

### Date Formats

All datetime fields use **ISO 8601** format:
```
2025-10-24T01:17:54.544Z
```

### URL Encoding

Company names and emails in URLs must be **URL-encoded**:
- `Acme Health LLC` → `Acme%20Health%20LLC`
- `test+user@example.com` → `test%2Buser%40example.com`

### Refund Tracking

The `refunds` array maintains a complete history:
- Multiple refunds are supported (partial refunds)
- Each refund has its own status
- Refund sum may be less than or equal to payment amount
- Payment status changes to `REFUNDED` after any refund is processed

### Pagination Best Practices

For large result sets:
1. Use `limit` and `skip` parameters
2. Default limit is 50, maximum is 100
3. Calculate pages: `total_pages = ceil(total / limit)`
4. Next page: `skip = current_page * limit`

---

## OpenAPI Schema Components

### PaymentListResponse

```yaml
PaymentListResponse:
  type: object
  required:
    - success
    - data
  properties:
    success:
      type: boolean
      description: Indicates request success
    data:
      type: object
      required:
        - payments
        - count
        - limit
        - skip
        - filters
      properties:
        payments:
          type: array
          items:
            $ref: '#/components/schemas/Payment'
        count:
          type: integer
          description: Number of payments in response
        total:
          type: integer
          description: Total payments matching filters
        limit:
          type: integer
          description: Limit value used
        skip:
          type: integer
          description: Skip value used
        filters:
          type: object
          properties:
            status:
              type: string
              nullable: true
            company_name:
              type: string
              nullable: true
            start_date:
              type: string
              format: date-time
              nullable: true
            end_date:
              type: string
              format: date-time
              nullable: true
        page_info:
          type: object
          properties:
            current_page:
              type: integer
            total_pages:
              type: integer
            has_next:
              type: boolean
            has_previous:
              type: boolean
```

### Payment

```yaml
Payment:
  type: object
  required:
    - _id
    - company_name
    - user_email
    - square_payment_id
    - amount
    - currency
    - payment_status
    - refunds
    - payment_date
    - created_at
    - updated_at
  properties:
    _id:
      type: string
      pattern: '^[0-9a-fA-F]{24}$'
      description: MongoDB ObjectId
      example: "68fad3c2a0f41c24037c4810"
    company_name:
      type: string
      description: Company name
      example: "Acme Health LLC"
    user_email:
      type: string
      format: email
      description: User email address
      example: "test5@yahoo.com"
    square_payment_id:
      type: string
      description: Square payment identifier
      example: "payment_sq_1761244600756"
    amount:
      type: integer
      minimum: 1
      description: Payment amount in cents
      example: 1299
    currency:
      type: string
      description: Currency code (ISO 4217)
      example: "USD"
    payment_status:
      type: string
      enum: [COMPLETED, PENDING, FAILED, REFUNDED]
      description: Current payment status
      example: "COMPLETED"
    refunds:
      type: array
      items:
        $ref: '#/components/schemas/Refund'
      description: Array of refund objects
    payment_date:
      type: string
      format: date-time
      description: Payment processing date
      example: "2025-10-24T01:17:54.544Z"
    created_at:
      type: string
      format: date-time
      description: Record creation timestamp
      example: "2025-10-24T01:17:54.544Z"
    updated_at:
      type: string
      format: date-time
      description: Last update timestamp
      example: "2025-10-24T01:17:54.544Z"
```

### Refund

```yaml
Refund:
  type: object
  required:
    - refund_id
    - amount
    - currency
    - status
    - idempotency_key
    - created_at
  properties:
    refund_id:
      type: string
      description: Square refund identifier
      example: "rfn_01J2M9ABCD"
    amount:
      type: integer
      minimum: 1
      description: Refund amount in cents
      example: 500
    currency:
      type: string
      description: Currency code
      example: "USD"
    status:
      type: string
      enum: [COMPLETED, PENDING, FAILED]
      description: Refund status
      example: "COMPLETED"
    idempotency_key:
      type: string
      description: Unique idempotency key for Square API
      example: "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
    created_at:
      type: string
      format: date-time
      description: Refund creation timestamp
      example: "2025-10-24T01:15:43.453Z"
```

---

**End of Payment Management API Documentation**
