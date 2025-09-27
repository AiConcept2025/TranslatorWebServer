#!/usr/bin/env python3
"""
Script to check Google Drive folder structure and provide links.
"""

import asyncio
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

async def check_google_drive_structure():
    """Check Google Drive folder structure and provide links."""
    
    from app.services.google_drive_service import google_drive_service
    
    # Import settings to get customer email from config
    from app.config import settings
    customer_email = settings.default_customer_email
    
    try:
        print("🔍 Checking Google Drive folder structure...")
        
        # Get the folder structure
        folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
        print(f"📁 Target folder ID: {folder_id}")
        
        # Get folder information with details
        folder_info = await google_drive_service.get_folder_info(folder_id)
        print(f"\n📊 Folder Information:")
        print(f"   Folder ID: {folder_info['folder_id']}")
        print(f"   Folder Name: {folder_info.get('folder_name', 'Unknown')}")
        print(f"   Total Files: {folder_info['total_files']}")
        print(f"   Total Size: {folder_info['total_size_mb']} MB")
        
        # Get the actual folder details to show the path
        try:
            # Get root folder details
            root_folder = google_drive_service.service.files().get(
                fileId=google_drive_service.root_folder_id if hasattr(google_drive_service, 'root_folder_id') else None,
                fields='id,name,webViewLink'
            ).execute()
            print(f"\n🌐 Root Folder: {root_folder.get('name', 'TranslatorWebServer')}")
            print(f"   Link: {root_folder.get('webViewLink', 'N/A')}")
        except:
            print(f"\n🌐 Root Folder: TranslatorWebServer")
        
        # Get current folder link
        try:
            current_folder = google_drive_service.service.files().get(
                fileId=folder_id,
                fields='id,name,webViewLink,parents'
            ).execute()
            
            folder_link = current_folder.get('webViewLink')
            if folder_link:
                print(f"\n📂 Direct link to Temp folder:")
                print(f"   {folder_link}")
            
            # Try to get parent folder info
            parents = current_folder.get('parents', [])
            if parents:
                parent_folder = google_drive_service.service.files().get(
                    fileId=parents[0],
                    fields='id,name,webViewLink,parents'
                ).execute()
                print(f"\n📂 Customer folder ({customer_email}):")
                print(f"   Link: {parent_folder.get('webViewLink', 'N/A')}")
                
                # Get grandparent (root) if exists
                grandparents = parent_folder.get('parents', [])
                if grandparents:
                    root_folder = google_drive_service.service.files().get(
                        fileId=grandparents[0],
                        fields='id,name,webViewLink'
                    ).execute()
                    print(f"\n📂 Root folder ({root_folder.get('name')}):")
                    print(f"   Link: {root_folder.get('webViewLink', 'N/A')}")
        except Exception as e:
            print(f"   Could not get folder link: {e}")
        
        # List all files with their direct links
        files_in_folder = await google_drive_service.list_files_in_folder(folder_id)
        
        if files_in_folder:
            print(f"\n📋 Files in folder (Total: {len(files_in_folder)}):")
            print("=" * 60)
            
            for i, file_info in enumerate(files_in_folder, 1):
                print(f"{i}. {file_info['filename']}")
                print(f"   File ID: {file_info['file_id']}")
                print(f"   Size: {file_info.get('size', 0)} bytes")
                if file_info.get('google_drive_url'):
                    print(f"   Direct Link: {file_info['google_drive_url']}")
                print()
        else:
            print("\n❌ No files found in the folder!")
        
        # Print the folder path structure
        print("\n🗂️  Folder Path Structure:")
        print(f"   My Drive → TranslatorWebServer → {customer_email} → Temp")
        print(f"   All {len(files_in_folder)} .md files should be in the Temp folder")
        
        return folder_id, files_in_folder
        
    except Exception as e:
        print(f"❌ Error checking Google Drive: {e}")
        logging.exception("Failed to check Google Drive")
        raise

if __name__ == "__main__":
    print("🚀 Checking Google Drive folder structure and links...")
    asyncio.run(check_google_drive_structure())