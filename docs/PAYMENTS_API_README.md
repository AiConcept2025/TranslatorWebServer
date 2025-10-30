# Payments API - Documentation Overview

Welcome to the comprehensive Payments API documentation for the Translation Service platform.

---

## Documentation Structure

This documentation package consists of multiple files organized for easy navigation:

### Main Documentation

**[PAYMENTS_API.md](./PAYMENTS_API.md)** - Complete API Reference (100+ pages)
- System architecture and data models
- All endpoints with detailed specifications
- Authentication and authorization
- Error handling and best practices
- Integration guides
- Testing strategies

### Examples and Guides

**[examples/payments_requests.md](./examples/payments_requests.md)** - Request/Response Examples
- Complete request/response examples for all endpoints
- Success and error scenarios
- cURL commands ready to use
- JSON response samples

**[examples/payments_scenarios.md](./examples/payments_scenarios.md)** - Usage Scenarios
- Real-world use cases with step-by-step instructions
- Python code examples
- Admin workflows
- Company management scenarios
- Refund processing
- Reporting and analytics

---

## Quick Start

### 1. Understanding the API

The Payments API manages **subscription payment records** for the translation service platform:

- **Purpose:** Track subscription payments (NOT per-transaction payments)
- **Payment Processor:** Square
- **Database:** MongoDB
- **Technology:** FastAPI + Python

### 2. Key Endpoints

| Endpoint | Purpose | Auth |
|----------|---------|------|
| `GET /api/v1/payments` | View all payments (admin) | Admin |
| `POST /api/v1/payments/subscription` | Create subscription payment | Admin |
| `GET /api/v1/payments/company/{name}` | Get company payments | User/Admin |
| `POST /api/v1/payments/{id}/refund` | Process refund | Admin |
| `GET /api/v1/payments/company/{name}/stats` | Payment statistics | User/Admin |

### 3. Authentication

**Get Admin Token:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/admin/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "admin_password"
  }'
```

**Use Token:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 4. Basic Operations

**Get all payments (admin):**
```bash
curl -X GET "http://localhost:8000/api/v1/payments?limit=20" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Get company payments:**
```bash
curl -X GET "http://localhost:8000/api/v1/payments/company/Acme%20Health%20LLC"
```

**Create subscription payment:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/subscription" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Corp",
    "subscription_id": "690023c7eb2bceb90e274133",
    "square_payment_id": "sq_payment_123",
    "user_email": "admin@acme.com",
    "amount": 9000
  }'
```

**Process refund:**
```bash
curl -X POST "http://localhost:8000/api/v1/payments/sq_payment_123/refund" \
  -H "Content-Type: application/json" \
  -d '{
    "refund_id": "rfn_001",
    "amount": 500,
    "idempotency_key": "rfd_unique_key"
  }'
```

---

## Important Concepts

### Payment Status Values

- **COMPLETED** - Payment successfully processed
- **PENDING** - Payment awaiting confirmation
- **FAILED** - Payment processing failed
- **REFUNDED** - Payment has refunds (full or partial)

### Amount Handling

All amounts are in **cents** (integers):
- $12.99 → `1299` cents
- $90.00 → `9000` cents

**Why cents?** Avoids floating-point precision issues.

### Refund Processing

- Refunds are added to the `refunds` array (not replacing)
- Payment status changes to `REFUNDED`
- Partial refunds are supported
- Idempotency keys prevent duplicate refunds

---

## Common Use Cases

### Admin Tasks

1. **View all payments:** See payment activity across all companies
2. **Record subscription payment:** After receiving Square webhook
3. **Process refunds:** Handle customer refund requests
4. **Generate reports:** Export payment data for accounting

### Company Tasks

1. **View payment history:** See all company payments
2. **Track subscription payments:** Monitor subscription billing
3. **Get payment statistics:** Analyze payment trends
4. **Download invoices:** Get payment receipts

---

## Data Model Overview

### Payment Record

```javascript
{
  _id: "68fad3c2a0f41c24037c4810",
  square_payment_id: "sq_payment_123",
  company_name: "Acme Health LLC",
  subscription_id: "690023c7eb2bceb90e274133",
  user_email: "admin@acme.com",
  amount: 9000,                    // Cents
  currency: "USD",
  payment_status: "COMPLETED",
  payment_date: "2025-10-28T11:18:04.213Z",
  payment_method: "card",
  card_brand: "VISA",
  card_last_4: "1234",
  refunds: [],
  created_at: "2025-10-28T11:18:04.213Z",
  updated_at: "2025-10-28T11:18:04.213Z"
}
```

### Refund Object

```javascript
{
  refund_id: "rfn_01J2M9ABCD",
  amount: 500,
  currency: "USD",
  status: "COMPLETED",
  idempotency_key: "rfd_unique_key",
  created_at: "2025-10-29T10:00:00.000Z"
}
```

---

## Integration Patterns

### Square Webhook Integration

```python
@app.post("/webhooks/square")
async def handle_square_webhook(request: Request):
    """Handle Square payment webhooks"""

    event = await request.json()

    if event["type"] == "payment.updated":
        payment = event["data"]["object"]["payment"]

        # Record payment via API
        await create_subscription_payment(
            square_payment_id=payment["id"],
            amount=payment["amount_money"]["amount"],
            ...
        )
```

### Payment Status Lifecycle

```
PENDING ──────────────────┐
   │                      │
   │ (success)            │ (failure)
   ▼                      ▼
COMPLETED ────────────▶ FAILED
   │
   │ (refund)
   ▼
REFUNDED
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Common Cause |
|------|---------|--------------|
| 200 | OK | Request successful |
| 201 | Created | Payment created |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Not admin |
| 404 | Not Found | Payment not found |
| 500 | Server Error | Internal error |

### Common Errors

**Invalid Subscription ID:**
```json
{
  "detail": "Invalid subscription_id format: must be a valid 24-character ObjectId"
}
```

**Refund Exceeds Payment:**
```json
{
  "detail": "Refund amount (1500) exceeds payment amount (1299)"
}
```

**Unauthorized:**
```json
{
  "detail": "Authorization header missing"
}
```

---

## Testing

### Test with cURL

```bash
# Set environment
export API_URL="http://localhost:8000"
export ADMIN_TOKEN="your_token_here"

# Test admin endpoint
curl -X GET "$API_URL/api/v1/payments?limit=10" \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Test company endpoint
curl -X GET "$API_URL/api/v1/payments/company/Acme%20Health%20LLC"
```

### Test with Python

```python
import requests

# Create client
base_url = "http://localhost:8000"
headers = {"Authorization": f"Bearer {admin_token}"}

# Get payments
response = requests.get(
    f"{base_url}/api/v1/payments",
    headers=headers,
    params={"status": "COMPLETED", "limit": 20}
)

payments = response.json()["data"]["payments"]
print(f"Found {len(payments)} payments")
```

---

## Best Practices

### 1. Amount Handling
Always use cents (integers) to avoid floating-point issues:
```python
# Good
amount = 1299  # $12.99

# Bad
amount = 12.99  # Floating point
```

### 2. Idempotency
Use unique idempotency keys for refunds:
```python
import uuid
idempotency_key = f"rfd_{uuid.uuid4()}"
```

### 3. Error Handling
Always check response status:
```python
response = requests.post(url, json=data)
if response.status_code != 201:
    print(f"Error: {response.json()['detail']}")
```

### 4. Pagination
Use pagination for large datasets:
```python
limit = 100
skip = 0

while True:
    payments = get_payments(limit=limit, skip=skip)
    if len(payments) < limit:
        break
    skip += limit
```

### 5. Date Filtering
Use ISO 8601 format for dates:
```python
start_date = "2025-01-01T00:00:00Z"
end_date = "2025-12-31T23:59:59Z"
```

---

## Support and Resources

### Documentation Files

1. **[PAYMENTS_API.md](./PAYMENTS_API.md)** - Complete API reference
2. **[examples/payments_requests.md](./examples/payments_requests.md)** - Request/response examples
3. **[examples/payments_scenarios.md](./examples/payments_scenarios.md)** - Usage scenarios

### Related Documentation

- [Subscriptions API](./SUBSCRIPTIONS_API.md)
- [User Transactions API](./USER_TRANSACTIONS_API.md)
- [Admin Setup Guide](./ADMIN_SETUP.md)
- [MongoDB Integration](./MONGODB_INTEGRATION.md)

### API Version

- **Current Version:** 2.0.0
- **Last Updated:** October 30, 2025
- **Base URL:** `http://localhost:8000/api/v1/payments`

### Contact

- **GitHub Issues:** https://github.com/your-org/translation-service/issues
- **Email:** support@example.com
- **Slack:** #translation-api-support

---

## Quick Reference Card

### Admin Endpoints

```bash
# Get all payments
GET /api/v1/payments

# Create subscription payment
POST /api/v1/payments/subscription
```

### Company Endpoints

```bash
# Get company payments
GET /api/v1/payments/company/{company_name}

# Get payment stats
GET /api/v1/payments/company/{company_name}/stats
```

### Query Endpoints

```bash
# Get by ID
GET /api/v1/payments/{payment_id}

# Get by Square ID
GET /api/v1/payments/square/{square_payment_id}

# Get by email
GET /api/v1/payments/email/{email}
```

### Transaction Endpoints

```bash
# Create payment
POST /api/v1/payments

# Process refund
POST /api/v1/payments/{square_payment_id}/refund
```

---

## Next Steps

1. **Read the main documentation:** [PAYMENTS_API.md](./PAYMENTS_API.md)
2. **Try the examples:** [payments_requests.md](./examples/payments_requests.md)
3. **Explore scenarios:** [payments_scenarios.md](./examples/payments_scenarios.md)
4. **Test the API:** Use cURL or Python examples
5. **Integrate:** Follow integration guide in main documentation

---

**Happy Coding!**
