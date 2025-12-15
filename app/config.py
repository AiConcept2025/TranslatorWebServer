"""
Configuration management for the Translation Web Server.

STRICT CONFIGURATION POLICY:
- NO default values for critical settings
- Server MUST fail to start if required values are missing
- Configuration ONLY from .env file
- Clear error messages for missing configuration
"""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
import os


class Settings(BaseSettings):
    """
    Application settings with STRICT validation.

    All critical fields are REQUIRED and have NO defaults.
    Server will fail to start with clear error if configuration is missing.
    """

    # Application Configuration - Basic defaults OK
    app_name: str = "TranslatorWebServer"
    app_version: str = "1.0.0"
    environment: str  # REQUIRED - no default
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Security - REQUIRED, no defaults
    secret_key: str  # REQUIRED - no default
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Database Configuration - REQUIRED, no defaults
    mongodb_uri: str  # REQUIRED - no default
    mongodb_database: str  # REQUIRED - no default

    # Translation Services - Optional (truly optional)
    google_translate_api_key: Optional[str] = None
    deepl_api_key: Optional[str] = None
    azure_translator_key: Optional[str] = None
    azure_translator_endpoint: Optional[str] = None
    azure_translator_region: Optional[str] = None

    # Payment Configuration - REQUIRED for payment features
    stripe_secret_key: str  # REQUIRED - no default
    stripe_webhook_secret: Optional[str] = None  # Can be None for test mode

    @field_validator('stripe_webhook_secret')
    @classmethod
    def set_default_test_webhook_secret(cls, v, info):
        """Set default test webhook secret when in test mode."""
        # Test mode detected by mongodb_database ending with '_test'
        db_name = info.data.get('mongodb_database', '')
        if v is None and db_name.endswith('_test'):
            return 'whsec_test_secret_for_integration_testing'
        return v

    # File Upload Configuration - Sensible defaults OK
    max_file_size: int = 10485760  # 10MB
    allowed_file_types: str = "txt,doc,docx,pdf,rtf,odt,jpeg,jpg,png,tiff,tif"
    upload_dir: str = "./uploads"
    temp_dir: str = "./uploads/temp"

    # Document and Image Size Limits - Sensible defaults OK
    max_document_size: int = 104857600  # 100MB for documents
    max_image_size: int = 52428800      # 50MB for images

    # Google Drive Configuration - REQUIRED if enabled
    google_drive_enabled: bool = True
    google_drive_credentials_path: str  # REQUIRED - no default
    google_drive_parent_folder_id: str  # REQUIRED - no default
    google_drive_scopes: str = "https://www.googleapis.com/auth/drive.file"

    # OAuth2-specific (truly optional - only for OAuth2 Desktop flow)
    google_drive_token_path: Optional[str] = "./token.json"
    google_drive_application_name: Optional[str] = "TranslatorWebServer"

    # Subscription Configuration - Sensible default OK
    subscription_soft_limit: int = -100  # Warning threshold for negative balance

    # Rate Limiting - Sensible defaults OK
    rate_limiting_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour

    # Logging - Sensible defaults OK
    log_level: str = "INFO"
    log_file: str = "./logs/translator.log"

    # CORS Configuration - REQUIRED, no defaults
    cors_origins: str  # REQUIRED - no default
    cors_credentials: bool = True
    cors_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_headers: str = "*"

    # API Configuration - Optional (can be inferred from host/port)
    api_url: Optional[str] = None


    # Monitoring - Sensible defaults OK
    health_check_interval: int = 30
    metrics_enabled: bool = True

    # Email Configuration - REQUIRED for email features
    smtp_host: str  # REQUIRED - no default
    smtp_port: int  # REQUIRED - no default
    smtp_username: str  # REQUIRED - no default (can be empty string in .env)
    smtp_password: str  # REQUIRED - no default (can be empty string in .env)
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout: int = 30
    email_from: str  # REQUIRED - no default
    email_from_name: str  # REQUIRED - no default
    email_reply_to: Optional[str] = None
    email_enabled: bool = True
    email_template_dir: str = "./app/templates/email"

    # Company Information - REQUIRED for invoices and communications
    company_name: str  # REQUIRED - no default (e.g., "Iris Solutions")
    company_email: str  # REQUIRED - no default (e.g., "billing@irissolutions.com")
    company_phone: str  # REQUIRED - no default (e.g., "(555) 123-4567")
    translation_service_company: str  # REQUIRED - no default (legacy field)

    # Simple validators for basic format checking only
    @field_validator('allowed_file_types')
    @classmethod
    def validate_file_types(cls, v):
        """Ensure allowed_file_types is not empty."""
        if not v:
            raise ValueError("ALLOWED_FILE_TYPES cannot be empty")
        return v

    @field_validator('cors_origins')
    @classmethod
    def validate_cors_origins(cls, v):
        """Parse CORS origins to list."""
        if not v:
            raise ValueError("CORS_ORIGINS must be set")
        return [origin.strip() for origin in v.split(',') if origin.strip()]

    @field_validator('cors_methods')
    @classmethod
    def validate_cors_methods(cls, v):
        """Parse CORS methods to list."""
        return [method.strip() for method in v.split(',') if method.strip()]

    @field_validator('smtp_port')
    @classmethod
    def validate_smtp_port(cls, v):
        """Validate SMTP port is in valid range."""
        if not (1 <= v <= 65535):
            raise ValueError("SMTP_PORT must be between 1 and 65535")
        return v

    @property
    def allowed_file_extensions(self) -> List[str]:
        """Get list of allowed file extensions."""
        return [ext.strip() for ext in self.allowed_file_types.split(',')]
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    @property
    def active_mongodb_database(self) -> str:
        """Get the active MongoDB database name."""
        return self.mongodb_database

    def is_test_mode(self) -> bool:
        """Check if running in test mode (database ends with '_test')."""
        return self.mongodb_database.endswith('_test')

    @property
    def log_config(self) -> dict:
        """Get logging configuration."""
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S"
                },
                "json": {
                    "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                    "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout"
                },
                "file": {
                    "formatter": "json" if self.is_production else "default",
                    "class": "logging.FileHandler",
                    "filename": self.log_file,
                    "mode": "a"
                }
            },
            "root": {
                "level": self.log_level,
                "handlers": ["default", "file"]
            }
        }
    
    def ensure_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.upload_dir,
            self.temp_dir,
            self.email_template_dir,
            os.path.dirname(self.log_file) if self.log_file else None
        ]

        for directory in directories:
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.

    Note: Cache is cleared on module reload to ensure settings
    are re-read when code changes during development.
    """
    return Settings()


# Global settings instance
settings = get_settings()

# Ensure directories exist on import
settings.ensure_directories()