#!/usr/bin/env python3
"""
Test script to upload .md files to Google Drive using the upload service.
"""

import asyncio
import aiofiles
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_google_drive_upload():
    """Test uploading .md files to Google Drive."""
    
    # Import the Google Drive service
    from app.services.google_drive_service import google_drive_service
    
    # Import settings to get customer email from config
    from app.config import settings
    customer_email = settings.default_customer_email
    target_language = "es"  # Spanish for testing
    
    # Get all .md files
    md_files = list(Path(".").glob("*.md"))
    print(f"Found {len(md_files)} .md files to upload")
    
    try:
        # Create folder structure
        print(f"Creating folder structure for {customer_email}...")
        folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
        print(f"Folder created/found with ID: {folder_id}")
        
        # Upload each file
        uploaded_files = []
        for md_file in md_files:
            print(f"\nUploading {md_file.name}...")
            
            # Read file content
            async with aiofiles.open(md_file, 'rb') as f:
                file_content = await f.read()
            
            # Upload to Google Drive
            file_info = await google_drive_service.upload_file_to_folder(
                file_content=file_content,
                filename=md_file.name,
                folder_id=folder_id,
                target_language=target_language
            )
            
            uploaded_files.append(file_info)
            print(f"✓ Uploaded {md_file.name} - File ID: {file_info['file_id']}")
            print(f"  Google Drive URL: {file_info.get('google_drive_url', 'N/A')}")
        
        print(f"\n✅ Successfully uploaded {len(uploaded_files)} files!")
        
        # List files in the folder to verify
        print(f"\nVerifying files in folder {folder_id}...")
        files_in_folder = await google_drive_service.list_files_in_folder(folder_id)
        print(f"Found {len(files_in_folder)} files in the folder:")
        for file_info in files_in_folder:
            print(f"  - {file_info['filename']} (ID: {file_info['file_id']})")
        
        # Get folder information
        folder_info = await google_drive_service.get_folder_info(folder_id)
        print(f"\nFolder statistics:")
        print(f"  Total files: {folder_info['total_files']}")
        print(f"  Total size: {folder_info['total_size_mb']} MB")
        
        return uploaded_files
        
    except Exception as e:
        print(f"❌ Error during upload: {e}")
        logging.exception("Upload failed")
        raise

if __name__ == "__main__":
    print("🚀 Starting Google Drive upload test...")
    result = asyncio.run(test_google_drive_upload())
    print(f"✅ Test completed successfully! Uploaded {len(result)} files.")