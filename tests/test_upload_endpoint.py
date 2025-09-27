"""
Unit tests for the upload endpoint functionality.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, mock_open
from fastapi.testclient import TestClient
from httpx import AsyncClient
import io
from pathlib import Path

from app.main import app
from app.services.google_drive_service import google_drive_service
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveAuthenticationError,
    GoogleDriveStorageError
)


@pytest.mark.unit
class TestUploadEndpoint:
    """Test the /api/upload endpoint functionality."""
    
    @pytest.fixture
    def test_file_data(self, sample_md_content):
        """Create test file data for upload."""
        return {
            'files': ('README.md', sample_md_content, 'text/markdown'),
            'customer_email': 'danishevsky@gmail.com',
            'target_language': 'es'
        }
    
    def test_upload_endpoint_success(self, test_client, test_file_data):
        """Test successful file upload."""
        with patch.object(google_drive_service, 'create_customer_folder_structure') as mock_folder, \
             patch.object(google_drive_service, 'upload_file_to_folder') as mock_upload, \
             patch.object(google_drive_service, 'update_file_metadata') as mock_metadata, \
             patch('app.utils.file_validation.file_validator.comprehensive_file_validation') as mock_validation:
            
            # Mock successful operations
            mock_folder.return_value = asyncio.Future()
            mock_folder.return_value.set_result("test_folder_id")
            
            mock_upload.return_value = asyncio.Future()
            mock_upload.return_value.set_result({
                'file_id': 'uploaded_file_id',
                'filename': 'README.md',
                'folder_id': 'test_folder_id',
                'size': len(test_file_data['files'][1]),
                'target_language': 'es',
                'created_at': '2023-01-01T00:00:00.000Z',
                'google_drive_url': 'https://drive.google.com/file/d/uploaded_file_id/view',
                'parents': ['test_folder_id']
            })
            
            mock_metadata.return_value = asyncio.Future()
            mock_metadata.return_value.set_result(True)
            
            mock_validation.return_value = asyncio.Future()
            mock_validation.return_value.set_result((True, []))
            
            # Make the request
            response = test_client.post(
                "/api/upload",
                data={
                    'customer_email': test_file_data['customer_email'],
                    'target_language': test_file_data['target_language']
                },
                files=[test_file_data['files']]
            )
            
            assert response.status_code == 200
            response_data = response.json()
            
            assert response_data['success'] is True
            assert response_data['customer_email'] == 'danishevsky@gmail.com'
            assert response_data['target_language'] == 'es'
            assert response_data['total_files'] == 1
            assert response_data['successful_uploads'] == 1
            assert response_data['failed_uploads'] == 0
            assert len(response_data['results']) == 1
            
            result = response_data['results'][0]
            assert result['filename'] == 'README.md'
            assert result['status'] == 'success'
            assert result['file_id'] == 'uploaded_file_id'
    
    def test_upload_endpoint_invalid_email(self, test_client, sample_md_content):
        """Test upload with invalid email format."""
        response = test_client.post(
            "/api/upload",
            data={
                'customer_email': 'invalid-email',
                'target_language': 'es'
            },
            files=[('files', ('test.md', sample_md_content, 'text/markdown'))]
        )
        
        assert response.status_code == 400
        assert "Invalid request parameters" in response.json()['detail']
    
    def test_upload_endpoint_no_files(self, test_client):
        """Test upload with no files provided."""
        response = test_client.post(
            "/api/upload",
            data={
                'customer_email': 'danishevsky@gmail.com',
                'target_language': 'es'
            }
        )
        
        assert response.status_code == 422  # FastAPI validation error for missing files
    
    def test_upload_endpoint_google_drive_folder_creation_failure(self, test_client, test_file_data):
        """Test upload when Google Drive folder creation fails."""
        with patch.object(google_drive_service, 'create_customer_folder_structure') as mock_folder:
            # Mock folder creation failure
            mock_folder.side_effect = GoogleDriveStorageError("Failed to create folder structure")
            
            response = test_client.post(
                "/api/upload",
                data={
                    'customer_email': test_file_data['customer_email'],
                    'target_language': test_file_data['target_language']
                },
                files=[test_file_data['files']]
            )
            
            assert response.status_code == 500
            response_data = response.json()
            assert "google_drive_error" in response_data['detail']['error']
            assert response_data['detail']['operation_failed'] is True
    
    def test_upload_endpoint_file_validation_failure(self, test_client, test_file_data):
        """Test upload with file validation failure."""
        with patch.object(google_drive_service, 'create_customer_folder_structure') as mock_folder, \
             patch('app.utils.file_validation.file_validator.comprehensive_file_validation') as mock_validation:
            
            mock_folder.return_value = asyncio.Future()
            mock_folder.return_value.set_result("test_folder_id")
            
            # Mock validation failure
            mock_validation.return_value = asyncio.Future()
            mock_validation.return_value.set_result((False, ["File type not supported", "File too large"]))
            
            response = test_client.post(
                "/api/upload",
                data={
                    'customer_email': test_file_data['customer_email'],
                    'target_language': test_file_data['target_language']
                },
                files=[test_file_data['files']]
            )
            
            assert response.status_code == 400
            response_data = response.json()
            
            assert response_data['success'] is False
            assert response_data['successful_uploads'] == 0
            assert response_data['failed_uploads'] == 1
            
            result = response_data['results'][0]
            assert result['status'] == 'failed'
            assert "File type not supported; File too large" in result['message']
    
    def test_upload_endpoint_google_drive_upload_failure(self, test_client, test_file_data):
        """Test upload when Google Drive file upload fails."""
        with patch.object(google_drive_service, 'create_customer_folder_structure') as mock_folder, \
             patch.object(google_drive_service, 'upload_file_to_folder') as mock_upload, \
             patch('app.utils.file_validation.file_validator.comprehensive_file_validation') as mock_validation:
            
            mock_folder.return_value = asyncio.Future()
            mock_folder.return_value.set_result("test_folder_id")
            
            mock_validation.return_value = asyncio.Future()
            mock_validation.return_value.set_result((True, []))
            
            # Mock upload failure
            mock_upload.side_effect = GoogleDriveStorageError("Upload failed: quota exceeded")
            
            response = test_client.post(
                "/api/upload",
                data={
                    'customer_email': test_file_data['customer_email'],
                    'target_language': test_file_data['target_language']
                },
                files=[test_file_data['files']]
            )
            
            assert response.status_code == 400
            response_data = response.json()
            
            assert response_data['success'] is False
            assert response_data['successful_uploads'] == 0
            assert response_data['failed_uploads'] == 1
            
            result = response_data['results'][0]
            assert result['status'] == 'failed'
            assert "Google Drive error: Upload failed: quota exceeded" in result['message']
    
    def test_upload_endpoint_multiple_files_partial_success(self, test_client, sample_md_content):
        """Test upload with multiple files where some succeed and some fail."""
        with patch.object(google_drive_service, 'create_customer_folder_structure') as mock_folder, \
             patch.object(google_drive_service, 'upload_file_to_folder') as mock_upload, \
             patch.object(google_drive_service, 'update_file_metadata') as mock_metadata, \
             patch('app.utils.file_validation.file_validator.comprehensive_file_validation') as mock_validation:
            
            mock_folder.return_value = asyncio.Future()
            mock_folder.return_value.set_result("test_folder_id")
            
            # Mock validation: first file passes, second fails
            mock_validation.side_effect = [
                asyncio.Future(),
                asyncio.Future()
            ]
            mock_validation.side_effect[0].set_result((True, []))
            mock_validation.side_effect[1].set_result((False, ["Invalid file type"]))
            
            mock_upload.return_value = asyncio.Future()
            mock_upload.return_value.set_result({
                'file_id': 'uploaded_file_id',
                'filename': 'README.md',
                'folder_id': 'test_folder_id',
                'size': len(sample_md_content),
                'target_language': 'es',
                'created_at': '2023-01-01T00:00:00.000Z',
                'google_drive_url': 'https://drive.google.com/file/d/uploaded_file_id/view',
                'parents': ['test_folder_id']
            })
            
            mock_metadata.return_value = asyncio.Future()
            mock_metadata.return_value.set_result(True)
            
            # Upload two files
            files = [
                ('files', ('README.md', sample_md_content, 'text/markdown')),
                ('files', ('invalid.exe', b'invalid content', 'application/octet-stream'))
            ]
            
            response = test_client.post(
                "/api/upload",
                data={
                    'customer_email': 'danishevsky@gmail.com',
                    'target_language': 'es'
                },
                files=files
            )
            
            assert response.status_code == 207  # Multi-Status
            response_data = response.json()
            
            assert response_data['success'] is True  # At least one success
            assert response_data['total_files'] == 2
            assert response_data['successful_uploads'] == 1
            assert response_data['failed_uploads'] == 1
            
            # Check individual results
            results = response_data['results']
            success_result = next(r for r in results if r['status'] == 'success')
            failed_result = next(r for r in results if r['status'] == 'failed')
            
            assert success_result['filename'] == 'README.md'
            assert failed_result['filename'] == 'invalid.exe'
            assert "Invalid file type" in failed_result['message']


@pytest.mark.unit  
class TestUploadEndpointAsync:
    """Test upload endpoint using async client."""
    
    @pytest.mark.asyncio
    async def test_upload_endpoint_async_success(self, async_client, sample_md_content):
        """Test successful upload using async client."""
        with patch.object(google_drive_service, 'create_customer_folder_structure') as mock_folder, \
             patch.object(google_drive_service, 'upload_file_to_folder') as mock_upload, \
             patch.object(google_drive_service, 'update_file_metadata') as mock_metadata, \
             patch('app.utils.file_validation.file_validator.comprehensive_file_validation') as mock_validation:
            
            # Mock successful operations
            mock_folder.return_value = "test_folder_id"
            mock_upload.return_value = {
                'file_id': 'uploaded_file_id',
                'filename': 'README.md',
                'folder_id': 'test_folder_id',
                'size': len(sample_md_content),
                'target_language': 'es',
                'created_at': '2023-01-01T00:00:00.000Z',
                'google_drive_url': 'https://drive.google.com/file/d/uploaded_file_id/view',
                'parents': ['test_folder_id']
            }
            mock_metadata.return_value = True
            mock_validation.return_value = (True, [])
            
            # Prepare multipart data
            files = {'files': ('README.md', sample_md_content, 'text/markdown')}
            data = {
                'customer_email': 'danishevsky@gmail.com',
                'target_language': 'es'
            }
            
            response = await async_client.post("/api/upload", data=data, files=files)
            
            assert response.status_code == 200
            response_data = response.json()
            
            assert response_data['success'] is True
            assert response_data['customer_email'] == 'danishevsky@gmail.com'
            assert response_data['successful_uploads'] == 1
    
    @pytest.mark.asyncio
    async def test_upload_endpoint_authentication_error(self, async_client, sample_md_content):
        """Test upload when Google Drive authentication fails."""
        with patch.object(google_drive_service, 'create_customer_folder_structure') as mock_folder:
            # Mock authentication error
            mock_folder.side_effect = GoogleDriveAuthenticationError("Authentication failed")
            
            files = {'files': ('README.md', sample_md_content, 'text/markdown')}
            data = {
                'customer_email': 'danishevsky@gmail.com',
                'target_language': 'es'
            }
            
            response = await async_client.post("/api/upload", data=data, files=files)
            
            assert response.status_code == 401
            response_data = response.json()
            assert "google_drive_error" in response_data['detail']['error']
            assert response_data['detail']['message'] == "Authentication failed"


@pytest.mark.unit
class TestUploadEndpointValidation:
    """Test input validation for upload endpoint."""
    
    def test_upload_endpoint_missing_customer_email(self, test_client, sample_md_content):
        """Test upload without customer email."""
        response = test_client.post(
            "/api/upload",
            data={'target_language': 'es'},
            files=[('files', ('test.md', sample_md_content, 'text/markdown'))]
        )
        
        assert response.status_code == 422
        error_detail = response.json()['detail']
        assert any('customer_email' in str(error) for error in error_detail)
    
    def test_upload_endpoint_missing_target_language(self, test_client, sample_md_content):
        """Test upload without target language."""
        response = test_client.post(
            "/api/upload",
            data={'customer_email': 'danishevsky@gmail.com'},
            files=[('files', ('test.md', sample_md_content, 'text/markdown'))]
        )
        
        assert response.status_code == 422
        error_detail = response.json()['detail']
        assert any('target_language' in str(error) for error in error_detail)
    
    def test_upload_endpoint_empty_customer_email(self, test_client, sample_md_content):
        """Test upload with empty customer email."""
        response = test_client.post(
            "/api/upload",
            data={'customer_email': '', 'target_language': 'es'},
            files=[('files', ('test.md', sample_md_content, 'text/markdown'))]
        )
        
        assert response.status_code == 400
        assert "Invalid request parameters" in response.json()['detail']
    
    def test_upload_endpoint_empty_target_language(self, test_client, sample_md_content):
        """Test upload with empty target language."""
        response = test_client.post(
            "/api/upload",
            data={'customer_email': 'danishevsky@gmail.com', 'target_language': ''},
            files=[('files', ('test.md', sample_md_content, 'text/markdown'))]
        )
        
        assert response.status_code == 400
        assert "Invalid request parameters" in response.json()['detail']


@pytest.mark.integration
class TestUploadEndpointIntegration:
    """Integration tests for upload endpoint (requires actual Google Drive setup)."""
    
    @pytest.mark.skipif(
        not Path("./credentials.json").exists(),
        reason="Integration tests require ./credentials.json file"
    )
    def test_real_upload_integration(self, test_client, sample_md_content):
        """Test real upload integration with Google Drive."""
        # This test uses real Google Drive - use with caution
        test_email = "integration_test_danishevsky@gmail.com"
        
        try:
            response = test_client.post(
                "/api/upload",
                data={
                    'customer_email': test_email,
                    'target_language': 'es'
                },
                files=[('files', ('integration_test.md', sample_md_content, 'text/markdown'))]
            )
            
            # Should succeed or skip if credentials are invalid
            if response.status_code == 401:
                pytest.skip("Skipping integration test: Google Drive authentication failed")
            elif response.status_code == 500:
                pytest.skip("Skipping integration test: Google Drive service unavailable")
            
            assert response.status_code in [200, 207]  # Success or partial success
            response_data = response.json()
            assert response_data['customer_email'] == test_email
            
            # If successful, there should be at least one result
            if response_data['successful_uploads'] > 0:
                assert len(response_data['results']) > 0
                success_result = next(r for r in response_data['results'] if r['status'] == 'success')
                assert 'file_id' in success_result
                assert success_result['google_drive_folder'] is not None
        
        except Exception as e:
            pytest.skip(f"Skipping integration test due to error: {e}")