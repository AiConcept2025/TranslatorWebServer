# TranslatorWebServer Test Suite

This directory contains all test modules for the TranslatorWebServer project, organized by category and functionality.

## 📁 Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
├── integration/             # Integration tests for component interactions  
├── functional/              # End-to-end functional tests
├── google_drive/           # Google Drive specific tests
├── config/                 # Configuration and setup tests
├── debug/                  # Debug and development helper tests
├── fixtures/               # Test fixtures and mock data
├── conftest.py            # Pytest configuration and shared fixtures
└── run_tests.py           # Test runner script
```

## 🧪 Test Categories

### Unit Tests (`unit/`)
Tests individual components in isolation:
- **`test_configuration.py`** - Configuration loading and validation
- **`test_error_handling.py`** - Error handling and exception management
- **`test_file_operations.py`** - File validation and processing
- **`test_folder_operations.py`** - Folder creation and management
- **`test_google_drive_service.py`** - Google Drive service methods
- **`test_upload_endpoint.py`** - Upload endpoint validation

### Integration Tests (`integration/`)
Tests component interactions:
- **`test_google_drive_integration.py`** - Google Drive API integration

### Functional Tests (`functional/`)
End-to-end workflow tests:
- **`test_upload.py`** - Basic upload functionality
- **`test_correct_upload.py`** - Upload to correct folder structure
- **`test_optional_email_upload.py`** - Optional email parameter testing
- **`test_final_upload_verification.py`** - Complete upload workflow validation

### Google Drive Tests (`google_drive/`)
Google Drive specific functionality:
- **`test_ownership_separation.py`** - File ownership vs folder naming separation
- **`test_metadata_verification.py`** - Language metadata verification
- **`check_google_drive.py`** - Google Drive connectivity and structure check
- **`share_folders.py`** - Folder sharing functionality

### Configuration Tests (`config/`)
Configuration and setup validation:
- **`test_config_changes.py`** - Configuration loading and validation
- **`test_ben_email_verification.py`** - Default email configuration verification

### Debug Tests (`debug/`)
Development and debugging helpers:
- **`debug_test.py`** - VS Code debug configuration verification

## 🚀 Running Tests

### All Tests
```bash
# Run all tests with pytest
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html

# Run with the test runner
python tests/run_tests.py
```

### Specific Test Categories
```bash
# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Functional tests only
python -m pytest tests/functional/ -v

# Google Drive tests only
python -m pytest tests/google_drive/ -v
```

### Individual Test Files
```bash
# Run specific test file
python tests/functional/test_final_upload_verification.py

# Run specific test file with pytest
python -m pytest tests/google_drive/test_ownership_separation.py -v
```

## 🔧 VS Code Integration

### Debug Configurations
Available in VS Code Run and Debug panel:
- **Debug Upload Endpoint Test** - `tests/functional/test_final_upload_verification.py`
- **Debug Google Drive Service** - `tests/google_drive/test_ownership_separation.py`
- **Debug Metadata Verification** - `tests/google_drive/test_metadata_verification.py`
- **Debug Configuration Tests** - `tests/config/test_config_changes.py`
- **Debug Test (Debug Helper)** - `tests/debug/debug_test.py`

### VS Code Tasks
Use **Ctrl+Shift+P** → "Tasks: Run Task":
- **Run Upload Tests**
- **Run Ownership Tests**
- **Run Metadata Tests**
- **Run Configuration Tests**
- **Run Debug Helper Test**
- **Run All Tests**

## 📊 Test Categories by Purpose

### 🔒 Ownership & Security Tests
- `tests/google_drive/test_ownership_separation.py`
- `tests/google_drive/test_metadata_verification.py`

### 📁 File Upload Tests
- `tests/functional/test_upload.py`
- `tests/functional/test_correct_upload.py`
- `tests/functional/test_optional_email_upload.py`
- `tests/functional/test_final_upload_verification.py`

### ⚙️ Configuration Tests
- `tests/config/test_config_changes.py`
- `tests/config/test_ben_email_verification.py`
- `tests/unit/test_configuration.py`

### 🌐 Google Drive Integration Tests
- `tests/google_drive/test_ownership_separation.py`
- `tests/google_drive/test_metadata_verification.py`
- `tests/google_drive/check_google_drive.py`
- `tests/integration/test_google_drive_integration.py`

### 🛠️ Development & Debug Tests
- `tests/debug/debug_test.py`
- `tests/unit/test_error_handling.py`

## 🎯 Test Validation Checklist

### ✅ Core Functionality
- [ ] File upload works correctly
- [ ] Google Drive integration functional
- [ ] Language metadata stored properly
- [ ] Ownership separation working
- [ ] Configuration loading correctly

### ✅ Security & Access Control
- [ ] Files owned by service account only
- [ ] Customer emails used for folder naming only
- [ ] No unauthorized access to files
- [ ] Proper folder structure created

### ✅ Error Handling
- [ ] Invalid file types rejected
- [ ] Authentication errors handled
- [ ] Configuration errors caught
- [ ] Network errors handled gracefully

## 📋 Test Environment Setup

### Prerequisites
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install test dependencies
pip install pytest pytest-asyncio httpx pytest-cov

# Verify configuration
python tests/config/test_config_changes.py
```

### Environment Variables Required
```env
# In .env file
DEFAULT_CUSTOMER_EMAIL=ben.danishevsky@gmail.com
GOOGLE_DRIVE_OWNER_EMAIL=danishevsky@gmail.com
GOOGLE_DRIVE_ENABLED=true
GOOGLE_DRIVE_CREDENTIALS_PATH=./service-account-key.json
GOOGLE_DRIVE_ROOT_FOLDER=IrisSolutions
```

### Google Drive Setup
1. Ensure `service-account-key.json` exists and is valid
2. Verify Google Drive API access
3. Check folder permissions

## 🐛 Debugging Tests

### Debug Individual Tests
1. Open test file in VS Code
2. Set breakpoints
3. Choose appropriate debug configuration
4. Press F5 to start debugging

### Debug Test Failures
```bash
# Run with verbose output
python -m pytest tests/failing_test.py -v -s

# Run with pdb debugger on failure
python -m pytest tests/failing_test.py --pdb

# Run with logging
python -m pytest tests/failing_test.py -v --log-cli-level=DEBUG
```

## 📈 Test Coverage

### Generate Coverage Report
```bash
# Run with coverage
python -m pytest tests/ --cov=app --cov-report=html --cov-report=term

# Open coverage report
open htmlcov/index.html  # On macOS
```

### Coverage Targets
- **Minimum**: 80% overall coverage
- **Critical paths**: 95% coverage (upload, auth, Google Drive)
- **Configuration**: 90% coverage

## 🔄 Continuous Integration

### Pre-commit Checks
```bash
# Format code
python -m black app/ tests/

# Lint code  
python -m flake8 app/ tests/ --max-line-length=120

# Type check
python -m mypy app/ --ignore-missing-imports

# Run all tests
python -m pytest tests/ -v
```

### CI Pipeline
1. Code formatting check
2. Linting check
3. Type checking
4. Unit tests
5. Integration tests
6. Functional tests
7. Coverage report

---

## 📞 Support

For test-related issues:
1. Check test logs and error messages
2. Verify environment setup
3. Run debug helper: `python tests/debug/debug_test.py`
4. Check Google Drive connectivity: `python tests/google_drive/check_google_drive.py`

**Happy Testing! 🧪✅**