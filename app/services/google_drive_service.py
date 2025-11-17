"""
Google Drive service for folder management and file operations.
No local storage fallback - Google Drive only.
"""

import os
import io
import logging
import asyncio
import ssl
import time
from typing import Dict, List, Optional, Tuple, Any, Callable, TypeVar
from pathlib import Path
from datetime import datetime, timezone
from functools import wraps

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient.errors import HttpError
import json

from app.config import settings
from app.exceptions.google_drive_exceptions import (
    GoogleDriveError,
    GoogleDriveAuthenticationError,
    GoogleDriveStorageError,
    handle_google_drive_error,
    handle_google_drive_exceptions
)

# Type variable for generic retry decorator
T = TypeVar('T')


def retry_on_ssl_error(
    max_retries: int = 5,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0
):
    """
    Decorator to retry async functions on SSL and transient network errors.

    Implements exponential backoff to handle intermittent SSL connection failures
    commonly seen with httplib2 in Google Drive API operations.

    SSL errors typically manifest as:
    - ssl.SSLError: [SSL] record layer failure
    - ConnectionResetError
    - BrokenPipeError

    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay in seconds (default: 1.0)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)

    Returns:
        Decorated async function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    # Attempt to execute the function
                    return await func(*args, **kwargs)

                except ssl.SSLError as e:
                    last_exception = e
                    error_msg = str(e)

                    if attempt < max_retries:
                        # Log retry with details
                        logging.warning(
                            f"SSL error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): "
                            f"{error_msg}. Retrying in {delay:.1f}s..."
                        )

                        # Wait before retry with exponential backoff
                        await asyncio.sleep(delay)

                        # Calculate next delay with exponential backoff, capped at max_delay
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        # Final attempt failed
                        logging.error(
                            f"SSL error in {func.__name__} failed after {max_retries + 1} attempts: "
                            f"{error_msg}"
                        )

                except (ConnectionResetError, BrokenPipeError, ConnectionError) as e:
                    last_exception = e
                    error_msg = str(e)

                    if attempt < max_retries:
                        # Log retry for connection errors
                        logging.warning(
                            f"Connection error in {func.__name__} (attempt {attempt + 1}/{max_retries + 1}): "
                            f"{error_msg}. Retrying in {delay:.1f}s..."
                        )

                        # Wait before retry
                        await asyncio.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        logging.error(
                            f"Connection error in {func.__name__} failed after {max_retries + 1} attempts: "
                            f"{error_msg}"
                        )

                except HttpError as e:
                    # For Google API HTTP errors, only retry on specific transient errors
                    # 429: Too Many Requests, 500: Internal Server Error, 503: Service Unavailable
                    if e.resp.status in (429, 500, 503) and attempt < max_retries:
                        last_exception = e
                        logging.warning(
                            f"Transient HTTP error {e.resp.status} in {func.__name__} "
                            f"(attempt {attempt + 1}/{max_retries + 1}). Retrying in {delay:.1f}s..."
                        )

                        await asyncio.sleep(delay)
                        delay = min(delay * backoff_factor, max_delay)
                    else:
                        # Non-retryable HTTP error or final attempt - re-raise immediately
                        raise

                except Exception as e:
                    # For all other exceptions, don't retry - re-raise immediately
                    logging.debug(f"Non-retryable exception in {func.__name__}: {type(e).__name__}")
                    raise

            # All retries exhausted - raise the last exception
            if last_exception:
                raise GoogleDriveError(
                    f"Operation {func.__name__} failed after {max_retries + 1} attempts due to "
                    f"{type(last_exception).__name__}: {str(last_exception)}",
                    original_error=last_exception
                )

        return wrapper
    return decorator


class GoogleDriveService:
    """Service for Google Drive folder management and file operations."""
    
    def __init__(self):
        if not settings.google_drive_enabled:
            raise GoogleDriveStorageError("Google Drive is disabled in configuration")
            
        self.credentials_path = settings.google_drive_credentials_path
        self.token_path = settings.google_drive_token_path
        self.root_folder = settings.google_drive_root_folder
        self.scopes = [scope.strip() for scope in settings.google_drive_scopes.split(',')]
        self.application_name = settings.google_drive_application_name
        
        # Initialize service - no fallback, must succeed
        self.service = self._initialize_service()
        logging.info("Google Drive service initialized successfully")
    
    def _initialize_service(self):
        """
        Initialize Google Drive API service.
        
        Returns:
            Google Drive API service object
            
        Raises:
            GoogleDriveError: If initialization fails
        """
        try:
            creds = None
            
            # Check if credentials file exists
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                raise GoogleDriveAuthenticationError(
                    f"Google Drive credentials file not found: {self.credentials_path}"
                )
            
            # Try to determine credential type by reading the file
            try:
                with open(self.credentials_path, 'r') as f:
                    cred_data = json.load(f)
                
                # Check if it's a service account credential
                if cred_data.get('type') == 'service_account':
                    logging.info("Using service account credentials")
                    creds = ServiceAccountCredentials.from_service_account_file(
                        self.credentials_path, scopes=self.scopes
                    )
                else:
                    # OAuth2 flow - try existing token first
                    if self.token_path and os.path.exists(self.token_path):
                        creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
                    
                    # If no valid credentials, run OAuth flow
                    if not creds or not creds.valid:
                        if creds and creds.expired and creds.refresh_token:
                            try:
                                creds.refresh(Request())
                                logging.info("Google Drive credentials refreshed")
                            except Exception as e:
                                logging.error(f"Failed to refresh credentials: {e}")
                                raise GoogleDriveAuthenticationError(
                                    "Failed to refresh Google Drive credentials", 
                                    original_error=e
                                )
                        
                        if not creds:
                            try:
                                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
                                creds = flow.run_local_server(port=0)
                                logging.info("New Google Drive credentials obtained")
                            except Exception as e:
                                raise GoogleDriveAuthenticationError(
                                    "Failed to obtain Google Drive credentials",
                                    original_error=e
                                )
                        
                        # Save the credentials for the next run
                        if self.token_path:
                            try:
                                with open(self.token_path, 'w') as token:
                                    token.write(creds.to_json())
                                logging.info(f"Google Drive token saved to {self.token_path}")
                            except Exception as e:
                                logging.warning(f"Failed to save token file: {e}")
                
            except json.JSONDecodeError as e:
                raise GoogleDriveAuthenticationError(
                    f"Invalid JSON in credentials file: {self.credentials_path}",
                    original_error=e
                )
            except Exception as e:
                raise GoogleDriveAuthenticationError(
                    f"Failed to load credentials from {self.credentials_path}",
                    original_error=e
                )
            
            service = build('drive', 'v3', credentials=creds)
            logging.info("Google Drive service built successfully")
            return service
            
        except GoogleDriveError:
            raise
        except Exception as e:
            raise GoogleDriveStorageError(
                "Failed to initialize Google Drive service",
                original_error=e
            )
    
    @handle_google_drive_exceptions("create customer folder structure")
    async def create_customer_folder_structure(self, customer_email: str, company_name: str = None) -> str:
        """
        Create complete folder structure for customer.

        For enterprise customers (company_name provided):
            CompanyName/customer_email/Inbox/
            CompanyName/customer_email/Temp/
            CompanyName/customer_email/Completed/

        For individual customers (no company_name):
            customer_email/Inbox/
            customer_email/Temp/
            customer_email/Completed/

        Note: customer_email is used ONLY for folder naming/organization.
        All files are owned by the service account (google_drive_owner_email).
        The customer_email does NOT get access to the files.

        Args:
            customer_email: Customer's email address (used for folder name only)
            company_name: Optional company name for enterprise customers

        Returns:
            Folder ID of the Temp folder where files should be uploaded

        Raises:
            GoogleDriveError: If folder creation fails
        """
        if company_name:
            logging.info(f"Creating enterprise folder structure: {company_name}/{customer_email}")
        else:
            logging.info(f"Creating individual folder structure: {customer_email}")

        # Find or create root folder
        root_folder_id = await self._find_or_create_folder(self.root_folder, None)
        logging.info(f"Root folder ID: {root_folder_id}")

        # For enterprise customers, create company folder first
        if company_name:
            company_folder_id = await self._find_or_create_folder(company_name, root_folder_id)
            logging.info(f"Company folder ID: {company_folder_id}")
            parent_folder_id = company_folder_id
        else:
            parent_folder_id = root_folder_id

        # Find or create customer folder (under company folder for enterprise, under root for individual)
        customer_folder_id = await self._find_or_create_folder(customer_email, parent_folder_id)
        logging.info(f"Customer folder ID: {customer_folder_id}")

        # Create all required subfolders: Inbox, Temp, Completed
        inbox_folder_id = await self._find_or_create_folder("Inbox", customer_folder_id)
        temp_folder_id = await self._find_or_create_folder("Temp", customer_folder_id)
        completed_folder_id = await self._find_or_create_folder("Completed", customer_folder_id)

        if company_name:
            logging.info(f"Enterprise folder structure: {company_name}/{customer_email}/ - Inbox: {inbox_folder_id}, Temp: {temp_folder_id}, Completed: {completed_folder_id}")
        else:
            logging.info(f"Individual folder structure: {customer_email}/ - Inbox: {inbox_folder_id}, Temp: {temp_folder_id}, Completed: {completed_folder_id}")

        return temp_folder_id
    
    @handle_google_drive_exceptions("upload file to folder with metadata")
    async def upload_file_to_folder_with_metadata(
        self, 
        file_content: bytes, 
        filename: str, 
        folder_id: str,
        customer_email: str,
        source_language: str,
        target_language: str,
        page_count: int
    ) -> Dict[str, Any]:
        """
        Upload file to Google Drive folder with comprehensive metadata for payment tracking.
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            folder_id: Target folder ID (from create_customer_folder_structure)
            customer_email: Customer email for linking payment to files
            source_language: Source language
            target_language: Target language for metadata
            page_count: Number of pages for pricing
            
        Returns:
            Dictionary with file information
            
        Raises:
            GoogleDriveError: If upload fails
        """
        logging.info(f"Uploading file to Google Drive: {filename} -> {folder_id}")
        
        # Create file metadata with comprehensive payment tracking info
        file_metadata = {
            'name': filename,
            'parents': [folder_id],
            'properties': {
                'customer_email': customer_email,
                'source_language': source_language,
                'target_language': target_language,
                'page_count': str(page_count),
                'status': 'awaiting_payment',
                'upload_timestamp': datetime.utcnow().isoformat(),
                'original_filename': filename
            },
            'description': f'Translation file: {source_language}->{target_language}, {page_count} pages, customer: {customer_email}'
        }
        
        # Create media upload object
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype='application/octet-stream',
            resumable=True
        )

        # Upload file with retry logic for SSL errors
        file = await self._upload_file_with_retry(file_metadata, media)

        logging.info(f"File uploaded successfully: {file.get('id')}")

        file_info = {
            'file_id': file.get('id'),
            'filename': file.get('name'),
            'folder_id': folder_id,
            'size': int(file.get('size', len(file_content))),
            'customer_email': customer_email,
            'source_language': source_language,
            'target_language': target_language,
            'page_count': page_count,
            'status': 'awaiting_payment',
            'created_at': file.get('createdTime'),
            'google_drive_url': file.get('webViewLink'),
            'parents': file.get('parents', [])
        }

        return file_info

    @handle_google_drive_exceptions("upload file to folder")
    async def upload_file_to_folder(
        self, 
        file_content: bytes, 
        filename: str, 
        folder_id: str,
        target_language: str
    ) -> Dict[str, Any]:
        """
        Upload file to Google Drive folder and update metadata.
        
        Args:
            file_content: File content as bytes
            filename: Original filename
            folder_id: Target folder ID (from create_customer_folder_structure)
            target_language: Target language for metadata
            
        Returns:
            Dictionary with file information
            
        Raises:
            GoogleDriveError: If upload fails
        """
        logging.info(f"Uploading file to Google Drive: {filename} -> {folder_id}")
        
        # Create file metadata
        file_metadata = {
            'name': filename,
            'parents': [folder_id],
            'properties': {
                'target_language': target_language,
                'upload_timestamp': datetime.utcnow().isoformat(),
                'original_filename': filename
            },
            'description': f'File uploaded for translation to {target_language}'
        }

        # Create media upload object
        media = MediaIoBaseUpload(
            io.BytesIO(file_content),
            mimetype='application/octet-stream',
            resumable=True
        )

        # Upload file with retry logic for SSL errors
        file = await self._upload_file_with_retry(file_metadata, media)

        logging.info(f"File uploaded successfully: {file.get('id')}")

        file_info = {
            'file_id': file.get('id'),
            'filename': file.get('name'),
            'folder_id': folder_id,
            'size': int(file.get('size', len(file_content))),
            'target_language': target_language,
            'created_at': file.get('createdTime'),
            'google_drive_url': file.get('webViewLink'),
            'parents': file.get('parents', [])
        }

        return file_info
    
    @handle_google_drive_exceptions("update file metadata")
    async def update_file_metadata(self, file_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update file metadata in Google Drive.
        
        Args:
            file_id: Google Drive file ID
            metadata: Metadata to update
            
        Returns:
            True if successful
            
        Raises:
            GoogleDriveError: If metadata update fails
        """
        logging.info(f"Updating Google Drive file metadata for: {file_id}")
        
        # Update file properties
        body = {}
        if 'properties' in metadata:
            body['properties'] = metadata['properties']
        if 'description' in metadata:
            body['description'] = metadata['description']
        if 'name' in metadata:
            body['name'] = metadata['name']

        if body:
            # Update metadata with retry logic for SSL errors
            await self._update_file_metadata_with_retry(file_id, body)

        logging.info(f"Updated metadata for file {file_id}")
        return True
    
    @handle_google_drive_exceptions("list files in folder")
    async def list_files_in_folder(self, folder_id: str) -> List[Dict[str, Any]]:
        """
        List files in a Google Drive folder.
        
        Args:
            folder_id: Folder ID to list files from
            
        Returns:
            List of file information dictionaries
            
        Raises:
            GoogleDriveError: If listing files fails
        """
        logging.info(f"Listing Google Drive files in folder: {folder_id}")

        # Query for files in the folder
        query = f"'{folder_id}' in parents and trashed=false"

        # List files with retry logic for SSL errors
        results = await self._list_files_with_retry(
            query=query,
            fields='files(id,name,size,createdTime,webViewLink,mimeType,properties)'
        )

        files = results.get('files', [])
        file_list = []
        
        for file in files:
            file_info = {
                'file_id': file.get('id'),
                'filename': file.get('name'),
                'size': int(file.get('size', 0)) if file.get('size') else 0,
                'created_at': file.get('createdTime'),
                'folder_id': folder_id,
                'google_drive_url': file.get('webViewLink'),
                'mime_type': file.get('mimeType'),
                'properties': file.get('properties', {})
            }
            file_list.append(file_info)
        
        logging.info(f"Listed {len(file_list)} files in Google Drive folder")
        return file_list
    
    @handle_google_drive_exceptions("delete file")
    async def delete_file(self, file_id: str) -> bool:
        """
        Delete file from Google Drive.

        Args:
            file_id: File ID to delete

        Returns:
            True if successful

        Raises:
            GoogleDriveError: If deletion fails
        """
        logging.info(f"Deleting Google Drive file: {file_id}")

        # Delete file with retry logic for SSL errors
        await self._delete_file_with_retry(file_id)
        logging.info(f"Deleted Google Drive file: {file_id}")
        return True
    
    @handle_google_drive_exceptions("get folder info")
    async def get_folder_info(self, folder_id: str) -> Dict[str, Any]:
        """
        Get folder information and statistics.
        
        Args:
            folder_id: Folder ID to analyze
            
        Returns:
            Dictionary with folder information
            
        Raises:
            GoogleDriveError: If getting folder info fails
        """
        logging.info(f"Getting Google Drive folder info for: {folder_id}")
        
        files = await self.list_files_in_folder(folder_id)
        total_size = sum(file.get('size', 0) for file in files)
        
        # Get folder details
        folder_info = {
            'folder_id': folder_id,
            'total_files': len(files),
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'storage_type': 'google_drive',
            'last_updated': datetime.utcnow().isoformat()
        }

        try:
            # Get folder details with retry logic for SSL errors
            folder_details = await self._get_file_with_retry(
                file_id=folder_id,
                fields='name,createdTime,modifiedTime'
            )

            folder_info.update({
                'folder_name': folder_details.get('name'),
                'created_at': folder_details.get('createdTime'),
                'modified_at': folder_details.get('modifiedTime')
            })
        except Exception as e:
            logging.warning(f"Could not get folder details: {e}")
        
        logging.info(f"Folder info: {folder_info['total_files']} files, {folder_info['total_size_mb']}MB")
        return folder_info
    
    @handle_google_drive_exceptions("move files to inbox")
    async def move_files_to_inbox_on_payment_success(self, customer_email: str, file_ids: List[str], company_name: str = None) -> Dict[str, Any]:
        """
        Move files from Temp to Inbox folder when payment is confirmed.

        REDESIGNED: Simple, sequential approach that avoids parallel API calls.
        We already know the folder structure, so we get Temp folder ID once
        and use it to move all files.

        For enterprise: CompanyName/customer_email/Temp/ → CompanyName/customer_email/Inbox/
        For individual: customer_email/Temp/ → customer_email/Inbox/

        Args:
            customer_email: Customer's email address
            file_ids: List of file IDs to move
            company_name: Optional company name for enterprise customers

        Returns:
            Dictionary with move operation results

        Raises:
            GoogleDriveError: If file movement fails
        """
        if company_name:
            logging.info(f"Moving {len(file_ids)} files to Inbox for enterprise: {company_name}/{customer_email}")
            print(f"Google Drive: Moving {len(file_ids)} files to Inbox for {company_name}/{customer_email}")
        else:
            logging.info(f"Moving {len(file_ids)} files to Inbox for {customer_email}")
            print(f"Google Drive: Moving {len(file_ids)} files to Inbox for {customer_email}")
        print(f"Files to move: {file_ids}")

        # Get folder structure
        root_folder_id = await self._find_or_create_folder(self.root_folder, None)
        print(f"Root folder ID: {root_folder_id}")

        # For enterprise, navigate through company folder first
        if company_name:
            company_folder_id = await self._find_or_create_folder(company_name, root_folder_id)
            print(f"Company folder ID: {company_folder_id}")
            parent_folder_id = company_folder_id
        else:
            parent_folder_id = root_folder_id

        customer_folder_id = await self._find_or_create_folder(customer_email, parent_folder_id)
        print(f"Customer folder ID: {customer_folder_id}")

        # Get BOTH Temp and Inbox folder IDs - we know the structure!
        temp_folder_id = await self._find_or_create_folder("Temp", customer_folder_id)
        inbox_folder_id = await self._find_or_create_folder("Inbox", customer_folder_id)
        print(f"Temp folder ID: {temp_folder_id}")
        print(f"Inbox folder ID: {inbox_folder_id}")

        moved_files = []
        failed_moves = []

        # Move files one by one - simple and reliable
        print(f"📦 Moving {len(file_ids)} files from Temp to Inbox...")
        start_time = asyncio.get_event_loop().time()

        for index, file_id in enumerate(file_ids, 1):
            try:
                print(f"   [{index}/{len(file_ids)}] Moving {file_id}...")

                # Move file: remove from Temp, add to Inbox
                # Wrap in retry logic to handle SSL errors
                updated_file = await self._move_file_with_retry(
                    file_id=file_id,
                    add_parents=inbox_folder_id,
                    remove_parents=temp_folder_id
                )

                file_name = updated_file.get('name', 'Unknown')
                print(f"   ✓ [{index}/{len(file_ids)}] Moved: {file_name}")
                logging.info(f"Successfully moved file {file_id} ({file_name}) to Inbox")

                moved_files.append({
                    'file_id': file_id,
                    'status': 'moved',
                    'new_parent': inbox_folder_id,
                    'old_parent': temp_folder_id,
                    'file_name': file_name
                })

            except Exception as e:
                error_msg = str(e)
                print(f"   ✗ [{index}/{len(file_ids)}] Failed to move {file_id}: {error_msg}")
                logging.error(f"Failed to move file {file_id}: {error_msg}")

                failed_moves.append({
                    'file_id': file_id,
                    'status': 'failed',
                    'error': error_msg
                })

        elapsed_time = asyncio.get_event_loop().time() - start_time
        print(f"📦 Move operation completed in {elapsed_time:.2f}s")

        result = {
            'customer_email': customer_email,
            'total_files': len(file_ids),
            'moved_successfully': len(moved_files),
            'failed_moves': len(failed_moves),
            'moved_files': moved_files,
            'failed_files': failed_moves,
            'inbox_folder_id': inbox_folder_id,
            'temp_folder_id': temp_folder_id
        }

        print(f"✅ COMPLETE: {len(moved_files)}/{len(file_ids)} files moved successfully")
        if moved_files:
            print(f"   Files now in: {customer_email}/Inbox/ (ID: {inbox_folder_id})")
        if failed_moves:
            print(f"❌ FAILED: {len(failed_moves)} files")
            for failed in failed_moves[:3]:  # Show first 3 failures
                print(f"   - {failed['file_id']}: {failed['error'][:100]}")

        logging.info(f"Move operation completed: {len(moved_files)}/{len(file_ids)} files moved successfully")
        return result
    
    @handle_google_drive_exceptions("delete files on payment failure")
    async def delete_files_on_payment_failure(self, customer_email: str, file_ids: List[str]) -> Dict[str, Any]:
        """
        Delete files from Temp folder when payment fails.
        
        Args:
            customer_email: Customer's email address
            file_ids: List of file IDs to delete
            
        Returns:
            Dictionary with deletion operation results
            
        Raises:
            GoogleDriveError: If file deletion fails
        """
        logging.info(f"Deleting {len(file_ids)} files for failed payment: {customer_email}")
        
        deleted_files = []
        failed_deletions = []

        for file_id in file_ids:
            try:
                # Delete the file with retry logic for SSL errors
                await self._delete_file_with_retry(file_id)

                deleted_files.append({
                    'file_id': file_id,
                    'status': 'deleted'
                })

                logging.info(f"Successfully deleted file {file_id}")

            except Exception as e:
                logging.error(f"Failed to delete file {file_id}: {e}")
                failed_deletions.append({
                    'file_id': file_id,
                    'status': 'failed',
                    'error': str(e)
                })
        
        result = {
            'customer_email': customer_email,
            'total_files': len(file_ids),
            'deleted_successfully': len(deleted_files),
            'failed_deletions': len(failed_deletions),
            'deleted_files': deleted_files,
            'failed_files': failed_deletions
        }
        
        logging.info(f"Deletion operation completed: {len(deleted_files)}/{len(file_ids)} files deleted successfully")
        return result
    
    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _get_file_parent(self, file_id: str) -> str:
        """
        Get the parent folder ID of a file.

        Args:
            file_id: File ID to get parent for

        Returns:
            Parent folder ID

        Raises:
            GoogleDriveError: If getting parent fails
        """
        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        file_info = await asyncio.to_thread(
            lambda: self.service.files().get(
                fileId=file_id,
                fields='parents'
            ).execute()
        )

        parents = file_info.get('parents', [])
        if not parents:
            raise GoogleDriveStorageError(f"File {file_id} has no parent folder")

        return parents[0]  # Return first parent

    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _move_file_with_retry(
        self,
        file_id: str,
        add_parents: str,
        remove_parents: str
    ) -> Dict[str, Any]:
        """
        Move file between folders with SSL error retry logic.

        Args:
            file_id: File ID to move
            add_parents: Folder ID to add as parent
            remove_parents: Folder ID to remove as parent

        Returns:
            Updated file metadata

        Raises:
            GoogleDriveError: If file move fails after retries
        """
        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        updated_file = await asyncio.to_thread(
            lambda: self.service.files().update(
                fileId=file_id,
                addParents=add_parents,
                removeParents=remove_parents,
                fields='id,name,parents'
            ).execute()
        )

        return updated_file

    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _delete_file_with_retry(self, file_id: str) -> None:
        """
        Delete file from Google Drive with SSL error retry logic.

        Args:
            file_id: File ID to delete

        Raises:
            GoogleDriveError: If file deletion fails after retries
        """
        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        await asyncio.to_thread(
            lambda: self.service.files().delete(fileId=file_id).execute()
        )

    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _upload_file_with_retry(
        self,
        file_metadata: Dict[str, Any],
        media: MediaIoBaseUpload
    ) -> Dict[str, Any]:
        """
        Upload file to Google Drive with SSL error retry logic.

        Args:
            file_metadata: File metadata dictionary
            media: Media upload object

        Returns:
            Created file information

        Raises:
            GoogleDriveError: If file upload fails after retries
        """
        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        file = await asyncio.to_thread(
            lambda: self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime,webViewLink,parents'
            ).execute()
        )

        return file

    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _update_file_metadata_with_retry(
        self,
        file_id: str,
        body: Dict[str, Any]
    ) -> None:
        """
        Update file metadata in Google Drive with SSL error retry logic.

        Args:
            file_id: File ID to update
            body: Metadata update body

        Raises:
            GoogleDriveError: If metadata update fails after retries
        """
        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        await asyncio.to_thread(
            lambda: self.service.files().update(
                fileId=file_id,
                body=body
            ).execute()
        )

    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _list_files_with_retry(
        self,
        query: str,
        fields: str
    ) -> Dict[str, Any]:
        """
        List files in Google Drive with SSL error retry logic.

        Args:
            query: Google Drive query string
            fields: Fields to return

        Returns:
            List results from Google Drive

        Raises:
            GoogleDriveError: If listing fails after retries
        """
        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        results = await asyncio.to_thread(
            lambda: self.service.files().list(
                q=query,
                fields=fields
            ).execute()
        )

        return results

    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _get_file_with_retry(
        self,
        file_id: str,
        fields: str
    ) -> Dict[str, Any]:
        """
        Get file metadata from Google Drive with SSL error retry logic.

        Args:
            file_id: File ID to get
            fields: Fields to return

        Returns:
            File metadata

        Raises:
            GoogleDriveError: If getting file fails after retries
        """
        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        file_info = await asyncio.to_thread(
            lambda: self.service.files().get(
                fileId=file_id,
                fields=fields
            ).execute()
        )

        return file_info

    async def _find_or_create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """
        Find existing folder or create new one in Google Drive.
        
        Args:
            name: Folder name
            parent_id: Parent folder ID (None for root)
            
        Returns:
            Folder ID
            
        Raises:
            GoogleDriveError: If folder operations fail
        """
        # First, try to find existing folder
        folder_id = await self._find_folder(name, parent_id)
        if folder_id:
            logging.info(f"Found existing folder '{name}': {folder_id}")
            return folder_id
        
        # Create new folder if not found
        folder_id = await self._create_folder(name, parent_id)
        logging.info(f"Created new folder '{name}': {folder_id}")
        return folder_id
    
    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """
        Create a folder in Google Drive.

        Args:
            name: Folder name
            parent_id: Parent folder ID (None for root)

        Returns:
            Created folder ID

        Raises:
            GoogleDriveError: If folder creation fails
        """
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        if parent_id:
            file_metadata['parents'] = [parent_id]

        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        folder = await asyncio.to_thread(
            lambda: self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
        )

        folder_id = folder.get('id')
        logging.info(f"Created Google Drive folder '{name}': {folder_id}")
        return folder_id
    
    @retry_on_ssl_error(max_retries=5, initial_delay=1.0, backoff_factor=2.0, max_delay=30.0)
    async def _find_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Find folder by name in Google Drive.

        Args:
            name: Folder name to find
            parent_id: Parent folder ID (None for root)

        Returns:
            Folder ID if found, None otherwise

        Raises:
            GoogleDriveError: If search fails
        """
        # Build query
        query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        # Run synchronous Google Drive API call in thread pool
        # Retry decorator will handle SSL errors automatically
        results = await asyncio.to_thread(
            lambda: self.service.files().list(
                q=query,
                fields='files(id, name)'
            ).execute()
        )

        files = results.get('files', [])
        if files:
            folder_id = files[0]['id']
            logging.info(f"Found Google Drive folder '{name}': {folder_id}")
            return folder_id

        logging.info(f"Folder '{name}' not found")
        return None

    async def list_files_in_temp_folder(self, customer_email: str) -> Dict[str, Any]:
        """
        List all files in customer's Temp folder.
        
        Args:
            customer_email: Customer email to identify the folder
            
        Returns:
            Dictionary with temp_folder_id and list of files
            
        Raises:
            GoogleDriveError: If operation fails
        """
        try:
            # Get customer folder structure
            root_folder_id = await self._find_or_create_folder(self.root_folder, None)
            customer_folder_id = await self._find_folder(customer_email, root_folder_id)
            
            if not customer_folder_id:
                return {
                    "temp_folder_id": None,
                    "files": []
                }
            
            temp_folder_id = await self._find_folder("Temp", customer_folder_id)
            
            if not temp_folder_id:
                return {
                    "temp_folder_id": None,
                    "files": []
                }
            
            # List files in temp folder
            files = await self.list_files_in_folder(temp_folder_id)
            
            return {
                "temp_folder_id": temp_folder_id,
                "files": files
            }
            
        except Exception as e:
            logging.error(f"Failed to list files in temp folder for {customer_email}: {e}")
            raise GoogleDriveError(f"Failed to list temp folder files: {e}")

    async def cleanup_temp_folder(self, customer_email: str) -> Dict[str, Any]:
        """
        Clean up all files in customer's Temp folder.
        
        Args:
            customer_email: Customer email to identify the folder
            
        Returns:
            Dictionary with cleanup results
            
        Raises:
            GoogleDriveError: If cleanup fails
        """
        try:
            # Get temp folder contents
            result = await self.list_files_in_temp_folder(customer_email)
            temp_folder_id = result.get("temp_folder_id")
            files = result.get("files", [])
            
            if not temp_folder_id or not files:
                return {
                    "temp_folder_id": temp_folder_id,
                    "deleted_count": 0,
                    "deleted_files": [],
                    "errors": []
                }
            
            deleted_files = []
            errors = []

            # Delete each file
            for file_info in files:
                file_id = file_info.get('file_id') or file_info.get('id')  # Try both possible keys
                file_name = file_info.get('filename') or file_info.get('name')  # Try both possible keys

                try:
                    # Delete file with retry logic for SSL errors
                    await self._delete_file_with_retry(file_id)
                    deleted_files.append({
                        "id": file_id,
                        "name": file_name,
                        "status": "deleted"
                    })
                    logging.info(f"Deleted file from temp: {file_name} (ID: {file_id})")

                except Exception as e:
                    error_msg = f"Failed to delete {file_name}: {e}"
                    errors.append(error_msg)
                    logging.error(error_msg)
            
            return {
                "temp_folder_id": temp_folder_id,
                "deleted_count": len(deleted_files),
                "deleted_files": deleted_files,
                "errors": errors
            }
            
        except Exception as e:
            logging.error(f"Failed to cleanup temp folder for {customer_email}: {e}")
            raise GoogleDriveError(f"Failed to cleanup temp folder: {e}")

    @handle_google_drive_exceptions("find files by customer email")
    async def find_files_by_customer_email(self, customer_email: str, status: str = "awaiting_payment") -> List[Dict[str, Any]]:
        """
        Find files by customer email and status (no sessions needed).
        This replaces the payment session lookup mechanism.
        
        Args:
            customer_email: Customer email to search for
            status: File status to filter by (default: "awaiting_payment")
            
        Returns:
            List of file information dictionaries
            
        Raises:
            GoogleDriveError: If search fails
        """
        logging.info(f"Searching for files by customer: {customer_email}, status: {status}")

        # Search for files with matching customer_email in properties
        query = f"properties has {{key='customer_email' and value='{customer_email}'}} and properties has {{key='status' and value='{status}'}} and trashed=false"

        try:
            # Search files with retry logic for SSL errors
            results = await self._list_files_with_retry(
                query=query,
                fields='files(id,name,size,createdTime,webViewLink,mimeType,properties,parents)'
            )

            files = results.get('files', [])
            file_list = []

            for file in files:
                properties = file.get('properties', {})
                file_info = {
                    'file_id': file.get('id'),
                    'filename': file.get('name'),
                    'size': int(file.get('size', 0)) if file.get('size') else 0,
                    'created_at': file.get('createdTime'),
                    'google_drive_url': file.get('webViewLink'),
                    'mime_type': file.get('mimeType'),
                    'parents': file.get('parents', []),

                    # Extract metadata
                    'customer_email': properties.get('customer_email'),
                    'source_language': properties.get('source_language'),
                    'target_language': properties.get('target_language'),
                    'page_count': int(properties.get('page_count', 1)),
                    'status': properties.get('status'),
                    'upload_timestamp': properties.get('upload_timestamp')
                }
                file_list.append(file_info)

            logging.info(f"Found {len(file_list)} files for customer {customer_email} with status {status}")
            return file_list

        except Exception as e:
            logging.error(f"Failed to search files by customer email: {e}")
            raise GoogleDriveError(f"Failed to search files: {e}")

    @handle_google_drive_exceptions("update file status")
    async def update_file_status(self, file_id: str, new_status: str, payment_intent_id: str = None) -> bool:
        """
        Update file status after payment confirmation.
        
        Args:
            file_id: Google Drive file ID
            new_status: New status (e.g., "payment_confirmed")
            payment_intent_id: Optional payment intent ID for tracking
            
        Returns:
            True if successful
            
        Raises:
            GoogleDriveError: If update fails
        """
        logging.info(f"Updating file status: {file_id} -> {new_status}")
        
        # Prepare metadata update
        metadata = {
            'properties': {
                'status': new_status,
                'payment_confirmed_at': datetime.utcnow().isoformat()
            }
        }
        
        if payment_intent_id:
            metadata['properties']['payment_intent_id'] = payment_intent_id
        
        # Update file properties
        await self.update_file_metadata(file_id, metadata)
        
        logging.info(f"Updated file {file_id} status to {new_status}")
        return True

    async def update_file_properties(self, file_id: str, properties: Dict[str, str]) -> bool:
        """
        Update file properties in Google Drive.

        Args:
            file_id: Google Drive file ID
            properties: Dictionary of properties to set

        Returns:
            True if successful

        Raises:
            GoogleDriveError: If update fails
        """
        try:
            logging.info(f"Updating file {file_id} properties")

            # Update the file properties with retry logic for SSL errors
            await self._update_file_metadata_with_retry(
                file_id=file_id,
                body={'properties': properties}
            )

            logging.info(f"File {file_id} properties updated successfully")
            return True

        except Exception as e:
            logging.error(f"Failed to update file {file_id} properties: {e}")
            raise GoogleDriveError(f"Failed to update file properties: {e}")

    @handle_google_drive_exceptions("clean trash folder")
    async def clean_trash_folder(self) -> Dict[str, Any]:
        """
        Clean all files from Trash folder if not empty.
        Called on a timer every hour.

        Returns:
            Dictionary with cleanup results including:
            - trash_was_empty: Whether trash was already empty
            - files_found: Number of files found in trash
            - files_deleted: Number of files successfully deleted
            - errors: List of any errors encountered

        Raises:
            GoogleDriveError: If cleanup fails critically
        """
        start_time = time.time()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        logging.info("=" * 80)
        logging.info(f"🗑️  TRASH CLEANUP STARTED at {timestamp}")
        logging.info("=" * 80)
        print(f"\n🗑️  TRASH CLEANUP STARTED at {timestamp}")

        try:
            # Query for all trashed files
            query = "trashed=true"

            # List all trashed files with retry logic
            results = await self._list_files_with_retry(
                query=query,
                fields='files(id,name,size,trashedTime,mimeType)'
            )

            files = results.get('files', [])
            files_count = len(files)

            # Check if trash is empty
            if files_count == 0:
                elapsed = time.time() - start_time
                logging.info(f"✅ TRASH FOLDER IS EMPTY - No cleanup needed")
                logging.info(f"⏱️  Cleanup check completed in {elapsed:.2f}s")
                logging.info("=" * 80)
                print(f"✅ TRASH FOLDER IS EMPTY - No cleanup needed (checked in {elapsed:.2f}s)")

                return {
                    'trash_was_empty': True,
                    'files_found': 0,
                    'files_deleted': 0,
                    'total_size_bytes': 0,
                    'errors': [],
                    'duration_seconds': elapsed
                }

            # Trash is not empty - proceed with deletion
            total_size = sum(int(f.get('size', 0)) for f in files if f.get('size'))
            total_size_mb = total_size / (1024 * 1024)

            logging.info(f"📊 TRASH STATISTICS:")
            logging.info(f"   Files found: {files_count}")
            logging.info(f"   Total size: {total_size_mb:.2f} MB ({total_size:,} bytes)")
            print(f"\n📊 Found {files_count} files in Trash ({total_size_mb:.2f} MB)")

            # Delete files one by one
            deleted_count = 0
            errors = []

            logging.info(f"\n🔥 DELETING {files_count} FILES FROM TRASH...")
            print(f"🔥 Deleting {files_count} files from Trash...")

            for index, file in enumerate(files, 1):
                file_id = file.get('id')
                file_name = file.get('name', 'Unknown')
                file_size = int(file.get('size', 0)) if file.get('size') else 0

                try:
                    # Permanently delete the file
                    await self._delete_file_with_retry(file_id)
                    deleted_count += 1

                    # Log progress every 10 files or for first/last file
                    if index == 1 or index == files_count or index % 10 == 0:
                        logging.info(f"   ✓ [{index}/{files_count}] Deleted: {file_name} ({file_size:,} bytes)")
                        print(f"   ✓ [{index}/{files_count}] Deleted: {file_name}")

                except Exception as e:
                    error_msg = f"Failed to delete {file_name} (ID: {file_id}): {str(e)}"
                    logging.warning(f"   ✗ [{index}/{files_count}] {error_msg}")
                    print(f"   ✗ [{index}/{files_count}] Failed: {file_name}")
                    errors.append(error_msg)

            # Final summary
            elapsed = time.time() - start_time
            success_rate = (deleted_count / files_count * 100) if files_count > 0 else 0

            logging.info("")
            logging.info(f"✅ TRASH CLEANUP COMPLETED")
            logging.info(f"   Files deleted: {deleted_count}/{files_count} ({success_rate:.1f}%)")
            logging.info(f"   Space freed: {total_size_mb:.2f} MB")
            logging.info(f"   Failed deletions: {len(errors)}")
            logging.info(f"⏱️  Total duration: {elapsed:.2f}s")
            logging.info("=" * 80)

            print(f"\n✅ TRASH CLEANUP COMPLETED:")
            print(f"   Deleted: {deleted_count}/{files_count} files ({success_rate:.1f}%)")
            print(f"   Space freed: {total_size_mb:.2f} MB")
            if errors:
                print(f"   ⚠️  Errors: {len(errors)}")
            print(f"   Duration: {elapsed:.2f}s\n")

            return {
                'trash_was_empty': False,
                'files_found': files_count,
                'files_deleted': deleted_count,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size_mb, 2),
                'errors': errors,
                'duration_seconds': round(elapsed, 2),
                'success_rate': round(success_rate, 1)
            }

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"Critical error during trash cleanup: {str(e)}"
            logging.error(f"❌ {error_msg}")
            logging.error(f"⏱️  Failed after {elapsed:.2f}s")
            logging.error("=" * 80)
            print(f"\n❌ TRASH CLEANUP FAILED: {str(e)}\n")
            raise GoogleDriveError(error_msg, original_error=e)

    @handle_google_drive_exceptions("get file by ID")
    async def get_file_by_id(self, file_id: str) -> Dict[str, Any]:
        """
        Get file information by Google Drive file ID (no searching).

        This method directly fetches a file by its ID, which is much faster and more
        accurate than searching. Used by payment confirmation to process only the
        specific files the user uploaded.

        Args:
            file_id: Google Drive file ID

        Returns:
            Dictionary with file information including:
            - file_id: Google Drive file ID
            - filename: File name
            - size: File size in bytes
            - customer_email: Customer email from properties
            - source_language: Source language from properties
            - target_language: Target language from properties
            - page_count: Page count from properties
            - status: File status from properties
            - upload_timestamp: Upload timestamp from properties
            - google_drive_url: Web view link
            - parents: Parent folder IDs

        Raises:
            GoogleDriveError: If file fetch fails or file not found
        """
        logging.info(f"Fetching file by ID: {file_id}")

        try:
            # Use retry logic for SSL errors
            file = await self._get_file_with_retry(
                file_id=file_id,
                fields='id,name,size,createdTime,webViewLink,mimeType,properties,parents'
            )

            properties = file.get('properties', {})

            file_info = {
                'file_id': file['id'],
                'filename': file['name'],
                'size': int(file.get('size', 0)) if file.get('size') else 0,
                'created_at': file.get('createdTime'),
                'google_drive_url': file.get('webViewLink'),
                'mime_type': file.get('mimeType'),
                'parents': file.get('parents', []),

                # Extract metadata from properties
                'customer_email': properties.get('customer_email'),
                'source_language': properties.get('source_language'),
                'target_language': properties.get('target_language'),
                'page_count': int(properties.get('page_count', 1)),
                'status': properties.get('status'),
                'upload_timestamp': properties.get('upload_timestamp')
            }

            logging.info(f"Successfully fetched file {file_id}: {file_info['filename']}")
            return file_info

        except Exception as e:
            logging.error(f"Failed to fetch file {file_id}: {e}")
            raise GoogleDriveError(f"Failed to fetch file by ID: {e}")


# Global Google Drive service instance - initialized lazily
_google_drive_service = None

def get_google_drive_service() -> GoogleDriveService:
    """Get or create the Google Drive service instance."""
    global _google_drive_service
    if _google_drive_service is None:
        _google_drive_service = GoogleDriveService()
    return _google_drive_service

class LazyGoogleDriveService:
    """Lazy proxy for Google Drive service."""
    
    def __getattr__(self, name):
        return getattr(get_google_drive_service(), name)

# For backward compatibility - lazy initialization
google_drive_service = LazyGoogleDriveService()