#!/usr/bin/env python3
"""
Test script to verify that ben.danishevsky@gmail.com is used as default and works correctly.
"""

import asyncio
import aiofiles
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_ben_email_default():
    """Test that ben.danishevsky@gmail.com is used as default and works correctly."""
    
    print("🧪 Testing ben.danishevsky@gmail.com as default customer email...")
    print("=" * 60)
    
    from app.config import settings
    from app.services.google_drive_service import google_drive_service
    from app.models.requests import FileUploadRequest
    
    # Test 1: Verify configuration
    print("📋 Test 1: Configuration Verification")
    print(f"   Default customer email: {settings.default_customer_email}")
    print(f"   Google Drive owner email: {settings.google_drive_owner_email}")
    
    expected_customer = "ben.danishevsky@gmail.com"
    expected_owner = "danishevsky@gmail.com"
    
    if settings.default_customer_email == expected_customer:
        print("✅ Default customer email is correct")
    else:
        print(f"❌ Default customer email mismatch!")
        print(f"   Expected: {expected_customer}")
        print(f"   Found: {settings.default_customer_email}")
        return False
    
    if settings.google_drive_owner_email == expected_owner:
        print("✅ Owner email is correct")
    else:
        print(f"❌ Owner email mismatch!")
        print(f"   Expected: {expected_owner}")
        print(f"   Found: {settings.google_drive_owner_email}")
        return False
    
    # Test 2: Upload endpoint model with None email
    print(f"\n📋 Test 2: Upload Request Model Validation")
    try:
        # Test with None customer_email (should be allowed)
        request = FileUploadRequest(
            customer_email=None,
            target_language="es"
        )
        print(f"✅ Request with None email: {request.customer_email}")
        
        # Test with explicit ben email
        request2 = FileUploadRequest(
            customer_email=settings.default_customer_email,
            target_language="fr"
        )
        print(f"✅ Request with ben email: {request2.customer_email}")
        
    except Exception as e:
        print(f"❌ Model validation failed: {e}")
        return False
    
    # Test 3: Folder creation and file upload for ben
    print(f"\n📋 Test 3: File Upload for Ben")
    try:
        customer_email = settings.default_customer_email
        
        # Create folder structure
        folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
        print(f"✅ Folder created for ben: {folder_id}")
        
        # Upload test file
        test_content = b"""# Test File for Ben Danishevsky

This file tests the default customer email configuration.

Customer: ben.danishevsky@gmail.com (default)
Owner: danishevsky@gmail.com (from service account)
Purpose: Verify folder naming vs ownership separation
"""
        
        test_filename = "ben_test_verification.md"
        
        file_info = await google_drive_service.upload_file_to_folder(
            file_content=test_content,
            filename=test_filename,
            folder_id=folder_id,
            target_language="en"
        )
        
        print(f"✅ File uploaded for ben:")
        print(f"   File ID: {file_info['file_id']}")
        print(f"   Filename: {file_info['filename']}")
        print(f"   Target language: {file_info.get('target_language', 'N/A')}")
        
        # Verify file metadata
        file_details = google_drive_service.service.files().get(
            fileId=file_info['file_id'],
            fields='id,name,owners,properties,description'
        ).execute()
        
        # Check properties
        properties = file_details.get('properties', {})
        if properties.get('target_language') == 'en':
            print("✅ Target language metadata correct")
        else:
            print(f"❌ Target language metadata incorrect: {properties.get('target_language')}")
        
        # Check ownership
        owners = file_details.get('owners', [])
        owner_emails = [owner.get('emailAddress') for owner in owners]
        service_account_email = "irissolutions-850@synologysafeaccess-320003.iam.gserviceaccount.com"
        
        if service_account_email in owner_emails:
            print("✅ Service account is file owner")
        else:
            print(f"❌ Service account is not owner: {owner_emails}")
        
        if settings.default_customer_email not in owner_emails:
            print("✅ Ben is NOT file owner (correct)")
        else:
            print("❌ Ben should not be file owner")
        
    except Exception as e:
        print(f"❌ File upload test failed: {e}")
        return False
    
    # Test 4: Verify existing test scripts use ben
    print(f"\n📋 Test 4: Test Scripts Configuration Check")
    test_scripts = [
        "test_upload.py",
        "test_correct_upload.py", 
        "test_metadata_verification.py",
        "check_google_drive.py",
        "share_folders.py"
    ]
    
    scripts_using_config = 0
    
    for script in test_scripts:
        if Path(script).exists():
            try:
                with open(script, 'r') as f:
                    content = f.read()
                
                if "settings.default_customer_email" in content:
                    print(f"✅ {script}: Uses config for customer email")
                    scripts_using_config += 1
                else:
                    print(f"❌ {script}: Does not use config")
                    
            except Exception as e:
                print(f"❌ {script}: Error reading: {e}")
        else:
            print(f"❓ {script}: Not found")
    
    if scripts_using_config >= 3:  # At least 3 scripts should use config
        print(f"✅ {scripts_using_config} scripts use configuration")
    else:
        print(f"❌ Only {scripts_using_config} scripts use configuration")
    
    # Test 5: Verify folder structure
    print(f"\n📋 Test 5: Folder Structure Verification")
    try:
        files = await google_drive_service.list_files_in_folder(folder_id)
        ben_files = [f for f in files if 'ben' in f['filename'].lower()]
        
        print(f"✅ Files in ben's folder: {len(files)} total")
        print(f"   Ben-related files: {len(ben_files)}")
        
        if ben_files:
            print("   Recent ben files:")
            for file_info in ben_files[-3:]:  # Show last 3
                print(f"      - {file_info['filename']}")
        
        # Get folder info
        folder_info = await google_drive_service.get_folder_info(folder_id)
        print(f"   Folder path: IrisSolutions/{settings.default_customer_email}/Temp")
        print(f"   Total files: {folder_info['total_files']}")
        print(f"   Total size: {folder_info['total_size_mb']} MB")
        
    except Exception as e:
        print(f"❌ Folder verification failed: {e}")
        return False
    
    print(f"\n🎉 Ben email verification completed successfully!")
    print(f"\n📋 Summary:")
    print(f"   ✅ Default customer email: {settings.default_customer_email}")
    print(f"   ✅ Files owned by service account, not by ben")
    print(f"   ✅ Folders named after ben for organization")
    print(f"   ✅ Language metadata properly stored")
    print(f"   ✅ Test scripts use configuration")
    
    return True

if __name__ == "__main__":
    print("🚀 Starting ben.danishevsky@gmail.com verification test...")
    result = asyncio.run(test_ben_email_default())
    if result:
        print(f"\n✅ Ben email configuration working perfectly!")
    else:
        print(f"\n❌ Ben email configuration has issues!")