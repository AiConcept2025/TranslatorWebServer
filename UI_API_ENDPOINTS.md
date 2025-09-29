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
- Documents: PDF (.pdf), Word (.doc, .docx), RTF (.rtf), Text (.txt) - Max 100MB each
- Images: JPEG (.jpeg, .jpg), PNG (.png), TIFF (.tiff, .tif) - Max 50MB each

**Page Counting Support:**
All uploaded files must support page counting functionality. Files with unsupported formats will be rejected.

**Response:**
```json
{
  "success": true,
  "message": "Upload completed: 1 successful, 0 failed",
  "customer_email": "customer@email.com",
  "target_language": "es",
  "total_files": 1,
  "successful_uploads": 1,
  "failed_uploads": 0,
  "results": [
    {
      "filename": "document.pdf",
      "file_id": "1TV8LYChypfMm0uH7bSNQfs9KD9zI8ReZ",
      "status": "success",
      "message": "File uploaded successfully. Pages: 5",
      "file_size": 1048576,
      "content_type": "application/pdf",
      "google_drive_folder": "1UyC-P8P44GOpJ7w40cLB2_2L3Pc4qDxv",
      "page_count": 5,
      "supports_page_counting": true
    }
  ],
  "google_drive_folder_path": "1UyC-P8P44GOpJ7w40cLB2_2L3Pc4qDxv"
}
```

**Errors:**
- `400` - Invalid request parameters, unsupported file type, file too large, file format not supported for page counting
- `422` - Validation error (invalid email format, missing target_language)
- `500` - Google Drive service error, upload failed

**Error Response Format:**
```json
{
  "success": false,
  "message": "Upload completed: 0 successful, 1 failed",
  "customer_email": "customer@email.com",
  "target_language": "es",
  "total_files": 1,
  "successful_uploads": 0,
  "failed_uploads": 1,
  "results": [
    {
      "filename": "unsupported.xyz",
      "file_id": "",
      "status": "failed",
      "message": "File format not supported for page counting. Supported formats: .doc, .docx, .jpeg, .jpg, .pdf, .png, .rtf, .tiff, .txt",
      "file_size": 1024,
      "content_type": "application/octet-stream",
      "google_drive_folder": null,
      "page_count": null,
      "supports_page_counting": false
    }
  ],
  "google_drive_folder_path": null
}
```

**New Page Counting Features:**
- Each uploaded file is validated for page counting support
- Only files with supported formats (.pdf, .doc, .docx, .txt, .rtf, .png, .jpg, .jpeg, .tiff) are accepted
- Response includes page count for each successfully uploaded file
- Files with unsupported formats are rejected with descriptive error messages

## Base URL
`http://localhost:8000` (development)

## Authentication
None required (service account handles Google Drive access)

## File Access
- Files stored in Google Drive under service account ownership
- Customer email used for folder organization only
- No customer access to uploaded files