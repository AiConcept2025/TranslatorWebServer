# User Transactions API - Quick Reference

## Base URL
```
http://localhost:8000/api/v1/user-transactions
```

---

## Endpoints

### 1. Process Payment Transaction
**Create a new user transaction with Square payment details**

```http
POST /api/v1/user-transactions/process
```

**Request Body:**
```json
{
  "user_name": "John Doe",
  "user_email": "john.doe@example.com",
  "document_url": "https://drive.google.com/file/d/abc123/view",
  "number_of_units": 10,
  "unit_type": "page",
  "cost_per_unit": 0.15,
  "source_language": "en",
  "target_language": "es",
  "square_transaction_id": "SQR-ABC123",
  "square_payment_id": "SQR-PAY-XYZ789",
  "amount_cents": 150,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "status": "completed"
}
```

**Response:** `201 Created`
```json
{
  "_id": "67185abc123...",
  "user_name": "John Doe",
  "user_email": "john.doe@example.com",
  "square_transaction_id": "SQR-ABC123",
  "square_payment_id": "SQR-PAY-XYZ789",
  "amount_cents": 150,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "refunds": [],
  ...
}
```

---

### 2. Process Refund
**Add a refund to an existing transaction**

```http
POST /api/v1/user-transactions/{square_transaction_id}/refund
```

**Path Parameters:**
- `square_transaction_id` - Square transaction ID

**Request Body:**
```json
{
  "refund_id": "rfn_01J2M9ABCD",
  "amount_cents": 50,
  "currency": "USD",
  "idempotency_key": "rfd_uuid_12345",
  "reason": "Customer request"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Refund processed successfully",
  "data": {
    "square_transaction_id": "SQR-ABC123",
    "refund_id": "rfn_01J2M9ABCD",
    "amount_cents": 50,
    "total_refunds": 1
  }
}
```

---

### 3. Get User Transaction History
**Retrieve all transactions for a user by email**

```http
GET /api/v1/user-transactions/user/{email}
```

**Path Parameters:**
- `email` - User email address

**Query Parameters:**
- `status` (optional) - Filter by status: `processing`, `completed`, `failed`
- `limit` (optional) - Max results (1-100, default: 50)

**Example:**
```
GET /api/v1/user-transactions/user/john.doe@example.com?status=completed&limit=20
```

**Response:** `200 OK`
```json
{
  "success": true,
  "data": {
    "email": "john.doe@example.com",
    "transactions": [
      {
        "_id": "67185abc123...",
        "user_name": "John Doe",
        "square_transaction_id": "SQR-ABC123",
        "amount_cents": 150,
        "payment_status": "COMPLETED",
        ...
      }
    ],
    "count": 1,
    "filters": {
      "status": "completed",
      "limit": 20
    }
  }
}
```

---

### 4. Get Transaction by ID
**Retrieve a single transaction by Square transaction ID**

```http
GET /api/v1/user-transactions/{square_transaction_id}
```

**Path Parameters:**
- `square_transaction_id` - Square transaction ID

**Response:** `200 OK`
```json
{
  "success": true,
  "data": {
    "_id": "67185abc123...",
    "user_name": "John Doe",
    "user_email": "john.doe@example.com",
    "square_transaction_id": "SQR-ABC123",
    "square_payment_id": "SQR-PAY-XYZ789",
    "amount_cents": 150,
    "currency": "USD",
    "payment_status": "COMPLETED",
    "refunds": [...],
    ...
  }
}
```

---

### 5. Update Payment Status
**Update the payment status of a transaction**

```http
PATCH /api/v1/user-transactions/{square_transaction_id}/payment-status
```

**Path Parameters:**
- `square_transaction_id` - Square transaction ID

**Query Parameters:**
- `payment_status` (required) - New status: `APPROVED`, `COMPLETED`, `CANCELED`, `FAILED`

**Example:**
```
PATCH /api/v1/user-transactions/SQR-ABC123/payment-status?payment_status=COMPLETED
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Payment status updated successfully",
  "data": {
    "square_transaction_id": "SQR-ABC123",
    "payment_status": "COMPLETED",
    "updated_at": "2025-10-23T12:00:00Z"
  }
}
```

---

## Field Reference

### Payment Status Values
- `APPROVED` - Payment approved by Square
- `COMPLETED` - Payment completed successfully
- `CANCELED` - Payment canceled
- `FAILED` - Payment failed

### Transaction Status Values
- `processing` - Transaction is being processed
- `completed` - Transaction completed successfully
- `failed` - Transaction failed

### Unit Types
- `page` - Page-based pricing
- `word` - Word-based pricing
- `character` - Character-based pricing

---

## Error Responses

### 400 Bad Request
```json
{
  "success": false,
  "error": {
    "code": 400,
    "message": "Invalid payment_status: INVALID",
    "type": "validation_error"
  }
}
```

### 404 Not Found
```json
{
  "success": false,
  "error": {
    "code": 404,
    "message": "Transaction not found: SQR-ABC123",
    "type": "not_found"
  }
}
```

### 422 Unprocessable Entity
```json
{
  "success": false,
  "error": {
    "code": 422,
    "message": "Request validation failed",
    "type": "validation_error",
    "details": [...]
  }
}
```

### 500 Internal Server Error
```json
{
  "success": false,
  "error": {
    "code": 500,
    "message": "Failed to process transaction",
    "type": "internal_error"
  }
}
```

---

## Testing with cURL

### 1. Create Transaction
```bash
curl -X POST "http://localhost:8000/api/v1/user-transactions/process" \
  -H "Content-Type: application/json" \
  -d '{
    "user_name": "Jane Smith",
    "user_email": "jane@example.com",
    "document_url": "https://drive.google.com/file/d/xyz789/view",
    "number_of_units": 5,
    "unit_type": "page",
    "cost_per_unit": 0.20,
    "source_language": "en",
    "target_language": "fr",
    "square_transaction_id": "SQR-TEST123",
    "square_payment_id": "SQR-PAY-TEST456",
    "payment_status": "COMPLETED"
  }'
```

### 2. Get User History
```bash
curl -X GET "http://localhost:8000/api/v1/user-transactions/user/jane@example.com"
```

### 3. Process Refund
```bash
curl -X POST "http://localhost:8000/api/v1/user-transactions/SQR-TEST123/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_test789",
    "amount_cents": 25,
    "currency": "USD",
    "idempotency_key": "idem_key_12345",
    "reason": "Partial refund"
  }'
```

### 4. Update Payment Status
```bash
curl -X PATCH "http://localhost:8000/api/v1/user-transactions/SQR-TEST123/payment-status?payment_status=COMPLETED"
```

---

## Interactive Documentation

Access the interactive Swagger UI at:
```
http://localhost:8000/docs
```

Filter for "User Transaction Payments" tag to see all endpoints.

---

## Notes

- All dates/times are in UTC and ISO 8601 format
- `amount_cents` is auto-calculated if not provided (total_cost × 100)
- `square_payment_id` defaults to `square_transaction_id` if not provided
- `currency` defaults to "USD"
- Refunds are stored in an array and can be queried via transaction ID
- All operations are logged for auditing

---

## Database Queries

### MongoDB Shell Examples

```javascript
// Find transaction by Square ID
db.user_transactions.findOne({ square_transaction_id: "SQR-ABC123" })

// Find all transactions for user
db.user_transactions.find({ user_email: "john.doe@example.com" })

// Find transactions with refunds
db.user_transactions.find({ "refunds.0": { $exists: true } })

// Find by payment status
db.user_transactions.find({ payment_status: "COMPLETED" })

// Count transactions by status
db.user_transactions.aggregate([
  { $group: { _id: "$payment_status", count: { $sum: 1 } } }
])
```

---

For detailed implementation information, see: `SQUARE_PAYMENT_IMPLEMENTATION_SUMMARY.md`
