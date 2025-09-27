"""
Google Drive specific exceptions and error handling.
"""

from typing import Optional
from fastapi import HTTPException
from googleapiclient.errors import HttpError
import logging


class GoogleDriveError(Exception):
    """Base class for Google Drive related errors."""
    
    def __init__(self, message: str, status_code: int = 500, original_error: Optional[Exception] = None):
        self.message = message
        self.status_code = status_code
        self.original_error = original_error
        super().__init__(self.message)


class GoogleDriveAuthenticationError(GoogleDriveError):
    """Raised when Google Drive authentication fails."""
    
    def __init__(self, message: str = "Google Drive authentication failed", original_error: Optional[Exception] = None):
        super().__init__(message, 401, original_error)


class GoogleDriveQuotaExceededError(GoogleDriveError):
    """Raised when Google Drive quota is exceeded."""
    
    def __init__(self, message: str = "Google Drive quota exceeded", original_error: Optional[Exception] = None):
        super().__init__(message, 429, original_error)


class GoogleDriveFileNotFoundError(GoogleDriveError):
    """Raised when a file or folder is not found in Google Drive."""
    
    def __init__(self, message: str = "File or folder not found in Google Drive", original_error: Optional[Exception] = None):
        super().__init__(message, 404, original_error)


class GoogleDrivePermissionError(GoogleDriveError):
    """Raised when Google Drive permission is denied."""
    
    def __init__(self, message: str = "Google Drive permission denied", original_error: Optional[Exception] = None):
        super().__init__(message, 403, original_error)


class GoogleDriveStorageError(GoogleDriveError):
    """Raised when Google Drive storage operations fail."""
    
    def __init__(self, message: str = "Google Drive storage operation failed", original_error: Optional[Exception] = None):
        super().__init__(message, 500, original_error)


def handle_google_drive_error(error: Exception, operation: str = "Google Drive operation") -> GoogleDriveError:
    """
    Convert Google Drive API errors to custom exceptions.
    
    Args:
        error: The original exception
        operation: Description of the operation that failed
        
    Returns:
        GoogleDriveError: Appropriate custom exception
    """
    if isinstance(error, HttpError):
        status_code = error.resp.status
        error_details = error.error_details if hasattr(error, 'error_details') else []
        
        # Log the original error for debugging
        logging.error(f"Google Drive API error during {operation}: {status_code} - {error}")
        
        if status_code == 401:
            return GoogleDriveAuthenticationError(
                f"Authentication failed during {operation}. Please check credentials.",
                original_error=error
            )
        elif status_code == 403:
            # Check if it's a quota or permission issue
            error_reason = ""
            for detail in error_details:
                if detail.get("reason") in ["quotaExceeded", "rateLimitExceeded"]:
                    return GoogleDriveQuotaExceededError(
                        f"Google Drive quota exceeded during {operation}",
                        original_error=error
                    )
                error_reason = detail.get("reason", "")
            
            return GoogleDrivePermissionError(
                f"Permission denied during {operation}: {error_reason}",
                original_error=error
            )
        elif status_code == 404:
            return GoogleDriveFileNotFoundError(
                f"File or folder not found during {operation}",
                original_error=error
            )
        elif status_code == 429:
            return GoogleDriveQuotaExceededError(
                f"Rate limit exceeded during {operation}",
                original_error=error
            )
        else:
            return GoogleDriveStorageError(
                f"Google Drive API error during {operation}: {status_code}",
                original_error=error
            )
    
    elif isinstance(error, (ConnectionError, TimeoutError)):
        logging.error(f"Network error during {operation}: {error}")
        return GoogleDriveStorageError(
            f"Network error during {operation}. Please check your connection.",
            original_error=error
        )
    
    else:
        logging.error(f"Unexpected error during {operation}: {error}")
        return GoogleDriveStorageError(
            f"Unexpected error during {operation}: {str(error)}",
            original_error=error
        )


def google_drive_error_to_http_exception(error: GoogleDriveError) -> HTTPException:
    """
    Convert GoogleDriveError to FastAPI HTTPException.
    
    Args:
        error: GoogleDriveError instance
        
    Returns:
        HTTPException: FastAPI compatible exception
    """
    return HTTPException(
        status_code=error.status_code,
        detail={
            "error": "google_drive_error",
            "message": error.message,
            "operation_failed": True,
            "retry_recommended": error.status_code in [429, 500, 502, 503, 504]
        }
    )


# Error handling decorator
def handle_google_drive_exceptions(operation: str):
    """
    Decorator to handle Google Drive exceptions in service methods.
    
    Args:
        operation: Description of the operation being performed
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except GoogleDriveError:
                # Re-raise our custom exceptions
                raise
            except Exception as e:
                # Convert other exceptions to our custom format
                custom_error = handle_google_drive_error(e, operation)
                raise custom_error
        return wrapper
    return decorator