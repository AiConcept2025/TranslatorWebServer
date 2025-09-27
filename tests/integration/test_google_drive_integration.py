"""
Integration tests for Google Drive functionality.

These tests require actual Google Drive credentials and will create/modify
files in Google Drive. They are skipped if credentials are not available.
"""

import pytest
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from app.services.google_drive_service import GoogleDriveService
from app.config import Settings
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveAuthenticationError,
    GoogleDriveStorageError
)


@pytest.mark.integration
class TestGoogleDriveIntegrationService:
    """Integration tests for Google Drive service with real API calls."""

    @pytest.fixture(scope="class")
    def integration_service(self, integration_test_settings):
        """Create a GoogleDriveService instance for integration testing."""
        with patch('app.services.google_drive_service.settings', integration_test_settings):
            try:
                service = GoogleDriveService()
                yield service
            except GoogleDriveAuthenticationError:
                pytest.skip("Google Drive authentication failed - check credentials")
            except Exception as e:
                pytest.skip(f"Failed to initialize Google Drive service: {e}")

    @pytest.fixture
    def test_customer_email(self):
        """Test customer email for folder structure."""
        return "integration.test@example.com"

    @pytest.fixture
    def test_file_content(self):
        """Sample file content for upload testing."""
        return b"""# Integration Test Document

This is a test document created by the TranslatorWebServer integration tests.

## Test Information
- Test Type: Google Drive Integration
- Customer Email: integration.test@example.com  
- Target Language: Spanish (es)
- Timestamp: Generated during test execution

## Test Content
This document tests the complete Google Drive workflow including:
1. Folder structure creation
2. File upload
3. Metadata management
4. File listing
5. Cleanup operations

**Note**: This file should be automatically cleaned up after tests complete.
"""

    @pytest.mark.asyncio
    async def test_create_customer_folder_structure_integration(self, integration_service, test_customer_email):
        """Test creating customer folder structure in real Google Drive."""
        folder_id = await integration_service.create_customer_folder_structure(test_customer_email)
        
        assert folder_id is not None
        assert isinstance(folder_id, str)
        assert len(folder_id) > 0
        
        # Store folder_id for cleanup
        integration_service._test_folder_id = folder_id

    @pytest.mark.asyncio
    async def test_upload_file_integration(self, integration_service, test_customer_email, test_file_content):
        """Test uploading file to Google Drive."""
        # Ensure folder structure exists
        if not hasattr(integration_service, '_test_folder_id'):
            folder_id = await integration_service.create_customer_folder_structure(test_customer_email)
            integration_service._test_folder_id = folder_id
        else:
            folder_id = integration_service._test_folder_id
        
        file_info = await integration_service.upload_file_to_folder(
            file_content=test_file_content,
            filename="integration_test.md",
            folder_id=folder_id,
            target_language="es"
        )
        
        assert file_info is not None
        assert file_info['file_id'] is not None
        assert file_info['filename'] == "integration_test.md"
        assert file_info['folder_id'] == folder_id
        assert file_info['size'] == len(test_file_content)
        assert file_info['target_language'] == "es"
        assert file_info['google_drive_url'] is not None
        assert file_info['created_at'] is not None
        
        # Store file_id for subsequent tests
        integration_service._test_file_id = file_info['file_id']

    @pytest.mark.asyncio
    async def test_update_file_metadata_integration(self, integration_service):
        """Test updating file metadata in Google Drive."""
        if not hasattr(integration_service, '_test_file_id'):
            pytest.skip("File upload test must run first")
        
        file_id = integration_service._test_file_id
        metadata = {
            'properties': {
                'test_status': 'integration_tested',
                'test_timestamp': '2023-01-01T12:00:00Z',
                'translation_status': 'pending'
            },
            'description': 'Integration test file - updated metadata'
        }
        
        result = await integration_service.update_file_metadata(file_id, metadata)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_list_files_in_folder_integration(self, integration_service):
        """Test listing files in Google Drive folder."""
        if not hasattr(integration_service, '_test_folder_id'):
            pytest.skip("Folder creation test must run first")
        
        folder_id = integration_service._test_folder_id
        files = await integration_service.list_files_in_folder(folder_id)
        
        assert isinstance(files, list)
        # Should have at least the file we uploaded
        assert len(files) >= 1
        
        # Find our test file
        test_file = next((f for f in files if f['filename'] == 'integration_test.md'), None)
        assert test_file is not None
        assert test_file['file_id'] is not None
        assert test_file['folder_id'] == folder_id
        assert test_file['size'] > 0

    @pytest.mark.asyncio
    async def test_get_folder_info_integration(self, integration_service):
        """Test getting folder information from Google Drive."""
        if not hasattr(integration_service, '_test_folder_id'):
            pytest.skip("Folder creation test must run first")
        
        folder_id = integration_service._test_folder_id
        folder_info = await integration_service.get_folder_info(folder_id)
        
        assert folder_info is not None
        assert folder_info['folder_id'] == folder_id
        assert folder_info['total_files'] >= 1  # At least our test file
        assert folder_info['total_size_bytes'] > 0
        assert folder_info['total_size_mb'] > 0
        assert folder_info['storage_type'] == 'google_drive'
        assert 'last_updated' in folder_info

    @pytest.mark.asyncio
    async def test_delete_file_integration(self, integration_service):
        """Test deleting file from Google Drive."""
        if not hasattr(integration_service, '_test_file_id'):
            pytest.skip("File upload test must run first")
        
        file_id = integration_service._test_file_id
        result = await integration_service.delete_file(file_id)
        
        assert result is True
        
        # Verify file is deleted by trying to list files again
        if hasattr(integration_service, '_test_folder_id'):
            folder_id = integration_service._test_folder_id
            files = await integration_service.list_files_in_folder(folder_id)
            
            # Our test file should no longer be in the list
            test_file = next((f for f in files if f['file_id'] == file_id), None)
            assert test_file is None


@pytest.mark.integration
class TestGoogleDriveIntegrationEndToEnd:
    """End-to-end integration tests with real Google Drive."""

    @pytest.mark.asyncio
    async def test_complete_workflow_integration(self, integration_test_settings, existing_md_file_path):
        """Test complete workflow from service creation to cleanup."""
        if existing_md_file_path is None:
            pytest.skip("No .md test files found")
        
        # Read actual file content
        with open(existing_md_file_path, 'rb') as f:
            file_content = f.read()
        
        filename = os.path.basename(existing_md_file_path)
        customer_email = "complete.workflow.test@example.com"
        target_language = "fr"
        
        # Create service
        with patch('app.services.google_drive_service.settings', integration_test_settings):
            service = GoogleDriveService()
        
        try:
            # Step 1: Create folder structure
            folder_id = await service.create_customer_folder_structure(customer_email)
            assert folder_id is not None
            
            # Step 2: Upload file
            file_info = await service.upload_file_to_folder(
                file_content=file_content,
                filename=filename,
                folder_id=folder_id,
                target_language=target_language
            )
            
            assert file_info['file_id'] is not None
            assert file_info['filename'] == filename
            assert file_info['size'] == len(file_content)
            
            file_id = file_info['file_id']
            
            # Step 3: Update metadata
            metadata = {
                'properties': {
                    'workflow_test': 'complete',
                    'customer_email': customer_email,
                    'target_language': target_language,
                    'test_type': 'end_to_end_integration'
                }
            }
            
            update_result = await service.update_file_metadata(file_id, metadata)
            assert update_result is True
            
            # Step 4: List files and verify
            files = await service.list_files_in_folder(folder_id)
            uploaded_file = next((f for f in files if f['file_id'] == file_id), None)
            assert uploaded_file is not None
            assert uploaded_file['filename'] == filename
            
            # Step 5: Get folder info
            folder_info = await service.get_folder_info(folder_id)
            assert folder_info['total_files'] >= 1
            assert folder_info['total_size_bytes'] >= len(file_content)
            
            # Step 6: Cleanup - delete file
            delete_result = await service.delete_file(file_id)
            assert delete_result is True
            
            # Verify deletion
            files_after_delete = await service.list_files_in_folder(folder_id)
            deleted_file = next((f for f in files_after_delete if f['file_id'] == file_id), None)
            assert deleted_file is None
            
        except GoogleDriveAuthenticationError:
            pytest.skip("Google Drive authentication failed - check credentials")
        except Exception as e:
            pytest.fail(f"End-to-end integration test failed: {e}")

    @pytest.mark.asyncio
    async def test_multiple_files_workflow_integration(self, integration_test_settings, sample_md_content):
        """Test workflow with multiple files."""
        customer_email = "multiple.files.test@example.com"
        target_language = "de"
        
        # Create different file contents
        files_to_upload = [
            ("document1.md", sample_md_content),
            ("document2.md", sample_md_content + b"\n\n## Additional Content\nThis is document 2."),
            ("document3.md", b"# Document 3\n\nThis is the third document for testing.")
        ]
        
        with patch('app.services.google_drive_service.settings', integration_test_settings):
            service = GoogleDriveService()
        
        try:
            # Create folder structure
            folder_id = await service.create_customer_folder_structure(customer_email)
            
            uploaded_file_ids = []
            
            # Upload multiple files
            for filename, content in files_to_upload:
                file_info = await service.upload_file_to_folder(
                    file_content=content,
                    filename=filename,
                    folder_id=folder_id,
                    target_language=target_language
                )
                
                uploaded_file_ids.append(file_info['file_id'])
                assert file_info['filename'] == filename
                assert file_info['size'] == len(content)
            
            # Verify all files are listed
            files = await service.list_files_in_folder(folder_id)
            uploaded_filenames = [f['filename'] for f in files if f['file_id'] in uploaded_file_ids]
            expected_filenames = [filename for filename, _ in files_to_upload]
            
            for expected_filename in expected_filenames:
                assert expected_filename in uploaded_filenames
            
            # Get folder info and verify totals
            folder_info = await service.get_folder_info(folder_id)
            assert folder_info['total_files'] >= len(files_to_upload)
            
            expected_total_size = sum(len(content) for _, content in files_to_upload)
            assert folder_info['total_size_bytes'] >= expected_total_size
            
            # Cleanup - delete all uploaded files
            for file_id in uploaded_file_ids:
                delete_result = await service.delete_file(file_id)
                assert delete_result is True
            
        except GoogleDriveAuthenticationError:
            pytest.skip("Google Drive authentication failed - check credentials")
        except Exception as e:
            pytest.fail(f"Multiple files integration test failed: {e}")

    @pytest.mark.asyncio
    async def test_large_file_upload_integration(self, integration_test_settings):
        """Test uploading larger file to Google Drive."""
        customer_email = "large.file.test@example.com"
        target_language = "it"
        
        # Create larger content (1MB)
        large_content = b"# Large File Test\n\n" + (b"This is repeated content for large file testing. " * 20000)
        filename = "large_test_file.md"
        
        with patch('app.services.google_drive_service.settings', integration_test_settings):
            service = GoogleDriveService()
        
        try:
            # Create folder and upload large file
            folder_id = await service.create_customer_folder_structure(customer_email)
            
            file_info = await service.upload_file_to_folder(
                file_content=large_content,
                filename=filename,
                folder_id=folder_id,
                target_language=target_language
            )
            
            assert file_info['file_id'] is not None
            assert file_info['filename'] == filename
            assert file_info['size'] == len(large_content)
            
            # Verify file appears in listing
            files = await service.list_files_in_folder(folder_id)
            large_file = next((f for f in files if f['file_id'] == file_info['file_id']), None)
            assert large_file is not None
            assert large_file['size'] == len(large_content)
            
            # Cleanup
            delete_result = await service.delete_file(file_info['file_id'])
            assert delete_result is True
            
        except GoogleDriveAuthenticationError:
            pytest.skip("Google Drive authentication failed - check credentials")
        except Exception as e:
            pytest.fail(f"Large file integration test failed: {e}")


@pytest.mark.integration
class TestGoogleDriveIntegrationErrors:
    """Integration tests for error scenarios with real Google Drive."""

    @pytest.mark.asyncio
    async def test_invalid_folder_id_operations(self, integration_test_settings):
        """Test operations with invalid folder ID."""
        with patch('app.services.google_drive_service.settings', integration_test_settings):
            service = GoogleDriveService()
        
        try:
            # Try to list files in non-existent folder
            with pytest.raises(GoogleDriveError):
                await service.list_files_in_folder("invalid_folder_id_12345")
            
            # Try to upload to non-existent folder
            with pytest.raises(GoogleDriveError):
                await service.upload_file_to_folder(
                    file_content=b"test content",
                    filename="test.md",
                    folder_id="invalid_folder_id_12345",
                    target_language="es"
                )
            
        except GoogleDriveAuthenticationError:
            pytest.skip("Google Drive authentication failed - check credentials")

    @pytest.mark.asyncio
    async def test_invalid_file_id_operations(self, integration_test_settings):
        """Test operations with invalid file ID."""
        with patch('app.services.google_drive_service.settings', integration_test_settings):
            service = GoogleDriveService()
        
        try:
            # Try to update metadata for non-existent file
            with pytest.raises(GoogleDriveError):
                await service.update_file_metadata(
                    "invalid_file_id_12345",
                    {"properties": {"test": "value"}}
                )
            
            # Try to delete non-existent file
            with pytest.raises(GoogleDriveError):
                await service.delete_file("invalid_file_id_12345")
            
        except GoogleDriveAuthenticationError:
            pytest.skip("Google Drive authentication failed - check credentials")


# Marker for slow tests (integration tests)
pytestmark = pytest.mark.slow


# Skip all integration tests if credentials are not available
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


# Custom pytest collection hook to skip integration tests by default
def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle integration test skipping."""
    if config.getoption("--run-integration"):
        # Don't skip integration tests if explicitly requested
        return
    
    skip_integration = pytest.mark.skip(reason="Integration tests skipped by default. Use --run-integration to run.")
    
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires Google Drive credentials)"
    )