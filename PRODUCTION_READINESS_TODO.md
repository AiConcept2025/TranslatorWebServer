# Server Production Readiness TODO

**Last Updated:** 2025-12-08
**Source:** Comprehensive Code Review & Security Audit

---

## ✅ COMPLETED

- [x] Fix deprecated `datetime.utcnow()` usage (45 occurrences in 6 files)
  - google_drive_service.py
  - translation_service.py
  - payment_service.py
  - file_service.py
  - test_helpers.py
  - user_transactions.py

---

## 🔴 CRITICAL ISSUES (Must Fix Before Production)

### 1. Remove Print Statements (408 occurrences)
**Priority:** CRITICAL
**Effort:** 1-2 days
**Files Affected:**
- app/routers/payments.py (4 occurrences)
- app/middleware/auth_middleware.py (timing debug prints)
- app/main.py (153 lines)
- app/services/ (multiple files)

**Action:**
```bash
# Find all print statements
grep -r "print(" server/app --include="*.py" | wc -l

# Replace with logger
# Example:
# print(f"[DEBUG] Message") → logger.debug("[DEBUG] Message")
# print(f"[INFO] Message") → logger.info("[INFO] Message")
```

**Why Critical:**
- Performance degradation
- Log pollution
- Bypasses logging infrastructure
- Can't be filtered/disabled
- Sensitive data may leak to stdout

---

### 2. Remove Password Properties Logging
**Priority:** CRITICAL
**Effort:** 1 hour
**File:** `app/services/email_service.py:738-755`

**Action:**
```python
# REMOVE these lines:
logger.info(f"  Password length: {len(self.smtp_password)}")
logger.info(f"  Password has spaces: {' ' in self.smtp_password}")
logger.info(f"  Password is alphanumeric: {self.smtp_password.isalnum()}")

# REPLACE with:
logger.info("Validating SMTP configuration...")
# DO NOT log password properties
```

**Why Critical:**
- Information leakage
- Aids brute-force attacks
- Violates security best practices

---

### 3. Remove JWT Token Logging
**Priority:** CRITICAL
**Effort:** 2 hours
**Files:**
- app/services/auth_service.py:173
- app/middleware/auth_middleware.py:78,84
- app/routers/auth.py:848

**Action:**
```python
# REMOVE:
logger.info(f"[AUTH] Token: {access_token[:16]}...{access_token[-8:]}")

# REPLACE with:
logger.info("[AUTH] JWT token created successfully")
logger.info(f"[AUTH] Token expires: {expires_at.isoformat()}")
```

**Why Critical:**
- Token theft risk
- Impersonation attacks
- Security violation

---

### 4. Implement JWT Token Blacklist (Enable Logout)
**Priority:** CRITICAL
**Effort:** 2 days
**File:** `app/services/auth_service.py:310-338`

**Current Issue:**
- Logout function is commented out
- Returns `True` without invalidating token
- Compromised tokens valid for 8 hours

**Action:**
```python
# Option 1: Redis-based token blacklist
async def invalidate_session(self, session_token: str) -> bool:
    # Decode token to get expiration
    payload = jwt_service.decode_token_without_verification(session_token)
    exp = payload.get('exp')
    now = datetime.now(timezone.utc).timestamp()
    ttl = int(exp - now)

    # Add to Redis blacklist with TTL
    await redis_client.setex(f"blacklist:{session_token}", ttl, "revoked")
    return True

# Option 2: Short-lived access tokens + refresh tokens
# Access: 15 minutes, Refresh: 7 days (stored in DB)
```

**Why Critical:**
- Can't revoke compromised tokens
- Logout doesn't work
- Security incident response impossible

---

### 5. Strengthen Password Policy
**Priority:** CRITICAL
**Effort:** 3 hours
**File:** `app/models/auth_models.py:39-48`

**Current Policy:**
- Minimum 6 characters (too short)
- Only letter + number required
- No special characters
- No uppercase/lowercase mix

**Action:**
```python
@validator('password')
def validate_password(cls, v):
    if len(v) < 12:  # NIST: 12+ chars
        raise ValueError("Password must be at least 12 characters")

    has_upper = re.search(r'[A-Z]', v)
    has_lower = re.search(r'[a-z]', v)
    has_digit = re.search(r'\d', v)
    has_special = re.search(r'[!@#$%^&*(),.?":{}|<>]', v)

    if not (has_upper and has_lower and has_digit and has_special):
        raise ValueError(
            "Password must contain uppercase, lowercase, digit, and special character"
        )

    return v
```

**Why Critical:**
- Vulnerable to brute-force
- Doesn't meet industry standards
- NIST recommends 12+ characters

---

### 6. Add Database Name Verification to Test Helpers
**Priority:** CRITICAL
**Effort:** 2 hours
**File:** `app/routers/test_helpers.py:276-290`

**Current Risk:**
- Can delete production data if `.env` misconfigured
- No database-level protection

**Action:**
```python
async def reset_test_data():
    check_test_environment()

    # CRITICAL: Verify test database
    current_db_name = database.db.name
    if current_db_name != "translation_test":
        raise HTTPException(
            status_code=500,
            detail=f"SAFETY BLOCK: Cannot delete from {current_db_name}"
        )

    # ... rest of deletion logic
```

**Why Critical:**
- Production data safety
- Defense in depth
- Prevent accidental data loss

---

### 7. Replace Broad Exception Handling
**Priority:** CRITICAL
**Effort:** 3 days
**Files:**
- app/services/subscription_service.py
- app/services/payment_service.py
- app/services/auth_service.py
- app/database/mongodb.py

**Action:**
```python
# WRONG:
try:
    result = await database.find_one({"_id": ObjectId(id)})
except Exception as e:  # TOO BROAD
    logger.error(f"Error: {e}")
    return None

# CORRECT:
from bson.errors import InvalidId

try:
    result = await database.find_one({"_id": ObjectId(id)})
except InvalidId:
    logger.warning(f"Invalid ID format: {id}")
    return None
# Let unexpected exceptions propagate
```

**Why Critical:**
- Masks programming errors
- Silent failures
- Difficult debugging

---

## 🟠 HIGH-PRIORITY ISSUES (Fix Before Launch)

### 8. Add Security Headers Middleware
**Priority:** HIGH
**Effort:** 1 day
**File:** Create `app/middleware/security_headers.py`

**Action:**
```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        if settings.is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:;"
        )

        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response

# Add to main.py
app.add_middleware(SecurityHeadersMiddleware)
```

**Why High Priority:**
- XSS protection
- Clickjacking protection
- HTTPS enforcement

---

### 9. Add Request Size Limits
**Priority:** HIGH
**Effort:** 1 day

**Action:**
```python
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    MAX_REQUEST_SIZE = 100 * 1024 * 1024  # 100MB

    async def dispatch(self, request: Request, call_next):
        if request.headers.get('content-length'):
            content_length = int(request.headers['content-length'])
            if content_length > self.MAX_REQUEST_SIZE:
                raise HTTPException(status_code=413, detail="Request too large")
        return await call_next(request)
```

**Why High Priority:**
- DoS protection
- Memory exhaustion prevention

---

### 10. Add Request Timeout Middleware
**Priority:** HIGH
**Effort:** 1 day

**Action:**
```python
from asyncio import wait_for, TimeoutError as AsyncTimeoutError

class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout: int = 30):
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request, call_next):
        try:
            return await wait_for(call_next(request), timeout=self.timeout)
        except AsyncTimeoutError:
            return JSONResponse({"detail": "Request timeout"}, status_code=504)
```

**Why High Priority:**
- Prevent slow clients from tying up resources
- DoS protection

---

### 11. Implement NoSQL Injection Protection
**Priority:** HIGH
**Effort:** 2 days

**Action:**
```python
class LoginRequest(BaseModel):
    email: EmailStr
    company_name: str

    @validator('company_name')
    def sanitize_company_name(cls, v):
        if not isinstance(v, str):
            raise ValueError("company_name must be a string")
        if v.startswith('$'):
            raise ValueError("Invalid company_name format")
        return v
```

**Why High Priority:**
- Prevent database injection attacks
- Data integrity

---

### 12. Add CSRF Protection
**Priority:** HIGH
**Effort:** 2 days

**Action:**
```python
# Option 1: Use SameSite cookies
response.set_cookie(
    "access_token",
    value=token,
    httponly=True,
    secure=True,
    samesite="strict"  # CSRF protection
)

# Option 2: CSRF tokens
from fastapi_csrf_protect import CsrfProtect

@app.post("/api/endpoint")
async def endpoint(csrf_protect: CsrfProtect = Depends()):
    await csrf_protect.validate_csrf(request)
```

**Why High Priority:**
- Prevent cross-site request forgery
- State-changing operation protection

---

### 13. Implement Account Lockout Mechanism
**Priority:** HIGH
**Effort:** 2 days

**Action:**
```python
async def record_failed_login(email: str):
    key = f"failed_login:{email}"
    attempts = await redis_client.incr(key)
    await redis_client.expire(key, 900)  # 15 minutes

    if attempts >= 5:
        await redis_client.setex(f"locked:{email}", 1800, "1")
        raise HTTPException(
            status_code=429,
            detail="Account locked due to failed login attempts"
        )
```

**Why High Priority:**
- Brute-force protection
- Credential stuffing prevention

---

### 14. Add Rate Limiting to Password Endpoints
**Priority:** HIGH
**Effort:** 1 day

**Action:**
```python
@router.post("/password/reset")
@limiter.limit("3/hour")  # Strict limit
async def reset_password(request: Request, ...):
    ...
```

**Why High Priority:**
- Password attack prevention
- Account security

---

### 15. Enforce HTTPS in Production CORS
**Priority:** HIGH
**Effort:** 1 hour
**File:** `app/main.py:101-108`

**Action:**
```python
if settings.is_production:
    for origin in settings.cors_origins:
        if not origin.startswith('https://'):
            raise ValueError(f"Production CORS origin must use HTTPS: {origin}")
```

**Why High Priority:**
- Prevent MitM attacks
- Protect sensitive data in transit

---

### 16. Implement 2FA for Admin Accounts
**Priority:** HIGH
**Effort:** 3 days

**Action:**
```python
@router.post("/admin/login")
async def admin_login(req: AdminLoginRequest):
    # Step 1: Verify password
    auth_result = await auth_service.authenticate_admin(...)

    # Step 2: Require 2FA
    if auth_result["user"]["permission_level"] == "admin":
        code = generate_totp_code(admin["email"])
        await send_2fa_code(admin["email"], code)
        return {"requires_2fa": True}

    return auth_result
```

**Why High Priority:**
- Admin account security
- Privileged access protection

---

### 17. Make Connection Pool Settings Configurable
**Priority:** HIGH
**Effort:** 2 days
**File:** `app/database/mongodb.py:36-42`

**Action:**
```python
# config.py
class Settings(BaseSettings):
    mongodb_max_pool_size: int = 50
    mongodb_min_pool_size: int = 10
    mongodb_max_idle_time_ms: int = 30000
    mongodb_server_selection_timeout_ms: int = 5000

# database/mongodb.py
self.client = AsyncIOMotorClient(
    settings.mongodb_uri,
    serverSelectionTimeoutMS=settings.mongodb_server_selection_timeout_ms,
    maxPoolSize=settings.mongodb_max_pool_size,
    minPoolSize=settings.mongodb_min_pool_size,
    maxIdleTimeMS=settings.mongodb_max_idle_time_ms,
    connectTimeoutMS=10000,
    socketTimeoutMS=30000
)
```

**Why High Priority:**
- Environment-specific tuning
- Performance optimization
- Resource management

---

## 🟡 MEDIUM-PRIORITY IMPROVEMENTS (Post-Launch)

### 18. Implement Structured Logging (JSON)
**Effort:** 2-3 days

Use `structlog` for machine-parseable logs:
```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)

logger.info("payment_processed",
    payment_id=payment_id,
    amount=amount,
    currency=currency
)
```

---

### 19. Add Comprehensive Audit Logging
**Effort:** 3-5 days

Track security events:
- Permission changes
- Admin actions
- Data access
- Failed login attempts

---

### 20. Migrate Rate Limiter to Redis
**Effort:** 2 days
**File:** `app/middleware/rate_limiting.py:21`

Replace in-memory storage with Redis for distributed rate limiting.

---

### 21. Implement Database Transactions
**Effort:** 1 week

Use MongoDB transactions for multi-collection updates to ensure consistency.

---

### 22. Add Dependency Security Scanning
**Effort:** 1 day

```bash
# Add to CI/CD
pip install safety pip-audit
safety check --json
pip-audit --desc
```

---

### 23. Add API Key Rotation Mechanism
**Effort:** 3 days

Implement API key management with expiration and rotation.

---

### 24. Add File Upload Malware Scanning
**Effort:** 3-5 days

Use `python-magic` and antivirus integration to scan uploaded files.

---

## 📊 STATISTICS

**Critical Issues:** 7
**High-Priority Issues:** 10
**Medium-Priority Issues:** 7
**Total Issues:** 24

**Completed:** 1 (datetime fix)
**Remaining:** 23

---

## 🎯 RECOMMENDED IMPLEMENTATION ORDER

### Phase 1: Security Fixes (Week 1)
1. Remove password/JWT token logging (2-3 hours)
2. Strengthen password policy (3 hours)
3. Add security headers middleware (1 day)
4. Enforce HTTPS in CORS (1 hour)

**Total:** 2-3 days

---

### Phase 2: Critical Code Quality (Week 2)
1. Replace print() statements with logger (2 days)
2. Replace broad exception handling (3 days)
3. Add database name verification (2 hours)

**Total:** 5-6 days

---

### Phase 3: Authentication & Authorization (Week 3)
1. Implement JWT token blacklist (2 days)
2. Implement account lockout (2 days)
3. Add rate limiting to password endpoints (1 day)
4. Implement 2FA for admins (3 days)

**Total:** 8 days (1.5 weeks)

---

### Phase 4: API Security (Week 4-5)
1. Add request size limits (1 day)
2. Add request timeout middleware (1 day)
3. Implement NoSQL injection protection (2 days)
4. Add CSRF protection (2 days)
5. Configure connection pool settings (2 days)

**Total:** 8 days (1.5 weeks)

---

### Phase 5: Post-Launch Improvements (Ongoing)
1. Structured logging
2. Audit logging
3. Redis rate limiting
4. Database transactions
5. Dependency scanning
6. API key rotation
7. File upload scanning

---

## 📝 NOTES

- All critical issues must be resolved before production deployment
- High-priority issues should be completed before launch
- Medium-priority issues can be addressed post-launch
- Regular security audits recommended (quarterly)
- Keep dependencies updated
- Monitor security advisories

---

**Next Review Date:** 2026-03-08 (3 months after launch)
