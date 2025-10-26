# MongoDB Collection Analysis - Index & Summary

**Generated:** 2025-10-21
**Location:** `/Users/vladimirdanishevsky/projects/Translator/server/`

---

## Quick Navigation

This analysis contains **THREE comprehensive documents** documenting all MongoDB collection usage in the translation service backend.

### 1. COLLECTION_USAGE_ANALYSIS.md (21 KB) - MAIN REPORT
**Read this first for complete understanding**

**Contents:**
- Executive summary of user collections
- Detailed collection schemas (users, company_users, users_login)
- Purpose and differences between collections
- API endpoints and routing matrix
- User flow diagrams
- Data flow between collections
- Pydantic model definitions
- Code locations for all operations
- **5 Critical issues identified** with impact assessment
- Recommendations (Priority 1-4)

**Key Findings:**
- `users` collection: Primary multi-purpose (individual + enterprise)
- `company_users` collection: Legacy fallback (enterprise only)
- `users_login` collection: Simple auth (isolated, no company integration)
- Recommendation: Consolidate to single `users` collection

---

### 2. COLLECTION_USAGE_MAP.md (14 KB) - OPERATIONAL REFERENCE
**Use this for understanding specific operations**

**Contents:**
- CREATE operations per collection
- READ operations per collection
- UPDATE operations per collection
- DELETE operations per collection
- Collection access patterns matrix
- Critical code paths with flowcharts
- Transaction consistency notes
- Index usage patterns
- Performance implications

**Key Sections:**
- `users` collection: 6 operations (create, read x5, update x3)
- `company_users` collection: 2 operations (read x1, update x1)
- `users_login` collection: 3 operations (create, read x2, update x1)
- Critical Path 1: Corporate login with dual collection lookup
- Critical Path 2: Individual login (OAuth)
- Critical Path 3: Simple user signup

---

### 3. COLLECTION_CODE_REFERENCES.md (16 KB) - CODE LOCATION GUIDE
**Use this to find exact code implementing operations**

**Contents:**
- Complete file locations index
- Database configuration references
- Authentication service line numbers
- Authentication routes line numbers
- Model definitions with line numbers
- Setup and migration scripts
- Query patterns by operation type
- Error handling and validation
- Logging and debugging points
- Indexes and performance details
- Schema validation details
- Testing and verification instructions
- Key constants and configuration

**Quick Lookup:**
- Find any operation by file and line number
- See exact query syntax used
- View error handling for each path
- Locate test data creation scripts

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                   AUTHENTICATION FLOWS                            │
└──────────────────────────────────────────────────────────────────┘

┌─────────────────────────────┐
│  Corporate User             │
│  (company + password)       │
│  POST /login/corporate      │
└────────────┬────────────────┘
             │
    ┌────────v────────┐
    │ Lookup company  │
    │ db.company      │
    └────────┬────────┘
             │
    ┌────────v──────────────────────────────────┐
    │ Find user (PRIMARY PATH)                  │
    │ db.users                                  │
    │ Query: email+company_id+user_name         │
    └────────┬──────────────────────────────────┘
             │
        NOT FOUND?
             │
    ┌────────v──────────────────────────────────┐
    │ Find user (FALLBACK PATH - LEGACY)        │
    │ db.company_users                          │
    │ Query: email+company_id+user_name         │
    └────────┬──────────────────────────────────┘
             │
    ┌────────v────────┐
    │ Verify password │
    │ bcrypt check    │
    └────────┬────────┘
             │
    ┌────────v──────────────────┐
    │ Create JWT token (8 hrs)  │
    │ Update last_login         │
    └────────┬──────────────────┘
             │
          SUCCESS
          (return token)


┌─────────────────────────────┐
│  Individual User            │
│  (OAuth, no company)        │
│  POST /login/individual     │
└────────┬────────────────────┘
         │
  ┌──────v────────────────────┐
  │ Find or CREATE user       │
  │ db.users                  │
  │ Query: email+company_id   │
  │ company_id = NULL         │
  └──────┬────────────────────┘
         │
  ┌──────v──────────────────────┐
  │ Create JWT token (8 hrs)   │
  │ (NO password needed)        │
  └──────┬──────────────────────┘
         │
      SUCCESS
      (return token)


┌─────────────────────────────┐
│  Simple User                │
│  (username/email/password)  │
│  POST /login/api/auth/...   │
└────────┬────────────────────┘
         │
  ┌──────v──────────────────────┐
  │ Check uniqueness            │
  │ db.users_login              │
  │ Query: user_email           │
  │ Query: user_name            │
  └──────┬──────────────────────┘
         │
  ┌──────v──────────────────────┐
  │ Hash password (bcrypt 12)  │
  │ OR verify password          │
  └──────┬──────────────────────┘
         │
  ┌──────v──────────────────────┐
  │ Insert or update            │
  │ db.users_login              │
  │ Generate session token      │
  └──────┬──────────────────────┘
         │
      SUCCESS
      (return token)
```

---

## Collection Schema Overview

### users (Primary Multi-Purpose)
```
Purpose: Individual users (company_id=null) + Enterprise users (company_id=ObjectId)
Fields:  user_id, user_name, email, company_id, permission_level, status,
         password_hash, last_login, created_at, updated_at
Indexes: 6 (including email_company compound index)
Usage:   Primary lookup in all auth flows
```

### company_users (Legacy Fallback)
```
Purpose: Enterprise users only (DEPRECATED - fallback only)
Fields:  user_id, customer_id, user_name, email, phone_number, permission_level,
         status, password_hash, last_login, created_at, updated_at
Indexes: 4 (including customer_id+email unique compound)
Usage:   Fallback if user not found in 'users' collection
Issue:   Field name inconsistency (customer_id vs company_id)
```

### users_login (Simple Authentication)
```
Purpose: Simple auth (no company integration, isolated)
Fields:  user_name, user_email, password, created_at, updated_at, last_login
Indexes: 3 (user_email unique, user_name unique)
Usage:   Separate signup/login endpoints (/api/auth/signup, /api/auth/login)
Note:    Completely independent from corporate auth flows
```

---

## Critical Issues Found

### Issue 1: Data Duplication Risk (HIGH)
**Problem:** Same user could exist in both `users` and `company_users`
**Impact:** Data inconsistency, incorrect auth results
**Location:** app/services/auth_service.py:85-101
**Solution:** Migrate all data to `users`, remove fallback

### Issue 2: Field Name Inconsistency (MEDIUM)
**Problem:** `users` uses `company_id`, `company_users` uses `customer_id`
**Impact:** Schema confusion, seed data mismatch
**Location:** Multiple (setup_db.py, seed_data.py, auth_service.py)
**Solution:** Standardize on `company_id` everywhere

### Issue 3: Collection Redundancy (MEDIUM)
**Problem:** Three user collections with overlapping purposes
**Impact:** Maintenance burden, testing complexity
**Location:** mongodb.py, seed_data.py, auth.py
**Solution:** Consolidate to single `users` collection

### Issue 4: Mixed Auth Patterns (LOW)
**Problem:** JWT for corporate/individual, session tokens for simple users
**Impact:** Inconsistent auth mechanism
**Location:** auth_service.py vs auth.py
**Solution:** Standardize on JWT for all flows

### Issue 5: Sessions Collection Disabled (LOW)
**Problem:** Sessions collection creation commented out
**Impact:** Cannot track active sessions, logout ineffective
**Location:** app/database/mongodb.py:139-149
**Solution:** Re-enable or fully implement JWT validation

---

## API Endpoint Summary

| Endpoint | Collection | User Type | Auth Type | Status |
|----------|-----------|-----------|-----------|--------|
| POST /login/corporate | users + company_users | Enterprise | JWT | Working |
| POST /login/individual | users | Individual | JWT | Working |
| POST /login/logout | N/A (stateless JWT) | Both | JWT | Working |
| GET /login/verify | N/A (JWT decoded) | Both | JWT | Working |
| POST /login/api/auth/signup | users_login | Simple | Session | Working |
| POST /login/api/auth/login | users_login | Simple | Session | Working |

---

## Statistics

### Code Coverage
- **Total Python Files Analyzed:** 50+
- **Authentication Service:** 510 lines
- **Authentication Routes:** 704 lines
- **Database Configuration:** 251 lines
- **MongoDB Models:** 315 lines
- **Setup Scripts:** 450+ lines

### Collections & Indexes
- **Collections in Use:** 7 (company, users, company_users, users_login, subscriptions, translation_transactions, sessions)
- **Total Indexes:** 25+
- **Unique Constraints:** 8
- **Compound Indexes:** 5

### Operations by Collection
- `users`: 8 distinct operation sets
- `company_users`: 2 distinct operation sets
- `users_login`: 4 distinct operation sets
- `companies`: 2 distinct operation sets (lookup only)

---

## How to Use This Analysis

### For Understanding Architecture
1. Start with COLLECTION_USAGE_ANALYSIS.md
2. Read "User Flow Diagram" section
3. Review "API Endpoints & Collection Routing" table

### For Implementation Work
1. Refer to COLLECTION_USAGE_MAP.md
2. Find operation type (create/read/update)
3. See exact code pattern used
4. Check indexes section for query optimization

### For Debugging Issues
1. Check COLLECTION_CODE_REFERENCES.md
2. Find exact file and line number
3. Review error handling section
4. Check logging/debugging points

### For Making Changes
1. Identify affected operations in COLLECTION_USAGE_MAP.md
2. Update all locations listed in COLLECTION_CODE_REFERENCES.md
3. Review Critical Issues section for safety considerations
4. Update tests in scripts/utils/

---

## File Locations

### Analysis Documents (this analysis)
- `/Users/vladimirdanishevsky/projects/Translator/server/COLLECTION_USAGE_ANALYSIS.md` (Main report)
- `/Users/vladimirdanishevsky/projects/Translator/server/COLLECTION_USAGE_MAP.md` (Operational reference)
- `/Users/vladimirdanishevsky/projects/Translator/server/COLLECTION_CODE_REFERENCES.md` (Code locations)
- `/Users/vladimirdanishevsky/projects/Translator/server/MONGODB_COLLECTION_INDEX.md` (This file)

### Source Code Locations
```
app/
├── database/mongodb.py              # Collection definitions & indexes
├── services/auth_service.py         # Authentication logic
├── routers/auth.py                  # API endpoints
├── models/auth_models.py            # Request/response models
├── mongodb_models.py                # Pydantic models
└── models/subscription.py           # Subscription models

scripts/
├── setup/
│   ├── setup_db.py                 # Schema validation
│   ├── seed_data.py                # Test data population
│   └── cleanup_db.py               # Database cleanup
└── utils/
    └── create_test_user.py         # Test user creation
```

---

## Recommended Reading Order

**For Complete Understanding:**
1. This file (MONGODB_COLLECTION_INDEX.md) - 5 min
2. COLLECTION_USAGE_ANALYSIS.md - 15 min
3. COLLECTION_USAGE_MAP.md - 15 min
4. COLLECTION_CODE_REFERENCES.md - Reference as needed

**For Quick Reference:**
1. Architecture diagram (above)
2. Collection Schema Overview (above)
3. API Endpoint Summary (above)
4. Use specific files as needed

---

## Ongoing Maintenance

### When Adding New User Type:
1. Check if fits in existing schema (company_id=null or company_id=ObjectId)
2. If new schema needed, update COLLECTION_USAGE_ANALYSIS.md
3. Add new endpoint to this index
4. Document query patterns in COLLECTION_USAGE_MAP.md
5. Add code references to COLLECTION_CODE_REFERENCES.md

### When Migrating Data:
1. Use scripts in scripts/setup/
2. Verify data integrity with create_test_user.py
3. Update both COLLECTION_USAGE_MAP.md and COLLECTION_CODE_REFERENCES.md
4. Run cleanup_db.py to remove old collections

### When Troubleshooting Issues:
1. Check COLLECTION_USAGE_MAP.md for data flow
2. Review logging points in COLLECTION_CODE_REFERENCES.md
3. Verify query patterns match expected behavior
4. Check Critical Issues section for known problems

---

## Questions Answered by This Analysis

**Q: Which collection stores individual users?**
A: `users` collection (with company_id=null)

**Q: Which collection stores corporate users?**
A: `users` collection (primary, with company_id=ObjectId) or `company_users` (legacy fallback)

**Q: Is data synchronized between collections?**
A: No, they operate independently. Use fallback logic to minimize inconsistency.

**Q: What happens if password verification fails?**
A: AuthenticationError raised, no changes to database

**Q: How long do JWT tokens last?**
A: 8 hours (defined in auth_service.py:29 as SESSION_EXPIRATION_HOURS)

**Q: Can individual and corporate users be the same person?**
A: Yes if they have different email addresses or company affiliations

**Q: Is the sessions collection in use?**
A: No, creation is commented out. JWT is stateless (no session lookup)

**Q: What's the field naming issue?**
A: `users` uses `company_id`, `company_users` uses `customer_id` (inconsistent)

**Q: Should I use company_users collection?**
A: No, use `users` collection. `company_users` is legacy fallback only.

**Q: How do I migrate from company_users to users?**
A: Not documented yet. Recommendation: Use scripts/setup/seed_data.py as pattern.

---

## Next Steps Recommended

1. **Immediate:** Review COLLECTION_USAGE_ANALYSIS.md "Critical Issues" section
2. **Short-term:** Plan migration from `company_users` → `users`
3. **Medium-term:** Consolidate auth flows (eliminate `users_login` or integrate)
4. **Long-term:** Implement proper session management with renewed JWT validation

---

**End of Index**

Generated: 2025-10-21
Version: 1.0
Scope: FastAPI backend, MongoDB collections, authentication flows
