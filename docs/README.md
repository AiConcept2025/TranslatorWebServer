# Server Documentation

This directory contains documentation and guides for the Translation Service backend.

## Directory Structure

```
docs/
├── README.md                    # This file
├── ADMIN_SETUP.md              # Guide for setting up admin users
├── MONGODB_INTEGRATION.md      # MongoDB integration guide
├── MONGODB_SETUP_COMPLETE.md   # MongoDB setup completion reference
├── INDIVIDUAL_LOGIN_ENDPOINT.md # Individual user login endpoint documentation
├── UI_API_ENDPOINTS.md         # UI/API contract documentation
└── archive/                     # Historical documentation and debug notes
    ├── AUTH_IMPLEMENTATION_SUMMARY.md
    ├── AUTH_TESTING.md
    ├── CLIENT_API_WORKFLOW.md
    ├── CODE_CHANGES.md
    ├── DEBUG_GUIDE.md
    ├── DEBUG_SSL_CONNECTION_POOL_EXHAUSTION.md
    ├── FIX_SUMMARY.md
    ├── FIXES_APPLIED.md
    ├── ISSUES_FIXED.md
    ├── JWT_AUTHENTICATION_FIX.md
    ├── LOG_ANALYSIS.md
    ├── LOGGING_EXAMPLE.md
    ├── MONGODB_TEST_SUMMARY.md
    ├── PAYMENT_API_SUMMARY.md
    ├── QUICK_START_TRANSLATIONS.md
    ├── ROOT_CAUSE_ANALYSIS.md
    ├── SSL_FIX_IMPLEMENTATION.md
    ├── SUBSCRIPTION_IMPLEMENTATION_SUMMARY.md
    ├── USER_COLLECTION_README.md
    └── USER_TRANSLATIONS_REPORT.md
```

## Quick Reference

### Essential Documentation (Root Directory)
- `../CLAUDE.md` - Project instructions for Claude Code
- `../API_REFERENCE.md` - API endpoint reference
- `../BACKEND_QUICK_START.md` - Getting started guide

### Current Documentation (docs/)
- **Setup Guides**: ADMIN_SETUP.md, MONGODB_*.md
- **API Documentation**: UI_API_ENDPOINTS.md, INDIVIDUAL_LOGIN_ENDPOINT.md

### Archived Documentation (docs/archive/)
Contains historical debugging notes, fix summaries, and implementation logs.
These documents were useful during development but are now archived for reference.

## See Also
- `../scripts/` - Utility and setup scripts
- `../tests/` - Test suites and manual test scripts
