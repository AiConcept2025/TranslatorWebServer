"""
Unit tests for Google Drive folder operations.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from googleapiclient.errors import HttpError

from app.services.google_drive_service import GoogleDriveService
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveStorageError,
    GoogleDriveFileNotFoundError,
    GoogleDrivePermissionError
)


class TestFolderStructureCreation:
    """Test folder structure creation functionality."""

    @pytest.fixture
    def mock_service_with_folder_ops(self, mock_google_drive_service):
        """Create a mock service configured for folder operations."""
        service = mock_google_drive_service
        
        # Mock the service methods we'll use
        service.create_customer_folder_structure = AsyncMock()
        service._find_or_create_folder = AsyncMock()
        service._find_folder = AsyncMock()
        service._create_folder = AsyncMock()
        
        return service

    @pytest.mark.asyncio
    async def test_create_customer_folder_structure_success(self, mock_service_with_folder_ops):
        """Test successful customer folder structure creation."""
        # Setup mock responses
        root_folder_id = "root_folder_123"
        customer_folder_id = "customer_folder_456" 
        temp_folder_id = "temp_folder_789"
        
        mock_service_with_folder_ops._find_or_create_folder.side_effect = [
            root_folder_id,      # Root folder
            customer_folder_id,  # Customer folder
            temp_folder_id       # Temp folder
        ]
        
        # Create a real service instance for testing
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_service_with_folder_ops
            
            service = GoogleDriveService()
            
            # Override the method with our mock
            service._find_or_create_folder = mock_service_with_folder_ops._find_or_create_folder
            
            result = await service.create_customer_folder_structure("danishevsky@gmail.com")
            
            # Verify the result
            assert result == temp_folder_id
            
            # Verify the correct sequence of folder creation calls
            expected_calls = [
                (service.root_folder, None),                    # Root folder
                ("danishevsky@gmail.com", root_folder_id),      # Customer folder
                ("Temp", customer_folder_id)                   # Temp folder
            ]
            
            actual_calls = mock_service_with_folder_ops._find_or_create_folder.call_args_list
            assert len(actual_calls) == 3
            
            for i, (expected_name, expected_parent) in enumerate(expected_calls):
                actual_args = actual_calls[i][0]
                assert actual_args[0] == expected_name
                assert actual_args[1] == expected_parent

    @pytest.mark.asyncio 
    async def test_create_customer_folder_structure_root_folder_creation_fails(self, mock_service_with_folder_ops):
        """Test customer folder structure creation when root folder creation fails."""
        mock_service_with_folder_ops._find_or_create_folder.side_effect = GoogleDriveStorageError("Failed to create root folder")
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_service_with_folder_ops
            
            service = GoogleDriveService()
            service._find_or_create_folder = mock_service_with_folder_ops._find_or_create_folder
            
            with pytest.raises(GoogleDriveStorageError, match="Failed to create root folder"):
                await service.create_customer_folder_structure("danishevsky@gmail.com")

    @pytest.mark.asyncio
    async def test_find_or_create_folder_existing_folder(self, mock_service_with_folder_ops):
        """Test find_or_create_folder when folder already exists."""
        existing_folder_id = "existing_folder_123"
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_service_with_folder_ops
            
            service = GoogleDriveService()
            
            # Mock _find_folder to return existing folder
            service._find_folder = AsyncMock(return_value=existing_folder_id)
            service._create_folder = AsyncMock()  # Should not be called
            
            result = await service._find_or_create_folder("TestFolder", "parent_id")
            
            assert result == existing_folder_id
            service._find_folder.assert_called_once_with("TestFolder", "parent_id")
            service._create_folder.assert_not_called()

    @pytest.mark.asyncio
    async def test_find_or_create_folder_create_new(self, mock_service_with_folder_ops):
        """Test find_or_create_folder when folder needs to be created."""
        new_folder_id = "new_folder_456"
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_service_with_folder_ops
            
            service = GoogleDriveService()
            
            # Mock _find_folder to return None (not found)
            service._find_folder = AsyncMock(return_value=None)
            service._create_folder = AsyncMock(return_value=new_folder_id)
            
            result = await service._find_or_create_folder("NewFolder", "parent_id")
            
            assert result == new_folder_id
            service._find_folder.assert_called_once_with("NewFolder", "parent_id")
            service._create_folder.assert_called_once_with("NewFolder", "parent_id")

    @pytest.mark.asyncio
    async def test_create_folder_success(self, mock_google_drive_service):
        """Test successful folder creation."""
        folder_id = "created_folder_123"
        folder_name = "TestFolder"
        parent_id = "parent_folder_456"
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {'id': folder_id}
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service._create_folder(folder_name, parent_id)
            
            assert result == folder_id
            
            # Verify the API call
            expected_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            mock_files.create.assert_called_once_with(
                body=expected_metadata,
                fields='id'
            )

    @pytest.mark.asyncio
    async def test_create_folder_root_level(self, mock_google_drive_service):
        """Test folder creation at root level (no parent)."""
        folder_id = "root_level_folder_123"
        folder_name = "RootFolder"
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {'id': folder_id}
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service._create_folder(folder_name, None)
            
            assert result == folder_id
            
            # Verify the API call (no parents field when parent_id is None)
            expected_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            mock_files.create.assert_called_once_with(
                body=expected_metadata,
                fields='id'
            )

    @pytest.mark.asyncio
    async def test_find_folder_success(self, mock_google_drive_service):
        """Test successful folder finding."""
        folder_id = "found_folder_123"
        folder_name = "ExistingFolder"
        parent_id = "parent_folder_456"
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = {
            'files': [
                {'id': folder_id, 'name': folder_name}
            ]
        }
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service._find_folder(folder_name, parent_id)
            
            assert result == folder_id
            
            # Verify the search query
            expected_query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false and '{parent_id}' in parents"
            
            mock_files.list.assert_called_once_with(
                q=expected_query,
                fields='files(id, name)'
            )

    @pytest.mark.asyncio
    async def test_find_folder_not_found(self, mock_google_drive_service):
        """Test folder finding when folder doesn't exist."""
        folder_name = "NonExistentFolder"
        parent_id = "parent_folder_456"
        
        # Setup mock service response with empty results
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = {'files': []}
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service._find_folder(folder_name, parent_id)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_find_folder_root_level(self, mock_google_drive_service):
        """Test folder finding at root level (no parent)."""
        folder_id = "root_folder_123"
        folder_name = "RootLevelFolder"
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = {
            'files': [
                {'id': folder_id, 'name': folder_name}
            ]
        }
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service._find_folder(folder_name, None)
            
            assert result == folder_id
            
            # Verify the search query (no parent constraint when parent_id is None)
            expected_query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            mock_files.list.assert_called_once_with(
                q=expected_query,
                fields='files(id, name)'
            )

    @pytest.mark.asyncio
    async def test_find_folder_multiple_matches(self, mock_google_drive_service):
        """Test folder finding when multiple folders match (returns first one)."""
        folder_name = "DuplicateFolder"
        parent_id = "parent_folder_456"
        
        # Setup mock service response with multiple matches
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = {
            'files': [
                {'id': 'first_folder_123', 'name': folder_name},
                {'id': 'second_folder_456', 'name': folder_name}
            ]
        }
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service._find_folder(folder_name, parent_id)
            
            # Should return the first match
            assert result == 'first_folder_123'


class TestFolderOperationsErrorHandling:
    """Test error handling in folder operations."""

    @pytest.mark.asyncio
    async def test_create_folder_api_error(self, mock_google_drive_service, google_api_error_responses):
        """Test folder creation with Google API error."""
        # Setup mock service to raise HttpError
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.side_effect = google_api_error_responses['server_error']
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            # The error should be handled by the decorator
            with pytest.raises(Exception):  # Will be converted by the decorator
                await service._create_folder("TestFolder", "parent_id")

    @pytest.mark.asyncio
    async def test_find_folder_api_error(self, mock_google_drive_service, google_api_error_responses):
        """Test folder finding with Google API error."""
        # Setup mock service to raise HttpError
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.side_effect = google_api_error_responses['permission_error']
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            # The error should be handled by the decorator
            with pytest.raises(Exception):  # Will be converted by the decorator
                await service._find_folder("TestFolder", "parent_id")


# Parametrized tests for different folder scenarios
@pytest.mark.parametrize("customer_email,expected_structure", [
    ("danishevsky@gmail.com", ["TranslatorWebServer", "danishevsky@gmail.com", "Temp"]),
    ("test.user@example.com", ["TranslatorWebServer", "test.user@example.com", "Temp"]),
    ("user+tag@domain.co.uk", ["TranslatorWebServer", "user+tag@domain.co.uk", "Temp"]),
])
@pytest.mark.asyncio
async def test_folder_structure_for_different_emails(customer_email, expected_structure, mock_google_drive_service):
    """Test folder structure creation for different email formats."""
    folder_ids = ["root_123", "customer_456", "temp_789"]
    
    with patch('app.services.google_drive_service.build') as mock_build, \
         patch('app.services.google_drive_service.Credentials') as mock_creds, \
         patch('app.services.google_drive_service.os.path.exists', return_value=True):
        
        mock_creds_instance = Mock()
        mock_creds_instance.valid = True
        mock_creds.from_authorized_user_file.return_value = mock_creds_instance
        mock_build.return_value = mock_google_drive_service
        
        service = GoogleDriveService()
        service._find_or_create_folder = AsyncMock(side_effect=folder_ids)
        
        result = await service.create_customer_folder_structure(customer_email)
        
        assert result == folder_ids[-1]  # Should return temp folder ID
        
        # Verify folder creation calls
        calls = service._find_or_create_folder.call_args_list
        assert len(calls) == 3
        
        # Check folder names in sequence
        for i, expected_name in enumerate(expected_structure):
            actual_name = calls[i][0][0]  # First argument of the call
            assert actual_name == expected_name