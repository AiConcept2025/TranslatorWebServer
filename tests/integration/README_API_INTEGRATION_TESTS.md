# Integration Tests - HTTP API Endpoints

## Overview

This directory contains **real integration tests** that make actual HTTP requests to the running FastAPI server and verify responses against the MongoDB database.

**NO MOCKS** - These tests use:
- Real HTTP API endpoints (via httpx.AsyncClient)
- Real MongoDB database (translation_test)
- Real authentication (JWT tokens)

## Test Files

### `test_table_updates_simplified.py`

Tests UPDATE operations via HTTP API on:
- **Subscriptions**: POST, GET, PATCH endpoints
- **Company Users**: POST, GET endpoints
- **Companies**: GET endpoint

**Test Coverage:**
1. **Subscription Status Update** - Create → Get → Update → Verify
2. **Subscription Units/Price Update** - Update multiple fields
3. **Company User Creation** - Create user and verify via GET
4. **Company Query** - Query companies via API

## Prerequisites

### 1. Running FastAPI Server

The tests require a **running FastAPI server** on `localhost:8000`:

```bash
# Terminal 1 - Start the server
cd /Users/vladimirdanishevsky/projects/Translator/server
uvicorn app.main:app --reload --port 8000
```

### 2. MongoDB Test Database

The tests use the `translation_test` database:

```bash
# MongoDB connection string (configured in tests)
mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation
```

### 3. Python Dependencies

```bash
pip install pytest pytest-asyncio httpx motor pymongo bcrypt
```

## Running Tests

### Run All Tests

```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
pytest tests/integration/test_table_updates_simplified.py -v -s
```

### Run Specific Test Class

```bash
# Subscription tests only
pytest tests/integration/test_table_updates_simplified.py::TestSubscriptionAPIUpdates -v -s

# Company user tests only
pytest tests/integration/test_table_updates_simplified.py::TestCompanyUserAPIUpdates -v -s

# Company tests only
pytest tests/integration/test_table_updates_simplified.py::TestCompanyAPIUpdates -v -s
```

### Run Specific Test

```bash
pytest tests/integration/test_table_updates_simplified.py::TestSubscriptionAPIUpdates::test_update_subscription_status -v -s
```

### Run as Python Script (Alternative)

```bash
python tests/integration/test_table_updates_simplified.py
```

## Test Data Management

### Automatic Cleanup

Tests use the `cleanup_test_data` fixture which:
- **Before test**: Deletes all test records matching `TEST_UPDATE_API_*` prefix
- **After test**: Deletes all test records matching `TEST_UPDATE_API_*` prefix

This ensures:
- Clean slate for each test
- No test data pollution
- Idempotent test execution

### Test Data Prefix

All test data uses the prefix `TEST_UPDATE_API_` to identify test records:

```python
TEST_PREFIX = "TEST_UPDATE_API_"
TEST_COMPANY = "TEST_UPDATE_API_TestCorp"
TEST_USER_EMAIL = "TEST_UPDATE_API_user@testcorp.com"
```

### Manual Cleanup (if needed)

If tests fail and leave test data, clean up manually:

```javascript
// MongoDB Shell
use translation_test

// Remove test subscriptions
db.subscriptions.deleteMany({company_name: /^TEST_UPDATE_API_/})

// Remove test users
db.company_users.deleteMany({email: /^TEST_UPDATE_API_/})

// Remove test companies
db.companies.deleteMany({company_name: /^TEST_UPDATE_API_/})
db.company.deleteMany({company_name: /^TEST_UPDATE_API_/})
```

## Authentication

Tests use **real JWT authentication** via the `admin_token` fixture:

1. Creates test company via database (no POST endpoint)
2. Creates admin user via database (password hashing with bcrypt)
3. Authenticates via `/api/auth/login` endpoint
4. Returns JWT token for authenticated requests

**Admin Credentials:**
- Email: `TEST_UPDATE_API_admin@testcorp.com`
- Password: `AdminPass123`
- Permission: `admin`
- Company: `TEST_UPDATE_API_TestCorp`

## Test Flow Pattern

All tests follow this pattern:

```python
async def test_example(http_client, db, cleanup_test_data, admin_token):
    # 1. CREATE via HTTP POST API
    create_response = await http_client.post(
        "/api/endpoint",
        json=data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert create_response.status_code in [200, 201]

    # 2. GET original state via HTTP GET API
    get_response = await http_client.get(f"/api/endpoint/{id}")
    assert get_response.status_code == 200
    before = get_response.json()

    # 3. UPDATE via HTTP PATCH API
    update_response = await http_client.patch(
        f"/api/endpoint/{id}",
        json=update_data,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert update_response.status_code == 200

    # 4. GET updated state via HTTP GET API
    get_after_response = await http_client.get(f"/api/endpoint/{id}")
    assert get_after_response.status_code == 200
    after = get_after_response.json()

    # 5. VERIFY changes via assertions
    assert after["field"] != before["field"]

    # 6. VERIFY in database (optional but recommended)
    db_record = await db.collection.find_one({"_id": ObjectId(id)})
    assert db_record["field"] == expected_value
```

## Expected Output

Tests include detailed logging:

```
================================================================================
STEP 1: CREATE subscription via POST API
================================================================================
📤 POST /api/subscriptions/ - Status: 201
📥 Response: {'success': True, 'data': {'subscription_id': '...'}}
✅ Created subscription via API: 678a9b0c1d2e3f4g5h6i7j8k

================================================================================
STEP 2: GET original state via GET API
================================================================================
📤 GET /api/subscriptions/678a9b0c1d2e3f4g5h6i7j8k - Status: 200
📥 Response: {'success': True, 'data': {'status': 'active', ...}}
✅ Verified initial status via API: active

================================================================================
STEP 3: UPDATE subscription via PATCH API
================================================================================
📤 PATCH /api/subscriptions/678a9b0c1d2e3f4g5h6i7j8k - Status: 200
📦 Update Data: {'status': 'inactive'}
📥 Response: {'success': True, ...}
✅ Updated subscription via API

================================================================================
STEP 4: VERIFY update via GET API
================================================================================
📤 GET /api/subscriptions/678a9b0c1d2e3f4g5h6i7j8k - Status: 200
📥 Response: {'success': True, 'data': {'status': 'inactive', ...}}
✅ Verified status changed via API: active → inactive

================================================================================
STEP 5: VERIFY in database
================================================================================
✅ Database confirmed: status = inactive
```

## Troubleshooting

### Server Not Running

```
Error: httpx.ConnectError: [Errno 61] Connection refused
```

**Solution:** Start the FastAPI server:
```bash
uvicorn app.main:app --reload --port 8000
```

### Authentication Failed

```
Error: Login failed: 401
```

**Solution:** Check admin user exists in database or recreate via fixture

### Test Data Not Cleaned

```
Error: Email already exists for this company
```

**Solution:** Run manual cleanup (see above) or restart tests

### Database Connection Failed

```
Error: ServerSelectionTimeoutError
```

**Solution:** Ensure MongoDB is running and connection string is correct

## Key Differences from Direct Database Tests

| Aspect | Direct DB Tests | HTTP API Tests |
|--------|----------------|----------------|
| **Method** | `db.collection.insert_one()` | `http_client.post("/api/endpoint")` |
| **Authentication** | Not needed | JWT token required |
| **Validation** | Manual | Automatic via Pydantic |
| **Error Handling** | Manual | Automatic via FastAPI |
| **Real User Flow** | No | Yes |
| **API Contract Testing** | No | Yes |

## Benefits of HTTP API Testing

1. **Tests Real User Flow** - Same path as frontend/API consumers
2. **Validates API Contracts** - Ensures request/response match specs
3. **Tests Authentication** - Verifies JWT and permissions
4. **Tests Validation** - Pydantic validation automatically tested
5. **Tests Error Handling** - HTTP error responses tested
6. **Integration Testing** - Full stack (routes → services → database)
7. **Documentation** - Tests serve as API usage examples

## Next Steps

- Add more test cases for edge cases (invalid data, unauthorized access)
- Add performance benchmarks for API endpoints
- Add tests for error scenarios (404, 403, 422, 500)
- Add tests for pagination and filtering
- Add tests for concurrent requests
- Add load testing with multiple parallel requests

## Related Files

- **API Routers**: `/Users/vladimirdanishevsky/projects/Translator/server/app/routers/`
- **Services**: `/Users/vladimirdanishevsky/projects/Translator/server/app/services/`
- **Models**: `/Users/vladimirdanishevsky/projects/Translator/server/app/models/`
- **Database**: `/Users/vladimirdanishevsky/projects/Translator/server/app/database/`

## Contact

For questions or issues with these tests, refer to:
- Main project CLAUDE.md: `/Users/vladimirdanishevsky/projects/Translator/CLAUDE.md`
- Server CLAUDE.md: `/Users/vladimirdanishevsky/projects/Translator/server/CLAUDE.md`
