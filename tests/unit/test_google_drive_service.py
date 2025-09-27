"""
Unit tests for Google Drive service functionality.
"""

import pytest
import os
import json
from unittest.mock import Mock, AsyncMock, patch, mock_open
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

from app.services.google_drive_service import GoogleDriveService
from app.config import settings
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveAuthenticationError,
    GoogleDriveStorageError,
    GoogleDriveFileNotFoundError,
    GoogleDrivePermissionError,
    GoogleDriveQuotaExceededError
)


class TestGoogleDriveServiceInitialization:
    """Test Google Drive service initialization scenarios."""

    def test_service_initialization_disabled(self, test_settings_disabled):
        """Test that service raises error when Google Drive is disabled."""
        with patch('app.services.google_drive_service.settings', test_settings_disabled):
            with pytest.raises(GoogleDriveStorageError, match="Google Drive is disabled"):
                GoogleDriveService()

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.Credentials')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_service_initialization_with_valid_token(self, mock_exists, mock_creds_class, mock_build, test_settings, mock_credentials):
        """Test service initialization with valid existing token."""
        # Setup mocks
        mock_exists.return_value = True
        mock_creds_class.from_authorized_user_file.return_value = mock_credentials
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        with patch('app.services.google_drive_service.settings', test_settings):
            service = GoogleDriveService()
            
            # Verify service was built correctly
            mock_build.assert_called_once_with('drive', 'v3', credentials=mock_credentials)
            assert service.service == mock_service
            mock_creds_class.from_authorized_user_file.assert_called_once_with(
                test_settings.google_drive_token_path, 
                [scope.strip() for scope in test_settings.google_drive_scopes.split(',')]
            )

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.Credentials')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_service_initialization_with_expired_token_refresh_success(self, mock_exists, mock_creds_class, mock_build, test_settings):
        """Test service initialization with expired token that refreshes successfully."""
        # Setup expired credentials that refresh successfully
        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds.refresh = Mock()  # Successful refresh
        
        mock_exists.return_value = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        with patch('app.services.google_drive_service.settings', test_settings):
            service = GoogleDriveService()
            
            # Verify refresh was called and service was built
            mock_creds.refresh.assert_called_once()
            mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds)
            assert service.service == mock_service

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.Credentials')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_service_initialization_with_expired_token_refresh_failure(self, mock_exists, mock_creds_class, mock_build, test_settings):
        """Test service initialization with expired token that fails to refresh."""
        # Setup expired credentials that fail to refresh
        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds.refresh = Mock(side_effect=Exception("Refresh failed"))
        
        mock_exists.return_value = True
        mock_creds_class.from_authorized_user_file.return_value = mock_creds
        
        with patch('app.services.google_drive_service.settings', test_settings):
            with pytest.raises(GoogleDriveAuthenticationError, match="Failed to refresh Google Drive credentials"):
                GoogleDriveService()

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.InstalledAppFlow')
    @patch('app.services.google_drive_service.os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_service_initialization_no_token_new_auth_flow(self, mock_file, mock_exists, mock_flow_class, mock_build, test_settings):
        """Test service initialization with no token, triggering new auth flow."""
        # Setup mocks for new auth flow
        mock_exists.side_effect = lambda path: path == test_settings.google_drive_credentials_path
        
        mock_flow = Mock()
        mock_flow_class.from_client_secrets_file.return_value = mock_flow
        
        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = True
        mock_creds.to_json.return_value = '{"token": "new_token"}'
        mock_flow.run_local_server.return_value = mock_creds
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        with patch('app.services.google_drive_service.settings', test_settings):
            service = GoogleDriveService()
            
            # Verify new auth flow was triggered
            mock_flow_class.from_client_secrets_file.assert_called_once_with(
                test_settings.google_drive_credentials_path, 
                [scope.strip() for scope in test_settings.google_drive_scopes.split(',')]
            )
            mock_flow.run_local_server.assert_called_once_with(port=0)
            mock_build.assert_called_once_with('drive', 'v3', credentials=mock_creds)
            
            # Verify token was saved
            mock_file.assert_called_with(test_settings.google_drive_token_path, 'w')
            mock_file().write.assert_called_once_with('{"token": "new_token"}')

    @patch('app.services.google_drive_service.os.path.exists')
    def test_service_initialization_missing_credentials_file(self, mock_exists, test_settings):
        """Test service initialization fails when credentials file is missing."""
        mock_exists.return_value = False  # Credentials file doesn't exist
        
        with patch('app.services.google_drive_service.settings', test_settings):
            with pytest.raises(GoogleDriveAuthenticationError, match="credentials file not found"):
                GoogleDriveService()

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.InstalledAppFlow')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_service_initialization_auth_flow_failure(self, mock_exists, mock_flow_class, mock_build, test_settings):
        """Test service initialization fails when auth flow fails."""
        mock_exists.side_effect = lambda path: path == test_settings.google_drive_credentials_path
        
        mock_flow = Mock()
        mock_flow_class.from_client_secrets_file.return_value = mock_flow
        mock_flow.run_local_server.side_effect = Exception("Auth flow failed")
        
        with patch('app.services.google_drive_service.settings', test_settings):
            with pytest.raises(GoogleDriveAuthenticationError, match="Failed to obtain Google Drive credentials"):
                GoogleDriveService()

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.Credentials')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_service_initialization_build_service_failure(self, mock_exists, mock_creds_class, mock_build, test_settings, mock_credentials):
        """Test service initialization fails when building Google Drive service fails."""
        mock_exists.return_value = True
        mock_creds_class.from_authorized_user_file.return_value = mock_credentials
        mock_build.side_effect = Exception("Build service failed")
        
        with patch('app.services.google_drive_service.settings', test_settings):
            with pytest.raises(GoogleDriveStorageError, match="Failed to initialize Google Drive service"):
                GoogleDriveService()


class TestGoogleDriveServiceAuthentication:
    """Test Google Drive service authentication scenarios."""

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.Credentials')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_service_with_valid_credentials(self, mock_exists, mock_creds_class, mock_build, test_settings, mock_credentials):
        """Test service works correctly with valid credentials."""
        mock_exists.return_value = True
        mock_creds_class.from_authorized_user_file.return_value = mock_credentials
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        with patch('app.services.google_drive_service.settings', test_settings):
            service = GoogleDriveService()
            
            assert service.service == mock_service
            assert service.credentials_path == test_settings.google_drive_credentials_path
            assert service.token_path == test_settings.google_drive_token_path
            assert service.root_folder == test_settings.google_drive_root_folder

    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.InstalledAppFlow')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_token_save_failure_warning(self, mock_exists, mock_flow_class, mock_build, mock_file, test_settings):
        """Test that token save failure logs warning but doesn't fail initialization."""
        mock_exists.side_effect = lambda path: path == test_settings.google_drive_credentials_path
        
        mock_flow = Mock()
        mock_flow_class.from_client_secrets_file.return_value = mock_flow
        
        mock_creds = Mock(spec=Credentials)
        mock_creds.valid = True
        mock_creds.to_json.return_value = '{"token": "new_token"}'
        mock_flow.run_local_server.return_value = mock_creds
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        with patch('app.services.google_drive_service.settings', test_settings):
            # Should not raise exception, just log warning
            service = GoogleDriveService()
            assert service.service == mock_service


class TestGoogleDriveServiceProperties:
    """Test Google Drive service property access."""

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.Credentials')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_service_properties_from_settings(self, mock_exists, mock_creds_class, mock_build, test_settings, mock_credentials):
        """Test that service properties are correctly set from settings."""
        mock_exists.return_value = True
        mock_creds_class.from_authorized_user_file.return_value = mock_credentials
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        with patch('app.services.google_drive_service.settings', test_settings):
            service = GoogleDriveService()
            
            assert service.credentials_path == test_settings.google_drive_credentials_path
            assert service.token_path == test_settings.google_drive_token_path
            assert service.root_folder == test_settings.google_drive_root_folder
            assert service.scopes == [scope.strip() for scope in test_settings.google_drive_scopes.split(',')]
            assert service.application_name == test_settings.google_drive_application_name

    @patch('app.services.google_drive_service.build')
    @patch('app.services.google_drive_service.Credentials')
    @patch('app.services.google_drive_service.os.path.exists')
    def test_scopes_parsing(self, mock_exists, mock_creds_class, mock_build, mock_credentials):
        """Test that scopes are correctly parsed from comma-separated string."""
        mock_exists.return_value = True
        mock_creds_class.from_authorized_user_file.return_value = mock_credentials
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        test_settings_with_scopes = Mock()
        test_settings_with_scopes.google_drive_enabled = True
        test_settings_with_scopes.google_drive_credentials_path = "./test_creds.json"
        test_settings_with_scopes.google_drive_token_path = "./test_token.json"
        test_settings_with_scopes.google_drive_root_folder = "TestRoot"
        test_settings_with_scopes.google_drive_scopes = "scope1, scope2 ,scope3,  scope4  "
        test_settings_with_scopes.google_drive_application_name = "TestApp"
        
        with patch('app.services.google_drive_service.settings', test_settings_with_scopes):
            service = GoogleDriveService()
            
            expected_scopes = ['scope1', 'scope2', 'scope3', 'scope4']
            assert service.scopes == expected_scopes


class TestGoogleDriveServiceExceptionHandling:
    """Test exception handling in Google Drive service initialization."""

    def test_google_drive_error_passthrough(self, test_settings):
        """Test that GoogleDriveError exceptions are passed through unchanged."""
        original_error = GoogleDriveAuthenticationError("Original auth error")
        
        with patch('app.services.google_drive_service.settings', test_settings):
            with patch.object(GoogleDriveService, '_initialize_service', side_effect=original_error):
                with pytest.raises(GoogleDriveAuthenticationError, match="Original auth error"):
                    GoogleDriveService()

    def test_generic_exception_conversion(self, test_settings):
        """Test that generic exceptions are converted to GoogleDriveStorageError."""
        generic_error = RuntimeError("Generic runtime error")
        
        with patch('app.services.google_drive_service.settings', test_settings):
            with patch.object(GoogleDriveService, '_initialize_service', side_effect=generic_error):
                with pytest.raises(GoogleDriveStorageError, match="Failed to initialize Google Drive service"):
                    GoogleDriveService()


# Run tests with different scenarios
@pytest.mark.parametrize("token_exists,creds_exist,expected_exception", [
    (False, False, GoogleDriveAuthenticationError),  # No token, no creds
    (True, False, None),  # Token exists, no creds needed
    (False, True, None),  # No token, creds exist for new auth
])
def test_initialization_scenarios(token_exists, creds_exist, expected_exception, test_settings):
    """Test various initialization scenarios with parametrization."""
    
    with patch('app.services.google_drive_service.os.path.exists') as mock_exists, \
         patch('app.services.google_drive_service.build') as mock_build, \
         patch('app.services.google_drive_service.Credentials') as mock_creds_class, \
         patch('app.services.google_drive_service.InstalledAppFlow') as mock_flow_class, \
         patch('builtins.open', mock_open()) as mock_file:
        
        # Configure file existence
        def exists_side_effect(path):
            if path == test_settings.google_drive_token_path:
                return token_exists
            elif path == test_settings.google_drive_credentials_path:
                return creds_exist
            return False
        
        mock_exists.side_effect = exists_side_effect
        
        if token_exists:
            # Mock valid existing token
            mock_creds = Mock(spec=Credentials)
            mock_creds.valid = True
            mock_creds_class.from_authorized_user_file.return_value = mock_creds
            mock_build.return_value = Mock()
        
        elif creds_exist:
            # Mock new auth flow
            mock_flow = Mock()
            mock_flow_class.from_client_secrets_file.return_value = mock_flow
            mock_new_creds = Mock(spec=Credentials)
            mock_new_creds.valid = True
            mock_new_creds.to_json.return_value = '{"token": "new"}'
            mock_flow.run_local_server.return_value = mock_new_creds
            mock_build.return_value = Mock()
        
        with patch('app.services.google_drive_service.settings', test_settings):
            if expected_exception:
                with pytest.raises(expected_exception):
                    GoogleDriveService()
            else:
                service = GoogleDriveService()
                assert service.service is not None