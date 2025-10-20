# CLAUDE.md - FastAPI Backend

**Stack:** Python 3.11+, FastAPI 0.104+, Pydantic v2, Uvicorn, pytest-asyncio, httpx

## Structure
```
server/
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── core/                # config, security, deps
│   ├── api/v1/              # versioned routes
│   ├── services/            # business logic
│   ├── models/              # Pydantic schemas
│   ├── db/                  # models, session, repos
│   └── middleware/          # logging, CORS, rate limiting
├── tests/                   # unit, integration, fixtures
└── alembic/                 # migrations
```

**Quick Start:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
pytest -v --cov=app
```

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
| Agent | Purpose |
|-------|---------|
| `backend-architect` | API/system design |
| `database-architect` | Schema design |
| `python-backend-engineer` | FastAPI implementation |
| `database-admin` | Migrations, setup |
| `database-optimizer` | Query optimization, indexing |
| `test-automator` | Test generation |
| `security-auditor` | Security scanning |
| `performance-engineer` | Performance profiling |
| `incident-responder` | Production debugging |
| `code-reviewer` | Code quality review |

## Agent Usage

**Decision Tree:**
- Architecture/Design → `backend-architect`, `database-architect`
- Implementation → `python-backend-engineer`, `database-admin`
- Testing → `test-automator`
- Security → `security-auditor`, `backend-security-coder`
- Performance → `performance-engineer`, `database-optimizer`
- Incidents → `incident-responder`

**Invocation:**
```bash
# Natural language (auto-select)
"Design REST API for document translation"

# Explicit
"Use backend-architect to design authentication API with OAuth2"

# Plugin workflow
/backend-development:api-design "document translation service"

# Multi-agent chain
"Implement payment feature"
→ backend-architect → python-backend-engineer → test-automator → security-auditor
```

**Always Include:**
1. Context (file structure, dependencies, existing behavior)
2. Acceptance criteria (status codes, schemas, performance targets)
3. Constraints (what not to change, compatibility)
4. For bugs: test case, logs, steps to reproduce

## Database Development

**MCP Setup** (`~/.claude.json`):
```json
{
  "mcpServers": {
    "postgresql": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {"POSTGRES_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/db"}
    }
  }
}
```

**Usage:**
```bash
# Direct queries
"Show all tables" | "Get schema for users table"

# With agents
"Use database-optimizer to analyze query performance for documents table"
```

## Workflows

**New Feature:**
```
1. backend-architect: Design API spec
2. database-architect: Schema design (if needed)
3. python-backend-engineer: Implement
4. test-automator: Create tests
5. security-auditor: Security review
6. performance-engineer: Profile (target: p95 <200ms)
7. code-reviewer: Final review
```

**Production Incident:**
```
1. incident-responder: Triage
2. debugger: Root cause analysis
3. python-backend-engineer: Fix
4. test-automator: Regression test
5. deployment-engineer: Deploy
```

## Quality Gates (Mandatory)
```bash
pytest -v --cov=app --cov-report=term-missing  # 80% coverage
mypy app --strict
ruff check app tests --fix
black app tests --check
bandit -r app -ll
pip-audit
```

## FastAPI Patterns

**App Factory:**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB pool, cache
    yield
    # Shutdown: close connections

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    # Add middleware, routers
    return app
```

**Thin Controllers:**
```python
@router.post("/", response_model=TranslationResponse, status_code=202)
async def create_translation(
    file: UploadFile = File(...),
    service: TranslationService = Depends(get_translation_service),
    current_user = Depends(get_current_user),
) -> TranslationResponse:
    result = await service.create_translation_job(file, current_user.id)
    return result
```

**Service Layer:**
```python
class TranslationService:
    def __init__(self, db: AsyncSession):
        self.repo = TranslationRepository(db)
    
    async def create_translation_job(self, file: UploadFile, user_id: str):
        file_data = await file.read()
        await self._validate_file(file_data)
        return await self.repo.create_job(user_id=user_id)
```

**Repository:**
```python
class TranslationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, job_id: str) -> Translation | None:
        result = await self.db.execute(
            select(Translation).where(Translation.id == job_id)
        )
        return result.scalar_one_or_none()
```

## Performance Budgets
| Endpoint | P95 Target |
|----------|------------|
| GET /health | <20ms |
| GET /api/v1/translations | <100ms |
| POST /api/v1/translate | <200ms |

## Agent Templates

**API Design:**
```
"Use backend-architect to design auth API:
- POST /api/v1/auth/login, /refresh
- JWT RS256, 15min access, 7d refresh
- Rate limit: 5/min
→ Spec, errors, security, examples"
```

**DB Optimization:**
```
"Use database-optimizer for translations query (850ms → <200ms):
[query]
→ Query plan, indexes, rewrite, metrics, test"
```

**Security:**
```
"Use security-auditor for app/core/security.py:
- OWASP Top 10, hardcoded secrets, SQL injection
→ Vulnerability report, fixes, tests"
```

## Commands
```bash
# Dev
uvicorn app.main:app --reload

# Test
pytest -v --cov=app
pytest tests/integration/test_translate.py -v

# Lint
ruff check app tests --fix && black app tests && mypy app --strict

# DB
alembic revision --autogenerate -m "msg"
alembic upgrade head
```

