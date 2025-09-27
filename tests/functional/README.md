# Functional Tests

End-to-end workflow tests that verify complete functionality from user input to final result.

## 📋 Test Files

### `test_upload.py`
**Purpose**: Basic upload functionality test
- Tests basic file upload to Google Drive
- Verifies folder structure creation
- Validates file metadata storage

**Usage**:
```bash
python tests/functional/test_upload.py
```

### `test_correct_upload.py`
**Purpose**: Upload to correct folder structure
- Tests upload to IrisSolutions folder
- Verifies service account authentication
- Checks folder hierarchy creation

**Usage**:
```bash
python tests/functional/test_correct_upload.py
```

### `test_optional_email_upload.py`
**Purpose**: Optional email parameter testing
- Tests upload with and without customer email
- Verifies default email configuration usage
- Validates model validation logic

**Usage**:
```bash
python tests/functional/test_optional_email_upload.py
```

### `test_final_upload_verification.py` ⭐ **Primary Test**
**Purpose**: Complete upload workflow validation
- Tests multiple customer scenarios
- Verifies ownership separation
- Validates complete end-to-end workflow
- Tests different target languages

**Features Tested**:
- ✅ File ownership by service account
- ✅ Folder naming by customer email
- ✅ Language metadata storage
- ✅ Multiple customer scenarios
- ✅ Access control verification

**Usage**:
```bash
python tests/functional/test_final_upload_verification.py
```

## 🎯 What These Tests Validate

### Upload Process
1. **File Reception**: API receives files correctly
2. **Validation**: File types and sizes validated
3. **Authentication**: Google Drive access works
4. **Folder Creation**: Proper folder structure created
5. **File Upload**: Files uploaded to correct location
6. **Metadata Storage**: Language and customer info stored
7. **Access Control**: Ownership and permissions correct

### Customer Scenarios
- Default customer (ben.danishevsky@gmail.com)
- Custom customers (various email domains)
- Multiple uploads from same customer
- Different target languages

### Error Handling
- Invalid file types
- Missing configuration
- Authentication failures
- Network issues

## 🚀 Running Functional Tests

### All Functional Tests
```bash
python -m pytest tests/functional/ -v
```

### Individual Tests
```bash
# Basic upload
python tests/functional/test_upload.py

# Correct folder structure
python tests/functional/test_correct_upload.py

# Optional email handling
python tests/functional/test_optional_email_upload.py

# Complete workflow (recommended)
python tests/functional/test_final_upload_verification.py
```

### Debug Mode
Use VS Code debug configuration:
- **Debug Upload Endpoint Test** - Primary functional test

## 📊 Expected Results

### Successful Test Run
```
🎉 ALL TESTS PASSED! Upload workflow working perfectly!
✅ Ownership separation implemented correctly
✅ ben.danishevsky@gmail.com used as default customer
✅ Files owned by danishevsky@gmail.com (service account)
✅ Folders named by customer email for organization
```

### Test Coverage
- Multiple customer emails tested
- Different target languages (es, fr, de)
- Various file types (.md files)
- Complete folder structure verification

## 🔍 Troubleshooting

### Common Issues

1. **Google Drive Authentication**
   ```
   Solution: Check service-account-key.json file
   ```

2. **Folder Access Issues**
   ```
   Solution: Verify Google Drive API permissions
   ```

3. **Configuration Problems**
   ```
   Solution: Run tests/config/test_config_changes.py first
   ```

### Debug Steps
1. Check configuration: `python tests/config/test_config_changes.py`
2. Test Google Drive: `python tests/google_drive/check_google_drive.py`
3. Run debug helper: `python tests/debug/debug_test.py`
4. Then run functional tests

## 📋 Functional Test Checklist

Before running functional tests, ensure:
- [ ] Virtual environment activated
- [ ] Configuration files present (.env, service-account-key.json)
- [ ] Google Drive API access working
- [ ] Internet connection available
- [ ] Required permissions granted

After running tests, verify:
- [ ] Files uploaded to Google Drive
- [ ] Correct folder structure created
- [ ] Proper file ownership
- [ ] Language metadata stored
- [ ] No access granted to customer emails

---

**These tests validate the complete user workflow from file upload to Google Drive storage with proper security and organization.** 🎯✅