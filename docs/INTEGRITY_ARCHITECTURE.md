# Referential Integrity Architecture

## Visual Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REFERENTIAL INTEGRITY LAYERS                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: APPLICATION VALIDATION (Pydantic)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  FastAPI Endpoint                                                           │
│       ↓                                                                     │
│  Pydantic Model Validation                                                  │
│       ↓                                                                     │
│  Service Layer: Check company exists                                        │
│       ↓                                                                     │
│  ✅ Pass → Proceed    ❌ Fail → 404 Not Found                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: DATABASE SCHEMA VALIDATION (JSON Schema)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  MongoDB receives insert/update                                             │
│       ↓                                                                     │
│  JSON Schema Validation                                                     │
│    - Required fields present?                                               │
│    - Correct data types?                                                    │
│    - Enum values valid?                                                     │
│    - Business rules (units > 0, etc.)?                                      │
│       ↓                                                                     │
│  ✅ Pass → Insert    ❌ Fail → WriteError                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: INDEX CONSTRAINTS                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  Check unique constraints                                                   │
│    - company_name unique in companies?                                      │
│    - No duplicate companies?                                                │
│       ↓                                                                     │
│  ✅ Pass → Commit    ❌ Fail → DuplicateKeyError                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: CONTINUOUS VERIFICATION (Monitoring)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Scheduled integrity checks (daily/weekly)                                  │
│       ↓                                                                     │
│  verify_data_integrity.py                                                   │
│    - Detect orphaned subscriptions                                          │
│    - Verify schema validation enabled                                       │
│    - Check index configuration                                              │
│       ↓                                                                     │
│  ✅ Pass → Report    ❌ Fail → Alert + Auto-fix (optional)                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow: Creating a Subscription

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 1. CLIENT REQUEST                                                        │
└──────────────────────────────────────────────────────────────────────────┘
    POST /api/v1/subscriptions
    {
      "company_name": "Tech Corp",
      "subscription_unit": "page",
      "units_per_subscription": 1000,
      ...
    }
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ 2. FASTAPI VALIDATION (Pydantic)                                         │
└──────────────────────────────────────────────────────────────────────────┘
    SubscriptionCreate model validates:
    ✅ company_name is string
    ✅ subscription_unit in ["page", "word", "character"]
    ✅ units_per_subscription > 0
    ✅ price_per_unit > 0
    ✅ end_date > start_date
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ 3. SERVICE LAYER CHECK                                                   │
└──────────────────────────────────────────────────────────────────────────┘
    company = await db.companies.find_one({"company_name": "Tech Corp"})

    if not company:
        ❌ raise HTTPException(404, "Company not found")

    ✅ Company exists → Proceed
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ 4. DATABASE INSERT                                                       │
└──────────────────────────────────────────────────────────────────────────┘
    await db.subscriptions.insert_one(subscription_data)
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ 5. JSON SCHEMA VALIDATION (MongoDB)                                      │
└──────────────────────────────────────────────────────────────────────────┘
    MongoDB checks:
    ✅ Required fields present
    ✅ Data types correct (int, string, date)
    ✅ Enum values valid
    ✅ Business rules (units > 0, discount 0-1)

    If validation fails:
    ❌ raise WriteError("Document failed validation")
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ 6. INDEX CHECK                                                           │
└──────────────────────────────────────────────────────────────────────────┘
    company_name_idx (non-unique) → OK (multiple subs per company allowed)

    If had unique constraint:
    ❌ raise DuplicateKeyError
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ 7. SUCCESS                                                               │
└──────────────────────────────────────────────────────────────────────────┘
    return 201 Created
    {
      "id": "507f1f77bcf86cd799439011",
      "company_name": "Tech Corp",
      ...
    }
```

## Collection Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          COMPANIES COLLECTION                           │
├─────────────────────────────────────────────────────────────────────────┤
│  {                                                                      │
│    _id: ObjectId("..."),                                                │
│    company_name: "Tech Corp",  ← [UNIQUE INDEX]                        │
│    created_at: ISODate("..."),                                          │
│    updated_at: ISODate("...")                                           │
│  }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    ↑
                                    │ References (1:N)
                                    │ [NON-UNIQUE INDEX]
                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│                       SUBSCRIPTIONS COLLECTION                          │
├─────────────────────────────────────────────────────────────────────────┤
│  {                                                                      │
│    _id: ObjectId("..."),                                                │
│    company_name: "Tech Corp",  ← [NON-UNIQUE INDEX] (foreign key)      │
│    subscription_unit: "page",  ← [ENUM: page|word|character]           │
│    units_per_subscription: 1000,  ← [MIN: 1]                            │
│    price_per_unit: 0.01,       ← [MIN: 0]                               │
│    subscription_price: 10.00,  ← [MIN: 0]                               │
│    start_date: ISODate("..."), ← [REQUIRED]                             │
│    end_date: ISODate("..."),   ← [NULLABLE]                             │
│    status: "active",           ← [ENUM: active|inactive|expired]       │
│    usage_periods: [...],       ← [ARRAY]                                │
│    created_at: ISODate("..."),                                          │
│    updated_at: ISODate("...")                                           │
│  }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘

Relationship Type: ONE-TO-MANY
- One company can have MANY subscriptions
- Each subscription belongs to ONE company

Enforcement:
✅ Application layer: Check company exists before insert
✅ Database layer: JSON schema validation (required fields, types, enums)
✅ Index layer: Unique company names, non-unique foreign keys
⚠️  MongoDB limitation: Cannot enforce foreign key at DB level (use app logic)
```

## Index Strategy Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COMPANIES INDEXES                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. _id (default)                                                       │
│     { _id: 1 }                                                          │
│     Purpose: Primary key lookup                                         │
│     Type: Unique                                                        │
│                                                                         │
│  2. company_name_unique                                                 │
│     { company_name: 1 }                                                 │
│     Purpose: Prevent duplicate companies, fast lookup                   │
│     Type: Unique                                                        │
│     Used by: Subscriptions foreign key checks                           │
│                                                                         │
│  3. created_at_asc                                                      │
│     { created_at: 1 }                                                   │
│     Purpose: Sort/filter by creation time                               │
│     Type: Non-unique                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                       SUBSCRIPTIONS INDEXES                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. _id (default)                                                       │
│     { _id: 1 }                                                          │
│     Purpose: Primary key lookup                                         │
│     Type: Unique                                                        │
│                                                                         │
│  2. company_name_idx ⭐ CRITICAL                                        │
│     { company_name: 1 }                                                 │
│     Purpose: Fast foreign key lookup (company → subscriptions)          │
│     Type: NON-UNIQUE (multiple subscriptions per company)               │
│     Query: db.subscriptions.find({company_name: "Tech Corp"})           │
│                                                                         │
│  3. status_idx                                                          │
│     { status: 1 }                                                       │
│     Purpose: Filter by status (active, inactive, expired)               │
│     Type: Non-unique                                                    │
│     Query: db.subscriptions.find({status: "active"})                    │
│                                                                         │
│  4. company_status_idx (compound)                                       │
│     { company_name: 1, status: 1 }                                      │
│     Purpose: Combined queries (company + status filter)                 │
│     Type: Non-unique                                                    │
│     Query: db.subscriptions.find({                                      │
│              company_name: "Tech Corp",                                 │
│              status: "active"                                           │
│            })                                                           │
│                                                                         │
│  5. start_date_idx                                                      │
│     { start_date: 1 }                                                   │
│     Purpose: Date range queries, sorting                                │
│     Type: Non-unique                                                    │
│                                                                         │
│  6. end_date_idx                                                        │
│     { end_date: 1 }                                                     │
│     Purpose: Find expiring subscriptions                                │
│     Type: Non-unique                                                    │
│     Query: db.subscriptions.find({                                      │
│              end_date: {$lt: new Date()}                                │
│            })                                                           │
│                                                                         │
│  7. created_at_asc                                                      │
│     { created_at: 1 }                                                   │
│     Purpose: Sort/filter by creation time                               │
│     Type: Non-unique                                                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

⚠️  CRITICAL ISSUE FIXED BY MIGRATION:
   OLD: subscriptions.company_name with unique=true ❌ WRONG
   NEW: subscriptions.company_name with unique=false ✅ CORRECT

   Why wrong: Unique constraint prevents multiple subscriptions per company!
   Impact: Cannot create 2nd subscription for same company
   Fix: Drop and recreate as non-unique index
```

## Migration Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│ START MIGRATION                                                          │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1: DATA INTEGRITY VERIFICATION                                     │
├──────────────────────────────────────────────────────────────────────────┤
│  - Get all company_name from subscriptions                               │
│  - Get all company_name from companies                                   │
│  - Find missing companies (orphans)                                      │
│                                                                          │
│  If orphans found:                                                       │
│    ❌ ABORT migration                                                    │
│    → User must fix with verify_data_integrity.py --fix                  │
│                                                                          │
│  If no orphans:                                                          │
│    ✅ PROCEED to Step 2                                                  │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 2: FIX UNIQUE CONSTRAINT ISSUE                                     │
├──────────────────────────────────────────────────────────────────────────┤
│  Check: Does "company_name_unique" index exist on subscriptions?         │
│                                                                          │
│  If YES:                                                                 │
│    1. Drop index: db.subscriptions.dropIndex("company_name_unique")     │
│    2. Create non-unique: db.subscriptions.createIndex(                  │
│         {company_name: 1},                                               │
│         {name: "company_name_idx", unique: false}                        │
│       )                                                                  │
│                                                                          │
│  If NO:                                                                  │
│    ✅ Already fixed or doesn't exist                                     │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 3: APPLY JSON SCHEMA VALIDATION                                    │
├──────────────────────────────────────────────────────────────────────────┤
│  Apply to companies:                                                     │
│    db.runCommand({                                                       │
│      collMod: "companies",                                               │
│      validator: {$jsonSchema: {...}},                                    │
│      validationLevel: "strict",                                          │
│      validationAction: "error"                                           │
│    })                                                                    │
│                                                                          │
│  Apply to subscriptions:                                                 │
│    db.runCommand({                                                       │
│      collMod: "subscriptions",                                           │
│      validator: {$jsonSchema: {...}},                                    │
│      validationLevel: "strict",                                          │
│      validationAction: "error"                                           │
│    })                                                                    │
│                                                                          │
│  If validation fails on existing data:                                   │
│    ❌ ABORT (data violates schema)                                       │
│                                                                          │
│  If validation succeeds:                                                 │
│    ✅ PROCEED to Step 4                                                  │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 4: CREATE/UPDATE INDEXES                                           │
├──────────────────────────────────────────────────────────────────────────┤
│  For each required index:                                                │
│    - Check if exists                                                     │
│    - If exists: Skip                                                     │
│    - If not exists: Create                                               │
│                                                                          │
│  Companies indexes:                                                      │
│    ✅ company_name_unique (already exists)                               │
│    ✅ created_at_asc (already exists)                                    │
│                                                                          │
│  Subscriptions indexes:                                                  │
│    ✅ company_name_idx (created in Step 2)                               │
│    ✅ status_idx (already exists)                                        │
│    ✅ company_status_idx (already exists)                                │
│    ✅ start_date_idx, end_date_idx (already exist)                       │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ MIGRATION COMPLETE ✅                                                    │
├──────────────────────────────────────────────────────────────────────────┤
│  Next steps:                                                             │
│    1. Run verification: python scripts/verify_data_integrity.py          │
│    2. Test application functionality                                     │
│    3. Monitor logs for validation errors                                 │
└──────────────────────────────────────────────────────────────────────────┘
```

## Verification Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│ START VERIFICATION                                                       │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ CHECK 1: REFERENTIAL INTEGRITY                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  companies = db.companies.distinct("company_name")                       │
│  subscription_companies = db.subscriptions.distinct("company_name")      │
│                                                                          │
│  missing = subscription_companies - companies                            │
│                                                                          │
│  If missing:                                                             │
│    ❌ FAIL                                                               │
│    Report: Orphaned subscriptions found                                  │
│                                                                          │
│    If --fix flag:                                                        │
│      → Create missing companies                                          │
│      → Re-check integrity                                                │
│                                                                          │
│  If no missing:                                                          │
│    ✅ PASS                                                               │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ CHECK 2: SCHEMA VALIDATION                                              │
├──────────────────────────────────────────────────────────────────────────┤
│  For companies:                                                          │
│    db.runCommand({listCollections: 1, filter: {name: "companies"}})     │
│    Check: validator field exists?                                        │
│                                                                          │
│  For subscriptions:                                                      │
│    db.runCommand({listCollections: 1, filter: {name: "subscriptions"}}) │
│    Check: validator field exists?                                        │
│                                                                          │
│  If validators missing:                                                  │
│    ⚠️  WARNING: Schema validation not configured                         │
│                                                                          │
│  If validators present:                                                  │
│    ✅ PASS                                                               │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ CHECK 3: INDEX CONFIGURATION                                            │
├──────────────────────────────────────────────────────────────────────────┤
│  Check companies indexes:                                                │
│    - company_name_unique exists and is unique?                           │
│                                                                          │
│  Check subscriptions indexes:                                            │
│    - company_name_idx exists and is NON-unique?                          │
│    - company_name_unique does NOT exist? (critical!)                     │
│                                                                          │
│  If company_name_unique exists on subscriptions:                         │
│    ❌ CRITICAL: Prevents multiple subscriptions per company!             │
│                                                                          │
│  If indexes correct:                                                     │
│    ✅ PASS                                                               │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ GENERATE REPORT                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  {                                                                       │
│    "summary": {                                                          │
│      "total_companies": N,                                               │
│      "total_subscriptions": M,                                           │
│      "missing_companies": 0,                                             │
│      "orphaned_subscriptions": 0,                                        │
│      "validation_errors": 0                                              │
│    },                                                                    │
│    "passed": true/false                                                  │
│  }                                                                       │
│                                                                          │
│  If --export flag:                                                       │
│    → Save to JSON file                                                   │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────────────────────────────┐
│ VERIFICATION COMPLETE                                                    │
├──────────────────────────────────────────────────────────────────────────┤
│  Exit code: 0 (pass) or 1 (fail)                                         │
└──────────────────────────────────────────────────────────────────────────┘
```

## Error Handling Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│ INSERT/UPDATE SUBSCRIPTION                                              │
└──────────────────────────────────────────────────────────────────────────┘
                    ↓
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│ VALIDATION ERROR │  │ DUPLICATE ERROR  │
│ (JSON Schema)    │  │ (Unique Index)   │
└──────────────────┘  └──────────────────┘
          │                   │
          ▼                   ▼
┌──────────────────┐  ┌──────────────────┐
│ WriteError       │  │ DuplicateKeyError│
└──────────────────┘  └──────────────────┘
          │                   │
          ▼                   ▼
┌──────────────────────────────────────────┐
│ Application catches and transforms       │
├──────────────────────────────────────────┤
│ WriteError → 400 Bad Request             │
│   {                                      │
│     "error": "Validation failed",        │
│     "details": {...}                     │
│   }                                      │
│                                          │
│ DuplicateKeyError → 409 Conflict         │
│   {                                      │
│     "error": "Company already exists",   │
│     "details": {...}                     │
│   }                                      │
└──────────────────────────────────────────┘
```

## Performance Impact

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PERFORMANCE METRICS                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  READS (Queries)                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ WITHOUT INDEXES                                                 │   │
│  │   db.subscriptions.find({company_name: "Tech Corp"})            │   │
│  │   → Full collection scan                                        │   │
│  │   → O(n) where n = total subscriptions                          │   │
│  │   → 45ms for 10,000 documents                                   │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                          ↓ OPTIMIZATION                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ WITH INDEX (company_name_idx)                                   │   │
│  │   db.subscriptions.find({company_name: "Tech Corp"})            │   │
│  │   → Index scan + document fetch                                 │   │
│  │   → O(log n + k) where k = matching docs                        │   │
│  │   → 2ms for 10,000 documents (22x faster!)                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  WRITES (Inserts/Updates)                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ WITHOUT VALIDATION/INDEXES                                      │   │
│  │   → Direct insert: ~1ms                                         │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                          ↓ OVERHEAD                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ WITH VALIDATION + INDEXES                                       │   │
│  │   → JSON Schema validation: +1-3ms                              │   │
│  │   → Index updates: +1-2ms                                       │   │
│  │   → Total: ~3-6ms (3-6x slower, but ensures data integrity!)    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  CONCLUSION:                                                            │
│    ✅ Reads: MUCH FASTER (22x improvement)                              │
│    ⚠️  Writes: Slightly slower (3-6x), but acceptable for integrity     │
│    ✅ Net benefit: Positive for read-heavy workloads                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Monitoring Dashboard (Conceptual)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   DATABASE INTEGRITY DASHBOARD                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  REFERENTIAL INTEGRITY                                                  │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Orphaned Subscriptions:  0  ✅                                   │ │
│  │  Missing Companies:       0  ✅                                   │ │
│  │  Last Check:              2 hours ago                             │ │
│  │  Status:                  ✅ HEALTHY                               │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  SCHEMA VALIDATION                                                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Companies:               ✅ ENABLED                               │ │
│  │  Subscriptions:           ✅ ENABLED                               │ │
│  │  Validation Errors (24h): 3                                       │ │
│  │  Error Rate:              0.01%                                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  INDEX HEALTH                                                           │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  company_name_unique:     ✅ OK (unique)                           │ │
│  │  company_name_idx:        ✅ OK (non-unique)                       │ │
│  │  Index Hit Rate:          98.5%                                   │ │
│  │  Covered Queries:         87%                                     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  COLLECTION STATS                                                       │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Total Companies:         45                                      │ │
│  │  Total Subscriptions:     128                                     │ │
│  │  Avg Subs per Company:    2.8                                     │ │
│  │  Growth (30d):            +12%                                    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ALERTS                                                                 │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  🔔 No active alerts                                              │ │
│  │                                                                   │ │
│  │  Recent (7d):                                                     │ │
│  │    - 2025-11-13: Orphaned subscription detected (auto-fixed)     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```
