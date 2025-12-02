# Integration Tests - Real Server + Real Database

## ⚠️ CRITICAL: How to Run Integration Tests

Integration tests MUST run against a **real running webserver** and **real test database**.

### Setup

**Terminal 1: Start Test Server**
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
```

**Terminal 2: Run Tests**
```bash
cd /Users/vladimirdanishevsky/projects/Translator/server
pytest tests/integration/test_pricing_api_integration.py -v
```

### What These Tests Do

✅ **CORRECT Integration Testing:**
- Use `httpx.AsyncClient` to make real HTTP requests
- POST to actual API endpoints like `/translate`, `/translate-user`
- Verify HTTP responses (status codes, JSON structure)
- Verify database state in `translation_test` database
- Test full stack: HTTP → routing → middleware → validation → business logic → database

❌ **WRONG (Deprecated) Approach:**
- Direct function imports: `from app.pricing.pricing_calculator import ...`
- Calling functions directly: `calculate_individual_price(...)`
- Bypasses HTTP layer, routing, middleware, serialization

### Test Files

- ✅ **`test_pricing_api_integration.py`** - NEW, correct API integration tests
- ❌ **`test_pricing_integration_DEPRECATED.py`** - OLD, violates testing rule (kept for reference only)

### Why This Matters

Real API integration tests catch issues that direct function tests miss:
1. **HTTP Serialization Issues** - JSON encoding/decoding, datetime formatting
2. **Middleware Problems** - CORS, authentication, rate limiting
3. **Routing Issues** - Incorrect paths, missing route parameters
4. **Request Validation** - Pydantic models with `extra='forbid'`
5. **Response Structure** - Actual API response format vs internal function returns

### Example Test Structure

```python
@pytest.mark.asyncio
async def test_pricing_endpoint(http_client, test_db, test_pdf_file):
    # ARRANGE: Prepare request
    with open(test_pdf_file, 'rb') as f:
        file_content = f.read()

    files = {'files': ('test.pdf', file_content, 'application/pdf')}
    data = {
        'sourceLanguage': 'en',
        'targetLanguage': 'es',
        'email': 'test@test.com',
        'translation_mode': 'default'
    }

    # ACT: Real HTTP POST to running server
    response = await http_client.post(
        "/translate",
        json=data
    )

    # ASSERT: Verify HTTP response
    assert response.status_code == 200
    response_data = response.json()
    assert "pricing" in response_data

    # VERIFY: Check real test database
    transaction = await test_db.translation_transactions.find_one({
        "email": "test@test.com"
    })
    assert transaction is not None
    assert transaction["price"] > 0
```

### Troubleshooting

**"Server not running" error:**
- Make sure Terminal 1 is running the server
- Check server is on port 8000: `curl http://localhost:8000/health`
- Verify DATABASE_MODE=test is set

**"Connection refused" error:**
- Server not started
- Wrong port number
- Firewall blocking localhost:8000

**Tests skip automatically:**
- The test fixture checks if server is running
- If server not available, tests skip gracefully with message
- This prevents false failures when server isn't started

### Database Cleanup

Tests automatically clean up after themselves:
- Remove test records with `TEST_` prefix
- Remove test user transactions with `test.*@test.com` emails
- Uses real `translation_test` database (NOT production)

### Adding New Integration Tests

1. Always use `http_client` fixture for HTTP requests
2. Always use `test_db` fixture for database verification
3. Test format: HTTP request → assert response → verify database
4. Clean up test data in fixture or test teardown
5. Skip gracefully if server not running

## References

- **CRITICAL RULE #0** in `server/CLAUDE.md` - Mandatory testing requirements
- **Section: Real Integration Testing** in `server/CLAUDE.md` - Detailed guidelines
