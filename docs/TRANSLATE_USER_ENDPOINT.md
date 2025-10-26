# `/translate-user` Endpoint Documentation

## Overview

The `/translate-user` endpoint is designed for **individual (non-enterprise) users** who pay per translation. This endpoint handles file uploads, Google Drive storage, and transaction tracking with Square payment integration.

**Key Characteristics:**
- No enterprise/subscription logic
- Fixed pricing: $0.10 per page
- Uses `user_transactions` collection (not `translation_transactions`)
- Requires `userName` field
- Square transaction IDs: `sqt_{20_random_chars}`

---

## Endpoint Details

**URL:** `POST /translate-user`

**Tags:** `Translation`

**Authentication:** None required (public endpoint)

---

## Request Schema

### `TranslateUserRequest`

```json
{
  "files": [
    {
      "id": "string",
      "name": "string",
      "size": 0,
      "type": "string",
      "content": "string (base64-encoded)"
    }
  ],
  "sourceLanguage": "string (ISO 639-1 code)",
  "targetLanguage": "string (ISO 639-1 code)",
  "email": "string (valid email)",
  "userName": "string",
  "paymentIntentId": "string (optional)"
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `files` | Array | Yes | Array of file objects (max 10 files) |
| `files[].id` | String | Yes | Unique client-side file identifier |
| `files[].name` | String | Yes | Original filename with extension |
| `files[].size` | Integer | Yes | File size in bytes |
| `files[].type` | String | Yes | MIME type (e.g., "application/pdf") |
| `files[].content` | String | Yes | Base64-encoded file content |
| `sourceLanguage` | String | Yes | Source language code (e.g., "en") |
| `targetLanguage` | String | Yes | Target language code (e.g., "es") |
| `email` | String | Yes | Valid email address (no disposable domains) |
| `userName` | String | Yes | Full name of the user |
| `paymentIntentId` | String | No | Optional payment intent ID from payment processor |

### Supported Languages

```
en, es, fr, de, it, pt, ru, zh, ja, ko, ar, hi, nl, pl, tr, sv, da, no, fi, th, vi, uk, cs, hu, ro
```

---

## Response Schema

### Success Response (200 OK)

```json
{
  "success": true,
  "data": {
    "id": "store_abc1234567",
    "status": "stored",
    "progress": 100,
    "message": "Files uploaded successfully. Ready for payment.",
    "pricing": {
      "total_units": 10,
      "unit_type": "page",
      "cost_per_unit": 0.10,
      "total_amount": 1.00,
      "currency": "USD"
    },
    "files": {
      "total_files": 2,
      "successful_uploads": 2,
      "failed_uploads": 0,
      "stored_files": [
        {
          "file_id": "gdrive_file_id_123",
          "filename": "document.pdf",
          "status": "stored",
          "page_count": 5,
          "unit_type": "page",
          "size": 250000,
          "google_drive_url": "https://drive.google.com/...",
          "square_transaction_id": "sqt_1ac7fac591b94eeb8c92"
        }
      ]
    },
    "customer": {
      "email": "user@example.com",
      "user_name": "John Doe",
      "temp_folder_id": "gdrive_folder_id"
    },
    "payment": {
      "required": true,
      "amount_cents": 100,
      "customer_email": "user@example.com"
    },
    "square_transaction_ids": [
      "sqt_1ac7fac591b94eeb8c92",
      "sqt_2bd8gbd602c95ffc9d03"
    ]
  },
  "error": null
}
```

### Error Response (4xx/5xx)

```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Validation Rules

### Email Validation
- Must match regex: `^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$`
- Cannot be from disposable domains (tempmail.org, 10minutemail.com, guerrillamail.com)

### Language Validation
- Both source and target must be in the supported languages list
- Source and target languages cannot be the same

### File Validation
- At least 1 file required
- Maximum 10 files per request
- Files must have valid base64-encoded content

---

## Pricing Logic

### Unit Calculation

| File Type | Unit Type | Estimation Formula |
|-----------|-----------|-------------------|
| PDF (.pdf) | page | `max(1, file_size // 50000)` |
| Word (.doc, .docx) | page | `max(1, file_size // 25000)` |
| Images (.png, .jpg, .jpeg, .gif, .bmp) | page | `1` (fixed) |
| Other | page | `max(1, file_size // 50000)` |

### Cost Calculation

```
cost_per_unit = $0.10 (fixed for individual users)
total_amount = total_units × cost_per_unit
amount_cents = int(total_amount × 100)
```

**Example:**
- File 1: 5 pages × $0.10 = $0.50
- File 2: 3 pages × $0.10 = $0.30
- **Total: 8 pages = $0.80 (80 cents)**

---

## Google Drive Folder Structure

### Individual User Structure
```
{user_email}/
├── Temp/           # Files awaiting payment
└── Inbox/          # Files after payment (moved by webhook)
```

**Example:**
```
john.doe@example.com/
├── Temp/
│   ├── document.pdf
│   └── presentation.pptx
└── Inbox/
```

**Note:** No company folder for individual users (unlike enterprise users).

---

## Transaction Records

### Database Collection: `user_transactions`

Each successfully uploaded file creates a transaction record:

```json
{
  "user_name": "John Doe",
  "user_email": "john.doe@example.com",
  "document_url": "https://drive.google.com/...",
  "number_of_units": 5,
  "unit_type": "page",
  "cost_per_unit": 0.10,
  "source_language": "en",
  "target_language": "es",
  "square_transaction_id": "sqt_1ac7fac591b94eeb8c92",
  "date": "2025-10-20T12:34:56Z",
  "status": "processing",
  "total_cost": 0.50,
  "created_at": "2025-10-20T12:34:56Z",
  "updated_at": "2025-10-20T12:34:56Z"
}
```

### Transaction Status Values
- `processing` - Initial status after upload
- `completed` - Translation completed successfully
- `failed` - Translation failed with error

---

## Workflow

1. **Validation**
   - Validate email format and domain
   - Validate language codes
   - Validate file count and content

2. **Google Drive Setup**
   - Create `{user_email}/Temp/` folder structure
   - No company folder (individual user)

3. **File Processing**
   - Decode base64 file content
   - Estimate page count based on file type
   - Upload to Google Drive Temp folder
   - Set file metadata properties

4. **Transaction Creation**
   - Generate Square transaction ID: `sqt_{20_random_chars}`
   - Create record in `user_transactions` collection
   - Link transaction to file via Square ID

5. **Response**
   - Return file metadata
   - Return pricing information
   - Return Square transaction IDs for payment processing

6. **Payment Flow** (handled by frontend/webhook)
   - Frontend processes payment with Square
   - Webhook moves files from Temp to Inbox
   - Webhook updates transaction status to "completed"

---

## Differences from `/translate` Endpoint

| Feature | `/translate` (Enterprise) | `/translate-user` (Individual) |
|---------|---------------------------|-------------------------------|
| Authentication | Required (JWT) | Not required |
| Subscription | Checked for enterprise pricing | No subscription logic |
| Company ID | Required for enterprise | Not used |
| Folder Structure | `CompanyName/user_email/Temp/` | `user_email/Temp/` |
| Pricing | Dynamic (subscription-based) | Fixed ($0.10/page) |
| Database Collection | `translation_transactions` | `user_transactions` |
| Transaction ID Format | `TXN-{10_chars}` | `sqt_{20_chars}` |
| Required Fields | `email`, languages, files | `userName`, `email`, languages, files |
| Payment Check | Checks subscription units | Always requires payment |

---

## Error Responses

### 400 Bad Request

**Invalid Email Format:**
```json
{
  "detail": "Invalid email format"
}
```

**Disposable Email:**
```json
{
  "detail": "Disposable email addresses are not allowed"
}
```

**Invalid Language:**
```json
{
  "detail": "Invalid source language: xx"
}
```

**Same Source/Target:**
```json
{
  "detail": "Source and target languages cannot be the same"
}
```

**No Files:**
```json
{
  "detail": "At least one file is required"
}
```

**Too Many Files:**
```json
{
  "detail": "Maximum 10 files allowed per request"
}
```

**Base64 Decode Error:**
```json
{
  "detail": "Failed to decode file content for 'filename.pdf': ..."
}
```

### 500 Internal Server Error

**Folder Creation Failed:**
```json
{
  "detail": "Failed to create folder structure: ..."
}
```

**Google Drive Error:**
```json
{
  "detail": "Google Drive error: ..."
}
```

---

## Example Request

### Using cURL

```bash
curl -X POST "http://localhost:8000/translate-user" \
  -H "Content-Type: application/json" \
  -d '{
    "files": [
      {
        "id": "file-1",
        "name": "document.pdf",
        "size": 250000,
        "type": "application/pdf",
        "content": "JVBERi0xLjQK..."
      }
    ],
    "sourceLanguage": "en",
    "targetLanguage": "es",
    "email": "john.doe@example.com",
    "userName": "John Doe"
  }'
```

### Using Python (requests)

```python
import base64
import requests

# Read and encode file
with open("document.pdf", "rb") as f:
    file_content = base64.b64encode(f.read()).decode("utf-8")

# Prepare request
url = "http://localhost:8000/translate-user"
payload = {
    "files": [
        {
            "id": "file-1",
            "name": "document.pdf",
            "size": 250000,
            "type": "application/pdf",
            "content": file_content
        }
    ],
    "sourceLanguage": "en",
    "targetLanguage": "es",
    "email": "john.doe@example.com",
    "userName": "John Doe"
}

# Send request
response = requests.post(url, json=payload)
data = response.json()

# Extract Square transaction IDs for payment
square_tx_ids = data["data"]["square_transaction_ids"]
total_amount_cents = data["data"]["payment"]["amount_cents"]

print(f"Upload successful!")
print(f"Total amount: ${total_amount_cents / 100:.2f}")
print(f"Transaction IDs: {square_tx_ids}")
```

### Using JavaScript (fetch)

```javascript
// Read file
const file = document.getElementById('fileInput').files[0];
const reader = new FileReader();

reader.onload = async (e) => {
  const base64Content = btoa(
    new Uint8Array(e.target.result)
      .reduce((data, byte) => data + String.fromCharCode(byte), '')
  );

  // Prepare request
  const payload = {
    files: [
      {
        id: 'file-1',
        name: file.name,
        size: file.size,
        type: file.type,
        content: base64Content
      }
    ],
    sourceLanguage: 'en',
    targetLanguage: 'es',
    email: 'john.doe@example.com',
    userName: 'John Doe'
  };

  // Send request
  const response = await fetch('http://localhost:8000/translate-user', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  const data = await response.json();

  // Process response
  console.log('Upload successful!');
  console.log('Total:', data.data.payment.amount_cents / 100, 'USD');
  console.log('Transaction IDs:', data.data.square_transaction_ids);
};

reader.readAsArrayBuffer(file);
```

---

## Testing

### Unit Tests

```python
import pytest
from app.routers.translate_user import (
    generate_square_transaction_id,
    estimate_page_count,
    get_unit_type
)

def test_generate_square_transaction_id():
    tx_id = generate_square_transaction_id()
    assert tx_id.startswith("sqt_")
    assert len(tx_id) == 24  # "sqt_" + 20 chars

def test_estimate_page_count_pdf():
    count = estimate_page_count("document.pdf", 100000)
    assert count == 2  # 100000 // 50000 = 2

def test_estimate_page_count_image():
    count = estimate_page_count("photo.jpg", 2000000)
    assert count == 1

def test_get_unit_type():
    assert get_unit_type("document.pdf") == "page"
    assert get_unit_type("image.png") == "page"
```

### Integration Tests

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_translate_user_success():
    payload = {
        "files": [
            {
                "id": "test-1",
                "name": "test.pdf",
                "size": 50000,
                "type": "application/pdf",
                "content": "JVBERi0xLjQK..."  # Valid base64
            }
        ],
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "email": "test@example.com",
        "userName": "Test User"
    }

    response = client.post("/translate-user", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["pricing"]["cost_per_unit"] == 0.10
    assert len(data["data"]["square_transaction_ids"]) > 0

@pytest.mark.asyncio
async def test_translate_user_invalid_email():
    payload = {
        "files": [...],
        "sourceLanguage": "en",
        "targetLanguage": "es",
        "email": "invalid-email",
        "userName": "Test User"
    }

    response = client.post("/translate-user", json=payload)
    assert response.status_code == 400
    assert "Invalid email format" in response.json()["detail"]
```

---

## Logging

The endpoint includes comprehensive logging at each step:

```
[TRANSLATE-USER 0.00s] REQUEST RECEIVED - User: John Doe (john.doe@example.com)
[TRANSLATE-USER 0.01s] REQUEST DETAILS - en -> es, Files: 2
[TRANSLATE-USER 0.02s] VALIDATION START - Validating request data
[TRANSLATE-USER 0.03s] VALIDATION PASSED - Languages: en -> es
[TRANSLATE-USER 0.04s] VALIDATION COMPLETE - 2 file(s) validated
[TRANSLATE-USER 0.10s] FOLDER CREATE START - Creating structure for: john.doe@example.com
[TRANSLATE-USER 0.25s] FOLDER CREATED - john.doe@example.com/Temp/ (ID: folder_id_123)
[TRANSLATE-USER 0.30s] FILE 1 UPLOAD START - 'document.pdf' (250,000 bytes)
[TRANSLATE-USER 0.31s] FILE 1 BASE64 DECODED - Decoded 250,000 bytes
[TRANSLATE-USER 0.32s] FILE 1 PAGE COUNT - 5 pages estimated
[TRANSLATE-USER 0.40s] FILE 1 GDRIVE UPLOAD - Uploading to folder folder_id_123
[TRANSLATE-USER 0.80s] FILE 1 GDRIVE UPLOADED - File ID: gdrive_file_id_123
[TRANSLATE-USER 0.85s] FILE 1 METADATA UPDATE - Setting file properties
[TRANSLATE-USER 0.90s] FILE 1 TRANSACTION CREATE - Square ID: sqt_1ac7fac591b94eeb8c92
[TRANSLATE-USER 0.95s] FILE 1 TRANSACTION CREATED - TX ID: sqt_1ac7fac591b94eeb8c92
[TRANSLATE-USER 1.00s] FILE 1 COMPLETE - URL: https://drive.google.com/...
[TRANSLATE-USER 1.50s] RESPONSE PREPARE - Success: 2/2 files, 8 units, $0.80
[TRANSLATE-USER 1.52s] RESPONSE SENDING - Returning response to client
```

---

## Security Considerations

1. **Email Validation**: Prevents disposable email domains
2. **Input Sanitization**: All inputs validated before processing
3. **File Size Limits**: Implicit via base64 encoding overhead
4. **No Sensitive Data Exposure**: Transaction IDs are safe to expose
5. **Google Drive Isolation**: Each user has separate folder structure

---

## Performance Considerations

1. **Base64 Overhead**: ~33% size increase during transmission
2. **Concurrent File Processing**: Files processed sequentially (can be optimized)
3. **Google Drive API Limits**: Subject to Google Drive API quotas
4. **Database Operations**: Each file creates one transaction record

---

## Maintenance Notes

### Configuration
- `cost_per_unit`: Currently hardcoded to $0.10 (consider making configurable)
- Supported languages: Defined in validation function (consider external config)
- Disposable domains: Hardcoded list (consider external blocklist)

### Future Enhancements
- [ ] Parallel file processing for faster uploads
- [ ] Configurable pricing per file type
- [ ] Support for additional file types
- [ ] Enhanced page count estimation (actual PDF parsing)
- [ ] Rate limiting per email address
- [ ] WebSocket progress updates during upload

---

## Related Endpoints

- `POST /translate` - Enterprise translation endpoint (with subscriptions)
- `POST /payment/webhook` - Payment webhook (moves files from Temp to Inbox)
- `GET /languages` - List supported languages

---

## Support

For issues or questions:
- Check logs for detailed error messages
- Verify Google Drive service configuration
- Verify MongoDB connection and `user_transactions` collection
- Check Square API integration for payment processing

---

**Last Updated:** 2025-10-20
**Version:** 1.0.0
**File:** `/Users/vladimirdanishevsky/projects/Translator/server/app/routers/translate_user.py`
