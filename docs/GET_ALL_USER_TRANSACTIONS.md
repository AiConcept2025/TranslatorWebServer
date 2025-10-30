# GET All User Transactions Endpoint

## Overview
New admin endpoint to fetch all user transactions from the database, regardless of user email.

## Implementation Details

### Endpoint
```
GET /api/v1/user-transactions
```

### Location
File: `/Users/vladimirdanishevsky/projects/Translator/server/app/routers/user_transactions.py`
Line: 324-473

### Query Parameters

| Parameter | Type | Required | Default | Range | Description |
|-----------|------|----------|---------|-------|-------------|
| `status` | string | No | null | - | Filter by transaction status (completed, pending, failed) |
| `limit` | integer | No | 100 | 1-1000 | Maximum number of transactions to return |
| `skip` | integer | No | 0 | >= 0 | Number of transactions to skip for pagination |

### Response Format

#### Success Response (200 OK)
```json
{
  "success": true,
  "data": {
    "transactions": [
      {
        "_id": "68fac0c78d81a68274ac140b",
        "user_name": "John Doe",
        "user_email": "john.doe@example.com",
        "document_url": "https://drive.google.com/file/d/1ABC/view",
        "number_of_units": 10,
        "unit_type": "page",
        "cost_per_unit": 0.15,
        "source_language": "en",
        "target_language": "es",
        "square_transaction_id": "SQR-1EC28E70F10B4D9E",
        "date": "2025-10-23T23:56:55.438Z",
        "status": "completed",
        "total_cost": 1.5,
        "created_at": "2025-10-23T23:56:55.438Z",
        "updated_at": "2025-10-23T23:56:55.438Z"
      }
    ],
    "count": 1,
    "total": 1,
    "limit": 100,
    "skip": 0,
    "filters": {
      "status": "completed"
    }
  }
}
```

#### Error Responses

**400 Bad Request** - Invalid status filter
```json
{
  "detail": "Invalid transaction status. Must be one of: completed, pending, failed"
}
```

**500 Internal Server Error** - Database error
```json
{
  "detail": "Failed to retrieve transactions: <error message>"
}
```

### Usage Examples

#### Example 1: Get all transactions (first 100)
```bash
curl -X GET "http://localhost:8000/api/v1/user-transactions"
```

#### Example 2: Get all completed transactions
```bash
curl -X GET "http://localhost:8000/api/v1/user-transactions?status=completed"
```

#### Example 3: Get transactions with pagination (50 per page, page 2)
```bash
curl -X GET "http://localhost:8000/api/v1/user-transactions?limit=50&skip=50"
```

#### Example 4: Get up to 500 pending transactions
```bash
curl -X GET "http://localhost:8000/api/v1/user-transactions?status=pending&limit=500"
```

### Database Query

The endpoint uses MongoDB aggregation pipeline:

1. **Match Stage** (optional): Filters by status if provided
2. **Sort Stage**: Sorts by `created_at` descending (newest first)
3. **Skip Stage**: Implements pagination offset
4. **Limit Stage**: Limits number of results

```python
pipeline = []
if status:
    pipeline.append({"$match": {"status": status}})

pipeline.extend([
    {"$sort": {"created_at": -1}},
    {"$skip": skip},
    {"$limit": limit}
])
```

### Data Transformations

The endpoint performs the following transformations:
1. Converts MongoDB `ObjectId` to string
2. Converts `Decimal128` fields to float
3. Converts `datetime` objects to ISO format strings

### Key Features

1. **No Email Filter**: Unlike `/user/{email}`, this endpoint retrieves transactions for all users
2. **Higher Limit**: Allows up to 1000 transactions (vs 100 for user-specific endpoint)
3. **Total Count**: Returns both `count` (returned) and `total` (matching query) for better pagination
4. **Sorting**: Always returns newest transactions first
5. **Comprehensive Logging**: Logs all operations for monitoring

### Route Precedence

The endpoint is placed **before** `/user/{email}` in the router to ensure correct routing:
- Empty path (`""`) matches first
- Parameterized paths (`/user/{email}`) match later

### Tests

Location: `/Users/vladimirdanishevsky/projects/Translator/server/tests/test_user_transactions.py`
Class: `TestUserTransactionAPIEndpoints`

Tests include:
- ✓ Successful retrieval of all transactions
- ✓ Status filtering (completed, pending, failed)
- ✓ Pagination (limit and skip)
- ✓ Invalid status rejection
- ✓ Empty result handling

### OpenAPI Documentation

The endpoint is automatically documented in FastAPI's interactive docs:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Performance Considerations

1. **Indexing**: Ensure indexes on:
   - `status` (for filtering)
   - `created_at` (for sorting)

2. **Pagination**: Always use `limit` to avoid loading too many documents

3. **Monitoring**: Watch for slow queries when total documents exceed 10,000

### Security Considerations

**Important**: This is an admin endpoint. In production:
1. Add authentication middleware
2. Require admin role/permissions
3. Rate limit the endpoint
4. Log all access attempts

### Comparison with Existing Endpoints

| Endpoint | Path | Scope | Max Limit | Use Case |
|----------|------|-------|-----------|----------|
| **New** | `GET /api/v1/user-transactions` | All users | 1000 | Admin dashboard, reporting |
| Existing | `GET /api/v1/user-transactions/user/{email}` | Single user | 100 | User transaction history |
| Existing | `GET /api/v1/user-transactions/{square_transaction_id}` | Single transaction | N/A | Transaction details |

### Future Enhancements

Potential improvements for this endpoint:
1. Add date range filtering (`start_date`, `end_date`)
2. Add sorting options (by amount, date, status)
3. Add search by user email or name
4. Add aggregation stats (total amount, average, etc.)
5. Add export functionality (CSV, Excel)
