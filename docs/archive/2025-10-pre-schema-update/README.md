# Archived Documentation (Pre-Schema Update)

**Archive Date:** October 24, 2025
**Reason:** Superseded by comprehensive schema update documentation

This directory contains documentation from before the payments and user_transactions schema updates.

## Archived Files

### Schema Documentation
- MONGODB_SCHEMAS.md - Old MongoDB schemas (superseded by PAYMENT_SCHEMA_UPDATE_COMPLETE.md and USER_TRANSACTIONS_SCHEMA_UPDATE_COMPLETE.md)
- SQUARE_PAYMENT_IMPLEMENTATION_SUMMARY.md - Old Square payment implementation (superseded)

### API Documentation
- API_SCHEMA_FIX_SUMMARY.md - Interim fix documentation
- USER_TRANSACTIONS_API_QUICK_REFERENCE.md - Old quick reference
- VERIFICATION_REPORT.md - Old verification report

### Utility Documentation
- README_USER_TRANSACTIONS.md - Old user transaction helper docs (missing translated_url field)
- USER_TRANSACTION_HELPER.md - Old helper documentation
- USER_TRANSACTION_QUICK_REF.md - Old quick reference
- TEST_USER_TRANSACTIONS_README.md - Old test documentation

## Current Documentation

For current documentation, see:
- `/PAYMENT_SCHEMA_UPDATE_COMPLETE.md` - Payments collection schema
- `/USER_TRANSACTIONS_SCHEMA_UPDATE_COMPLETE.md` - User transactions collection schema
- `/SWAGGER_UPDATE_SUMMARY.md` - Swagger documentation updates
- `/SWAGGER_DOCUMENTATION_VERIFICATION_REPORT.md` - API verification report

## Key Changes Since Archive

1. **translated_url field added** to user_transactions collection
2. **Simplified payments schema** from 30+ fields to 12 fields
3. **Fixed refund schemas** - payments use "amount", user_transactions use "amount_cents"
4. **Updated Swagger documentation** to match database schemas exactly
5. **Removed obsolete fields** - subscription_id, user_id, company fields from user_transactions
