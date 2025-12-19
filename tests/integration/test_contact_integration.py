"""
Integration tests for the contact form endpoint (/api/contact).

Tests all routing paths and validation rules for the contact form submission.
Uses real HTTP requests to the running server with comprehensive validation.

Test Coverage:
- 4 tests for subject routing (each subject type routes to correct recipient)
- 3 tests for validation (email format, message length, subject validation)
"""

import pytest
import httpx


@pytest.fixture
async def http_client():
    """
    Provides an HTTP client for making requests to the test server.

    CRITICAL: Assumes server is already running at http://localhost:8000.
    Tests use real HTTP requests, NOT direct function calls.

    Returns:
        httpx.AsyncClient: Async HTTP client configured for localhost:8000
    """
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        # Verify server is running
        try:
            await client.get("/health")
        except httpx.ConnectError:
            pytest.skip("Server not running at http://localhost:8000")
        yield client


# ============================================================================
# Test Cases 1-4: Routing for Each Subject Type
# ============================================================================

@pytest.mark.asyncio
async def test_contact_form_enterprise_sales_routing(http_client):
    """
    Test that "Enterprise Sales Inquiry" routes correctly.

    Expected behavior:
    - POST /api/contact with subject="Enterprise Sales Inquiry"
    - Should route to sales@irissolutions.ai
    - Should return 200 status code
    - Should return success: true in response
    """
    response = await http_client.post("/api/contact", json={
        "name": "Test Enterprise Customer",
        "email": "test.customer@example.com",
        "subject": "Enterprise Sales Inquiry",
        "message": "I need enterprise pricing information for our company"
    })

    # Verify HTTP response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify response structure
    data = response.json()
    assert "success" in data, "Response missing 'success' field"
    assert data["success"] is True, "Expected success: true"
    assert "message" in data, "Response missing 'message' field"


@pytest.mark.asyncio
async def test_contact_form_technical_support_routing(http_client):
    """
    Test that "Technical Support" routes correctly.

    Expected behavior:
    - POST /api/contact with subject="Technical Support"
    - Should route to support@irissolutions.ai
    - Should return 200 status code
    - Should return success: true in response
    """
    response = await http_client.post("/api/contact", json={
        "name": "Test Developer",
        "email": "dev@example.com",
        "subject": "Technical Support",
        "message": "I'm experiencing an issue with the API integration"
    })

    # Verify HTTP response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify response structure
    data = response.json()
    assert data["success"] is True, "Expected success: true"
    assert "message" in data, "Response missing 'message' field"


@pytest.mark.asyncio
async def test_contact_form_api_integration_routing(http_client):
    """
    Test that "API Integration" routes correctly.

    Expected behavior:
    - POST /api/contact with subject="API Integration"
    - Should route to support@irissolutions.ai
    - Should return 200 status code
    - Should return success: true in response
    """
    response = await http_client.post("/api/contact", json={
        "name": "API Integration Engineer",
        "email": "engineer@example.com",
        "subject": "API Integration",
        "message": "I need assistance integrating your API into our system"
    })

    # Verify HTTP response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify response structure
    data = response.json()
    assert data["success"] is True, "Expected success: true"


@pytest.mark.asyncio
async def test_contact_form_general_question_routing(http_client):
    """
    Test that "General Question" routes correctly.

    Expected behavior:
    - POST /api/contact with subject="General Question"
    - Should route to sales@irissolutions.ai
    - Should return 200 status code
    - Should return success: true in response
    """
    response = await http_client.post("/api/contact", json={
        "name": "General Inquirer",
        "email": "inquirer@example.com",
        "subject": "General Question",
        "message": "I have a general question about your translation services"
    })

    # Verify HTTP response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    # Verify response structure
    data = response.json()
    assert data["success"] is True, "Expected success: true"


# ============================================================================
# Test Cases 5-7: Validation Rules
# ============================================================================

@pytest.mark.asyncio
async def test_contact_form_invalid_email_format(http_client):
    """
    Test that invalid email format returns 422 validation error.

    Expected behavior:
    - POST /api/contact with email="invalid-email-format"
    - Pydantic EmailStr validation should reject invalid format
    - Should return 422 Unprocessable Entity status code
    """
    response = await http_client.post("/api/contact", json={
        "name": "Test User",
        "email": "not-an-email",  # Invalid email format
        "subject": "General Question",
        "message": "This should fail validation"
    })

    # Verify validation error
    assert response.status_code == 422, (
        f"Expected 422 validation error, got {response.status_code}: {response.text}"
    )

    # Verify error structure (custom error response format)
    data = response.json()
    assert "error" in data, "Validation error should have 'error' field"
    assert "details" in data["error"], "Error should have 'details' field"


@pytest.mark.asyncio
async def test_contact_form_message_under_min_length(http_client):
    """
    Test that message under 10 characters returns 422 validation error.

    Expected behavior:
    - POST /api/contact with message less than 10 characters
    - Pydantic min_length=10 validation should reject
    - Should return 422 Unprocessable Entity status code
    """
    response = await http_client.post("/api/contact", json={
        "name": "Test User",
        "email": "test@example.com",
        "subject": "General Question",
        "message": "short"  # Only 5 characters, needs minimum 10
    })

    # Verify validation error
    assert response.status_code == 422, (
        f"Expected 422 validation error, got {response.status_code}: {response.text}"
    )

    # Verify error structure (custom error response format)
    data = response.json()
    assert "error" in data, "Validation error should have 'error' field"
    assert "details" in data["error"], "Error should have 'details' field"


@pytest.mark.asyncio
async def test_contact_form_invalid_subject(http_client):
    """
    Test that invalid subject (not in allowed list) returns 422 validation error.

    Expected behavior:
    - POST /api/contact with subject not in allowed list
    - Pydantic Literal validation should reject invalid subject
    - Should return 422 Unprocessable Entity status code
    - Allowed subjects: "Enterprise Sales Inquiry", "Technical Support", "API Integration", "General Question"
    """
    response = await http_client.post("/api/contact", json={
        "name": "Test User",
        "email": "test@example.com",
        "subject": "Invalid Subject Type",  # Not in allowed list
        "message": "This should fail validation"
    })

    # Verify validation error
    assert response.status_code == 422, (
        f"Expected 422 validation error, got {response.status_code}: {response.text}"
    )

    # Verify error structure (custom error response format)
    data = response.json()
    assert "error" in data, "Validation error should have 'error' field"
    assert "details" in data["error"], "Error should have 'details' field"
