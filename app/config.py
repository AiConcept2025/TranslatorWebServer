"""
Configuration management for the Translation Web Server.
"""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import validator
import os


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Application Configuration
    app_name: str = "TranslatorWebServer"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Database Configuration
    database_url: str = "sqlite:///./translator.db"
    mongodb_uri: str  # Required - must be set in .env file (no hardcoded credentials)
    mongodb_database: str = "translation"
    mongodb_database_test: str = "translation_test"
    database_mode: str = "production"  # "production" or "test"

    # Redis Configuration
    redis_url: str = "redis://localhost:6379/0"
    
    # Translation Services
    google_translate_api_key: Optional[str] = None
    deepl_api_key: Optional[str] = None
    azure_translator_key: Optional[str] = None
    azure_translator_endpoint: Optional[str] = None
    azure_translator_region: Optional[str] = None
    
    # Payment Configuration
    stripe_public_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    
    # File Upload Configuration
    max_file_size: int = 10485760  # 10MB
    allowed_file_types: str = "txt,doc,docx,pdf,rtf,odt,jpeg,jpg,png,tiff,tif"
    upload_dir: str = "./uploads"
    temp_dir: str = "./uploads/temp"
    
    # Document and Image Size Limits
    max_document_size: int = 104857600  # 100MB for documents
    max_image_size: int = 52428800      # 50MB for images
    
    # Google Drive Configuration
    google_drive_enabled: bool = True
    google_drive_credentials_path: str = "./service-account-key.json"
    google_drive_token_path: str = "./token.json"
    google_drive_root_folder: str = "IrisSolutions"
    google_drive_scopes: str = "https://www.googleapis.com/auth/drive"
    google_drive_application_name: str = "TranslatorWebServer"
    
    # Customer Configuration
    default_customer_email: str = "ben.danishevsky@gmail.com"  # Used for folder names only
    google_drive_owner_email: str = "danishevsky@gmail.com"    # Actual file owner (.env account)
    
    # Rate Limiting
    rate_limiting_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # 1 hour
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/translator.log"
    
    # CORS Configuration
    cors_origins: str = "http://localhost:3000,http://localhost:8080"
    cors_credentials: bool = True
    cors_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_headers: str = "*"
    
    # Background Tasks
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    
    # Monitoring
    health_check_interval: int = 30
    metrics_enabled: bool = True
    
    # Email Configuration (Yahoo SMTP defaults)
    smtp_host: str = "smtp.mail.yahoo.com"
    smtp_port: int = 587
    smtp_username: Optional[str] = None  # Yahoo email address
    smtp_password: Optional[str] = None  # Yahoo app-specific password
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    smtp_timeout: int = 30
    email_from: Optional[str] = None  # Sender email
    email_from_name: str = "Iris Solutions Translation Services"
    email_reply_to: Optional[str] = None
    email_enabled: bool = True
    email_template_dir: str = "./app/templates/email"
    translation_service_company: str = "Iris Solutions"
    
    @validator('secret_key')
    def validate_secret_key(cls, v):
        if not v or v == "your-secret-key-here-change-in-production":
            raise ValueError("SECRET_KEY must be set and not be the default value")
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    @validator('mongodb_uri')
    def validate_mongodb_uri(cls, v):
        if not v:
            raise ValueError("MONGODB_URI must be set in .env file")
        # Check for placeholder values
        placeholder_values = ['user:password', 'your-', 'changeme', 'placeholder']
        for placeholder in placeholder_values:
            if placeholder in v.lower():
                raise ValueError(
                    f"MONGODB_URI contains placeholder value '{placeholder}'. "
                    "Please set actual MongoDB credentials in .env file"
                )
        # Basic format validation
        if not v.startswith(('mongodb://', 'mongodb+srv://')):
            raise ValueError("MONGODB_URI must start with 'mongodb://' or 'mongodb+srv://'")
        return v
    
    @validator('allowed_file_types')
    def validate_file_types(cls, v):
        if not v:
            raise ValueError("ALLOWED_FILE_TYPES cannot be empty")
        return v
    
    @validator('cors_origins')
    def validate_cors_origins(cls, v):
        return [origin.strip() for origin in v.split(',') if origin.strip()]
    
    @validator('cors_methods')
    def validate_cors_methods(cls, v):
        return [method.strip() for method in v.split(',') if method.strip()]
    
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
        """Get the active MongoDB database based on database_mode."""
        if self.database_mode.lower() == "test":
            return self.mongodb_database_test
        return self.mongodb_database

    def is_test_mode(self) -> bool:
        """Check if running in test mode."""
        return self.database_mode.lower() == "test"

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
    """Get cached application settings."""
    return Settings()


# Global settings instance
settings = get_settings()

# Ensure directories exist on import
settings.ensure_directories()