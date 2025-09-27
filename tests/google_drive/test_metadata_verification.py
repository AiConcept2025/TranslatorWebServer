#!/usr/bin/env python3
"""
Test script to verify that language identifier is properly stored as metadata in uploaded files.
"""

import asyncio
import aiofiles
from pathlib import Path
import logging
import json
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_language_metadata():
    """Test that language identifier is properly stored as metadata in uploaded files."""
    
    from app.services.google_drive_service import google_drive_service
    
    # Import settings to get customer email from config
    from app.config import settings
    customer_email = settings.default_customer_email
    
    # Test with different target languages
    test_cases = [
        {"language": "es", "description": "Spanish"},
        {"language": "fr", "description": "French"}, 
        {"language": "de", "description": "German"}
    ]
    
    print("🧪 Testing language metadata in Google Drive uploads...")
    print("=" * 60)
    
    try:
        # Get folder structure
        folder_id = await google_drive_service.create_customer_folder_structure(customer_email)
        print(f"📁 Using folder ID: {folder_id}")
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            target_language = test_case["language"]
            lang_description = test_case["description"]
            
            print(f"\n🧪 Test Case {i}: Uploading file with target language '{target_language}' ({lang_description})")
            
            # Create a test file content
            test_content = f"""# Test File for {lang_description} Translation
            
This is a test file to verify that the target language '{target_language}' 
is properly stored as metadata in Google Drive.

Upload timestamp: {datetime.utcnow().isoformat()}
Target language: {target_language}
Test case: {i}
"""
            
            test_filename = f"test_metadata_{target_language}_{i}.md"
            
            # Upload the test file
            file_info = await google_drive_service.upload_file_to_folder(
                file_content=test_content.encode('utf-8'),
                filename=test_filename,
                folder_id=folder_id,
                target_language=target_language
            )
            
            print(f"✅ Uploaded {test_filename}")
            print(f"   File ID: {file_info['file_id']}")
            print(f"   Expected target_language metadata: {target_language}")
            
            # Now retrieve the file metadata directly from Google Drive API
            try:
                file_details = google_drive_service.service.files().get(
                    fileId=file_info['file_id'],
                    fields='id,name,properties,description,createdTime,size,parents'
                ).execute()
                
                print(f"📊 Retrieved metadata for {test_filename}:")
                print(f"   File ID: {file_details['id']}")
                print(f"   Name: {file_details['name']}")
                print(f"   Description: {file_details.get('description', 'No description')}")
                print(f"   Created: {file_details.get('createdTime', 'Unknown')}")
                print(f"   Size: {file_details.get('size', 'Unknown')} bytes")
                
                # Check properties (custom metadata)
                properties = file_details.get('properties', {})
                if properties:
                    print(f"📝 Custom Properties (Metadata):")
                    for key, value in properties.items():
                        print(f"      {key}: {value}")
                    
                    # Verify target_language is present and correct
                    stored_target_language = properties.get('target_language')
                    if stored_target_language == target_language:
                        print(f"✅ PASS: target_language metadata is correct ({stored_target_language})")
                        test_result = "PASS"
                    else:
                        print(f"❌ FAIL: target_language metadata mismatch!")
                        print(f"   Expected: {target_language}")
                        print(f"   Found: {stored_target_language}")
                        test_result = "FAIL"
                else:
                    print(f"❌ FAIL: No custom properties found in metadata!")
                    test_result = "FAIL"
                
                results.append({
                    'test_case': i,
                    'filename': test_filename,
                    'file_id': file_info['file_id'],
                    'target_language': target_language,
                    'stored_language': properties.get('target_language'),
                    'properties': properties,
                    'description': file_details.get('description'),
                    'result': test_result
                })
                
            except Exception as e:
                print(f"❌ Error retrieving metadata for {test_filename}: {e}")
                results.append({
                    'test_case': i,
                    'filename': test_filename,
                    'file_id': file_info['file_id'],
                    'target_language': target_language,
                    'error': str(e),
                    'result': "ERROR"
                })
        
        # Summary of results
        print(f"\n📊 METADATA VERIFICATION SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in results if r.get('result') == 'PASS')
        failed = sum(1 for r in results if r.get('result') == 'FAIL')
        errors = sum(1 for r in results if r.get('result') == 'ERROR')
        
        print(f"Total test cases: {len(results)}")
        print(f"✅ PASSED: {passed}")
        print(f"❌ FAILED: {failed}")
        print(f"🔥 ERRORS: {errors}")
        
        print(f"\n📋 DETAILED RESULTS:")
        for result in results:
            status_emoji = "✅" if result['result'] == 'PASS' else "❌" if result['result'] == 'FAIL' else "🔥"
            print(f"{status_emoji} Test {result['test_case']}: {result['filename']}")
            print(f"   Target Language: {result['target_language']}")
            if 'stored_language' in result:
                print(f"   Stored Language: {result['stored_language']}")
            if 'properties' in result and result['properties']:
                print(f"   All Properties: {list(result['properties'].keys())}")
            print()
        
        # Test the existing uploaded files too
        print(f"\n🔍 CHECKING EXISTING .MD FILES METADATA")
        print("=" * 60)
        
        existing_files = await google_drive_service.list_files_in_folder(folder_id)
        md_files = [f for f in existing_files if f['filename'].endswith('.md') and not f['filename'].startswith('test_metadata_')]
        
        print(f"Found {len(md_files)} existing .md files to check...")
        
        for file_info in md_files[:3]:  # Check first 3 to avoid too much output
            try:
                file_details = google_drive_service.service.files().get(
                    fileId=file_info['file_id'],
                    fields='id,name,properties,description'
                ).execute()
                
                properties = file_details.get('properties', {})
                print(f"\n📄 {file_details['name']}")
                print(f"   Description: {file_details.get('description', 'No description')}")
                if properties:
                    print(f"   Properties: {properties}")
                    if 'target_language' in properties:
                        print(f"   ✅ Has target_language: {properties['target_language']}")
                    else:
                        print(f"   ❌ Missing target_language property")
                else:
                    print(f"   ❌ No properties found")
                    
            except Exception as e:
                print(f"   🔥 Error checking {file_info['filename']}: {e}")
        
        return results
        
    except Exception as e:
        print(f"❌ Error during metadata testing: {e}")
        logging.exception("Metadata test failed")
        raise

if __name__ == "__main__":
    print("🚀 Starting language metadata verification test...")
    result = asyncio.run(test_language_metadata())
    print(f"\n🏁 Metadata verification test completed!")