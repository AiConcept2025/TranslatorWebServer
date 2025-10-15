# Authentication System Testing Guide

Complete enterprise authentication system with MongoDB integration.

## System Overview

- **Database**: MongoDB with collections: `companies`, `users` (or `company_users`), `sessions`
- **Authentication Method**: bcrypt password hashing
- **Session Management**: 8-hour session tokens stored in MongoDB
- **Token Format**: Bearer token in Authorization header

## Prerequisites

1. **MongoDB Running**: Ensure MongoDB is running with the database configured in `.env`
2. **Server Running**: Start the FastAPI server
   ```bash
   cd /Users/vladimirdanishevsky/projects/Translator/server
   python -m app.main
   ```
3. **Test Data**: Ensure you have test company and user in MongoDB

## Test Data Setup

### Sample Company Document (companies collection)
```json
{
  "_id": ObjectId("..."),
  "company_id": "COMP-12345678",
  "company_name": "Iris Trading",
  "description": "Test company",
  "created_at": ISODate("2025-01-01T00:00:00Z"),
  "updated_at": ISODate("2025-01-01T00:00:00Z")
}
```

### Sample User Document (users collection)
```json
{
  "_id": ObjectId("..."),
  "user_id": "user_XXXXXXXX",
  "company_id": ObjectId("..."),  // Must match company's _id
  "user_name": "Vladimir Danishevsky",
  "email": "danishevsky@gmail.com",
  "password_hash": "$2b$12$...",  // bcrypt hash of password
  "permission_level": "admin",
  "status": "active",
  "last_login": null,
  "created_at": ISODate("2025-01-01T00:00:00Z"),
  "updated_at": ISODate("2025-01-01T00:00:00Z")
}
```

### Generate Password Hash (Python)
```python
import bcrypt

password = "your-password-here"
hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
print(hashed.decode('utf-8'))
```

## API Endpoints

### Base URL
```
http://localhost:8000
```

### Authentication Endpoints
- `POST /login/corporate` - Login with company credentials
- `POST /login/logout` - Logout and invalidate session
- `GET /login/verify` - Verify session token validity

---

## Test Cases

### 1. Corporate Login (Success)

**Request:**
```bash
curl -X POST http://localhost:8000/login/corporate \
  -H "Content-Type: application/json" \
  -d '{
    "companyName": "Iris Trading",
    "password": "your-password-here",
    "userFullName": "Vladimir Danishevsky",
    "userEmail": "danishevsky@gmail.com",
    "loginDateTime": "2025-10-13T10:30:00Z"
  }'
```

**Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "Corporate login successful",
  "data": {
    "authToken": "vR6N5_yJ4p8QKxwE3mZ9Ag1WtHuLc2VnBfDo0SrNk7M",
    "tokenType": "Bearer",
    "expiresIn": 28800,
    "expiresAt": "2025-10-13T18:30:00Z",
    "user": {
      "user_id": "user_XXXXXXXX",
      "user_name": "Vladimir Danishevsky",
      "email": "danishevsky@gmail.com",
      "company_name": "Iris Trading",
      "permission_level": "admin"
    },
    "loginDateTime": "2025-10-13T10:30:00Z"
  }
}
```

**Save the authToken for subsequent requests!**

---

### 2. Login with Wrong Password

**Request:**
```bash
curl -X POST http://localhost:8000/login/corporate \
  -H "Content-Type: application/json" \
  -d '{
    "companyName": "Iris Trading",
    "password": "wrong-password",
    "userFullName": "Vladimir Danishevsky",
    "userEmail": "danishevsky@gmail.com",
    "loginDateTime": "2025-10-13T10:30:00Z"
  }'
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Invalid credentials"
}
```

---

### 3. Login with Non-existent Company

**Request:**
```bash
curl -X POST http://localhost:8000/login/corporate \
  -H "Content-Type: application/json" \
  -d '{
    "companyName": "NonExistent Company",
    "password": "password123",
    "userFullName": "Test User",
    "userEmail": "test@example.com",
    "loginDateTime": "2025-10-13T10:30:00Z"
  }'
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Invalid credentials"
}
```

---

### 4. Verify Session (Valid Token)

**Request:**
```bash
# Replace YOUR_TOKEN_HERE with the authToken from login response
curl -X GET http://localhost:8000/login/verify \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Expected Response (200 OK):**
```json
{
  "success": true,
  "valid": true,
  "user": {
    "user_id": "user_XXXXXXXX",
    "user_name": "Vladimir Danishevsky",
    "email": "danishevsky@gmail.com",
    "company_name": "Iris Trading",
    "permission_level": "admin"
  }
}
```

---

### 5. Verify Session (Invalid Token)

**Request:**
```bash
curl -X GET http://localhost:8000/login/verify \
  -H "Authorization: Bearer invalid-token-xyz"
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Invalid or expired session"
}
```

---

### 6. Verify Session (Missing Authorization Header)

**Request:**
```bash
curl -X GET http://localhost:8000/login/verify
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Missing or invalid authorization header. Expected: Authorization: Bearer {token}"
}
```

---

### 7. Logout (Success)

**Request:**
```bash
# Replace YOUR_TOKEN_HERE with the authToken from login response
curl -X POST http://localhost:8000/login/logout \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Expected Response (200 OK):**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

### 8. Logout (Already Logged Out)

**Request:**
```bash
# Use the same token again after logout
curl -X POST http://localhost:8000/login/logout \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Expected Response (404 Not Found):**
```json
{
  "detail": "Session not found"
}
```

---

### 9. Verify Session After Logout

**Request:**
```bash
# Try to verify the token after logout
curl -X GET http://localhost:8000/login/verify \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Invalid or expired session"
}
```

---

### 10. Login with Inactive User

**Prerequisites:** Set user status to "inactive" in MongoDB:
```javascript
db.users.updateOne(
  { email: "danishevsky@gmail.com" },
  { $set: { status: "inactive" } }
)
```

**Request:**
```bash
curl -X POST http://localhost:8000/login/corporate \
  -H "Content-Type: application/json" \
  -d '{
    "companyName": "Iris Trading",
    "password": "your-password-here",
    "userFullName": "Vladimir Danishevsky",
    "userEmail": "danishevsky@gmail.com",
    "loginDateTime": "2025-10-13T10:30:00Z"
  }'
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "User account is not active"
}
```

**Cleanup:** Reactivate the user:
```javascript
db.users.updateOne(
  { email: "danishevsky@gmail.com" },
  { $set: { status: "active" } }
)
```

---

## Testing Protected Routes

### Example: Creating a Protected Endpoint

Add this to any router file:

```python
from fastapi import APIRouter, Depends
from app.middleware.auth_middleware import get_current_user, get_admin_user

router = APIRouter()

@router.get("/protected/user-info")
async def get_user_info(current_user: dict = Depends(get_current_user)):
    """Protected endpoint - requires authentication."""
    return {
        "message": f"Hello {current_user['user_name']}!",
        "user": current_user
    }

@router.post("/protected/admin-only")
async def admin_only_action(admin_user: dict = Depends(get_admin_user)):
    """Protected endpoint - requires admin permission."""
    return {
        "message": "Admin action successful",
        "user": admin_user
    }
```

### Test Protected Endpoint (Authenticated)

```bash
curl -X GET http://localhost:8000/protected/user-info \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

**Expected Response (200 OK):**
```json
{
  "message": "Hello Vladimir Danishevsky!",
  "user": {
    "user_id": "user_XXXXXXXX",
    "user_name": "Vladimir Danishevsky",
    "email": "danishevsky@gmail.com",
    "company_name": "Iris Trading",
    "permission_level": "admin"
  }
}
```

### Test Protected Endpoint (Unauthenticated)

```bash
curl -X GET http://localhost:8000/protected/user-info
```

**Expected Response (401 Unauthorized):**
```json
{
  "detail": "Authorization header missing"
}
```

---

## MongoDB Session Verification

### Check Active Sessions in MongoDB

```javascript
// Connect to MongoDB
use translation

// Find all active sessions
db.sessions.find({ is_active: true }).pretty()

// Find sessions for specific user
db.sessions.find({
  user_id: "user_XXXXXXXX",
  is_active: true
}).pretty()

// Count active sessions
db.sessions.countDocuments({ is_active: true })
```

### Check User Last Login

```javascript
// Check when user last logged in
db.users.findOne(
  { email: "danishevsky@gmail.com" },
  { last_login: 1, user_name: 1, email: 1, status: 1 }
)
```

### Manual Session Cleanup (if needed)

```javascript
// Invalidate all expired sessions
db.sessions.updateMany(
  { expires_at: { $lt: new Date() } },
  { $set: { is_active: false } }
)

// Delete old inactive sessions (older than 30 days)
db.sessions.deleteMany({
  is_active: false,
  created_at: { $lt: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) }
})
```

---

## Complete End-to-End Test Script

```bash
#!/bin/bash

# Save this as test_auth.sh and run: bash test_auth.sh

BASE_URL="http://localhost:8000"

echo "=========================================="
echo "Authentication System E2E Test"
echo "=========================================="

# Test 1: Login
echo -e "\n1. Testing Login..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/login/corporate" \
  -H "Content-Type: application/json" \
  -d '{
    "companyName": "Iris Trading",
    "password": "your-password-here",
    "userFullName": "Vladimir Danishevsky",
    "userEmail": "danishevsky@gmail.com",
    "loginDateTime": "2025-10-13T10:30:00Z"
  }')

echo "$LOGIN_RESPONSE" | jq .

# Extract token
TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.data.authToken')
echo -e "\nExtracted Token: $TOKEN"

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "ERROR: Login failed - no token received"
  exit 1
fi

# Test 2: Verify Session
echo -e "\n2. Testing Session Verification..."
curl -s -X GET "$BASE_URL/login/verify" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Test 3: Protected Route (if implemented)
# echo -e "\n3. Testing Protected Route..."
# curl -s -X GET "$BASE_URL/protected/user-info" \
#   -H "Authorization: Bearer $TOKEN" | jq .

# Test 4: Logout
echo -e "\n3. Testing Logout..."
curl -s -X POST "$BASE_URL/login/logout" \
  -H "Authorization: Bearer $TOKEN" | jq .

# Test 5: Verify Session After Logout
echo -e "\n4. Testing Session After Logout..."
curl -s -X GET "$BASE_URL/login/verify" \
  -H "Authorization: Bearer $TOKEN" | jq .

echo -e "\n=========================================="
echo "Test Complete"
echo "=========================================="
```

---

## Server Logs

The authentication system provides extensive logging. Check the server console for detailed logs:

```
================================================================================
[AUTH] 2025-10-13T10:30:00+00:00 - Login attempt
[AUTH] Company: Iris Trading
[AUTH] Email: danishevsky@gmail.com
[AUTH] User Name: Vladimir Danishevsky
================================================================================
[AUTH] Step 1: Looking up company 'Iris Trading'...
[AUTH] SUCCESS - Company found
[AUTH]   Company ID: 507f1f77bcf86cd799439011
[AUTH]   Company Name: Iris Trading
[AUTH] Step 2: Looking up user in database...
[AUTH]   Searching with:
[AUTH]     - email: danishevsky@gmail.com
[AUTH]     - company_id: 507f1f77bcf86cd799439011
[AUTH]     - user_name: Vladimir Danishevsky
[AUTH] SUCCESS - User found in 'users' collection
[AUTH]   User ID: user_12345678
[AUTH]   User Name: Vladimir Danishevsky
[AUTH]   Email: danishevsky@gmail.com
[AUTH]   Status: active
[AUTH]   Permission Level: admin
[AUTH] Step 3: Checking user status...
[AUTH] SUCCESS - User status is active
[AUTH] Step 4: Verifying password...
[AUTH] SUCCESS - Password verified
[AUTH] Step 5: Creating session token...
[AUTH] SUCCESS - Session created
[AUTH]   Token: vR6N5_yJ4p8Q...Nk7M
[AUTH]   Expires: 2025-10-13T18:30:00+00:00
[AUTH] Step 6: Updating last_login timestamp...
[AUTH] SUCCESS - Last login updated to 2025-10-13T10:30:00+00:00
================================================================================
[AUTH] AUTHENTICATION SUCCESSFUL
[AUTH] User: danishevsky@gmail.com
[AUTH] Company: Iris Trading
[AUTH] Session expires: 2025-10-13T18:30:00+00:00
================================================================================
```

---

## Troubleshooting

### Issue: "Invalid credentials" on correct password

**Solution:**
1. Verify password hash is correct in MongoDB:
   ```python
   import bcrypt
   password = "your-password"
   stored_hash = "$2b$12$..."  # From MongoDB

   # This should return True
   bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
   ```
2. Check user_name matches exactly (case-sensitive)
3. Verify email matches exactly
4. Confirm company_id in user document matches company's _id

### Issue: "Company not found"

**Solution:**
- Check company_name matches exactly (case-sensitive)
- Verify company exists in companies collection:
  ```javascript
  db.companies.findOne({ company_name: "Iris Trading" })
  ```

### Issue: "User account is not active"

**Solution:**
- Check user status in MongoDB:
  ```javascript
  db.users.findOne({ email: "danishevsky@gmail.com" }, { status: 1 })
  ```
- Update status to "active" if needed:
  ```javascript
  db.users.updateOne(
    { email: "danishevsky@gmail.com" },
    { $set: { status: "active" } }
  )
  ```

### Issue: MongoDB connection failed

**Solution:**
1. Check MongoDB is running: `mongosh`
2. Verify connection string in `.env`:
   ```
   MONGODB_URI=mongodb://username:password@localhost:27017/translation?authSource=translation
   ```
3. Check server logs for connection errors

---

## Security Notes

1. **Password Storage**: Passwords are hashed with bcrypt before storage
2. **Session Tokens**: Cryptographically secure tokens (32 bytes)
3. **Session Expiration**: Automatic expiration after 8 hours
4. **TTL Index**: MongoDB automatically cleans up expired sessions
5. **No Sensitive Data in Logs**: Passwords are never logged
6. **HTTPS Recommended**: Use HTTPS in production for token transmission

---

## Next Steps

1. **Install bcrypt**: `pip install bcrypt>=4.0.0`
2. **Create test data** in MongoDB
3. **Start server**: `python -m app.main`
4. **Run tests** using curl commands above
5. **Integrate** authentication middleware in protected routes

---

## Support

For issues or questions, check:
- Server logs in console
- MongoDB logs: `tail -f /var/log/mongodb/mongod.log`
- API documentation: http://localhost:8000/docs
