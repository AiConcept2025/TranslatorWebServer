"""
Pytest configuration and fixtures for TranslatorWebServer tests.
"""

import os
import sys
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from typing import Generator, AsyncGenerator
import tempfile

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.config import settings
from app.services.google_drive_service import GoogleDriveService
from app.exceptions.google_drive_exceptions import GoogleDriveError


@pytest.fixture
def test_email():
    """Test email for folder creation."""
    return "danishevsky@gmail.com"


@pytest.fixture
def test_target_language():
    """Test target language."""
    return "es"


@pytest.fixture
def sample_md_file():
    """Path to a sample markdown file for testing."""
    return project_root / "README.md"


@pytest.fixture
def sample_md_content(sample_md_file):
    """Content of the sample markdown file."""
    with open(sample_md_file, 'rb') as f:
        return f.read()


@pytest.fixture
def mock_google_drive_service():
    """Mock Google Drive service for testing."""
    mock_service = Mock(spec=GoogleDriveService)
    
    # Mock the service methods
    mock_service.create_customer_folder_structure = AsyncMock(return_value="mock_folder_id")
    mock_service.upload_file_to_folder = AsyncMock(return_value={
        'file_id': 'mock_file_id',
        'filename': 'test_file.md',
        'folder_id': 'mock_folder_id',
        'size': 1024,
        'target_language': 'es',
        'created_at': '2023-01-01T00:00:00.000Z',
        'google_drive_url': 'https://drive.google.com/file/d/mock_file_id/view',
        'parents': ['mock_folder_id']
    })
    mock_service.update_file_metadata = AsyncMock(return_value=True)
    mock_service.list_files_in_folder = AsyncMock(return_value=[])
    mock_service.delete_file = AsyncMock(return_value=True)
    mock_service.get_folder_info = AsyncMock(return_value={
        'folder_id': 'mock_folder_id',
        'total_files': 0,
        'total_size_bytes': 0,
        'total_size_mb': 0.0,
        'storage_type': 'google_drive',
        'last_updated': '2023-01-01T00:00:00.000Z'
    })
    
    return mock_service


@pytest.fixture
def mock_google_api_service():
    """Mock Google API service object."""
    mock_service = Mock()
    
    # Mock files() method chain
    mock_files = Mock()
    mock_service.files.return_value = mock_files
    
    # Mock create method
    mock_create = Mock()
    mock_files.create.return_value = mock_create
    mock_create.execute.return_value = {
        'id': 'mock_file_id',
        'name': 'test_file.md',
        'size': '1024',
        'createdTime': '2023-01-01T00:00:00.000Z',
        'webViewLink': 'https://drive.google.com/file/d/mock_file_id/view',
        'parents': ['mock_folder_id']
    }
    
    # Mock list method
    mock_list = Mock()
    mock_files.list.return_value = mock_list
    mock_list.execute.return_value = {'files': []}
    
    # Mock update method
    mock_update = Mock()
    mock_files.update.return_value = mock_update
    mock_update.execute.return_value = {}
    
    # Mock delete method
    mock_delete = Mock()
    mock_files.delete.return_value = mock_delete
    mock_delete.execute.return_value = {}
    
    # Mock get method
    mock_get = Mock()
    mock_files.get.return_value = mock_get
    mock_get.execute.return_value = {
        'name': 'Test Folder',
        'createdTime': '2023-01-01T00:00:00.000Z',
        'modifiedTime': '2023-01-01T00:00:00.000Z'
    }
    
    return mock_service


@pytest.fixture
def test_client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Async HTTP client for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def temp_credentials_file():
    """Temporary credentials file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        credentials_data = {
            "installed": {
                "client_id": "test_client_id",
                "project_id": "test_project",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_secret": "test_client_secret",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
            }
        }
        import json
        json.dump(credentials_data, f)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def temp_token_file():
    """Temporary token file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        token_data = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/drive.file"]
        }
        import json
        json.dump(token_data, f)
        temp_file = f.name
    
    yield temp_file
    
    # Cleanup
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def mock_settings(temp_credentials_file, temp_token_file):
    """Mock settings for testing."""
    original_settings = {}
    
    # Store original values
    for attr in ['google_drive_enabled', 'google_drive_credentials_path', 
                 'google_drive_token_path', 'google_drive_root_folder', 
                 'google_drive_application_name', 'google_drive_scopes']:
        if hasattr(settings, attr):
            original_settings[attr] = getattr(settings, attr)
    
    # Set test values
    settings.google_drive_enabled = True
    settings.google_drive_credentials_path = temp_credentials_file
    settings.google_drive_token_path = temp_token_file
    settings.google_drive_root_folder = "TestTranslatorWebServer"
    settings.google_drive_application_name = "TestTranslatorWebServer"
    settings.google_drive_scopes = "https://www.googleapis.com/auth/drive.file,https://www.googleapis.com/auth/drive.metadata"
    
    yield settings
    
    # Restore original values
    for attr, value in original_settings.items():
        setattr(settings, attr, value)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Integration test markers
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (may require actual credentials)"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (use mocks)"
    )