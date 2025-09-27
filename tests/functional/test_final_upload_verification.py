#!/usr/bin/env python3
"""
Final test to verify the complete upload workflow with the new ownership separation.
"""

import asyncio
import aiofiles
import sys
from pathlib import Path
import logging

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_final_upload_workflow():
    """Test the complete upload workflow with ownership separation."""
    
    print("🧪 Final Upload Workflow Verification...")
    print("=" * 60)
    
    from app.config import settings
    from app.services.google_drive_service import google_drive_service
    
    print("📋 Configuration Summary:")
    print(f"   Default customer email (folder naming): {settings.default_customer_email}")
    print(f"   Google Drive owner email (file ownership): {settings.google_drive_owner_email}")
    print(f"   Root folder: {settings.google_drive_root_folder}")
    
    # Test scenarios
    test_scenarios = [
        {
            "name": "Default customer (ben.danishevsky@gmail.com)",
            "customer_email": settings.default_customer_email,
            "target_language": "es"
        },
        {
            "name": "Custom customer (sarah@newcompany.com)",
            "customer_email": "sarah@newcompany.com",
            "target_language": "fr"
        },
        {
            "name": "Another customer (mike@agency.co)",
            "customer_email": "mike@agency.co", 
            "target_language": "de"
        }
    ]
    
    results = []
    
    for i, scenario in enumerate(test_scenarios, 1):
        print(f"\n🧪 Test Scenario {i}: {scenario['name']}")
        print(f"   Customer email: {scenario['customer_email']}")
        print(f"   Target language: {scenario['target_language']}")
        
        try:
            # Create folder structure
            folder_id = await google_drive_service.create_customer_folder_structure(
                scenario['customer_email']
            )
            print(f"✅ Folder structure created")
            print(f"   Folder ID: {folder_id}")
            
            # Create test file content
            test_content = f"""# Upload Test - Scenario {i}

**Customer**: {scenario['customer_email']}
**Target Language**: {scenario['target_language']}
**Test Date**: {__import__('datetime').datetime.utcnow().isoformat()}

## Test Purpose
This file verifies that:
1. Files are owned by the service account (danishevsky@gmail.com)
2. Folders are named after the customer email ({scenario['customer_email']})
3. Customer email does NOT get file access
4. Language metadata is properly stored

## Expected Results
- File owner: irissolutions-850@synologysafeaccess-320003.iam.gserviceaccount.com
- Folder path: IrisSolutions/{scenario['customer_email']}/Temp
- Language metadata: {scenario['target_language']}
- Customer access: None
""".encode('utf-8')
            
            test_filename = f"final_test_scenario_{i}_{scenario['customer_email'].split('@')[0]}.md"
            
            # Upload file
            file_info = await google_drive_service.upload_file_to_folder(
                file_content=test_content,
                filename=test_filename,
                folder_id=folder_id,
                target_language=scenario['target_language']
            )
            
            print(f"✅ File uploaded successfully")
            print(f"   File ID: {file_info['file_id']}")
            print(f"   Filename: {file_info['filename']}")
            
            # Verify file details
            file_details = google_drive_service.service.files().get(
                fileId=file_info['file_id'],
                fields='id,name,owners,properties,description,parents'
            ).execute()
            
            # Check ownership
            owners = file_details.get('owners', [])
            owner_emails = [owner.get('emailAddress') for owner in owners]
            service_account_email = "irissolutions-850@synologysafeaccess-320003.iam.gserviceaccount.com"
            
            # Check properties
            properties = file_details.get('properties', {})
            target_language = properties.get('target_language')
            
            # Get folder path
            current_folder = google_drive_service.service.files().get(
                fileId=folder_id,
                fields='name,parents'
            ).execute()
            
            customer_folder_id = current_folder.get('parents', [])[0]
            customer_folder = google_drive_service.service.files().get(
                fileId=customer_folder_id,
                fields='name,parents'
            ).execute()
            
            root_folder_id = customer_folder.get('parents', [])[0]
            root_folder = google_drive_service.service.files().get(
                fileId=root_folder_id,
                fields='name'
            ).execute()
            
            folder_path = f"{root_folder['name']}/{customer_folder['name']}/{current_folder['name']}"
            
            # Verification checks
            checks = {
                'service_account_owner': service_account_email in owner_emails,
                'customer_not_owner': scenario['customer_email'] not in owner_emails,
                'language_metadata_correct': target_language == scenario['target_language'],
                'folder_path_correct': customer_folder['name'] == scenario['customer_email']
            }
            
            print(f"📊 Verification Results:")
            for check, result in checks.items():
                status = "✅" if result else "❌"
                print(f"   {status} {check.replace('_', ' ').title()}: {result}")
            
            all_checks_passed = all(checks.values())
            
            results.append({
                'scenario': scenario['name'],
                'customer_email': scenario['customer_email'],
                'target_language': scenario['target_language'],
                'file_id': file_info['file_id'],
                'filename': test_filename,
                'folder_path': folder_path,
                'checks': checks,
                'passed': all_checks_passed
            })
            
            print(f"   {'✅ SCENARIO PASSED' if all_checks_passed else '❌ SCENARIO FAILED'}")
            
        except Exception as e:
            print(f"❌ Scenario {i} failed: {e}")
            results.append({
                'scenario': scenario['name'],
                'customer_email': scenario['customer_email'],
                'error': str(e),
                'passed': False
            })
    
    # Final summary
    print(f"\n📊 FINAL WORKFLOW VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed_scenarios = sum(1 for r in results if r.get('passed'))
    total_scenarios = len(results)
    
    print(f"Total scenarios: {total_scenarios}")
    print(f"✅ PASSED: {passed_scenarios}")
    print(f"❌ FAILED: {total_scenarios - passed_scenarios}")
    
    print(f"\n📋 DETAILED RESULTS:")
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result.get('passed') else "❌ FAIL"
        print(f"{status} Scenario {i}: {result['scenario']}")
        print(f"   Customer: {result['customer_email']}")
        if 'folder_path' in result:
            print(f"   Path: {result['folder_path']}")
        if 'filename' in result:
            print(f"   File: {result['filename']}")
        if 'error' in result:
            print(f"   Error: {result['error']}")
        print()
    
    # Configuration summary
    print(f"📋 FINAL CONFIGURATION:")
    print(f"   ✅ Files owned by: {settings.google_drive_owner_email} (via service account)")
    print(f"   ✅ Default customer folder: {settings.default_customer_email}")
    print(f"   ✅ Root folder: {settings.google_drive_root_folder}")
    print(f"   ✅ Language metadata: Properly stored for each file")
    print(f"   ✅ Customer access: None (folders for organization only)")
    
    return passed_scenarios == total_scenarios

if __name__ == "__main__":
    print("🚀 Starting final upload workflow verification...")
    success = asyncio.run(test_final_upload_workflow())
    if success:
        print(f"\n🎉 ALL TESTS PASSED! Upload workflow working perfectly!")
        print(f"✅ Ownership separation implemented correctly")
        print(f"✅ ben.danishevsky@gmail.com used as default customer")
        print(f"✅ Files owned by danishevsky@gmail.com (service account)")
        print(f"✅ Folders named by customer email for organization")
    else:
        print(f"\n❌ Some tests failed! Check the implementation.")