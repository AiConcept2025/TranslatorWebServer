# User Transaction Helper Module

## Overview

The `user_transaction_helper.py` module provides comprehensive CRUD operations for managing the `user_transactions` MongoDB collection. This collection stores individual user payment transactions integrated with Square payment processing.

## Collection Schema

### Fields

| Field | Type | Description | Indexed | Unique |
|-------|------|-------------|---------|--------|
| `_id` | ObjectId | MongoDB document ID | Yes | Yes |
| `user_name` | string | Full name of the user | No | No |
| `user_email` | string | User's email address | Yes | No |
| `document_url` | string | URL or path to document | No | No |
| `number_of_units` | integer | Number of units consumed | No | No |
| `unit_type` | string | Type: "page", "word", "character" | No | No |
| `cost_per_unit` | decimal | Cost per single unit | No | No |
| `source_language` | string | Source language code | No | No |
| `target_language` | string | Target language code | No | No |
| `square_transaction_id` | string | Square payment ID | Yes | Yes |
| `date` | datetime | Transaction date | Yes | No |
| `status` | string | Status: "processing", "completed", "failed" | Yes | No |
| `total_cost` | decimal | Calculated: number_of_units × cost_per_unit | No | No |
| `error_message` | string | Optional error message | No | No |
| `created_at` | datetime | Record creation timestamp | Yes | No |
| `updated_at` | datetime | Last update timestamp | No | No |

### Indexes

The MongoDB collection has the following indexes (created automatically):

- `square_transaction_id` (unique)
- `user_email`
- `date` (descending)
- `user_email + date` (compound)
- `status`
- `created_at`

## Functions

### 1. `create_user_transaction()`

Creates a new user transaction record with automatic total_cost calculation.

**Signature:**
```python
async def create_user_transaction(
    user_name: str,
    user_email: str,
    document_url: str,
    number_of_units: int,
    unit_type: str,
    cost_per_unit: float,
    source_language: str,
    target_language: str,
    square_transaction_id: str,
    date: datetime,
    status: str = "processing",
) -> Optional[str]
```

**Parameters:**
- `user_name` (str): Full name of the user
- `user_email` (str): Email address (indexed for queries)
- `document_url` (str): URL or path to the document being translated
- `number_of_units` (int): Quantity of units (pages, words, or characters)
- `unit_type` (str): One of "page", "word", "character"
- `cost_per_unit` (float): Cost per single unit (decimal)
- `source_language` (str): Source language code (e.g., "en")
- `target_language` (str): Target language code (e.g., "es")
- `square_transaction_id` (str): Unique Square payment transaction ID
- `date` (datetime): Transaction date (should include timezone)
- `status` (str, optional): Initial status, defaults to "processing"

**Returns:**
- `str`: The `square_transaction_id` if successful
- `None`: If creation failed (duplicate ID, validation error, etc.)

**Behavior:**
- Automatically calculates `total_cost` = `number_of_units` × `cost_per_unit`
- Sets `created_at` and `updated_at` to current UTC time
- Validates `unit_type` (must be "page", "word", or "character")
- Validates `status` (must be "processing", "completed", or "failed")
- Handles duplicate `square_transaction_id` gracefully
- Logs all operations and errors

**Example:**
```python
from datetime import datetime, timezone
from app.utils.user_transaction_helper import create_user_transaction

# Create a new transaction
transaction_id = await create_user_transaction(
    user_name="John Doe",
    user_email="john.doe@example.com",
    document_url="https://drive.google.com/file/d/abc123",
    number_of_units=10,
    unit_type="page",
    cost_per_unit=5.99,
    source_language="en",
    target_language="es",
    square_transaction_id="sq_payment_12345",
    date=datetime.now(timezone.utc),
    status="processing",
)

if transaction_id:
    print(f"Transaction created: {transaction_id}")
else:
    print("Failed to create transaction")
```

---

### 2. `update_user_transaction_status()`

Updates the status of an existing transaction and optionally adds an error message.

**Signature:**
```python
async def update_user_transaction_status(
    square_transaction_id: str,
    new_status: str,
    error_message: Optional[str] = None,
) -> bool
```

**Parameters:**
- `square_transaction_id` (str): Unique Square transaction ID
- `new_status` (str): New status ("processing", "completed", "failed")
- `error_message` (str, optional): Error message (only added if provided)

**Returns:**
- `bool`: `True` if update successful, `False` otherwise

**Behavior:**
- Updates `status` field to new value
- Updates `updated_at` timestamp to current UTC time
- Adds `error_message` field if provided (useful for failed transactions)
- Validates `new_status` before updating
- Returns `False` if transaction not found
- Returns `True` even if status was already the same (idempotent)

**Example:**
```python
from app.utils.user_transaction_helper import update_user_transaction_status

# Update to completed
success = await update_user_transaction_status(
    square_transaction_id="sq_payment_12345",
    new_status="completed",
)

# Update to failed with error message
success = await update_user_transaction_status(
    square_transaction_id="sq_payment_12345",
    new_status="failed",
    error_message="Translation service timeout",
)

if success:
    print("Status updated successfully")
else:
    print("Failed to update status")
```

---

### 3. `get_user_transactions_by_email()`

Retrieves all transactions for a specific user, optionally filtered by status.

**Signature:**
```python
async def get_user_transactions_by_email(
    user_email: str,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]
```

**Parameters:**
- `user_email` (str): Email address of the user
- `status` (str, optional): Filter by status if provided

**Returns:**
- `List[Dict[str, Any]]`: List of transaction dictionaries (empty if none found)

**Behavior:**
- Queries by `user_email` field (indexed for performance)
- Optionally filters by `status` if provided
- Sorts results by `date` descending (most recent first)
- Converts MongoDB `_id` to string for JSON serialization
- Returns empty list on error or if no transactions found
- Validates `status` parameter if provided

**Example:**
```python
from app.utils.user_transaction_helper import get_user_transactions_by_email

# Get all transactions for user
all_transactions = await get_user_transactions_by_email(
    user_email="john.doe@example.com"
)

# Get only completed transactions
completed_transactions = await get_user_transactions_by_email(
    user_email="john.doe@example.com",
    status="completed",
)

print(f"Found {len(all_transactions)} total transactions")
for tx in all_transactions:
    print(f"  - {tx['square_transaction_id']}: {tx['status']}")
```

---

### 4. `get_user_transaction()`

Retrieves a single transaction by its Square transaction ID.

**Signature:**
```python
async def get_user_transaction(
    square_transaction_id: str,
) -> Optional[Dict[str, Any]]
```

**Parameters:**
- `square_transaction_id` (str): Unique Square transaction ID

**Returns:**
- `Dict[str, Any]`: Transaction dictionary if found
- `None`: If transaction not found or error occurred

**Behavior:**
- Queries by `square_transaction_id` field (indexed and unique)
- Converts MongoDB `_id` to string for JSON serialization
- Returns `None` if transaction doesn't exist
- Logs retrieval operations

**Example:**
```python
from app.utils.user_transaction_helper import get_user_transaction

# Get specific transaction
transaction = await get_user_transaction(
    square_transaction_id="sq_payment_12345"
)

if transaction:
    print(f"User: {transaction['user_name']}")
    print(f"Email: {transaction['user_email']}")
    print(f"Units: {transaction['number_of_units']} {transaction['unit_type']}(s)")
    print(f"Total Cost: ${transaction['total_cost']:.2f}")
    print(f"Status: {transaction['status']}")
    if 'error_message' in transaction:
        print(f"Error: {transaction['error_message']}")
else:
    print("Transaction not found")
```

## Error Handling

All functions implement robust error handling:

1. **Validation Errors**: Invalid `unit_type` or `status` values are rejected
2. **Duplicate Keys**: Duplicate `square_transaction_id` is handled gracefully
3. **MongoDB Errors**: All `PyMongoError` exceptions are caught and logged
4. **General Exceptions**: Unexpected errors are caught, logged, and don't crash
5. **Logging**: All operations and errors are logged with appropriate levels

**Error Return Values:**
- `create_user_transaction()`: Returns `None` on error
- `update_user_transaction_status()`: Returns `False` on error
- `get_user_transactions_by_email()`: Returns empty list `[]` on error
- `get_user_transaction()`: Returns `None` on error

## Usage Patterns

### Pattern 1: Creating a Transaction After Payment

```python
from datetime import datetime, timezone
from app.utils.user_transaction_helper import create_user_transaction

async def process_payment_and_create_transaction(
    user_data: dict,
    payment_data: dict,
    document_info: dict,
):
    """Create transaction after successful Square payment."""

    transaction_id = await create_user_transaction(
        user_name=user_data["name"],
        user_email=user_data["email"],
        document_url=document_info["url"],
        number_of_units=document_info["page_count"],
        unit_type="page",
        cost_per_unit=payment_data["price_per_page"],
        source_language=document_info["source_lang"],
        target_language=document_info["target_lang"],
        square_transaction_id=payment_data["square_id"],
        date=datetime.now(timezone.utc),
        status="processing",
    )

    return transaction_id is not None
```

### Pattern 2: Updating Transaction as Translation Progresses

```python
from app.utils.user_transaction_helper import update_user_transaction_status

async def mark_translation_complete(square_transaction_id: str):
    """Mark transaction as completed after translation finishes."""

    success = await update_user_transaction_status(
        square_transaction_id=square_transaction_id,
        new_status="completed",
    )

    return success

async def mark_translation_failed(
    square_transaction_id: str,
    error: str,
):
    """Mark transaction as failed with error message."""

    success = await update_user_transaction_status(
        square_transaction_id=square_transaction_id,
        new_status="failed",
        error_message=error,
    )

    return success
```

### Pattern 3: User Transaction History API Endpoint

```python
from fastapi import APIRouter, HTTPException
from app.utils.user_transaction_helper import get_user_transactions_by_email

router = APIRouter()

@router.get("/users/{email}/transactions")
async def get_user_transaction_history(
    email: str,
    status: Optional[str] = None,
):
    """Get transaction history for a user."""

    transactions = await get_user_transactions_by_email(
        user_email=email,
        status=status,
    )

    return {
        "email": email,
        "count": len(transactions),
        "transactions": transactions,
    }
```

### Pattern 4: Transaction Receipt Lookup

```python
from fastapi import APIRouter, HTTPException
from app.utils.user_transaction_helper import get_user_transaction

router = APIRouter()

@router.get("/transactions/{square_transaction_id}")
async def get_transaction_receipt(square_transaction_id: str):
    """Get transaction details for receipt."""

    transaction = await get_user_transaction(square_transaction_id)

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction {square_transaction_id} not found",
        )

    return {
        "transaction": transaction,
        "receipt_url": f"/receipts/{square_transaction_id}",
    }
```

## Testing

A comprehensive test script is provided at `server/test_user_transaction_helper.py`.

**Run tests:**
```bash
cd server
python test_user_transaction_helper.py
```

**Test coverage:**
- ✅ Create transaction
- ✅ Retrieve single transaction
- ✅ Retrieve all transactions for user
- ✅ Filter transactions by status
- ✅ Update transaction status
- ✅ Update with error message
- ✅ Duplicate transaction ID handling
- ✅ Database connection/disconnection

## Integration with Existing Code

### With MongoDB Connection

```python
from app.database import database
from app.utils.user_transaction_helper import create_user_transaction

# In FastAPI lifespan or startup
await database.connect()

# Use transaction helpers
transaction_id = await create_user_transaction(...)

# In shutdown
await database.disconnect()
```

### With FastAPI Dependency Injection

```python
from fastapi import Depends
from app.database import database

async def get_database():
    """Dependency to ensure database is connected."""
    if not database.is_connected:
        await database.connect()
    return database

# Use in routes
@router.post("/transactions")
async def create_transaction(
    data: TransactionCreate,
    db = Depends(get_database),
):
    transaction_id = await create_user_transaction(
        user_name=data.user_name,
        user_email=data.user_email,
        # ... other fields
    )
    return {"transaction_id": transaction_id}
```

## Performance Considerations

### Indexes

All critical fields are indexed for optimal query performance:

- **Unique index** on `square_transaction_id` ensures O(1) lookups
- **Index** on `user_email` optimizes user transaction queries
- **Compound index** on `user_email + date` optimizes paginated history
- **Index** on `status` enables fast status filtering
- **Index** on `date` enables fast chronological sorting

### Best Practices

1. **Use timezone-aware datetimes**: Always use `datetime.now(timezone.utc)`
2. **Batch queries**: When getting multiple transactions, use `get_user_transactions_by_email()` instead of multiple `get_user_transaction()` calls
3. **Status filters**: Use status parameter to reduce result set size
4. **Error handling**: Always check return values (`None`, `False`, `[]`)
5. **Logging**: Review logs for failed operations

## Decimal Precision

The module uses Python's `Decimal` type for precise monetary calculations:

```python
from decimal import Decimal

total_cost = Decimal(str(number_of_units)) * Decimal(str(cost_per_unit))
```

This prevents floating-point precision errors common in financial calculations.

## Future Enhancements

Potential improvements for future versions:

1. **Pagination**: Add offset/limit parameters to `get_user_transactions_by_email()`
2. **Date range filtering**: Add `start_date` and `end_date` parameters
3. **Bulk operations**: Add `create_many_transactions()` for batch inserts
4. **Aggregations**: Add functions for total spent, transaction counts, etc.
5. **Refund support**: Add `refund_transaction()` function
6. **Soft deletes**: Add `deleted_at` field and `delete_transaction()` function

## Support

For issues or questions:

1. Check the test script for usage examples
2. Review the inline docstrings in the module
3. Check MongoDB logs for connection issues
4. Enable DEBUG logging: `logging.getLogger('app.utils.user_transaction_helper').setLevel(logging.DEBUG)`

## License

Part of the Translation Service project.
