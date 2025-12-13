# Configuration Guide

## Overview

This server uses **STRICT configuration loading** with NO defaults for critical settings.

**Design Philosophy:**
- Server MUST fail to start if required configuration is missing
- Configuration ONLY from `.env` file (no defaults, no guessing)
- Clear error messages indicating what's missing
- Fail fast with helpful error messages

## Quick Start

### 1. Check Current Configuration

```bash
python3 scripts/check_config.py
```

This will show:
- ✅ Fields that are properly configured
- ❌ Fields that are missing
- 📋 Suggested values for missing fields

### 2. Add Missing Fields

Based on the diagnostic output, add missing fields to your `.env` file:

```bash
# Required fields identified as missing:
DATABASE_URL=sqlite:///./translator.db
REDIS_URL=redis://localhost:6379/0
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### 3. Verify Configuration

```bash
# Run diagnostic again - should show all required fields configured
python3 scripts/check_config.py

# Try starting server - should start successfully
uvicorn app.main:app --reload
```

## Required Fields

### Application (1 field)
- `ENVIRONMENT` - Application environment (development/staging/production)

### Security (1 field)
- `SECRET_KEY` - JWT secret key (min 32 chars, use `openssl rand -hex 32`)

### Database (3 fields)
- `DATABASE_URL` - SQLite/PostgreSQL connection URL
- `MONGODB_URI` - MongoDB connection string
- `MONGODB_DATABASE` - MongoDB database name

### Redis (1 field)
- `REDIS_URL` - Redis connection URL

### Payment (1 field)
- `STRIPE_SECRET_KEY` - Stripe API secret key

### Google Drive (2 fields)
- `GOOGLE_DRIVE_CREDENTIALS_PATH` - Path to Google service account JSON
- `GOOGLE_DRIVE_PARENT_FOLDER_ID` - Google Drive folder ID for uploads

### CORS (1 field)
- `CORS_ORIGINS` - Comma-separated list of allowed origins

### Background Tasks (2 fields)
- `CELERY_BROKER_URL` - Celery broker URL (usually Redis)
- `CELERY_RESULT_BACKEND` - Celery result backend URL (usually Redis)

### Email (7 fields)
- `SMTP_HOST` - SMTP server hostname
- `SMTP_PORT` - SMTP server port
- `SMTP_USERNAME` - SMTP username (can be empty string for development)
- `SMTP_PASSWORD` - SMTP password (can be empty string for development)
- `EMAIL_FROM` - Sender email address
- `EMAIL_FROM_NAME` - Sender display name
- `TRANSLATION_SERVICE_COMPANY` - Company name for emails

**Total: 19 required fields**

## Optional Fields

These fields are truly optional and have sensible defaults or auto-detection:

- `GOOGLE_TRANSLATE_API_KEY` - For Google Translate API
- `DEEPL_API_KEY` - For DeepL translation
- `AZURE_TRANSLATOR_KEY` - For Azure Translator
- `STRIPE_WEBHOOK_SECRET` - Auto-set in test mode
- `API_URL` - Auto-inferred from host/port

## Development vs Production

### Development Configuration
```bash
ENVIRONMENT=development
SECRET_KEY=dev-secret-key-change-in-production-min-32-chars
MONGODB_URI=mongodb://localhost:27017
DATABASE_URL=sqlite:///./translator.db
SMTP_HOST=localhost
SMTP_PORT=1025  # For mailhog/mailcatcher
```

### Production Configuration
```bash
ENVIRONMENT=production
SECRET_KEY=<use openssl rand -hex 32>
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net
DATABASE_URL=postgresql://user:pass@host/db
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
```

## Error Messages

### Missing Required Field
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
database_url
  Field required [type=missing, ...]
```

**Solution:** Add the missing field to `.env` file

### Invalid Format
```
ValueError: SMTP_PORT must be between 1 and 65535
```

**Solution:** Fix the value in `.env` file to meet validation requirements

## Migration from Old Configuration

### Before (with defaults)
```python
# Old config.py
secret_key: str = "dev-secret-key-please-change-in-production-min-32-chars"
mongodb_uri: str = "mongodb://localhost:27017"
cors_origins: str = "http://localhost:3000,http://localhost:5173"
```

Server would start even if `.env` was missing these fields.

### After (strict, no defaults)
```python
# New config.py
secret_key: str  # REQUIRED - no default
mongodb_uri: str  # REQUIRED - no default
cors_origins: str  # REQUIRED - no default
```

Server FAILS to start with clear error if `.env` is missing these fields.

## Troubleshooting

### Server Won't Start
1. Run diagnostic: `python3 scripts/check_config.py`
2. Add missing fields shown in output
3. Verify: `python3 scripts/check_config.py` should show all green

### How to Generate SECRET_KEY
```bash
openssl rand -hex 32
```

### How to Find Google Drive Folder ID
1. Open Google Drive folder in browser
2. URL looks like: `https://drive.google.com/drive/folders/1a2b3c4d5e6f...`
3. Folder ID is the part after `/folders/`: `1a2b3c4d5e6f...`

### Development Email Testing
Use mailhog or similar for local SMTP:
```bash
docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog

# In .env:
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USERNAME=
SMTP_PASSWORD=
```

View emails at: http://localhost:8025

## Benefits of Strict Configuration

1. **No Silent Failures**: Server fails immediately if configuration is wrong
2. **Clear Error Messages**: Pydantic shows exactly what's missing
3. **No Surprises**: What's in `.env` is what runs (no hidden defaults)
4. **Environment Consistency**: Same strict rules for dev and production
5. **Easier Debugging**: If server starts, config is valid

## Configuration Checklist

Before deploying:
- [ ] Run `python3 scripts/check_config.py`
- [ ] All required fields show ✅
- [ ] No placeholders in production (localhost, dev-secret-key, etc.)
- [ ] SECRET_KEY is 32+ characters
- [ ] CORS_ORIGINS matches frontend URLs
- [ ] MONGODB_URI points to correct database
- [ ] STRIPE_SECRET_KEY is production key (starts with `sk_live_`)
- [ ] Email settings work (test with forgotten password flow)

## Summary

**Old way:** Server starts with defaults → bugs in production
**New way:** Server fails fast with clear errors → fix before deployment

**Philosophy:** Better to fail loud during development than silent in production.
