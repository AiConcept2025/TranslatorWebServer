# Individual Login Endpoint Documentation

## Overview
This document specifies the requirements for implementing the `/login/individual` endpoint for JWT token authentication for individual users on the translate page.

## Endpoint Specification

### Route
```
POST /login/individual
```

### Purpose
Authenticates individual users (non-enterprise) accessing the translation service and issues a JWT token for API access.

### Request Model

#### Request Body (JSON)
```json
{
    "userFullName": "John Doe",
    "userEmail": "john.doe@example.com",
    "loginDateTime": "2025-10-15T10:30:00Z"
}
```

#### Pydantic Model (Python)
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

### Response Model

#### Success Response (200 OK)
```json
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
            "email": "john.doe@example.com"
        },
        "loginDateTime": "2025-10-15T10:30:00Z"
    }
}
```

#### Error Response (401 Unauthorized)
```json
{
    "success": false,
    "message": "Authentication failed",
    "error": {
        "code": "AUTH_FAILED",
        "message": "Invalid user credentials"
    }
}
```

#### Error Response (500 Internal Server Error)
```json
{
    "success": false,
    "message": "Login processing failed",
    "error": {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred during login"
    }
}
```

## Implementation Requirements

### 1. Authentication Logic
Unlike corporate login which requires company verification and password, individual login should:
- Accept any valid email address and full name
- Create a session for the user
- Generate a JWT token valid for 8 hours (28800 seconds)
- Store session information in MongoDB sessions collection

### 2. JWT Token Structure
The JWT token should contain the following claims:
```json
{
    "user_id": "user_XXXXXXXX",
    "email": "john.doe@example.com",
    "full_name": "John Doe",
    "user_type": "individual",
    "login_datetime": "2025-10-15T10:30:00Z",
    "exp": 1729007400,
    "iat": 1728978600
}
```

### 3. Database Operations

#### Users Collection
Create or update user record:
```json
{
    "_id": "user_XXXXXXXX",
    "email": "john.doe@example.com",
    "full_name": "John Doe",
    "user_type": "individual",
    "created_at": "2025-10-15T10:30:00Z",
    "last_login": "2025-10-15T10:30:00Z"
}
```

#### Sessions Collection
Create session record:
```json
{
    "_id": "session_XXXXXXXX",
    "user_id": "user_XXXXXXXX",
    "session_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "email": "john.doe@example.com",
    "user_type": "individual",
    "created_at": "2025-10-15T10:30:00Z",
    "expires_at": "2025-10-15T18:30:00Z",
    "is_active": true
}
```

### 4. Comparison with Corporate Login

#### Similarities
- Both return JWT tokens with same structure
- Both use 8-hour token expiration
- Both store sessions in MongoDB
- Both use Bearer token authentication

#### Differences
| Aspect | Corporate Login | Individual Login |
|--------|----------------|------------------|
| Password | Required | Not required |
| Company | Required | Not applicable |
| Validation | Company + User verification | Email format only |
| User Type | "enterprise" | "individual" |
| Permission Level | "admin" or "user" | Not applicable |

### 5. FastAPI Implementation Skeleton

```python
@router.post("/individual", response_model=IndividualLoginResponse)
async def individual_login(request: IndividualLoginRequest):
    """
    Individual login endpoint with MongoDB authentication.

    Creates or retrieves user record and generates JWT session token.
    No password required - email-based authentication for individual users.

    Returns session token stored in MongoDB sessions collection.
    """
    logger.info("=" * 80)
    logger.info(f"👤 INDIVIDUAL LOGIN REQUEST")
    logger.info("=" * 80)
    logger.info(f"  Email: {request.user_email}")
    logger.info(f"  User: {request.user_full_name}")
    logger.info(f"  Login Time: {request.login_date_time}")
    logger.info("=" * 80)

    try:
        # Create or update user in MongoDB
        # Generate session token (JWT)
        # Store session in MongoDB
        # Return success response

        response_content = {
            "success": True,
            "message": "Individual login successful",
            "data": {
                "authToken": session_token,
                "tokenType": "Bearer",
                "expiresIn": 28800,  # 8 hours in seconds
                "expiresAt": expires_at_iso,
                "user": {
                    "fullName": request.user_full_name,
                    "email": request.user_email
                },
                "loginDateTime": request.login_date_time
            }
        }

        return JSONResponse(content=response_content)

    except Exception as e:
        logger.error(f"💥 INDIVIDUAL LOGIN ERROR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Login processing failed")
```

## Frontend Integration

### Token Storage
The frontend stores the token in sessionStorage using the same keys as corporate login:
```javascript
sessionStorage.setItem('corporate_auth_token', token);
sessionStorage.setItem('corporate_token_type', 'Bearer');
sessionStorage.setItem('corporate_token_expires_at', expiresAt);
sessionStorage.setItem('corporate_user', JSON.stringify({
    fullName: user.fullName,
    email: user.email,
    userType: 'individual',
    loginDateTime: loginDateTime
}));
```

### Token Injection
The existing API service automatically injects the token in all requests:
```javascript
Authorization: Bearer {token}
```

### Token Validation
On page load, the frontend checks:
1. Token exists in sessionStorage
2. Token is not expired
3. If invalid/missing: shows login modal
4. If valid: allows access to translation features

## Security Considerations

1. **Email Validation**: Ensure proper email format validation
2. **Rate Limiting**: Implement rate limiting to prevent abuse
3. **Token Expiration**: 8-hour expiration balances security and UX
4. **Session Management**: Clean up expired sessions periodically
5. **HTTPS Only**: Ensure endpoint only accessible via HTTPS in production
6. **CORS**: Configure appropriate CORS headers

## Testing Checklist

- [ ] Valid email and full name creates session successfully
- [ ] JWT token is valid and properly structured
- [ ] Token expires after 8 hours
- [ ] Session stored in MongoDB with correct fields
- [ ] User record created/updated in MongoDB
- [ ] Invalid email format returns 400 error
- [ ] Missing fields return validation errors
- [ ] Token can be used to authenticate API requests
- [ ] Expired tokens are rejected by API endpoints
- [ ] Multiple logins with same email update last_login timestamp

## Related Files

### Frontend
- `/ui/translation-service/src/components/IndividualLogin/index.tsx` - Login modal component
- `/ui/translation-service/src/components/TranslationApp.tsx` - Integration point
- `/ui/translation-service/src/services/api.ts` - API service with token injection
- `/ui/translation-service/src/types/index.ts` - TypeScript type definitions

### Backend (To Be Created)
- `/server/app/routers/auth.py` - Add individual_login route
- `/server/app/services/auth_service.py` - Add individual authentication logic
- `/server/app/models/requests.py` - Add IndividualLoginRequest model
- `/server/app/models/responses.py` - Add IndividualLoginResponse model

## Reference Implementation
See existing `/login/corporate` endpoint in `/server/app/routers/auth.py` for similar implementation pattern.
