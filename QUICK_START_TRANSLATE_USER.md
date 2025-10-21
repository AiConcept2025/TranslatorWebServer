# Quick Start: `/translate-user` Endpoint

## Overview
Individual user translation endpoint (non-enterprise) with fixed pricing and Square payment integration.

---

## Endpoint
```
POST /translate-user
```

---

## Request Example

```json
{
  "files": [
    {
      "id": "file-1",
      "name": "document.pdf",
      "size": 250000,
      "type": "application/pdf",
      "content": "JVBERi0xLjQK..."  // base64-encoded
    }
  ],
  "sourceLanguage": "en",
  "targetLanguage": "es",
  "email": "john.doe@example.com",
  "userName": "John Doe"
}
```

---

## Response Example

```json
{
  "success": true,
  "data": {
    "id": "store_abc123",
    "status": "stored",
    "progress": 100,
    "message": "Files uploaded successfully. Ready for payment.",
    "pricing": {
      "total_units": 5,
      "unit_type": "page",
      "cost_per_unit": 0.10,
      "total_amount": 0.50,
      "currency": "USD"
    },
    "files": {
      "total_files": 1,
      "successful_uploads": 1,
      "failed_uploads": 0,
      "stored_files": [
        {
          "file_id": "gdrive_123",
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
      "email": "john.doe@example.com",
      "user_name": "John Doe",
      "temp_folder_id": "folder_id"
    },
    "payment": {
      "required": true,
      "amount_cents": 50,
      "customer_email": "john.doe@example.com"
    },
    "square_transaction_ids": ["sqt_1ac7fac591b94eeb8c92"]
  }
}
```

---

## cURL Test

```bash
curl -X POST "http://localhost:8000/translate-user" \
  -H "Content-Type: application/json" \
  -d '{
    "files": [{
      "id": "test-1",
      "name": "test.pdf",
      "size": 100000,
      "type": "application/pdf",
      "content": "JVBERi0xLjQK..."
    }],
    "sourceLanguage": "en",
    "targetLanguage": "es",
    "email": "test@example.com",
    "userName": "Test User"
  }'
```

---

## Key Features

- ✅ **Fixed Pricing:** $0.10 per page
- ✅ **No Authentication:** Public endpoint
- ✅ **Square Integration:** Transaction IDs for payment
- ✅ **Google Drive:** Files stored in `{email}/Temp/`
- ✅ **MongoDB:** Transactions in `user_transactions` collection
- ✅ **Max Files:** 10 per request
- ✅ **Supported Languages:** 25 languages (en, es, fr, de, etc.)

---

## Pricing

| File Type | Estimation |
|-----------|-----------|
| PDF | size ÷ 50KB = pages |
| Word (.doc, .docx) | size ÷ 25KB = pages |
| Images | 1 page (fixed) |

**Example:** 250KB PDF = 5 pages × $0.10 = **$0.50**

---

## Validation

### Email
- Must be valid format
- No disposable domains (tempmail.org, etc.)

### Languages
- Must be in supported list: `en, es, fr, de, it, pt, ru, zh, ja, ko, ar, hi, nl, pl, tr, sv, da, no, fi, th, vi, uk, cs, hu, ro`
- Source ≠ Target

### Files
- 1-10 files per request
- Must have base64-encoded content

---

## Errors

| Status | Error | Cause |
|--------|-------|-------|
| 400 | Invalid email format | Bad email regex |
| 400 | Disposable email addresses not allowed | Blocked domain |
| 400 | Invalid source/target language | Unsupported code |
| 400 | Source and target cannot be same | Same language |
| 400 | At least one file required | Empty files array |
| 400 | Maximum 10 files allowed | Too many files |
| 400 | Failed to decode file content | Bad base64 |
| 500 | Failed to create folder structure | Google Drive error |

---

## Workflow

```
1. Upload files → /translate-user
2. Get pricing + Square IDs
3. Process payment via Square
4. Webhook moves files Temp → Inbox
5. Translation starts automatically
```

---

## Files

- **Router:** `/server/app/routers/translate_user.py`
- **Docs:** `/server/docs/TRANSLATE_USER_ENDPOINT.md`
- **Tests:** `/server/tests/test_translate_user.py`
- **Summary:** `/server/TRANSLATE_USER_IMPLEMENTATION.md`

---

## Testing

```bash
# Start server
uvicorn app.main:app --reload

# Run tests
pytest tests/test_translate_user.py -v

# View API docs
open http://localhost:8000/docs
```

---

## Database

**Collection:** `user_transactions`

**Key Fields:**
- `user_name`, `user_email`
- `square_transaction_id` (unique)
- `document_url` (Google Drive)
- `number_of_units`, `unit_type`, `cost_per_unit`
- `source_language`, `target_language`
- `status` ("processing", "completed", "failed")
- `total_cost`, `created_at`, `updated_at`

---

## Help

📖 **Full Documentation:** `/server/docs/TRANSLATE_USER_ENDPOINT.md`
🔧 **Implementation Details:** `/server/TRANSLATE_USER_IMPLEMENTATION.md`
🧪 **Tests:** `/server/tests/test_translate_user.py`
💻 **Source Code:** `/server/app/routers/translate_user.py`

---

**Ready to use!** 🚀
