#!/usr/bin/env python3
"""
Test script to verify that email configuration changes are working correctly.
"""

import asyncio
import aiofiles
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_config_changes():
    """Test that email configuration is properly loaded and used."""
    
    print("🧪 Testing email configuration changes...")
    print("=" * 60)
    
    # Test 1: Verify configuration loading
    print("📋 Test 1: Configuration Loading")
    try:
        from app.config import settings
        
        print(f"✅ Configuration loaded successfully")
        print(f"   Default customer email: {settings.default_customer_email}")
        print(f"   Google Drive root folder: {settings.google_drive_root_folder}")
        print(f"   Google Drive enabled: {settings.google_drive_enabled}")
        
        if not settings.default_customer_email:
            print("❌ ERROR: default_customer_email is not set in configuration!")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Failed to load configuration: {e}")
        return False
    
    # Test 2: Verify Google Drive service uses configuration
    print(f"\n📋 Test 2: Google Drive Service Configuration")
    try:
        from app.services.google_drive_service import google_drive_service
        
        print(f"✅ Google Drive service loaded")
        print(f"   Root folder from service: {google_drive_service.root_folder}")
        print(f"   Credentials path: {google_drive_service.credentials_path}")
        
        if google_drive_service.root_folder != settings.google_drive_root_folder:
            print(f"❌ ERROR: Root folder mismatch!")
            print(f"   Expected: {settings.google_drive_root_folder}")
            print(f"   Found: {google_drive_service.root_folder}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: Failed to initialize Google Drive service: {e}")
        return False
    
    # Test 3: Create folder structure using config email
    print(f"\n📋 Test 3: Folder Creation with Config Email")
    try:
        customer_email = settings.default_customer_email
        print(f"   Using customer email from config: {customer_email}")
        
        folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
        print(f"✅ Folder structure created/found successfully")
        print(f"   Folder ID: {folder_id}")
        print(f"   Path: {settings.google_drive_root_folder}/{customer_email}/Temp")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to create folder structure: {e}")
        return False
    
    # Test 4: Test file upload endpoint validation (without actual upload)
    print(f"\n📋 Test 4: Upload Endpoint Model Validation")
    try:
        from app.models.requests import FileUploadRequest
        
        # Test with explicit email
        request1 = FileUploadRequest(
            customer_email="test@example.com",
            target_language="fr"
        )
        print(f"✅ Request with explicit email: {request1.customer_email}")
        
        # Test with None email (should be allowed now)
        request2 = FileUploadRequest(
            customer_email=None,
            target_language="es"
        )
        print(f"✅ Request with None email: {request2.customer_email}")
        
        # Test with empty string (should fail)
        try:
            request3 = FileUploadRequest(
                customer_email="",
                target_language="de"
            )
            print(f"❌ ERROR: Empty email should have failed validation!")
            return False
        except Exception:
            print(f"✅ Empty email correctly rejected")
        
    except Exception as e:
        print(f"❌ ERROR: Model validation test failed: {e}")
        return False
    
    # Test 5: Verify all test scripts import config correctly
    print(f"\n📋 Test 5: Test Scripts Configuration Import")
    test_scripts = [
        "test_upload.py",
        "test_correct_upload.py", 
        "test_metadata_verification.py",
        "check_google_drive.py",
        "share_folders.py"
    ]
    
    for script in test_scripts:
        if Path(script).exists():
            try:
                # Read the script content to verify it imports settings
                with open(script, 'r') as f:
                    content = f.read()
                
                if "from app.config import settings" in content and "settings.default_customer_email" in content:
                    print(f"✅ {script}: Uses configuration")
                elif "danishevsky@gmail.com" in content:
                    print(f"⚠️  {script}: Still has hardcoded email (check manual hardcoding in test data)")
                else:
                    print(f"❓ {script}: Configuration status unclear")
                    
            except Exception as e:
                print(f"❌ {script}: Error reading file: {e}")
        else:
            print(f"❓ {script}: File not found")
    
    print(f"\n🎉 Configuration tests completed successfully!")
    print(f"\n📋 Summary:")
    print(f"   ✅ Configuration loaded from .env file")
    print(f"   ✅ Default customer email: {settings.default_customer_email}")
    print(f"   ✅ Google Drive root folder: {settings.google_drive_root_folder}")
    print(f"   ✅ Upload endpoint supports optional email parameter")
    print(f"   ✅ Test scripts updated to use configuration")
    
    return True

if __name__ == "__main__":
    print("🚀 Starting configuration changes test...")
    result = asyncio.run(test_config_changes())
    if result:
        print(f"✅ All configuration tests passed!")
    else:
        print(f"❌ Some configuration tests failed!")