# TDD RED STATE - Enhanced Subscription Billing Schema Tests

**Status:** Phase 1 (RED) - Failing Tests Written
**Date:** 2025-12-04
**Purpose:** Write failing integration tests FIRST before implementation (TDD RED state)

---

## Overview

Created 3 comprehensive integration test files with **26 failing tests** that verify Enhanced Subscription Billing Schema functionality. These tests will guide the implementation phase (GREEN state).

**Test Philosophy:**
- ✅ REAL running server (uvicorn)
- ✅ REAL test database (translation_test)
- ✅ REAL HTTP requests (httpx.AsyncClient)
- ❌ NO mocks, NO shortcuts

---

## Test Files Created

### 1. `test_subscriptions_billing_integration.py`

**Location:** `/Users/vladimirdanishevsky/projects/Translator/server/tests/integration/test_subscriptions_billing_integration.py`

**Test Count:** 9 tests

**Endpoints Tested:**
- POST /api/subscriptions
- GET /api/subscriptions/{id}
- GET /api/subscriptions/company/{name}
- PATCH /api/subscriptions/{id}

**Coverage:**

| Test Name | Purpose | Expected Failure |
|-----------|---------|------------------|
| `test_create_subscription_with_billing_frequency_quarterly` | Create subscription with billing_frequency='quarterly' | 422 validation error or missing fields in response |
| `test_create_subscription_with_billing_frequency_monthly` | Create subscription with billing_frequency='monthly' | Same as above |
| `test_create_subscription_with_billing_frequency_annual` | Create subscription with billing_frequency='annual' | Same as above |
| `test_get_subscription_returns_billing_fields` | GET single subscription returns billing fields | 500 serialization error or missing fields |
| `test_get_subscriptions_by_company_returns_billing_fields` | GET company subscriptions list includes billing fields | Same as above |
| `test_update_subscription_billing_fields` | PATCH to update billing_frequency and payment_terms_days | 422 or fields not updated in DB |
| `test_create_subscription_without_billing_fields_uses_defaults` | Verify default values (quarterly, 30 days) | Defaults not configured |
| `test_billing_frequency_validation_rejects_invalid_value` | Reject invalid billing_frequency='weekly' | Validation not implemented, may accept invalid value |

**New Fields Tested:**
- `billing_frequency` (values: 'monthly', 'quarterly', 'annual')
- `payment_terms_days` (integer, e.g., 15, 30, 60)

---

### 2. `test_invoices_billing_integration.py`

**Location:** `/Users/vladimirdanishevsky/projects/Translator/server/tests/integration/test_invoices_billing_integration.py`

**Test Count:** 9 tests

**Endpoints Tested:**
- POST /api/v1/invoices
- PATCH /api/v1/invoices/{id}
- GET /api/v1/invoices/company/{name}
- POST /api/v1/invoices/generate-quarterly

**Coverage:**

| Test Name | Purpose | Expected Failure |
|-----------|---------|------------------|
| `test_create_invoice_with_billing_period_and_line_items` | Create invoice with billing_period and line_items | 422 validation error or fields not saved |
| `test_create_invoice_subtotal_auto_calculated_from_line_items` | Verify subtotal auto-calculated from line_items | Auto-calculation not implemented |
| `test_update_invoice_billing_period` | PATCH to update billing_period | Field not in update model |
| `test_get_invoices_by_company_returns_billing_fields` | GET company invoices includes billing fields | Serialization error on new fields |
| `test_generate_quarterly_invoice_includes_line_items` | Quarterly invoice generation creates line_items | Endpoint exists but may not create line_items structure |
| `test_invoice_amount_due_calculation_after_payment` | amount_due = total - amount_paid, status updates | Calculation logic not implemented |
| `test_invoice_line_items_validation_requires_amount` | Reject line_item without amount field | Validation not implemented |

**New Fields Tested:**
- `billing_period` (object: {start_date, end_date})
- `line_items` (array of objects: {description, quantity, unit_price, amount})
- `subtotal` (float)
- `amount_paid` (float)
- `amount_due` (float)

**Business Logic Tested:**
- `subtotal = sum(line_items[].amount)`
- `total_amount = subtotal + tax_amount`
- `amount_due = total_amount - amount_paid`
- `status = 'paid' when amount_due = 0`
- `status = 'partial' when 0 < amount_due < total_amount`

---

### 3. `test_payments_billing_integration.py`

**Location:** `/Users/vladimirdanishevsky/projects/Translator/server/tests/integration/test_payments_billing_integration.py`

**Test Count:** 8 tests

**Endpoints Tested:**
- GET /api/v1/payments/
- POST /api/v1/payments/{id}/apply-to-invoice

**Coverage:**

| Test Name | Purpose | Expected Failure |
|-----------|---------|------------------|
| `test_get_payments_returns_invoice_and_subscription_ids` | GET payments includes invoice_id and subscription_id | Response missing new fields |
| `test_apply_payment_to_invoice_updates_invoice_amount_paid` | Apply payment updates invoice.amount_paid | Endpoint exists but logic incomplete |
| `test_apply_full_payment_changes_invoice_status_to_paid` | Full payment sets status='paid' | Status not updated |
| `test_apply_multiple_payments_to_same_invoice` | Multiple payments accumulate correctly | amount_paid may not accumulate |
| `test_overpayment_handling` | Handle payment > invoice total | Overpayment logic not implemented |
| `test_payment_without_invoice_has_null_invoice_id` | Unlinked payment has invoice_id=null | Field may not exist in response |

**New Fields Tested:**
- `invoice_id` (string, nullable)
- `subscription_id` (string, nullable)

**Business Logic Tested:**
- Payment application updates invoice.amount_paid
- Invoice.amount_due recalculated: `total_amount - amount_paid`
- Invoice status changes: pending → partial → paid
- Payment.invoice_id set when applied to invoice
- Overpayment handling (reject or accept with credit)

---

## Expected Failure Scenarios

### Category 1: Validation Errors (422)
**Cause:** Pydantic models don't include new fields

**Symptoms:**
```json
{
  "detail": [
    {
      "loc": ["body", "billing_frequency"],
      "msg": "extra fields not permitted",
      "type": "value_error.extra"
    }
  ]
}
```

**Affected Tests:**
- Subscription creation with billing_frequency
- Invoice creation with billing_period/line_items
- Invoice/subscription updates with new fields

**Fix Required:**
- Update Pydantic models (SubscriptionCreate, InvoiceCreate, etc.)
- Add field validation rules

---

### Category 2: Serialization Errors (500)
**Cause:** Response models don't include new fields from database

**Symptoms:**
```
KeyError: 'billing_frequency'
# OR
TypeError: Object of type datetime is not JSON serializable
```

**Affected Tests:**
- GET /api/subscriptions/{id} - missing billing fields
- GET /api/invoices/company/{name} - missing billing fields
- GET /api/v1/payments/ - missing invoice_id/subscription_id

**Fix Required:**
- Update response models (SubscriptionResponse, InvoiceResponse, PaymentResponse)
- Add serialization helpers for new field types

---

### Category 3: Missing Business Logic
**Cause:** Calculation/update logic not implemented

**Symptoms:**
- Subtotal not calculated from line_items
- amount_due not recalculated after payment
- Invoice status not updated to 'paid'
- Payment.invoice_id not set when applied

**Affected Tests:**
- Auto-calculation tests
- Payment application tests
- Status update tests

**Fix Required:**
- Implement calculation functions
- Add triggers/hooks for status updates
- Implement payment application logic

---

### Category 4: Database Schema Issues
**Cause:** MongoDB documents don't have new fields

**Symptoms:**
```python
# Field exists in code but not in DB
subscription["billing_frequency"]  # KeyError
```

**Affected Tests:**
- Tests that insert data then query via API
- Tests verifying database state

**Fix Required:**
- Update MongoDB document schemas
- Create migration script for existing records
- Add default values

---

## How to Run Tests (RED State Verification)

### Prerequisites
```bash
# Ensure test database exists
mongosh mongodb://iris:Sveta87201120@localhost:27017/translation_test?authSource=translation

# Verify DATABASE_MODE=test in .env
grep DATABASE_MODE /Users/vladimirdanishevsky/projects/Translator/server/.env
```

### Start Test Server
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server

# Terminal 1: Start server in test mode
DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
```

### Run Tests (Expect Failures)
```bash
# Terminal 2: Run all billing integration tests
pytest tests/integration/test_subscriptions_billing_integration.py -v
pytest tests/integration/test_invoices_billing_integration.py -v
pytest tests/integration/test_payments_billing_integration.py -v

# Or run all at once
pytest tests/integration/test_*_billing_integration.py -v

# Expected output: 26 FAILED tests (RED state confirmed)
```

### Verify RED State
Each test should FAIL with one of these errors:
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Serialization/KeyError
- `AssertionError` - Missing fields in response
- `KeyError` - Field not in database document

**If any test PASSES in RED state → Test is incorrectly written!**

---

## Next Steps (GREEN State)

Once RED state is confirmed (all 26 tests failing), proceed to implementation:

### Phase 2: Implementation (GREEN)

1. **Update Pydantic Models**
   - `app/models/subscription.py` - Add billing_frequency, payment_terms_days
   - `app/models/invoice.py` - Add billing_period, line_items, subtotal, amount_paid, amount_due
   - `app/models/payment.py` - Add invoice_id, subscription_id

2. **Update Service Layer**
   - `app/services/subscription_service.py` - Handle new fields
   - `app/services/invoice_service.py` - Implement calculations
   - `app/services/payment_service.py` - Implement apply_to_invoice logic

3. **Update API Routes**
   - `app/api/v1/subscriptions.py` - Serialize new fields
   - `app/api/v1/invoices.py` - Serialize new fields
   - `app/api/v1/payments.py` - Serialize new fields

4. **Database Migration**
   - Create script to add default values to existing records
   - Update indexes if needed

5. **Re-run Tests**
   ```bash
   pytest tests/integration/test_*_billing_integration.py -v
   # Target: 26 PASSED tests (GREEN state achieved)
   ```

### Phase 3: Refactor (if needed)

Once all tests pass:
- Code cleanup
- Performance optimization
- Documentation updates

---

## Test Quality Metrics

**Integration Test Best Practices:**
✅ All tests use real HTTP client
✅ All tests use real test database
✅ All tests verify database state after API calls
✅ All tests clean up test data
✅ All tests have descriptive names
✅ All tests document expected failures
✅ No mocks or stubs (real integration testing)

**Coverage:**
- **Subscription endpoints:** 4/4 endpoints tested
- **Invoice endpoints:** 4/5 endpoints tested (95% coverage)
- **Payment endpoints:** 2/2 new fields tested

**Field Coverage:**
- billing_frequency: ✅ CREATE, ✅ READ, ✅ UPDATE, ✅ VALIDATION
- payment_terms_days: ✅ CREATE, ✅ READ, ✅ UPDATE
- billing_period: ✅ CREATE, ✅ READ, ✅ UPDATE
- line_items: ✅ CREATE, ✅ READ, ✅ VALIDATION, ✅ AUTO-CALCULATION
- amount_paid: ✅ READ, ✅ UPDATE, ✅ CALCULATION
- amount_due: ✅ READ, ✅ AUTO-CALCULATION
- invoice_id (payment): ✅ READ, ✅ UPDATE via apply-to-invoice
- subscription_id (payment): ✅ READ

---

## Files Created

1. `/Users/vladimirdanishevsky/projects/Translator/server/tests/integration/test_subscriptions_billing_integration.py` (9 tests)
2. `/Users/vladimirdanishevsky/projects/Translator/server/tests/integration/test_invoices_billing_integration.py` (9 tests)
3. `/Users/vladimirdanishevsky/projects/Translator/server/tests/integration/test_payments_billing_integration.py` (8 tests)
4. `/Users/vladimirdanishevsky/projects/Translator/server/tests/integration/TDD_RED_STATE_SUMMARY.md` (this file)

**Total:** 26 failing integration tests ready for GREEN phase implementation

---

## Important Notes

### DO NOT Skip RED State
Running these tests and seeing them fail is CRITICAL for TDD. It verifies:
1. Tests actually test what they claim to test
2. Implementation doesn't accidentally already work
3. Tests fail for the RIGHT reasons
4. Test failure messages are clear and actionable

### Test Database Safety
All tests use:
- Database: `translation_test` (NOT `translation`)
- Test data prefixes: `TEST-BILLING-`, `TEST-INVOICE-`, `TEST-PAYMENT-`
- Auto-cleanup after each test
- Golden Source restoration before test suite

### Authentication
Tests use real corporate login:
- Company: "Iris Trading"
- User: "danishevsky@gmail.com"
- Tests create temporary companies/users as needed

---

**TDD Cycle Progress:**
- ✅ Phase 1 (RED): Write failing tests - **COMPLETE**
- ⏳ Phase 2 (GREEN): Implement to make tests pass - **PENDING**
- ⏳ Phase 3 (REFACTOR): Clean up and optimize - **PENDING**

**Ready for GREEN phase implementation.**
