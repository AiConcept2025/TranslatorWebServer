"""
Unit tests for Google Drive file operations.
"""

import pytest
import io
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload

from app.services.google_drive_service import GoogleDriveService
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveStorageError,
    GoogleDriveFileNotFoundError,
    GoogleDrivePermissionError
)


class TestFileUploadOperations:
    """Test file upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_file_to_folder_success(self, mock_google_drive_service, sample_md_content, sample_file_info):
        """Test successful file upload to Google Drive."""
        file_id = "uploaded_file_123"
        folder_id = "target_folder_456"
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {
            'id': file_id,
            'name': sample_file_info['filename'],
            'size': str(len(sample_md_content)),
            'createdTime': '2023-01-01T12:00:00Z',
            'webViewLink': f'https://drive.google.com/file/d/{file_id}/view',
            'parents': [folder_id]
        }
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service.upload_file_to_folder(
                file_content=sample_md_content,
                filename=sample_file_info['filename'],
                folder_id=folder_id,
                target_language=sample_file_info['target_language']
            )
            
            # Verify result structure
            assert result['file_id'] == file_id
            assert result['filename'] == sample_file_info['filename']
            assert result['folder_id'] == folder_id
            assert result['size'] == len(sample_md_content)
            assert result['target_language'] == sample_file_info['target_language']
            assert result['created_at'] == '2023-01-01T12:00:00Z'
            assert result['google_drive_url'] == f'https://drive.google.com/file/d/{file_id}/view'
            assert result['parents'] == [folder_id]
            
            # Verify API call was made correctly
            mock_files.create.assert_called_once()
            call_args = mock_files.create.call_args
            
            # Check metadata
            body = call_args[1]['body']
            assert body['name'] == sample_file_info['filename']
            assert body['parents'] == [folder_id]
            assert body['properties']['target_language'] == sample_file_info['target_language']
            assert body['properties']['original_filename'] == sample_file_info['filename']
            assert 'upload_timestamp' in body['properties']
            
            # Check media upload
            media_body = call_args[1]['media_body']
            assert isinstance(media_body, MediaIoBaseUpload)
            
            # Check fields
            assert call_args[1]['fields'] == 'id,name,size,createdTime,webViewLink,parents'

    @pytest.mark.asyncio
    async def test_upload_file_metadata_structure(self, mock_google_drive_service, sample_md_content):
        """Test that file upload creates correct metadata structure."""
        filename = "test_document.md"
        folder_id = "test_folder_123"
        target_language = "es"
        file_id = "test_file_456"
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.return_value = {
            'id': file_id,
            'name': filename,
            'size': str(len(sample_md_content)),
            'createdTime': '2023-01-01T12:00:00Z',
            'webViewLink': f'https://drive.google.com/file/d/{file_id}/view',
            'parents': [folder_id]
        }
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            await service.upload_file_to_folder(
                file_content=sample_md_content,
                filename=filename,
                folder_id=folder_id,
                target_language=target_language
            )
            
            # Extract the metadata that was passed to the API
            call_args = mock_files.create.call_args
            metadata = call_args[1]['body']
            
            # Verify metadata structure
            assert metadata['name'] == filename
            assert metadata['parents'] == [folder_id]
            assert metadata['description'] == f'File uploaded for translation to {target_language}'
            
            # Verify properties
            properties = metadata['properties']
            assert properties['target_language'] == target_language
            assert properties['original_filename'] == filename
            assert 'upload_timestamp' in properties
            
            # Verify timestamp format (should be ISO format)
            timestamp = properties['upload_timestamp']
            # Should be parseable as datetime
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

    @pytest.mark.asyncio
    async def test_upload_file_with_different_file_types(self, mock_google_drive_service):
        """Test file upload with different file types."""
        test_cases = [
            ("document.md", b"# Markdown content", "text/markdown"),
            ("document.pdf", b"%PDF-1.4 fake pdf", "application/pdf"),
            ("document.txt", b"Plain text content", "text/plain"),
        ]
        
        folder_id = "test_folder_123"
        target_language = "fr"
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            for filename, content, mime_type in test_cases:
                file_id = f"file_id_{filename.replace('.', '_')}"
                
                mock_create = Mock()
                mock_files.create.return_value = mock_create
                mock_create.execute.return_value = {
                    'id': file_id,
                    'name': filename,
                    'size': str(len(content)),
                    'createdTime': '2023-01-01T12:00:00Z',
                    'webViewLink': f'https://drive.google.com/file/d/{file_id}/view',
                    'parents': [folder_id]
                }
                
                result = await service.upload_file_to_folder(
                    file_content=content,
                    filename=filename,
                    folder_id=folder_id,
                    target_language=target_language
                )
                
                assert result['file_id'] == file_id
                assert result['filename'] == filename
                assert result['size'] == len(content)


class TestFileMetadataOperations:
    """Test file metadata operations."""

    @pytest.mark.asyncio
    async def test_update_file_metadata_success(self, mock_google_drive_service):
        """Test successful file metadata update."""
        file_id = "test_file_123"
        metadata = {
            'properties': {
                'status': 'translated',
                'translation_service': 'google',
                'completion_time': '2023-01-01T14:00:00Z'
            },
            'description': 'File translated successfully',
            'name': 'translated_document.md'
        }
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_update = Mock()
        mock_files.update.return_value = mock_update
        mock_update.execute.return_value = {'id': file_id}
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service.update_file_metadata(file_id, metadata)
            
            assert result is True
            
            # Verify API call
            mock_files.update.assert_called_once_with(
                fileId=file_id,
                body=metadata
            )

    @pytest.mark.asyncio
    async def test_update_file_metadata_partial_update(self, mock_google_drive_service):
        """Test file metadata update with only some fields."""
        file_id = "test_file_123"
        metadata = {
            'properties': {
                'status': 'processing'
            }
        }
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_update = Mock()
        mock_files.update.return_value = mock_update
        mock_update.execute.return_value = {'id': file_id}
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service.update_file_metadata(file_id, metadata)
            
            assert result is True
            
            # Verify API call with only properties
            expected_body = {'properties': {'status': 'processing'}}
            mock_files.update.assert_called_once_with(
                fileId=file_id,
                body=expected_body
            )

    @pytest.mark.asyncio
    async def test_update_file_metadata_empty_metadata(self, mock_google_drive_service):
        """Test file metadata update with empty metadata (no API call)."""
        file_id = "test_file_123"
        metadata = {}
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_update = Mock()
        mock_files.update.return_value = mock_update
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service.update_file_metadata(file_id, metadata)
            
            assert result is True
            
            # No API call should be made for empty metadata
            mock_files.update.assert_not_called()


class TestFileListingOperations:
    """Test file listing functionality."""

    @pytest.mark.asyncio
    async def test_list_files_in_folder_success(self, mock_google_drive_service):
        """Test successful file listing in a folder."""
        folder_id = "test_folder_123"
        
        mock_files_response = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'document1.md',
                    'size': '2048',
                    'createdTime': '2023-01-01T10:00:00Z',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view',
                    'mimeType': 'text/markdown',
                    'properties': {
                        'target_language': 'es',
                        'customer_email': 'danishevsky@gmail.com'
                    }
                },
                {
                    'id': 'file2',
                    'name': 'document2.pdf',
                    'size': '4096',
                    'createdTime': '2023-01-01T11:00:00Z',
                    'webViewLink': 'https://drive.google.com/file/d/file2/view',
                    'mimeType': 'application/pdf',
                    'properties': {
                        'target_language': 'fr',
                        'customer_email': 'danishevsky@gmail.com'
                    }
                }
            ]
        }
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = mock_files_response
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service.list_files_in_folder(folder_id)
            
            assert len(result) == 2
            
            # Verify first file
            file1 = result[0]
            assert file1['file_id'] == 'file1'
            assert file1['filename'] == 'document1.md'
            assert file1['size'] == 2048
            assert file1['folder_id'] == folder_id
            assert file1['mime_type'] == 'text/markdown'
            assert file1['properties']['target_language'] == 'es'
            
            # Verify second file
            file2 = result[1]
            assert file2['file_id'] == 'file2'
            assert file2['filename'] == 'document2.pdf'
            assert file2['size'] == 4096
            assert file2['folder_id'] == folder_id
            assert file2['mime_type'] == 'application/pdf'
            assert file2['properties']['target_language'] == 'fr'
            
            # Verify API call
            expected_query = f"'{folder_id}' in parents and trashed=false"
            mock_files.list.assert_called_once_with(
                q=expected_query,
                fields='files(id,name,size,createdTime,webViewLink,mimeType,properties)'
            )

    @pytest.mark.asyncio
    async def test_list_files_in_folder_empty(self, mock_google_drive_service):
        """Test file listing in empty folder."""
        folder_id = "empty_folder_123"
        
        # Setup mock service response with empty files
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
            
            result = await service.list_files_in_folder(folder_id)
            
            assert result == []

    @pytest.mark.asyncio
    async def test_list_files_handles_missing_size(self, mock_google_drive_service):
        """Test file listing handles files without size information."""
        folder_id = "test_folder_123"
        
        mock_files_response = {
            'files': [
                {
                    'id': 'file1',
                    'name': 'document1.md',
                    # 'size' field missing
                    'createdTime': '2023-01-01T10:00:00Z',
                    'webViewLink': 'https://drive.google.com/file/d/file1/view',
                    'mimeType': 'text/markdown',
                    'properties': {}
                }
            ]
        }
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.return_value = mock_files_response
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service.list_files_in_folder(folder_id)
            
            assert len(result) == 1
            assert result[0]['size'] == 0  # Default value for missing size


class TestFileDeleteOperations:
    """Test file deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_file_success(self, mock_google_drive_service):
        """Test successful file deletion."""
        file_id = "file_to_delete_123"
        
        # Setup mock service response
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_delete = Mock()
        mock_files.delete.return_value = mock_delete
        mock_delete.execute.return_value = None  # Delete returns None on success
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            result = await service.delete_file(file_id)
            
            assert result is True
            
            # Verify API call
            mock_files.delete.assert_called_once_with(fileId=file_id)


class TestFolderInfoOperations:
    """Test folder information retrieval functionality."""

    @pytest.mark.asyncio
    async def test_get_folder_info_success(self, mock_google_drive_service):
        """Test successful folder info retrieval."""
        folder_id = "test_folder_123"
        
        # Mock file listing for the folder
        mock_files_in_folder = [
            {'size': 1024, 'filename': 'file1.md'},
            {'size': 2048, 'filename': 'file2.pdf'},
            {'size': 512, 'filename': 'file3.txt'}
        ]
        
        # Mock folder details
        folder_details_response = {
            'name': 'TestFolder',
            'createdTime': '2023-01-01T10:00:00Z',
            'modifiedTime': '2023-01-01T12:00:00Z'
        }
        
        # Setup mock service responses
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        
        # Mock get operation for folder details
        mock_get = Mock()
        mock_files.get.return_value = mock_get
        mock_get.execute.return_value = folder_details_response
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            # Mock the list_files_in_folder method
            service.list_files_in_folder = AsyncMock(return_value=mock_files_in_folder)
            
            result = await service.get_folder_info(folder_id)
            
            # Verify result structure
            assert result['folder_id'] == folder_id
            assert result['total_files'] == 3
            assert result['total_size_bytes'] == 3584  # 1024 + 2048 + 512
            assert result['total_size_mb'] == 3.41  # Rounded to 2 decimals
            assert result['storage_type'] == 'google_drive'
            assert result['folder_name'] == 'TestFolder'
            assert result['created_at'] == '2023-01-01T10:00:00Z'
            assert result['modified_at'] == '2023-01-01T12:00:00Z'
            assert 'last_updated' in result
            
            # Verify API calls
            service.list_files_in_folder.assert_called_once_with(folder_id)
            mock_files.get.assert_called_once_with(
                fileId=folder_id,
                fields='name,createdTime,modifiedTime'
            )

    @pytest.mark.asyncio
    async def test_get_folder_info_folder_details_error(self, mock_google_drive_service):
        """Test folder info when folder details retrieval fails."""
        folder_id = "test_folder_123"
        
        # Mock file listing for the folder
        mock_files_in_folder = [
            {'size': 1024, 'filename': 'file1.md'}
        ]
        
        # Setup mock service responses
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        
        # Mock get operation to raise exception
        mock_get = Mock()
        mock_files.get.return_value = mock_get
        mock_get.execute.side_effect = Exception("Failed to get folder details")
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            service.list_files_in_folder = AsyncMock(return_value=mock_files_in_folder)
            
            result = await service.get_folder_info(folder_id)
            
            # Should still return basic info even if folder details fail
            assert result['folder_id'] == folder_id
            assert result['total_files'] == 1
            assert result['total_size_bytes'] == 1024
            assert result['storage_type'] == 'google_drive'
            
            # These fields should not be present when folder details fail
            assert 'folder_name' not in result
            assert 'created_at' not in result
            assert 'modified_at' not in result


# Parametrized tests for different file upload scenarios
@pytest.mark.parametrize("filename,content_size,target_language", [
    ("test.md", 1024, "es"),
    ("document.pdf", 5000, "fr"),
    ("file.txt", 500, "de"),
    ("long_filename_with_spaces_and_special_chars.md", 2048, "it"),
])
@pytest.mark.asyncio
async def test_upload_different_file_scenarios(filename, content_size, target_language, mock_google_drive_service):
    """Test file upload with different scenarios."""
    folder_id = "test_folder_123"
    file_content = b"x" * content_size  # Create content of specified size
    file_id = f"uploaded_{filename.replace('.', '_').replace(' ', '_')}"
    
    # Setup mock service response
    mock_files = Mock()
    mock_google_drive_service.files.return_value = mock_files
    mock_create = Mock()
    mock_files.create.return_value = mock_create
    mock_create.execute.return_value = {
        'id': file_id,
        'name': filename,
        'size': str(content_size),
        'createdTime': '2023-01-01T12:00:00Z',
        'webViewLink': f'https://drive.google.com/file/d/{file_id}/view',
        'parents': [folder_id]
    }
    
    with patch('app.services.google_drive_service.build') as mock_build, \
         patch('app.services.google_drive_service.Credentials') as mock_creds, \
         patch('app.services.google_drive_service.os.path.exists', return_value=True):
        
        mock_creds_instance = Mock()
        mock_creds_instance.valid = True
        mock_creds.from_authorized_user_file.return_value = mock_creds_instance
        mock_build.return_value = mock_google_drive_service
        
        service = GoogleDriveService()
        
        result = await service.upload_file_to_folder(
            file_content=file_content,
            filename=filename,
            folder_id=folder_id,
            target_language=target_language
        )
        
        assert result['file_id'] == file_id
        assert result['filename'] == filename
        assert result['size'] == content_size
        assert result['target_language'] == target_language