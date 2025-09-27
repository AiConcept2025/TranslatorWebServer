# VS Code Debug Configuration

This document explains how to use the VS Code debugging setup for the TranslatorWebServer project.

## 🚀 Quick Start

1. **Open VS Code** in the project directory
2. **Install recommended extensions** (VS Code will prompt you)
3. **Select Python interpreter**: `./venv/bin/python`
4. **Press F5** or go to Run and Debug panel
5. **Choose a debug configuration** from the dropdown

## 📋 Available Debug Configurations

### 1. **Debug FastAPI App**
- **Purpose**: Debug the main FastAPI application directly
- **Usage**: Direct debugging of `app/main.py`
- **Best for**: Application startup issues, main app logic

### 2. **Debug FastAPI with Uvicorn** ⭐ *Recommended*
- **Purpose**: Debug FastAPI with the Uvicorn server (production-like)
- **Usage**: Full server debugging with hot reload
- **Best for**: API endpoint debugging, request handling
- **Access**: http://localhost:8000 after starting

### 3. **Debug Test Scripts**
- **Purpose**: Debug any Python file currently open
- **Usage**: Select any `.py` file and debug it
- **Best for**: Individual test script debugging

### 4. **Debug Upload Endpoint Test**
- **Purpose**: Debug the complete upload workflow
- **Usage**: Debugs `test_final_upload_verification.py`
- **Best for**: Upload functionality issues

### 5. **Debug Google Drive Service**
- **Purpose**: Debug Google Drive integration
- **Usage**: Debugs `test_ownership_separation.py`
- **Best for**: Google Drive API issues, authentication

### 6. **Debug Metadata Verification**
- **Purpose**: Debug metadata and language handling
- **Usage**: Debugs `test_metadata_verification.py`
- **Best for**: File metadata issues

### 7. **Debug Python File (Current)**
- **Purpose**: Debug currently open Python file with full tracing
- **Usage**: More detailed debugging with `justMyCode: false`
- **Best for**: Deep debugging including external libraries

### 8. **Debug with Pytest**
- **Purpose**: Debug unit tests
- **Usage**: Runs pytest with debugging
- **Best for**: Test suite debugging

### 9. **Debug FastAPI Production Mode**
- **Purpose**: Debug in production-like environment
- **Usage**: No reload, production settings
- **Best for**: Production issue reproduction

## 🔧 Debug Features

### Breakpoints
- **Set breakpoints**: Click in the left margin or press F9
- **Conditional breakpoints**: Right-click breakpoint → Edit Breakpoint
- **Logpoints**: Right-click → Add Logpoint (non-breaking logging)

### Debug Controls
- **F5**: Continue
- **F10**: Step Over
- **F11**: Step Into
- **Shift+F11**: Step Out
- **Ctrl+Shift+F5**: Restart
- **Shift+F5**: Stop

### Debug Views
- **Variables**: See all variable values in current scope
- **Watch**: Monitor specific expressions
- **Call Stack**: View function call hierarchy
- **Debug Console**: Execute code in debug context

## 🎯 Common Debugging Scenarios

### 1. **Debug API Endpoints**
```python
# Set breakpoint in app/routers/upload.py
@router.post("/upload")
async def upload_files(...):
    # Breakpoint here ⬅️
    customer_email = request.customer_email
```

1. Choose "Debug FastAPI with Uvicorn"
2. Set breakpoint in endpoint
3. Make API request to http://localhost:8000/api/upload
4. Debug through the request handling

### 2. **Debug Google Drive Upload**
```python
# Set breakpoint in app/services/google_drive_service.py
async def upload_file_to_folder(...):
    # Breakpoint here ⬅️
    file_metadata = {...}
```

1. Choose "Debug Google Drive Service"
2. Set breakpoint in Google Drive service
3. Step through the upload process

### 3. **Debug Configuration Issues**
```python
# Set breakpoint in app/config.py
class Settings(BaseSettings):
    def __init__(self):
        super().__init__()
        # Breakpoint here ⬅️
```

1. Choose "Debug Test Scripts"
2. Open and run `debug_test.py`
3. Step through configuration loading

### 4. **Debug Async Code**
```python
async def some_async_function():
    # Breakpoint here ⬅️
    await some_operation()
    # Another breakpoint here ⬅️
    return result
```

- VS Code handles async debugging seamlessly
- Use Step Into (F11) to enter async functions
- Watch the call stack for async context

## 🛠️ Debug Configuration Details

### Environment Variables
All debug configurations include:
```json
"env": {
    "PYTHONPATH": "${workspaceFolder}",
    "DEBUG": "true"
}
```

### Python Interpreter
- **Path**: `${workspaceFolder}/venv/bin/python`
- **Virtual Environment**: Automatically activated
- **Working Directory**: Project root

### Debug Output
- **Console**: Integrated Terminal
- **Logging**: Debug level enabled
- **Output**: Redirected to debug console

## 📝 VS Code Tasks

Use **Ctrl+Shift+P** → "Tasks: Run Task" for quick actions:

- **Start FastAPI Development Server**: Launch server without debugging
- **Run Upload Tests**: Execute upload test suite
- **Run Ownership Tests**: Test ownership separation
- **Run Metadata Tests**: Test metadata handling
- **Format Code with Black**: Auto-format code
- **Lint Code with Flake8**: Check code quality
- **Install Dependencies**: Update packages

## 🔍 Troubleshooting

### Common Issues

1. **Python Interpreter Not Found**
   - Solution: Select correct interpreter with `Ctrl+Shift+P` → "Python: Select Interpreter"
   - Choose: `./venv/bin/python`

2. **Import Errors**
   - Solution: Check PYTHONPATH in debug config
   - Ensure working directory is project root

3. **Environment Variables Not Loaded**
   - Solution: Check `.env` file exists
   - Verify `python.envFile` in settings.json

4. **Breakpoints Not Hit**
   - Solution: Ensure `justMyCode: true` for your code only
   - Use `justMyCode: false` for library debugging

5. **Google Drive Authentication Errors**
   - Solution: Check `service-account-key.json` exists and is valid
   - Verify Google Drive API permissions

### Debug Tips

1. **Use Watch Expressions**
   ```python
   # Add to Watch panel:
   settings.default_customer_email
   len(uploaded_files)
   file_info['file_id']
   ```

2. **Debug Console Commands**
   ```python
   # Execute in Debug Console:
   print(customer_email)
   len(files)
   type(google_drive_service)
   ```

3. **Conditional Breakpoints**
   ```python
   # Condition: customer_email == "ben.danishevsky@gmail.com"
   # Hit Count: > 5
   ```

## 🎉 Testing the Setup

Run the debug test to verify everything works:

```bash
# Command line test
python debug_test.py

# Or use VS Code:
# 1. Open debug_test.py
# 2. Choose "Debug Test Scripts"
# 3. Set breakpoints and press F5
```

The test will verify:
- ✅ Basic Python debugging
- ✅ Configuration loading
- ✅ File operations
- ✅ Async functionality
- ✅ Google Drive service initialization

## 📚 Additional Resources

- [VS Code Python Debugging](https://code.visualstudio.com/docs/python/debugging)
- [FastAPI Debugging Guide](https://fastapi.tiangolo.com/tutorial/debugging/)
- [Python Debugger (pdb) Guide](https://docs.python.org/3/library/pdb.html)

---

**Happy Debugging! 🐛🔍**