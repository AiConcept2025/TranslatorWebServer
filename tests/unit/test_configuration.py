"""
Unit tests for configuration and environment variable handling.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, Mock
from pydantic import ValidationError

from app.config import Settings, get_settings


class TestSettingsValidation:
    """Test settings validation and environment variable handling."""

    def test_settings_with_minimal_required_env_vars(self):
        """Test settings creation with minimal required environment variables."""
        env_vars = {
            'SECRET_KEY': 'test-secret-key-that-is-at-least-32-characters-long',
            'GOOGLE_DRIVE_ENABLED': 'true',
            'GOOGLE_DRIVE_CREDENTIALS_PATH': './test_credentials.json',
            'GOOGLE_DRIVE_TOKEN_PATH': './test_token.json'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.secret_key == env_vars['SECRET_KEY']
            assert settings.google_drive_enabled is True
            assert settings.google_drive_credentials_path == './test_credentials.json'
            assert settings.google_drive_token_path == './test_token.json'

    def test_settings_secret_key_validation_too_short(self):
        """Test that secret key validation fails for short keys."""
        env_vars = {
            'SECRET_KEY': 'short_key',  # Less than 32 characters
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValidationError, match="at least 32 characters"):
                Settings()

    def test_settings_secret_key_validation_default_value(self):
        """Test that secret key validation fails for default value."""
        env_vars = {
            'SECRET_KEY': 'your-secret-key-here-change-in-production',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValidationError, match="must be set and not be the default value"):
                Settings()

    def test_settings_secret_key_validation_empty(self):
        """Test that secret key validation fails for empty key."""
        env_vars = {
            'SECRET_KEY': '',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValidationError, match="must be set and not be the default value"):
                Settings()

    def test_settings_allowed_file_types_validation_empty(self):
        """Test that allowed file types validation fails for empty value."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'ALLOWED_FILE_TYPES': '',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(ValidationError, match="cannot be empty"):
                Settings()

    def test_settings_cors_origins_validation(self):
        """Test CORS origins parsing and validation."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'CORS_ORIGINS': 'http://localhost:3000, https://example.com ,  http://test.local  ',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            expected_origins = ['http://localhost:3000', 'https://example.com', 'http://test.local']
            assert settings.cors_origins == expected_origins

    def test_settings_cors_methods_validation(self):
        """Test CORS methods parsing and validation."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'CORS_METHODS': 'GET, POST , PUT,DELETE,  OPTIONS  ',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            expected_methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
            assert settings.cors_methods == expected_methods

    def test_settings_google_drive_configuration(self):
        """Test Google Drive specific configuration."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'GOOGLE_DRIVE_ENABLED': 'true',
            'GOOGLE_DRIVE_CREDENTIALS_PATH': '/path/to/credentials.json',
            'GOOGLE_DRIVE_TOKEN_PATH': '/path/to/token.json',
            'GOOGLE_DRIVE_ROOT_FOLDER': 'CustomRootFolder',
            'GOOGLE_DRIVE_SCOPES': 'scope1,scope2, scope3,  scope4  ',
            'GOOGLE_DRIVE_APPLICATION_NAME': 'CustomAppName',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.google_drive_enabled is True
            assert settings.google_drive_credentials_path == '/path/to/credentials.json'
            assert settings.google_drive_token_path == '/path/to/token.json'
            assert settings.google_drive_root_folder == 'CustomRootFolder'
            assert settings.google_drive_scopes == 'scope1,scope2, scope3,  scope4  '
            assert settings.google_drive_application_name == 'CustomAppName'

    def test_settings_google_drive_disabled(self):
        """Test Google Drive disabled configuration."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'GOOGLE_DRIVE_ENABLED': 'false',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.google_drive_enabled is False

    def test_settings_file_size_limits(self):
        """Test file size limit configurations."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'MAX_DOCUMENT_SIZE': '200000000',  # 200MB
            'MAX_IMAGE_SIZE': '100000000',     # 100MB
            'MAX_FILE_SIZE': '50000000',       # 50MB
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.max_document_size == 200000000
            assert settings.max_image_size == 100000000
            assert settings.max_file_size == 50000000

    def test_settings_database_configuration(self):
        """Test database configuration options."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'DATABASE_URL': 'postgresql://user:pass@localhost:5432/testdb',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.database_url == 'postgresql://user:pass@localhost:5432/testdb'

    def test_settings_redis_configuration(self):
        """Test Redis configuration options."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'REDIS_URL': 'redis://localhost:6379/1',
            'CELERY_BROKER_URL': 'redis://localhost:6379/2',
            'CELERY_RESULT_BACKEND': 'redis://localhost:6379/3',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.redis_url == 'redis://localhost:6379/1'
            assert settings.celery_broker_url == 'redis://localhost:6379/2'
            assert settings.celery_result_backend == 'redis://localhost:6379/3'

    def test_settings_translation_services_configuration(self):
        """Test translation services API keys configuration."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'GOOGLE_TRANSLATE_API_KEY': 'google_api_key_123',
            'DEEPL_API_KEY': 'deepl_api_key_456',
            'AZURE_TRANSLATOR_KEY': 'azure_key_789',
            'AZURE_TRANSLATOR_ENDPOINT': 'https://api.cognitive.microsoft.com',
            'AZURE_TRANSLATOR_REGION': 'eastus',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.google_translate_api_key == 'google_api_key_123'
            assert settings.deepl_api_key == 'deepl_api_key_456'
            assert settings.azure_translator_key == 'azure_key_789'
            assert settings.azure_translator_endpoint == 'https://api.cognitive.microsoft.com'
            assert settings.azure_translator_region == 'eastus'

    def test_settings_payment_configuration(self):
        """Test payment (Stripe) configuration."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'STRIPE_PUBLIC_KEY': 'pk_test_123',
            'STRIPE_SECRET_KEY': 'sk_test_456',
            'STRIPE_WEBHOOK_SECRET': 'whsec_789',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.stripe_public_key == 'pk_test_123'
            assert settings.stripe_secret_key == 'sk_test_456'
            assert settings.stripe_webhook_secret == 'whsec_789'

    def test_settings_logging_configuration(self):
        """Test logging configuration."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'LOG_LEVEL': 'DEBUG',
            'LOG_FILE': '/custom/path/app.log',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.log_level == 'DEBUG'
            assert settings.log_file == '/custom/path/app.log'

    def test_settings_rate_limiting_configuration(self):
        """Test rate limiting configuration."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'RATE_LIMIT_REQUESTS': '500',
            'RATE_LIMIT_WINDOW': '7200',  # 2 hours
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            assert settings.rate_limit_requests == 500
            assert settings.rate_limit_window == 7200


class TestSettingsProperties:
    """Test computed properties in settings."""

    def test_allowed_file_extensions_property(self):
        """Test allowed file extensions property."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'ALLOWED_FILE_TYPES': 'txt,pdf,doc, docx , md,  rtf  ',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            expected_extensions = ['txt', 'pdf', 'doc', 'docx', 'md', 'rtf']
            assert settings.allowed_file_extensions == expected_extensions

    def test_is_production_property(self):
        """Test is_production property."""
        # Test production environment
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'ENVIRONMENT': 'production',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            assert settings.is_production is True
            assert settings.is_development is False

    def test_is_development_property(self):
        """Test is_development property."""
        # Test development environment
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'ENVIRONMENT': 'development',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            assert settings.is_development is True
            assert settings.is_production is False

    def test_is_development_property_case_insensitive(self):
        """Test environment property is case insensitive."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'ENVIRONMENT': 'DEVELOPMENT',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            assert settings.is_development is True

    def test_log_config_property_development(self):
        """Test log config property in development."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'ENVIRONMENT': 'development',
            'LOG_LEVEL': 'DEBUG',
            'LOG_FILE': '/tmp/test.log',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            log_config = settings.log_config
            
            assert log_config['version'] == 1
            assert log_config['disable_existing_loggers'] is False
            assert 'formatters' in log_config
            assert 'handlers' in log_config
            assert 'root' in log_config
            assert log_config['root']['level'] == 'DEBUG'
            assert 'default' in log_config['handlers']
            assert 'file' in log_config['handlers']
            
            # In development, should use default formatter for file
            file_handler = log_config['handlers']['file']
            assert file_handler['formatter'] == 'default'

    def test_log_config_property_production(self):
        """Test log config property in production."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'ENVIRONMENT': 'production',
            'LOG_LEVEL': 'INFO',
            'LOG_FILE': '/var/log/app.log',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            log_config = settings.log_config
            
            assert log_config['root']['level'] == 'INFO'
            
            # In production, should use JSON formatter for file
            file_handler = log_config['handlers']['file']
            assert file_handler['formatter'] == 'json'


class TestSettingsDirectoryCreation:
    """Test directory creation functionality."""

    def test_ensure_directories_creates_directories(self):
        """Test that ensure_directories creates required directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_dir = os.path.join(temp_dir, 'uploads')
            temp_upload_dir = os.path.join(upload_dir, 'temp')
            log_dir = os.path.join(temp_dir, 'logs')
            log_file = os.path.join(log_dir, 'app.log')
            
            env_vars = {
                'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
                'UPLOAD_DIR': upload_dir,
                'TEMP_DIR': temp_upload_dir,
                'LOG_FILE': log_file,
            }
            
            with patch.dict(os.environ, env_vars, clear=True):
                settings = Settings()
                settings.ensure_directories()
                
                assert os.path.exists(upload_dir)
                assert os.path.exists(temp_upload_dir)
                assert os.path.exists(log_dir)

    def test_ensure_directories_handles_existing_directories(self):
        """Test that ensure_directories handles existing directories gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_dir = os.path.join(temp_dir, 'uploads')
            os.makedirs(upload_dir)  # Create directory first
            
            env_vars = {
                'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
                'UPLOAD_DIR': upload_dir,
                'TEMP_DIR': os.path.join(upload_dir, 'temp'),
                'LOG_FILE': os.path.join(temp_dir, 'logs', 'app.log'),
            }
            
            with patch.dict(os.environ, env_vars, clear=True):
                settings = Settings()
                # Should not raise exception for existing directory
                settings.ensure_directories()
                
                assert os.path.exists(upload_dir)

    def test_ensure_directories_handles_none_values(self):
        """Test that ensure_directories handles None values gracefully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            upload_dir = os.path.join(temp_dir, 'uploads')
            
            env_vars = {
                'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
                'UPLOAD_DIR': upload_dir,
                'TEMP_DIR': os.path.join(upload_dir, 'temp'),
                # LOG_FILE not set, so log_file will be default
            }
            
            with patch.dict(os.environ, env_vars, clear=True):
                settings = Settings()
                # Should handle None values without crashing
                settings.ensure_directories()


class TestGetSettings:
    """Test the get_settings function and caching."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = get_settings()
            assert isinstance(settings, Settings)

    def test_get_settings_caching(self):
        """Test that get_settings uses caching (returns same instance)."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings1 = get_settings()
            settings2 = get_settings()
            
            # Should return the same cached instance
            assert settings1 is settings2

    def test_get_settings_cache_invalidation(self):
        """Test get_settings cache behavior with different environment variables."""
        # This test demonstrates that the cache is based on the function call,
        # not on environment variables, so changing env vars won't affect
        # the cached result within the same test run
        env_vars1 = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
            'ENVIRONMENT': 'development',
        }
        
        with patch.dict(os.environ, env_vars1, clear=True):
            settings1 = get_settings()
            assert settings1.environment == 'development'


class TestSettingsDefaults:
    """Test default values in settings."""

    def test_default_values(self):
        """Test that settings have expected default values."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            # Application defaults
            assert settings.app_name == "TranslatorWebServer"
            assert settings.app_version == "1.0.0"
            assert settings.environment == "development"
            assert settings.debug is True
            assert settings.host == "0.0.0.0"
            assert settings.port == 8000
            
            # Security defaults
            assert settings.algorithm == "HS256"
            assert settings.access_token_expire_minutes == 30
            
            # Database defaults
            assert settings.database_url == "sqlite:///./translator.db"
            
            # File upload defaults
            assert settings.max_file_size == 10485760  # 10MB
            assert settings.max_document_size == 104857600  # 100MB
            assert settings.max_image_size == 52428800  # 50MB
            assert settings.upload_dir == "./uploads"
            assert settings.temp_dir == "./uploads/temp"
            
            # Google Drive defaults
            assert settings.google_drive_enabled is True
            assert settings.google_drive_credentials_path == "./credentials.json"
            assert settings.google_drive_token_path == "./token.json"
            assert settings.google_drive_root_folder == "TranslatorWebServer"
            assert settings.google_drive_application_name == "TranslatorWebServer"
            
            # Rate limiting defaults
            assert settings.rate_limit_requests == 100
            assert settings.rate_limit_window == 3600
            
            # Logging defaults
            assert settings.log_level == "INFO"
            assert settings.log_file == "./logs/translator.log"

    def test_optional_fields_can_be_none(self):
        """Test that optional configuration fields can be None."""
        env_vars = {
            'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            
            # Translation service API keys (optional)
            assert settings.google_translate_api_key is None
            assert settings.deepl_api_key is None
            assert settings.azure_translator_key is None
            assert settings.azure_translator_endpoint is None
            assert settings.azure_translator_region is None
            
            # Payment configuration (optional)
            assert settings.stripe_public_key is None
            assert settings.stripe_secret_key is None
            assert settings.stripe_webhook_secret is None
            
            # Email configuration (optional)
            assert settings.smtp_host is None
            assert settings.smtp_port is None
            assert settings.smtp_username is None
            assert settings.smtp_password is None
            assert settings.email_from is None


# Parametrized tests for environment variations
@pytest.mark.parametrize("env_value,expected_bool", [
    ("true", True),
    ("True", True),
    ("TRUE", True),
    ("1", True),
    ("yes", True),
    ("false", False),
    ("False", False),
    ("FALSE", False),
    ("0", False),
    ("no", False),
    ("", False),
])
def test_boolean_environment_variable_parsing(env_value, expected_bool):
    """Test that boolean environment variables are parsed correctly."""
    env_vars = {
        'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
        'GOOGLE_DRIVE_ENABLED': env_value,
        'DEBUG': env_value,
        'METRICS_ENABLED': env_value,
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        
        assert settings.google_drive_enabled == expected_bool
        assert settings.debug == expected_bool
        assert settings.metrics_enabled == expected_bool


@pytest.mark.parametrize("file_types,expected_extensions", [
    ("txt,pdf,doc", ["txt", "pdf", "doc"]),
    ("txt, pdf , doc,  docx  ", ["txt", "pdf", "doc", "docx"]),
    ("md", ["md"]),
    ("txt,PDF,DoC", ["txt", "PDF", "DoC"]),  # Case preserved
])
def test_file_types_parsing(file_types, expected_extensions):
    """Test that file types are parsed correctly."""
    env_vars = {
        'SECRET_KEY': 'valid-secret-key-that-is-at-least-32-characters-long',
        'ALLOWED_FILE_TYPES': file_types,
    }
    
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        assert settings.allowed_file_extensions == expected_extensions