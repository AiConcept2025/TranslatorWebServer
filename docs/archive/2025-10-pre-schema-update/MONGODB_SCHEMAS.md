# MongoDB Schemas Documentation

**Database Name:** `translation`
**Last Updated:** 2025-10-23
**Source of Truth:** MongoDB collections (schemas verified by insertion scripts)

This document provides comprehensive schema definitions for the 3 main transaction collections in the translation service MongoDB database.

---

## Table of Contents

1. [Payments Collection](#payments-collection)
2. [User Transactions Collection](#user-transactions-collection)
3. [Translation Transactions Collection](#translation-transactions-collection)
4. [Relationships Between Collections](#relationships-between-collections)
5. [Verification Scripts](#verification-scripts)

---

## Payments Collection

**Collection Name:** `payments`
**Purpose:** Track company payments with Square payment integration
**Script:** `server/scripts/schema_payments.py`

### Schema

| Field | Type | Required | Indexed | Default | Description |
|-------|------|----------|---------|---------|-------------|
| `_id` | ObjectId | ✓ (auto) | ✓ (auto) | - | MongoDB document ID |
| `company_id` | String | ✓ | ✓ | - | Company identifier (e.g., "cmp_00123") |
| `company_name` | String | ✓ | - | - | Company name |
| `user_email` | String | ✓ | ✓ | - | User email address |
| `square_payment_id` | String | ✓ | ✓ | - | Square payment ID (non-unique for stub) |
| `amount` | Integer | ✓ | - | - | Payment amount in cents |
| `currency` | String | - | - | "USD" | Currency code (ISO 4217) |
| `payment_status` | String | ✓ | ✓ | - | Payment status enum |
| `refunds` | Array | - | - | `[]` | Array of refund objects |
| `created_at` | DateTime | ✓ (auto) | ✓ | UTC now | Record creation timestamp |
| `updated_at` | DateTime | ✓ (auto) | - | UTC now | Last update timestamp |
| `payment_date` | DateTime | ✓ | ✓ | - | Payment processing date |

### Payment Status Enum

- `COMPLETED` - Payment successfully completed
- `PENDING` - Payment pending/processing
- `FAILED` - Payment failed
- `REFUNDED` - Payment refunded

### Refund Object Schema

Each refund in the `refunds` array has the following structure:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refund_id` | String | ✓ | Refund identifier |
| `amount` | Integer | ✓ | Refund amount in cents |
| `currency` | String | ✓ | Currency code |
| `status` | String | ✓ | Refund status (COMPLETED, PENDING, FAILED) |
| `idempotency_key` | String | ✓ | Idempotency key for Square API |
| `created_at` | DateTime | ✓ | Refund creation timestamp |

### Indexes

1. `square_payment_id_idx` - Non-unique index (allows duplicate for stub implementation)
2. `company_id_idx` - Single field index
3. `subscription_id_idx` - Single field index
4. `user_id_idx` - Single field index
5. `payment_status_idx` - Single field index
6. `payment_date_idx` - Single field index
7. `user_email_idx` - Single field index
8. `company_status_idx` - Compound index: `(company_id, payment_status)`
9. `user_payment_date_idx` - Compound index: `(user_id, payment_date)`
10. `square_order_id_idx` - Single field index
11. `square_customer_id_idx` - Single field index
12. `created_at_asc` - Single field index

### Example Document

```json
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "company_id": "cmp_00123",
  "company_name": "Acme Health LLC",
  "user_email": "test5@yahoo.com",
  "square_payment_id": "payment_sq_1761244600756_u12vb3tx6",
  "amount": 1299,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "refunds": [
    {
      "refund_id": "rfn_01J2M9ABCD",
      "amount": 500,
      "currency": "USD",
      "status": "COMPLETED",
      "idempotency_key": "rfd_7e6df9c2-5f7c-43f9-9b1a-3e7e2e6b2b62",
      "created_at": ISODate("2025-10-23T12:00:00.000Z")
    }
  ],
  "created_at": ISODate("2025-10-23T10:30:00.000Z"),
  "updated_at": ISODate("2025-10-23T10:30:00.000Z"),
  "payment_date": ISODate("2025-10-23T10:30:00.000Z")
}
```

### Common Queries

```javascript
// Find payment by Square payment ID
db.payments.findOne({ "square_payment_id": "payment_sq_1761244600756_u12vb3tx6" })

// Find all payments for a company
db.payments.find({ "company_id": "cmp_00123" })

// Find completed payments
db.payments.find({ "payment_status": "COMPLETED" })

// Find payments with refunds
db.payments.find({ "refunds": { "$ne": [] } })

// Find payments by user email
db.payments.find({ "user_email": "test5@yahoo.com" })

// Aggregate total payments by company
db.payments.aggregate([
  { "$group": { "_id": "$company_id", "total": { "$sum": "$amount" } } }
])
```

---

## User Transactions Collection

**Collection Name:** `user_transactions`
**Purpose:** Track individual user translation transactions with Square payments
**Script:** `server/scripts/schema_user_transactions.py`

### Schema

| Field | Type | Required | Indexed | Default | Description |
|-------|------|----------|---------|---------|-------------|
| `_id` | ObjectId | ✓ (auto) | ✓ (auto) | - | MongoDB document ID |
| `user_name` | String | ✓ | - | - | Full name of the user |
| `user_email` | String | ✓ | ✓ | - | User email address |
| `document_url` | String | ✓ | - | - | Document URL/path (e.g., Google Drive) |
| `number_of_units` | Integer | ✓ | - | - | Number of units translated |
| `unit_type` | String | ✓ | - | - | Unit type enum |
| `cost_per_unit` | Float | ✓ | - | - | Cost per unit in dollars |
| `source_language` | String | ✓ | - | - | Source language code (ISO 639-1) |
| `target_language` | String | ✓ | - | - | Target language code (ISO 639-1) |
| `square_transaction_id` | String | ✓ | ✓ (unique) | - | Square transaction ID |
| `date` | DateTime | ✓ | - | - | Transaction date |
| `status` | String | - | ✓ | "processing" | Transaction status enum |
| `total_cost` | Float | ✓ | - | - | Total cost (number_of_units * cost_per_unit) |
| `created_at` | DateTime | ✓ (auto) | ✓ | UTC now | Record creation timestamp |
| `updated_at` | DateTime | ✓ (auto) | - | UTC now | Last update timestamp |
| `square_payment_id` | String | ✓ | - | - | Square payment ID |
| `amount_cents` | Integer | ✓ | - | - | Payment amount in cents |
| `currency` | String | - | - | "USD" | Currency code (ISO 4217) |
| `payment_status` | String | - | - | "COMPLETED" | Payment status enum |
| `refunds` | Array | - | - | `[]` | Array of refund objects |
| `payment_date` | DateTime | ✓ | - | - | Payment processing date |

### Unit Type Enum

- `page` - Cost per page
- `word` - Cost per word
- `character` - Cost per character

### Transaction Status Enum

- `processing` - Transaction in progress
- `completed` - Transaction completed successfully
- `failed` - Transaction failed

### Payment Status Enum

- `APPROVED` - Payment approved
- `COMPLETED` - Payment completed
- `CANCELED` - Payment canceled
- `FAILED` - Payment failed

### Indexes

1. `square_transaction_id_unique` - Unique index
2. `user_email_idx` - Single field index
3. `date_desc_idx` - Single field index (descending)
4. `user_email_date_idx` - Compound index: `(user_email, date)`
5. `status_idx` - Single field index
6. `created_at_asc` - Single field index

### Example Document

```json
{
  "_id": ObjectId("507f1f77bcf86cd799439012"),
  "user_name": "John Doe",
  "user_email": "john.doe@example.com",
  "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
  "number_of_units": 10,
  "unit_type": "page",
  "cost_per_unit": 0.15,
  "source_language": "en",
  "target_language": "es",
  "square_transaction_id": "SQR-1EC28E70F10B4D9E",
  "date": ISODate("2025-10-23T10:30:00.000Z"),
  "status": "completed",
  "total_cost": 1.5,
  "created_at": ISODate("2025-10-23T10:30:00.000Z"),
  "updated_at": ISODate("2025-10-23T10:30:00.000Z"),
  "square_payment_id": "SQR-1EC28E70F10B4D9E",
  "amount_cents": 150,
  "currency": "USD",
  "payment_status": "COMPLETED",
  "refunds": [],
  "payment_date": ISODate("2025-10-23T10:30:00.000Z")
}
```

### Common Queries

```javascript
// Find transaction by Square transaction ID
db.user_transactions.findOne({ "square_transaction_id": "SQR-1EC28E70F10B4D9E" })

// Find all transactions for a user
db.user_transactions.find({ "user_email": "john.doe@example.com" })

// Find completed transactions
db.user_transactions.find({ "status": "completed" })

// Find by language pair
db.user_transactions.find({
  "source_language": "en",
  "target_language": "es"
})

// Find recent transactions (last 30 days)
db.user_transactions.find({
  "date": { "$gte": new Date(Date.now() - 30*24*60*60*1000) }
})

// Find by unit type
db.user_transactions.find({ "unit_type": "page" })

// Aggregate total cost by user
db.user_transactions.aggregate([
  { "$group": { "_id": "$user_email", "total": { "$sum": "$total_cost" } } }
])

// Find transactions with specific payment status
db.user_transactions.find({ "payment_status": "COMPLETED" })
```

---

## Translation Transactions Collection

**Collection Name:** `translation_transactions`
**Purpose:** Track company translation transactions (subscription-based or individual)
**Script:** `server/scripts/schema_translation_transactions.py`

### Schema

| Field | Type | Required | Indexed | Default | Description |
|-------|------|----------|---------|---------|-------------|
| `_id` | ObjectId | ✓ (auto) | ✓ (auto) | - | MongoDB document ID |
| `transaction_id` | String | ✓ | ✓ (unique) | - | Transaction identifier |
| `company_id` | String | ✓ | ✓ | - | Company identifier |
| `user_id` | String | - | - | - | User identifier |
| `subscription_id` | String | - | - | null | Subscription ID (null for individual) |
| `file_name` | String | ✓ | - | - | Original file name |
| `file_size` | Integer | ✓ | - | - | File size in bytes |
| `original_file_url` | String | ✓ | - | - | URL to original file |
| `translated_file_url` | String | - | - | "" | URL to translated file |
| `source_language` | String | ✓ | - | - | Source language code (ISO 639-1) |
| `target_language` | String | ✓ | - | - | Target language code (ISO 639-1) |
| `status` | String | ✓ | - | - | Transaction status enum |
| `unit_type` | String | ✓ | - | - | Unit type enum |
| `units_count` | Integer | ✓ | - | - | Number of units |
| `price_per_unit` | Float | ✓ | - | - | Price per unit in dollars |
| `total_price` | Float | ✓ | - | - | Total price (units_count * price_per_unit) |
| `estimated_cost` | Float | ✓ | - | - | Estimated cost before processing |
| `actual_cost` | Float | - | - | null | Actual cost after completion |
| `error_message` | String | - | - | "" | Error message if failed |
| `metadata` | Object | - | - | - | Additional metadata |
| `created_at` | DateTime | ✓ (auto) | ✓ | UTC now | Record creation timestamp |
| `updated_at` | DateTime | ✓ (auto) | - | UTC now | Last update timestamp |
| `completed_at` | DateTime | - | - | null | Completion timestamp |

### Unit Type Enum

- `page` - Cost per page
- `word` - Cost per word
- `character` - Cost per character

### Transaction Status Enum

- `pending` - Transaction pending/queued
- `processing` - Transaction in progress
- `completed` - Transaction completed successfully
- `failed` - Transaction failed

### Metadata Object Schema (Optional)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_email` | String | - | Customer email address |
| `translation_service` | String | - | Translation service used (e.g., "google", "deepl") |
| `preserve_formatting` | Boolean | - | Whether to preserve original formatting |
| `original_file_type` | String | - | Original file type/extension |
| `target_file_type` | String | - | Target file type/extension |

### Indexes

1. `transaction_id_unique` - Unique index
2. `company_status_idx` - Compound index: `(company_id, status)`
3. `created_at_asc` - Single field index

### Example Document

```json
{
  "_id": ObjectId("507f1f77bcf86cd799439013"),
  "transaction_id": "TXN-MOCK-ABC123",
  "company_id": "test-company-123",
  "user_id": "test-user-456",
  "subscription_id": null,
  "file_name": "business_proposal_2024.pdf",
  "file_size": 2457600,
  "original_file_url": "https://drive.google.com/file/d/1ABC_mock_original_file/view",
  "translated_file_url": "",
  "source_language": "en",
  "target_language": "es",
  "status": "pending",
  "unit_type": "page",
  "units_count": 12,
  "price_per_unit": 0.10,
  "total_price": 1.20,
  "estimated_cost": 1.20,
  "actual_cost": null,
  "error_message": "",
  "metadata": {
    "customer_email": "test@example.com",
    "translation_service": "google",
    "preserve_formatting": true,
    "original_file_type": "pdf",
    "target_file_type": "pdf"
  },
  "created_at": ISODate("2025-10-23T10:30:00.000Z"),
  "updated_at": ISODate("2025-10-23T10:30:00.000Z"),
  "completed_at": null
}
```

### Common Queries

```javascript
// Find transaction by transaction ID
db.translation_transactions.findOne({ "transaction_id": "TXN-MOCK-ABC123" })

// Find all transactions for a company
db.translation_transactions.find({ "company_id": "test-company-123" })

// Find by status
db.translation_transactions.find({ "status": "pending" })

// Find by language pair
db.translation_transactions.find({
  "source_language": "en",
  "target_language": "es"
})

// Find subscription-based transactions
db.translation_transactions.find({ "subscription_id": { "$ne": null } })

// Find individual transactions
db.translation_transactions.find({ "subscription_id": null })

// Aggregate total cost by company
db.translation_transactions.aggregate([
  { "$group": { "_id": "$company_id", "total": { "$sum": "$total_price" } } }
])

// Find failed transactions
db.translation_transactions.find({
  "status": "failed",
  "error_message": { "$ne": "" }
})

// Find completed transactions with actual cost
db.translation_transactions.find({
  "status": "completed",
  "actual_cost": { "$ne": null }
})
```

---

## Relationships Between Collections

### Payments ↔ User Transactions

- **Link:** `user_transactions.square_payment_id` references `payments.square_payment_id`
- **Cardinality:** One-to-one (each user transaction has one payment)
- **Use Case:** Individual user payments tracking

### Payments ↔ Translation Transactions

- **Link:** Via `company_id` (indirect relationship)
- **Cardinality:** One company has many payments and many translation transactions
- **Use Case:** Company-level payment and translation tracking

### User Transactions ↔ Translation Transactions

- **Distinction:**
  - `user_transactions` - Individual user translations (B2C)
  - `translation_transactions` - Company translations (B2B)
- **No direct relationship:** Separate business flows

### Collection Decision Tree

```
Is this a company translation?
├─ YES → Use translation_transactions
│         - Can be subscription-based (subscription_id != null)
│         - Can be individual company transaction (subscription_id = null)
│
└─ NO → Is this an individual user?
         └─ YES → Use user_transactions
                  - Always includes Square payment details
                  - Direct user payment tracking
```

---

## Verification Scripts

Three Python scripts are provided to verify and document these schemas:

### 1. Payments Schema Script

```bash
python3 server/scripts/schema_payments.py
```

**What it does:**
- Documents the payments collection schema
- Creates a dummy payment record with refunds
- Verifies insertion
- Shows collection statistics
- Provides query examples

### 2. User Transactions Schema Script

```bash
python3 server/scripts/schema_user_transactions.py
```

**What it does:**
- Documents the user_transactions collection schema
- Creates a dummy user transaction record
- Verifies insertion
- Shows collection statistics
- Provides query examples

### 3. Translation Transactions Schema Script

```bash
python3 server/scripts/schema_translation_transactions.py
```

**What it does:**
- Documents the translation_transactions collection schema
- Creates a dummy translation transaction record
- Verifies insertion
- Shows collection statistics
- Provides query examples

### Running All Scripts

```bash
# Run all three scripts
cd /Users/vladimirdanishevsky/projects/Translator/server

python3 scripts/schema_payments.py
python3 scripts/schema_user_transactions.py
python3 scripts/schema_translation_transactions.py
```

---

## Data Type Mappings

### Python ↔ MongoDB Type Mapping

| Python Type | MongoDB BSON Type | Notes |
|-------------|-------------------|-------|
| `str` | String | UTF-8 encoded |
| `int` | Int32 / Int64 | Depends on value size |
| `float` | Double | 64-bit floating point |
| `bool` | Boolean | True/False |
| `datetime` | Date | UTC timezone recommended |
| `list` | Array | Can contain mixed types |
| `dict` | Object | Embedded document |
| `None` | Null | Null value |
| `ObjectId` | ObjectId | 12-byte BSON type |

### Pydantic ↔ MongoDB Type Mapping

| Pydantic Type | MongoDB BSON Type | Example |
|---------------|-------------------|---------|
| `str` | String | "hello" |
| `int` | Int32 / Int64 | 123 |
| `float` | Double | 12.99 |
| `bool` | Boolean | true |
| `datetime` | Date | ISODate("2025-10-23T10:30:00Z") |
| `List[T]` | Array | [1, 2, 3] |
| `Dict[str, Any]` | Object | {"key": "value"} |
| `Optional[T]` | T or Null | "value" or null |
| `Enum` | String | "COMPLETED" |

---

## Schema Validation Rules

### Field Naming Conventions

- Use **snake_case** for field names (e.g., `user_email`, not `userEmail`)
- Use **descriptive names** (e.g., `square_payment_id`, not `sq_id`)
- Use **consistent suffixes**:
  - `_id` for identifiers
  - `_at` for timestamps
  - `_url` for URLs
  - `_status` for status fields
  - `_count` for counts

### Required Fields

- **Always required:**
  - Business identifiers (`company_id`, `user_email`, etc.)
  - Core data fields (amounts, dates, languages)
  - Status fields

- **Auto-generated (required but automatic):**
  - `_id` - MongoDB ObjectId
  - `created_at` - Creation timestamp
  - `updated_at` - Update timestamp

- **Optional/nullable:**
  - `subscription_id` - Only for subscription-based transactions
  - `actual_cost` - Only after completion
  - `completed_at` - Only after completion
  - `error_message` - Only on failure
  - `metadata` - Optional additional data

### Default Values

- Empty arrays: `[]` for `refunds`
- Empty strings: `""` for `error_message`, `translated_file_url`
- Null values: `null` for `subscription_id`, `actual_cost`, `completed_at`
- Default strings: `"USD"` for `currency`, `"processing"` for transaction status

---

## Best Practices

### 1. Always Use UTC Timestamps

```python
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

### 2. Validate Before Insert

```python
# Validate required fields before insertion
if not all([company_id, user_email, amount]):
    raise ValueError("Missing required fields")
```

### 3. Handle Refunds as Immutable

```python
# Never modify existing refund objects
# Always append new refund objects to the array
refunds.append({
    "refund_id": generate_refund_id(),
    "amount": refund_amount,
    "status": "COMPLETED",
    "created_at": datetime.now(timezone.utc)
})
```

### 4. Update updated_at on Every Change

```python
await database.payments.update_one(
    {"_id": payment_id},
    {
        "$set": {
            "payment_status": "COMPLETED",
            "updated_at": datetime.now(timezone.utc)
        }
    }
)
```

### 5. Use Indexes for Frequent Queries

```python
# Good: Uses index on user_email
db.user_transactions.find({"user_email": "user@example.com"})

# Bad: Full collection scan (no index on user_name alone)
db.user_transactions.find({"user_name": "John Doe"})
```

---

## Next Steps

After verifying these schemas with the scripts:

1. **Update Pydantic Models** - Align Python models in `app/models/` with these schemas
2. **API Contract Testing** - Test request/response cycles match schemas
3. **Type Generation** - Generate TypeScript types from Pydantic models
4. **Integration Tests** - Write integration tests for CRUD operations
5. **Documentation** - Update API documentation with schema examples

---

## Related Documentation

- **API Endpoints:** `.claude/ENDPOINTS.md`
- **Database Setup:** `server/app/database/mongodb.py`
- **Testing Guide:** `server/tests/README.md`
- **CLAUDE.md:** Root project instructions

---

**Document Maintainers:** Backend Team
**Review Frequency:** After any schema changes
**Approval Required:** Yes (for breaking changes)
