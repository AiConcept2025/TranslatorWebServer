# Integration Tests Guide

This directory contains comprehensive integration tests for the Translation Service API.

## Overview

Integration tests validate the complete request-response flow of API endpoints using:
- **Real MongoDB connections** (translation_test database)
- **Real FastAPI application** (via httpx.AsyncClient)
- **Real authentication** (session tokens and JWT)
- **No mocking** (except for external services like Square API)

## Test Files

### `test_payments_api.py`
Comprehensive tests for all payment endpoints:

**Endpoints Covered:**
- `POST /api/v1/payments/subscription` - Create subscription payment (admin only)
- `GET /api/v1/payments/` - Get all payments (admin only)
- `GET /api/v1/payments/company/{company_name}` - Get company payments
- `GET /api/v1/payments/email/{email}` - Get payments by email
- `GET /api/v1/payments/{payment_id}` - Get payment by ID
- `GET /api/v1/payments/square/{square_payment_id}` - Get payment by Square ID
- `PATCH /api/v1/payments/{square_payment_id}` - Update payment
- `POST /api/v1/payments/{square_payment_id}/refund` - Process refund
- `GET /api/v1/payments/company/{company_name}/stats` - Get payment statistics

**Test Coverage:**
- ✅ Success cases with valid data
- ❌ Authentication failures (missing, invalid tokens)
- ❌ Authorization failures (non-admin accessing admin endpoints)
- ❌ Validation errors (invalid IDs, amounts, statuses)
- ❌ Business logic errors (company mismatch, refund exceeds amount)
- ✅ Pagination and filtering
- ✅ Sorting and date ranges
- ✅ Edge cases (empty results, special characters)

**Test Count:** 40+ test cases

### `test_subscription_payments.py`
Legacy tests for subscription payment creation (can be consolidated).

## Running Tests

### Run All Integration Tests
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
pytest tests/integration/ -v
```

### Run Specific Test File
```bash
pytest tests/integration/test_payments_api.py -v
```

### Run Specific Test Class
```bash
pytest tests/integration/test_payments_api.py::TestCreateSubscriptionPayment -v
```

### Run Single Test
```bash
pytest tests/integration/test_payments_api.py::TestCreateSubscriptionPayment::test_create_subscription_payment_success -v
```

### Run with Coverage
```bash
pytest tests/integration/test_payments_api.py --cov=app.routers.payments --cov-report=html
```

### Run with Output
```bash
pytest tests/integration/test_payments_api.py -v -s
```

## Test Database

**Database:** `translation_test`
**Connection:** Configured in `app/database/mongodb.py`

### Database Setup
```bash
# Tests automatically connect to test database
# No manual setup required - fixtures handle creation/cleanup
```

### Data Cleanup
All test fixtures automatically clean up:
- Test users
- Test sessions
- Test companies
- Test subscriptions
- Test payments

**No data persists between test runs.**

## Test Fixtures

### Authentication Fixtures

**`admin_token`**
- Creates admin user with session token
- Returns: `Tuple[str, Dict]` - (token, user_data)
- Auto-cleanup after test

**`user_token`**
- Creates regular user with session token
- Returns: `Tuple[str, Dict]` - (token, user_data)
- Auto-cleanup after test

### Data Fixtures

**`test_company`**
- Creates test company record
- Returns: `str` - company_name
- Auto-cleanup after test

**`test_subscription`**
- Creates test subscription linked to company
- Returns: `Tuple[str, str]` - (subscription_id, company_name)
- Auto-cleanup after test

**`sample_payment`**
- Creates sample payment record
- Returns: `Dict` - payment document with _id
- Auto-cleanup after test

### Client Fixture

**`client`**
- AsyncClient for making API requests
- Base URL: "http://test"
- Yields: `AsyncClient` instance

**`test_db`**
- Motor AsyncIOMotorDatabase connection
- Yields: database instance
- Auto-connects/disconnects

## Writing New Tests

### Template for New Test Class
```python
class TestMyEndpoint:
    """Tests for POST /api/v1/my-endpoint."""

    @pytest.mark.asyncio
    async def test_success_case(self, client, admin_token, test_db):
        """Test successful operation."""
        token, _ = admin_token

        # Setup test data
        test_data = {"field": "value"}

        # Make request
        response = await client.post(
            "/api/v1/my-endpoint",
            json=test_data,
            headers={"Authorization": f"Bearer {token}"}
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Cleanup (if needed)
        # await test_db.collection.delete_one(...)

    @pytest.mark.asyncio
    async def test_unauthorized(self, client):
        """Test error when not authenticated."""
        response = await client.post(
            "/api/v1/my-endpoint",
            json={"field": "value"}
        )

        assert response.status_code == 401
```

### Test Naming Convention
- `test_<action>_<scenario>` - e.g., `test_create_subscription_payment_success`
- Use descriptive docstrings
- Group related tests in classes

### Assertion Best Practices
```python
# ✅ Good - Check status code first
assert response.status_code == 200
data = response.json()
assert data["success"] is True

# ✅ Good - Validate data types
assert isinstance(payment["amount"], int)
assert isinstance(payment["_id"], str)

# ✅ Good - Validate required fields
assert "_id" in payment
assert "created_at" in payment

# ❌ Bad - No status code check
data = response.json()  # Could fail if 500 error
```

## Test Patterns

### Testing Admin-Only Endpoints
```python
@pytest.mark.asyncio
async def test_admin_endpoint_unauthorized(self, client):
    """Test fails without auth."""
    response = await client.get("/api/v1/admin-endpoint")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_admin_endpoint_non_admin(self, client, user_token):
    """Test fails with non-admin user."""
    token, _ = user_token
    response = await client.get(
        "/api/v1/admin-endpoint",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
```

### Testing Pagination
```python
@pytest.mark.asyncio
async def test_pagination(self, client, test_db, test_company):
    """Test pagination works correctly."""
    # Create test data
    payment_ids = []
    for i in range(5):
        payment = {...}
        result = await test_db.payments.insert_one(payment)
        payment_ids.append(result.inserted_id)

    # Test first page
    response = await client.get("/api/v1/payments?limit=2&skip=0")
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["limit"] == 2
    assert data["data"]["skip"] == 0

    # Cleanup
    for payment_id in payment_ids:
        await test_db.payments.delete_one({"_id": payment_id})
```

### Testing Validation Errors
```python
@pytest.mark.asyncio
async def test_invalid_data(self, client, admin_token):
    """Test validation catches invalid data."""
    token, _ = admin_token

    invalid_data = {
        "amount": -100,  # Invalid negative amount
        "email": "not-an-email"  # Invalid email format
    }

    response = await client.post(
        "/api/v1/payments",
        json=invalid_data,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    # or 422 for Pydantic validation errors
```

## Debugging Tests

### View Test Output
```bash
pytest tests/integration/test_payments_api.py -v -s
```

### Run Single Failing Test
```bash
pytest tests/integration/test_payments_api.py::TestClassName::test_method_name -v -s
```

### Use Python Debugger
```python
@pytest.mark.asyncio
async def test_debug_example(self, client, admin_token):
    """Test with debugger."""
    import pdb; pdb.set_trace()  # Add breakpoint

    token, _ = admin_token
    response = await client.get(
        "/api/v1/payments",
        headers={"Authorization": f"Bearer {token}"}
    )
```

### Check Database State
```python
@pytest.mark.asyncio
async def test_check_db(self, test_db):
    """Verify database state during test."""
    # Check what's in database
    payments = await test_db.payments.find({}).to_list(length=100)
    print(f"Found {len(payments)} payments in database")

    for payment in payments:
        print(f"Payment: {payment}")
```

## Common Issues

### Issue: Tests fail with "Database connection error"
**Solution:** Ensure MongoDB is running and connection string is correct in `.env`

### Issue: Tests fail with "Authorization header missing"
**Solution:** Check that admin_token or user_token fixture is being used and passed correctly

### Issue: Tests leave data in database
**Solution:** Ensure cleanup code in fixtures runs (use `yield` pattern, not `return`)

### Issue: Intermittent failures
**Solution:** Tests may interfere with each other. Use unique identifiers (ObjectId) for test data

## Test Coverage Goals

**Target Coverage:** >80% for payment endpoints

### Check Coverage
```bash
pytest tests/integration/test_payments_api.py --cov=app.routers.payments --cov-report=term-missing
```

### Coverage Report
```bash
pytest tests/integration/ --cov=app --cov-report=html
open htmlcov/index.html
```

## Best Practices

1. **Always test authentication/authorization** - Every protected endpoint needs both tests
2. **Test happy path first** - Verify success case before testing failures
3. **Use descriptive test names** - Should explain what is being tested
4. **Clean up after yourself** - Use fixtures for automatic cleanup
5. **Test edge cases** - Empty results, large datasets, special characters
6. **Validate response structure** - Check data types, required fields
7. **Use real data** - No mocking unless testing external services
8. **Test error messages** - Verify helpful error messages are returned

## Test Maintenance

### When Adding New Endpoint
1. Add test class to `test_payments_api.py`
2. Test success case with valid data
3. Test authentication (401)
4. Test authorization if admin-only (403)
5. Test validation errors (400/422)
6. Test edge cases (404, empty results)
7. Update this README

### When Modifying Endpoint
1. Update existing tests
2. Add new tests for new behavior
3. Verify all tests still pass
4. Update test coverage report

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [httpx AsyncClient](https://www.python-httpx.org/async/)
- [Motor (Async MongoDB)](https://motor.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
