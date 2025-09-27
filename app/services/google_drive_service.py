"""
Google Drive service for folder management and file operations.
No local storage fallback - Google Drive only.
"""

import os
import io
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime

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
    async def create_customer_folder_structure(self, customer_email: str) -> str:
        """
        Create folder structure for customer: {customer_email}/Temp/
        
        Note: customer_email is used ONLY for folder naming/organization.
        All files are owned by the service account (google_drive_owner_email).
        The customer_email does NOT get access to the files.
        
        Args:
            customer_email: Customer's email address (used for folder name only)
            
        Returns:
            Folder ID of the Temp folder where files should be uploaded
            
        Raises:
            GoogleDriveError: If folder creation fails
        """
        logging.info(f"Creating Google Drive folder structure for: {customer_email}")
        
        # Find or create root folder
        root_folder_id = await self._find_or_create_folder(self.root_folder, None)
        logging.info(f"Root folder ID: {root_folder_id}")
        
        # Find or create customer folder
        customer_folder_id = await self._find_or_create_folder(customer_email, root_folder_id)
        logging.info(f"Customer folder ID: {customer_folder_id}")
        
        # Find or create Temp folder
        temp_folder_id = await self._find_or_create_folder("Temp", customer_folder_id)
        logging.info(f"Temp folder ID: {temp_folder_id}")
        
        return temp_folder_id
    
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
        
        # Upload file
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,size,createdTime,webViewLink,parents'
        ).execute()
        
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
            self.service.files().update(
                fileId=file_id,
                body=body
            ).execute()
            
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
        
        results = self.service.files().list(
            q=query,
            fields='files(id,name,size,createdTime,webViewLink,mimeType,properties)'
        ).execute()
        
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
        
        self.service.files().delete(fileId=file_id).execute()
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
            folder_details = self.service.files().get(
                fileId=folder_id,
                fields='name,createdTime,modifiedTime'
            ).execute()
            
            folder_info.update({
                'folder_name': folder_details.get('name'),
                'created_at': folder_details.get('createdTime'),
                'modified_at': folder_details.get('modifiedTime')
            })
        except Exception as e:
            logging.warning(f"Could not get folder details: {e}")
        
        logging.info(f"Folder info: {folder_info['total_files']} files, {folder_info['total_size_mb']}MB")
        return folder_info
    
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
        
        folder = self.service.files().create(
            body=file_metadata,
            fields='id'
        ).execute()
        
        folder_id = folder.get('id')
        logging.info(f"Created Google Drive folder '{name}': {folder_id}")
        return folder_id
    
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
        
        results = self.service.files().list(
            q=query,
            fields='files(id, name)'
        ).execute()
        
        files = results.get('files', [])
        if files:
            folder_id = files[0]['id']
            logging.info(f"Found Google Drive folder '{name}': {folder_id}")
            return folder_id
        
        logging.info(f"Folder '{name}' not found")
        return None


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