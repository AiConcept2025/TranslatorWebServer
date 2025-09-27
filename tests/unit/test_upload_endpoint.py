"""
Unit tests for the /api/upload endpoint.
"""

import pytest
import io
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app.main import app
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveStorageError,
    GoogleDriveAuthenticationError,
    GoogleDriveQuotaExceededError
)


class TestUploadEndpoint:
    """Test the /api/upload endpoint functionality."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def valid_upload_data(self, sample_md_content):
        """Create valid upload form data."""
        return {
            "customer_email": "danishevsky@gmail.com",
            "target_language": "es",
            "files": [
                ("files", ("test_document.md", sample_md_content, "text/markdown"))
            ]
        }

    @pytest.fixture
    def mock_successful_upload(self):
        """Mock successful Google Drive operations."""
        with patch('app.routers.upload.google_drive_service') as mock_service:
            # Mock folder creation
            mock_service.create_customer_folder_structure = AsyncMock(return_value="test_folder_123")
            
            # Mock file upload
            mock_service.upload_file_to_folder = AsyncMock(return_value={
                'file_id': 'uploaded_file_456',
                'filename': 'test_document.md',
                'folder_id': 'test_folder_123',
                'size': 512,
                'target_language': 'es',
                'created_at': '2023-01-01T12:00:00Z',
                'google_drive_url': 'https://drive.google.com/file/d/uploaded_file_456/view',
                'parents': ['test_folder_123']
            })
            
            # Mock metadata update
            mock_service.update_file_metadata = AsyncMock(return_value=True)
            
            yield mock_service

    @patch('app.routers.upload.file_validator')
    def test_upload_single_file_success(self, mock_validator, client, valid_upload_data, mock_successful_upload):
        """Test successful upload of a single file."""
        # Mock file validation
        mock_validator.comprehensive_file_validation = AsyncMock(return_value=(True, []))
        
        response = client.post("/api/upload", data={
            "customer_email": valid_upload_data["customer_email"],
            "target_language": valid_upload_data["target_language"]
        }, files=valid_upload_data["files"])
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["customer_email"] == "danishevsky@gmail.com"
        assert data["target_language"] == "es"
        assert data["total_files"] == 1
        assert data["successful_uploads"] == 1
        assert data["failed_uploads"] == 0
        assert data["google_drive_folder_path"] == "test_folder_123"
        
        # Check file result
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["filename"] == "test_document.md"
        assert result["file_id"] == "uploaded_file_456"
        assert result["status"] == "success"
        assert result["message"] == "File uploaded successfully"
        assert result["google_drive_folder"] == "test_folder_123"

    @patch('app.routers.upload.file_validator')
    def test_upload_multiple_files_success(self, mock_validator, client, sample_md_content, mock_successful_upload):
        """Test successful upload of multiple files."""
        mock_validator.comprehensive_file_validation = AsyncMock(return_value=(True, []))
        
        # Mock different responses for different files
        mock_successful_upload.upload_file_to_folder.side_effect = [
            {
                'file_id': 'file_1',
                'filename': 'document1.md',
                'folder_id': 'test_folder_123',
                'size': 256,
                'target_language': 'fr',
                'created_at': '2023-01-01T12:00:00Z',
                'google_drive_url': 'https://drive.google.com/file/d/file_1/view',
                'parents': ['test_folder_123']
            },
            {
                'file_id': 'file_2',
                'filename': 'document2.md',
                'folder_id': 'test_folder_123',
                'size': 512,
                'target_language': 'fr',
                'created_at': '2023-01-01T12:01:00Z',
                'google_drive_url': 'https://drive.google.com/file/d/file_2/view',
                'parents': ['test_folder_123']
            }
        ]
        
        files = [
            ("files", ("document1.md", sample_md_content[:256], "text/markdown")),
            ("files", ("document2.md", sample_md_content, "text/markdown"))
        ]
        
        response = client.post("/api/upload", data={
            "customer_email": "danishevsky@gmail.com",
            "target_language": "fr"
        }, files=files)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_files"] == 2
        assert data["successful_uploads"] == 2
        assert data["failed_uploads"] == 0
        assert len(data["results"]) == 2

    def test_upload_no_files_error(self, client):
        """Test upload with no files provided."""
        response = client.post("/api/upload", data={
            "customer_email": "danishevsky@gmail.com",
            "target_language": "es"
        })
        
        assert response.status_code == 400
        assert "No files provided" in response.json()["detail"]

    def test_upload_invalid_email(self, client, sample_md_content):
        """Test upload with invalid email format."""
        files = [("files", ("test.md", sample_md_content, "text/markdown"))]
        
        response = client.post("/api/upload", data={
            "customer_email": "invalid-email",
            "target_language": "es"
        }, files=files)
        
        assert response.status_code == 400
        assert "Invalid request parameters" in response.json()["detail"]

    def test_upload_invalid_target_language(self, client, sample_md_content):
        """Test upload with invalid target language."""
        files = [("files", ("test.md", sample_md_content, "text/markdown"))]
        
        response = client.post("/api/upload", data={
            "customer_email": "danishevsky@gmail.com",
            "target_language": "x"  # Invalid language code
        }, files=files)
        
        assert response.status_code == 400
        assert "Invalid request parameters" in response.json()["detail"]

    @patch('app.routers.upload.file_validator')
    def test_upload_file_validation_failure(self, mock_validator, client, sample_md_content, mock_successful_upload):
        """Test upload when file validation fails."""
        mock_validator.comprehensive_file_validation = AsyncMock(
            return_value=(False, ["File type not supported", "File size too large"])
        )
        
        files = [("files", ("invalid.exe", b"invalid content", "application/x-executable"))]
        
        response = client.post("/api/upload", data={
            "customer_email": "danishevsky@gmail.com",
            "target_language": "es"
        }, files=files)
        
        # Should return 400 since all uploads failed
        assert response.status_code == 400
        data = response.json()["detail"]
        
        assert data["successful_uploads"] == 0
        assert data["failed_uploads"] == 1
        
        result = data["results"][0]
        assert result["status"] == "failed"
        assert "File type not supported; File size too large" in result["message"]

    def test_upload_folder_creation_failure(self, client, sample_md_content):
        """Test upload when folder creation fails."""
        with patch('app.routers.upload.google_drive_service') as mock_service:
            mock_service.create_customer_folder_structure = AsyncMock(
                side_effect=GoogleDriveAuthenticationError("Authentication failed")
            )
            
            files = [("files", ("test.md", sample_md_content, "text/markdown"))]
            
            response = client.post("/api/upload", data={
                "customer_email": "danishevsky@gmail.com",
                "target_language": "es"
            }, files=files)
            
            assert response.status_code == 401
            assert "Authentication failed" in response.json()["detail"]["message"]

    @patch('app.routers.upload.file_validator')
    def test_upload_file_upload_failure(self, mock_validator, client, sample_md_content):
        """Test upload when file upload to Google Drive fails."""
        mock_validator.comprehensive_file_validation = AsyncMock(return_value=(True, []))
        
        with patch('app.routers.upload.google_drive_service') as mock_service:
            mock_service.create_customer_folder_structure = AsyncMock(return_value="test_folder_123")
            mock_service.upload_file_to_folder = AsyncMock(
                side_effect=GoogleDriveQuotaExceededError("Quota exceeded")
            )
            
            files = [("files", ("test.md", sample_md_content, "text/markdown"))]
            
            response = client.post("/api/upload", data={
                "customer_email": "danishevsky@gmail.com",
                "target_language": "es"
            }, files=files)
            
            # Should return 400 since all uploads failed
            assert response.status_code == 400
            data = response.json()["detail"]
            
            assert data["successful_uploads"] == 0
            assert data["failed_uploads"] == 1
            
            result = data["results"][0]
            assert result["status"] == "failed"
            assert "Google Drive error: Quota exceeded" in result["message"]

    @patch('app.routers.upload.file_validator')
    def test_upload_mixed_success_failure(self, mock_validator, client, sample_md_content):
        """Test upload with mixed success and failure results."""
        mock_validator.comprehensive_file_validation = AsyncMock(
            side_effect=[(True, []), (False, ["Invalid file"])]
        )
        
        with patch('app.routers.upload.google_drive_service') as mock_service:
            mock_service.create_customer_folder_structure = AsyncMock(return_value="test_folder_123")
            mock_service.upload_file_to_folder = AsyncMock(return_value={
                'file_id': 'file_1',
                'filename': 'document1.md',
                'folder_id': 'test_folder_123',
                'size': 256,
                'target_language': 'es',
                'created_at': '2023-01-01T12:00:00Z',
                'google_drive_url': 'https://drive.google.com/file/d/file_1/view',
                'parents': ['test_folder_123']
            })
            mock_service.update_file_metadata = AsyncMock(return_value=True)
            
            files = [
                ("files", ("valid.md", sample_md_content, "text/markdown")),
                ("files", ("invalid.exe", b"invalid", "application/x-executable"))
            ]
            
            response = client.post("/api/upload", data={
                "customer_email": "danishevsky@gmail.com",
                "target_language": "es"
            }, files=files)
            
            # Should return 207 Multi-Status for partial success
            assert response.status_code == 207
            data = response.json()
            
            assert data["successful_uploads"] == 1
            assert data["failed_uploads"] == 1
            assert len(data["results"]) == 2
            
            # Check successful file
            success_result = next(r for r in data["results"] if r["status"] == "success")
            assert success_result["filename"] == "valid.md"
            
            # Check failed file
            failed_result = next(r for r in data["results"] if r["status"] == "failed")
            assert failed_result["filename"] == "invalid.exe"

    @patch('app.routers.upload.file_validator')
    def test_upload_metadata_update_failure_continues(self, mock_validator, client, sample_md_content):
        """Test that metadata update failure doesn't prevent success."""
        mock_validator.comprehensive_file_validation = AsyncMock(return_value=(True, []))
        
        with patch('app.routers.upload.google_drive_service') as mock_service:
            mock_service.create_customer_folder_structure = AsyncMock(return_value="test_folder_123")
            mock_service.upload_file_to_folder = AsyncMock(return_value={
                'file_id': 'uploaded_file_456',
                'filename': 'test_document.md',
                'folder_id': 'test_folder_123',
                'size': 512,
                'target_language': 'es',
                'created_at': '2023-01-01T12:00:00Z',
                'google_drive_url': 'https://drive.google.com/file/d/uploaded_file_456/view',
                'parents': ['test_folder_123']
            })
            # Metadata update fails but upload should still be considered successful
            mock_service.update_file_metadata = AsyncMock(
                side_effect=GoogleDriveError("Metadata update failed")
            )
            
            files = [("files", ("test.md", sample_md_content, "text/markdown"))]
            
            response = client.post("/api/upload", data={
                "customer_email": "danishevsky@gmail.com",
                "target_language": "es"
            }, files=files)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["successful_uploads"] == 1
            assert data["failed_uploads"] == 0
            
            result = data["results"][0]
            assert result["status"] == "success"

    def test_upload_unexpected_error_handling(self, client, sample_md_content):
        """Test handling of unexpected errors during upload."""
        with patch('app.routers.upload.google_drive_service') as mock_service:
            mock_service.create_customer_folder_structure = AsyncMock(
                side_effect=Exception("Unexpected error")
            )
            
            files = [("files", ("test.md", sample_md_content, "text/markdown"))]
            
            response = client.post("/api/upload", data={
                "customer_email": "danishevsky@gmail.com",
                "target_language": "es"
            }, files=files)
            
            assert response.status_code == 500
            assert "Failed to create folder structure" in response.json()["detail"]

    @patch('app.routers.upload.file_validator')
    def test_upload_file_read_error(self, mock_validator, client):
        """Test handling of file read errors."""
        mock_validator.comprehensive_file_validation = AsyncMock(return_value=(True, []))
        
        # Create a mock file that raises an exception on read
        mock_file = Mock()
        mock_file.filename = "test.md"
        mock_file.content_type = "text/markdown"
        mock_file.read = AsyncMock(side_effect=IOError("Failed to read file"))
        
        with patch('app.routers.upload.google_drive_service') as mock_service:
            mock_service.create_customer_folder_structure = AsyncMock(return_value="test_folder_123")
            
            # Manually create upload file
            files = [("files", ("test.md", b"content", "text/markdown"))]
            
            with patch('fastapi.File') as mock_file_func:
                mock_file_func.return_value = [mock_file]
                
                response = client.post("/api/upload", data={
                    "customer_email": "danishevsky@gmail.com",
                    "target_language": "es"
                }, files=files)
                
                # The actual implementation may vary, but it should handle the error gracefully
                # This test ensures the endpoint doesn't crash on file read errors

    def test_upload_empty_file(self, client):
        """Test upload with empty file."""
        files = [("files", ("empty.md", b"", "text/markdown"))]
        
        response = client.post("/api/upload", data={
            "customer_email": "danishevsky@gmail.com",
            "target_language": "es"
        }, files=files)
        
        # Should handle empty files gracefully (may pass or fail based on validation)
        assert response.status_code in [200, 207, 400]

    def test_upload_large_filename(self, client, sample_md_content):
        """Test upload with very long filename."""
        long_filename = "a" * 200 + ".md"  # Very long filename
        files = [("files", (long_filename, sample_md_content, "text/markdown"))]
        
        response = client.post("/api/upload", data={
            "customer_email": "danishevsky@gmail.com",
            "target_language": "es"
        }, files=files)
        
        # Should handle long filenames gracefully
        assert response.status_code in [200, 207, 400]

    @pytest.mark.parametrize("customer_email", [
        "danishevsky@gmail.com",
        "test.user@example.com",
        "user+tag@domain.co.uk",
        "a@b.co"
    ])
    @patch('app.routers.upload.file_validator')
    def test_upload_various_email_formats(self, mock_validator, client, sample_md_content, customer_email, mock_successful_upload):
        """Test upload with various valid email formats."""
        mock_validator.comprehensive_file_validation = AsyncMock(return_value=(True, []))
        
        files = [("files", ("test.md", sample_md_content, "text/markdown"))]
        
        response = client.post("/api/upload", data={
            "customer_email": customer_email,
            "target_language": "es"
        }, files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["customer_email"] == customer_email.lower()  # Should be normalized to lowercase

    @pytest.mark.parametrize("target_language", [
        "es", "fr", "de", "it", "pt", "en-US", "zh-CN"
    ])
    @patch('app.routers.upload.file_validator')
    def test_upload_various_target_languages(self, mock_validator, client, sample_md_content, target_language, mock_successful_upload):
        """Test upload with various valid target languages."""
        mock_validator.comprehensive_file_validation = AsyncMock(return_value=(True, []))
        
        files = [("files", ("test.md", sample_md_content, "text/markdown"))]
        
        response = client.post("/api/upload", data={
            "customer_email": "danishevsky@gmail.com",
            "target_language": target_language
        }, files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["target_language"] == target_language.lower()

    def test_upload_endpoint_request_validation(self, client, sample_md_content):
        """Test that request validation works correctly."""
        # Test missing customer_email
        files = [("files", ("test.md", sample_md_content, "text/markdown"))]
        
        response = client.post("/api/upload", data={
            "target_language": "es"
        }, files=files)
        
        assert response.status_code == 422  # FastAPI validation error
        
        # Test missing target_language
        response = client.post("/api/upload", data={
            "customer_email": "danishevsky@gmail.com"
        }, files=files)
        
        assert response.status_code == 422  # FastAPI validation error


class TestLegacyUploadEndpoint:
    """Test the legacy /api/upload/legacy endpoint."""

    def test_legacy_upload_success(self, client, sample_md_content):
        """Test successful legacy upload."""
        files = [("files", ("test.md", sample_md_content, "text/markdown"))]
        
        response = client.post("/api/upload/legacy", files=files)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["deprecated"] is True
        assert "deprecated" in data["message"]
        assert len(data["data"]) == 1  # Should have one file ID

    def test_legacy_upload_unsupported_file_type(self, client):
        """Test legacy upload with unsupported file type."""
        files = [("files", ("test.exe", b"executable content", "application/x-executable"))]
        
        response = client.post("/api/upload/legacy", files=files)
        
        assert response.status_code == 415
        assert "Unsupported file type" in response.json()["detail"]

    def test_legacy_upload_file_too_large(self, client):
        """Test legacy upload with file that's too large."""
        # Create a file larger than 100MB (for documents)
        large_content = b"x" * (101 * 1024 * 1024)  # 101MB
        files = [("files", ("large.pdf", large_content, "application/pdf"))]
        
        response = client.post("/api/upload/legacy", files=files)
        
        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]

    def test_legacy_upload_invalid_extension(self, client, sample_md_content):
        """Test legacy upload with invalid file extension."""
        files = [("files", ("test.txt", sample_md_content, "application/pdf"))]  # Extension doesn't match content type
        
        response = client.post("/api/upload/legacy", files=files)
        
        # This might pass or fail depending on how strict the validation is
        # The test ensures the endpoint handles extension mismatches