"""
Google Drive specific test fixtures and mock factories.
"""

import pytest
import json
import tempfile
import os
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timezone


class GoogleDriveMockFactory:
    """Factory class for creating Google Drive API mocks and test data."""
    
    @staticmethod
    def create_file_response(
        file_id: str = "test_file_123",
        filename: str = "test_document.md",
        size: int = 1024,
        mime_type: str = "text/markdown",
        parent_id: str = "parent_folder_456",
        created_time: str = "2023-01-01T12:00:00Z",
        properties: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create a mock Google Drive file response."""
        if properties is None:
            properties = {
                "target_language": "es",
                "upload_timestamp": created_time,
                "original_filename": filename
            }
        
        return {
            "id": file_id,
            "name": filename,
            "size": str(size),
            "createdTime": created_time,
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
            "parents": [parent_id],
            "mimeType": mime_type,
            "properties": properties
        }
    
    @staticmethod
    def create_folder_response(
        folder_id: str = "folder_123",
        folder_name: str = "TestFolder",
        parent_id: Optional[str] = None,
        created_time: str = "2023-01-01T10:00:00Z"
    ) -> Dict[str, Any]:
        """Create a mock Google Drive folder response."""
        response = {
            "id": folder_id,
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "createdTime": created_time
        }
        
        if parent_id:
            response["parents"] = [parent_id]
        
        return response
    
    @staticmethod
    def create_files_list_response(files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a mock Google Drive files.list() response."""
        return {
            "files": files
        }
    
    @staticmethod
    def create_mock_service_with_responses(
        file_responses: Optional[List[Dict[str, Any]]] = None,
        folder_responses: Optional[List[Dict[str, Any]]] = None,
        list_responses: Optional[List[Dict[str, Any]]] = None,
        should_fail: bool = False,
        failure_exception: Optional[Exception] = None
    ) -> Mock:
        """Create a comprehensive mock Google Drive service."""
        mock_service = Mock()
        
        # Setup files() method
        mock_files = Mock()
        mock_service.files.return_value = mock_files
        
        if should_fail and failure_exception:
            # Configure service to fail
            mock_files.create.side_effect = failure_exception
            mock_files.list.side_effect = failure_exception
            mock_files.update.side_effect = failure_exception
            mock_files.get.side_effect = failure_exception
            mock_files.delete.side_effect = failure_exception
        else:
            # Configure successful responses
            
            # Mock create operation (for files and folders)
            mock_create = Mock()
            mock_files.create.return_value = mock_create
            
            if file_responses or folder_responses:
                # Combine file and folder responses for create operations
                all_create_responses = []
                if file_responses:
                    all_create_responses.extend(file_responses)
                if folder_responses:
                    all_create_responses.extend(folder_responses)
                
                if len(all_create_responses) == 1:
                    mock_create.execute.return_value = all_create_responses[0]
                else:
                    mock_create.execute.side_effect = all_create_responses
            else:
                # Default create response
                mock_create.execute.return_value = GoogleDriveMockFactory.create_file_response()
            
            # Mock list operation
            mock_list = Mock()
            mock_files.list.return_value = mock_list
            
            if list_responses:
                if len(list_responses) == 1:
                    mock_list.execute.return_value = list_responses[0]
                else:
                    mock_list.execute.side_effect = list_responses
            else:
                # Default empty list response
                mock_list.execute.return_value = {"files": []}
            
            # Mock update operation
            mock_update = Mock()
            mock_files.update.return_value = mock_update
            mock_update.execute.return_value = {"id": "updated_file_123"}
            
            # Mock get operation (for folder details)
            mock_get = Mock()
            mock_files.get.return_value = mock_get
            mock_get.execute.return_value = {
                "id": "folder_123",
                "name": "TestFolder",
                "createdTime": "2023-01-01T10:00:00Z",
                "modifiedTime": "2023-01-01T12:00:00Z"
            }
            
            # Mock delete operation
            mock_delete = Mock()
            mock_files.delete.return_value = mock_delete
            mock_delete.execute.return_value = None  # Delete returns None on success
        
        return mock_service
    
    @staticmethod
    def create_file_content_samples() -> Dict[str, bytes]:
        """Create sample file contents for testing."""
        return {
            "markdown": b"""# Test Document

This is a test markdown document for Google Drive upload testing.

## Features to Test
- File upload functionality
- Folder structure creation
- Metadata management
- Error handling

### Customer Information
- Email: danishevsky@gmail.com
- Target Language: Spanish (es)

**Note**: This is test content for the TranslatorWebServer test suite.
""",
            "text": b"""Test Document

This is a plain text document for testing.

Features to test:
- File upload
- Metadata management
- Error handling

Customer: danishevsky@gmail.com
Language: Spanish
""",
            "small": b"Small test file content.",
            "large": b"Large file content. " + (b"This is repeated content. " * 1000),
            "empty": b"",
            "unicode": "Test with unicode characters: café, naïve, résumé, 中文, العربية".encode('utf-8')
        }


class GoogleDriveCredentialsMockFactory:
    """Factory for creating Google Drive credentials mocks."""
    
    @staticmethod
    def create_mock_credentials(
        valid: bool = True,
        expired: bool = False,
        has_refresh_token: bool = True,
        refresh_succeeds: bool = True
    ) -> Mock:
        """Create mock Google credentials."""
        mock_creds = Mock()
        mock_creds.valid = valid and not expired
        mock_creds.expired = expired
        mock_creds.refresh_token = "refresh_token_123" if has_refresh_token else None
        mock_creds.to_json.return_value = json.dumps({
            "token": "access_token_123",
            "refresh_token": "refresh_token_123" if has_refresh_token else None,
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/drive.file"]
        })
        
        if refresh_succeeds:
            mock_creds.refresh.return_value = None
        else:
            mock_creds.refresh.side_effect = Exception("Refresh failed")
        
        return mock_creds
    
    @staticmethod
    def create_credentials_file(temp_dir: str) -> str:
        """Create a temporary credentials file."""
        credentials_content = {
            "web": {
                "client_id": "test_client_id.apps.googleusercontent.com",
                "project_id": "test-project",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_secret": "test_client_secret",
                "redirect_uris": ["http://localhost"]
            }
        }
        
        credentials_path = os.path.join(temp_dir, "credentials.json")
        with open(credentials_path, 'w') as f:
            json.dump(credentials_content, f)
        
        return credentials_path
    
    @staticmethod
    def create_token_file(temp_dir: str) -> str:
        """Create a temporary token file."""
        token_content = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id.apps.googleusercontent.com",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/drive.file"],
            "expiry": "2024-01-01T12:00:00Z"
        }
        
        token_path = os.path.join(temp_dir, "token.json")
        with open(token_path, 'w') as f:
            json.dump(token_content, f)
        
        return token_path


# Pytest fixtures using the factories

@pytest.fixture
def google_drive_mock_factory():
    """Provide access to GoogleDriveMockFactory."""
    return GoogleDriveMockFactory


@pytest.fixture
def google_drive_credentials_mock_factory():
    """Provide access to GoogleDriveCredentialsMockFactory."""
    return GoogleDriveCredentialsMockFactory


@pytest.fixture
def sample_file_contents(google_drive_mock_factory):
    """Provide sample file contents for testing."""
    return google_drive_mock_factory.create_file_content_samples()


@pytest.fixture
def mock_google_drive_service_success(google_drive_mock_factory):
    """Create a mock Google Drive service that returns successful responses."""
    file_responses = [
        google_drive_mock_factory.create_file_response(
            file_id="uploaded_file_123",
            filename="test.md",
            size=512
        )
    ]
    
    folder_responses = [
        google_drive_mock_factory.create_folder_response(
            folder_id="root_folder_123",
            folder_name="TranslatorWebServer"
        ),
        google_drive_mock_factory.create_folder_response(
            folder_id="customer_folder_456",
            folder_name="danishevsky@gmail.com",
            parent_id="root_folder_123"
        ),
        google_drive_mock_factory.create_folder_response(
            folder_id="temp_folder_789",
            folder_name="Temp",
            parent_id="customer_folder_456"
        )
    ]
    
    list_responses = [
        google_drive_mock_factory.create_files_list_response([]),  # Empty for folder search
        google_drive_mock_factory.create_files_list_response([
            google_drive_mock_factory.create_file_response()
        ])  # File listing
    ]
    
    return google_drive_mock_factory.create_mock_service_with_responses(
        file_responses=file_responses,
        folder_responses=folder_responses,
        list_responses=list_responses
    )


@pytest.fixture
def mock_google_drive_service_failure(google_drive_mock_factory):
    """Create a mock Google Drive service that fails with errors."""
    from googleapiclient.errors import HttpError
    
    # Create mock HTTP error
    resp = Mock()
    resp.status = 403
    resp.reason = "Forbidden"
    
    failure_exception = HttpError(resp, content=b'{"error": {"message": "Permission denied"}}')
    
    return google_drive_mock_factory.create_mock_service_with_responses(
        should_fail=True,
        failure_exception=failure_exception
    )


@pytest.fixture
def mock_valid_credentials(google_drive_credentials_mock_factory):
    """Create mock valid Google credentials."""
    return google_drive_credentials_mock_factory.create_mock_credentials(
        valid=True,
        expired=False,
        has_refresh_token=True
    )


@pytest.fixture
def mock_expired_credentials(google_drive_credentials_mock_factory):
    """Create mock expired Google credentials that can be refreshed."""
    return google_drive_credentials_mock_factory.create_mock_credentials(
        valid=False,
        expired=True,
        has_refresh_token=True,
        refresh_succeeds=True
    )


@pytest.fixture
def mock_expired_credentials_refresh_fails(google_drive_credentials_mock_factory):
    """Create mock expired credentials that fail to refresh."""
    return google_drive_credentials_mock_factory.create_mock_credentials(
        valid=False,
        expired=True,
        has_refresh_token=True,
        refresh_succeeds=False
    )


@pytest.fixture
def temporary_credentials_setup(google_drive_credentials_mock_factory):
    """Create temporary credentials and token files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        credentials_path = google_drive_credentials_mock_factory.create_credentials_file(temp_dir)
        token_path = google_drive_credentials_mock_factory.create_token_file(temp_dir)
        
        yield {
            "temp_dir": temp_dir,
            "credentials_path": credentials_path,
            "token_path": token_path
        }


@pytest.fixture
def google_drive_test_scenarios():
    """Provide common test scenarios for Google Drive operations."""
    return {
        "folder_creation": {
            "customer_emails": [
                "danishevsky@gmail.com",
                "test.user@example.com",
                "user+tag@domain.co.uk",
                "simple@test.co"
            ],
            "expected_structure": ["TranslatorWebServer", "{email}", "Temp"]
        },
        "file_uploads": {
            "test_files": [
                {"filename": "document.md", "size": 1024, "mime_type": "text/markdown"},
                {"filename": "document.pdf", "size": 5000, "mime_type": "application/pdf"},
                {"filename": "document.txt", "size": 500, "mime_type": "text/plain"}
            ],
            "target_languages": ["es", "fr", "de", "it", "pt"]
        },
        "error_conditions": [
            {"status": 401, "reason": "Unauthorized", "exception_type": "GoogleDriveAuthenticationError"},
            {"status": 403, "reason": "Forbidden", "exception_type": "GoogleDrivePermissionError"},
            {"status": 404, "reason": "Not Found", "exception_type": "GoogleDriveFileNotFoundError"},
            {"status": 429, "reason": "Too Many Requests", "exception_type": "GoogleDriveQuotaExceededError"},
            {"status": 500, "reason": "Internal Server Error", "exception_type": "GoogleDriveStorageError"}
        ]
    }


@pytest.fixture
def performance_test_data():
    """Provide data for performance testing."""
    return {
        "small_files": [
            {"name": f"small_file_{i}.md", "content": b"Small content " * 10}
            for i in range(5)
        ],
        "medium_files": [
            {"name": f"medium_file_{i}.pdf", "content": b"Medium content " * 1000}
            for i in range(3)
        ],
        "large_file": {
            "name": "large_file.txt",
            "content": b"Large content " * 10000
        }
    }


@pytest.fixture
def metadata_test_cases():
    """Provide test cases for metadata operations."""
    return [
        {
            "description": "Basic metadata update",
            "metadata": {
                "properties": {
                    "target_language": "es",
                    "customer_email": "danishevsky@gmail.com",
                    "status": "uploaded"
                },
                "description": "File uploaded for translation"
            }
        },
        {
            "description": "Metadata with special characters",
            "metadata": {
                "properties": {
                    "target_language": "zh-CN",
                    "customer_email": "user+tag@domain.com",
                    "notes": "File with special chars: café, naïve"
                }
            }
        },
        {
            "description": "Empty metadata update",
            "metadata": {}
        },
        {
            "description": "Large metadata values",
            "metadata": {
                "properties": {
                    "large_property": "x" * 1000,
                    "target_language": "fr"
                },
                "description": "y" * 500
            }
        }
    ]


# Parametrized fixture for different customer email formats
@pytest.fixture(params=[
    "danishevsky@gmail.com",
    "test.user@example.com", 
    "user+tag@domain.co.uk",
    "simple@test.co",
    "user.with.dots@company.org",
    "user_with_underscores@site.net"
])
def customer_email_variations(request):
    """Provide various customer email formats for testing."""
    return request.param


# Parametrized fixture for different target languages
@pytest.fixture(params=["es", "fr", "de", "it", "pt", "en-US", "zh-CN"])
def target_language_variations(request):
    """Provide various target language codes for testing."""
    return request.param


# Parametrized fixture for different file sizes
@pytest.fixture(params=[
    ("tiny", 10),
    ("small", 1024),
    ("medium", 10 * 1024),
    ("large", 100 * 1024),
    ("very_large", 1024 * 1024)
])
def file_size_variations(request):
    """Provide various file sizes for testing."""
    size_name, size_bytes = request.param
    return {
        "name": size_name,
        "size": size_bytes,
        "content": b"x" * size_bytes
    }