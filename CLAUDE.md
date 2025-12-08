markdown# CLAUDE.md - FastAPI Backend

**Stack:** Python 3.11+, FastAPI 0.104+, Pydantic v2, Uvicorn, pytest-asyncio, httpx, MongoDB, Motor

## Structure
server/
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── core/                # config, security, deps
│   ├── api/v1/              # versioned routes
│   ├── services/            # business logic
│   ├── models/              # Pydantic schemas
│   ├── db/                  # MongoDB models, session, repos
│   └── middleware/          # logging, CORS, rate limiting
├── tests/                   # unit, integration, fixtures
│   ├── integration/         # API integration tests
│   ├── unit/                # Unit tests
│   └── conftest.py          # Shared fixtures
├── scripts/                 # Automation scripts
└── .env                     # Environment variables

**Quick Start:**
```bash
./scripts/setup.sh           # Complete environment setup
./scripts/test.sh all        # Run all tests with coverage
uvicorn app.main:app --reload --port 8000

# Debugging
# See ../.claude/DEBUGGING_SETUP.md for VS Code debugger configuration
# TL;DR: Open app/main.py, press F5
```

---

## ⚠️ CRITICAL RULES - ALWAYS FOLLOW

### **-2. ABSOLUTE TOP PRIORITY: NEVER START WEBSERVER WITHOUT EXPLICIT USER REQUEST**

**CRITICAL REQUIREMENT:**
- ❌ **NEVER** start uvicorn or any webserver automatically
- ❌ **NEVER** run webserver in background without explicit user request
- ❌ **NEVER** start server "for convenience" or "to run tests"
- ✅ **ALWAYS** wait for user to start their own server manually
- ✅ **ALWAYS** use the server instance started by the user
- ✅ **ALWAYS** assume server is already running at http://localhost:8000 when running tests

**Why This is Rule #-2 (Highest Priority):**
- User maintains full control over server lifecycle
- Prevents port conflicts and resource issues
- User can monitor server logs in their own terminal
- Allows user to debug server issues independently
- Respects user's development workflow preferences

**Red Flag - VIOLATION if:**
```bash
# ❌ NEVER DO THIS - Starting server automatically
uvicorn app.main:app --port 8000 &
DATABASE_MODE=test uvicorn app.main:app --reload --port 8000 &

# ❌ NEVER DO THIS - Background server processes
nohup uvicorn app.main:app > logs/server.log 2>&1 &
```

**Correct - ALWAYS DO THIS:**
```bash
# ✅ Wait for user to start server manually in their terminal
# ✅ User runs: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000

# ✅ Then run tests against the user's server
pytest tests/integration/test_subscriptions_billing_integration.py -v
```

**When Tests Fail Due to "Server Not Running":**
- ❌ **NEVER** automatically start the server
- ✅ **ALWAYS** inform user: "Server not running. Please start server with: DATABASE_MODE=test uvicorn app.main:app --reload --port 8000"
- ✅ **WAIT** for user to start server manually
- ✅ **ONLY THEN** proceed with running tests

**Enforcement:**
- If you start a webserver without explicit user request → CRITICAL VIOLATION
- If you run background uvicorn processes → CRITICAL VIOLATION
- If you bypass this rule "to be helpful" → CRITICAL VIOLATION

---

### **-1. TOP PRIORITY: NEVER MOCK OR BYPASS HTTP LAYER IN INTEGRATION TESTS**

**ABSOLUTE REQUIREMENT:**
- ❌ **NEVER** use direct function calls, service imports, or database operations in integration tests
- ❌ **NEVER** bypass the HTTP layer "for convenience" or "to avoid authentication"
- ❌ **NEVER** create tests that don't show HTTP logs in test output
- ✅ **ALWAYS** use `http_client.post()`, `http_client.get()`, etc. with real endpoints
- ✅ **ALWAYS** verify HTTP logs appear in test output (look for "HTTP Request: POST ...")

**Why This is Rule #-1 (Higher Priority than Rule #0):**
- Mocked tests hide critical bugs in HTTP layer, routing, middleware, serialization
- Direct database calls bypass authentication, validation, business logic
- Tests without HTTP logs are NOT integration tests - they are unit tests in disguise

**Red Flag - Test is WRONG if:**
```python
# ❌ NO HTTP LOGS in test output
# ❌ Direct service/database calls
from app.services.some_service import some_service
result = await some_service.do_something()  # WRONG - bypasses HTTP!

# ❌ Direct database operations
await test_db.collection.update_one(...)  # WRONG - bypasses API!
```

**Correct - Test is RIGHT if:**
```python
# ✅ HTTP LOGS appear in output: "HTTP Request: POST http://localhost:8000/api/endpoint"
# ✅ Real HTTP request
response = await http_client.post("/api/endpoint", json=data, headers=auth_headers)
assert response.status_code == 200

# ✅ Then verify database state
record = await test_db.collection.find_one(...)
```

**Enforcement:**
- If test output shows NO HTTP request logs → Test is INVALID
- If test imports services/functions → Test is INVALID
- If test passes but you can't see API calls → Test is INVALID

---

### **0. MANDATORY: Real Server + Real Database Testing (NO EXCEPTIONS)**

**ALL tests MUST run against:**
- ✅ **Real running webserver** (FastAPI uvicorn instance)
- ✅ **Real test database** (`translation_test`, NOT `translation` production DB)
- ✅ **Real HTTP requests** using `httpx.AsyncClient`

**NEVER:**
- ❌ NO mocking of server/database/internal services (unless EXPLICITLY approved by user)
- ❌ NO direct function imports for integration tests (use HTTP API endpoints)
- ❌ NO testing against production database

**Test Structure:**
```python
# ✅ CORRECT - Integration test with real server + real DB
import httpx
import pytest

@pytest.fixture
async def http_client():
    """Client for real running server at http://localhost:8000"""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        yield client

@pytest.mark.asyncio
async def test_translate_endpoint(http_client, test_db):
    # ACT: Real HTTP POST to running server
    response = await http_client.post(
        "/api/translate",
        json={"file": "...", "translation_mode": "default"}
    )

    # ASSERT: Verify HTTP response
    assert response.status_code == 200
    data = response.json()
    assert "pricing" in data

    # VERIFY: Check real test database
    transaction = await test_db.translation_transactions.find_one({...})
    assert transaction is not None
```

```python
# ❌ WRONG - Direct function import (NOT testing HTTP layer)
from app.pricing.pricing_calculator import calculate_individual_price
price = calculate_individual_price(5, "default", config)  # Bypasses API!
```

**Rationale:**
- Integration tests must verify the FULL stack: HTTP → routing → validation → business logic → database
- Direct function calls skip HTTP serialization, middleware, authentication, and routing
- Real server catches issues that unit tests miss (CORS, serialization, middleware bugs)

**Before Running Tests:**
```bash
# ⚠️ USER must start server manually in Terminal 1:
# (NEVER start server automatically - see Rule #-2)
DATABASE_MODE=test uvicorn app.main:app --port 8000

# ✅ THEN run tests in Terminal 2 (only after user starts server):
pytest tests/integration/ -v
```

**IMPORTANT:** If server is not running, **NEVER** start it automatically. Instead, inform the user to start the server manually as shown above.

---

### **1. MongoDB → JSON Serialization (JSONResponse)**

When returning MongoDB documents in `JSONResponse`, **ALWAYS** serialize:

```python
# ✅ ALWAYS use this helper or similar
def serialize_transaction_for_json(txn: dict) -> dict:
    # Convert ObjectId → string
    if "_id" in txn:
        txn["_id"] = str(txn["_id"])

    # Convert Decimal128 → float
    for key, value in list(txn.items()):
        if isinstance(value, Decimal128):
            txn[key] = float(value.to_decimal())

    # Convert datetime → ISO 8601 string
    datetime_fields = ["date", "created_at", "updated_at", "payment_date"]
    for field in datetime_fields:
        if field in txn and hasattr(txn[field], "isoformat"):
            txn[field] = txn[field].isoformat()

    # ⚠️ CRITICAL: Handle nested arrays with datetime fields
    if "documents" in txn and isinstance(txn["documents"], list):
        for doc in txn["documents"]:
            doc_datetime_fields = ["uploaded_at", "translated_at"]
            for field in doc_datetime_fields:
                if field in doc and doc[field] is not None and hasattr(doc[field], "isoformat"):
                    doc[field] = doc[field].isoformat()

    return txn
```

**Why:** `JSONResponse` does NOT auto-serialize Python objects. Missing datetime serialization in nested arrays causes:
```
TypeError: Object of type datetime is not JSON serializable
```

**Prevention:**
- ✅ Use Pydantic `response_model` when possible (auto-serializes)
- ✅ Create reusable serialization helpers
- ✅ Test datetime field types in integration tests (not just structure)

---

### **2. Variable Naming - Avoid Import Shadowing**

**NEVER** name function parameters with these reserved/import names:

```python
# ❌ WRONG - Shadows FastAPI status module
from fastapi import status

async def my_endpoint(
    status: Optional[str] = Query(None, ...)  # ❌ Shadows import!
):
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)  # CRASH!
```

```python
# ✅ CORRECT - Use descriptive name with alias
from fastapi import status

async def my_endpoint(
    status_filter: Optional[str] = Query(None, alias="status", ...)  # ✅ No shadowing
):
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)  # Works!
```

**Commonly Shadowed Names:**
- `status` (FastAPI status codes)
- `json` (json module)
- `date` / `datetime` (datetime module)
- `Path` / `Query` (FastAPI imports)
- `dict` / `list` / `str` (built-ins)

**Why:** Variable shadowing causes `AttributeError: 'str' object has no attribute 'HTTP_500_INTERNAL_SERVER_ERROR'`

**Prevention:**
- ✅ Use descriptive names: `status_filter`, `date_param`, `json_data`
- ✅ Use `alias="status"` in Query/Path for backward compatibility
- ✅ Enable linting to catch shadowing (pylint, ruff)

---

### **3. Test Coverage - Validate Field Types, Not Just Structure**

```python
# ❌ INSUFFICIENT - Only checks structure
assert "documents" in transaction
assert isinstance(transaction["documents"], list)

# ✅ COMPREHENSIVE - Validates serialization
assert "documents" in transaction
assert isinstance(transaction["documents"], list)
# Validate datetime fields are ISO strings, not datetime objects
doc = transaction["documents"][0]
assert isinstance(doc["uploaded_at"], str), "uploaded_at must be ISO string"
if doc["translated_at"] is not None:
    assert isinstance(doc["translated_at"], str), "translated_at must be ISO string"
# Validate ISO 8601 format
from datetime import datetime
datetime.fromisoformat(doc["uploaded_at"].replace("Z", "+00:00"))
```

**Why:** Structural tests pass even when serialization is broken. Tests must validate:
1. Field existence ✅
2. Field type (str vs datetime) ✅
3. Format validity (ISO 8601) ✅

---

### **4. Data Preservation - Test Scripts Must Be Safe**

```python
# ❌ DANGEROUS - Deletes ALL records
async def clear_user_transactions():
    collection = database.user_transactions
    result = await collection.delete_many({})  # Deletes everything!

# ✅ SAFE - Only deletes test records
async def clear_user_transactions():
    collection = database.user_transactions
    # Only delete test records with specific prefix
    result = await collection.delete_many({
        "square_transaction_id": {"$regex": "^TEST-"}
    })
    print(f"Deleted {result.deleted_count} TEST records")
```

**MANDATORY RULE:** Test scripts must NEVER delete production data from these collections:
- `user_transactions`
- `translation_transactions`
- `payments`
- `invoices`
- `subscriptions`
- `companies`
- `users`

**Prevention:**
- ✅ Always filter by test-specific identifiers (TEST- prefix, test email domains)
- ✅ Add database name check (must contain "test")
- ✅ Require confirmation flag: `--confirm-delete-production` (and never use it)
- ✅ Document in script: "ONLY DELETES TEST RECORDS"

---

### **5. Pydantic vs JSONResponse - Know When to Use Each**

| Scenario | Use | Auto-Serialization | Example |
|----------|-----|-------------------|---------|
| **Single model response** | `response_model=ModelClass` | ✅ Yes | POST /process returns UserTransactionResponse |
| **List of models** | `response_model=List[ModelClass]` | ✅ Yes | GET /transactions returns List[Transaction] |
| **Custom structure** | `JSONResponse(content={...})` | ❌ No - Manual required | Custom paginated responses |
| **Raw dict from MongoDB** | `JSONResponse` + serialization helper | ❌ No - Manual required | Complex aggregations |

**Best Practice:**
1. **Prefer Pydantic `response_model`** for consistency and auto-serialization
2. If using `JSONResponse`, always create/use serialization helper
3. Test both structure AND field types

---

### **6. DateTime Handling - Use Timezone-Aware UTC**

```python
# ❌ DEPRECATED (Python 3.12+ will remove in 3.14)
from datetime import datetime
timestamp = datetime.utcnow()  # No timezone info

# ✅ CORRECT - Timezone-aware UTC
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc)  # Has timezone info
```

**Why:**
- `datetime.utcnow()` is deprecated since Python 3.12
- Timezone-naive datetimes cause ambiguity
- MongoDB stores UTC timestamps with timezone info

---

### **7. MongoDB Unique Indexes - Use Sparse for Nullable Fields**

**Problem:** Unique indexes on nullable fields only allow ONE document with `null` value.

```python
# ❌ WRONG - Only allows one null value
collection.create_index(
    [("square_transaction_id", ASCENDING)],
    unique=True,
    name="square_transaction_id_unique"
)
```

**Error:**
```
E11000 duplicate key error collection: translation.user_transactions
index: square_transaction_id_unique dup key: { square_transaction_id: null }
```

**Solution:** Use **sparse** unique indexes for fields populated later:

```python
# ✅ CORRECT - Allows multiple null values
collection.create_index(
    [("square_transaction_id", ASCENDING)],
    unique=True,
    sparse=True,  # Multiple nulls OK, enforces uniqueness on non-null
    name="square_transaction_id_unique"
)
```

**When to Use Sparse Unique:**
- Payment IDs (null before payment, unique after)
- External system IDs (null before sync, unique after)
- Any field populated asynchronously

**Migration:**
```bash
python scripts/fix_sparse_index_migration.py --database translation_test --confirm
```

**Why This Matters:**
- Integration tests create multiple transactions with `null` payment IDs
- Without sparse, second transaction fails → test fails
- Sparse allows test data while enforcing uniqueness on real data

---

## Plugin System (wshobson/agents)

**Install:**
```bash
/plugin marketplace add wshobson/agents
/plugin install backend-development database-development debugging-toolkit security-scanning testing-automation
```

**Key Plugins:**
- `backend-development` - API design, architecture, docs
- `database-development` - Schema, migrations, optimization
- `debugging-toolkit` - Bug investigation, incidents
- `security-scanning` - Audits, OWASP compliance
- `testing-automation` - Test generation, coverage

**Core Agents:**
| Agent | Purpose | When to Use |
|-------|---------|-------------|
| `backend-architect` | API/system design | New features, API design needed |
| `database-architect` | Schema design | New collections, relationships |
| `python-pro` | FastAPI implementation | Writing code, refactoring |
| `database-admin` | MongoDB setup, indexes | Index creation, migrations |
| `database-optimizer` | Query optimization | Slow queries, performance issues |
| `test-automator` | Test generation | Need tests, coverage gaps |
| `security-auditor` | Security scanning | Security review, OWASP check |
| `performance-engineer` | Performance profiling | Performance issues, benchmarking |
| `incident-responder` | Production debugging | Production issues, incidents |
| `code-reviewer` | Code quality review | Code review, refactoring |
| `debugger` | Root cause analysis | Bug investigation, errors |

---

## Agent Usage

**Quick Workflows (use scripts):**
```bash
# Complete feature with all agents - runs scripts/feature_flow.py
"FLOW: implement [feature_name]"

# Generate tests - runs scripts/gen_tests.py
"TESTS: generate for [module]"

# Optimize DB - runs scripts/optimize_db.py
"OPTIMIZE: [collection]"
```

**Direct Agent Invocation:**
```bash
# Natural language (auto-select)
"Design REST API for document translation"

# Explicit
"Use backend-architect to design authentication API with OAuth2"

# Multi-agent chain
"Implement payment feature"
→ backend-architect → python-pro → test-automator → security-auditor
```

**Always Include:**
1. Context (file structure, dependencies, existing behavior)
2. Acceptance criteria (status codes, schemas, performance targets)
3. Constraints (what not to change, compatibility)
4. For bugs: test case, logs, steps to reproduce

---

## Database Development

**MCP Setup** (`~/.claude/mcp.json` or `.claude/mcp.json`):
```json
{
  "mcpServers": {
    "mongodb": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-mongodb"],
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017/translation"
      }
    },
    "mongodb_test": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-mongodb"],
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017/translation_test"
      }
    }
  }
}
```

**Available MCP Operations:**
- `list_databases` - List all databases
- `list_collections` - List collections in current database
- `find` - Query documents with filter
- `aggregate` - Run aggregation pipeline
- `insert_one` / `insert_many` - Create documents
- `update_one` / `update_many` - Update documents
- `delete_one` / `delete_many` - Delete documents
- `count_documents` - Count matching documents
- `create_index` - Create collection index

---

## Real Integration Testing (MANDATORY)

**Default Testing Mode:** Real Running Webserver + Real MongoDB

**CRITICAL:** All integration tests MUST run against:
1. **Real running FastAPI webserver** (`uvicorn app.main:app --port 8000`)
2. **Real HTTP requests** (using `httpx.AsyncClient`)
3. **Real MongoDB test database** (`translation_test`)

**Test Database:** `translation_test` (separate from production `translation`)

**Setup:**
```bash
# Terminal 1: Start test server
DATABASE_MODE=test uvicorn app.main:app --reload --port 8000

# Terminal 2: Run integration tests
pytest tests/integration/ -v
```

**NEVER:**
- ❌ Direct function imports for integration tests
- ❌ Mocking internal services/database (unless explicitly approved)
- ❌ Testing against production database

---

## Implementation Patterns

See complete examples in the full CLAUDE.md file for:
- Route Implementation
- Service Layer
- Repository Pattern
- Error Handling
- Performance Monitoring

---

## Commands
```bash
# Development
uvicorn app.main:app --reload --port 8000

# Testing
pytest -v --cov=app                          # All tests with coverage
./scripts/test.sh all                        # Full test suite with reporting

# DB Optimization
./scripts/optimize_db.py --collection users  # Optimize specific collection

# Test Generation
./scripts/gen_tests.py openapi.yaml          # Generate tests from spec

# Linting & Security
ruff check app tests --fix                   # Lint and auto-fix
bandit -r app -ll                            # Security scan

