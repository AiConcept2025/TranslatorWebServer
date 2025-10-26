# Backend Quick Start - Individual Login Implementation

## Quick Implementation Guide

Follow these steps to implement the `/login/individual` endpoint:

## Step 1: Add Request/Response Models

**File**: `app/models/requests.py` or inline in `app/routers/auth.py`

```python
class IndividualLoginRequest(BaseModel):
    """Individual login request model."""
    user_full_name: str = Field(..., alias='userFullName', min_length=1)
    user_email: EmailStr = Field(..., alias='userEmail')
    login_date_time: str = Field(..., alias='loginDateTime')

    model_config = {
        'populate_by_name': True
    }
```

## Step 2: Add Route to auth.py

**File**: `app/routers/auth.py`

```python
@router.post("/individual", response_model=CorporateLoginResponse)  # Reuse response model
async def individual_login(request: IndividualLoginRequest):
    """
    Individual user login endpoint.

    Simpler than corporate login - no company or password required.
    Creates/updates user and returns JWT session token.
    """
    logger.info("=" * 80)
    logger.info(f"👤 INDIVIDUAL LOGIN REQUEST")
    logger.info("=" * 80)
    logger.info(f"  Email: {request.user_email}")
    logger.info(f"  User: {request.user_full_name}")
    logger.info(f"  Login Time: {request.login_date_time}")
    logger.info("=" * 80)

    try:
        # Authenticate user via MongoDB (simplified version)
        auth_result = await auth_service.authenticate_individual_user(
            user_name=request.user_full_name,
            email=request.user_email
        )

        # Prepare successful response
        response_content = {
            "success": True,
            "message": "Individual login successful",
            "data": {
                "authToken": auth_result["session_token"],
                "tokenType": "Bearer",
                "expiresIn": 28800,  # 8 hours in seconds
                "expiresAt": auth_result["expires_at"],
                "user": {
                    "fullName": request.user_full_name,
                    "email": request.user_email
                },
                "loginDateTime": request.login_date_time
            }
        }

        logger.info("=" * 80)
        logger.info("✅ INDIVIDUAL LOGIN SUCCESSFUL")
        logger.info("=" * 80)
        logger.info(f"  User: {request.user_email}")
        logger.info(f"  Token expires: {auth_result['expires_at']}")
        logger.info("=" * 80)

        return JSONResponse(content=response_content)

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"💥 INDIVIDUAL LOGIN ERROR: {e}", exc_info=True)
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail="Login processing failed")
```

## Step 3: Add Auth Service Method

**File**: `app/services/auth_service.py`

```python
async def authenticate_individual_user(
    self,
    user_name: str,
    email: str
) -> dict:
    """
    Authenticate individual user (simplified - no password).

    Creates or updates user and generates session token.
    """
    try:
        # Generate user ID
        user_id = f"user_{secrets.token_hex(8)}"

        # Get or create user in MongoDB
        users_collection = self.db["users"]

        # Check if user exists by email
        existing_user = await users_collection.find_one({"email": email})

        if existing_user:
            # Update existing user
            user_id = existing_user["_id"]
            await users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "user_name": user_name,
                        "last_login": datetime.utcnow().isoformat()
                    }
                }
            )
        else:
            # Create new user
            user_doc = {
                "_id": user_id,
                "email": email,
                "user_name": user_name,
                "user_type": "individual",
                "created_at": datetime.utcnow().isoformat(),
                "last_login": datetime.utcnow().isoformat()
            }
            await users_collection.insert_one(user_doc)

        # Generate JWT session token
        session_token = self._generate_jwt_token(
            user_id=user_id,
            email=email,
            user_name=user_name,
            user_type="individual"
        )

        # Store session in MongoDB
        expires_at = datetime.utcnow() + timedelta(hours=8)
        session_id = f"session_{secrets.token_hex(8)}"

        sessions_collection = self.db["sessions"]
        session_doc = {
            "_id": session_id,
            "user_id": user_id,
            "session_token": session_token,
            "email": email,
            "user_type": "individual",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_active": True
        }
        await sessions_collection.insert_one(session_doc)

        return {
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "user": {
                "user_id": user_id,
                "user_name": user_name,
                "email": email
            }
        }

    except Exception as e:
        logger.error(f"Error authenticating individual user: {e}")
        raise AuthenticationError(f"Authentication failed: {str(e)}")


def _generate_jwt_token(
    self,
    user_id: str,
    email: str,
    user_name: str,
    user_type: str
) -> str:
    """Generate JWT token for session."""
    payload = {
        "user_id": user_id,
        "email": email,
        "user_name": user_name,
        "user_type": user_type,
        "exp": datetime.utcnow() + timedelta(hours=8),
        "iat": datetime.utcnow()
    }

    # Use secret key from config
    secret_key = self.config.get("JWT_SECRET_KEY", "your-secret-key-here")

    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token
```

## Step 4: Test with Frontend

### Manual Testing

1. **Start Backend**:
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
python -m app.main
```

2. **Start Frontend**:
```bash
cd /Users/vladimirdanishevsky/projects/Translator/ui/translation-service
npm start
```

3. **Navigate to**: http://localhost:3000/translate

4. **Expected Behavior**:
   - Login modal appears automatically
   - Enter: "John Doe" and "john@example.com"
   - Click "Start Translation"
   - Success animation shows
   - Modal closes
   - Translation interface becomes accessible

### Testing with curl

```bash
# Test individual login
curl -X POST http://localhost:8000/login/individual \
  -H "Content-Type: application/json" \
  -d '{
    "userFullName": "John Doe",
    "userEmail": "john@example.com",
    "loginDateTime": "2025-10-15T10:30:00Z"
  }'

# Expected Response:
{
  "success": true,
  "message": "Individual login successful",
  "data": {
    "authToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "tokenType": "Bearer",
    "expiresIn": 28800,
    "expiresAt": "2025-10-15T18:30:00Z",
    "user": {
      "fullName": "John Doe",
      "email": "john@example.com"
    },
    "loginDateTime": "2025-10-15T10:30:00Z"
  }
}
```

### Testing Protected Endpoint

```bash
# Get token from login response
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Test translation endpoint with token
curl -X POST http://localhost:8000/translate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "files": [...],
    "sourceLanguage": "en",
    "targetLanguage": "es",
    "email": "john@example.com"
  }'
```

## Step 5: MongoDB Collections Structure

### Users Collection
```javascript
{
  "_id": "user_a1b2c3d4e5f6g7h8",
  "email": "john@example.com",
  "user_name": "John Doe",
  "user_type": "individual",
  "created_at": "2025-10-15T10:30:00Z",
  "last_login": "2025-10-15T10:30:00Z"
}
```

### Sessions Collection
```javascript
{
  "_id": "session_x1y2z3a4b5c6d7e8",
  "user_id": "user_a1b2c3d4e5f6g7h8",
  "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "email": "john@example.com",
  "user_type": "individual",
  "created_at": "2025-10-15T10:30:00Z",
  "expires_at": "2025-10-15T18:30:00Z",
  "is_active": true
}
```

## Common Issues & Solutions

### Issue 1: CORS Error
**Solution**: Ensure CORS middleware allows frontend origin
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue 2: JWT Import Error
**Solution**: Install PyJWT
```bash
pip install pyjwt
```

### Issue 3: Token Not Validated on Protected Endpoints
**Solution**: Add JWT validation middleware
```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

## Checklist

- [ ] Add IndividualLoginRequest model
- [ ] Add /login/individual route to auth.py
- [ ] Add authenticate_individual_user() to auth_service.py
- [ ] Add _generate_jwt_token() helper method
- [ ] Test login endpoint with curl
- [ ] Test with frontend
- [ ] Verify token stored in sessionStorage
- [ ] Verify token injected in API requests
- [ ] Test protected endpoints with token
- [ ] Test token expiration (wait 8 hours or manually set short expiration)
- [ ] Test 401 error handling (invalid token)
- [ ] Verify MongoDB collections populated correctly

## References

- **Corporate Login**: `/server/app/routers/auth.py` (lines 41-161)
- **Auth Service**: `/server/app/services/auth_service.py`
- **Full Spec**: `/server/INDIVIDUAL_LOGIN_ENDPOINT.md`
- **Frontend Component**: `/ui/translation-service/src/components/IndividualLogin/index.tsx`
- **API Service**: `/ui/translation-service/src/services/api.ts` (lines 953-1001)

## Need Help?

1. Review existing corporate login implementation pattern
2. Check MongoDB connection settings
3. Verify JWT secret key is configured
4. Test with Postman/curl before frontend integration
5. Check backend logs for detailed error messages
