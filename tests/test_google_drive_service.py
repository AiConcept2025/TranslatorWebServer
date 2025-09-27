"""
Unit tests for Google Drive service functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import os

from app.services.google_drive_service import GoogleDriveService
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveAuthenticationError,
    GoogleDriveStorageError,
    GoogleDriveFileNotFoundError
)
from app.config import settings


@pytest.mark.unit
class TestGoogleDriveServiceInit:
    """Test Google Drive service initialization."""
    
    def test_init_disabled_google_drive_raises_error(self):
        """Test that disabled Google Drive raises storage error."""
        with patch.object(settings, 'google_drive_enabled', False):
            with pytest.raises(GoogleDriveStorageError, match="Google Drive is disabled"):
                GoogleDriveService()
    
    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.Credentials')
    def test_init_success_with_existing_token(self, mock_credentials, mock_build, mock_settings):
        """Test successful initialization with existing token."""
        # Mock existing valid credentials
        mock_creds = Mock()
        mock_creds.valid = True
        mock_credentials.from_authorized_user_file.return_value = mock_creds
        
        # Mock Google API service build
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Create service instance
        service = GoogleDriveService()
        
        assert service.service == mock_service
        mock_credentials.from_authorized_user_file.assert_called_once()
        mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds)
    
    def test_init_missing_credentials_file_raises_error(self, mock_settings):
        """Test that missing credentials file raises authentication error."""
        # Set non-existent credentials path
        mock_settings.google_drive_credentials_path = "/nonexistent/path.json"
        
        with pytest.raises(GoogleDriveAuthenticationError, match="credentials file not found"):
            GoogleDriveService()


@pytest.mark.unit
class TestGoogleDriveServiceMethods:
    """Test Google Drive service methods with mocked API."""
    
    @pytest.fixture
    def mock_service_instance(self, mock_google_api_service, mock_settings):
        """Create a mocked Google Drive service instance."""
        with patch('app.services.google_drive_service.build', return_value=mock_google_api_service), \
             patch('app.services.google_drive_service.Credentials') as mock_creds_class:
            
            mock_creds = Mock()
            mock_creds.valid = True
            mock_creds_class.from_authorized_user_file.return_value = mock_creds
            
            service = GoogleDriveService()
            return service
    
    @pytest.mark.asyncio
    async def test_create_customer_folder_structure_success(self, mock_service_instance, test_email):
        """Test successful folder structure creation."""
        # Mock folder creation to return different IDs
        with patch.object(mock_service_instance, '_find_or_create_folder') as mock_find_create:
            mock_find_create.side_effect = ["root_id", "customer_id", "temp_id"]
            
            result = await mock_service_instance.create_customer_folder_structure(test_email)
            
            assert result == "temp_id"
            assert mock_find_create.call_count == 3
            # Check calls were made with correct parameters
            calls = mock_find_create.call_args_list
            assert calls[0][0] == (mock_service_instance.root_folder, None)
            assert calls[1][0] == (test_email, "root_id")
            assert calls[2][0] == ("Temp", "customer_id")
    
    @pytest.mark.asyncio
    async def test_upload_file_to_folder_success(self, mock_service_instance, sample_md_content, test_target_language):
        """Test successful file upload."""
        folder_id = "test_folder_id"
        filename = "test_file.md"
        
        # Mock the service.files().create() call chain
        mock_create = mock_service_instance.service.files().create.return_value
        mock_create.execute.return_value = {
            'id': 'uploaded_file_id',
            'name': filename,
            'size': str(len(sample_md_content)),
            'createdTime': '2023-01-01T00:00:00.000Z',
            'webViewLink': 'https://drive.google.com/file/d/uploaded_file_id/view',
            'parents': [folder_id]
        }
        
        result = await mock_service_instance.upload_file_to_folder(
            file_content=sample_md_content,
            filename=filename,
            folder_id=folder_id,
            target_language=test_target_language
        )
        
        assert result['file_id'] == 'uploaded_file_id'
        assert result['filename'] == filename
        assert result['folder_id'] == folder_id
        assert result['target_language'] == test_target_language
        assert result['size'] == len(sample_md_content)
        
        # Verify the API call was made correctly
        mock_service_instance.service.files().create.assert_called_once()
        call_args = mock_service_instance.service.files().create.call_args
        assert call_args[1]['body']['name'] == filename
        assert call_args[1]['body']['parents'] == [folder_id]
        assert call_args[1]['body']['properties']['target_language'] == test_target_language
    
    @pytest.mark.asyncio
    async def test_update_file_metadata_success(self, mock_service_instance):
        """Test successful file metadata update."""
        file_id = "test_file_id"
        metadata = {
            'properties': {
                'target_language': 'fr',
                'customer_email': 'test@example.com'
            },
            'description': 'Updated description'
        }
        
        result = await mock_service_instance.update_file_metadata(file_id, metadata)
        
        assert result is True
        mock_service_instance.service.files().update.assert_called_once()
        call_args = mock_service_instance.service.files().update.call_args
        assert call_args[1]['fileId'] == file_id
        assert call_args[1]['body'] == metadata
    
    @pytest.mark.asyncio
    async def test_list_files_in_folder_success(self, mock_service_instance):
        """Test successful file listing."""
        folder_id = "test_folder_id"
        
        # Mock the list response
        mock_list = mock_service_instance.service.files().list.return_value
        mock_list.execute.return_value = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'document.md',
                    'size': '2048',
                    'createdTime': '2023-01-01T00:00:00.000Z',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view',
                    'mimeType': 'text/markdown',
                    'properties': {'target_language': 'es'}
                }
            ]
        }
        
        result = await mock_service_instance.list_files_in_folder(folder_id)
        
        assert len(result) == 1
        assert result[0]['file_id'] == 'file1'
        assert result[0]['filename'] == 'document.md'
        assert result[0]['size'] == 2048
        assert result[0]['folder_id'] == folder_id
        
        # Verify the API call
        mock_service_instance.service.files().list.assert_called_once()
        call_args = mock_service_instance.service.files().list.call_args
        assert f"'{folder_id}' in parents and trashed=false" in call_args[1]['q']
    
    @pytest.mark.asyncio
    async def test_delete_file_success(self, mock_service_instance):
        """Test successful file deletion."""
        file_id = "test_file_id"
        
        result = await mock_service_instance.delete_file(file_id)
        
        assert result is True
        mock_service_instance.service.files().delete.assert_called_once()
        call_args = mock_service_instance.service.files().delete.call_args
        assert call_args[1]['fileId'] == file_id
    
    @pytest.mark.asyncio
    async def test_get_folder_info_success(self, mock_service_instance):
        """Test successful folder info retrieval."""
        folder_id = "test_folder_id"
        
        # Mock list_files_in_folder
        with patch.object(mock_service_instance, 'list_files_in_folder') as mock_list:
            mock_list.return_value = [
                {'size': 1024, 'filename': 'file1.md'},
                {'size': 2048, 'filename': 'file2.md'}
            ]
            
            # Mock folder details
            mock_get = mock_service_instance.service.files().get.return_value
            mock_get.execute.return_value = {
                'name': 'Test Folder',
                'createdTime': '2023-01-01T00:00:00.000Z',
                'modifiedTime': '2023-01-02T00:00:00.000Z'
            }
            
            result = await mock_service_instance.get_folder_info(folder_id)
            
            assert result['folder_id'] == folder_id
            assert result['total_files'] == 2
            assert result['total_size_bytes'] == 3072
            assert result['total_size_mb'] == 0.0
            assert result['storage_type'] == 'google_drive'
            assert result['folder_name'] == 'Test Folder'


@pytest.mark.unit
class TestGoogleDriveServiceErrorHandling:
    """Test error handling in Google Drive service."""
    
    @pytest.fixture
    def mock_service_instance_with_errors(self, mock_settings):
        """Create a service instance that can trigger errors."""
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds_class:
            
            mock_creds = Mock()
            mock_creds.valid = True
            mock_creds_class.from_authorized_user_file.return_value = mock_creds
            
            mock_service = Mock()
            mock_build.return_value = mock_service
            
            service = GoogleDriveService()
            return service
    
    @pytest.mark.asyncio
    async def test_upload_file_api_error_raises_google_drive_error(self, mock_service_instance_with_errors, sample_md_content):
        """Test that Google API errors are properly converted to GoogleDriveError."""
        from googleapiclient.errors import HttpError
        
        # Mock HttpError
        mock_resp = Mock()
        mock_resp.status = 403
        http_error = HttpError(mock_resp, b'{"error": {"message": "Quota exceeded"}}')
        
        mock_service_instance_with_errors.service.files().create().execute.side_effect = http_error
        
        with pytest.raises(GoogleDriveError):
            await mock_service_instance_with_errors.upload_file_to_folder(
                file_content=sample_md_content,
                filename="test.md",
                folder_id="test_folder_id",
                target_language="es"
            )
    
    @pytest.mark.asyncio
    async def test_folder_creation_handles_existing_folder(self, mock_service_instance_with_errors):
        """Test folder creation when folder already exists."""
        folder_name = "ExistingFolder"
        parent_id = "parent_id"
        
        # Mock _find_folder to return an existing folder
        with patch.object(mock_service_instance_with_errors, '_find_folder', return_value="existing_folder_id"), \
             patch.object(mock_service_instance_with_errors, '_create_folder') as mock_create:
            
            result = await mock_service_instance_with_errors._find_or_create_folder(folder_name, parent_id)
            
            assert result == "existing_folder_id"
            mock_create.assert_not_called()


@pytest.mark.integration
class TestGoogleDriveServiceIntegration:
    """Integration tests for Google Drive service (requires real credentials)."""
    
    @pytest.mark.skipif(
        not os.path.exists("./credentials.json"),
        reason="Integration tests require ./credentials.json file"
    )
    @pytest.mark.asyncio
    async def test_real_folder_creation_and_cleanup(self, test_email):
        """Test real folder creation with cleanup."""
        # This test requires real Google Drive credentials
        try:
            service = GoogleDriveService()
            
            # Create folder structure
            folder_id = await service.create_customer_folder_structure(f"test_{test_email}")
            assert folder_id is not None
            
            # Get folder info
            folder_info = await service.get_folder_info(folder_id)
            assert folder_info['storage_type'] == 'google_drive'
            
        except GoogleDriveError as e:
            pytest.skip(f"Skipping integration test due to Google Drive error: {e}")
    
    @pytest.mark.skipif(
        not os.path.exists("./credentials.json"),
        reason="Integration tests require ./credentials.json file"
    )
    @pytest.mark.asyncio
    async def test_real_file_upload_and_cleanup(self, test_email, sample_md_content):
        """Test real file upload with cleanup."""
        try:
            service = GoogleDriveService()
            
            # Create folder and upload file
            folder_id = await service.create_customer_folder_structure(f"test_{test_email}")
            
            file_info = await service.upload_file_to_folder(
                file_content=sample_md_content,
                filename="test_readme.md",
                folder_id=folder_id,
                target_language="es"
            )
            
            assert file_info['file_id'] is not None
            assert file_info['google_drive_url'] is not None
            
            # Update metadata
            result = await service.update_file_metadata(
                file_info['file_id'],
                {'properties': {'test_marker': 'integration_test'}}
            )
            assert result is True
            
            # Clean up - delete the uploaded file
            delete_result = await service.delete_file(file_info['file_id'])
            assert delete_result is True
            
        except GoogleDriveError as e:
            pytest.skip(f"Skipping integration test due to Google Drive error: {e}")