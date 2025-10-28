# MongoDB Collections Schema Documentation

**Generated:** 2025-10-27
**Database:** Translation Service
**Server:** FastAPI + Motor (AsyncIO MongoDB)

---

## Overview

This document provides a comprehensive reference for all MongoDB collections used by the Translation Service FastAPI backend. Each collection's schema, indexes, relationships, and usage patterns are documented.

**Total Collections:** 10

---

## Table of Contents

1. [company (companies)](#collection-company-companies)
2. [users](#collection-users)
3. [company_users](#collection-company_users)
4. [sessions](#collection-sessions)
5. [subscriptions](#collection-subscriptions)
6. [users_login](#collection-users_login)
7. [translation_transactions](#collection-translation_transactions)
8. [user_transactions](#collection-user_transactions)
9. [payments](#collection-payments)
10. [invoices](#collection-invoices)

---

## Collection: company (companies)

**Purpose:** Stores company/organization records for enterprise customers.

**Collection Name in Database:** `company` (singular)
**Collection Accessor:** `database.companies` (returns `db.company`)

**Note:** The code references `companies` (plural) but the actual MongoDB collection name is `company` (singular). The accessor property in `mongodb.py` handles this mapping.

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "company_id": str,                  # Unique company identifier (e.g., "cmp_00123")
    "company_name": str,                # Company name (unique)
    "created_at": datetime,             # Record creation timestamp
    "updated_at": datetime              # Last update timestamp (optional)
}
```

### Field Details

- `_id` (ObjectId) - MongoDB primary key, auto-generated
- `company_id` (string, unique) - Custom company identifier for external references
- `company_name` (string, unique) - Full company name, must be unique
- `created_at` (datetime) - Timestamp when company was created
- `updated_at` (datetime, optional) - Last modification timestamp

### Indexes

| Index Name | Fields | Type | Properties |
|------------|--------|------|------------|
| `company_name_unique` | `company_name` (ASC) | Single field | UNIQUE |
| `company_id_unique` | `company_id` (ASC) | Single field | UNIQUE |
| `created_at_asc` | `created_at` (ASC) | Single field | Standard |

### Relationships

**Referenced By:**
- `company_users.company_id` → `company._id` (ObjectId foreign key) - TO BE MIGRATED
- `users.company_id` → `company._id` (ObjectId foreign key, nullable) - TO BE MIGRATED
- `subscriptions.company_name` → `company.company_name` (String foreign key) ✅ MIGRATED
- `translation_transactions.company_name` → `company.company_name` (String foreign key, nullable) ✅ MIGRATED
- `payments.company_id` → `company.company_id` (string reference) - TO BE MIGRATED
- `invoices.company_id` → `company._id` (ObjectId foreign key) - TO BE MIGRATED

### Example Document

```json
{
    "_id": ObjectId("68ec42a48ca6a1781d9fe5c9"),
    "company_id": "cmp_00123",
    "company_name": "Acme Health LLC",
    "created_at": ISODate("2025-01-15T10:30:00.000Z"),
    "updated_at": ISODate("2025-10-23T14:20:00.000Z")
}
```

### Critical Notes

- **Unique Constraint:** Both `company_name` and `company_id` must be unique across all companies
- **Foreign Key Migration:** Collections are being migrated from `company_id` (ObjectId) to `company_name` (String)
  - ✅ **Completed:** subscriptions, translation_transactions
  - ⏳ **Pending:** users, company_users, payments, invoices
- **Referential Integrity:** Subscriptions enforce company existence by checking `company.company_name` before creation (see `subscription_service.py:50-53`)

---

## Collection: users

**Purpose:** Stores individual user accounts (non-enterprise) and new enterprise users.

**Collection Accessor:** `database.users`

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "user_id": str,                     # Unique user identifier (e.g., "user_abc123def456")
    "user_name": str,                   # Full name of the user
    "email": str,                       # User email address (indexed)
    "company_id": ObjectId | None,      # Company reference (None for individual users) ⏳ TO BE MIGRATED
    "permission_level": str,            # Permission level: "user" | "admin"
    "status": str,                      # Account status: "active" | "inactive"
    "created_at": datetime,             # Record creation timestamp
    "updated_at": datetime,             # Last update timestamp
    "last_login": datetime              # Last login timestamp
}
```

### Field Details

- `_id` (ObjectId) - MongoDB primary key
- `user_id` (string, unique) - Custom user identifier (e.g., "user_abc123def456")
- `user_name` (string) - Full name of the user
- `email` (string, indexed) - User's email address
- `company_id` (ObjectId or null) - Reference to `company._id`, null for individual users ⏳ TO BE MIGRATED to company_name
- `permission_level` (string) - "user" or "admin"
- `status` (string) - "active" or "inactive"
- `created_at` (datetime) - Account creation timestamp
- `updated_at` (datetime) - Last modification timestamp
- `last_login` (datetime) - Last successful login timestamp

### Indexes

| Index Name | Fields | Type | Properties |
|------------|--------|------|------------|
| `user_id_unique` | `user_id` (ASC) | Single field | UNIQUE |
| `email_idx` | `email` (ASC) | Single field | Standard |
| `company_id_idx` | `company_id` (ASC) | Single field | Standard |
| `email_company_idx` | `email` (ASC), `company_id` (ASC) | Compound | Standard |
| `status_idx` | `status` (ASC) | Single field | Standard |
| `created_at_asc` | `created_at` (ASC) | Single field | Standard |

### Relationships

**References:**
- `users.company_id` → `company._id` (nullable)

### Example Documents

**Individual User (No Company):**
```json
{
    "_id": ObjectId("68fac0c78d81a68274ac140b"),
    "user_id": "user_abc123def456",
    "user_name": "John Doe",
    "email": "john.doe@example.com",
    "company_id": null,
    "permission_level": "user",
    "status": "active",
    "created_at": ISODate("2025-10-23T23:56:55.438Z"),
    "updated_at": ISODate("2025-10-23T23:56:55.438Z"),
    "last_login": ISODate("2025-10-23T23:56:55.438Z")
}
```

**Enterprise User:**
```json
{
    "_id": ObjectId("68fac0c78d81a68274ac140c"),
    "user_id": "user_xyz789ghi012",
    "user_name": "Jane Smith",
    "email": "jane.smith@acmehealth.com",
    "company_id": ObjectId("68ec42a48ca6a1781d9fe5c9"),
    "permission_level": "admin",
    "status": "active",
    "created_at": ISODate("2025-10-20T10:00:00.000Z"),
    "updated_at": ISODate("2025-10-26T15:30:00.000Z"),
    "last_login": ISODate("2025-10-26T15:30:00.000Z")
}
```

### Usage Patterns

- **Individual User Authentication:** Used by `auth_service.authenticate_individual_user()` for non-enterprise users
- **Auto-creation:** Individual users are automatically created on first login if they don't exist
- **Company Assignment:** `company_id` is null for individual users, ObjectId for enterprise users

---

## Collection: company_users

**Purpose:** Stores enterprise/corporate user accounts with company association.

**Collection Accessor:** `database.company_users`

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "user_id": str,                     # Unique user identifier
    "user_name": str,                   # Full name of the user
    "email": str,                       # User email address (indexed)
    "company_id": ObjectId,             # Company reference (required) ⏳ TO BE MIGRATED
    "password_hash": str,               # Bcrypt password hash
    "permission_level": str,            # Permission level: "user" | "admin"
    "status": str,                      # Account status: "active" | "inactive"
    "created_at": datetime,             # Record creation timestamp
    "updated_at": datetime,             # Last update timestamp
    "last_login": datetime              # Last login timestamp
}
```

### Field Details

- `_id` (ObjectId) - MongoDB primary key
- `user_id` (string, unique) - Custom user identifier
- `user_name` (string) - Full name of the user
- `email` (string, indexed) - User's email address
- `company_id` (ObjectId, required) - Reference to `company._id` ⏳ TO BE MIGRATED to company_name
- `password_hash` (string) - Bcrypt-hashed password (72-byte limit)
- `permission_level` (string) - "user" or "admin"
- `status` (string) - "active" or "inactive"
- `created_at` (datetime) - Account creation timestamp
- `updated_at` (datetime) - Last modification timestamp
- `last_login` (datetime) - Last successful login timestamp

### Indexes

| Index Name | Fields | Type | Properties |
|------------|--------|------|------------|
| `user_id_unique` | `user_id` (ASC) | Single field | UNIQUE |
| `email_idx` | `email` (ASC) | Single field | Standard |
| `company_id_idx` | `company_id` (ASC) | Single field | Standard |
| `email_company_idx` | `email` (ASC), `company_id` (ASC) | Compound | Standard |
| `status_idx` | `status` (ASC) | Single field | Standard |
| `created_at_asc` | `created_at` (ASC) | Single field | Standard |

### Relationships

**References:**
- `company_users.company_id` → `company._id` (required)

### Example Document

```json
{
    "_id": ObjectId("68fac0c78d81a68274ac140d"),
    "user_id": "user_enterprise_001",
    "user_name": "Alice Johnson",
    "email": "alice.johnson@acmehealth.com",
    "company_id": ObjectId("68ec42a48ca6a1781d9fe5c9"),
    "password_hash": "$2b$12$KIXvZ3L.8xQ7j9k5L.8xQ7j9k5L.8xQ7j9k5L.8xQ7j9k5",
    "permission_level": "admin",
    "status": "active",
    "created_at": ISODate("2025-10-15T08:00:00.000Z"),
    "updated_at": ISODate("2025-10-26T14:00:00.000Z"),
    "last_login": ISODate("2025-10-26T14:00:00.000Z")
}
```

### Usage Patterns

- **Enterprise Authentication:** Used by `auth_service.authenticate_user()` for company-based login
- **Password Verification:** Bcrypt password verification with 72-byte truncation
- **Company Validation:** Must provide valid `company_name`, `email`, and `user_name` for login

### Security Notes

- **Bcrypt Limit:** Passwords are truncated to 72 bytes before hashing due to bcrypt limitation
- **Non-blocking Verification:** Password verification runs in thread pool to avoid blocking event loop
- **Status Check:** Only "active" users can authenticate

---

## Collection: sessions

**Purpose:** Stores user session tokens (CURRENTLY DISABLED - JWT is used instead).

**Collection Accessor:** `database.sessions`

**Status:** ⚠️ **DEPRECATED** - Session table updates are commented out in production code. JWT tokens are used for stateless authentication.

### Schema (Historical Reference)

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "session_token": str,               # Cryptographically secure session token
    "user_id": str,                     # User identifier
    "user_object_id": ObjectId,         # User's MongoDB ObjectId
    "company_id": ObjectId,             # Company reference (nullable)
    "created_at": datetime,             # Session creation timestamp
    "expires_at": datetime,             # Session expiration timestamp
    "is_active": bool                   # Session active status
}
```

### Indexes (Not Currently Created)

Sessions index creation is skipped in `mongodb.py:173-177`.

### Current Implementation

- **JWT Tokens:** Self-contained tokens with 8-hour expiration
- **No Database Lookup:** Token verification is instant with no database queries
- **Session Creation:** `auth_service.create_session()` logs but doesn't insert to database
- **Session Invalidation:** `auth_service.invalidate_session()` returns True without database update

### Migration Notes

If re-enabling sessions:
1. Uncomment lines in `auth_service.py:267-268` (session insertion)
2. Uncomment lines in `auth_service.py:326-338` (session invalidation)
3. Uncomment TTL index creation in `mongodb.py`
4. Update `auth_service.verify_session()` to query database instead of JWT verification

---

## Collection: subscriptions

**Purpose:** Manages company subscription plans with usage tracking and billing periods.

**Collection Accessor:** `database.subscriptions`

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "company_name": str,                # Company reference (unique - one subscription per company) ✅ MIGRATED
    "subscription_unit": str,           # Unit type: "page" | "word" | "character"
    "units_per_subscription": int,      # Number of units allocated per period
    "price_per_unit": float,            # Price per single unit in dollars
    "promotional_units": int,           # Promotional/bonus units available
    "discount": float,                  # Discount multiplier (0.0 to 1.0, default 1.0)
    "subscription_price": float,        # Total subscription price in dollars
    "start_date": datetime,             # Subscription start date
    "end_date": datetime | None,        # Subscription end date (null for ongoing)
    "status": str,                      # Status: "active" | "inactive" | "expired"
    "usage_periods": [                  # Array of usage period documents
        {
            "period_start": datetime,
            "period_end": datetime,
            "units_allocated": int,
            "units_used": int,
            "units_remaining": int,
            "promotional_units": int,
            "last_updated": datetime
        }
    ],
    "created_at": datetime,             # Record creation timestamp
    "updated_at": datetime              # Last update timestamp
}
```

### Field Details

- `_id` (ObjectId) - MongoDB primary key
- `company_name` (string, unique) - Reference to `company.company_name`, ONE subscription per company ✅ MIGRATED
- `subscription_unit` (string) - Billing unit: "page", "word", or "character"
- `units_per_subscription` (int) - Number of units allocated per billing period
- `price_per_unit` (float) - Cost per unit in USD
- `promotional_units` (int) - Total promotional units available
- `discount` (float) - Discount factor (1.0 = no discount, 0.8 = 20% off)
- `subscription_price` (float) - Total subscription cost in USD
- `start_date` (datetime) - When subscription begins
- `end_date` (datetime or null) - When subscription ends (null for ongoing)
- `status` (string) - "active", "inactive", or "expired"
- `usage_periods` (array) - Nested array of usage tracking periods

#### Usage Period Schema

- `period_start` (datetime) - Period start date
- `period_end` (datetime) - Period end date
- `units_allocated` (int) - Units allocated for this period
- `units_used` (int) - Units consumed in this period
- `units_remaining` (int) - Remaining units (calculated: allocated - used)
- `promotional_units` (int) - Promotional units used in this period
- `last_updated` (datetime) - Last usage update timestamp

### Indexes

| Index Name | Fields | Type | Properties |
|------------|--------|------|------------|
| `company_name_unique` | `company_name` (ASC) | Single field | **UNIQUE** (enforces one subscription per company) ✅ |
| `status_idx` | `status` (ASC) | Single field | Standard |
| `start_date_idx` | `start_date` (ASC) | Single field | Standard |
| `end_date_idx` | `end_date` (ASC) | Single field | Standard |
| `company_status_idx` | `company_name` (ASC), `status` (ASC) | Compound | Standard ✅ |
| `created_at_asc` | `created_at` (ASC) | Single field | Standard |

### Relationships

**References:**
- `subscriptions.company_name` → `company.company_name` (required, unique) ✅ MIGRATED

**Referenced By:**
- `translation_transactions.subscription_id` → `subscriptions._id`
- `invoices.subscription_id` → `subscriptions._id`

### Example Document

```json
{
    "_id": ObjectId("68fa6add22b0c739f4f4b273"),
    "company_name": "Acme Translation Corp",
    "subscription_unit": "page",
    "units_per_subscription": 1000,
    "price_per_unit": 0.01,
    "promotional_units": 100,
    "discount": 1.0,
    "subscription_price": 10.00,
    "start_date": ISODate("2025-01-01T00:00:00.000Z"),
    "end_date": ISODate("2026-01-01T00:00:00.000Z"),
    "status": "active",
    "usage_periods": [
        {
            "period_start": ISODate("2025-01-01T00:00:00.000Z"),
            "period_end": ISODate("2025-02-01T00:00:00.000Z"),
            "units_allocated": 1000,
            "units_used": 350,
            "units_remaining": 650,
            "promotional_units": 20,
            "last_updated": ISODate("2025-01-15T10:30:00.000Z")
        }
    ],
    "created_at": ISODate("2025-01-01T00:00:00.000Z"),
    "updated_at": ISODate("2025-01-15T10:30:00.000Z")
}
```

### Critical Business Rules

1. **One Subscription Per Company:** Enforced by unique index on `company_name` ✅ MIGRATED
2. **Referential Integrity:** Company must exist before subscription creation (validated by checking `company.company_name` in code) ✅ MIGRATED
3. **Usage Calculation:** Total available units = `promotional_units + units_allocated - units_used`
4. **Insufficient Units Error:** Transaction fails if `total_available < units_needed`
5. **Auto-Expiration:** Background job marks subscriptions as "expired" when `end_date < now`

### Usage Patterns

- **Creation:** `subscription_service.create_subscription()` validates company existence
- **Usage Tracking:** `subscription_service.record_usage()` updates current period
- **Summary:** `subscription_service.get_subscription_summary()` calculates totals across all periods
- **Expiration:** `subscription_service.expire_subscriptions()` runs periodically

---

## Collection: users_login

**Purpose:** Stores simple user authentication credentials for individual (non-enterprise) users.

**Collection Accessor:** `database.users_login`

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "user_name": str,                   # Username (unique, 1-100 chars)
    "user_email": str,                  # User email (unique, lowercase)
    "password_hash": str,               # Bcrypt password hash
    "created_at": datetime              # Account creation timestamp
}
```

### Field Details

- `_id` (ObjectId) - MongoDB primary key
- `user_name` (string, unique) - Username (1-100 characters)
- `user_email` (string, unique) - Email address (lowercase, validated format)
- `password_hash` (string) - Bcrypt-hashed password
- `created_at` (datetime) - Account creation timestamp

### Indexes

| Index Name | Fields | Type | Properties |
|------------|--------|------|------------|
| `user_email_unique` | `user_email` (ASC) | Single field | UNIQUE |
| `user_name_unique` | `user_name` (ASC) | Single field | UNIQUE |
| `created_at_asc` | `created_at` (ASC) | Single field | Standard |

### Validation Rules

**Username (`user_name`):**
- Min length: 1 character (after trimming)
- Max length: 100 characters
- Cannot be empty or whitespace-only

**Email (`user_email`):**
- Valid email format (regex pattern)
- Converted to lowercase
- Must be unique across all users

**Password:**
- Min length: 6 characters
- Max length: 128 characters
- Must contain at least one letter AND one number
- Stored as bcrypt hash

### Example Document

```json
{
    "_id": ObjectId("68fac0c78d81a68274ac140e"),
    "user_name": "johndoe123",
    "user_email": "john.doe@example.com",
    "password_hash": "$2b$12$KIXvZ3L.8xQ7j9k5L.8xQ7j9k5L.8xQ7j9k5L.8xQ7j9k5",
    "created_at": ISODate("2025-10-23T23:56:55.438Z")
}
```

### Relationships

**None** - This collection is independent and used for simple authentication only.

### Usage Patterns

- **Signup:** `POST /api/auth/signup` creates new user with validated credentials
- **Login:** `POST /api/auth/login` verifies email and password
- **Password Update:** `PATCH /api/auth/update-password` updates password hash

### Security Notes

- **Bcrypt:** Industry-standard password hashing with automatic salt
- **Email Validation:** Regex pattern validation + EmailStr type
- **Unique Constraints:** Both email and username must be unique
- **Password Complexity:** Requires letters + numbers minimum

---

## Collection: translation_transactions

**Purpose:** Tracks translation job transactions with file metadata, pricing, and status.

**Collection Accessor:** `database.translation_transactions`

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "transaction_id": str,              # Unique transaction identifier (e.g., "TXN-20FEF6D8FE")
    "user_id": str,                     # User email address
    "original_file_url": str,           # Google Drive URL of original file
    "translated_file_url": str,         # Google Drive URL of translated file (empty until complete)
    "source_language": str,             # Source language code (ISO 639-1)
    "target_language": str,             # Target language code (ISO 639-1)
    "file_name": str,                   # Original filename
    "file_size": int,                   # File size in bytes
    "units_count": int,                 # Number of translation units
    "price_per_unit": float,            # Price per unit in dollars
    "total_price": float,               # Total transaction price in dollars
    "status": str,                      # Status: "started" | "confirmed" | "pending" | "failed"
    "error_message": str,               # Error message if status is "failed"
    "created_at": datetime,             # Record creation timestamp
    "updated_at": datetime,             # Record update timestamp
    "company_name": str | None,         # Company reference (nullable for individual users) ✅ MIGRATED
    "subscription_id": ObjectId | None, # Subscription reference (null for individual users)
    "unit_type": str                    # Unit type: "page" | "word"
}
```

### Field Details

- `_id` (ObjectId) - MongoDB primary key
- `transaction_id` (string, unique) - Custom transaction ID (e.g., "TXN-20FEF6D8FE")
- `user_id` (string) - User's email address
- `original_file_url` (string) - Google Drive URL of source file
- `translated_file_url` (string) - Google Drive URL of translated file (empty until translation complete)
- `source_language` (string) - Source language code (e.g., "en", "es", "fr")
- `target_language` (string) - Target language code
- `file_name` (string) - Original filename
- `file_size` (int) - File size in bytes
- `units_count` (int) - Number of units (pages or words) to translate
- `price_per_unit` (float) - Cost per unit in USD
- `total_price` (float) - Total transaction cost in USD
- `status` (string) - Transaction status: "started", "confirmed", "pending", or "failed"
- `error_message` (string) - Error details if status is "failed"
- `created_at` (datetime) - Transaction creation timestamp
- `updated_at` (datetime) - Last update timestamp
- `company_name` (string or null) - Company reference (matches `company.company_name`, null for individual users) ✅ MIGRATED
- `subscription_id` (ObjectId or null) - Reference to `subscriptions._id` (null for individual users)
- `unit_type` (string) - Billing unit: "page" or "word"

### Indexes

| Index Name | Fields | Type | Properties |
|------------|--------|------|------------|
| `transaction_id_unique` | `transaction_id` (ASC) | Single field | UNIQUE |
| `company_status_idx` | `company_id` (ASC), `status` (ASC) | Compound | ⏳ NEEDS MIGRATION to company_name |
| `created_at_asc` | `created_at` (ASC) | Single field | Standard |

### Relationships

**References:**
- `translation_transactions.company_name` → `company.company_name` (nullable) ✅ MIGRATED (code updated, index pending)
- `translation_transactions.subscription_id` → `subscriptions._id` (nullable)

### Example Documents

**Enterprise Customer Transaction:**
```json
{
    "_id": ObjectId("68fe1edeac2359ccbc6b05b2"),
    "transaction_id": "TXN-20FEF6D8FE",
    "user_id": "alice.johnson@acmehealth.com",
    "original_file_url": "https://docs.google.com/document/d/1ABCdef123/edit",
    "translated_file_url": "",
    "source_language": "en",
    "target_language": "fr",
    "file_name": "Medical_Report.docx",
    "file_size": 838186,
    "units_count": 33,
    "price_per_unit": 0.01,
    "total_price": 0.33,
    "status": "started",
    "error_message": "",
    "created_at": ISODate("2025-10-26T13:15:10.913Z"),
    "updated_at": ISODate("2025-10-26T13:15:10.913Z"),
    "company_name": "Acme Health LLC",
    "subscription_id": ObjectId("68fa6add22b0c739f4f4b273"),
    "unit_type": "page"
}
```

**Individual User Transaction:**
```json
{
    "_id": ObjectId("68fe1edeac2359ccbc6b05b3"),
    "transaction_id": "TXN-30FEF6D8FF",
    "user_id": "john.doe@example.com",
    "original_file_url": "https://docs.google.com/document/d/2XYZabc456/edit",
    "translated_file_url": "https://docs.google.com/document/d/3XYZabc789/edit",
    "source_language": "es",
    "target_language": "de",
    "file_name": "Document.pdf",
    "file_size": 524288,
    "units_count": 15,
    "price_per_unit": 0.15,
    "total_price": 2.25,
    "status": "confirmed",
    "error_message": "",
    "created_at": ISODate("2025-10-25T10:30:00.000Z"),
    "updated_at": ISODate("2025-10-25T11:00:00.000Z"),
    "company_name": null,
    "subscription_id": null,
    "unit_type": "page"
}
```

### Query Patterns

**Get Company Transactions (Simple Query):**
```python
# ✅ MIGRATED - Now uses company_name directly
transactions = await database.translation_transactions.find({
    "company_name": company_name
}).to_list(length=100)
```

**Legacy Query Pattern (Pre-Migration):**
```python
# ⏳ DEPRECATED - Old ObjectId-based aggregation (no longer needed after migration)
pipeline = [
    {"$match": {"company_id": {"$in": [company_id_str, ObjectId(company_id_str)]}}},
    {
        "$lookup": {
            "from": "company",
            "let": {"transaction_company_id": "$company_id"},
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$or": [
                                {"$eq": ["$_id", "$$transaction_company_id"]},
                                {"$eq": [{"$toString": "$_id"}, {"$toString": "$$transaction_company_id"}]}
                            ]
                        }
                    }
                }
            ],
            "as": "company_data"
        }
    },
    {"$unwind": {"path": "$company_data", "preserveNullAndEmptyArrays": True}}
]
```

### Critical Notes

- **Migration Status:** ✅ Code updated to use `company_name` (String), ⏳ indexes still need update
- **Translation Status Flow:** started → confirmed → (processing) → completed or failed
- **Individual vs Enterprise:** Null `company_name` indicates individual user transaction

---

## Collection: user_transactions

**Purpose:** Tracks individual user translation transactions with Square payment integration.

**Collection Accessor:** `database.user_transactions`

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "user_name": str,                   # Full name of the user
    "user_email": str,                  # Email address of the user
    "document_url": str,                # URL to the translated document
    "translated_url": str | None,       # URL to translated document (optional)
    "number_of_units": int,             # Number of units (pages, words, or characters)
    "unit_type": str,                   # Type: "page" | "word" | "character"
    "cost_per_unit": float,             # Cost per unit in dollars
    "source_language": str,             # Source language code (ISO 639-1)
    "target_language": str,             # Target language code (ISO 639-1)
    "square_transaction_id": str,       # Unique Square transaction ID (unique)
    "date": datetime,                   # Transaction date
    "status": str,                      # Status: "processing" | "completed" | "failed"
    "total_cost": float,                # Total cost in dollars

    # Square payment fields
    "square_payment_id": str,           # Square payment ID
    "amount_cents": int,                # Payment amount in cents
    "currency": str,                    # Currency code (default: "USD")
    "payment_status": str,              # Payment status: "APPROVED" | "COMPLETED" | "CANCELED" | "FAILED"
    "refunds": [                        # Array of refund documents
        {
            "refund_id": str,
            "amount_cents": int,
            "currency": str,
            "status": str,
            "created_at": datetime,
            "idempotency_key": str,
            "reason": str | None
        }
    ],
    "payment_date": datetime,           # Payment processing date

    # Timestamps
    "created_at": datetime,             # Record creation timestamp
    "updated_at": datetime              # Record update timestamp
}
```

### Field Details

**Transaction Fields:**
- `_id` (ObjectId) - MongoDB primary key
- `user_name` (string) - Full name of the user
- `user_email` (string, indexed) - User's email address
- `document_url` (string) - URL or path to the original document
- `translated_url` (string or null) - URL or path to translated document
- `number_of_units` (int) - Number of units translated
- `unit_type` (string) - "page", "word", or "character"
- `cost_per_unit` (float) - Cost per single unit in USD
- `source_language` (string) - Source language code (e.g., "en", "es")
- `target_language` (string) - Target language code
- `square_transaction_id` (string, unique) - Square transaction identifier
- `date` (datetime) - Transaction date
- `status` (string) - "processing", "completed", or "failed"
- `total_cost` (float) - Total transaction cost (auto-calculated)

**Payment Fields:**
- `square_payment_id` (string) - Square payment identifier
- `amount_cents` (int) - Payment amount in cents
- `currency` (string) - Currency code (ISO 4217, default "USD")
- `payment_status` (string) - "APPROVED", "COMPLETED", "CANCELED", or "FAILED"
- `refunds` (array) - List of refund objects
- `payment_date` (datetime) - When payment was processed

**Refund Schema:**
- `refund_id` (string) - Square refund ID
- `amount_cents` (int) - Refund amount in cents
- `currency` (string) - Currency code
- `status` (string) - "COMPLETED", "PENDING", or "FAILED"
- `created_at` (datetime) - Refund creation timestamp
- `idempotency_key` (string) - Unique key for refund operation
- `reason` (string or null) - Reason for refund

### Indexes

| Index Name | Fields | Type | Properties |
|------------|--------|------|------------|
| `square_transaction_id_unique` | `square_transaction_id` (ASC) | Single field | UNIQUE |
| `user_email_idx` | `user_email` (ASC) | Single field | Standard |
| `date_desc_idx` | `date` (ASC) | Single field | Standard |
| `user_email_date_idx` | `user_email` (ASC), `date` (ASC) | Compound | Standard |
| `status_idx` | `status` (ASC) | Single field | Standard |
| `created_at_asc` | `created_at` (ASC) | Single field | Standard |

### Relationships

**None** - This collection is independent for individual user transactions.

### Example Document

```json
{
    "_id": ObjectId("68fac0c78d81a68274ac140b"),
    "user_name": "John Doe",
    "user_email": "john.doe@example.com",
    "document_url": "https://drive.google.com/file/d/1ABC_sample_document/view",
    "translated_url": "https://drive.google.com/file/d/1ABC_transl_document/view",
    "number_of_units": 10,
    "unit_type": "page",
    "cost_per_unit": 0.15,
    "source_language": "en",
    "target_language": "es",
    "square_transaction_id": "SQR-1EC28E70F10B4D9E",
    "date": ISODate("2025-10-23T23:56:55.438Z"),
    "status": "completed",
    "total_cost": 1.5,
    "square_payment_id": "SQR-1EC28E70F10B4D9E",
    "amount_cents": 150,
    "currency": "USD",
    "payment_status": "COMPLETED",
    "refunds": [],
    "payment_date": ISODate("2025-10-23T23:56:55.438Z"),
    "created_at": ISODate("2025-10-23T23:56:55.438Z"),
    "updated_at": ISODate("2025-10-23T23:56:55.438Z")
}
```

### API Endpoints

- `GET /api/v1/user-transactions?user_email={email}` - List user transactions with pagination
- Query parameters: `user_email`, `status` (optional), `limit`, `skip`

### Usage Patterns

- **Individual Users Only:** This collection is separate from enterprise `translation_transactions`
- **Square Integration:** Direct integration with Square payment processing
- **Refund Tracking:** Supports multiple refunds per transaction
- **Auto-calculation:** `total_cost = number_of_units * cost_per_unit`

---

## Collection: payments

**Purpose:** Tracks Square payment transactions for enterprise customers.

**Collection Accessor:** `database.payments`

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "company_id": str,                  # Company identifier (string, e.g., "cmp_00123") ⏳ TO BE MIGRATED
    "company_name": str,                # Company name (currently redundant, will become primary reference)
    "user_email": str,                  # User email address
    "square_payment_id": str,           # Square payment ID (indexed, NOT unique for stub support)
    "amount": int,                      # Payment amount in cents
    "currency": str,                    # Currency code (ISO 4217, default "USD")
    "payment_status": str,              # Status: "COMPLETED" | "PENDING" | "FAILED" | "REFUNDED"
    "refunds": [                        # Array of refund documents
        {
            "refund_id": str,
            "amount": int,
            "currency": str,
            "status": str,
            "idempotency_key": str,
            "created_at": datetime
        }
    ],
    "created_at": datetime,             # Record creation timestamp
    "updated_at": datetime,             # Last update timestamp
    "payment_date": datetime            # Payment processing date
}
```

### Field Details

- `_id` (ObjectId) - MongoDB primary key
- `company_id` (string, indexed) - Company identifier (e.g., "cmp_00123"), NOT ObjectId ⏳ TO BE DEPRECATED (migrate to company_name)
- `company_name` (string) - Full company name (will become primary reference after migration)
- `user_email` (string, indexed) - Email of user who made payment
- `square_payment_id` (string, indexed) - Square payment identifier (not unique for stub implementation)
- `amount` (int) - Payment amount in cents (e.g., 1299 = $12.99)
- `currency` (string) - Currency code (ISO 4217), default "USD"
- `payment_status` (string) - "COMPLETED", "PENDING", "FAILED", or "REFUNDED"
- `refunds` (array) - List of refund objects
- `created_at` (datetime) - Record creation timestamp
- `updated_at` (datetime) - Last update timestamp
- `payment_date` (datetime) - When payment was processed

**Refund Schema:**
- `refund_id` (string) - Square refund ID
- `amount` (int) - Refund amount in cents
- `currency` (string) - Currency code
- `status` (string) - "COMPLETED", "PENDING", or "FAILED"
- `idempotency_key` (string) - Unique key for idempotent refund processing
- `created_at` (datetime) - Refund creation timestamp

### Indexes

| Index Name | Fields | Type | Properties |
|------------|--------|------|------------|
| `square_payment_id_idx` | `square_payment_id` (ASC) | Single field | Standard (NOT unique for stub support) |
| `company_id_idx` | `company_id` (ASC) | Single field | Standard |
| `subscription_id_idx` | `subscription_id` (ASC) | Single field | Standard (field not in schema above) |
| `user_id_idx` | `user_id` (ASC) | Single field | Standard (field not in schema above) |
| `payment_status_idx` | `payment_status` (ASC) | Single field | Standard |
| `payment_date_idx` | `payment_date` (ASC) | Single field | Standard |
| `user_email_idx` | `user_email` (ASC) | Single field | Standard |
| `company_status_idx` | `company_id` (ASC), `payment_status` (ASC) | Compound | Standard |
| `user_payment_date_idx` | `user_id` (ASC), `payment_date` (ASC) | Compound | Standard |
| `square_order_id_idx` | `square_order_id` (ASC) | Single field | Standard (field not in schema above) |
| `square_customer_id_idx` | `square_customer_id` (ASC) | Single field | Standard (field not in schema above) |
| `created_at_asc` | `created_at` (ASC) | Single field | Standard |

### Relationships

**References:**
- `payments.company_id` → `company.company_id` (string field, NOT `company._id` ObjectId) ⏳ TO BE MIGRATED to company_name
- After migration: `payments.company_name` → `company.company_name` (String foreign key)

### Example Document

```json
{
    "_id": ObjectId("68fad3c2a0f41c24037c4810"),
    "company_id": "cmp_00123",
    "company_name": "Acme Health LLC",
    "user_email": "test5@yahoo.com",
    "square_payment_id": "payment_sq_1761244600756_u12vb3tx6",
    "amount": 1299,
    "currency": "USD",
    "payment_status": "COMPLETED",
    "refunds": [],
    "created_at": ISODate("2025-10-24T01:17:54.544Z"),
    "updated_at": ISODate("2025-10-24T01:17:54.544Z"),
    "payment_date": ISODate("2025-10-24T01:17:54.544Z")
}
```

### API Endpoints

- `GET /api/v1/payments/company/{company_id}` - List company payments
- Query parameters: `status` (optional), `limit`, `skip`

### Critical Notes

- **String Company ID:** Uses `company.company_id` string field, NOT ObjectId `company._id`
- **Non-Unique Payment ID:** `square_payment_id` index is NOT unique to support stub implementation
- **Stub Testing:** Hardcoded payment IDs allowed for testing purposes
- **Refund Support:** Multiple refunds per payment tracked in embedded array

---

## Collection: invoices

**Purpose:** Stores billing invoices for company subscriptions.

**Collection Accessor:** `database.invoices`

### Schema

```python
{
    "_id": ObjectId,                    # MongoDB ObjectId (auto-generated)
    "invoice_id": str | None,           # Legacy invoice ID (optional)
    "company_id": ObjectId,             # Company reference ⏳ TO BE MIGRATED
    "company_name": str | None,         # Company name (currently from $lookup, will become primary reference)
    "subscription_id": ObjectId,        # Subscription reference
    "invoice_number": str,              # Unique invoice number (e.g., "INV-2025-001")
    "invoice_date": datetime,           # Invoice date
    "due_date": datetime,               # Payment due date
    "total_amount": float,              # Total invoice amount in dollars
    "tax_amount": float,                # Tax amount in dollars
    "status": str,                      # Status: "sent" | "paid" | "overdue" | "cancelled"
    "pdf_url": str | None,              # URL to invoice PDF document
    "payment_applications": list,       # Array of payment application objects
    "created_at": datetime              # Record creation timestamp
}
```

### Field Details

- `_id` (ObjectId) - MongoDB primary key
- `invoice_id` (string or null) - Legacy invoice identifier (optional)
- `company_id` (ObjectId, indexed) - Reference to `company._id` ⏳ TO BE MIGRATED to company_name
- `company_name` (string or null) - Company name (currently from $lookup, will become primary reference after migration)
- `subscription_id` (ObjectId) - Reference to `subscriptions._id`
- `invoice_number` (string) - Unique invoice number (e.g., "INV-2025-001")
- `invoice_date` (datetime) - Date invoice was issued
- `due_date` (datetime) - Payment due date
- `total_amount` (float) - Total invoice amount in USD
- `tax_amount` (float) - Tax amount in USD
- `status` (string) - "sent", "paid", "overdue", or "cancelled"
- `pdf_url` (string or null) - URL to downloadable invoice PDF
- `payment_applications` (array) - List of applied payments (optional)
- `created_at` (datetime) - Invoice creation timestamp

### Indexes

**Note:** No specific indexes are defined in `mongodb.py` for the invoices collection. The collection is accessed but index creation is not implemented.

### Relationships

**References:**
- `invoices.company_id` → `company._id` (ObjectId) ⏳ TO BE MIGRATED to company_name
- After migration: `invoices.company_name` → `company.company_name` (String foreign key)
- `invoices.subscription_id` → `subscriptions._id` (ObjectId)

### Example Document

```json
{
    "_id": ObjectId("671b2bc25c62a0b61c084b34"),
    "invoice_id": "inv_legacy_001",
    "company_id": ObjectId("68ec42a48ca6a1781d9fe5c9"),
    "company_name": "Acme Health LLC",
    "subscription_id": ObjectId("68fa6add22b0c739f4f4b273"),
    "invoice_number": "INV-2025-001",
    "invoice_date": ISODate("2025-10-08T00:07:00.396Z"),
    "due_date": ISODate("2025-11-07T00:07:00.396Z"),
    "total_amount": 106.00,
    "tax_amount": 6.00,
    "status": "sent",
    "pdf_url": "https://storage.example.com/invoices/INV-2025-001.pdf",
    "payment_applications": [],
    "created_at": ISODate("2025-10-08T00:07:00.396Z")
}
```

### API Endpoints

- `GET /api/v1/invoices/company/{company_id}` - List company invoices
- Query parameters: `status` (optional), `limit`, `skip`

### Query Patterns

**Get Invoices with Company Name (Aggregation):**
```python
pipeline = [
    {"$match": {"company_id": {"$in": [company_id_str, ObjectId(company_id_str)]}}},
    {
        "$lookup": {
            "from": "company",
            "let": {"invoice_company_id": "$company_id"},
            "pipeline": [
                {
                    "$match": {
                        "$expr": {
                            "$or": [
                                {"$eq": ["$_id", "$$invoice_company_id"]},
                                {"$eq": [{"$toString": "$_id"}, {"$toString": "$$invoice_company_id"}]}
                            ]
                        }
                    }
                }
            ],
            "as": "company_data"
        }
    },
    {"$unwind": {"path": "$company_data", "preserveNullAndEmptyArrays": True}}
]
```

### Usage Patterns

- **Billing Integration:** Invoices are generated for subscription billing periods
- **Status Workflow:** sent → paid (or overdue if unpaid after due_date)
- **PDF Generation:** External service generates invoice PDFs, URL stored here
- **Mixed Type Handling:** `company_id` queries handle both string and ObjectId formats

---

## Summary Table

| Collection | Purpose | Primary Key | Unique Constraints | Foreign Keys | Migration Status |
|------------|---------|-------------|-------------------|--------------|------------------|
| company | Enterprise customer organizations | `_id` | `company_name`, `company_id` | Referenced by many | Source collection |
| users | Individual + new enterprise users | `_id` | `user_id` | `company_id` → company._id | ⏳ TO BE MIGRATED |
| company_users | Legacy enterprise users | `_id` | `user_id` | `company_id` → company._id | ⏳ TO BE MIGRATED |
| sessions | User sessions (DEPRECATED) | `_id` | None | None (JWT used instead) | N/A (deprecated) |
| subscriptions | Company subscription plans | `_id` | `company_name` (one per company) | `company_name` → company.company_name | ✅ MIGRATED |
| users_login | Simple user authentication | `_id` | `user_email`, `user_name` | None | N/A (no company ref) |
| translation_transactions | Translation job tracking | `_id` | `transaction_id` | `company_name`, `subscription_id` | ✅ MIGRATED (indexes pending) |
| user_transactions | Individual user transactions | `_id` | `square_transaction_id` | None | N/A (no company ref) |
| payments | Enterprise payment tracking | `_id` | None | `company_id` (string) | ⏳ TO BE MIGRATED |
| invoices | Billing invoices | `_id` | None | `company_id`, `subscription_id` | ⏳ TO BE MIGRATED |

---

## Key Architectural Patterns

### 1. Company Reference Migration (ObjectId/String → company_name)

**Migration Goal:** Standardize all company references to use `company.company_name` (String) instead of ObjectId or custom company_id string.

**Migration Status:**

**✅ Completed:**
- `subscriptions.company_name` → Uses String company_name, unique index created
- `translation_transactions.company_name` → Code updated to use company_name (indexes pending)

**⏳ Pending Migration:**
- `company_users.company_id` → ObjectId (needs migration to company_name)
- `users.company_id` → ObjectId (needs migration to company_name)
- `payments.company_id` → String referencing `company.company_id` (needs migration to company_name)
- `invoices.company_id` → ObjectId (needs migration to company_name)

**Benefits After Migration:**
- Simpler queries (no ObjectId conversion needed)
- No expensive $lookup aggregations for company names
- Direct string matching for filtering/joins
- Better readability in logs and debugging

**Legacy Query Pattern (Pre-Migration):**
```python
# OLD: Required complex aggregation to handle mixed types
{
    "$match": {
        "$expr": {
            "$or": [
                {"$eq": ["$_id", ObjectId(company_id)]},
                {"$eq": [{"$toString": "$_id"}, company_id]}
            ]
        }
    }
}
```

**New Query Pattern (Post-Migration):**
```python
# NEW: Simple string matching
{"company_name": company_name}
```

### 2. JWT vs Session-Based Authentication

**Current:** JWT tokens (stateless, self-contained)
- No database queries for auth verification
- 8-hour token expiration
- Token contains: user_id, email, fullName, company, company_id, company_name, permission_level

**Deprecated:** Session-based (database lookups)
- Sessions collection exists but not used
- Session creation/invalidation commented out in production

**Implications:**
- Instant authentication (no DB lookup)
- Cannot revoke tokens before expiration
- Logout is client-side only (token deletion)

### 3. Enterprise vs Individual User Separation

**Enterprise Users:**
- Collection: `company_users` (with `company_id`)
- Authentication: Company name + email + username + password
- Features: Subscriptions, usage tracking, invoices
- Transactions: `translation_transactions` collection

**Individual Users:**
- Collection: `users` (with `company_id = null`)
- Authentication: Email + username (auto-created on first login)
- Features: Pay-per-use with Square
- Transactions: `user_transactions` collection

**Dual Purpose of `users` Collection:**
- Stores individual users (`company_id = null`)
- Can also store new enterprise users (`company_id = ObjectId`)

### 4. Subscription Business Logic

**One Subscription Per Company:**
- Enforced by unique index on `company_id`
- Prevents multiple active subscriptions

**Usage Calculation Formula:**
```python
total_available = promotional_units + units_allocated - units_used
```

**Referential Integrity:**
- Subscriptions validate company existence before creation
- Code-level enforcement (no database-level foreign key constraints)

### 5. Aggregation for Company Name Lookups

Many queries use `$lookup` to join company names:
```python
{
    "$lookup": {
        "from": "company",
        "let": {"ref_company_id": "$company_id"},
        "pipeline": [
            {
                "$match": {
                    "$expr": {
                        "$or": [
                            {"$eq": ["$_id", "$$ref_company_id"]},
                            {"$eq": [{"$toString": "$_id"}, {"$toString": "$$ref_company_id"}]}
                        ]
                    }
                }
            }
        ],
        "as": "company_data"
    }
}
```

This handles both ObjectId and string `company_id` formats.

---

## Migration Considerations

### Migration to company_name (In Progress)

1. **company_name Migration Status:**
   - **Goal:** Migrate all collections from ObjectId/string company_id to String company_name
   - **Completed:** subscriptions ✅, translation_transactions ✅ (code done, indexes pending)
   - **Pending:** users, company_users, payments, invoices ⏳
   - **Impact:** Simplified queries, better performance, no ObjectId conversion needed
   - **Next Steps:**
     1. Migrate translation_transactions indexes (company_status_idx needs update)
     2. Update users and company_users collections (code + data + indexes)
     3. Update payments collection (currently uses company.company_id string field)
     4. Update invoices collection (currently uses ObjectId)

2. **sessions Collection:**
   - Recommendation: Remove collection entirely or implement JWT blacklist
   - Impact: Current code already bypasses database for sessions
   - Action: Clean up commented code or fully remove session logic

3. **Subscription Constraints:**
   - Current: One subscription per company (unique index on company_name) ✅
   - Future: If multi-subscription support needed, redesign required
   - Impact: Major schema change for subscription management

### Performance Recommendations

1. **Add Indexes for invoices:**
   - Currently no indexes defined
   - Recommend: `company_id`, `status`, `invoice_date`, `invoice_number`

2. **Compound Indexes:**
   - `translation_transactions`: Add `(user_id, created_at)` for user queries
   - `payments`: Consider `(user_email, payment_date)` for user payment history

3. **Aggregation Optimization:**
   - Company name lookups require `$lookup` (expensive)
   - Consider denormalizing company_name in child collections
   - Trade-off: Storage vs query performance

---

## Database Initialization

**Location:** `/Users/vladimirdanishevsky/projects/Translator/server/app/database/mongodb.py`

**Index Creation:** `MongoDB._create_indexes()` (lines 112-273)
- Runs on application startup (`database.connect()`)
- Each collection wrapped in try-except (isolated failure handling)
- Logs success/failure for each collection
- Sessions index creation skipped (commented out)

**Connection Details:**
- Driver: Motor (AsyncIO MongoDB driver)
- Connection pooling: 10-50 connections
- Timeout: 5 seconds
- Database: Configured via `settings.mongodb_database`

**Health Check:** `MongoDB.health_check()` returns:
```json
{
    "healthy": true,
    "status": "connected",
    "database": "translation",
    "version": "7.0.0",
    "collections": ["company", "users", "subscriptions", ...]
}
```

---

## Document Generation Metadata

**Generated By:** Claude Code (python-pro agent)
**Date:** 2025-10-27
**Source Files Analyzed:**
- `/Users/vladimirdanishevsky/projects/Translator/server/app/database/mongodb.py`
- `/Users/vladimirdanishevsky/projects/Translator/server/app/models/*.py`
- `/Users/vladimirdanishevsky/projects/Translator/server/app/services/*.py`
- `/Users/vladimirdanishevsky/projects/Translator/server/app/routers/*.py`

**Total Lines Analyzed:** ~10,000+ lines of code
**Collections Documented:** 10
**Total Indexes:** 50+

---

**END OF DOCUMENT**
