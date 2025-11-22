# Database Backup & Restore System

## Overview

The database backup system provides automatic protection against data loss during E2E testing. Backups are created automatically before Playwright tests run and can be restored manually if needed.

## Automatic Backup (Playwright Tests)

**When:** Automatically before every `npx playwright test` run
**Where:** Backups stored in `server/backups/`
**What:** All critical collections (subscriptions, companies, users, invoices, payments, transactions)

The backup is triggered by `ui/tests/global-setup.ts` before any tests execute.

## Manual Backup Commands

### Create Backup
```bash
cd server
python3 scripts/backup_database.py
```

Output:
```
🔄 Creating backup of database 'translation'...
📁 Backup location: /path/to/server/backups/backup_translation_20251115_183045.json
   ✅ subscriptions: 10 documents
   ✅ companies: 8 documents
   ✅ users: 5 documents
   ...
✅ Backup created successfully!
   Total documents: 250
   File size: 125.43 KB
```

### List Available Backups
```bash
cd server
python3 scripts/backup_database.py --list
```

Output:
```
📂 Available backups in /path/to/server/backups:

1. backup_translation_20251115_183045.json
   Database: translation
   Created: 2025-11-15T18:30:45.123456+00:00
   Documents: 250
   Size: 125.43 KB
   ⭐ LATEST

2. backup_translation_20251115_120530.json
   Database: translation
   Created: 2025-11-15T12:05:30.654321+00:00
   Documents: 248
   Size: 123.87 KB
```

### Restore from Backup
```bash
cd server

# Restore from latest backup
python3 scripts/backup_database.py --restore latest

# Restore from specific backup
python3 scripts/backup_database.py --restore backup_translation_20251115_183045.json
```

**⚠️ WARNING:** Restore will DELETE all existing data and replace it with backup data!

You will be prompted to confirm:
```
⚠️  WARNING: This will DELETE existing data and restore from backup!
   Type 'YES' to confirm restore: YES
```

### Cleanup Old Backups
```bash
cd server

# Keep only the 10 most recent backups (delete older ones)
python3 scripts/backup_database.py --cleanup 10
```

## Backup File Format

Backups are stored as JSON files with this structure:
```json
{
  "database": "translation",
  "timestamp": "2025-11-15T18:30:45.123456+00:00",
  "collections": {
    "subscriptions": [
      { "_id": {"$oid": "..."}, "company_name": "...", ... }
    ],
    "companies": [ ... ],
    "users": [ ... ]
  }
}
```

## Collections Backed Up

1. **subscriptions** - Subscription plans with usage_periods
2. **companies** - Customer company information
3. **users** - Company users and authentication
4. **invoices** - Billing invoices
5. **payments** - Payment transactions
6. **translation_transactions** - Enterprise translation jobs
7. **user_transactions** - Individual user transactions

## Recovery Scenarios

### Scenario 1: Tests Deleted Data

**Problem:** Playwright tests ran and deleted/corrupted data

**Solution:**
```bash
cd server
python3 scripts/backup_database.py --restore latest
```

The most recent backup (created before tests ran) will be restored.

### Scenario 2: Manual Mistake

**Problem:** Accidentally ran a destructive operation

**Solution:**
```bash
cd server
python3 scripts/backup_database.py --list  # Find the backup before the mistake
python3 scripts/backup_database.py --restore backup_translation_YYYYMMDD_HHMMSS.json
```

### Scenario 3: Compare Data Over Time

**Problem:** Need to see what changed between test runs

**Solution:**
```bash
cd server
python3 scripts/backup_database.py --list  # Identify two backups to compare

# Extract and compare manually (backups are JSON)
cat backups/backup_translation_20251115_120000.json | jq '.collections.subscriptions | length'
cat backups/backup_translation_20251115_130000.json | jq '.collections.subscriptions | length'
```

## Backup Best Practices

### For Development
1. **Let automatic backups run** - Don't disable them in global-setup.ts
2. **Keep recent backups** - Run cleanup weekly: `--cleanup 10`
3. **Check backup success** - Verify backup messages in test output

### For Production Testing
1. **Always use test database** - Set `MONGODB_URI=mongodb://localhost:27017/translation_test`
2. **Backup before major changes** - Run manual backup before risky operations
3. **Verify restore works** - Practice restoration before you need it

### Storage Management
- **Backup size:** ~100-200 KB per backup (varies with data)
- **Disk usage:** 10 backups = ~1-2 MB
- **Retention:** Keep last 10 backups (automatic cleanup recommended)

## Troubleshooting

### Backup Script Not Found
```
⚠️  Backup script not found - skipping backup
   Expected: /path/to/server/scripts/backup_database.py
```

**Solution:** Verify the file exists in `server/scripts/backup_database.py`

### Python Not Found
```
❌ Database backup failed: command not found: python3
```

**Solution:**
```bash
cd server
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
.\venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

### MongoDB Connection Failed
```
❌ Database backup failed: Could not connect to MongoDB
```

**Solution:** Ensure MongoDB is running:
```bash
# Check if MongoDB is running
docker ps | grep mongo
# or
brew services list | grep mongodb-community
```

### Permission Denied
```
❌ Database backup failed: Permission denied
```

**Solution:** Check backup directory permissions:
```bash
chmod 755 server/backups
```

## Advanced Usage

### Backup Specific Database
```bash
python3 scripts/backup_database.py --db translation_test
```

### Script in CI/CD Pipeline
```yaml
# .github/workflows/test.yml
- name: Backup database before tests
  run: |
    cd server
    python3 scripts/backup_database.py

- name: Run tests
  run: npm run test:e2e

- name: Restore on failure
  if: failure()
  run: |
    cd server
    echo "YES" | python3 scripts/backup_database.py --restore latest
```

## Related Documentation

- **Test Setup:** `ui/tests/global-setup.ts` - Automatic backup integration
- **Data Restoration:** `server/restore_usage_periods_fixed.py` - Restore specific fields
- **Test Helpers:** `server/app/routers/test_helpers.py` - Test data management

## Support

If you encounter issues with the backup system:
1. Check MongoDB connection
2. Verify Python virtual environment is activated
3. Check disk space in `server/backups/`
4. Review test output for backup error messages
