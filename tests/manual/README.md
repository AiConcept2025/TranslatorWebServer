# Manual Test Scripts

This directory contains manual test scripts for development and debugging purposes.

## Test Scripts

### Authentication & Authorization
- `test_auth_endpoints.py` - Test authentication endpoints
- `test_password_hash.py` - Verify password hashing
- `test_user_authentication.py` - Test user authentication flow

### Payment & Transactions
- `test_payment_success.py` - Test successful payment flow
- `test_transaction_insert.py` - Test transaction creation
- `test_transaction_timeout.py` - Test transaction timeout handling
- `test_payment_instant.sh` - Quick payment endpoint test
- `test_instant_response.sh` - Test response time

### Data & Database
- `test_db.py` - Database connection and operations
- `test_mongodb_setup.py` - MongoDB setup verification
- `test_data.py` - Data manipulation tests
- `test_subscriptions.py` - Subscription management tests

### API Endpoints
- `test_actual_client_payload.py` - Test with actual client data
- `test_translate_performance.py` - Performance testing for translation endpoint
- `test_login.sh` - Quick login endpoint test

## Usage

### Running Python Tests
```bash
# Activate virtual environment
source venv/bin/activate

# Run individual test
python tests/manual/test_auth_endpoints.py

# Run with verbose output
python tests/manual/test_translate_performance.py -v
```

### Running Shell Scripts
```bash
# Make executable if needed
chmod +x tests/manual/test_login.sh

# Run shell test
./tests/manual/test_login.sh

# Or use bash directly
bash tests/manual/test_payment_instant.sh
```

## Test Categories

### Quick Tests (Shell Scripts)
Fast smoke tests for rapid feedback during development:
- `test_login.sh` - Login endpoint health check
- `test_instant_response.sh` - Response time check
- `test_payment_instant.sh` - Payment endpoint check

### Integration Tests (Python)
More comprehensive tests that verify multiple components:
- `test_auth_endpoints.py` - Full auth flow
- `test_translate_performance.py` - End-to-end translation
- `test_user_authentication.py` - Complete user journey

### Unit Tests (Python)
Focused tests for specific functionality:
- `test_password_hash.py` - Password hashing only
- `test_transaction_insert.py` - Transaction creation only

## Notes
- These are **manual** tests - not part of the automated test suite
- Automated tests are in `tests/unit/`, `tests/integration/`, etc.
- Manual tests are useful for:
  - Quick smoke testing during development
  - Debugging specific issues
  - Performance profiling
  - API exploration

## Automated Tests
For automated test suites, see:
- `tests/unit/` - Unit tests (pytest)
- `tests/integration/` - Integration tests (pytest)
- `tests/functional/` - Functional tests (pytest)
- `tests/README.md` - Main test documentation
