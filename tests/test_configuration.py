"""
Tests for configuration and exception handling.
"""

import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch
from pathlib import Path

from app.config import settings, Settings
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveAuthenticationError,
    GoogleDriveQuotaExceededError,
    GoogleDriveFileNotFoundError,
    GoogleDrivePermissionError,
    GoogleDriveStorageError,
    handle_google_drive_error,
    google_drive_error_to_http_exception
)


@pytest.mark.unit
class TestConfiguration:
    """Test configuration loading and validation."""
    
    def test_settings_loads_google_drive_config(self):
        """Test that Google Drive settings are loaded correctly."""
        # Test current settings
        assert hasattr(settings, 'google_drive_enabled')
        assert hasattr(settings, 'google_drive_credentials_path')
        assert hasattr(settings, 'google_drive_token_path')
        assert hasattr(settings, 'google_drive_root_folder')
        assert hasattr(settings, 'google_drive_application_name')
        assert hasattr(settings, 'google_drive_scopes')
    
    def test_settings_google_drive_enabled_default(self):
        """Test Google Drive enabled default value."""
        # Current implementation should have it enabled
        assert settings.google_drive_enabled is True
    
    def test_settings_google_drive_paths_default(self):
        """Test Google Drive file paths defaults."""
        assert settings.google_drive_credentials_path == "./credentials.json"
        assert settings.google_drive_token_path == "./token.json"
    
    def test_settings_google_drive_folder_config(self):
        """Test Google Drive folder configuration."""
        assert settings.google_drive_root_folder == "TranslatorWebServer"
        assert settings.google_drive_application_name == "TranslatorWebServer"
    
    def test_settings_google_drive_scopes(self):
        """Test Google Drive API scopes configuration."""
        scopes = settings.google_drive_scopes
        assert "https://www.googleapis.com/auth/drive.file" in scopes
        assert "https://www.googleapis.com/auth/drive.metadata" in scopes
    
    def test_file_size_limits_configuration(self):
        """Test file size limits are configured correctly."""
        assert hasattr(settings, 'max_document_size')
        assert hasattr(settings, 'max_image_size')
        assert settings.max_document_size == 104857600  # 100MB
        assert settings.max_image_size == 52428800      # 50MB
    
    def test_settings_with_env_override(self, temp_credentials_file, temp_token_file):
        """Test settings override with environment variables."""
        with patch.dict(os.environ, {
            'GOOGLE_DRIVE_ENABLED': 'false',
            'GOOGLE_DRIVE_CREDENTIALS_PATH': temp_credentials_file,
            'GOOGLE_DRIVE_TOKEN_PATH': temp_token_file,
            'GOOGLE_DRIVE_ROOT_FOLDER': 'TestFolder',
            'GOOGLE_DRIVE_APPLICATION_NAME': 'TestApp'
        }):
            # Create new settings instance to pick up env vars
            test_settings = Settings()
            
            assert test_settings.google_drive_enabled is False
            assert test_settings.google_drive_credentials_path == temp_credentials_file
            assert test_settings.google_drive_token_path == temp_token_file
            assert test_settings.google_drive_root_folder == "TestFolder"
            assert test_settings.google_drive_application_name == "TestApp"


@pytest.mark.unit
class TestGoogleDriveExceptions:
    """Test Google Drive exception handling."""
    
    def test_google_drive_error_base_class(self):
        """Test base GoogleDriveError class."""
        error = GoogleDriveError("Test error", 500)
        assert str(error) == "Test error"
        assert error.status_code == 500
        assert error.original_error is None
    
    def test_google_drive_authentication_error(self):
        """Test GoogleDriveAuthenticationError."""
        original_error = Exception("Original error")
        error = GoogleDriveAuthenticationError("Auth failed", original_error)
        
        assert str(error) == "Auth failed"
        assert error.status_code == 401
        assert error.original_error == original_error
    
    def test_google_drive_quota_exceeded_error(self):
        """Test GoogleDriveQuotaExceededError."""
        error = GoogleDriveQuotaExceededError("Quota exceeded")
        assert str(error) == "Quota exceeded"
        assert error.status_code == 429
    
    def test_google_drive_file_not_found_error(self):
        """Test GoogleDriveFileNotFoundError."""
        error = GoogleDriveFileNotFoundError("File not found")
        assert str(error) == "File not found"
        assert error.status_code == 404
    
    def test_google_drive_permission_error(self):
        """Test GoogleDrivePermissionError."""
        error = GoogleDrivePermissionError("Permission denied")
        assert str(error) == "Permission denied"
        assert error.status_code == 403
    
    def test_google_drive_storage_error(self):
        """Test GoogleDriveStorageError."""
        error = GoogleDriveStorageError("Storage failed")
        assert str(error) == "Storage failed"
        assert error.status_code == 500
    
    def test_handle_google_drive_error_http_401(self):
        """Test handling HTTP 401 error."""
        from googleapiclient.errors import HttpError
        
        mock_resp = Mock()
        mock_resp.status = 401
        http_error = HttpError(mock_resp, b'{"error": {"message": "Unauthorized"}}')
        
        result = handle_google_drive_error(http_error, "test operation")
        
        assert isinstance(result, GoogleDriveAuthenticationError)
        assert "Authentication failed during test operation" in result.message
    
    def test_handle_google_drive_error_http_403_quota(self):
        """Test handling HTTP 403 quota error."""
        from googleapiclient.errors import HttpError
        
        mock_resp = Mock()
        mock_resp.status = 403
        http_error = HttpError(mock_resp, b'{"error": {"message": "Quota exceeded"}}')
        http_error.error_details = [{"reason": "quotaExceeded"}]
        
        result = handle_google_drive_error(http_error, "test operation")
        
        assert isinstance(result, GoogleDriveQuotaExceededError)
        assert "Google Drive quota exceeded during test operation" in result.message
    
    def test_handle_google_drive_error_http_403_permission(self):
        """Test handling HTTP 403 permission error."""
        from googleapiclient.errors import HttpError
        
        mock_resp = Mock()
        mock_resp.status = 403
        http_error = HttpError(mock_resp, b'{"error": {"message": "Permission denied"}}')
        http_error.error_details = [{"reason": "permissionDenied"}]
        
        result = handle_google_drive_error(http_error, "test operation")
        
        assert isinstance(result, GoogleDrivePermissionError)
        assert "Permission denied during test operation" in result.message
    
    def test_handle_google_drive_error_http_404(self):
        """Test handling HTTP 404 error."""
        from googleapiclient.errors import HttpError
        
        mock_resp = Mock()
        mock_resp.status = 404
        http_error = HttpError(mock_resp, b'{"error": {"message": "Not found"}}')
        
        result = handle_google_drive_error(http_error, "test operation")
        
        assert isinstance(result, GoogleDriveFileNotFoundError)
        assert "File or folder not found during test operation" in result.message
    
    def test_handle_google_drive_error_http_429(self):
        """Test handling HTTP 429 rate limit error."""
        from googleapiclient.errors import HttpError
        
        mock_resp = Mock()
        mock_resp.status = 429
        http_error = HttpError(mock_resp, b'{"error": {"message": "Rate limit exceeded"}}')
        
        result = handle_google_drive_error(http_error, "test operation")
        
        assert isinstance(result, GoogleDriveQuotaExceededError)
        assert "Rate limit exceeded during test operation" in result.message
    
    def test_handle_google_drive_error_connection_error(self):
        """Test handling connection error."""
        connection_error = ConnectionError("Network unreachable")
        
        result = handle_google_drive_error(connection_error, "test operation")
        
        assert isinstance(result, GoogleDriveStorageError)
        assert "Network error during test operation" in result.message
    
    def test_handle_google_drive_error_generic_exception(self):
        """Test handling generic exception."""
        generic_error = ValueError("Some unexpected error")
        
        result = handle_google_drive_error(generic_error, "test operation")
        
        assert isinstance(result, GoogleDriveStorageError)
        assert "Unexpected error during test operation" in result.message
    
    def test_google_drive_error_to_http_exception(self):
        """Test conversion of GoogleDriveError to HTTPException."""
        from fastapi import HTTPException
        
        drive_error = GoogleDriveAuthenticationError("Authentication failed")
        
        http_exception = google_drive_error_to_http_exception(drive_error)
        
        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == 401
        assert http_exception.detail['error'] == 'google_drive_error'
        assert http_exception.detail['message'] == 'Authentication failed'
        assert http_exception.detail['operation_failed'] is True
        assert http_exception.detail['retry_recommended'] is False
    
    def test_google_drive_error_to_http_exception_retry_recommended(self):
        """Test HTTP exception with retry recommendation."""
        from fastapi import HTTPException
        
        drive_error = GoogleDriveQuotaExceededError("Rate limit exceeded")
        
        http_exception = google_drive_error_to_http_exception(drive_error)
        
        assert http_exception.status_code == 429
        assert http_exception.detail['retry_recommended'] is True
    
    def test_handle_google_drive_exceptions_decorator_success(self):
        """Test the decorator with successful operation."""
        from app.exceptions.google_drive_exceptions import handle_google_drive_exceptions
        
        @handle_google_drive_exceptions("test operation")
        async def successful_operation():
            return "success"
        
        # Should not raise any exception
        result = asyncio.run(successful_operation())
        assert result == "success"
    
    def test_handle_google_drive_exceptions_decorator_google_drive_error(self):
        """Test the decorator with GoogleDriveError."""
        from app.exceptions.google_drive_exceptions import handle_google_drive_exceptions
        
        @handle_google_drive_exceptions("test operation")
        async def failing_operation():
            raise GoogleDriveAuthenticationError("Auth failed")
        
        # Should re-raise GoogleDriveError as-is
        with pytest.raises(GoogleDriveAuthenticationError, match="Auth failed"):
            asyncio.run(failing_operation())
    
    def test_handle_google_drive_exceptions_decorator_generic_error(self):
        """Test the decorator with generic exception."""
        from app.exceptions.google_drive_exceptions import handle_google_drive_exceptions
        
        @handle_google_drive_exceptions("test operation")
        async def failing_operation():
            raise ValueError("Some error")
        
        # Should convert to GoogleDriveError
        with pytest.raises(GoogleDriveStorageError):
            asyncio.run(failing_operation())


@pytest.mark.unit
class TestFileValidationConfiguration:
    """Test file validation configuration and setup."""
    
    def test_supported_file_extensions(self):
        """Test that supported file extensions are configured."""
        allowed_extensions = settings.allowed_file_extensions
        
        # Should include the extensions we support
        expected_extensions = ['pdf', 'doc', 'docx', 'jpeg', 'jpg', 'png', 'tiff', 'tif']
        for ext in expected_extensions:
            assert ext in allowed_extensions
    
    def test_file_size_limits_are_reasonable(self):
        """Test that file size limits are reasonable."""
        # Document size limit (100MB)
        assert settings.max_document_size == 100 * 1024 * 1024
        
        # Image size limit (50MB) 
        assert settings.max_image_size == 50 * 1024 * 1024
        
        # Document limit should be larger than image limit
        assert settings.max_document_size > settings.max_image_size
    
    def test_upload_directory_configuration(self):
        """Test upload directory configuration."""
        assert hasattr(settings, 'upload_dir')
        assert hasattr(settings, 'temp_dir')
        
        # Should be reasonable paths
        assert settings.upload_dir == "./uploads"
        assert settings.temp_dir == "./uploads/temp"


@pytest.mark.integration  
class TestConfigurationIntegration:
    """Integration tests for configuration loading."""
    
    def test_settings_can_be_loaded_from_env_file(self):
        """Test that settings can be loaded from .env file."""
        # This tests the actual .env file loading mechanism
        test_settings = Settings()
        
        # Should have loaded the basic configuration
        assert hasattr(test_settings, 'google_drive_enabled')
        assert hasattr(test_settings, 'secret_key')
        assert hasattr(test_settings, 'environment')
    
    def test_directory_creation_function(self):
        """Test that ensure_directories creates required directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a temporary settings instance
            temp_settings = Settings(
                upload_dir=f"{temp_dir}/uploads",
                temp_dir=f"{temp_dir}/uploads/temp", 
                log_file=f"{temp_dir}/logs/app.log",
                secret_key="test-secret-key-for-testing-min-32-chars"
            )
            
            # Call ensure_directories
            temp_settings.ensure_directories()
            
            # Verify directories were created
            assert os.path.exists(f"{temp_dir}/uploads")
            assert os.path.exists(f"{temp_dir}/uploads/temp")
            assert os.path.exists(f"{temp_dir}/logs")
    
    def test_secret_key_validation_failure(self):
        """Test secret key validation with invalid key."""
        with pytest.raises(ValueError, match="SECRET_KEY must be set"):
            Settings(secret_key="your-secret-key-here-change-in-production")
        
        with pytest.raises(ValueError, match="SECRET_KEY must be at least 32 characters"):
            Settings(secret_key="short")
    
    def test_file_types_validation_failure(self):
        """Test file types validation with empty value."""
        with pytest.raises(ValueError, match="ALLOWED_FILE_TYPES cannot be empty"):
            Settings(
                allowed_file_types="",
                secret_key="valid-secret-key-for-testing-min-32-chars"
            )