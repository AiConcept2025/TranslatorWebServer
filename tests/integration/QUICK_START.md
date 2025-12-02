# Quick Start Guide - Real Integration Tests

## 🚀 Quick Run (3 Steps)

### Step 1: Start the Server
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
uvicorn app.main:app --reload --port 8000
```

Keep this terminal open!

### Step 2: Validate Setup (NEW TERMINAL)
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
python3 tests/integration/validate_test_setup.py
```

Expected output:
```
✅ ALL CHECKS PASSED - Ready to run real integration tests!
```

### Step 3: Run Tests
```bash
pytest tests/integration/test_confirm_square_payment.py -v
```

Expected output:
```
================================ 8 passed in 45.32s ==================================
```

---

## 🎯 What Gets Tested

These tests verify the `/api/transactions/confirm` endpoint with:
- ✅ Real MongoDB operations
- ✅ Real JWT authentication
- ✅ Real Google Drive file operations
- ✅ Real HTTP requests to localhost:8000

---

## 📋 Prerequisites Checklist

Before running tests, ensure:

- [ ] Server running on `http://localhost:8000`
- [ ] MongoDB running on `localhost:27017`
- [ ] Google Drive credentials configured (`service-account-key.json`)
- [ ] Python dependencies installed (`pip install -r requirements.txt`)

**Quick Check:**
```bash
python3 tests/integration/validate_test_setup.py
```

---

## 🧪 Run Individual Tests

```bash
# Test 1: Valid success request
pytest tests/integration/test_confirm_square_payment.py::test_1_valid_success_request -v -s

# Test 2: Valid failure request
pytest tests/integration/test_confirm_square_payment.py::test_2_valid_failure_request -v -s

# Test 3a: Missing stripe_checkout_session_id
pytest tests/integration/test_confirm_square_payment.py::test_3a_missing_stripe_checkout_session_id -v -s

# Test 3b: Missing status field
pytest tests/integration/test_confirm_square_payment.py::test_3b_missing_status_field -v -s

# Test 4: Transaction creation
pytest tests/integration/test_confirm_square_payment.py::test_4_transaction_creation_on_success -v -s

# Test 5: No transaction on failure
pytest tests/integration/test_confirm_square_payment.py::test_5_no_transaction_on_failure -v -s

# Test 6a: Success response format
pytest tests/integration/test_confirm_square_payment.py::test_6a_success_response_format -v -s

# Test 6b: Failure response format
pytest tests/integration/test_confirm_square_payment.py::test_6b_failure_response_format -v -s
```

---

## 🛠️ Troubleshooting

### Server Not Running

**Error:**
```
Connection refused on http://localhost:8000
```

**Fix:**
```bash
# Terminal 1
cd /Users/vladimirdanishevsky/projects/Translator/server
uvicorn app.main:app --reload --port 8000
```

### MongoDB Not Running

**Error:**
```
ServerSelectionTimeoutError: localhost:27017
```

**Fix:**
```bash
# Check if running
mongosh --eval "db.version()"

# Start MongoDB
brew services start mongodb-community
```

### Google Drive Credentials Missing

**Error:**
```
GoogleDriveAuthenticationError: credentials file not found
```

**Fix:**
```bash
# Check file exists
ls -la service-account-key.json

# Check .env
cat .env | grep GOOGLE_DRIVE_ENABLED
# Should show: GOOGLE_DRIVE_ENABLED=true
```

### Tests Timeout

**Error:**
```
httpx.ReadTimeout
```

**Fix:**
- Increase timeout in test code (already set to 30s)
- Check if server is responding: `curl http://localhost:8000/health`

---

## 🧹 Data Cleanup

Tests automatically clean up:
- ✅ Test transactions (TEST- prefix)
- ✅ Test users (test-confirm@example.com)
- ✅ Test files in Google Drive (TEST_ prefix)

**NEVER deletes production data:**
- ❌ Real customer transactions
- ❌ Real user accounts
- ❌ Real files

---

## 📊 Expected Results

### All Tests Pass
```
tests/integration/test_confirm_square_payment.py::test_1_valid_success_request PASSED [ 12%]
tests/integration/test_confirm_square_payment.py::test_2_valid_failure_request PASSED [ 25%]
tests/integration/test_confirm_square_payment.py::test_3a_missing_stripe_checkout_session_id PASSED [ 37%]
tests/integration/test_confirm_square_payment.py::test_3b_missing_status_field PASSED [ 50%]
tests/integration/test_confirm_square_payment.py::test_4_transaction_creation_on_success PASSED [ 62%]
tests/integration/test_confirm_square_payment.py::test_5_no_transaction_on_failure PASSED [ 75%]
tests/integration/test_confirm_square_payment.py::test_6a_success_response_format PASSED [ 87%]
tests/integration/test_confirm_square_payment.py::test_6b_failure_response_format PASSED [100%]

================================ 8 passed in 45.32s ==================================
```

### Execution Time
- Single test: ~5-10 seconds
- Full suite: ~45-60 seconds

This is **normal** for real integration tests!

---

## 📚 More Information

- **Full Documentation:** `README_REAL_TESTS.md`
- **Implementation Details:** `IMPLEMENTATION_SUMMARY.md`
- **Setup Validation:** `validate_test_setup.py`

---

## 🎉 Success Checklist

After running tests, verify:

- [ ] All 8 tests passed
- [ ] No TEST- transactions in MongoDB
  ```bash
  mongosh translation --eval 'db.user_transactions.find({stripe_checkout_session_id: /^TEST-/}).count()'
  ```
  Should show: `0`

- [ ] No TEST_ files in Google Drive
- [ ] Server still running (no crashes)

**You're done!** 🚀
