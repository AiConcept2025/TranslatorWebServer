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

**Default Testing Mode:** Real API + Real MongoDB

All tests use real backend endpoints and MongoDB connections unless explicitly mocking external services.

**Test Database:** `translation_test` (separate from production)

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

