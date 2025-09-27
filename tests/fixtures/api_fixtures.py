"""
API and FastAPI specific test fixtures.
"""

import pytest
import io
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.main import app


class APITestDataFactory:
    """Factory for creating API test data."""
    
    @staticmethod
    def create_upload_file(
        filename: str = "test.md",
        content: bytes = b"test content",
        content_type: str = "text/markdown"
    ) -> UploadFile:
        """Create a mock UploadFile for testing."""
        file_obj = io.BytesIO(content)
        return UploadFile(
            filename=filename,
            file=file_obj,
            content_type=content_type
        )
    
    @staticmethod
    def create_upload_form_data(
        customer_email: str = "danishevsky@gmail.com",
        target_language: str = "es",
        files: List[tuple] = None
    ) -> Dict[str, Any]:
        """Create form data for upload endpoint testing."""
        if files is None:
            files = [("files", ("test.md", b"test content", "text/markdown"))]
        
        return {
            "data": {
                "customer_email": customer_email,
                "target_language": target_language
            },
            "files": files
        }
    
    @staticmethod
    def create_upload_response_success(
        customer_email: str = "danishevsky@gmail.com",
        target_language: str = "es",
        total_files: int = 1,
        successful_uploads: int = 1,
        failed_uploads: int = 0,
        folder_path: str = "test_folder_123"
    ) -> Dict[str, Any]:
        """Create a successful upload response."""
        results = []
        for i in range(successful_uploads):
            results.append({
                "filename": f"test_file_{i+1}.md",
                "file_id": f"file_id_{i+1}",
                "status": "success",
                "message": "File uploaded successfully",
                "file_size": 512,
                "content_type": "text/markdown",
                "google_drive_folder": folder_path
            })
        
        for i in range(failed_uploads):
            results.append({
                "filename": f"failed_file_{i+1}.md",
                "file_id": "",
                "status": "failed",
                "message": "File upload failed",
                "file_size": 512,
                "content_type": "text/markdown",
                "google_drive_folder": folder_path
            })
        
        return {
            "success": successful_uploads > 0,
            "message": f"Upload completed: {successful_uploads} successful, {failed_uploads} failed",
            "customer_email": customer_email,
            "target_language": target_language,
            "total_files": total_files,
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
            "results": results,
            "google_drive_folder_path": folder_path,
            "timestamp": "2023-01-01T12:00:00.000Z"
        }
    
    @staticmethod
    def create_validation_error_response(field: str, message: str) -> Dict[str, Any]:
        """Create a validation error response."""
        return {
            "detail": [
                {
                    "loc": ["body", field],
                    "msg": message,
                    "type": "value_error"
                }
            ]
        }
    
    @staticmethod
    def create_google_drive_error_response(
        status_code: int = 500,
        message: str = "Google Drive error",
        retry_recommended: bool = True
    ) -> Dict[str, Any]:
        """Create a Google Drive error response."""
        return {
            "detail": {
                "error": "google_drive_error",
                "message": message,
                "operation_failed": True,
                "retry_recommended": retry_recommended
            }
        }


class FileValidationMockFactory:
    """Factory for creating file validation mocks."""
    
    @staticmethod
    def create_validation_success() -> tuple:
        """Create successful validation result."""
        return (True, [])
    
    @staticmethod
    def create_validation_failure(errors: List[str] = None) -> tuple:
        """Create failed validation result."""
        if errors is None:
            errors = ["File type not supported", "File size too large"]
        return (False, errors)
    
    @staticmethod
    def create_mock_validator(
        validation_results: List[tuple] = None,
        default_result: tuple = None
    ) -> Mock:
        """Create mock file validator."""
        mock_validator = Mock()
        
        if validation_results:
            mock_validator.comprehensive_file_validation = AsyncMock(
                side_effect=validation_results
            )
        elif default_result:
            mock_validator.comprehensive_file_validation = AsyncMock(
                return_value=default_result
            )
        else:
            # Default to success
            mock_validator.comprehensive_file_validation = AsyncMock(
                return_value=FileValidationMockFactory.create_validation_success()
            )
        
        return mock_validator


# Pytest fixtures

@pytest.fixture
def api_test_client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def api_factory():
    """Provide access to APITestDataFactory."""
    return APITestDataFactory


@pytest.fixture
def file_validation_factory():
    """Provide access to FileValidationMockFactory."""
    return FileValidationMockFactory


@pytest.fixture
def mock_upload_file(api_factory):
    """Create a mock UploadFile for testing."""
    return api_factory.create_upload_file()


@pytest.fixture
def mock_upload_files_multiple(api_factory):
    """Create multiple mock UploadFiles for testing."""
    return [
        api_factory.create_upload_file("document1.md", b"Content 1", "text/markdown"),
        api_factory.create_upload_file("document2.pdf", b"PDF content", "application/pdf"),
        api_factory.create_upload_file("document3.txt", b"Text content", "text/plain")
    ]


@pytest.fixture
def valid_upload_form_data(api_factory):
    """Create valid upload form data."""
    return api_factory.create_upload_form_data()


@pytest.fixture
def invalid_upload_form_data():
    """Create invalid upload form data for testing validation."""
    return {
        "invalid_email": {
            "data": {
                "customer_email": "invalid-email",
                "target_language": "es"
            },
            "files": [("files", ("test.md", b"content", "text/markdown"))]
        },
        "invalid_language": {
            "data": {
                "customer_email": "danishevsky@gmail.com",
                "target_language": "x"  # Too short
            },
            "files": [("files", ("test.md", b"content", "text/markdown"))]
        },
        "missing_email": {
            "data": {
                "target_language": "es"
            },
            "files": [("files", ("test.md", b"content", "text/markdown"))]
        },
        "missing_language": {
            "data": {
                "customer_email": "danishevsky@gmail.com"
            },
            "files": [("files", ("test.md", b"content", "text/markdown"))]
        }
    }


@pytest.fixture
def upload_endpoint_responses(api_factory):
    """Provide various upload endpoint response examples."""
    return {
        "success_single": api_factory.create_upload_response_success(
            total_files=1,
            successful_uploads=1,
            failed_uploads=0
        ),
        "success_multiple": api_factory.create_upload_response_success(
            total_files=3,
            successful_uploads=3,
            failed_uploads=0
        ),
        "partial_success": api_factory.create_upload_response_success(
            total_files=3,
            successful_uploads=2,
            failed_uploads=1
        ),
        "all_failed": api_factory.create_upload_response_success(
            total_files=2,
            successful_uploads=0,
            failed_uploads=2
        ),
        "validation_error": api_factory.create_validation_error_response(
            "customer_email", 
            "Invalid email format"
        ),
        "google_drive_error_auth": api_factory.create_google_drive_error_response(
            status_code=401,
            message="Authentication failed",
            retry_recommended=False
        ),
        "google_drive_error_quota": api_factory.create_google_drive_error_response(
            status_code=429,
            message="Quota exceeded",
            retry_recommended=True
        )
    }


@pytest.fixture
def mock_file_validator_success(file_validation_factory):
    """Create mock file validator that always succeeds."""
    return file_validation_factory.create_mock_validator(
        default_result=file_validation_factory.create_validation_success()
    )


@pytest.fixture
def mock_file_validator_failure(file_validation_factory):
    """Create mock file validator that always fails."""
    return file_validation_factory.create_mock_validator(
        default_result=file_validation_factory.create_validation_failure()
    )


@pytest.fixture
def mock_file_validator_mixed(file_validation_factory):
    """Create mock file validator with mixed results."""
    results = [
        file_validation_factory.create_validation_success(),  # First file passes
        file_validation_factory.create_validation_failure(["Invalid file type"]),  # Second fails
        file_validation_factory.create_validation_success(),  # Third passes
    ]
    return file_validation_factory.create_mock_validator(validation_results=results)


@pytest.fixture
def upload_test_scenarios():
    """Provide various upload test scenarios."""
    return {
        "single_file_success": {
            "description": "Upload single file successfully",
            "files": [("files", ("test.md", b"test content", "text/markdown"))],
            "expected_status": 200,
            "expected_successful": 1,
            "expected_failed": 0
        },
        "multiple_files_success": {
            "description": "Upload multiple files successfully",
            "files": [
                ("files", ("doc1.md", b"content 1", "text/markdown")),
                ("files", ("doc2.pdf", b"pdf content", "application/pdf")),
                ("files", ("doc3.txt", b"text content", "text/plain"))
            ],
            "expected_status": 200,
            "expected_successful": 3,
            "expected_failed": 0
        },
        "no_files": {
            "description": "Upload request with no files",
            "files": [],
            "expected_status": 400,
            "expected_error": "No files provided"
        },
        "large_file": {
            "description": "Upload large file",
            "files": [("files", ("large.md", b"x" * (5 * 1024 * 1024), "text/markdown"))],  # 5MB
            "expected_status": 200,
            "expected_successful": 1,
            "expected_failed": 0
        }
    }


@pytest.fixture
def api_error_test_cases():
    """Provide API error test cases."""
    return [
        {
            "name": "google_drive_auth_error",
            "exception_type": "GoogleDriveAuthenticationError",
            "exception_message": "Authentication failed",
            "expected_status": 401,
            "expected_retry": False
        },
        {
            "name": "google_drive_permission_error", 
            "exception_type": "GoogleDrivePermissionError",
            "exception_message": "Permission denied",
            "expected_status": 403,
            "expected_retry": False
        },
        {
            "name": "google_drive_quota_error",
            "exception_type": "GoogleDriveQuotaExceededError",
            "exception_message": "Quota exceeded",
            "expected_status": 429,
            "expected_retry": True
        },
        {
            "name": "google_drive_storage_error",
            "exception_type": "GoogleDriveStorageError",
            "exception_message": "Storage error",
            "expected_status": 500,
            "expected_retry": True
        },
        {
            "name": "generic_error",
            "exception_type": "Exception",
            "exception_message": "Unexpected error",
            "expected_status": 500,
            "expected_retry": False
        }
    ]


# Parametrized fixtures for different test scenarios

@pytest.fixture(params=[
    {"customer_email": "danishevsky@gmail.com", "target_language": "es"},
    {"customer_email": "test.user@example.com", "target_language": "fr"},
    {"customer_email": "user+tag@domain.co.uk", "target_language": "de"},
])
def upload_request_variations(request):
    """Provide various valid upload request parameter combinations."""
    return request.param


@pytest.fixture(params=[
    "text/markdown",
    "application/pdf", 
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
])
def supported_content_types(request):
    """Provide various supported content types."""
    return request.param


@pytest.fixture(params=[
    "application/x-executable",
    "image/jpeg",  # If not in allowed types
    "application/zip",
    "text/html"
])
def unsupported_content_types(request):
    """Provide various unsupported content types."""
    return request.param


@pytest.fixture(params=[100, 1024, 10*1024, 100*1024, 1024*1024])
def file_sizes(request):
    """Provide various file sizes for testing."""
    size = request.param
    return {
        "size": size,
        "content": b"x" * size,
        "description": f"{size} bytes"
    }