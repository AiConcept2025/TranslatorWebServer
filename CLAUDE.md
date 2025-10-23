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
```

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

