"""
Unit tests for Google Drive error handling scenarios.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from googleapiclient.errors import HttpError

from app.services.google_drive_service import GoogleDriveService
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveAuthenticationError,
    GoogleDriveStorageError,
    GoogleDriveFileNotFoundError,
    GoogleDrivePermissionError,
    GoogleDriveQuotaExceededError,
    handle_google_drive_error,
    google_drive_error_to_http_exception
)


class TestGoogleDriveErrorHandling:
    """Test error handling in Google Drive operations."""

    def test_handle_google_drive_error_auth_error(self, google_api_error_responses):
        """Test handling of 401 authentication errors."""
        error = google_api_error_responses['auth_error']
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveAuthenticationError)
        assert "Authentication failed during test operation" in result.message
        assert result.status_code == 401
        assert result.original_error == error

    def test_handle_google_drive_error_permission_error(self, google_api_error_responses):
        """Test handling of 403 permission errors."""
        error = google_api_error_responses['permission_error']
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDrivePermissionError)
        assert "Permission denied during test operation" in result.message
        assert result.status_code == 403
        assert result.original_error == error

    def test_handle_google_drive_error_not_found_error(self, google_api_error_responses):
        """Test handling of 404 not found errors."""
        error = google_api_error_responses['not_found_error']
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveFileNotFoundError)
        assert "File or folder not found during test operation" in result.message
        assert result.status_code == 404
        assert result.original_error == error

    def test_handle_google_drive_error_quota_error(self, google_api_error_responses):
        """Test handling of 429 quota exceeded errors."""
        error = google_api_error_responses['quota_error']
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveQuotaExceededError)
        assert "Rate limit exceeded during test operation" in result.message
        assert result.status_code == 429
        assert result.original_error == error

    def test_handle_google_drive_error_server_error(self, google_api_error_responses):
        """Test handling of 500 server errors."""
        error = google_api_error_responses['server_error']
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveStorageError)
        assert "Google Drive API error during test operation: 500" in result.message
        assert result.status_code == 500
        assert result.original_error == error

    def test_handle_google_drive_error_quota_in_403_details(self):
        """Test handling of quota error disguised as 403 with specific reason."""
        # Create mock HttpError with quota exceeded reason in details
        resp = Mock()
        resp.status = 403
        resp.reason = "Forbidden"
        
        error = HttpError(resp, content=b'{"error": {"message": "Quota exceeded"}}')
        error.error_details = [{"reason": "quotaExceeded"}]
        
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveQuotaExceededError)
        assert "Google Drive quota exceeded during test operation" in result.message

    def test_handle_google_drive_error_rate_limit_in_403_details(self):
        """Test handling of rate limit error in 403 with specific reason."""
        resp = Mock()
        resp.status = 403
        resp.reason = "Forbidden"
        
        error = HttpError(resp, content=b'{"error": {"message": "Rate limit exceeded"}}')
        error.error_details = [{"reason": "rateLimitExceeded"}]
        
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveQuotaExceededError)
        assert "Google Drive quota exceeded during test operation" in result.message

    def test_handle_google_drive_error_network_error(self):
        """Test handling of network connection errors."""
        error = ConnectionError("Connection failed")
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveStorageError)
        assert "Network error during test operation" in result.message
        assert result.status_code == 500
        assert result.original_error == error

    def test_handle_google_drive_error_timeout_error(self):
        """Test handling of timeout errors."""
        error = TimeoutError("Operation timed out")
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveStorageError)
        assert "Network error during test operation" in result.message
        assert result.status_code == 500
        assert result.original_error == error

    def test_handle_google_drive_error_generic_error(self):
        """Test handling of generic errors."""
        error = RuntimeError("Something went wrong")
        result = handle_google_drive_error(error, "test operation")
        
        assert isinstance(result, GoogleDriveStorageError)
        assert "Unexpected error during test operation: Something went wrong" in result.message
        assert result.status_code == 500
        assert result.original_error == error


class TestGoogleDriveErrorToHttpException:
    """Test conversion of GoogleDriveError to HTTPException."""

    def test_auth_error_conversion(self):
        """Test conversion of authentication error to HTTPException."""
        error = GoogleDriveAuthenticationError("Auth failed")
        http_error = google_drive_error_to_http_exception(error)
        
        assert http_error.status_code == 401
        assert http_error.detail['error'] == 'google_drive_error'
        assert http_error.detail['message'] == 'Auth failed'
        assert http_error.detail['operation_failed'] is True
        assert http_error.detail['retry_recommended'] is False

    def test_quota_error_conversion(self):
        """Test conversion of quota error to HTTPException."""
        error = GoogleDriveQuotaExceededError("Quota exceeded")
        http_error = google_drive_error_to_http_exception(error)
        
        assert http_error.status_code == 429
        assert http_error.detail['error'] == 'google_drive_error'
        assert http_error.detail['message'] == 'Quota exceeded'
        assert http_error.detail['operation_failed'] is True
        assert http_error.detail['retry_recommended'] is True  # 429 is retryable

    def test_server_error_conversion(self):
        """Test conversion of server error to HTTPException."""
        error = GoogleDriveStorageError("Server error")
        http_error = google_drive_error_to_http_exception(error)
        
        assert http_error.status_code == 500
        assert http_error.detail['error'] == 'google_drive_error'
        assert http_error.detail['message'] == 'Server error'
        assert http_error.detail['operation_failed'] is True
        assert http_error.detail['retry_recommended'] is True  # 500 is retryable


class TestServiceMethodErrorDecorators:
    """Test error handling decorators on service methods."""

    @pytest.mark.asyncio
    async def test_folder_creation_error_handling(self, mock_google_drive_service, google_api_error_responses):
        """Test error handling in folder creation operations."""
        # Setup mock to raise permission error
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.side_effect = google_api_error_responses['permission_error']
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            # The decorator should convert the HttpError to GoogleDrivePermissionError
            with pytest.raises(GoogleDrivePermissionError):
                await service.create_customer_folder_structure("danishevsky@gmail.com")

    @pytest.mark.asyncio
    async def test_file_upload_error_handling(self, mock_google_drive_service, google_api_error_responses):
        """Test error handling in file upload operations."""
        # Setup mock to raise quota exceeded error
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_create = Mock()
        mock_files.create.return_value = mock_create
        mock_create.execute.side_effect = google_api_error_responses['quota_error']
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            with pytest.raises(GoogleDriveQuotaExceededError):
                await service.upload_file_to_folder(
                    file_content=b"test content",
                    filename="test.md",
                    folder_id="test_folder",
                    target_language="es"
                )

    @pytest.mark.asyncio
    async def test_metadata_update_error_handling(self, mock_google_drive_service, google_api_error_responses):
        """Test error handling in metadata update operations."""
        # Setup mock to raise not found error
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_update = Mock()
        mock_files.update.return_value = mock_update
        mock_update.execute.side_effect = google_api_error_responses['not_found_error']
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            with pytest.raises(GoogleDriveFileNotFoundError):
                await service.update_file_metadata("nonexistent_file_id", {"properties": {"test": "value"}})

    @pytest.mark.asyncio
    async def test_file_listing_error_handling(self, mock_google_drive_service, google_api_error_responses):
        """Test error handling in file listing operations."""
        # Setup mock to raise auth error
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.side_effect = google_api_error_responses['auth_error']
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            with pytest.raises(GoogleDriveAuthenticationError):
                await service.list_files_in_folder("test_folder")

    @pytest.mark.asyncio
    async def test_file_deletion_error_handling(self, mock_google_drive_service, google_api_error_responses):
        """Test error handling in file deletion operations."""
        # Setup mock to raise server error
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_delete = Mock()
        mock_files.delete.return_value = mock_delete
        mock_delete.execute.side_effect = google_api_error_responses['server_error']
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            with pytest.raises(GoogleDriveStorageError):
                await service.delete_file("test_file_id")


class TestErrorPropagation:
    """Test error propagation through the service layers."""

    @pytest.mark.asyncio
    async def test_nested_operation_error_propagation(self, mock_google_drive_service, google_api_error_responses):
        """Test that errors in nested operations are properly propagated."""
        # Setup mock to fail on the first _find_folder call (looking for root folder)
        mock_files = Mock()
        mock_google_drive_service.files.return_value = mock_files
        mock_list = Mock()
        mock_files.list.return_value = mock_list
        mock_list.execute.side_effect = google_api_error_responses['auth_error']
        
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            # Error in _find_folder should propagate through create_customer_folder_structure
            with pytest.raises(GoogleDriveAuthenticationError):
                await service.create_customer_folder_structure("danishevsky@gmail.com")

    @pytest.mark.asyncio
    async def test_custom_error_passthrough(self, mock_google_drive_service):
        """Test that custom GoogleDrive errors are passed through unchanged."""
        with patch('app.services.google_drive_service.build') as mock_build, \
             patch('app.services.google_drive_service.Credentials') as mock_creds, \
             patch('app.services.google_drive_service.os.path.exists', return_value=True):
            
            mock_creds_instance = Mock()
            mock_creds_instance.valid = True
            mock_creds.from_authorized_user_file.return_value = mock_creds_instance
            mock_build.return_value = mock_google_drive_service
            
            service = GoogleDriveService()
            
            # Create a method that directly raises a custom error
            original_error = GoogleDriveQuotaExceededError("Custom quota error")
            
            with patch.object(service, '_find_folder', side_effect=original_error):
                with pytest.raises(GoogleDriveQuotaExceededError) as exc_info:
                    await service._find_or_create_folder("TestFolder", "parent_id")
                
                # Should be the exact same error object
                assert exc_info.value is original_error


# Parametrized tests for different error scenarios
@pytest.mark.parametrize("status_code,expected_exception", [
    (401, GoogleDriveAuthenticationError),
    (403, GoogleDrivePermissionError),
    (404, GoogleDriveFileNotFoundError),
    (429, GoogleDriveQuotaExceededError),
    (500, GoogleDriveStorageError),
    (502, GoogleDriveStorageError),
    (503, GoogleDriveStorageError),
])
def test_http_error_status_code_mapping(status_code, expected_exception):
    """Test that different HTTP status codes map to correct exception types."""
    resp = Mock()
    resp.status = status_code
    resp.reason = f"HTTP {status_code} Error"
    
    error = HttpError(resp, content=b'{"error": {"message": "Test error"}}')
    result = handle_google_drive_error(error, "test operation")
    
    assert isinstance(result, expected_exception)
    assert result.status_code == status_code


@pytest.mark.parametrize("exception_type,retry_recommended", [
    (GoogleDriveAuthenticationError("test"), False),
    (GoogleDrivePermissionError("test"), False),
    (GoogleDriveFileNotFoundError("test"), False),
    (GoogleDriveQuotaExceededError("test"), True),
    (GoogleDriveStorageError("test", status_code=500), True),
    (GoogleDriveStorageError("test", status_code=502), True),
    (GoogleDriveStorageError("test", status_code=503), True),
    (GoogleDriveStorageError("test", status_code=400), False),
])
def test_retry_recommendation_logic(exception_type, retry_recommended):
    """Test that retry recommendations are correctly set based on error type."""
    http_error = google_drive_error_to_http_exception(exception_type)
    assert http_error.detail['retry_recommended'] == retry_recommended


class TestErrorLogMessages:
    """Test that error scenarios produce appropriate log messages."""

    @patch('app.exceptions.google_drive_exceptions.logging')
    def test_http_error_logging(self, mock_logging, google_api_error_responses):
        """Test that HttpErrors are properly logged."""
        error = google_api_error_responses['server_error']
        handle_google_drive_error(error, "test operation")
        
        mock_logging.error.assert_called_once()
        log_call_args = mock_logging.error.call_args[0][0]
        assert "Google Drive API error during test operation" in log_call_args
        assert "500" in log_call_args

    @patch('app.exceptions.google_drive_exceptions.logging')
    def test_network_error_logging(self, mock_logging):
        """Test that network errors are properly logged."""
        error = ConnectionError("Connection failed")
        handle_google_drive_error(error, "test operation")
        
        mock_logging.error.assert_called_once()
        log_call_args = mock_logging.error.call_args[0][0]
        assert "Network error during test operation" in log_call_args

    @patch('app.exceptions.google_drive_exceptions.logging')
    def test_generic_error_logging(self, mock_logging):
        """Test that generic errors are properly logged."""
        error = RuntimeError("Something unexpected")
        handle_google_drive_error(error, "test operation")
        
        mock_logging.error.assert_called_once()
        log_call_args = mock_logging.error.call_args[0][0]
        assert "Unexpected error during test operation" in log_call_args