# UI API Endpoints

## 1. Get Supported Languages

**Endpoint:** `GET /api/v1/languages/`

**Parameters:** None

**Response:**
```json
{
  "languages": [
    {
      "code": "en",
      "name": "English",
      "native_name": "English"
    },
    {
      "code": "es", 
      "name": "Spanish",
      "native_name": "Español"
    }
  ],
  "total": 42
}
```

**Errors:**
- `500` - Service unavailable

## 2. Upload Files

**Endpoint:** `POST /api/upload`

**Content-Type:** `multipart/form-data`

**Parameters:**
- `customer_email` (optional): string - Customer email (uses default if not provided)
- `target_language` (required): string - Target language code (e.g., "es", "fr", "de")
- `files` (required): File[] - Files to upload

**Supported File Types:**
- Documents: PDF (.pdf), Word (.doc, .docx) - Max 100MB each
- Images: JPEG (.jpeg, .jpg), PNG (.png), TIFF (.tiff, .tif) - Max 50MB each

**Response:**
```json
{
  "success": true,
  "message": "Files uploaded successfully",
  "folder_id": "1UyC-P8P44GOpJ7w40cLB2_2L3Pc4qDxv",
  "folder_path": "IrisSolutions/customer@email.com/Temp",
  "customer_email": "customer@email.com",
  "target_language": "es",
  "uploaded_files": [
    {
      "file_id": "1TV8LYChypfMm0uH7bSNQfs9KD9zI8ReZ",
      "filename": "document.pdf",
      "size": 1048576,
      "status": "uploaded",
      "google_drive_url": "https://drive.google.com/file/d/1TV8LYChypfMm0uH7bSNQfs9KD9zI8ReZ/view",
      "target_language": "es"
    }
  ],
  "failed_files": [],
  "total_uploaded": 1,
  "total_failed": 0
}
```

**Errors:**
- `400` - Invalid request parameters, unsupported file type, file too large
- `422` - Validation error (invalid email format, missing target_language)
- `500` - Google Drive service error, upload failed

**Error Response Format:**
```json
{
  "success": false,
  "error": "Error description",
  "detail": "Detailed error message",
  "failed_files": [
    {
      "filename": "file.txt",
      "error": "Unsupported file type"
    }
  ]
}
```

## Base URL
`http://localhost:8000` (development)

## Authentication
None required (service account handles Google Drive access)

## File Access
- Files stored in Google Drive under service account ownership
- Customer email used for folder organization only
- No customer access to uploaded files