# Iris Admins Migration: Add user_email Field

## Overview

This migration adds the `user_email` field to the iris-admins collection and creates a unique index on it. It also inserts a new admin user with proper bcrypt password hashing.

## Migration Details

**Date:** 2025-10-30
**Collection:** iris-admins
**Database:** translation

### Schema Changes

#### Before:
```javascript
{
  _id: ObjectId,
  user_name: String,
  password: String (bcrypt hashed),
  login_date: Date,
  created_at: Date,
  updated_at: Date
}
```

#### After:
```javascript
{
  _id: ObjectId,
  user_name: String,
  user_email: String (UNIQUE),  // NEW FIELD
  password: String (bcrypt hashed),
  login_date: Date,
  created_at: Date,
  updated_at: Date
}
```

### Migration Steps

1. **Add user_email to existing admin**
   - Update iris-admin record (ID: 68f3a1c1e44710d091e002e5)
   - Add user_email: "admin@iris-translation.com"

2. **Create unique index**
   - Index name: user_email_unique
   - Field: user_email (ascending)
   - Constraint: UNIQUE

3. **Insert new admin user**
   - user_name: "Vladimir Danishevsky"
   - user_email: "danishevsky@gmail.com"
   - password: bcrypt hashed with 12 rounds

4. **Verify migration**
   - Confirm user_email field exists on existing record
   - Confirm new admin user created
   - Confirm unique index created

## Usage

### Option 1: Python Script (Recommended)

```bash
# From server directory
cd /Users/vladimirdanishevsky/projects/Translator/server

# Run migration
python scripts/migrations/migrate_iris_admins_add_email.py
```

### Option 2: MongoDB Shell Commands

```javascript
// Connect to MongoDB
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation"

// Step 1: Add user_email to existing admin
db.getCollection("iris-admins").updateOne(
  { _id: ObjectId("68f3a1c1e44710d091e002e5") },
  {
    $set: {
      user_email: "admin@iris-translation.com",
      updated_at: new Date()
    }
  }
)

// Step 2: Create unique index
db.getCollection("iris-admins").createIndex(
  { user_email: 1 },
  {
    unique: true,
    name: "user_email_unique",
    background: true
  }
)

// Step 3: Insert new admin user (password pre-hashed)
db.getCollection("iris-admins").insertOne({
  user_name: "Vladimir Danishevsky",
  user_email: "danishevsky@gmail.com",
  password: "$2b$12$bwP5j/GqK9WvXYlZ8kH0QuLxJj5vN7P0R5Y0mxE1yLqHc8K0vP7xO",
  login_date: new Date(),
  created_at: new Date(),
  updated_at: new Date()
})

// Verify migration
db.getCollection("iris-admins").find().pretty()
db.getCollection("iris-admins").getIndexes()
```

## Safety Features

### Pre-Migration Checks
- ✓ Validates collection exists
- ✓ Validates existing admin record exists
- ✓ Checks if migration already run
- ✓ Verifies MongoDB connection

### Idempotency
- ✓ Safe to run multiple times
- ✓ Skips steps if already completed
- ✓ No data loss on re-run

### Validation
- ✓ Password hash verification after creation
- ✓ Post-migration verification of all changes
- ✓ Comprehensive logging of all operations

## Rollback

If you need to rollback this migration:

```javascript
// Remove user_email from existing admin
db.getCollection("iris-admins").updateOne(
  { _id: ObjectId("68f3a1c1e44710d091e002e5") },
  {
    $unset: { user_email: "" },
    $set: { updated_at: new Date() }
  }
)

// Delete new admin user
db.getCollection("iris-admins").deleteOne({
  user_email: "danishevsky@gmail.com"
})

// Drop unique index
db.getCollection("iris-admins").dropIndex("user_email_unique")
```

**WARNING:** Only perform rollback if absolutely necessary. This will remove the new admin user and email functionality.

## Verification

After migration, verify the changes:

```bash
# Check collection structure
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" --eval "
  db.getCollection('iris-admins').find().forEach(function(doc) {
    print('User: ' + doc.user_name);
    print('Email: ' + doc.user_email);
    print('Has Password: ' + (doc.password ? 'Yes' : 'No'));
    print('---');
  });
"

# Check indexes
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" --eval "
  db.getCollection('iris-admins').getIndexes().forEach(function(idx) {
    print(idx.name + ': ' + JSON.stringify(idx.key));
  });
"
```

## Expected Output

```
==================================================================================
IRIS-ADMINS MIGRATION: Add user_email field
==================================================================================
Target database: translation
Target collection: iris-admins

Connecting to MongoDB...
✓ Successfully connected to MongoDB database: translation

STEP 0: Checking preconditions...
--------------------------------------------------------------------------------
✓ Collection 'iris-admins' exists
✓ Existing admin record found:
  - user_name: iris-admin
  - _id: 68f3a1c1e44710d091e002e5
✓ Total admin users in collection: 1

STEP 1: Add user_email to existing admin record
--------------------------------------------------------------------------------
✓ Successfully added user_email field
  - user_name: iris-admin
  - user_email: admin@iris-translation.com
  - updated_at: 2025-10-30T...

STEP 2: Create unique index on user_email
--------------------------------------------------------------------------------
✓ Successfully created unique index on user_email
  Total indexes: 3
  - _id_: {'_id': 1}
  - user_name_unique: {'user_name': 1}
  - user_email_unique: {'user_email': 1}

STEP 3: Insert new admin user
--------------------------------------------------------------------------------
Hashing password with bcrypt (rounds: 12)...
✓ Password hashed successfully
✓ Successfully inserted new admin user
  - user_name: Vladimir Danishevsky
  - user_email: danishevsky@gmail.com
  - _id: ...
  - password_hash: $2b$12$...
  - password verification: PASSED ✓

STEP 4: Verify migration
--------------------------------------------------------------------------------
✓ Existing admin has user_email field:
  - user_name: iris-admin
  - user_email: admin@iris-translation.com
✓ New admin user exists:
  - user_name: Vladimir Danishevsky
  - user_email: danishevsky@gmail.com
✓ Unique index on user_email exists
✓ Total admin users: 2

==================================================================================
MIGRATION SUMMARY
==================================================================================
Status: SUCCESS ✓

Started at: 2025-10-30T...
Completed at: 2025-10-30T...

Steps completed:
  ✓ step1_add_email
  ✓ step2_create_index
  ✓ step3_insert_admin

==================================================================================
```

## Security Notes

1. **Password Hashing:**
   - All passwords hashed with bcrypt
   - Salt rounds: 12 (industry standard)
   - Plain text passwords never stored

2. **Unique Constraint:**
   - user_email field has unique index
   - Prevents duplicate email addresses
   - Enforced at database level

3. **Authentication:**
   - Compatible with existing auth_service.py bcrypt implementation
   - Password verification tested during migration

## Database Impact

- **Documents Modified:** 1 (existing iris-admin)
- **Documents Inserted:** 1 (new admin user)
- **Indexes Created:** 1 (user_email_unique)
- **Collection Size Impact:** Minimal (~200 bytes per document)
- **Downtime Required:** None (online migration)

## Compatibility

- **MongoDB Version:** 4.0+
- **Python Version:** 3.11+
- **Dependencies:** pymongo, bcrypt
- **Backend Impact:** None (backward compatible)

## Support

For issues or questions:
1. Check migration logs for error messages
2. Verify MongoDB connection string
3. Ensure required Python packages installed
4. Review database permissions

## Related Files

- Migration script: `/scripts/migrations/migrate_iris_admins_add_email.py`
- Auth service: `/app/services/auth_service.py`
- Admin user script: `/scripts/utils/create_admin_user.py`
- Database config: `/app/database/mongodb.py`
