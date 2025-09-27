#!/usr/bin/env python3
"""
Test script to upload .md files to the correct IrisSolutions folder in danishevsky@gmail.com's Google Drive.
"""

import asyncio
import aiofiles
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_correct_google_drive_upload():
    """Test uploading .md files to the correct IrisSolutions folder."""
    
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
        # First, let's check what the service account can see
        print("🔍 Checking service account access to Google Drive...")
        
        # List all files/folders the service account can see
        try:
            results = google_drive_service.service.files().list(
                q="mimeType='application/vnd.google-apps.folder'",
                fields='files(id, name, owners)'
            ).execute()
            
            folders = results.get('files', [])
            print(f"Service account can see {len(folders)} folders:")
            for folder in folders[:10]:  # Show first 10
                owners = folder.get('owners', [])
                owner_emails = [owner.get('emailAddress', 'Unknown') for owner in owners]
                print(f"  - {folder['name']} (ID: {folder['id']}) - Owners: {', '.join(owner_emails)}")
            
        except Exception as e:
            print(f"❌ Service account access check failed: {e}")
            print("This means the service account cannot access your personal Google Drive.")
            print("\n💡 SOLUTION: You need to either:")
            print("   1. Share your IrisSolutions folder with the service account email:")
            print("      irissolutions-850@synologysafeaccess-320003.iam.gserviceaccount.com")
            print("   2. Or use OAuth credentials instead of service account")
            return None
        
        # Create folder structure in IrisSolutions
        print(f"Creating folder structure for {customer_email} in IrisSolutions...")
        folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
        print(f"Folder created/found with ID: {folder_id}")
        
        # Upload each file
        uploaded_files = []
        for md_file in md_files:
            print(f"\nUploading {md_file.name} to IrisSolutions folder...")
            
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
            print(f"✅ Uploaded {md_file.name} - File ID: {file_info['file_id']}")
            print(f"   Google Drive URL: {file_info.get('google_drive_url', 'N/A')}")
        
        print(f"\n🎉 Successfully uploaded {len(uploaded_files)} files to IrisSolutions!")
        
        # Verify the folder structure
        print(f"\n📂 Folder Path Structure:")
        print(f"   My Drive → IrisSolutions → {customer_email} → Temp")
        
        # Get folder information
        folder_info = await google_drive_service.get_folder_info(folder_id)
        print(f"\n📊 Folder Statistics:")
        print(f"   Total files: {folder_info['total_files']}")
        print(f"   Total size: {folder_info['total_size_mb']} MB")
        print(f"   Folder ID: {folder_info['folder_id']}")
        
        # Get the full folder path for verification
        try:
            # Get folder hierarchy
            current_folder = google_drive_service.service.files().get(
                fileId=folder_id,
                fields='id,name,parents'
            ).execute()
            
            customer_folder_id = current_folder.get('parents', [])[0] if current_folder.get('parents') else None
            if customer_folder_id:
                customer_folder = google_drive_service.service.files().get(
                    fileId=customer_folder_id,
                    fields='id,name,parents,webViewLink'
                ).execute()
                
                root_folder_id = customer_folder.get('parents', [])[0] if customer_folder.get('parents') else None
                if root_folder_id:
                    root_folder = google_drive_service.service.files().get(
                        fileId=root_folder_id,
                        fields='id,name,webViewLink'
                    ).execute()
                    
                    print(f"\n🔗 Access Links:")
                    print(f"   IrisSolutions folder: {root_folder.get('webViewLink', 'N/A')}")
                    print(f"   Customer folder: {customer_folder.get('webViewLink', 'N/A')}")
                    print(f"   Temp folder (files): https://drive.google.com/drive/folders/{folder_id}")
        
        except Exception as e:
            print(f"Could not get folder hierarchy: {e}")
        
        return uploaded_files
        
    except Exception as e:
        print(f"❌ Error during upload: {e}")
        logging.exception("Upload failed")
        
        if "insufficient permissions" in str(e).lower() or "access" in str(e).lower():
            print("\n💡 SOLUTION: The service account needs access to your Google Drive.")
            print("   Please share your 'IrisSolutions' folder with:")
            print("   irissolutions-850@synologysafeaccess-320003.iam.gserviceaccount.com")
            print("   with 'Editor' permissions.")
        
        raise

if __name__ == "__main__":
    print("🚀 Starting corrected Google Drive upload test...")
    result = asyncio.run(test_correct_google_drive_upload())
    if result:
        print(f"✅ Test completed successfully! Uploaded {len(result)} files to IrisSolutions.")