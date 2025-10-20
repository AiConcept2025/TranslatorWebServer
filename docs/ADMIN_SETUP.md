# Admin User Setup Documentation

## Overview

This document describes the MongoDB `iris-admins` collection and the admin user management system for the Translation Service.

## Collection Details

### Database Information
- **Database**: `translation`
- **Collection**: `iris-admins`
- **Connection**: `mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation`

### Schema

The `iris-admins` collection contains admin user documents with the following structure:

```javascript
{
  _id: ObjectId,           // MongoDB auto-generated ID
  user_name: String,       // Admin username (unique)
  password: String,        // Bcrypt hashed password (NOT plain text)
  login_date: Date,        // Last login timestamp
  created_at: Date,        // Account creation timestamp
  updated_at: Date         // Last update timestamp
}
```

### Indexes

The collection has the following indexes for performance and data integrity:

1. **Primary Index**: `_id` (default MongoDB index)
2. **Unique Index**: `user_name_unique` on `user_name` field
   - Ensures no duplicate usernames
3. **Query Index**: `login_date_idx` on `login_date` field
   - Optimizes login history queries

## Current Admin User

### Credentials
- **Username**: `iris-admin`
- **Password**: `Sveta87201120!` (stored as bcrypt hash)
- **Created**: 2025-10-18

### Security Notes
- Password is hashed using bcrypt with 12 salt rounds
- Original password is NEVER stored in the database
- Hash: `$2b$12$2I4tgQUsnCQ8F9OOWcYt4.y/NsfEVAlesSxtLiGDsPx3wWTGcap2W`

## Setup Scripts

### 1. create_admin_user.py

**Purpose**: Creates the iris-admins collection and inserts the admin user with a securely hashed password.

**Usage**:
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
source venv/bin/activate
python3 create_admin_user.py
```

**Features**:
- Connects to MongoDB using configuration from `app/config.py`
- Creates collection with proper indexes
- Hashes password using bcrypt (12 rounds)
- Prevents duplicate usernames
- Verifies password hash after creation
- Lists all admin users

**Security**:
- Uses bcrypt for password hashing
- Configurable salt rounds (default: 12)
- Never stores plain text passwords
- Validates password immediately after hashing

### 2. verify_admin_login.py

**Purpose**: Tests authentication by verifying credentials against the database.

**Usage**:
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
source venv/bin/activate
python3 verify_admin_login.py
```

**Features**:
- Connects to MongoDB
- Retrieves user by username
- Verifies password using bcrypt
- Returns success/failure status

## MongoDB Commands

### View All Admin Users
```bash
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" \
  --eval "db['iris-admins'].find().pretty()"
```

### View Collection Indexes
```bash
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" \
  --eval "db['iris-admins'].getIndexes()"
```

### Count Admin Users
```bash
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" \
  --eval "db['iris-admins'].countDocuments()"
```

### Delete an Admin User
```bash
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" \
  --eval "db['iris-admins'].deleteOne({user_name: 'iris-admin'})"
```

### Drop the Collection (BE CAREFUL!)
```bash
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" \
  --eval "db['iris-admins'].drop()"
```

## Password Management

### Bcrypt Configuration
- **Algorithm**: bcrypt
- **Salt Rounds**: 12 (configurable in script)
- **Hash Format**: `$2b$12$[salt][hash]`

### Changing the Password

To change an admin password, you have two options:

**Option 1: Delete and Recreate**
```bash
# Delete the user
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" \
  --eval "db['iris-admins'].deleteOne({user_name: 'iris-admin'})"

# Edit create_admin_user.py to change ADMIN_PASSWORD
# Run the script again
python3 create_admin_user.py
```

**Option 2: Update Password Directly**
```python
import bcrypt
from pymongo import MongoClient

# Connect to MongoDB
client = MongoClient("mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation")
db = client.translation

# Hash new password
new_password = "YourNewPassword123!"
hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt(rounds=12))

# Update the password
db['iris-admins'].update_one(
    {"user_name": "iris-admin"},
    {"$set": {
        "password": hashed.decode('utf-8'),
        "updated_at": datetime.now(timezone.utc)
    }}
)
```

## Integration with FastAPI

### Example Authentication Function

```python
from pymongo import MongoClient
import bcrypt
from app.config import settings

def authenticate_admin(username: str, password: str) -> bool:
    """
    Authenticate admin user against iris-admins collection.

    Args:
        username: Admin username
        password: Plain text password

    Returns:
        bool: True if credentials are valid
    """
    client = MongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_database]

    # Find user
    user = db['iris-admins'].find_one({"user_name": username})

    if not user:
        return False

    # Verify password
    is_valid = bcrypt.checkpw(
        password.encode('utf-8'),
        user['password'].encode('utf-8')
    )

    if is_valid:
        # Update login_date
        from datetime import datetime, timezone
        db['iris-admins'].update_one(
            {"user_name": username},
            {"$set": {"login_date": datetime.now(timezone.utc)}}
        )

    client.close()
    return is_valid
```

### Example FastAPI Endpoint

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/api/v1/admin/login")
async def admin_login(credentials: LoginRequest):
    """Admin login endpoint."""
    if authenticate_admin(credentials.username, credentials.password):
        # Generate JWT token or session
        return {"success": True, "message": "Login successful"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")
```

## Security Best Practices

1. **Never Log Passwords**
   - Always mask passwords in logs
   - Use `***` or similar placeholders

2. **Environment Variables**
   - Store sensitive credentials in `.env`
   - Never commit `.env` to version control

3. **Password Complexity**
   - Minimum 8 characters
   - Include uppercase, lowercase, numbers, special characters
   - Current password meets these requirements

4. **Salt Rounds**
   - Default: 12 rounds (good balance)
   - Increase for higher security (slower)
   - Decrease for faster processing (less secure)

5. **Connection Security**
   - Use TLS/SSL for production MongoDB connections
   - Restrict MongoDB network access
   - Use strong database passwords

## Troubleshooting

### Connection Issues
```bash
# Test MongoDB connection
mongosh "mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation" \
  --eval "db.adminCommand('ping')"
```

### Import Errors
```bash
# Ensure all dependencies are installed
pip install pymongo bcrypt python-dotenv pydantic pydantic-settings
```

### Duplicate Key Error
If you see "User already exists", the user has already been created. Either:
- Delete the existing user first
- Use a different username
- Update the existing user's password

## Files Created

1. **`/Users/vladimirdanishevsky/projects/Translator/server/create_admin_user.py`**
   - Main setup script
   - Creates collection and admin user

2. **`/Users/vladimirdanishevsky/projects/Translator/server/verify_admin_login.py`**
   - Verification script
   - Tests authentication

3. **`/Users/vladimirdanishevsky/projects/Translator/server/ADMIN_SETUP.md`**
   - This documentation file

## Success Verification

The setup was successful on **2025-10-18** with the following results:

- ✅ MongoDB connection established
- ✅ Collection `iris-admins` created
- ✅ Indexes created successfully
- ✅ Admin user `iris-admin` created
- ✅ Password hashed with bcrypt (12 rounds)
- ✅ Password verification passed
- ✅ Authentication test successful

### Verification Output
```
Document ID: 68f3a1c1e44710d091e002e5
Username: iris-admin
Password Hash: $2b$12$2I4tgQUsnCQ8F9OOWcYt4.y/NsfEVAlesSxtLiGDsPx3wWTGcap2W
Created: 2025-10-18 14:18:41.529000 UTC
```

## Support

For issues or questions:
1. Check MongoDB logs: `/var/log/mongodb/mongod.log`
2. Verify environment variables in `.env`
3. Test MongoDB connection with `mongosh`
4. Review script output for error messages
