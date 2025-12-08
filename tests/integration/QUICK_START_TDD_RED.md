# TDD RED State - Quick Start Guide

## Overview
✅ **31 failing integration tests** created for Enhanced Subscription Billing Schema
📍 Status: **Phase 1 (RED) - Ready for Implementation**

---

## Files Created

```
tests/integration/
├── test_subscriptions_billing_integration.py  (10 tests)
├── test_invoices_billing_integration.py       (10 tests)
├── test_payments_billing_integration.py       (11 tests)
├── TDD_RED_STATE_SUMMARY.md                   (detailed documentation)
└── QUICK_START_TDD_RED.md                     (this file)
```

---

## Run Tests (Verify RED State)

### Step 1: Start Test Server
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server

# Terminal 1
DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
```

### Step 2: Run Tests (Expect Failures)
```bash
# Terminal 2
cd /Users/vladimirdanishevsky/projects/Translator/server

# Run all billing integration tests
pytest tests/integration/test_*_billing_integration.py -v

# Or run individually
pytest tests/integration/test_subscriptions_billing_integration.py -v
pytest tests/integration/test_invoices_billing_integration.py -v
pytest tests/integration/test_payments_billing_integration.py -v
```

### Expected Output
```
========================= 31 failed in X.XXs =========================

FAILED test_subscriptions_billing_integration.py::test_create_subscription_with_billing_frequency_quarterly
FAILED test_subscriptions_billing_integration.py::test_create_subscription_with_billing_frequency_monthly
...
(all 31 tests should FAIL)
```

---

## What the Tests Cover

### Subscriptions (10 tests)
- ✅ Create with `billing_frequency` (monthly/quarterly/annual)
- ✅ Create with `payment_terms_days` (15/30/60)
- ✅ GET returns billing fields
- ✅ UPDATE billing fields
- ✅ Default values applied
- ✅ Validation rejects invalid values

### Invoices (10 tests)
- ✅ Create with `billing_period` {start_date, end_date}
- ✅ Create with `line_items` array
- ✅ Auto-calculate `subtotal` from line_items
- ✅ Auto-calculate `amount_due` = total - amount_paid
- ✅ Status changes: pending → partial → paid
- ✅ Quarterly invoice generation includes line_items
- ✅ Validation on line_items structure

### Payments (11 tests)
- ✅ GET returns `invoice_id` and `subscription_id` fields
- ✅ Apply payment to invoice updates `amount_paid`
- ✅ Invoice `amount_due` recalculated
- ✅ Invoice status changes to 'paid' when fully paid
- ✅ Multiple payments accumulate correctly
- ✅ Overpayment handling
- ✅ Unlinked payments have invoice_id=null

---

## Expected Failure Types

| Error Type | Count | Cause |
|------------|-------|-------|
| 422 Validation Error | ~15 | Pydantic models missing new fields |
| 500 Server Error | ~8 | Serialization errors, KeyError |
| AssertionError | ~8 | Missing fields in response, incorrect calculations |

---

## Next Steps

### Phase 2: GREEN (Implementation)

1. **Update Pydantic Models**
   ```
   app/models/subscription.py
   app/models/invoice.py
   app/models/payment.py
   ```

2. **Update Service Layer**
   ```
   app/services/subscription_service.py
   app/services/invoice_service.py
   app/services/payment_service.py
   ```

3. **Update API Routes**
   ```
   app/api/v1/subscriptions.py
   app/api/v1/invoices.py
   app/api/v1/payments.py
   ```

4. **Re-run Tests → All 31 PASS**

---

## Test Quality Guarantees

✅ **Real integration testing** - No mocks, real server + real DB
✅ **Proper cleanup** - Test data deleted after each test
✅ **Isolated tests** - Each test creates its own test data
✅ **Database safety** - Uses `translation_test`, not production
✅ **Clear failure messages** - Each test documents expected failure
✅ **Full stack coverage** - HTTP → API → Service → Database

---

## Key Fields Being Tested

**Subscriptions:**
- `billing_frequency`: "monthly" | "quarterly" | "annual"
- `payment_terms_days`: integer (15, 30, 60)

**Invoices:**
- `billing_period`: {start_date: string, end_date: string}
- `line_items`: [{description, quantity, unit_price, amount}]
- `subtotal`: float (sum of line_items)
- `amount_paid`: float (sum of applied payments)
- `amount_due`: float (total - amount_paid)

**Payments:**
- `invoice_id`: string | null (links payment to invoice)
- `subscription_id`: string | null (links payment to subscription)

---

## Success Criteria

**RED State (Current):**
- ✅ 31 tests fail with expected errors
- ✅ Failure messages are clear and actionable
- ✅ No test infrastructure errors

**GREEN State (Goal):**
- ⏳ All 31 tests pass
- ⏳ Implementation matches schema design
- ⏳ Database contains all new fields

**REFACTOR State (Future):**
- ⏳ Code is clean and maintainable
- ⏳ No duplicate logic
- ⏳ Performance optimized

---

## Important Notes

🔴 **Do NOT skip RED state verification** - Running failing tests confirms they test the right things

🔴 **Do NOT modify tests to make them pass** - Tests define the requirements

🔴 **Do NOT mock the database** - Integration tests need real database operations

---

**Ready to proceed to GREEN phase (implementation).**

For detailed information, see `TDD_RED_STATE_SUMMARY.md`
