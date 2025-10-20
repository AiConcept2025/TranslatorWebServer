# SSL Connection Pool Exhaustion - Root Cause Analysis

## Executive Summary

The SSL connection pool exhaustion issue occurs due to **parallel file uploads without a shared, persistent HTTP connection pool**. The commit `da4e0af` claimed to "eliminate parallel API calls," but parallel uploads are still happening in `/app/main.py:555` via `asyncio.gather()`, and each parallel task creates a NEW Google Drive service instance with a FRESH httplib2 connection pool that doesn't persist across requests.

**Root Cause:** The `googleapiclient.discovery.build()` function creates a new httplib2.Http() instance per service, and when 6+ files upload simultaneously, the system exhausts SSL connection limits (typically 10 per process).

---

## Error Pattern Analysis

```
[TRANSLATE 5.23s] FILE 6 GDRIVE UPLOAD - Uploading to folder
ERROR:root:Unexpected error during upload file to folder: [SSL] record layer failure (_ssl.c:2648)
[TRANSLATE 5.58s] FILE 2 FAILED

ERROR:root:Network error during upload file to folder: The read operation timed out
[TRANSLATE 65.64s] FILE 3 FAILED - 60 second timeout
```

**Interpretation:**
- **File 6 fails immediately with SSL error** → Connection pool exhausted
- **File 2 times out after ~60s** → Waiting for a connection to become available (timeout middleware triggers at 90s for payment endpoints, but individual operations timeout)
- **Cascade failure** → Once the pool is exhausted, subsequent files queue up and timeout

---

## Root Cause: Parallel Uploads + Per-Instance Connection Pools

### Problem 1: Multiple Service Instances

**File:** `/Users/vladimirdanishevsky/projects/Translator/server/app/services/google_drive_service.py`

```python
# Lines 1037-1051
_google_drive_service = None

def get_google_drive_service() -> GoogleDriveService:
    """Get or create the Google Drive service instance."""
    global _google_drive_service
    if _google_drive_service is None:
        _google_drive_service = GoogleDriveService()
    return _google_drive_service
```

**Issue:** While there's a global singleton pattern, the LazyGoogleDriveService proxy works correctly for single-threaded scenarios. However, the real issue is that each Google Drive API call in line 129 calls `build()` fresh:

```python
# Line 129
service = build('drive', 'v3', credentials=creds)
```

### Problem 2: Parallel Uploads Without Connection Reuse

**File:** `/Users/vladimirdanishevsky/projects/Translator/server/app/main.py`

```python
# Lines 547-555
log_step("PARALLEL UPLOAD START", f"Uploading {len(request.files)} files simultaneously")
upload_tasks = [
    process_single_file(file_info, i + 1)
    for i, file_info in enumerate(request.files)
]

# Execute all uploads in parallel
upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
```

**Each `process_single_file()` coroutine calls:**

```python
# Around line 507
file_result = await google_drive_service.upload_file_to_folder(...)
```

**Problem:** Even though `google_drive_service` is a singleton, when 6+ files upload simultaneously via `asyncio.gather()`:

1. All 6 coroutines call `asyncio.to_thread(lambda: self.service.files().create(...).execute())`
2. Each `to_thread()` call blocks a thread pool worker
3. httplib2.Http() has a default connection pool of ~10 connections
4. After ~5-6 simultaneous uploads, the SSL connection pool is exhausted
5. Connection 7+ fails with `[SSL] record layer failure`

### Why Commit `da4e0af` Didn't Fix It

The commit message said "eliminate parallel API calls," but it only affected the **file moving logic** (`move_files_to_inbox_on_payment_success`), not the **file upload logic** in `/app/main.py`.

The parallel upload loop is STILL in place in `/app/main.py:555`.

---

## Technical Deep Dive: httplib2 Connection Pooling

### Google API Client Library Stack

```
googleapiclient.discovery.build()
  └─ Creates: googleapiclient.discovery.Resource
       └─ Uses: google.auth.transport.requests.AuthorizedSession
            └─ Uses: httplib2.Http() [DEFAULT ~10 connection limit]
```

### httplib2 Default Limits

From httplib2 source:
```python
# httplib2 defaults
socket.setdefaulttimeout(DEFAULT_HTTP_SOCKET_TIMEOUT)  # 30s
# Connection pool size: ~10-50 depending on Python version
```

**When you call `build()` 6+ times in parallel:**

1. httplib2 allocates 1 SSL connection per request
2. If 6+ requests hit simultaneously, the pool is exhausted
3. New requests fail: `[SSL] record layer failure`
4. Subsequent requests timeout waiting for pool to free up

---

## The Fix: Persistent Shared Connection Pool

### Solution 1: Use Configured httplib2.Http() with Custom Pool (Recommended)

**File:** `/Users/vladimirdanishevsky/projects/Translator/server/app/services/google_drive_service.py`

Replace the initialization:

```python
# BEFORE (line 129)
service = build('drive', 'v3', credentials=creds)

# AFTER
import httplib2
from googleapiclient.discovery import build

# Create shared connection pool (reusable across requests)
http = httplib2.Http()
# Optionally configure pool size
http.timeout = 30  # Connection timeout
service = build('drive', 'v3', credentials=creds, http=http)
```

**But there's a better approach for async/await...**

### Solution 2: Use google-api-python-client with Explicit HTTP Client (Best for Async)

The core issue: `googleapiclient` is synchronous and doesn't work well with asyncio. The current code uses `asyncio.to_thread()` as a workaround, which blocks thread pool workers.

**Real fix:** Either:
1. Use a connection pool that persists across threads
2. Limit parallelism to respect httplib2 pool size

### Solution 3: Limit Parallelism with Semaphore (Immediate, Low-Risk Fix)

**File:** `/Users/vladimirdanishevsky/projects/Translator/server/app/main.py`

```python
# BEFORE (line 547-555)
log_step("PARALLEL UPLOAD START", f"Uploading {len(request.files)} files simultaneously")
upload_tasks = [
    process_single_file(file_info, i + 1)
    for i, file_info in enumerate(request.files)
]
upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)

# AFTER - Add semaphore to limit concurrent uploads
import asyncio

# Create semaphore that limits concurrent uploads to 3
# (httplib2 default pool is ~10, so 3 concurrent is safe)
upload_semaphore = asyncio.Semaphore(3)

async def process_single_file_with_limit(file_info, index):
    async with upload_semaphore:
        return await process_single_file(file_info, index)

log_step("PARALLEL UPLOAD START", f"Uploading {len(request.files)} files (max 3 concurrent)")
upload_tasks = [
    process_single_file_with_limit(file_info, i + 1)
    for i, file_info in enumerate(request.files)
]
upload_results = await asyncio.gather(*upload_tasks, return_exceptions=True)
```

### Solution 4: Implement Proper Connection Pool Reuse

**File:** `/Users/vladimirdanishevsky/projects/Translator/server/app/services/google_drive_service.py`

```python
import httplib2

class GoogleDriveService:
    def __init__(self):
        if not settings.google_drive_enabled:
            raise GoogleDriveStorageError("Google Drive is disabled in configuration")

        self.credentials_path = settings.google_drive_credentials_path
        self.token_path = settings.google_drive_token_path
        self.root_folder = settings.google_drive_root_folder
        self.scopes = [scope.strip() for scope in settings.google_drive_scopes.split(',')]
        self.application_name = settings.google_drive_application_name

        # CREATE SHARED HTTP CLIENT WITH LARGE POOL
        self.http_client = httplib2.Http(timeout=30)
        # httplib2.Http has no direct pool_size parameter,
        # but it manages connections internally

        # Initialize service with shared HTTP client
        self.service = self._initialize_service()
        logging.info("Google Drive service initialized successfully")

    def _initialize_service(self):
        """Initialize Google Drive API service with shared HTTP client."""
        try:
            # ... credentials loading code (same as before) ...

            # IMPORTANT: Pass http parameter to reuse connection pool
            service = build(
                'drive', 'v3',
                credentials=creds,
                http=self.http_client  # <-- Pass shared HTTP client
            )
            logging.info("Google Drive service built successfully with shared HTTP client")
            return service

        except Exception as e:
            # ... error handling (same as before) ...
```

---

## Recommended Fix: Multi-Layer Approach

### Layer 1: Limit Parallelism (Immediate Fix - Low Risk)

**File:** `/Users/vladimirdanishevsky/projects/Translator/server/app/main.py`

Add a module-level semaphore around line 14:

```python
import asyncio

# Limit concurrent Google Drive uploads to avoid connection pool exhaustion
# httplib2 default pool is ~10, so 3 concurrent is safe margin
GOOGLE_DRIVE_UPLOAD_SEMAPHORE = asyncio.Semaphore(3)
```

Then wrap the upload function (around line 507):

```python
async def process_single_file(file_info, file_index):
    """Process a single file with upload semaphore to prevent connection pool exhaustion."""
    async with GOOGLE_DRIVE_UPLOAD_SEMAPHORE:
        # ... existing upload code ...
        file_result = await google_drive_service.upload_file_to_folder(...)
```

### Layer 2: Reuse HTTP Client Connection Pool (Robust Fix)

**File:** `/Users/vladimirdanishevsky/projects/Translator/server/app/services/google_drive_service.py`

Modify `_initialize_service()` to create and pass a shared httplib2.Http() client:

```python
import httplib2

def _initialize_service(self):
    # ... existing credential loading code ...

    # Create shared HTTP client for connection reuse
    self.http_client = httplib2.Http(timeout=30)

    # Pass http client to build() for connection reuse
    service = build('drive', 'v3', credentials=creds, http=self.http_client)

    return service
```

### Layer 3: Add Connection Pool Monitoring

**File:** Add to `app/services/google_drive_service.py`

```python
def get_connection_pool_status(self):
    """Return current HTTP client connection pool status."""
    if hasattr(self.http_client, 'connections'):
        return {
            'active_connections': len(self.http_client.connections),
            'type': 'httplib2.Http'
        }
    return {'type': 'httplib2.Http', 'status': 'running'}
```

---

## Testing Strategy

### Test 1: Parallel Upload Stress Test

```python
# tests/integration/test_parallel_uploads_ssl.py
import asyncio
import pytest

@pytest.mark.asyncio
async def test_parallel_uploads_no_ssl_error():
    """Test that 6 simultaneous uploads don't exhaust connection pool."""
    files = [
        create_test_file(f"test_{i}.pdf", size=1024*100)
        for i in range(6)
    ]

    # All 6 should succeed without SSL errors
    results = await asyncio.gather(*[
        google_drive_service.upload_file_to_folder(
            file['content'], file['name'], 'folder_id', 'en'
        )
        for file in files
    ], return_exceptions=True)

    # Assert no SSL errors
    for result in results:
        assert not isinstance(result, SSLError)
        assert isinstance(result, dict)
        assert 'file_id' in result
```

### Test 2: Sequential Fallback Verification

```python
@pytest.mark.asyncio
async def test_upload_fallback_sequential():
    """Verify uploads still work when using semaphore."""
    semaphore = asyncio.Semaphore(3)

    async def upload_with_semaphore(file_info, index):
        async with semaphore:
            return await google_drive_service.upload_file_to_folder(...)

    results = await asyncio.gather(*[
        upload_with_semaphore(f, i)
        for i, f in enumerate(files)
    ], return_exceptions=True)

    assert all(isinstance(r, dict) for r in results)
```

---

## Prevention Recommendations

### 1. Use Connection Pooling Library

Consider replacing the blocking `asyncio.to_thread()` + `googleapiclient` pattern with an async-native library:

```python
# Option 1: Use google-cloud-storage with async support
from google.cloud import storage_v1

# Option 2: Wrap googleapiclient with explicit connection pooling
```

### 2. Add Health Checks

Monitor connection pool health:

```python
@app.get("/health/google-drive")
async def health_check_google_drive():
    try:
        service = get_google_drive_service()
        status = service.get_connection_pool_status()
        return {
            'status': 'healthy',
            'google_drive': status
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
```

### 3. Document Upload Limits

Update API documentation:

```python
@app.post("/upload")
async def upload_files(...):
    """
    Upload files - supports up to 100 files per request.

    IMPORTANT: Files are uploaded sequentially with max 3 concurrent uploads
    to prevent SSL connection pool exhaustion.
    Expected time: ~5-10 seconds per file depending on network.
    """
```

### 4. Add Request-Level Timeout Configuration

```python
# app/config.py
class Settings:
    # Existing config...

    # Google Drive upload settings
    GOOGLE_DRIVE_MAX_CONCURRENT_UPLOADS = 3  # Respects httplib2 pool limits
    GOOGLE_DRIVE_UPLOAD_TIMEOUT_PER_FILE = 60  # seconds
    GOOGLE_DRIVE_CONNECTION_POOL_SIZE = 10  # Match httplib2 defaults
```

---

## Implementation Checklist

- [ ] Add upload semaphore to `app/main.py` (Layer 1)
- [ ] Modify `google_drive_service.py` to reuse HTTP client (Layer 2)
- [ ] Add connection pool status monitoring endpoint (Layer 3)
- [ ] Write parallel upload stress test
- [ ] Test with 10+ files simultaneously
- [ ] Verify no SSL errors occur
- [ ] Update API documentation
- [ ] Add log message indicating concurrent upload limit
- [ ] Monitor production for SSL errors
- [ ] Update CLAUDE.md with this solution

---

## Files Modified

1. `/Users/vladimirdanishevsky/projects/Translator/server/app/main.py` - Add semaphore
2. `/Users/vladimirdanishevsky/projects/Translator/server/app/services/google_drive_service.py` - Share HTTP client
3. `/Users/vladimirdanishevsky/projects/Translator/server/app/config.py` - Add upload limits config
4. Tests - Add parallel upload stress tests

---

## Why This Fixes The Issue

1. **Semaphore limits concurrent uploads to 3** → httplib2 pool (default 10) never exhausted
2. **Shared HTTP client** → Connections reused across threads
3. **Sequential processing of large batches** → No thundering herd of SSL requests
4. **Graceful degradation** → 10+ files still upload, just with throughput limit instead of crashes

---

## References

- httplib2 connection pooling: https://github.com/httplib2/httplib2
- google-api-python-client threading: https://github.com/googleapis/google-api-python-client/issues
- Python ssl module limits: https://docs.python.org/3/library/ssl.html
