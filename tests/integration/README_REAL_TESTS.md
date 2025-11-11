# Real Integration Tests - NO MOCKS

This directory contains **REAL** integration tests that test against **REAL** services with **NO MOCKS**.

## Overview

These tests use:
- ✅ **REAL MongoDB** (translation_test database)
- ✅ **REAL JWT authentication** (actual tokens generated)
- ✅ **REAL Google Drive operations** (files created, moved, deleted)
- ✅ **REAL HTTP requests** to running server (http://localhost:8000)

## Prerequisites

Before running these tests, ensure:

### 1. Server is Running

```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
uvicorn app.main:app --reload --port 8000
```

The server MUST be running on `http://localhost:8000` for tests to work.

### 2. MongoDB is Running

```bash
# Check if MongoDB is running
mongosh --eval "db.version()"

# If not running, start MongoDB
brew services start mongodb-community
# OR
sudo systemctl start mongod
```

MongoDB MUST be accessible at `mongodb://localhost:27017/`.

### 3. Google Drive Credentials Configured

Ensure your Google Drive service account credentials are configured:

```bash
# Check if credentials exist
ls -la /Users/vladimirdanishevsky/projects/Translator/server/service-account-key.json

# Verify .env has correct settings
cat /Users/vladimirdanishevsky/projects/Translator/server/.env | grep GOOGLE_DRIVE
```

Required environment variables:
- `GOOGLE_DRIVE_ENABLED=true`
- `GOOGLE_DRIVE_CREDENTIALS_PATH=./service-account-key.json`

### 4. Python Dependencies Installed

```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
pip install -r requirements.txt -r requirements-dev.txt
```

## Running Tests

### Run All Integration Tests

```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
pytest tests/integration/test_confirm_square_payment.py -v
```

### Run Specific Test

```bash
# Test 1: Valid success request
pytest tests/integration/test_confirm_square_payment.py::test_1_valid_success_request -v

# Test 2: Valid failure request
pytest tests/integration/test_confirm_square_payment.py::test_2_valid_failure_request -v

# Test 3a: Missing square_transaction_id
pytest tests/integration/test_confirm_square_payment.py::test_3a_missing_square_transaction_id -v

# Test 3b: Missing status field
pytest tests/integration/test_confirm_square_payment.py::test_3b_missing_status_field -v

# Test 4: Transaction creation on success
pytest tests/integration/test_confirm_square_payment.py::test_4_transaction_creation_on_success -v

# Test 5: No transaction on failure
pytest tests/integration/test_confirm_square_payment.py::test_5_no_transaction_on_failure -v

# Test 6a: Success response format
pytest tests/integration/test_confirm_square_payment.py::test_6a_success_response_format -v

# Test 6b: Failure response format
pytest tests/integration/test_confirm_square_payment.py::test_6b_failure_response_format -v
```

### Run with Coverage

```bash
pytest tests/integration/test_confirm_square_payment.py -v --cov=app --cov-report=html
```

### Run with Debug Output

```bash
pytest tests/integration/test_confirm_square_payment.py -v -s
```

The `-s` flag shows all print statements, which helps debug test execution.

## Test Coverage

These tests cover:

### 1. Request Validation
- ✅ Valid success request (status=True)
- ✅ Valid failure request (status=False)
- ✅ Missing square_transaction_id field (422 error)
- ✅ Missing status field (422 error)

### 2. Transaction Creation
- ✅ Transaction created with TXN- format ID
- ✅ Transaction has square_transaction_id field
- ✅ Transaction saved to MongoDB
- ✅ Transaction has correct user_id, status, documents

### 3. Success Flow
- ✅ Files found in Google Drive Temp folder
- ✅ Files moved to Inbox folder
- ✅ File metadata updated with transaction_id
- ✅ Response contains transaction_id

### 4. Failure Flow
- ✅ No transaction created
- ✅ Files deleted from Google Drive
- ✅ Response has success=False
- ✅ Response contains files_deleted count

### 5. Response Format
- ✅ Success response structure
- ✅ Failure response structure
- ✅ Field types validated
- ✅ Required fields present

## Test Data Cleanup

Tests use **automatic cleanup** with these strategies:

### 1. TEST- Prefix
All test data uses `TEST-` prefix in `square_transaction_id`:
```python
"square_transaction_id": "TEST-sqt_test123"
```

### 2. Before Each Test
```python
# Clean up any leftover TEST- transactions
await database.user_transactions.delete_many({
    "square_transaction_id": {"$regex": "^TEST-"}
})
```

### 3. After Each Test
```python
# Clean up TEST- transactions created during test
await database.user_transactions.delete_many({
    "square_transaction_id": {"$regex": "^TEST-"}
})
```

### 4. Google Drive Files
```python
# Cleanup fixture automatically deletes test files
for file_id in file_ids:
    await google_drive_service.delete_file(file_id)
```

### 5. Test Users
```python
# Test user deleted after test
await database.users.delete_one({"_id": user_id})
```

## CRITICAL: Data Safety

**NEVER delete production data:**

- ✅ Tests only delete records with `TEST-` prefix
- ✅ Only `test-confirm@example.com` user is used
- ✅ Fixtures ensure cleanup even on test failure
- ✅ Production collections are NEVER touched

**Collections affected by tests:**
- `users` (test user only: `test-confirm@example.com`)
- `user_transactions` (TEST- prefix only)
- Google Drive (test files only: `TEST_integration_test.pdf`)

**Collections NEVER touched:**
- All production user data
- All real transactions
- All real files in Google Drive

## Troubleshooting

### Server Not Running

```
Error: Connection refused on http://localhost:8000
```

**Solution:**
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
uvicorn app.main:app --reload --port 8000
```

### MongoDB Not Running

```
Error: pymongo.errors.ServerSelectionTimeoutError
```

**Solution:**
```bash
brew services start mongodb-community
# OR
sudo systemctl start mongod
```

### Google Drive Credentials Missing

```
Error: GoogleDriveAuthenticationError: credentials file not found
```

**Solution:**
```bash
# Check credentials exist
ls -la service-account-key.json

# Verify .env settings
cat .env | grep GOOGLE_DRIVE
```

### Authentication Errors

```
Error: 401 Unauthorized
```

**Solution:**
Check JWT service is configured:
```bash
cat .env | grep SECRET_KEY
```

SECRET_KEY must be set and at least 32 characters.

### Timeout Errors

```
Error: httpx.ReadTimeout
```

**Solution:**
Increase timeout in test:
```python
async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=60.0) as client:
```

### Google Drive Quota Exceeded

```
Error: HttpError 403: User rate limit exceeded
```

**Solution:**
Wait a few minutes and retry. Google Drive has rate limits.

## Test Execution Flow

Each test follows this pattern:

1. **Setup Phase**
   ```
   → Database connects
   → Test user created in MongoDB
   → JWT token generated
   → Test files uploaded to Google Drive Temp folder
   ```

2. **Execution Phase**
   ```
   → HTTP request sent to localhost:8000
   → Server processes request
   → Real services invoked (MongoDB, Google Drive)
   ```

3. **Verification Phase**
   ```
   → Response status checked (200, 422, etc.)
   → Response data validated
   → Database state verified
   → Google Drive state verified
   ```

4. **Cleanup Phase**
   ```
   → Test transactions deleted (TEST- prefix)
   → Test files deleted from Google Drive
   → Test user deleted from MongoDB
   ```

## Expected Test Output

```
================================ test session starts =================================
platform darwin -- Python 3.11.0, pytest-7.4.0, pluggy-1.3.0 -- ...
cachedir: .pytest_cache
rootdir: /Users/vladimirdanishevsky/projects/Translator/server
plugins: asyncio-0.21.1, cov-4.1.0
collected 8 items

tests/integration/test_confirm_square_payment.py::test_1_valid_success_request PASSED [ 12%]
tests/integration/test_confirm_square_payment.py::test_2_valid_failure_request PASSED [ 25%]
tests/integration/test_confirm_square_payment.py::test_3a_missing_square_transaction_id PASSED [ 37%]
tests/integration/test_confirm_square_payment.py::test_3b_missing_status_field PASSED [ 50%]
tests/integration/test_confirm_square_payment.py::test_4_transaction_creation_on_success PASSED [ 62%]
tests/integration/test_confirm_square_payment.py::test_5_no_transaction_on_failure PASSED [ 75%]
tests/integration/test_confirm_square_payment.py::test_6a_success_response_format PASSED [ 87%]
tests/integration/test_confirm_square_payment.py::test_6b_failure_response_format PASSED [100%]

================================ 8 passed in 45.32s ==================================
```

## Performance Considerations

These tests are **slower** than unit tests because they:
- Make real HTTP requests
- Perform real database operations
- Upload/download real files to Google Drive
- Create/move/delete real files

**Typical execution time:**
- Single test: ~5-10 seconds
- Full test suite: ~45-60 seconds

This is expected and acceptable for **real integration tests**.

## Best Practices

1. **Run server first** - Always ensure server is running before tests
2. **Use TEST- prefix** - All test data must use TEST- prefix
3. **Clean up properly** - Use fixtures for automatic cleanup
4. **Verify real operations** - Check database and Google Drive state
5. **Handle timeouts** - Use appropriate timeout values (30s recommended)
6. **Isolate tests** - Each test should be independent
7. **Document assumptions** - Document what each test assumes/requires

## Differences from Mock Tests

| Aspect | Mock Tests | Real Integration Tests |
|--------|------------|------------------------|
| **Speed** | Fast (~1s per test) | Slower (~5-10s per test) |
| **Isolation** | Complete isolation | Tests real interactions |
| **Setup** | No external services | Server + MongoDB + Google Drive required |
| **Confidence** | Unit-level confidence | End-to-end confidence |
| **Debugging** | Hard to debug integration issues | Easy to debug - real services |
| **CI/CD** | Always works | Requires infrastructure |

## When to Run These Tests

- ✅ Before merging pull requests
- ✅ After changing API endpoints
- ✅ After changing database schemas
- ✅ After changing Google Drive operations
- ✅ Before production deployments
- ✅ When debugging integration issues
- ❌ NOT in CI/CD (requires real services)
- ❌ NOT for rapid unit testing

## Summary

These **REAL integration tests** provide:
- ✅ High confidence in end-to-end functionality
- ✅ Real service interaction validation
- ✅ Database integrity verification
- ✅ Google Drive operation validation
- ✅ Authentication flow testing
- ✅ API contract validation

**Trade-off:** Slower execution, but **much higher confidence** than mock tests.
