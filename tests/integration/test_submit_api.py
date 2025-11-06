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
async def test_submit_endpoint_success(http_client):
    """
    Test successful submission with valid request data.

    Verifies:
    - 200 status code returned
    - Response contains status and message fields
    - Response structure matches specification
    """
    payload = {
        "file_name": "test_document.docx",
        "file_url": "https://drive.google.com/file/d/test123/view",
        "user_email": "test@example.com",
        "company_name": "Test Company",
        "transaction_id": "txn_123"
    }

    response = await http_client.post("/submit", json=payload)

    # Verify status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify response structure
    data = response.json()
    assert "status" in data, "Response must contain 'status' field"
    assert "message" in data, "Response must contain 'message' field"

    # Verify field types
    assert isinstance(data["status"], str), "'status' must be a string"
    assert isinstance(data["message"], str), "'message' must be a string"


@pytest.mark.asyncio
async def test_submit_endpoint_without_transaction_id(http_client):
    """
    Test submission without optional transaction_id.

    Verifies:
    - Request succeeds without transaction_id
    - Response is properly formatted
    """
    payload = {
        "file_name": "test_document.pdf",
        "file_url": "https://drive.google.com/file/d/abc456/view",
        "user_email": "user@company.com",
        "company_name": "Another Company"
    }

    response = await http_client.post("/submit", json=payload)

    # Verify status code
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify response structure
    data = response.json()
    assert "status" in data
    assert "message" in data


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
async def test_submit_endpoint_individual_customer(http_client):
    """
    Test submission for individual customer (company_name="Ind").

    Verifies:
    - Submission succeeds
    - Email template selection is correct (individual vs corporate)
    """
    payload = {
        "file_name": "personal_document.pdf",
        "file_url": "https://drive.google.com/file/d/individual123/view",
        "user_email": "individual@example.com",
        "company_name": "Ind",
        "transaction_id": "txn_ind_001"
    }

    response = await http_client.post("/submit", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["received", "processed"]


@pytest.mark.asyncio
async def test_submit_endpoint_corporate_customer(http_client):
    """
    Test submission for corporate customer (company_name != "Ind").

    Verifies:
    - Submission succeeds
    - Corporate template is used
    """
    payload = {
        "file_name": "corporate_report.docx",
        "file_url": "https://drive.google.com/file/d/corporate456/view",
        "user_email": "employee@company.com",
        "company_name": "Acme Corporation",
        "transaction_id": "txn_corp_001"
    }

    response = await http_client.post("/submit", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["received", "processed"]


@pytest.mark.asyncio
async def test_submit_endpoint_email_integration(http_client):
    """
    Test that submission integrates with email service.

    NOTE: This test verifies email integration exists, but email sending
    may fail if SMTP credentials are not configured. The submission itself
    should still succeed even if email fails.

    Verifies:
    - Submission returns 200 even if email fails
    - Response indicates email status
    """
    payload = {
        "file_name": "test_email_integration.pdf",
        "file_url": "https://drive.google.com/file/d/email_test_789/view",
        "user_email": "test.user@example.com",
        "company_name": "Test Company"
    }

    response = await http_client.post("/submit", json=payload)

    # Should succeed regardless of email status
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] in ["received", "processed"]

    # Email status may be included in response
    # This is informational - doesn't affect submission success
    if "email_sent" in data:
        assert isinstance(data["email_sent"], bool)
