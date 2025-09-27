# Google Drive Tests

Tests specifically focused on Google Drive integration, authentication, file operations, and access control.

## 📋 Test Files

### `test_ownership_separation.py` ⭐ **Critical Test**
**Purpose**: Verify ownership and folder naming separation
- Tests that files are owned by service account only
- Verifies folders are named after customer emails
- Ensures customers have NO access to files
- Tests multiple customer scenarios

**Key Validations**:
- ✅ Service account is file owner
- ✅ Customer is NOT file owner
- ✅ Folder named after customer email
- ✅ Customer has NO file access
- ✅ Proper folder hierarchy created

**Usage**:
```bash
python tests/google_drive/test_ownership_separation.py
```

### `test_metadata_verification.py`
**Purpose**: Language metadata verification
- Tests that language identifiers are stored as metadata
- Verifies different target languages (es, fr, de)
- Checks metadata retrieval from Google Drive API
- Validates existing uploaded files

**Features Tested**:
- ✅ Target language metadata storage
- ✅ Upload timestamp metadata
- ✅ Original filename metadata
- ✅ File description with language info
- ✅ Metadata retrieval and verification

**Usage**:
```bash
python tests/google_drive/test_metadata_verification.py
```

### `check_google_drive.py`
**Purpose**: Google Drive connectivity and structure verification
- Checks Google Drive service initialization
- Verifies folder structure and links
- Lists files and provides access URLs
- Validates configuration settings

**Features**:
- 🔍 Service account authentication check
- 📂 Folder structure verification
- 🔗 Direct Google Drive links
- 📊 File count and size statistics

**Usage**:
```bash
python tests/google_drive/check_google_drive.py
```

### `share_folders.py`
**Purpose**: Folder sharing functionality (legacy)
- Shares folders with specific email addresses
- Used for troubleshooting access issues
- Provides folder permissions management

**Note**: This is primarily for debugging access issues and is not part of the main workflow.

**Usage**:
```bash
python tests/google_drive/share_folders.py
```

## 🎯 What These Tests Validate

### Authentication & Access
1. **Service Account Auth**: Proper authentication with Google Drive API
2. **Permissions**: Correct file and folder permissions
3. **Access Control**: Customer emails have no file access
4. **API Connectivity**: Google Drive API calls work correctly

### File Operations
1. **File Upload**: Files uploaded to correct locations
2. **Metadata Storage**: Language and timestamp metadata stored
3. **Folder Creation**: Proper folder hierarchy created
4. **File Ownership**: Service account owns all files

### Security Model
1. **Ownership Separation**: Files owned by service account, not customers
2. **Folder Organization**: Customer emails used for folder naming only
3. **Access Restriction**: Customers cannot access files
4. **Permission Model**: Only authorized users have access

## 🚀 Running Google Drive Tests

### All Google Drive Tests
```bash
python -m pytest tests/google_drive/ -v
```

### Individual Tests
```bash
# Ownership separation (critical)
python tests/google_drive/test_ownership_separation.py

# Metadata verification
python tests/google_drive/test_metadata_verification.py

# Connectivity check
python tests/google_drive/check_google_drive.py

# Folder sharing (if needed)
python tests/google_drive/share_folders.py
```

### Debug Mode
Use VS Code debug configurations:
- **Debug Google Drive Service** - Ownership separation test
- **Debug Metadata Verification** - Metadata test

## 📊 Expected Results

### Ownership Separation Test
```
📊 OWNERSHIP SEPARATION TEST SUMMARY
============================================================
Total test cases: 4
✅ PASSED: 4
❌ FAILED: 0

✅ PASS Test 1: ben.danishevsky@gmail.com
✅ PASS Test 2: alice@company.com
✅ PASS Test 3: bob@startup.io
✅ PASS Test 4: charlie@enterprise.org
```

### Metadata Verification Test
```
📊 METADATA VERIFICATION SUMMARY
============================================================
Total test cases: 3
✅ PASSED: 3
❌ FAILED: 0
🔥 ERRORS: 0
```

### Google Drive Check
```
📂 You can now access these folders:
✅ IrisSolutions (Root)
✅ Customer folder (ben.danishevsky@gmail.com)
✅ Temp folder (with files)
```

## 🔍 Google Drive Configuration

### Required Settings
```env
# .env file
GOOGLE_DRIVE_ENABLED=true
GOOGLE_DRIVE_CREDENTIALS_PATH=./service-account-key.json
GOOGLE_DRIVE_ROOT_FOLDER=IrisSolutions
DEFAULT_CUSTOMER_EMAIL=ben.danishevsky@gmail.com
GOOGLE_DRIVE_OWNER_EMAIL=danishevsky@gmail.com
```

### Service Account Setup
1. **Credentials File**: `service-account-key.json` must exist
2. **API Access**: Google Drive API enabled
3. **Permissions**: Service account has drive access
4. **Scopes**: Full drive scope (`https://www.googleapis.com/auth/drive`)

## 🛠️ Troubleshooting

### Authentication Issues
```bash
# Check service account file
ls -la service-account-key.json

# Verify JSON format
python -c "import json; print(json.load(open('service-account-key.json'))['type'])"
```

### Connectivity Issues
```bash
# Test basic connectivity
python tests/google_drive/check_google_drive.py

# Check configuration
python tests/config/test_config_changes.py
```

### Permission Issues
```bash
# Check ownership
python tests/google_drive/test_ownership_separation.py

# Verify folder structure
python tests/google_drive/check_google_drive.py
```

### Common Errors

1. **"Service account credentials not found"**
   - Solution: Ensure `service-account-key.json` exists and is valid

2. **"Insufficient permissions"**
   - Solution: Check Google Drive API permissions for service account

3. **"Folder not found"**
   - Solution: Verify folder structure and permissions

4. **"Authentication failed"**
   - Solution: Check service account key format and validity

## 📋 Google Drive Test Checklist

### Pre-test Requirements
- [ ] Service account credentials file exists
- [ ] Google Drive API enabled
- [ ] Internet connectivity available
- [ ] Configuration variables set
- [ ] Virtual environment activated

### Test Validation Points
- [ ] Service account authentication works
- [ ] Folders created with customer email names
- [ ] Files owned by service account only
- [ ] Language metadata stored correctly
- [ ] Customer emails have no file access
- [ ] Folder hierarchy correct (IrisSolutions/customer/Temp)

### Post-test Verification
- [ ] Files visible in Google Drive web interface
- [ ] Correct folder structure created
- [ ] Metadata accessible via API
- [ ] No unauthorized access granted
- [ ] All test cases passed

## 📈 Security Model Validation

The Google Drive tests specifically validate this security model:

```
┌─────────────────────────────────────────────────────────┐
│                    Security Model                       │
├─────────────────────────────────────────────────────────┤
│ File Owner:     danishevsky@gmail.com (service account) │
│ File Access:    Authorized users only                   │
│ Folder Names:   Customer emails (ben.danishevsky@...)   │
│ Customer Access: None (organization only)               │
│ Folder Path:    IrisSolutions/{customer_email}/Temp/    │
└─────────────────────────────────────────────────────────┘
```

This ensures:
- **🔒 Security**: Files are owned by the service account, not customers
- **📁 Organization**: Folders clearly organized by customer email
- **🚫 Access Control**: Customers cannot access files
- **🔑 Authentication**: Only authorized users can access files

---

**These tests ensure the Google Drive integration works securely and correctly with proper ownership separation.** 🔐✅