# MongoDB Referential Integrity Scripts

Quick reference guide for database integrity management scripts.

## Quick Start

```bash
# 1. Check current integrity status
python scripts/verify_data_integrity.py

# 2. If issues found, apply migration
python scripts/add_referential_integrity.py --dry-run  # Preview
python scripts/add_referential_integrity.py            # Apply

# 3. Verify success
python scripts/verify_data_integrity.py --verbose
```

## Scripts Overview

### 1. `add_referential_integrity.py`

**Purpose:** Apply database-level referential integrity (one-time migration)

**Features:**
- JSON Schema validation for companies and subscriptions
- Index optimization (fix unique constraint issue)
- Data integrity verification before applying
- Dry-run mode for safe preview

**Usage:**

```bash
# Dry run (recommended first)
python scripts/add_referential_integrity.py --dry-run

# Apply to production
python scripts/add_referential_integrity.py

# Apply to test database
python scripts/add_referential_integrity.py --database translation_test

# Force apply (skip confirmations)
python scripts/add_referential_integrity.py --force

# Help
python scripts/add_referential_integrity.py --help
```

**What It Does:**
1. ✅ Verifies all subscriptions reference existing companies
2. ✅ Fixes incorrect unique constraint on `subscriptions.company_name`
3. ✅ Applies JSON Schema validation to both collections
4. ✅ Creates/updates indexes for performance
5. ❌ **Never deletes data** (safe operation)

**Exit Codes:**
- `0`: Success
- `1`: Failure or data integrity issues found

---

### 2. `verify_data_integrity.py`

**Purpose:** Check data integrity and optionally fix issues (ongoing monitoring)

**Features:**
- Detect orphaned subscriptions
- Verify schema validation configuration
- Check index configuration
- Generate JSON reports
- Auto-fix by creating missing companies

**Usage:**

```bash
# Check integrity (read-only)
python scripts/verify_data_integrity.py

# Check and fix issues
python scripts/verify_data_integrity.py --fix

# Verbose output
python scripts/verify_data_integrity.py --verbose

# Export JSON report
python scripts/verify_data_integrity.py --export report.json

# Check test database
python scripts/verify_data_integrity.py --database translation_test

# Combine flags
python scripts/verify_data_integrity.py --fix --verbose --export report.json

# Help
python scripts/verify_data_integrity.py --help
```

**What It Checks:**
1. ✅ Referential integrity (subscriptions → companies)
2. ✅ Schema validation enabled and correct
3. ✅ Index configuration and uniqueness constraints
4. ✅ Missing companies and orphaned subscriptions

**What `--fix` Does:**
- ✅ Creates missing companies (with `created_at` and `updated_at`)
- ❌ **Never deletes subscriptions** (safe operation)

**Exit Codes:**
- `0`: All checks passed
- `1`: Integrity issues found

**Report Format (JSON):**

```json
{
  "timestamp": "2025-11-15T12:00:00",
  "database": "translation",
  "summary": {
    "total_companies": 5,
    "total_subscriptions": 8,
    "missing_companies": 0,
    "orphaned_subscriptions": 0,
    "validation_errors": 0
  },
  "missing_companies": [],
  "orphaned_subscriptions": [],
  "validation_errors": [],
  "passed": true
}
```

---

## Common Workflows

### Initial Setup (First Time)

```bash
# 1. Preview changes
python scripts/add_referential_integrity.py --dry-run

# 2. Review output, then apply
python scripts/add_referential_integrity.py

# 3. Verify success
python scripts/verify_data_integrity.py
```

### Daily Health Check

```bash
# Quick check
python scripts/verify_data_integrity.py

# Or with report export
python scripts/verify_data_integrity.py --export "reports/$(date +%Y%m%d)_integrity.json"
```

### Troubleshooting Data Issues

```bash
# 1. Detailed diagnosis
python scripts/verify_data_integrity.py --verbose

# 2. If orphaned subscriptions found, fix by creating missing companies
python scripts/verify_data_integrity.py --fix --verbose

# 3. Verify fix worked
python scripts/verify_data_integrity.py
```

### CI/CD Integration

```bash
# Pre-deployment check
python scripts/verify_data_integrity.py || { echo "Integrity check failed!"; exit 1; }

# Or export report for artifacts
python scripts/verify_data_integrity.py --export ci_report.json
```

---

## Automation Examples

### Cron Job (Daily Check)

```bash
# /etc/cron.d/db-integrity-check
0 2 * * * cd /app && python scripts/verify_data_integrity.py --export /var/log/integrity_$(date +\%Y\%m\%d).json && [ $? -eq 0 ] || echo "DB integrity issues" | mail -s "Alert" ops@example.com
```

### Systemd Timer (Weekly Check)

**Service:** `/etc/systemd/system/db-integrity-check.service`
```ini
[Unit]
Description=Database Integrity Check

[Service]
Type=oneshot
WorkingDirectory=/app
ExecStart=/usr/bin/python3 scripts/verify_data_integrity.py --verbose
User=app
Group=app
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Timer:** `/etc/systemd/system/db-integrity-check.timer`
```ini
[Unit]
Description=Run DB Integrity Check Weekly

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# Enable and start
sudo systemctl enable db-integrity-check.timer
sudo systemctl start db-integrity-check.timer
```

### Docker/Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: db-integrity-check
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: integrity-check
            image: translation-service:latest
            command:
            - python
            - scripts/verify_data_integrity.py
            - --export
            - /reports/integrity_$(date +%Y%m%d).json
            env:
            - name: MONGODB_URI
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: mongodb-uri
            volumeMounts:
            - name: reports
              mountPath: /reports
          restartPolicy: OnFailure
          volumes:
          - name: reports
            persistentVolumeClaim:
              claimName: integrity-reports
```

---

## Monitoring Integration

### CloudWatch Logs (AWS)

```bash
#!/bin/bash
# scripts/integrity_check_cloudwatch.sh

REPORT_FILE="/tmp/integrity_report_$(date +%Y%m%d).json"

python scripts/verify_data_integrity.py --export "$REPORT_FILE"
EXIT_CODE=$?

# Parse report
ORPHANED=$(jq '.summary.orphaned_subscriptions' "$REPORT_FILE")
MISSING=$(jq '.summary.missing_companies' "$REPORT_FILE")

# Send metrics to CloudWatch
aws cloudwatch put-metric-data \
  --namespace TranslationService \
  --metric-name OrphanedSubscriptions \
  --value "$ORPHANED" \
  --unit Count

aws cloudwatch put-metric-data \
  --namespace TranslationService \
  --metric-name MissingCompanies \
  --value "$MISSING" \
  --unit Count

# Alert if issues found
if [ $EXIT_CODE -ne 0 ]; then
    aws sns publish \
      --topic-arn "arn:aws:sns:us-east-1:123456789:db-alerts" \
      --subject "DB Integrity Alert" \
      --message "Database integrity issues detected. Orphaned: $ORPHANED, Missing: $MISSING"
fi

exit $EXIT_CODE
```

### DataDog (Python)

```python
# scripts/integrity_check_datadog.py
import asyncio
from datadog import initialize, statsd
from verify_data_integrity import DataIntegrityVerifier

async def main():
    # Initialize DataDog
    initialize(api_key='YOUR_API_KEY', app_key='YOUR_APP_KEY')

    # Run verification
    verifier = DataIntegrityVerifier()
    await verifier.connect()
    passed, report = await verifier.run_verification()
    await verifier.disconnect()

    # Send metrics
    statsd.gauge('db.orphaned_subscriptions', report['summary']['orphaned_subscriptions'])
    statsd.gauge('db.missing_companies', report['summary']['missing_companies'])

    # Send event if issues found
    if not passed:
        statsd.event(
            'Database Integrity Issues',
            f"Orphaned: {report['summary']['orphaned_subscriptions']}, "
            f"Missing: {report['summary']['missing_companies']}",
            alert_type='error',
            tags=['database', 'integrity']
        )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Troubleshooting

### Issue: Migration fails with "collection validation failed"

**Cause:** Existing data violates schema rules

**Solution:**
```bash
# 1. Find problematic records
python scripts/verify_data_integrity.py --verbose

# 2. Fix data issues
python scripts/verify_data_integrity.py --fix

# 3. Retry migration
python scripts/add_referential_integrity.py
```

---

### Issue: "company_name_unique" index prevents multiple subscriptions

**Cause:** Incorrect unique constraint on subscriptions.company_name

**Solution:**
```bash
# Migration script automatically fixes this
python scripts/add_referential_integrity.py
```

**Manual Fix:**
```javascript
// MongoDB shell
db.subscriptions.dropIndex("company_name_unique")
db.subscriptions.createIndex({company_name: 1}, {name: "company_name_idx", unique: false})
```

---

### Issue: Orphaned subscriptions detected

**Cause:** Subscriptions reference companies that don't exist

**Solution:**
```bash
# Automatically create missing companies
python scripts/verify_data_integrity.py --fix --verbose

# Or manually investigate
python scripts/verify_data_integrity.py --verbose --export orphans.json
```

---

### Issue: Schema validation prevents writes

**Cause:** Application trying to insert invalid data

**Check Validation Errors:**
```python
from pymongo.errors import WriteError

try:
    await db.subscriptions.insert_one(data)
except WriteError as e:
    print(f"Validation error: {e.details}")
```

**Temporary Disable (NOT RECOMMENDED):**
```javascript
// MongoDB shell - emergency only
db.runCommand({collMod: "subscriptions", validationLevel: "off"})
```

---

## Safety Guarantees

### What These Scripts NEVER Do

❌ Delete production data from collections
❌ Modify existing subscription or company records
❌ Drop collections
❌ Bypass critical confirmations (without `--force`)

### What These Scripts DO

✅ Add schema validation (prevents future invalid data)
✅ Create/update indexes (improves performance)
✅ Create missing companies (only with `--fix` flag)
✅ Report integrity issues (always safe)
✅ Provide dry-run mode (preview changes)

---

## Environment Variables

Both scripts support these environment variables:

```bash
# MongoDB connection
export MONGODB_URI="mongodb://localhost:27017"

# Default database (can be overridden with --database flag)
export MONGODB_DEFAULT_DB="translation"
```

---

## Exit Codes Summary

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| `0` | Success, all checks passed | No action needed |
| `1` | Integrity issues found OR migration failed | Review output, fix issues |

**CI/CD Integration:**
```bash
# Fail pipeline if integrity issues found
python scripts/verify_data_integrity.py || exit 1

# Warning only (don't fail pipeline)
python scripts/verify_data_integrity.py || echo "Warning: integrity issues"
```

---

## Best Practices

### 1. Always Dry-Run First

```bash
python scripts/add_referential_integrity.py --dry-run
```

### 2. Regular Health Checks

Schedule daily or weekly integrity checks:
```bash
0 2 * * * python scripts/verify_data_integrity.py
```

### 3. Keep Reports for Audit Trail

```bash
python scripts/verify_data_integrity.py --export "reports/$(date +%Y%m%d_%H%M%S).json"
```

### 4. Test on Non-Production First

```bash
python scripts/add_referential_integrity.py --database translation_test
python scripts/verify_data_integrity.py --database translation_test
```

### 5. Monitor Script Execution

```bash
# Log output
python scripts/verify_data_integrity.py 2>&1 | tee -a /var/log/integrity_checks.log
```

---

## Support

**Documentation:** See `docs/REFERENTIAL_INTEGRITY.md` for detailed design and architecture

**Common Issues:** Check troubleshooting section above

**Questions:** database-admin@example.com

---

## Version History

- **v1.0.0** (2025-11-15): Initial release
  - JSON Schema validation
  - Index optimization
  - Verification and migration scripts
