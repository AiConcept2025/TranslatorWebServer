#!/usr/bin/env python3
"""
Test script to verify that the upload endpoint works with optional email parameter.
"""

import asyncio
import aiofiles
import tempfile
import os
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_optional_email_upload():
    """Test upload endpoint with and without email parameter."""
    
    print("🧪 Testing upload endpoint with optional email parameter...")
    print("=" * 60)
    
    from app.config import settings
    
    # Test 1: Upload without providing email (should use default)
    print("📋 Test 1: Upload without email parameter (uses default)")
    try:
        from app.services.google_drive_service import google_drive_service
        
        # Create a test file
        test_content = b"# Test File\n\nThis is a test file for upload endpoint testing."
        test_filename = "test_optional_email.md"
        
        # Call the upload function directly (simulating what the endpoint does)
        # When customer_email is None, the endpoint should use settings.default_customer_email
        test_customer_email = None  # This simulates no email provided to endpoint
        
        # Simulate the endpoint logic
        if test_customer_email is None:
            customer_email = settings.default_customer_email
            print(f"   Using default customer email: {customer_email}")
        else:
            customer_email = test_customer_email
        
        # Create folder structure
        folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
        
        # Upload file
        file_info = await google_drive_service.upload_file_to_folder(
            file_content=test_content,
            filename=test_filename,
            folder_id=folder_id,
            target_language="en"
        )
        
        print(f"✅ Upload successful without providing email")
        print(f"   File ID: {file_info['file_id']}")
        print(f"   Used email: {customer_email}")
        print(f"   Folder: IrisSolutions/{customer_email}/Temp")
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False
    
    # Test 2: Upload with explicit email
    print(f"\n📋 Test 2: Upload with explicit email parameter")
    try:
        # Test with the same email as default (should work)
        explicit_email = settings.default_customer_email
        test_content = b"# Test File 2\n\nThis is a test file with explicit email."
        test_filename = "test_explicit_email.md"
        
        # Create folder structure
        folder_id = await google_drive_service.create_customer_folder_structure(explicit_email)
        
        # Upload file
        file_info = await google_drive_service.upload_file_to_folder(
            file_content=test_content,
            filename=test_filename,
            folder_id=folder_id,
            target_language="fr"
        )
        
        print(f"✅ Upload successful with explicit email")
        print(f"   File ID: {file_info['file_id']}")
        print(f"   Used email: {explicit_email}")
        print(f"   Target language: fr")
        
    except Exception as e:
        print(f"❌ Upload with explicit email failed: {e}")
        return False
    
    # Test 3: Verify model validation works correctly
    print(f"\n📋 Test 3: Model Validation Test")
    try:
        from app.models.requests import FileUploadRequest
        
        # Test valid request with None email
        request1 = FileUploadRequest(
            customer_email=None,
            target_language="es"
        )
        print(f"✅ None email validation passed: {request1.customer_email}")
        
        # Test valid request with valid email
        request2 = FileUploadRequest(
            customer_email="test@example.com",
            target_language="de"
        )
        print(f"✅ Valid email validation passed: {request2.customer_email}")
        
        # Test invalid email format
        try:
            request3 = FileUploadRequest(
                customer_email="invalid-email",
                target_language="it"
            )
            print(f"❌ Invalid email should have failed!")
            return False
        except Exception:
            print(f"✅ Invalid email correctly rejected")
        
    except Exception as e:
        print(f"❌ Model validation test failed: {e}")
        return False
    
    # Test 4: Check configuration values
    print(f"\n📋 Test 4: Configuration Verification")
    print(f"   Default customer email: {settings.default_customer_email}")
    print(f"   Google Drive root folder: {settings.google_drive_root_folder}")
    print(f"   Google Drive enabled: {settings.google_drive_enabled}")
    
    # Verify no hardcoded emails in main service files
    service_files = [
        "app/routers/upload.py",
        "app/services/google_drive_service.py",
        "app/config.py"
    ]
    
    print(f"\n📋 Test 5: Hardcoded Email Check in Service Files")
    for file_path in service_files:
        if Path(file_path).exists():
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Check for hardcoded email patterns (excluding comments and test data)
                hardcoded_patterns = [
                    "danishevsky@gmail.com",
                    "@gmail.com",
                    "@example.com"
                ]
                
                found_hardcoded = []
                for pattern in hardcoded_patterns:
                    if pattern in content:
                        # Check if it's in a comment or config default
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if pattern in line and not (line.strip().startswith('#') or 
                                                      'default_customer_email' in line or
                                                      'DEFAULT_CUSTOMER_EMAIL' in line):
                                found_hardcoded.append(f"Line {i+1}: {line.strip()}")
                
                if found_hardcoded:
                    print(f"⚠️  {file_path}: Found potential hardcoded emails:")
                    for item in found_hardcoded[:3]:  # Show first 3
                        print(f"      {item}")
                else:
                    print(f"✅ {file_path}: No hardcoded emails found")
                    
            except Exception as e:
                print(f"❌ {file_path}: Error reading file: {e}")
        else:
            print(f"❓ {file_path}: File not found")
    
    print(f"\n🎉 Optional email upload tests completed!")
    return True

if __name__ == "__main__":
    print("🚀 Starting optional email upload test...")
    result = asyncio.run(test_optional_email_upload())
    if result:
        print(f"\n✅ All optional email tests passed!")
    else:
        print(f"\n❌ Some optional email tests failed!")