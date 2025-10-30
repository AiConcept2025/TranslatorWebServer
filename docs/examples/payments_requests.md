# Payments API - Request/Response Examples

Complete examples of all payment API endpoints with realistic request and response data.

---

## Table of Contents

1. [Admin Endpoints](#admin-endpoints)
2. [Company Endpoints](#company-endpoints)
3. [Query Endpoints](#query-endpoints)
4. [Transaction Endpoints](#transaction-endpoints)
5. [Statistics Endpoints](#statistics-endpoints)

---

## Admin Endpoints

### GET /api/v1/payments - Get All Payments

#### Example 1: Get First 50 Payments (Default)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Response (200 OK):**
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
        "company_name": "TechCorp Inc",
        "user_email": "admin@techcorp.com",
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
    "total": 125,
    "limit": 50,
    "skip": 0,
    "filters": {
      "status": null,
      "company_name": null
    }
  }
}
```

---

#### Example 2: Filter by Status (COMPLETED)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED&limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Response (200 OK):**
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
    "total": 120,
    "limit": 10,
    "skip": 0,
    "filters": {
      "status": "COMPLETED",
      "company_name": null
    }
  }
}
```

---

#### Example 3: Filter by Company and Status

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED&company_name=Acme%20Health%20LLC" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Response (200 OK):**
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
    "total": 15,
    "limit": 50,
    "skip": 0,
    "filters": {
      "status": "COMPLETED",
      "company_name": "Acme Health LLC"
    }
  }
}
```

---

#### Example 4: Pagination (Second Page)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?limit=20&skip=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "_id": "68fad3c2a0f41c24037c4821",
        "company_name": "Global Translations Ltd",
        "user_email": "billing@globaltrans.com",
        "square_payment_id": "payment_sq_1761300000",
        "amount": 5000,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": "2025-10-23T15:00:00.000Z",
        "created_at": "2025-10-23T15:00:00.000Z",
        "updated_at": "2025-10-23T15:00:00.000Z"
      }
    ],
    "count": 20,
    "total": 125,
    "limit": 20,
    "skip": 20,
    "filters": {
      "status": null,
      "company_name": null
    }
  }
}
```

---

#### Example 5: Sort by Amount (Ascending)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?sort_by=amount&sort_order=asc&limit=5" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "_id": "68fad3c2a0f41c24037c4899",
        "company_name": "Small Biz Inc",
        "user_email": "owner@smallbiz.com",
        "square_payment_id": "payment_sq_1761100000",
        "amount": 999,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": "2025-10-22T10:00:00.000Z",
        "created_at": "2025-10-22T10:00:00.000Z",
        "updated_at": "2025-10-22T10:00:00.000Z"
      },
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
    "count": 5,
    "total": 125,
    "limit": 5,
    "skip": 0,
    "filters": {
      "status": null,
      "company_name": null
    }
  }
}
```

---

#### Example 6: Error - Unauthorized

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments"
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Authorization header missing"
}
```

---

#### Example 7: Error - Not Admin

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments" \
  -H "Authorization: Bearer <user_token_not_admin>"
```

**Response (403 Forbidden):**
```json
{
  "detail": "Admin permissions required"
}
```

---

### POST /api/v1/payments/subscription - Create Subscription Payment

#### Example 1: Create Full Subscription Payment

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

**Response (201 Created):**
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

---

#### Example 2: Create Minimal Subscription Payment

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Translation Corp",
    "subscription_id": "690023c7eb2bceb90e274133",
    "square_payment_id": "sq_payment_minimal_001",
    "user_email": "admin@acme.com",
    "amount": 9000
  }'
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Subscription payment created successfully",
  "data": {
    "_id": "690023c7eb2bceb90e274141",
    "square_payment_id": "sq_payment_minimal_001",
    "company_name": "Acme Translation Corp",
    "subscription_id": "690023c7eb2bceb90e274133",
    "user_email": "admin@acme.com",
    "amount": 9000,
    "currency": "USD",
    "payment_status": "COMPLETED",
    "payment_date": "2025-10-30T12:05:00.000Z",
    "payment_method": "card",
    "refunds": [],
    "created_at": "2025-10-30T12:05:00.000Z",
    "updated_at": "2025-10-30T12:05:00.000Z"
  }
}
```

---

#### Example 3: Error - Invalid Subscription ID

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Translation Corp",
    "subscription_id": "invalid_id",
    "square_payment_id": "sq_payment_test",
    "user_email": "admin@acme.com",
    "amount": 9000
  }'
```

**Response (400 Bad Request):**
```json
{
  "detail": "Invalid subscription_id format: must be a valid 24-character ObjectId"
}
```

---

#### Example 4: Error - Subscription Not Found

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Translation Corp",
    "subscription_id": "690023c7eb2bceb90e999999",
    "square_payment_id": "sq_payment_test",
    "user_email": "admin@acme.com",
    "amount": 9000
  }'
```

**Response (400 Bad Request):**
```json
{
  "detail": "Subscription not found with ID: 690023c7eb2bceb90e999999"
}
```

---

#### Example 5: Error - Company Mismatch

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Wrong Company Name",
    "subscription_id": "690023c7eb2bceb90e274133",
    "square_payment_id": "sq_payment_test",
    "user_email": "admin@acme.com",
    "amount": 9000
  }'
```

**Response (400 Bad Request):**
```json
{
  "detail": "Company name mismatch: provided 'Wrong Company Name' but subscription belongs to 'Acme Translation Corp'"
}
```

---

## Company Endpoints

### GET /api/v1/payments/company/{company_name} - Get Company Payments

#### Example 1: Get All Company Payments

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC"
```

**Response (200 OK):**
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

---

#### Example 2: Filter by Completed Status

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=COMPLETED"
```

**Response (200 OK):**
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

---

#### Example 3: Pagination

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?limit=10&skip=10"
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "_id": "68fad3c2a0f41c24037c4820",
        "company_name": "Acme Health LLC",
        "user_email": "user@acmehealth.com",
        "square_payment_id": "payment_sq_1761350000",
        "amount": 999,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "refunds": [],
        "payment_date": "2025-10-23T12:00:00.000Z",
        "created_at": "2025-10-23T12:00:00.000Z",
        "updated_at": "2025-10-23T12:00:00.000Z"
      }
    ],
    "count": 10,
    "limit": 10,
    "skip": 10,
    "filters": {
      "company_name": "Acme Health LLC",
      "status": null
    }
  }
}
```

---

#### Example 4: Empty Result (No Payments)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Unknown%20Company"
```

**Response (200 OK):**
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

---

#### Example 5: Payment with Refund

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC?status=REFUNDED"
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "_id": "68fad3c2a0f41c24037c4820",
        "company_name": "Acme Health LLC",
        "user_email": "refund@acmehealth.com",
        "square_payment_id": "payment_sq_1761400000",
        "amount": 5000,
        "currency": "USD",
        "payment_status": "REFUNDED",
        "refunds": [
          {
            "refund_id": "rfn_01J2M9ABCD",
            "amount": 500,
            "currency": "USD",
            "status": "COMPLETED",
            "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62",
            "created_at": "2025-10-24T05:00:00.000Z"
          }
        ],
        "payment_date": "2025-10-24T04:00:00.000Z",
        "created_at": "2025-10-24T04:00:00.000Z",
        "updated_at": "2025-10-24T05:00:00.000Z"
      }
    ],
    "count": 1,
    "limit": 50,
    "skip": 0,
    "filters": {
      "company_name": "Acme Health LLC",
      "status": "REFUNDED"
    }
  }
}
```

---

## Query Endpoints

### GET /api/v1/payments/{payment_id} - Get Payment by ID

#### Example 1: Get Existing Payment

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/68fad3c2a0f41c24037c4810"
```

**Response (200 OK):**
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

---

#### Example 2: Error - Invalid ObjectId

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/invalid_id"
```

**Response (400 Bad Request):**
```json
{
  "detail": "Invalid payment ID format: invalid_id"
}
```

---

#### Example 3: Error - Payment Not Found

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/68fad3c2a0f41c24037c9999"
```

**Response (404 Not Found):**
```json
{
  "detail": "Payment not found: 68fad3c2a0f41c24037c9999"
}
```

---

### GET /api/v1/payments/square/{square_payment_id} - Get by Square ID

#### Example 1: Get by Square Payment ID

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/sq_payment_abc123"
```

**Response (200 OK):**
```json
{
  "_id": "68fad3c2a0f41c24037c4810",
  "company_name": "Acme Health LLC",
  "user_email": "test5@yahoo.com",
  "square_payment_id": "sq_payment_abc123",
  "amount": 1299,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "refunds": [],
  "payment_date": "2025-10-24T01:17:54.544Z",
  "created_at": "2025-10-24T01:17:54.544Z",
  "updated_at": "2025-10-24T01:17:54.544Z"
}
```

---

#### Example 2: Error - Square Payment Not Found

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/square/sq_payment_nonexistent"
```

**Response (404 Not Found):**
```json
{
  "detail": "Payment not found for Square ID: sq_payment_nonexistent"
}
```

---

### GET /api/v1/payments/email/{email} - Get by Email

#### Example 1: Get Payments by Email

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/email/user@example.com"
```

**Response (200 OK):**
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

---

#### Example 2: Pagination

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/email/user@example.com?limit=10&skip=10"
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "payments": [],
    "count": 0,
    "limit": 10,
    "skip": 10,
    "email": "user@example.com"
  }
}
```

---

## Transaction Endpoints

### POST /api/v1/payments/{square_payment_id}/refund - Process Refund

#### Example 1: Partial Refund

**Request:**
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

**Response (200 OK):**
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

---

#### Example 2: Full Refund

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/payment_sq_1761268674/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_full_refund_001",
    "amount": 1299,
    "currency": "USD",
    "idempotency_key": "rfd_full_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
  }'
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Refund processed: 1299 cents",
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
          "refund_id": "rfn_full_refund_001",
          "amount": 1299,
          "currency": "USD",
          "status": "COMPLETED",
          "idempotency_key": "rfd_full_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62",
          "created_at": "2025-10-24T02:00:00.000Z"
        }
      ],
      "created_at": "2025-10-24T01:17:54.544Z",
      "updated_at": "2025-10-24T02:00:00.000Z",
      "payment_date": "2025-10-24T01:17:54.544Z"
    },
    "refund": {
      "refund_id": "rfn_full_refund_001",
      "amount": 1299,
      "idempotency_key": "rfd_full_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62"
    }
  }
}
```

---

#### Example 3: Error - Refund Exceeds Payment

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/payment_sq_1761268674/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_too_much",
    "amount": 2000,
    "currency": "USD",
    "idempotency_key": "rfd_exceed_test"
  }'
```

**Response (400 Bad Request):**
```json
{
  "detail": "Refund amount (2000) exceeds payment amount (1299)"
}
```

---

#### Example 4: Error - Payment Not Found

**Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/payment_sq_nonexistent/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_test",
    "amount": 500,
    "currency": "USD",
    "idempotency_key": "rfd_test"
  }'
```

**Response (404 Not Found):**
```json
{
  "detail": "Payment not found: payment_sq_nonexistent"
}
```

---

## Statistics Endpoints

### GET /api/v1/payments/company/{company_name}/stats - Get Payment Stats

#### Example 1: All-Time Statistics

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats"
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "company_name": "Acme Health LLC",
    "total_payments": 125,
    "total_amount_cents": 1325000,
    "total_amount_dollars": 13250.00,
    "completed_payments": 120,
    "failed_payments": 5,
    "success_rate": 96.0,
    "date_range": {
      "start_date": null,
      "end_date": null
    }
  }
}
```

---

#### Example 2: Statistics for Date Range

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC/stats?start_date=2025-01-01T00:00:00Z&end_date=2025-10-31T23:59:59Z"
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "company_name": "Acme Health LLC",
    "total_payments": 98,
    "total_amount_cents": 1050000,
    "total_amount_dollars": 10500.00,
    "completed_payments": 95,
    "failed_payments": 3,
    "success_rate": 96.94,
    "date_range": {
      "start_date": "2025-01-01T00:00:00Z",
      "end_date": "2025-10-31T23:59:59Z"
    }
  }
}
```

---

#### Example 3: Company with No Payments

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/New%20Company/stats"
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "company_name": "New Company",
    "total_payments": 0,
    "total_amount_cents": 0,
    "total_amount_dollars": 0.00,
    "completed_payments": 0,
    "failed_payments": 0,
    "success_rate": 0.0,
    "date_range": {
      "start_date": null,
      "end_date": null
    }
  }
}
```

---

**End of Examples**
