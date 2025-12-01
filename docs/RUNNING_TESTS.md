# Running Tests Guide

This guide covers how to run tests for the Translator server, including database configuration and viewing test results.

---

## Prerequisites

1. **Virtual environment activated:**
   ```bash
   cd /Users/vladimirdanishevsky/projects/Translator/server
   source venv/bin/activate
   ```

2. **MongoDB running:**
   ```bash
   # Check if MongoDB is running
   mongosh --eval "db.runCommand({ping:1})"
   ```

---

## Step 1: Configure Database Mode

**CRITICAL:** Tests require `DATABASE_MODE=test` in your `.env` file.

### Check Current Mode
```bash
grep "^DATABASE_MODE" .env
```

### Switch to Test Mode
```bash
# Option 1: Edit manually
nano .env
# Change DATABASE_MODE=production to DATABASE_MODE=test

# Option 2: Use sed (one-liner)
sed -i '' 's/^DATABASE_MODE=production/DATABASE_MODE=test/' .env
```

### Verify Change
```bash
grep "^DATABASE_MODE" .env
# Should show: DATABASE_MODE=test
```

> **Note:** If `DATABASE_MODE` is not `test`, pytest will exit immediately with a safety error.

---

## Step 2: Run Tests

### Option A: Using the Shell Script (Recommended)

The script automatically saves output to a file and displays it on screen.

```bash
# Run ALL tests
./scripts/run_tests.sh

# Run only integration tests
./scripts/run_tests.sh integration

# Run only unit tests
./scripts/run_tests.sh unit

# Run specific test file
./scripts/run_tests.sh tests/integration/test_enterprise_transaction_metadata.py
```

**Output locations:**
- Timestamped file: `test-results/test_run_YYYYMMDD_HHMMSS.log`
- Latest symlink: `test-results/latest.log`

### Option B: Using pytest Directly

```bash
# Run all tests
pytest -v

# Run specific test file
pytest tests/integration/test_enterprise_transaction_metadata.py -v

# Run with coverage
pytest -v --cov=app

# Save output manually with tee
pytest -v 2>&1 | tee test-results/my_test.log
```

---

## Step 3: View Test Results

### In Terminal
```bash
# View latest test output
cat test-results/latest.log

# View with less (scrollable)
less test-results/latest.log

# View only failed tests
grep -A 10 "FAILED" test-results/latest.log

# View test summary
tail -20 test-results/latest.log
```

### In Claude Code

To reference test results in Claude Code terminal:

```bash
# Show full path to latest results
echo "Test results: $(pwd)/test-results/latest.log"

# Read the file directly
cat test-results/latest.log

# Or use the Read tool with absolute path:
# /Users/vladimirdanishevsky/projects/Translator/server/test-results/latest.log
```

**Quick reference paths:**
- Latest results: `/Users/vladimirdanishevsky/projects/Translator/server/test-results/latest.log`
- All results: `/Users/vladimirdanishevsky/projects/Translator/server/test-results/`

---

## Step 4: Switch Back to Production Mode

After testing, switch back to production mode:

```bash
sed -i '' 's/^DATABASE_MODE=test/DATABASE_MODE=production/' .env
grep "^DATABASE_MODE" .env
# Should show: DATABASE_MODE=production
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Switch to test mode | `sed -i '' 's/^DATABASE_MODE=production/DATABASE_MODE=test/' .env` |
| Run all tests | `./scripts/run_tests.sh` |
| Run integration tests | `./scripts/run_tests.sh integration` |
| Run unit tests | `./scripts/run_tests.sh unit` |
| View latest results | `cat test-results/latest.log` |
| Switch to production | `sed -i '' 's/^DATABASE_MODE=test/DATABASE_MODE=production/' .env` |

---

## Troubleshooting

### Error: "Tests cannot run in PRODUCTION mode"
```
FATAL ERROR: Tests cannot run in PRODUCTION mode!
```
**Fix:** Set `DATABASE_MODE=test` in `.env` file.

### Error: MongoDB connection failed
```
Connection refused
```
**Fix:** Start MongoDB service:
```bash
brew services start mongodb-community  # macOS
# or
mongod --dbpath /path/to/data
```

### Tests pass locally but fail in CI
Ensure CI environment has:
- `DATABASE_MODE=test` in environment
- `MONGODB_DATABASE_TEST=translation_test`
- MongoDB test database accessible

---

## Test Output File Format

The test output file includes:
- Timestamp of test run
- Database mode (should be `test`)
- Test path being run
- Full pytest output with verbose mode
- Pass/fail count summary

Example:
```
==============================================
Test Run: Fri Nov 29 13:00:00 PST 2024
Test Path: tests/integration/
DATABASE_MODE: DATABASE_MODE=test
==============================================

================================================================================
Database Mode Verification: PASSED
  DATABASE_MODE: test
  Active Database: translation_test
================================================================================

tests/integration/test_example.py::test_something PASSED
...

============================== 11 passed in 0.09s ==============================
```
