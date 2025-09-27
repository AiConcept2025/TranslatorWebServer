"""
Custom exceptions for the TranslatorWebServer application.
"""

from .google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveAuthenticationError,
    GoogleDriveQuotaExceededError,
    GoogleDriveFileNotFoundError,
    GoogleDrivePermissionError,
    GoogleDriveStorageError,
    handle_google_drive_error,
    google_drive_error_to_http_exception,
    handle_google_drive_exceptions
)

__all__ = [
    "GoogleDriveError",
    "GoogleDriveAuthenticationError", 
    "GoogleDriveQuotaExceededError",
    "GoogleDriveFileNotFoundError",
    "GoogleDrivePermissionError",
    "GoogleDriveStorageError",
    "handle_google_drive_error",
    "google_drive_error_to_http_exception",
    "handle_google_drive_exceptions"
]