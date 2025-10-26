# User Transaction Helper Module

## Quick Start

```python
from app.utils.user_transaction_helper import (
    create_user_transaction,
    update_user_transaction_status,
    get_user_transactions_by_email,
    get_user_transaction,
)
from datetime import datetime, timezone

# Create transaction
tx_id = await create_user_transaction(
    user_name="John Doe",
    user_email="john@example.com",
    document_url="https://drive.google.com/file/d/abc123",
    number_of_units=10,
    unit_type="page",
    cost_per_unit=5.99,
    source_language="en",
    target_language="es",
    square_transaction_id="sq_payment_12345",
    date=datetime.now(timezone.utc),
)

# Update status
success = await update_user_transaction_status(
    square_transaction_id="sq_payment_12345",
    new_status="completed",
)

# Get user's transactions
transactions = await get_user_transactions_by_email("john@example.com")

# Get single transaction
transaction = await get_user_transaction("sq_payment_12345")
```

## Documentation

| File | Description |
|------|-------------|
| `USER_TRANSACTION_HELPER.md` | Complete API reference with detailed examples |
| `USER_TRANSACTION_QUICK_REF.md` | Quick reference card for common operations |
| `README_USER_TRANSACTIONS.md` | This file - overview and links |

## Files

- **Module:** `app/utils/user_transaction_helper.py` (336 lines)
- **Tests:** `test_user_transaction_helper.py` (160 lines)
- **Docs:** 739 lines total

## Features

- ✅ Full async/await with Motor
- ✅ Comprehensive error handling
- ✅ Input validation
- ✅ Decimal precision for money
- ✅ Automatic timestamp management
- ✅ Indexed MongoDB queries
- ✅ Type hints throughout
- ✅ Extensive logging
- ✅ Test suite included

## Schema

```typescript
{
  user_name: string,
  user_email: string,              // Indexed
  document_url: string,
  number_of_units: number,
  unit_type: "page" | "word" | "character",
  cost_per_unit: number,
  source_language: string,
  target_language: string,
  square_transaction_id: string,   // Unique, indexed
  date: Date,
  status: "processing" | "completed" | "failed",
  total_cost: number,              // Auto-calculated
  error_message?: string,          // Optional
  created_at: Date,                // Auto-set
  updated_at: Date,                // Auto-updated
}
```

## Testing

```bash
cd server
python test_user_transaction_helper.py
```

## Integration

Works seamlessly with existing MongoDB setup:

```python
from app.database import database

# Connection handled by FastAPI lifespan
await database.connect()

# Use helper functions
result = await create_user_transaction(...)

# Cleanup on shutdown
await database.disconnect()
```

## Next Steps

1. Create FastAPI routes using these helpers
2. Add Pydantic models for request/response
3. Integrate with Square payment flow
4. Build user dashboard with transaction history

## Support

- Review full documentation in `USER_TRANSACTION_HELPER.md`
- Check quick reference in `USER_TRANSACTION_QUICK_REF.md`
- Run test suite for usage examples
- Enable DEBUG logging for troubleshooting

## Architecture

```
FastAPI Routes
     ↓
User Transaction Helper
     ↓
MongoDB Connection Layer
     ↓
MongoDB Database (user_transactions)
```

Full architecture diagram: `MODULE_ARCHITECTURE.txt`

## Performance

All queries use optimized indexes:
- `square_transaction_id`: O(1) unique lookup
- `user_email`: O(log n) user queries
- `user_email + date`: Compound index for history
- `status`: Fast status filtering

## License

Part of the Translation Service project.
