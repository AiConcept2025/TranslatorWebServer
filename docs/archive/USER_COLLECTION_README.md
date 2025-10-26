# MongoDB User Collection Setup

This directory contains scripts for setting up and testing the `users_login` collection in the MongoDB translation database.

## Collection Overview

**Collection Name:** `users_login`

**Database:** `translation`

**Purpose:** Store user authentication credentials for the translation service.

## Collection Schema

| Field Name   | Type     | Required | Unique | Description                    |
|-------------|----------|----------|--------|--------------------------------|
| user_name   | string   | Yes      | Yes    | Username for login             |
| user_email  | string   | Yes      | Yes    | User's email address           |
| password    | string   | Yes      | No     | BCrypt hashed password         |
| created_at  | datetime | Yes      | No     | Account creation timestamp     |
| updated_at  | datetime | Yes      | No     | Last update timestamp          |
| last_login  | datetime | No       | No     | Last login timestamp (nullable)|

## Indexes

The collection has the following indexes:

1. **_id_** (default MongoDB index)
   - Keys: `_id` (ascending)
   - Unique: No (implicit)

2. **idx_user_email_unique**
   - Keys: `user_email` (ascending)
   - Unique: Yes
   - Purpose: Ensure unique email addresses

3. **idx_user_name_unique**
   - Keys: `user_name` (ascending)
   - Unique: Yes
   - Purpose: Ensure unique usernames

4. **idx_created_at**
   - Keys: `created_at` (ascending)
   - Unique: No
   - Purpose: Optimize queries sorting by creation date

## Scripts

### 1. create_users.py

**Purpose:** Initialize the `users_login` collection with dummy user data.

**Usage:**
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
source venv/bin/activate
python create_users.py
```

**Features:**
- Creates the `users_login` collection
- Inserts 8 dummy users with realistic data
- Hashes all passwords with BCrypt (12 salt rounds)
- Creates unique indexes on `user_name` and `user_email`
- Verifies all passwords can be authenticated
- Provides detailed execution report

**Important Notes:**
- If the collection already exists, the script will prompt before dropping it
- All passwords are hashed using BCrypt with 12 salt rounds
- The default password for all dummy users is: `Password123!`

### 2. test_user_authentication.py

**Purpose:** Verify user authentication functionality.

**Usage:**
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
source venv/bin/activate
python test_user_authentication.py
```

**Features:**
- Tests successful authentication with valid credentials
- Tests failed authentication with invalid passwords
- Tests authentication for non-existent users
- Provides detailed test results and summary

## Dummy Users

The following 8 dummy users are created:

| # | Username        | Email                       | Password     |
|---|-----------------|----------------------------|--------------|
| 1 | john_smith      | john.smith@example.com     | Password123! |
| 2 | sarah_jones     | sarah.jones@example.com    | Password123! |
| 3 | mike_wilson     | mike.wilson@example.com    | Password123! |
| 4 | emma_brown      | emma.brown@example.com     | Password123! |
| 5 | david_taylor    | david.taylor@example.com   | Password123! |
| 6 | lisa_anderson   | lisa.anderson@example.com  | Password123! |
| 7 | james_martinez  | james.martinez@example.com | Password123! |
| 8 | sophia_garcia   | sophia.garcia@example.com  | Password123! |

**Note:** All passwords are stored as BCrypt hashes with 12 salt rounds.

## Security Features

1. **Password Hashing:**
   - BCrypt algorithm with 12 salt rounds
   - Passwords never stored in plain text
   - Each hash is unique even for identical passwords

2. **Unique Constraints:**
   - Username must be unique across all users
   - Email must be unique across all users
   - Enforced at the database level via indexes

3. **Password Verification:**
   - Uses BCrypt's secure comparison
   - Resistant to timing attacks
   - Verified during collection setup

## MongoDB Connection

**Connection String:**
```
mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation
```

**Configuration:**
- Host: localhost
- Port: 27017
- Database: translation
- Auth Database: translation
- Username: iris
- Password: Sveta87201120

## Example Usage in Code

### Python (with PyMongo)

```python
import bcrypt
from pymongo import MongoClient

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user."""
    client = MongoClient('mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation')
    db = client['translation']
    collection = db['users_login']

    # Find user
    user = collection.find_one({"user_name": username})
    if not user:
        return False

    # Verify password
    return bcrypt.checkpw(
        password.encode('utf-8'),
        user['password'].encode('utf-8')
    )

# Usage
if authenticate_user('john_smith', 'Password123!'):
    print("Authentication successful!")
else:
    print("Authentication failed!")
```

### Python (with Motor - Async)

```python
import bcrypt
from motor.motor_asyncio import AsyncIOMotorClient

async def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user asynchronously."""
    client = AsyncIOMotorClient('mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation')
    db = client['translation']
    collection = db['users_login']

    # Find user
    user = await collection.find_one({"user_name": username})
    if not user:
        return False

    # Verify password
    return bcrypt.checkpw(
        password.encode('utf-8'),
        user['password'].encode('utf-8')
    )

# Usage
result = await authenticate_user('john_smith', 'Password123!')
```

## Verification Commands

### Check Collection Stats
```bash
python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation')
db = client['translation']
stats = db.command('collstats', 'users_login')
print(f'Documents: {stats[\"count\"]}')
print(f'Indexes: {stats[\"nindexes\"]}')
client.close()
"
```

### List All Users
```bash
python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation')
db = client['translation']
for user in db['users_login'].find({}, {'password': 0}):
    print(f'{user[\"user_name\"]}: {user[\"user_email\"]}')
client.close()
"
```

### View Indexes
```bash
python3 -c "
from pymongo import MongoClient
client = MongoClient('mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation')
db = client['translation']
for name, details in db['users_login'].index_information().items():
    print(f'{name}: {details}')
client.close()
"
```

## Troubleshooting

### Connection Issues

If you cannot connect to MongoDB:
1. Verify MongoDB is running: `brew services list` (on macOS) or `systemctl status mongod` (on Linux)
2. Check the connection string in the script
3. Verify credentials are correct
4. Ensure the `translation` database exists

### Import Errors

If you get module import errors:
1. Ensure you're in the virtual environment: `source venv/bin/activate`
2. Install required dependencies: `pip install -r requirements.txt`
3. Verify bcrypt and pymongo are installed: `pip list | grep -E "bcrypt|pymongo"`

### Permission Issues

If you get permission errors:
1. Make scripts executable: `chmod +x *.py`
2. Verify MongoDB user has write permissions on the `translation` database

## Maintenance

### Re-running the Setup Script

The `create_users.py` script can be run multiple times:
- If the collection exists, it will prompt before dropping it
- All data will be recreated from scratch
- Passwords will be re-hashed (resulting in different hashes)

### Adding New Users

To add new users programmatically:

```python
import bcrypt
from pymongo import MongoClient
from datetime import datetime, timezone

def add_user(username: str, email: str, password: str):
    """Add a new user to the collection."""
    client = MongoClient('mongodb://iris:Sveta87201120@localhost:27017/translation?authSource=translation')
    db = client['translation']
    collection = db['users_login']

    # Hash password
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))

    # Insert user
    user = {
        "user_name": username,
        "user_email": email,
        "password": hashed.decode('utf-8'),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "last_login": None
    }

    collection.insert_one(user)
    client.close()
```

## Production Considerations

When moving to production:

1. **Change Passwords:** Replace all dummy passwords with secure, randomly generated ones
2. **Update Connection String:** Use production MongoDB credentials
3. **Enable SSL/TLS:** Use encrypted connections
4. **Implement Rate Limiting:** Protect against brute force attacks
5. **Add Logging:** Log all authentication attempts
6. **Implement Account Lockout:** Lock accounts after failed login attempts
7. **Add Password Policies:** Enforce strong password requirements
8. **Implement Password Reset:** Add email-based password reset functionality
9. **Add Multi-Factor Authentication:** Consider implementing 2FA
10. **Monitor Access:** Set up alerts for suspicious activity

## References

- [BCrypt Documentation](https://pypi.org/project/bcrypt/)
- [PyMongo Documentation](https://pymongo.readthedocs.io/)
- [MongoDB Indexing Best Practices](https://docs.mongodb.com/manual/indexes/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
