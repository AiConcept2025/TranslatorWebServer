# GET /api/v1/payments - Retrieve All Payments (Admin Only)

## Overview
This endpoint retrieves all subscription payment records across all companies for admin dashboard viewing. It provides comprehensive filtering, sorting, and pagination capabilities.

**Authentication:** Admin users only (Bearer token required)

---

## Endpoint Details

### URL
```
GET /api/v1/payments
```

### Authentication
- **Required:** Admin user with Bearer token
- **Header:** `Authorization: Bearer {admin_token}`
- **Returns:** 401 if not authenticated, 403 if not admin

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | None | Filter by payment status: `COMPLETED`, `PENDING`, `FAILED`, `REFUNDED` |
| `company_name` | string | No | None | Filter by company name (e.g., "Acme Health LLC") |
| `limit` | integer | No | 50 | Maximum results to return (1-100) |
| `skip` | integer | No | 0 | Number of results to skip (pagination offset) |
| `sort_by` | string | No | payment_date | Field to sort by |
| `sort_order` | string | No | desc | Sort direction: `asc` or `desc` |

---

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "data": {
    "payments": [
      {
        "_id": "68fad3c2a0f41c24037c4810",
        "square_payment_id": "payment_sq_1761244600756",
        "square_order_id": "order_abc123",
        "square_customer_id": "cust_xyz789",
        "company_name": "Acme Health LLC",
        "subscription_id": "sub_12345",
        "user_id": "user_001",
        "user_email": "test5@yahoo.com",
        "amount": 1299,
        "currency": "USD",
        "payment_status": "COMPLETED",
        "payment_date": "2025-10-24T01:17:54.544Z",
        "payment_method": "CARD",
        "card_brand": "VISA",
        "card_last_4": "1234",
        "receipt_url": "https://squareup.com/receipt/xyz",
        "refunds": [],
        "created_at": "2025-10-24T01:17:54.544Z",
        "updated_at": "2025-10-24T01:17:54.544Z"
      }
    ],
    "count": 1,
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

### Response Fields

#### Root Object
- `success` (boolean): Indicates if request was successful
- `data` (object): Contains payment data

#### Data Object
- `payments` (array): Array of payment records
- `count` (integer): Number of payments in current response
- `total` (integer): Total payments matching filters (all pages)
- `limit` (integer): Limit value used
- `skip` (integer): Skip value used (pagination offset)
- `filters` (object): Applied filter values

#### Payment Record
- `_id` (string): MongoDB ObjectId (24-character hex)
- `square_payment_id` (string): Square payment identifier
- `square_order_id` (string, optional): Square order identifier
- `square_customer_id` (string, optional): Square customer identifier
- `company_name` (string): Full company name
- `subscription_id` (string, optional): Subscription identifier
- `user_id` (string, optional): User identifier
- `user_email` (string): Email of user who made payment
- `amount` (integer): Payment amount in cents (1299 = $12.99)
- `currency` (string): Currency code (ISO 4217, e.g., USD)
- `payment_status` (string): Current status (COMPLETED, PENDING, FAILED, REFUNDED)
- `payment_date` (string): Payment processing date (ISO 8601)
- `payment_method` (string, optional): Payment method type
- `card_brand` (string, optional): Card brand (VISA, MASTERCARD, etc.)
- `card_last_4` (string, optional): Last 4 digits of card
- `receipt_url` (string, optional): URL to payment receipt
- `refunds` (array): Array of refund objects (empty if no refunds)
- `created_at` (string): Record creation timestamp (ISO 8601)
- `updated_at` (string): Last update timestamp (ISO 8601)

### Error Responses

#### 401 Unauthorized
```json
{
  "detail": "Authorization header missing"
}
```

#### 403 Forbidden
```json
{
  "detail": "Admin permissions required"
}
```

#### 400 Bad Request
```json
{
  "detail": "Invalid payment status. Must be one of: COMPLETED, PENDING, FAILED, REFUNDED"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Failed to retrieve payments: Database connection error"
}
```

---

## Usage Examples

### Example 1: Get All Payments (First 50)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**Response:**
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
    "total": 2,
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

### Example 2: Filter by Status (Completed Only)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED" \
     -H "Authorization: Bearer {admin_token}"
```

**Response:**
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
    "limit": 50,
    "skip": 0,
    "filters": {
      "status": "COMPLETED",
      "company_name": null
    }
  }
}
```

---

### Example 3: Filter by Company

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?company_name=Acme%20Health%20LLC" \
     -H "Authorization: Bearer {admin_token}"
```

**Response:**
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
    "total": 1,
    "limit": 50,
    "skip": 0,
    "filters": {
      "status": null,
      "company_name": "Acme Health LLC"
    }
  }
}
```

---

### Example 4: Pagination (Second Page)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?limit=20&skip=20" \
     -H "Authorization: Bearer {admin_token}"
```

**Notes:**
- `skip=20` skips first 20 records
- `limit=20` returns next 20 records
- `total` field shows total matching records across all pages

---

### Example 5: Combine Filters with Sorting

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?status=COMPLETED&company_name=Acme%20Health%20LLC&limit=20&skip=0&sort_by=amount&sort_order=desc" \
     -H "Authorization: Bearer {admin_token}"
```

**Response:**
Returns first 20 completed payments for "Acme Health LLC", sorted by amount (highest first).

---

### Example 6: Sort by Amount (Ascending)

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?sort_by=amount&sort_order=asc&limit=10" \
     -H "Authorization: Bearer {admin_token}"
```

**Response:**
Returns 10 payments with lowest amounts first.

---

## Payment Status Values

| Status | Description |
|--------|-------------|
| `COMPLETED` | Payment successfully processed |
| `PENDING` | Payment awaiting processing |
| `FAILED` | Payment attempt failed |
| `REFUNDED` | Payment has been refunded (fully or partially) |

---

## Pagination Guide

### Basic Pagination
```bash
# First page (records 1-50)
curl -X GET "http://localhost:8000/api/v1/payments?limit=50&skip=0" \
     -H "Authorization: Bearer {admin_token}"

# Second page (records 51-100)
curl -X GET "http://localhost:8000/api/v1/payments?limit=50&skip=50" \
     -H "Authorization: Bearer {admin_token}"

# Third page (records 101-150)
curl -X GET "http://localhost:8000/api/v1/payments?limit=50&skip=100" \
     -H "Authorization: Bearer {admin_token}"
```

### Calculating Total Pages
```javascript
const totalPages = Math.ceil(response.data.total / response.data.limit);
```

### Example: Navigate Through All Pages
```javascript
const limit = 50;
let skip = 0;
let allPayments = [];

while (true) {
  const response = await fetch(
    `http://localhost:8000/api/v1/payments?limit=${limit}&skip=${skip}`,
    {
      headers: { 'Authorization': `Bearer ${adminToken}` }
    }
  );

  const data = await response.json();
  allPayments.push(...data.data.payments);

  // Check if we've retrieved all payments
  if (skip + data.data.count >= data.data.total) {
    break;
  }

  skip += limit;
}
```

---

## Notes

### Amount Format
- All amounts are in **cents**
- Example: `1299` = $12.99
- To convert to dollars: `amount / 100`

### Date Format
- All dates are in **ISO 8601 format**
- Example: `"2025-10-24T01:17:54.544Z"`
- Timezone: UTC (Z suffix)

### Filtering Best Practices
1. Use `status` filter to focus on specific payment states
2. Use `company_name` to view payments for specific companies
3. Combine filters for precise queries
4. Use pagination for large datasets (limit ≤ 100)

### Performance Considerations
- Use pagination for datasets > 100 records
- Prefer specific filters over retrieving all payments
- Default sorting (payment_date desc) is optimized with indexes
- Maximum limit is 100 records per request

### Security
- **Admin authentication required** - endpoint will return 401/403 for non-admin users
- Bearer token must be valid and belong to an admin user
- Tokens expire after session timeout (configurable)

---

## Related Endpoints

- `GET /api/v1/payments/company/{company_name}` - Get payments for specific company
- `GET /api/v1/payments/email/{email}` - Get payments by user email
- `GET /api/v1/payments/{payment_id}` - Get single payment by ID
- `GET /api/v1/payments/square/{square_payment_id}` - Get payment by Square ID
- `GET /api/v1/payments/company/{company_name}/stats` - Get payment statistics

---

## Implementation Details

### Repository Method
```python
async def get_all_payments(
    status: Optional[str] = None,
    company_name: Optional[str] = None,
    limit: int = 50,
    skip: int = 0,
    sort_by: str = "payment_date",
    sort_order: str = "desc"
) -> tuple[List[Dict[str, Any]], int]
```

### Authentication Dependency
```python
from app.middleware.auth_middleware import get_admin_user

@router.get("/")
async def get_all_payments(
    admin_user: Dict[str, Any] = Depends(get_admin_user),
    ...
):
    # Only admins can access this endpoint
    pass
```

---

## Testing Checklist

- [ ] Retrieve all payments without filters
- [ ] Filter by each payment status (COMPLETED, PENDING, FAILED, REFUNDED)
- [ ] Filter by company name
- [ ] Combine multiple filters
- [ ] Test pagination (skip/limit)
- [ ] Test sorting (asc/desc, different fields)
- [ ] Verify admin authentication required (401/403 for non-admin)
- [ ] Test invalid status value (400 error)
- [ ] Test invalid sort_order value (400 error)
- [ ] Verify total count accuracy
- [ ] Test empty result set
- [ ] Test large datasets (performance)

---

## Changelog

### Version 1.0 (2025-10-30)
- Initial implementation of GET /api/v1/payments endpoint
- Admin-only access with Bearer token authentication
- Filtering by status and company_name
- Pagination support (limit/skip)
- Sorting support (sort_by/sort_order)
- Comprehensive OpenAPI documentation
- Response includes total count for pagination
