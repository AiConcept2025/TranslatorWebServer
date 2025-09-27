# Google Drive Integration Setup

This document provides comprehensive instructions for setting up Google Drive integration with the TranslatorWebServer.

## Overview

The Google Drive integration allows the TranslatorWebServer to:
- Create organized folder structures for each customer
- Upload files directly to Google Drive
- Store file metadata including target languages
- Manage files with proper permissions and organization

**Important:** This integration requires Google Drive and will fail if Google Drive is unavailable. There is no local storage fallback.

## Quick Start

1. **Run the setup script:**
   ```bash
   python setup_google_drive.py
   ```
   This will guide you through the entire setup process.

2. **Follow the instructions** provided by the setup script.

3. **Test the integration** using the FastAPI endpoint.

## Detailed Setup Instructions

### Step 1: Google Cloud Console Setup

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   - Sign in with your Google account

2. **Create or Select Project**
   - Create a new project or select an existing one
   - Note the project name/ID for reference

3. **Enable Google Drive API**
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click on "Google Drive API" in the results
   - Click "Enable"

### Step 2: Create OAuth 2.0 Credentials

1. **Go to Credentials**
   - Navigate to "APIs & Services" > "Credentials"

2. **Create OAuth Client ID**
   - Click "+ CREATE CREDENTIALS"
   - Select "OAuth client ID"
   - Choose "Desktop application" as application type
   - Give it a name (e.g., "TranslatorWebServer")

3. **Download Credentials**
   - After creation, click the download button (⬇️)
   - Save the JSON file as `credentials.json`
   - Place it in your project root directory

### Step 3: Configure Application

1. **Update Environment Variables**
   Create or update your `.env` file:
   ```env
   # Google Drive Configuration
   GOOGLE_DRIVE_ENABLED=true
   GOOGLE_DRIVE_CREDENTIALS_PATH=./credentials.json
   GOOGLE_DRIVE_TOKEN_PATH=./token.json
   GOOGLE_DRIVE_ROOT_FOLDER=TranslatorWebServer
   GOOGLE_DRIVE_APPLICATION_NAME=TranslatorWebServer
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Step 4: First-Time Authentication

1. **Run the setup script:**
   ```bash
   python setup_google_drive.py
   ```

2. **Complete OAuth Flow**
   - The script will open a browser window
   - Sign in to Google and grant permissions
   - The script will save the token automatically

3. **Verify Setup**
   - The script will create a test folder structure
   - Check your Google Drive for the "TranslatorWebServer" folder

## API Usage

### Upload Files Endpoint

**Endpoint:** `POST /api/upload`

**Parameters:**
- `customer_email` (Form): Customer's email address
- `target_language` (Form): Target language code (e.g., "es", "fr", "de")
- `files` (File): One or more files to upload

**Supported File Types:**
- **Documents:** PDF (.pdf), Word (.doc, .docx) - Max 100MB each
- **Images:** JPEG (.jpeg, .jpg), PNG (.png), TIFF (.tiff, .tif) - Max 50MB each

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/api/upload" \
  -F "customer_email=john@example.com" \
  -F "target_language=es" \
  -F "files=@document.pdf" \
  -F "files=@image.jpg"
```

**Response Format:**
```json
{
  "success": true,
  "message": "Upload completed: 2 successful, 0 failed",
  "customer_email": "john@example.com",
  "target_language": "es",
  "total_files": 2,
  "successful_uploads": 2,
  "failed_uploads": 0,
  "results": [
    {
      "filename": "document.pdf",
      "file_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
      "status": "success",
      "message": "File uploaded successfully",
      "file_size": 1024000,
      "content_type": "application/pdf",
      "google_drive_folder": "folder_id_here"
    }
  ],
  "google_drive_folder_path": "folder_id_here"
}
```

## Folder Structure

The service creates the following folder structure in Google Drive:

```
TranslatorWebServer/
├── customer1@example.com/
│   └── Temp/
│       ├── uploaded_file1.pdf
│       └── uploaded_file2.jpg
├── customer2@example.com/
│   └── Temp/
│       └── uploaded_file3.docx
```

## File Metadata

Each uploaded file includes metadata:
- **target_language**: The target language for translation
- **customer_email**: Customer's email address
- **upload_timestamp**: When the file was uploaded
- **file_size**: Size of the file in bytes
- **content_type**: MIME type of the file

## Security Features

1. **File Validation:**
   - Magic number (file signature) validation
   - File size limits (100MB documents, 50MB images)
   - Content type verification
   - Executable file rejection

2. **Access Control:**
   - OAuth 2.0 authentication
   - Limited API scopes (`drive.file`, `drive.metadata`)
   - Customer-specific folder isolation

3. **Error Handling:**
   - **Google Drive Only:** No local fallback, returns errors if Google Drive fails
   - Comprehensive error messages with retry recommendations
   - Quota exceeded handling with proper HTTP status codes
   - Network error recovery with detailed failure information
   - Authentication failure handling with setup instructions

## Troubleshooting

### Common Issues

1. **"Credentials file not found"**
   - Ensure `credentials.json` is in the correct location
   - Check file permissions (should be readable)
   - Verify the path in configuration

2. **"Authentication failed"**
   - Delete `token.json` and re-authenticate
   - Check Google Cloud Console for API quotas
   - Verify OAuth client is not restricted

3. **"Google Drive quota exceeded"**
   - Check Google Drive storage limits
   - Monitor API usage quotas in Google Cloud Console
   - Consider implementing retry logic with exponential backoff

4. **"Permission denied"**
   - Verify API scopes in configuration
   - Check OAuth client permissions
   - Ensure Google Drive API is enabled

### Debug Mode

Enable debug logging by setting:
```env
LOG_LEVEL=DEBUG
```

This will provide detailed information about Google Drive operations.

### Disabling Google Drive

**Warning:** Disabling Google Drive will cause upload operations to fail since there is no local storage fallback.

To disable Google Drive integration:
```env
GOOGLE_DRIVE_ENABLED=false
```

This will cause the service to raise a `GoogleDriveStorageError` on initialization.

## API Quotas and Limits

Google Drive API has the following limits:
- **Queries per day:** 1,000,000,000
- **Queries per 100 seconds per user:** 1,000
- **Queries per 100 seconds:** 10,000

Monitor usage in Google Cloud Console under "APIs & Services" > "Quotas".

## Production Deployment

For production deployment:

1. **Use Service Account** (recommended for server applications)
2. **Implement proper logging and monitoring**
3. **Configure proper error handling and retry policies**
4. **Monitor API quotas and usage**
5. **Ensure Google Drive reliability** - consider backup authentication methods
6. **Set up monitoring for Google Drive API status**

## Support

For issues with Google Drive integration:
1. Check the setup script output
2. Review application logs
3. Verify Google Cloud Console configuration
4. Test with the provided curl examples

## Security Notes

- Never commit `credentials.json` or `token.json` to version control
- Use environment variables for sensitive configuration
- Regularly rotate OAuth credentials
- Monitor access logs for unusual activity
- Implement proper backup and recovery procedures