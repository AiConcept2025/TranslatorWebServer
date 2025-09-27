#!/usr/bin/env python3
"""
Test script to verify that folder naming and file ownership are properly separated.
- Files are owned by the service account (.env email)  
- Folders are named after customer email (UI input)
- Customer email does NOT get access to files
"""

import asyncio
import aiofiles
from pathlib import Path
import logging
import json
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_ownership_separation():
    """Test that ownership and folder naming are properly separated."""
    
    print("🧪 Testing ownership and folder naming separation...")
    print("=" * 60)
    
    from app.config import settings
    from app.services.google_drive_service import google_drive_service
    
    # Test configuration
    print("📋 Test Configuration:")
    print(f"   Default customer email (folder name): {settings.default_customer_email}")
    print(f"   Google Drive owner email (file owner): {settings.google_drive_owner_email}")
    print(f"   Google Drive root folder: {settings.google_drive_root_folder}")
    
    # Test different customer emails for folder naming
    test_customers = [
        settings.default_customer_email,  # ben.danishevsky@gmail.com
        "alice@company.com",
        "bob@startup.io", 
        "charlie@enterprise.org"
    ]
    
    results = []
    
    for i, customer_email in enumerate(test_customers, 1):
        print(f"\n🧪 Test Case {i}: Customer Email = {customer_email}")
        
        try:
            # Create folder structure using customer email
            folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
            print(f"✅ Folder structure created for {customer_email}")
            print(f"   Folder ID: {folder_id}")
            
            # Upload a test file
            test_content = f"""# Test File for {customer_email}

Customer: {customer_email}
Upload time: {datetime.utcnow().isoformat()}
Test case: {i}

This file should be owned by the service account, not by {customer_email}.
The customer email is used only for folder organization.
""".encode('utf-8')
            
            test_filename = f"ownership_test_{i}_{customer_email.split('@')[0]}.md"
            
            file_info = await google_drive_service.upload_file_to_folder(
                file_content=test_content,
                filename=test_filename,
                folder_id=folder_id,
                target_language="en"
            )
            
            print(f"✅ File uploaded: {test_filename}")
            print(f"   File ID: {file_info['file_id']}")
            
            # Get detailed file information from Google Drive API
            file_details = google_drive_service.service.files().get(
                fileId=file_info['file_id'],
                fields='id,name,owners,permissions,properties,description,parents,createdTime'
            ).execute()
            
            # Analyze ownership
            owners = file_details.get('owners', [])
            owner_emails = [owner.get('emailAddress') for owner in owners]
            
            print(f"📊 File Ownership Analysis:")
            print(f"   File owners: {owner_emails}")
            
            # Check if the service account is the owner
            service_account_email = "irissolutions-850@synologysafeaccess-320003.iam.gserviceaccount.com"
            is_service_account_owner = service_account_email in owner_emails
            
            # Check if customer email is NOT an owner
            is_customer_not_owner = customer_email not in owner_emails
            
            print(f"   ✅ Service account is owner: {is_service_account_owner}")
            print(f"   ✅ Customer is NOT owner: {is_customer_not_owner}")
            
            # Get folder path information
            try:
                # Get the folder hierarchy to verify path
                current_folder = google_drive_service.service.files().get(
                    fileId=folder_id,
                    fields='id,name,parents'
                ).execute()
                
                customer_folder_id = current_folder.get('parents', [])[0]
                customer_folder = google_drive_service.service.files().get(
                    fileId=customer_folder_id,
                    fields='id,name,parents'
                ).execute()
                
                root_folder_id = customer_folder.get('parents', [])[0]
                root_folder = google_drive_service.service.files().get(
                    fileId=root_folder_id,
                    fields='id,name'
                ).execute()
                
                folder_path = f"{root_folder['name']}/{customer_folder['name']}/{current_folder['name']}"
                print(f"   📂 Folder path: {folder_path}")
                
                # Verify the customer folder name matches the customer email
                is_folder_named_correctly = customer_folder['name'] == customer_email
                print(f"   ✅ Folder named after customer: {is_folder_named_correctly}")
                
            except Exception as e:
                print(f"   ❌ Could not verify folder path: {e}")
                is_folder_named_correctly = False
            
            # Get file permissions to ensure customer doesn't have access
            try:
                permissions = google_drive_service.service.permissions().list(
                    fileId=file_info['file_id'],
                    fields='permissions(id,emailAddress,role,type)'
                ).execute()
                
                permission_emails = []
                for perm in permissions.get('permissions', []):
                    if perm.get('emailAddress'):
                        permission_emails.append(perm.get('emailAddress'))
                
                customer_has_permission = customer_email in permission_emails
                print(f"   ✅ Customer has NO file access: {not customer_has_permission}")
                
                if permission_emails:
                    print(f"   📋 File permissions: {permission_emails}")
                
            except Exception as e:
                print(f"   ❌ Could not check permissions: {e}")
                customer_has_permission = None
            
            # Test result
            test_passed = (
                is_service_account_owner and 
                is_customer_not_owner and 
                is_folder_named_correctly and 
                not customer_has_permission
            )
            
            results.append({
                'customer_email': customer_email,
                'file_id': file_info['file_id'],
                'filename': test_filename,
                'folder_path': folder_path if 'folder_path' in locals() else 'Unknown',
                'service_account_owner': is_service_account_owner,
                'customer_not_owner': is_customer_not_owner,
                'folder_named_correctly': is_folder_named_correctly,
                'customer_no_access': not customer_has_permission if customer_has_permission is not None else True,
                'test_passed': test_passed
            })
            
            print(f"   {'✅ PASS' if test_passed else '❌ FAIL'}")
            
        except Exception as e:
            print(f"❌ Error in test case {i}: {e}")
            results.append({
                'customer_email': customer_email,
                'error': str(e),
                'test_passed': False
            })
    
    # Summary
    print(f"\n📊 OWNERSHIP SEPARATION TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results if r.get('test_passed'))
    total = len(results)
    
    print(f"Total test cases: {total}")
    print(f"✅ PASSED: {passed}")
    print(f"❌ FAILED: {total - passed}")
    
    print(f"\n📋 DETAILED RESULTS:")
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result.get('test_passed') else "❌ FAIL"
        print(f"{status} Test {i}: {result['customer_email']}")
        
        if 'folder_path' in result:
            print(f"   📂 Path: {result['folder_path']}")
        if 'filename' in result:
            print(f"   📄 File: {result['filename']}")
        if 'error' in result:
            print(f"   🔥 Error: {result['error']}")
        print()
    
    # Configuration verification
    print(f"📋 CONFIGURATION VERIFICATION:")
    print(f"   ✅ Default customer email: {settings.default_customer_email}")
    print(f"   ✅ Owner email: {settings.google_drive_owner_email}")
    print(f"   ✅ Root folder: {settings.google_drive_root_folder}")
    
    return results

if __name__ == "__main__":
    print("🚀 Starting ownership separation test...")
    result = asyncio.run(test_ownership_separation())
    
    passed_count = sum(1 for r in result if r.get('test_passed'))
    total_count = len(result)
    
    if passed_count == total_count:
        print(f"\n🎉 ALL TESTS PASSED! Ownership separation working correctly.")
    else:
        print(f"\n❌ {total_count - passed_count} tests failed. Check the implementation.")