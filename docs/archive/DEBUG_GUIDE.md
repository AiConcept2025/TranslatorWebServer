# DEBUG GUIDE - Timeout Issue Diagnosis

## Current Problem
- Request to `/translate` times out after 120 seconds
- Returns 408/400 with no CORS headers
- Browser shows CORS error instead of actual error
- Authentication logs never appear
- Endpoint function never executes

## Debug Logging Added

### 1. Authentication Dependency (auth_middleware.py:20-22)
```python
print("🟢 DEBUG: get_current_user() INVOKED - FastAPI dependency system working")
print(f"🟢 DEBUG: Authorization header present: {bool(authorization)}")
```
**Purpose**: Confirms if FastAPI is calling the authentication dependency

### 2. Endpoint Function Start (main.py:125-127)
```python
print("🔵 DEBUG: Endpoint function STARTED - Pydantic validation PASSED")
print(f"🔵 DEBUG: Received {len(request.files)} files")
print(f"🔵 DEBUG: First file name: {request.files[0].name if request.files else 'NO FILES'}")
```
**Purpose**: Confirms endpoint function is reached (after auth + validation)

### 3. Pydantic Validation Error (main.py:599-601)
```python
print("🔴 DEBUG: PYDANTIC VALIDATION ERROR!")
print(f"🔴 DEBUG: Path: {request.url.path}")
print(f"🔴 DEBUG: Errors: {exc.errors()}")
```
**Purpose**: Shows what validation errors occurred (if any)

---

## Test Procedure

### 1. Restart Server
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
# Stop current server (Ctrl+C)
python -m app.main
```

### 2. Test Translation Request from Frontend
- Upload a file
- Click "Upload for Translation"
- **Monitor server console immediately**

### 3. Analyze Debug Output

#### Scenario A: Pydantic Validation Error (Most Likely)
```
Hello World - Logging middleware processing: POST /translate
[RAW REQUEST METADATA] POST /translate...
🔴 DEBUG: PYDANTIC VALIDATION ERROR!
🔴 DEBUG: Path: /translate
🔴 DEBUG: Errors: [...]
```
**What this means**: The JSON payload doesn't match the Pydantic model
**Possible causes**:
- Missing required field
- Wrong data type
- Invalid base64 encoding
- Field name mismatch

**Fix**: Read the error details and adjust either:
- Client payload format
- Server Pydantic model

#### Scenario B: Authentication Hang (MongoDB Issue)
```
Hello World - Logging middleware processing: POST /translate
[RAW REQUEST METADATA] POST /translate...
🟢 DEBUG: get_current_user() INVOKED
🟢 DEBUG: Authorization header present: True
[AUTH MIDDLEWARE  0.00s] START - get_current_user called
[AUTH MIDDLEWARE  0.05s] TOKEN EXTRACTED...
[AUTH MIDDLEWARE  5.00s] CALLING auth_service.verify_session...
... (hangs here for 120 seconds)
```
**What this means**: MongoDB query is timing out
**Possible causes**:
- MongoDB connection lost
- Slow query (missing index)
- Network latency to MongoDB

**Fix**: Check MongoDB connection and optimize queries

#### Scenario C: Endpoint Processing Hang
```
Hello World - Logging middleware processing: POST /translate
[RAW REQUEST METADATA] POST /translate...
🟢 DEBUG: get_current_user() INVOKED
[AUTH MIDDLEWARE ... SUCCESS]
🔵 DEBUG: Endpoint function STARTED
[RAW INCOMING DATA] /translate ENDPOINT REACHED
[TRANSLATE  0.00s] REQUEST RECEIVED
[TRANSLATE  0.05s] FOLDER CREATE START
... (hangs during Google Drive operation)
```
**What this means**: Google Drive API is slow/hanging
**Possible causes**:
- Google Drive API rate limit
- Network latency
- Large file upload taking too long

**Fix**: Optimize Google Drive operations or increase timeout

#### Scenario D: Nothing Appears (Pydantic Parsing Hang)
```
Hello World - Logging middleware processing: POST /translate
[RAW REQUEST METADATA] POST /translate...
... (silence for 120 seconds)
INFO: 408 Request Timeout
```
**What this means**: Pydantic is stuck parsing the JSON body
**This is the CURRENT situation!**
**Possible causes**:
- JSON payload is malformed
- Base64 content is corrupt
- Memory issue with large payload (26KB compressed → could be MBs uncompressed)

**Fix**: See "Immediate Fixes" section below

---

## Immediate Fixes to Try

### Fix 1: Check Payload Size
The client is sending 26KB compressed, but after decompression it could be much larger.

**Check server logs for**:
```
[RAW REQUEST METADATA] Content-Length: 26788 bytes
```

**Then check if decompressed size exceeds FastAPI's limit**:
- Default body size limit: 100MB (should be fine)
- But parsing large JSON can still timeout

### Fix 2: Increase Request Body Size Limit
**File**: `/app/config.py` or `/app/main.py`

Add to FastAPI app creation:
```python
app = FastAPI(
    ...,
    # Increase body size limit
    json_body_max_size=100 * 1024 * 1024,  # 100MB
)
```

### Fix 3: Stream Large Requests
Instead of parsing entire body at once, use streaming:

**File**: `/app/main.py`

Change endpoint to:
```python
from fastapi import UploadFile, File, Form

@app.post("/translate")
async def translate_files(
    files_json: str = Form(...),  # Receive as form field instead of body
    current_user: dict = Depends(get_current_user)
):
    # Parse JSON manually after receiving
    import json
    files_data = json.loads(files_json)
    ...
```

### Fix 4: Use Multipart Form Data (Recommended)
**This eliminates base64 encoding entirely!**

**Client Change** (`api.ts`):
```typescript
async translateRequest(request: TranslateRequest): Promise<TranslateResponse> {
    const formData = new FormData();

    // Add files directly (NO base64)
    request.files.forEach(file => formData.append('files', file));

    // Add metadata
    formData.append('sourceLanguage', request.sourceLanguage);
    formData.append('targetLanguage', request.targetLanguage);
    formData.append('email', request.email);

    const response = await this.client.post('/translate', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000
    });
}
```

**Server Change** (`main.py`):
```python
from fastapi import UploadFile, File, Form

@app.post("/translate")
async def translate_files(
    files: List[UploadFile] = File(...),
    sourceLanguage: str = Form(...),
    targetLanguage: str = Form(...),
    email: str = Form(...),
    current_user: dict = Depends(get_current_user)
):
    # Read file content directly (no base64 decoding needed)
    for file in files:
        content = await file.read()
        # Upload to Google Drive...
```

**Benefits**:
- 33% smaller payload (no base64 overhead)
- Faster parsing (multipart is optimized)
- Lower memory usage
- No timeout issues

---

## Expected Debug Output (After Fixes)

```bash
Hello World - Logging middleware processing: POST /translate
================================================================================
[RAW REQUEST METADATA] POST /translate - Request ID: xxx
[RAW REQUEST METADATA] Content-Type: application/json; charset=UTF-8
[RAW REQUEST METADATA] Content-Length: 26788 bytes
================================================================================
🟢 DEBUG: get_current_user() INVOKED - FastAPI dependency system working
🟢 DEBUG: Authorization header present: True
[AUTH MIDDLEWARE  0.00s] START - get_current_user called
[AUTH MIDDLEWARE  0.15s] SUCCESS - User authenticated: user@example.com
🔵 DEBUG: Endpoint function STARTED - Pydantic validation PASSED
🔵 DEBUG: Received 1 files
🔵 DEBUG: First file name: membership Ольга_Бер (1).docx
====================================================================================================
[RAW INCOMING DATA] /translate ENDPOINT REACHED - Pydantic validation passed
[RAW INCOMING DATA] Files Details:
  File 1: 'membership Ольга_Бер (1).docx' | 13,394 bytes | Type: application/vnd...
====================================================================================================
[TRANSLATE  0.00s] REQUEST RECEIVED
[TRANSLATE  0.05s] VALIDATION COMPLETE - 1 file(s) validated
[TRANSLATE  0.10s] FOLDER CREATED - customer@example.com/Temp/
[TRANSLATE  0.15s] FILE 1 BASE64 DECODED - Decoded 13,394 bytes
[TRANSLATE  0.50s] FILE 1 GDRIVE UPLOADED - File ID: xxx
[TRANSLATE  0.60s] RESPONSE SENDING
====================================================================================================
[RAW OUTGOING DATA] /translate RESPONSE - Sending to client
[RAW OUTGOING DATA] Success: True
====================================================================================================
INFO: 127.0.0.1 - "POST /translate HTTP/1.1" 200 OK
```

---

## Next Steps

1. **Restart server** with new debug logging
2. **Test translation** and observe which debug markers appear
3. **If 🔴 appears**: Fix Pydantic validation error based on error details
4. **If nothing appears**: Implement multipart form data approach (Fix #4)
5. **Report findings** with the debug output so we can identify exact bottleneck

The debug markers will tell us EXACTLY where the request is failing!