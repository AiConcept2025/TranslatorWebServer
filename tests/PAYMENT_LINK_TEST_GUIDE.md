# Stripe Payment Link Test Guide

## Overview

Comprehensive test suite for Stripe payment link integration covering:
- **Unit tests**: Service logic with mocked Stripe API
- **Integration tests**: Full invoice email flow with real HTTP requests

---

## Test Files Created

### 1. Unit Tests
**File**: `tests/unit/test_stripe_payment_link_service.py`

**Coverage**:
- ✅ Successful payment link creation
- ✅ Idempotency (reuse existing links)
- ✅ Skip paid invoices
- ✅ Decimal128 to cents conversion
- ✅ Handle None/zero/negative amounts
- ✅ Stripe API error handling (graceful degradation)
- ✅ Database update verification
- ✅ Payment link metadata validation
- ✅ Invalid amount rejection
- ✅ Unexpected error handling

**Test Count**: 16 unit tests

### 2. Integration Tests
**File**: `tests/integration/test_invoice_payment_link_integration.py`

**Coverage**:
- ✅ Full flow: send invoice → payment link created → stored in DB
- ✅ Paid invoice skips link creation
- ✅ Invoice email response includes payment_link_url
- ✅ Stripe API failure doesn't break email sending
- ✅ Idempotency reuses existing links
- ✅ Invalid amounts prevent link creation

**Test Count**: 6 integration tests

---

## Running the Tests

### Prerequisites

1. **Start test server** (in Terminal 1):
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
```

2. **Verify test database** is being used:
   - Check server logs for: `Active Database: translation_test`
   - ⚠️ **NEVER run tests against production database!**

### Run Unit Tests

```bash
# All unit tests for payment link service
pytest tests/unit/test_stripe_payment_link_service.py -v

# Specific test
pytest tests/unit/test_stripe_payment_link_service.py::TestStripePaymentLinkService::test_create_payment_link_success -v

# With coverage
pytest tests/unit/test_stripe_payment_link_service.py -v --cov=app.services.stripe_payment_link_service
```

### Run Integration Tests

```bash
# All integration tests for payment link
pytest tests/integration/test_invoice_payment_link_integration.py -v

# Specific test
pytest tests/integration/test_invoice_payment_link_integration.py::TestInvoicePaymentLinkIntegration::test_send_invoice_creates_payment_link -v

# With detailed output
pytest tests/integration/test_invoice_payment_link_integration.py -v -s
```

### Run All Payment Link Tests

```bash
# Both unit and integration tests
pytest tests/unit/test_stripe_payment_link_service.py tests/integration/test_invoice_payment_link_integration.py -v

# With coverage report
pytest tests/unit/test_stripe_payment_link_service.py tests/integration/test_invoice_payment_link_integration.py -v --cov=app.services.stripe_payment_link_service --cov-report=html
```

---

## Expected Test Output

### Unit Tests (Example)

```
tests/unit/test_stripe_payment_link_service.py::TestStripePaymentLinkService::test_create_payment_link_success PASSED
tests/unit/test_stripe_payment_link_service.py::TestStripePaymentLinkService::test_idempotency_returns_existing_link PASSED
tests/unit/test_stripe_payment_link_service.py::TestStripePaymentLinkService::test_skip_paid_invoice PASSED
tests/unit/test_stripe_payment_link_service.py::TestStripePaymentLinkService::test_decimal128_to_cents_conversion PASSED
...

======================== 16 passed in 2.34s ========================
```

### Integration Tests (Example)

```
tests/integration/test_invoice_payment_link_integration.py::TestInvoicePaymentLinkIntegration::test_send_invoice_creates_payment_link PASSED
tests/integration/test_invoice_payment_link_integration.py::TestInvoicePaymentLinkIntegration::test_paid_invoice_skips_payment_link_creation PASSED
tests/integration/test_invoice_payment_link_integration.py::TestInvoicePaymentLinkIntegration::test_stripe_api_failure_does_not_break_email_sending PASSED
...

======================== 6 passed in 8.12s ========================
```

---

## Test Verification Checklist

After running tests, verify:

- [ ] All unit tests pass (16/16)
- [ ] All integration tests pass (6/6)
- [ ] No HTTP logs missing in integration test output
- [ ] Test database used (translation_test), NOT production
- [ ] Stripe API calls are mocked (no real charges)
- [ ] Database cleanup successful (no TEST- prefixed records remain)
- [ ] Coverage >= 90% for stripe_payment_link_service.py

---

## Test Strategy

### Unit Tests - Mock Stripe API
- **Purpose**: Test service logic in isolation
- **Speed**: Fast (no network calls)
- **Scope**:
  - Amount conversion logic
  - Error handling
  - Business rules (skip paid invoices)
  - Database update operations

### Integration Tests - Real HTTP + Mock Stripe
- **Purpose**: Test full invoice email flow
- **Speed**: Slower (real HTTP requests)
- **Scope**:
  - API endpoint behavior
  - HTTP request/response structure
  - Database state changes
  - Graceful degradation (Stripe errors)

---

## Key Test Patterns

### 1. Mocking Stripe API (Unit Tests)

```python
with patch('stripe.Price.create') as mock_price, \
     patch('stripe.PaymentLink.create') as mock_link:

    mock_price.return_value = MagicMock(id="price_123")
    mock_link.return_value = MagicMock(
        id="plink_123",
        url="https://buy.stripe.com/test_link"
    )

    result = await service.create_or_get_payment_link(invoice, mock_db)
```

### 2. Real HTTP Testing (Integration Tests)

```python
response = await http_client.post(
    f"/api/v1/invoices/{invoice_id}/send-email",
    headers=auth_headers
)

assert response.status_code == 200
data = response.json()
assert "payment_link_url" in data
```

### 3. Database Verification

```python
# Verify database state after operation
updated_invoice = await test_db.invoices.find_one({"_id": ObjectId(invoice_id)})
assert updated_invoice["stripe_payment_link_url"] == expected_url
assert "stripe_payment_link_id" in updated_invoice
```

---

## Troubleshooting

### Issue: Tests fail with "Server not running"
**Solution**: Start test server in separate terminal:
```bash
DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
```

### Issue: No HTTP logs in integration test output
**Problem**: Test is using direct function calls instead of HTTP API
**Solution**: Verify test uses `http_client.post()`, not service imports

### Issue: Stripe API key errors
**Problem**: Real Stripe API calls being made
**Solution**: Verify `@patch('stripe.Price.create')` is active in test

### Issue: Database errors (E11000 duplicate key)
**Problem**: Test cleanup not working
**Solution**:
1. Check TEST- prefix on all test data
2. Verify cleanup runs after each test
3. Manually clean: `await test_db.invoices.delete_many({"invoice_number": {"$regex": "^TEST-"}})`

### Issue: "Production database" error
**Problem**: DATABASE_MODE not set to "test"
**Solution**: Ensure server started with `DATABASE_MODE=test`

---

## Coverage Report

View detailed coverage:
```bash
pytest tests/unit/test_stripe_payment_link_service.py tests/integration/test_invoice_payment_link_integration.py --cov=app.services.stripe_payment_link_service --cov-report=html

# Open in browser
open htmlcov/index.html
```

Expected coverage: **>90%** for `stripe_payment_link_service.py`

---

## Next Steps

After all tests pass:

1. **Review coverage report** - Identify any untested edge cases
2. **Run full test suite** - Ensure no regressions:
   ```bash
   pytest tests/ -v
   ```
3. **Manual testing** - Test in UI with real Stripe test mode
4. **Update documentation** - Add payment link feature to API docs
5. **Monitor logs** - Check for `[PAYMENT_LINK]` logs in production

---

## Success Criteria

✅ All tests pass (22/22)
✅ Coverage >= 90% for payment link service
✅ No Stripe API calls in test logs (all mocked)
✅ Database state verified after each operation
✅ Graceful degradation tested (Stripe errors don't break emails)
✅ Test data cleanup successful
✅ No production database usage

---

## Contact

If tests fail or you encounter issues:
1. Check server logs for `[PAYMENT_LINK]` errors
2. Verify Stripe API key configuration
3. Ensure test database is properly configured
4. Review test output for specific assertion failures
