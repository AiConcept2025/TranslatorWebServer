# User Transaction Helper - Quick Reference

## Import

```python
from app.utils.user_transaction_helper import (
    create_user_transaction,
    update_user_transaction_status,
    get_user_transactions_by_email,
    get_user_transaction,
)
from datetime import datetime, timezone
```

## Quick Examples

### Create Transaction
```python
tx_id = await create_user_transaction(
    user_name="John Doe",
    user_email="john@example.com",
    document_url="https://drive.google.com/file/d/abc123",
    number_of_units=10,
    unit_type="page",  # "page" | "word" | "character"
    cost_per_unit=5.99,
    source_language="en",
    target_language="es",
    square_transaction_id="sq_12345",
    date=datetime.now(timezone.utc),
    status="processing",  # "processing" | "completed" | "failed"
)
# Returns: square_transaction_id or None
```

### Update Status
```python
# Mark as completed
success = await update_user_transaction_status(
    square_transaction_id="sq_12345",
    new_status="completed",
)

# Mark as failed with error
success = await update_user_transaction_status(
    square_transaction_id="sq_12345",
    new_status="failed",
    error_message="Translation timeout",
)
# Returns: True or False
```

### Get User's Transactions
```python
# All transactions
all_txs = await get_user_transactions_by_email("john@example.com")

# Filter by status
completed = await get_user_transactions_by_email(
    user_email="john@example.com",
    status="completed",
)
# Returns: List[Dict] (sorted by date desc)
```

### Get Single Transaction
```python
tx = await get_user_transaction("sq_12345")
# Returns: Dict or None

if tx:
    print(f"Status: {tx['status']}")
    print(f"Total: ${tx['total_cost']:.2f}")
```

## Valid Values

| Field | Valid Values |
|-------|--------------|
| `unit_type` | "page", "word", "character" |
| `status` | "processing", "completed", "failed" |

## Transaction Schema

```python
{
    "_id": ObjectId("..."),
    "user_name": "John Doe",
    "user_email": "john@example.com",
    "document_url": "https://...",
    "number_of_units": 10,
    "unit_type": "page",
    "cost_per_unit": 5.99,
    "source_language": "en",
    "target_language": "es",
    "square_transaction_id": "sq_12345",
    "date": datetime(...),
    "status": "completed",
    "total_cost": 59.90,  # Auto-calculated
    "error_message": "...",  # Optional
    "created_at": datetime(...),
    "updated_at": datetime(...),
}
```

## FastAPI Integration

```python
from fastapi import APIRouter, HTTPException
from app.utils.user_transaction_helper import (
    create_user_transaction,
    get_user_transactions_by_email,
)

router = APIRouter()

@router.post("/transactions")
async def create_tx(data: TransactionCreate):
    tx_id = await create_user_transaction(
        user_name=data.user_name,
        user_email=data.user_email,
        document_url=data.document_url,
        number_of_units=data.number_of_units,
        unit_type=data.unit_type,
        cost_per_unit=data.cost_per_unit,
        source_language=data.source_lang,
        target_language=data.target_lang,
        square_transaction_id=data.square_id,
        date=datetime.now(timezone.utc),
    )

    if not tx_id:
        raise HTTPException(status_code=400, detail="Failed to create transaction")

    return {"transaction_id": tx_id}

@router.get("/users/{email}/transactions")
async def get_history(email: str, status: Optional[str] = None):
    txs = await get_user_transactions_by_email(email, status)
    return {"count": len(txs), "transactions": txs}
```

## Error Handling

```python
# All functions handle errors gracefully
tx_id = await create_user_transaction(...)
if tx_id is None:
    # Handle failure (duplicate ID, validation error, etc.)
    pass

success = await update_user_transaction_status(...)
if not success:
    # Handle update failure
    pass

txs = await get_user_transactions_by_email(...)
# Returns empty list [] on error

tx = await get_user_transaction(...)
if tx is None:
    # Transaction not found or error
    pass
```

## Testing

```bash
# Run test script
cd server
python test_user_transaction_helper.py
```

## Common Patterns

### Complete Payment Flow
```python
# 1. Process payment with Square
square_id = await process_square_payment(...)

# 2. Create transaction record
tx_id = await create_user_transaction(
    square_transaction_id=square_id,
    # ... other fields
)

# 3. Start translation (async)
await queue_translation_job(tx_id)

# 4. Update on completion
await update_user_transaction_status(
    square_transaction_id=square_id,
    new_status="completed",
)
```

### User Dashboard
```python
# Get user's transaction history
transactions = await get_user_transactions_by_email(user_email)

# Calculate totals
total_spent = sum(tx["total_cost"] for tx in transactions)
completed_count = len([tx for tx in transactions if tx["status"] == "completed"])

return {
    "total_transactions": len(transactions),
    "completed_transactions": completed_count,
    "total_spent": total_spent,
    "recent_transactions": transactions[:10],  # Last 10
}
```

## Tips

- ✅ Always use `datetime.now(timezone.utc)` for timezone-aware dates
- ✅ Check return values (None/False means failure)
- ✅ Use status filter to reduce result set size
- ✅ Square transaction IDs must be unique
- ✅ All monetary values use precise Decimal calculation
- ✅ Functions are fully async - use `await`
- ✅ All operations are logged automatically

## Documentation

Full documentation: `USER_TRANSACTION_HELPER.md`
