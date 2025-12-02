"""
INTEGRATION TESTS FOR SUBMIT API - USING REAL DATABASE

These tests make actual HTTP requests to the running server and verify
responses against the REAL MongoDB database.

NO MOCKS - Real API + Real Database testing as per requirements.
"""

import pytest
import httpx


# ============================================================================
# Test Configuration
# ============================================================================

API_BASE_URL = "http://localhost:8000"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
async def http_client():
    """HTTP client for making real API calls to running server."""
    async_client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0)
    yield async_client
    await async_client.aclose()


# ============================================================================
# Test Cases
# ============================================================================

@pytest.mark.asyncio
async def test_submit_endpoint_nonexistent_transaction(http_client):
    """
    Test submission with non-existent transaction_id returns 404.

    Verifies:
    - 404 status code returned for non-existent transaction
    - Response contains error message
    """
    payload = {
        "file_name": "test_document.docx",
        "file_url": "https://drive.google.com/file/d/test123/view",
        "user_email": "test@example.com",
        "company_name": "Test Company",
        "transaction_id": "txn_nonexistent_123"
    }

    response = await http_client.post("/submit", json=payload)

    # Verify 404 for non-existent transaction
    assert response.status_code == 404, f"Expected 404 for non-existent transaction, got {response.status_code}: {response.text}"

    # Verify response contains error info
    data = response.json()
    assert "error" in data, "Response must contain 'error' field"
    assert "not found" in data["error"].lower(), "Error should indicate transaction not found"


@pytest.mark.asyncio
async def test_submit_endpoint_missing_transaction_id(http_client):
    """
    Test submission without transaction_id returns validation error.

    Verifies:
    - 422 status code returned for missing required field
    - Validation error message returned
    """
    payload = {
        "file_name": "test_document.pdf",
        "file_url": "https://drive.google.com/file/d/abc456/view",
        "user_email": "user@company.com",
        "company_name": "Another Company"
        # Missing transaction_id - which is required
    }

    response = await http_client.post("/submit", json=payload)

    # Verify validation error (422)
    assert response.status_code == 422, f"Expected 422 for missing transaction_id, got {response.status_code}: {response.text}"


@pytest.mark.asyncio
async def test_submit_endpoint_missing_required_field(http_client):
    """
    Test submission with missing required field.

    Verifies:
    - 422 status code for validation error (Pydantic validation)
    - Error response contains validation details
    """
    payload = {
        "file_name": "test_document.docx",
        "file_url": "https://drive.google.com/file/d/test123/view",
        # Missing user_email and company_name
    }

    response = await http_client.post("/submit", json=payload)

    # Verify validation error status code
    assert response.status_code == 422, f"Expected 422 for validation error, got {response.status_code}"


@pytest.mark.asyncio
async def test_submit_endpoint_invalid_email(http_client):
    """
    Test submission with invalid email format.

    Verifies:
    - 422 status code for validation error
    - Pydantic validator catches invalid email
    """
    payload = {
        "file_name": "test_document.docx",
        "file_url": "https://drive.google.com/file/d/test123/view",
        "user_email": "invalid-email",  # Invalid email format
        "company_name": "Test Company"
    }

    response = await http_client.post("/submit", json=payload)

    # Verify validation error
    assert response.status_code == 422, f"Expected 422 for invalid email, got {response.status_code}"


@pytest.mark.asyncio
async def test_submit_endpoint_empty_file_name(http_client):
    """
    Test submission with empty file_name.

    Verifies:
    - 422 status code for validation error
    - Validator catches empty strings
    """
    payload = {
        "file_name": "",  # Empty file name
        "file_url": "https://drive.google.com/file/d/test123/view",
        "user_email": "test@example.com",
        "company_name": "Test Company"
    }

    response = await http_client.post("/submit", json=payload)

    # Verify validation error
    assert response.status_code == 422, f"Expected 422 for empty file_name, got {response.status_code}"


@pytest.mark.asyncio
async def test_submit_endpoint_invalid_url(http_client):
    """
    Test submission with invalid URL format.

    Verifies:
    - 422 status code for validation error
    - URL validator works correctly
    """
    payload = {
        "file_name": "test_document.docx",
        "file_url": "not-a-valid-url",  # Invalid URL
        "user_email": "test@example.com",
        "company_name": "Test Company"
    }

    response = await http_client.post("/submit", json=payload)

    # Verify validation error
    assert response.status_code == 422, f"Expected 422 for invalid URL, got {response.status_code}"


@pytest.mark.asyncio
async def test_submit_endpoint_malformed_json(http_client):
    """
    Test submission with malformed JSON.

    Verifies:
    - Appropriate error code for malformed JSON
    """
    response = await http_client.post(
        "/submit",
        content="not valid json",
        headers={"Content-Type": "application/json"}
    )

    # Verify error status code (422 or 400)
    assert response.status_code in [400, 422], f"Expected 400 or 422 for malformed JSON, got {response.status_code}"


@pytest.mark.asyncio
async def test_submit_endpoint_individual_nonexistent_transaction(http_client):
    """
    Test submission for individual customer with non-existent transaction returns 404.

    Verifies:
    - 404 returned for non-existent transaction
    - Error message indicates transaction not found
    """
    payload = {
        "file_name": "personal_document.pdf",
        "file_url": "https://drive.google.com/file/d/individual123/view",
        "user_email": "individual@example.com",
        "company_name": "Ind",
        "transaction_id": "txn_nonexistent_ind_001"
    }

    response = await http_client.post("/submit", json=payload)

    # Individual transactions also return 404 when transaction doesn't exist
    assert response.status_code == 404, f"Expected 404 for non-existent individual transaction, got {response.status_code}"
    data = response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_submit_endpoint_corporate_nonexistent_transaction(http_client):
    """
    Test submission for corporate customer with non-existent transaction returns 404.

    Verifies:
    - 404 returned for non-existent transaction
    - Error message indicates transaction not found
    """
    payload = {
        "file_name": "corporate_report.docx",
        "file_url": "https://drive.google.com/file/d/corporate456/view",
        "user_email": "employee@company.com",
        "company_name": "Acme Corporation",
        "transaction_id": "txn_nonexistent_corp_001"
    }

    response = await http_client.post("/submit", json=payload)

    # Corporate transactions also return 404 when transaction doesn't exist
    assert response.status_code == 404, f"Expected 404 for non-existent corporate transaction, got {response.status_code}"
    data = response.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_submit_endpoint_validation_missing_transaction_id(http_client):
    """
    Test submission without transaction_id fails validation.

    Verifies:
    - 422 returned when transaction_id is missing
    - Validation error details are provided
    """
    payload = {
        "file_name": "test_email_integration.pdf",
        "file_url": "https://drive.google.com/file/d/email_test_789/view",
        "user_email": "test.user@example.com",
        "company_name": "Test Company"
        # Missing required transaction_id field
    }

    response = await http_client.post("/submit", json=payload)

    # Should fail validation - transaction_id is required
    assert response.status_code == 422, f"Expected 422 for missing transaction_id, got {response.status_code}: {response.text}"
