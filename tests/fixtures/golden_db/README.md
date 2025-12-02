# Golden Source Database Fixtures

This directory contains JSON dumps of the production MongoDB database collections, serving as the "Golden Source" for test database restoration.

## Purpose

- **Golden Source**: Represents a known-good state of the production database
- **Test Isolation**: Tests can restore to this clean state before each test run
- **Data Preservation**: No need to manually create test data
- **Consistency**: All tests run against the same baseline data

## Files

Each `.json` file corresponds to a MongoDB collection:
- `users.json` - User accounts
- `companies.json` - Company records
- `subscriptions.json` - Subscription data
- `invoices.json` - Invoice records
- `payments.json` - Payment transactions
- `translation_transactions.json` - Translation transactions
- `user_transactions.json` - User transaction records
- etc.

## Usage

### Dump Production Database to Golden Source

```bash
cd server
python3 scripts/dump_golden_db.py
python3 scripts/dump_golden_db.py --verbose  # With detailed output
```

This will:
1. Connect to the production `translation` database
2. Export all collections to JSON files in this directory
3. Handle BSON types (ObjectId, datetime, Decimal128) properly
4. Skip empty collections

### Restore Test Database from Golden Source

```bash
cd server
python3 scripts/restore_test_db.py
python3 scripts/restore_test_db.py --verbose  # With detailed output
python3 scripts/restore_test_db.py --skip-indexes  # Skip index recreation
```

This will:
1. Connect to the test `translation_test` database
2. **Drop all existing collections** (safety check: only works on databases with "test" in name)
3. Restore all collections from JSON files in this directory
4. Recreate indexes from production database
5. Verify document counts match

## Workflow

### Initial Setup
```bash
# 1. Dump production database to create golden source
python3 scripts/dump_golden_db.py

# 2. Restore to test database
python3 scripts/restore_test_db.py
```

### Before Test Runs
```bash
# Reset test database to clean state
python3 scripts/restore_test_db.py
```

### After Production Changes
```bash
# Re-dump golden source after schema changes or important data updates
python3 scripts/dump_golden_db.py
```

## Safety Features

### dump_golden_db.py
- ✅ Only reads from production database (no modifications)
- ✅ Overwrites existing JSON files (intentional)
- ✅ Handles all BSON types correctly
- ✅ No sensitive data sanitization needed (test environment)

### restore_test_db.py
- ✅ **Only operates on databases with "test" in the name**
- ✅ Verification check: Compares restored counts with source
- ✅ Drops all collections before restore (clean slate)
- ✅ Recreates indexes from production schema

## Notes

- **No Privacy Concerns**: This is a test environment, no real customer data
- **Version Control**: These JSON files can be committed to git
- **Size**: Monitor file sizes; large collections may need compression
- **Indexes**: Automatically recreated from production database schema
- **BSON Types**: ObjectId, datetime, Decimal128 are properly serialized/deserialized

## Troubleshooting

### "No JSON files found"
Run `dump_golden_db.py` first to create the golden source.

### "Database name does not contain 'test'"
Safety check failed. `restore_test_db.py` only works on test databases.

### Index creation errors
Use `--skip-indexes` flag if indexes cause issues, then create them manually.

### Count mismatch after restore
Check JSON files for corruption or re-run `dump_golden_db.py`.
