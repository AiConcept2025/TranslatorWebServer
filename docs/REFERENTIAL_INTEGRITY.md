# MongoDB Referential Integrity Implementation

## Overview

This document describes the database-level referential integrity implementation for the Translation Service MongoDB database, specifically for the relationship between `companies` and `subscriptions` collections.

## Problem Statement

MongoDB, unlike relational databases, does not have built-in foreign key constraints. This means:

1. **No automatic validation**: A subscription can reference a non-existent company
2. **Orphaned records**: Subscriptions can exist without corresponding companies
3. **Data inconsistency**: Application-level validation can be bypassed
4. **Runtime errors**: Missing companies can cause application failures

## Solution Architecture

### Multi-Layered Approach

Our solution implements referential integrity through **three complementary layers**:

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Application-Level Validation (Pydantic)           │
│ - Type checking, business rules, API validation            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Database-Level Schema Validation (JSON Schema)    │
│ - Field requirements, data types, enum values              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Performance Optimization (Indexes)                │
│ - Unique constraints, lookup optimization                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Continuous Verification (Monitoring Scripts)      │
│ - Integrity checks, orphan detection, reporting            │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Details

### 1. Schema Validation Rules

MongoDB JSON Schema validation enforces data integrity at the database level:

#### Companies Collection

```javascript
{
  "$jsonSchema": {
    "bsonType": "object",
    "required": ["company_name", "created_at", "updated_at"],
    "properties": {
      "company_name": {
        "bsonType": "string",
        "minLength": 1,
        "maxLength": 255,
        "description": "Company name must be a non-empty string (1-255 chars)"
      },
      "created_at": {
        "bsonType": "date",
        "description": "Creation timestamp must be a date"
      },
      "updated_at": {
        "bsonType": "date",
        "description": "Update timestamp must be a date"
      }
    },
    "additionalProperties": true
  }
}
```

**Enforces:**
- ✅ `company_name` is required and non-empty
- ✅ `company_name` length between 1-255 characters
- ✅ `created_at` and `updated_at` are valid dates
- ✅ Additional fields allowed for extensibility

#### Subscriptions Collection

```javascript
{
  "$jsonSchema": {
    "bsonType": "object",
    "required": [
      "company_name", "subscription_unit", "units_per_subscription",
      "price_per_unit", "subscription_price", "start_date",
      "status", "usage_periods", "created_at", "updated_at"
    ],
    "properties": {
      "company_name": {
        "bsonType": "string",
        "minLength": 1,
        "maxLength": 255,
        "description": "Company name must reference an existing company"
      },
      "subscription_unit": {
        "enum": ["page", "word", "character"],
        "description": "Must be one of: page, word, character"
      },
      "units_per_subscription": {
        "bsonType": "int",
        "minimum": 1
      },
      "status": {
        "enum": ["active", "inactive", "expired"]
      },
      // ... additional fields
    }
  }
}
```

**Enforces:**
- ✅ `company_name` is required (referential integrity requirement)
- ✅ Enum values for `subscription_unit` and `status`
- ✅ Positive integers for units
- ✅ All required fields present

**Limitation:** MongoDB JSON Schema **cannot directly validate** that `company_name` exists in the `companies` collection. This is handled by:
- Application-level checks before insert/update
- Verification scripts for continuous monitoring

### 2. Index Strategy

#### Companies Collection Indexes

```javascript
// 1. Unique index on company_name (primary identifier)
db.companies.createIndex(
  { company_name: 1 },
  { name: "company_name_unique", unique: true }
)

// 2. Ascending index on created_at (for sorting/filtering)
db.companies.createIndex(
  { created_at: 1 },
  { name: "created_at_asc" }
)
```

**Benefits:**
- ✅ Prevents duplicate companies
- ✅ Fast company lookup by name (O(log n))
- ✅ Efficient temporal queries

#### Subscriptions Collection Indexes

```javascript
// 1. Non-unique index on company_name (CRITICAL for foreign key lookups)
db.subscriptions.createIndex(
  { company_name: 1 },
  { name: "company_name_idx", unique: false }  // Must NOT be unique!
)

// 2. Status index (for filtering active/inactive subscriptions)
db.subscriptions.createIndex(
  { status: 1 },
  { name: "status_idx" }
)

// 3. Compound index for common queries
db.subscriptions.createIndex(
  { company_name: 1, status: 1 },
  { name: "company_status_idx" }
)

// 4. Date range indexes
db.subscriptions.createIndex({ start_date: 1 }, { name: "start_date_idx" })
db.subscriptions.createIndex({ end_date: 1 }, { name: "end_date_idx" })
```

**Benefits:**
- ✅ Fast company → subscriptions lookup (O(log n))
- ✅ Supports multiple subscriptions per company
- ✅ Optimized for common query patterns
- ✅ Efficient date range filtering

**Critical Fix:** The original implementation had `company_name` with `unique: true`, which prevented multiple subscriptions per company. The migration script fixes this.

### 3. Application-Level Validation

**Before Database Insert/Update:**

```python
# Example: Creating a subscription
async def create_subscription(subscription_data: SubscriptionCreate):
    # 1. Validate company exists
    company = await db.companies.find_one({"company_name": subscription_data.company_name})
    if not company:
        raise HTTPException(
            status_code=404,
            detail=f"Company '{subscription_data.company_name}' not found"
        )

    # 2. Insert subscription (will be validated by JSON Schema)
    result = await db.subscriptions.insert_one(subscription_data.dict())
    return result
```

**Validation Flow:**
```
API Request → Pydantic Validation → Company Exists Check → JSON Schema Validation → Insert
```

### 4. Continuous Verification

**Monitoring Script:** `scripts/verify_data_integrity.py`

Runs periodically to detect:
- Orphaned subscriptions (company_name references non-existent company)
- Missing companies
- Schema validation issues
- Index configuration problems

**Integration Options:**
1. **Cron Job:** Run daily/weekly
2. **CI/CD Pipeline:** Run before deployments
3. **Health Check Endpoint:** Expose as API endpoint
4. **Monitoring Dashboard:** Integrate with DataDog/CloudWatch

## Scripts Usage

### 1. Migration Script

**Purpose:** Apply referential integrity to existing database

**Usage:**

```bash
# Step 1: Dry run (recommended first)
python scripts/add_referential_integrity.py --dry-run

# Step 2: Review output, then apply
python scripts/add_referential_integrity.py

# Step 3: Verify success
python scripts/verify_data_integrity.py
```

**What It Does:**
1. ✅ Verifies existing data integrity
2. ✅ Fixes unique constraint issue on `subscriptions.company_name`
3. ✅ Applies JSON Schema validation to both collections
4. ✅ Creates/updates indexes
5. ❌ **Does NOT delete any data** (safe operation)

**Example Output:**

```
================================================================================
MONGODB REFERENTIAL INTEGRITY MIGRATION
================================================================================
Database: translation
Mode: APPLY CHANGES
Time: 2025-11-15T12:00:00

================================================================================
STEP 1: DATA INTEGRITY VERIFICATION
================================================================================
📊 Found 5 unique companies in subscriptions
📊 Found 5 companies in companies collection

✅ Data integrity check PASSED
   All subscriptions reference existing companies

================================================================================
STEP 2: FIX UNIQUE CONSTRAINT ISSUE
================================================================================
⚠️  Found incorrect unique constraint on subscriptions.company_name
✅ Dropped incorrect unique index: company_name_unique
✅ Created non-unique index: company_name_idx

================================================================================
STEP 3: APPLY SCHEMA VALIDATION
================================================================================
📋 Applying schema validation to 'companies' collection...
✅ Applied schema validation to 'companies'

📋 Applying schema validation to 'subscriptions' collection...
✅ Applied schema validation to 'subscriptions'

================================================================================
STEP 4: CREATE/UPDATE INDEXES
================================================================================
📊 Creating indexes for 'companies' collection...
   ℹ️  Index already exists: company_name_unique
   ℹ️  Index already exists: created_at_asc

📊 Creating indexes for 'subscriptions' collection...
   ✅ Created index: company_name_idx
   ℹ️  Index already exists: status_idx

================================================================================
✅ MIGRATION COMPLETED SUCCESSFULLY
================================================================================
```

### 2. Verification Script

**Purpose:** Check data integrity and optionally fix issues

**Usage:**

```bash
# Check integrity only (read-only)
python scripts/verify_data_integrity.py

# Check and fix by creating missing companies
python scripts/verify_data_integrity.py --fix

# Verbose output with details
python scripts/verify_data_integrity.py --verbose

# Export report to JSON
python scripts/verify_data_integrity.py --export report.json

# Check test database
python scripts/verify_data_integrity.py --database translation_test
```

**What It Checks:**
1. ✅ Referential integrity (all subscriptions have valid companies)
2. ✅ Schema validation configuration
3. ✅ Index configuration and correctness
4. ✅ Orphaned subscriptions detection

**Example Output:**

```
================================================================================
MONGODB DATA INTEGRITY VERIFICATION
================================================================================
Database: translation
Mode: CHECK ONLY
Time: 2025-11-15T12:05:00

================================================================================
REFERENTIAL INTEGRITY CHECK
================================================================================
📊 Total companies: 5
📊 Total subscriptions: 8

✅ Referential integrity check PASSED
   All subscriptions reference existing companies

================================================================================
SCHEMA VALIDATION CHECK
================================================================================
📋 Checking 'companies' collection validation...
✅ Schema validation enabled for 'companies'

📋 Checking 'subscriptions' collection validation...
✅ Schema validation enabled for 'subscriptions'

================================================================================
INDEX VERIFICATION
================================================================================
📊 Checking 'companies' collection indexes...
✅ Index 'company_name_unique': properly configured

📊 Checking 'subscriptions' collection indexes...
✅ Index 'company_name_idx': properly configured

================================================================================
VERIFICATION SUMMARY
================================================================================
Total companies: 5
Total subscriptions: 8
Missing companies: 0
Orphaned subscriptions: 0
Validation errors: 0

✅ ALL CHECKS PASSED
   Data integrity is valid
```

## MongoDB Limitations & Workarounds

### Limitation 1: No Foreign Keys

**Problem:** MongoDB doesn't support traditional foreign key constraints

**Workaround:**
- JSON Schema validation for required fields
- Application-level existence checks
- Verification scripts for continuous monitoring

### Limitation 2: No Cascading Deletes

**Problem:** Deleting a company doesn't automatically delete its subscriptions

**Workaround:**
```python
async def delete_company(company_name: str):
    # 1. Check for subscriptions
    subscription_count = await db.subscriptions.count_documents({"company_name": company_name})

    if subscription_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete company with {subscription_count} active subscriptions"
        )

    # 2. Delete company
    await db.companies.delete_one({"company_name": company_name})
```

### Limitation 3: No Cross-Collection Validation

**Problem:** JSON Schema cannot validate across collections

**Workaround:**
- Pre-insert/update checks in application code
- Periodic verification scripts
- Monitoring alerts for orphaned records

### Limitation 4: No Triggers (in Community Edition)

**Problem:** MongoDB Community Edition doesn't support database triggers

**Alternatives:**
1. **Change Streams:** Monitor collection changes and react
2. **Application-Level Hooks:** Implement in service layer
3. **Scheduled Jobs:** Run verification scripts periodically

## Error Handling

### Schema Validation Errors

When validation fails, MongoDB returns descriptive errors:

```python
# Example: Missing required field
{
  "error": "Document failed validation",
  "details": {
    "operatorName": "$jsonSchema",
    "schemaRulesNotSatisfied": [
      {
        "operatorName": "required",
        "specifiedAs": { "required": ["company_name", ...] },
        "missingProperties": ["company_name"]
      }
    ]
  }
}
```

**Application Error Handling:**

```python
from pymongo.errors import WriteError

async def create_subscription(data: SubscriptionCreate):
    try:
        result = await db.subscriptions.insert_one(data.dict())
        return result
    except WriteError as e:
        if "Document failed validation" in str(e):
            raise HTTPException(
                status_code=400,
                detail=f"Validation error: {e.details}"
            )
        raise
```

### Duplicate Company Names

```python
from pymongo.errors import DuplicateKeyError

async def create_company(data: CompanyCreate):
    try:
        result = await db.companies.insert_one(data.dict())
        return result
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail=f"Company '{data.company_name}' already exists"
        )
```

## Performance Considerations

### Index Impact

**Query Performance:**
- Lookups by company_name: **O(log n)** with index vs **O(n)** without
- Range queries on dates: **O(log n + k)** where k = results
- Compound index queries: **Covered queries** (no collection scan)

**Write Performance:**
- Index maintenance adds ~5-10% overhead on inserts
- Unique constraint checks require index lookup
- Acceptable trade-off for data integrity

**Benchmarks:**

```bash
# Without indexes
db.subscriptions.find({company_name: "Tech Corp"}).explain("executionStats")
# executionTimeMillis: 45ms, totalDocsExamined: 10000

# With index
db.subscriptions.find({company_name: "Tech Corp"}).explain("executionStats")
# executionTimeMillis: 2ms, totalDocsExamined: 5
```

### Schema Validation Overhead

- Validation adds **1-3ms per write operation**
- Minimal impact on read operations (validation only on writes)
- Caching of validation schemas reduces overhead

## Testing Strategy

### 1. Unit Tests

Test individual validation rules:

```python
async def test_subscription_requires_company_name():
    """Schema validation rejects subscription without company_name"""
    with pytest.raises(WriteError) as exc_info:
        await db.subscriptions.insert_one({
            "subscription_unit": "page",
            "units_per_subscription": 1000,
            # Missing company_name
        })

    assert "required" in str(exc_info.value).lower()
```

### 2. Integration Tests

Test referential integrity:

```python
async def test_cannot_create_subscription_for_nonexistent_company():
    """Application prevents subscription for non-existent company"""
    response = await client.post("/subscriptions", json={
        "company_name": "NonExistent Corp",
        "subscription_unit": "page",
        "units_per_subscription": 1000,
        # ...
    })

    assert response.status_code == 404
    assert "Company 'NonExistent Corp' not found" in response.json()["detail"]
```

### 3. Verification Tests

Test monitoring scripts:

```python
async def test_verify_data_integrity_detects_orphans():
    """Verification script detects orphaned subscriptions"""
    # Create orphaned subscription directly in DB (bypass validation)
    await db.subscriptions.insert_one({
        "company_name": "Missing Company",
        # ... valid fields
    }, bypass_document_validation=True)

    # Run verification
    verifier = DataIntegrityVerifier(database_name="translation_test")
    await verifier.connect()
    passed, report = await verifier.run_verification()
    await verifier.disconnect()

    assert not passed
    assert report["summary"]["missing_companies"] == 1
```

## Maintenance & Monitoring

### Daily Health Checks

```bash
#!/bin/bash
# scripts/daily_integrity_check.sh

python scripts/verify_data_integrity.py --export /var/log/integrity_$(date +%Y%m%d).json

if [ $? -ne 0 ]; then
    # Send alert (email, Slack, PagerDuty)
    echo "Data integrity issues detected!" | mail -s "DB Integrity Alert" ops@example.com
fi
```

### Monitoring Dashboard

**Key Metrics:**
- Total companies vs unique companies in subscriptions
- Orphaned subscriptions count (should be 0)
- Schema validation error rate
- Index hit rate

**CloudWatch/DataDog Example:**

```python
# Add to application monitoring
cloudwatch.put_metric_data(
    Namespace="TranslationService",
    MetricData=[
        {
            "MetricName": "OrphanedSubscriptions",
            "Value": orphan_count,
            "Unit": "Count"
        }
    ]
)
```

### Alerting Rules

1. **Critical:** Orphaned subscriptions detected (immediate alert)
2. **Warning:** Schema validation failure rate > 1% (1-hour alert)
3. **Info:** Index configuration mismatch (daily digest)

## Migration Checklist

Before deploying to production:

- [ ] Run migration script in dry-run mode on production snapshot
- [ ] Review migration output for potential issues
- [ ] Test rollback procedure (disable validation, restore indexes)
- [ ] Schedule maintenance window (minimal downtime, but schema changes require lock)
- [ ] Run migration on production
- [ ] Verify with verification script
- [ ] Monitor application logs for validation errors
- [ ] Set up automated integrity checks (cron/scheduled Lambda)

## Rollback Procedure

If issues arise:

```javascript
// 1. Disable schema validation
db.runCommand({
  collMod: "subscriptions",
  validator: {},
  validationLevel: "off"
})

// 2. Drop problematic indexes
db.subscriptions.dropIndex("company_name_idx")

// 3. Restore original state
// (Keep backups of original index configurations)
```

## Future Enhancements

### 1. Change Streams for Real-Time Validation

```python
async def watch_company_deletes():
    """Prevent company deletion if subscriptions exist"""
    async with db.companies.watch([
        {"$match": {"operationType": "delete"}}
    ]) as stream:
        async for change in stream:
            company_name = change["documentKey"]["company_name"]
            # Check and prevent if subscriptions exist
```

### 2. Automated Cleanup Jobs

```python
async def cleanup_expired_subscriptions():
    """Archive or delete expired subscriptions"""
    # Run monthly to clean old data
    cutoff_date = datetime.utcnow() - timedelta(days=365)

    await db.subscriptions.update_many(
        {"end_date": {"$lt": cutoff_date}, "status": "expired"},
        {"$set": {"archived": True}}
    )
```

### 3. Multi-Collection Transactions

```python
async def delete_company_with_subscriptions(company_name: str):
    """Atomic delete with cascading"""
    async with await client.start_session() as session:
        async with session.start_transaction():
            # Delete subscriptions
            await db.subscriptions.delete_many(
                {"company_name": company_name},
                session=session
            )

            # Delete company
            await db.companies.delete_one(
                {"company_name": company_name},
                session=session
            )
```

## References

- [MongoDB Schema Validation](https://www.mongodb.com/docs/manual/core/schema-validation/)
- [MongoDB Indexes](https://www.mongodb.com/docs/manual/indexes/)
- [MongoDB Change Streams](https://www.mongodb.com/docs/manual/changeStreams/)
- [JSON Schema Specification](https://json-schema.org/)

## Support

For issues or questions:
1. Check verification script output: `python scripts/verify_data_integrity.py --verbose`
2. Review application logs for validation errors
3. Run migration in dry-run mode: `python scripts/add_referential_integrity.py --dry-run`
4. Contact: database-admin@example.com
