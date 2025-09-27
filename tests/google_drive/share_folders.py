#!/usr/bin/env python3
"""
Script to share Google Drive folders with a user email.
"""

import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

async def share_folders_with_user():
    """Share the Google Drive folders with the user's email."""
    
    from app.services.google_drive_service import google_drive_service
    
    # Import settings to get customer email from config
    from app.config import settings
    
    # The email to share with (replace with your actual email)
    your_email = settings.default_customer_email  # You can change this to your actual Google account email
    customer_email = settings.default_customer_email
    
    try:
        print(f"🔗 Sharing Google Drive folders with {your_email}...")
        
        # Get folder structure
        temp_folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
        
        # Get parent folders
        current_folder = google_drive_service.service.files().get(
            fileId=temp_folder_id,
            fields='id,name,parents'
        ).execute()
        
        customer_folder_id = current_folder.get('parents', [])[0]
        
        customer_folder = google_drive_service.service.files().get(
            fileId=customer_folder_id,
            fields='id,name,parents'
        ).execute()
        
        root_folder_id = customer_folder.get('parents', [])[0]
        
        # Share root folder (this will give access to all subfolders)
        folders_to_share = [
            (root_folder_id, "TranslatorWebServer (Root)"),
            (customer_folder_id, f"Customer folder ({customer_email})"),
            (temp_folder_id, "Temp folder (with files)")
        ]
        
        shared_links = []
        
        for folder_id, folder_name in folders_to_share:
            try:
                # Create permission for the user
                permission = {
                    'type': 'user',
                    'role': 'reader',  # or 'writer' if you want edit access
                    'emailAddress': your_email
                }
                
                # Share the folder
                google_drive_service.service.permissions().create(
                    fileId=folder_id,
                    body=permission,
                    fields='id'
                ).execute()
                
                # Get the shareable link
                folder_info = google_drive_service.service.files().get(
                    fileId=folder_id,
                    fields='webViewLink'
                ).execute()
                
                shared_links.append((folder_name, folder_info.get('webViewLink')))
                print(f"✅ Shared {folder_name}")
                
            except Exception as e:
                print(f"❌ Failed to share {folder_name}: {e}")
        
        print(f"\n🎉 Folders shared successfully with {your_email}!")
        print("\n📂 You can now access these folders:")
        print("=" * 60)
        
        for folder_name, link in shared_links:
            print(f"📁 {folder_name}")
            print(f"   Link: {link}")
            print()
        
        # Also share individual files
        files_in_folder = await google_drive_service.list_files_in_folder(temp_folder_id)
        print(f"📋 Sharing {len(files_in_folder)} individual files...")
        
        for file_info in files_in_folder:
            try:
                # Share each file
                permission = {
                    'type': 'user',
                    'role': 'reader',
                    'emailAddress': your_email
                }
                
                google_drive_service.service.permissions().create(
                    fileId=file_info['file_id'],
                    body=permission,
                    fields='id'
                ).execute()
                
                print(f"✅ Shared file: {file_info['filename']}")
                
            except Exception as e:
                print(f"❌ Failed to share file {file_info['filename']}: {e}")
        
        return shared_links
        
    except Exception as e:
        print(f"❌ Error sharing folders: {e}")
        logging.exception("Failed to share folders")
        raise

if __name__ == "__main__":
    print("🚀 Starting folder sharing process...")
    asyncio.run(share_folders_with_user())