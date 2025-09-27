#!/usr/bin/env python3
"""
Google Drive setup script for TranslatorWebServer.

This script helps users set up Google Drive integration by:
1. Checking for required credentials
2. Testing the authentication process
3. Creating test folder structure
4. Providing setup instructions
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional

# Add the app directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.services.google_drive_service import GoogleDriveService
from app.exceptions.google_drive_exceptions import GoogleDriveError


def print_header():
    """Print setup script header."""
    print("=" * 60)
    print("         TranslatorWebServer Google Drive Setup")
    print("=" * 60)
    print()


def check_credentials_file() -> bool:
    """Check if Google Drive credentials file exists."""
    print("🔍 Checking Google Drive credentials...")
    
    if not settings.google_drive_credentials_path:
        print("❌ No credentials file configured in settings")
        print("   Set GOOGLE_DRIVE_CREDENTIALS_PATH in .env file")
        return False
    
    credentials_path = Path(settings.google_drive_credentials_path)
    if not credentials_path.exists():
        print(f"❌ Credentials file not found: {credentials_path}")
        print(f"   Please download credentials.json from Google Cloud Console")
        return False
    
    # Check if it's a valid JSON file
    try:
        with open(credentials_path, 'r') as f:
            creds_data = json.load(f)
            
        if 'installed' not in creds_data and 'web' not in creds_data:
            print("❌ Invalid credentials file format")
            return False
            
        print(f"✅ Credentials file found: {credentials_path}")
        return True
        
    except json.JSONDecodeError:
        print("❌ Credentials file is not valid JSON")
        return False
    except Exception as e:
        print(f"❌ Error reading credentials file: {e}")
        return False


def print_setup_instructions():
    """Print Google Drive setup instructions."""
    print()
    print("📋 Google Drive Setup Instructions:")
    print("=" * 40)
    print()
    print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
    print("2. Create a new project or select existing one")
    print("3. Enable Google Drive API:")
    print("   - Go to 'APIs & Services' > 'Library'")
    print("   - Search for 'Google Drive API'")
    print("   - Click 'Enable'")
    print()
    print("4. Create credentials:")
    print("   - Go to 'APIs & Services' > 'Credentials'")
    print("   - Click '+ CREATE CREDENTIALS' > 'OAuth client ID'")
    print("   - Choose 'Desktop application'")
    print("   - Download the credentials JSON file")
    print()
    print("5. Place the credentials file:")
    print(f"   - Save as: {settings.google_drive_credentials_path}")
    print("   - Make sure the file is readable")
    print("   - Set GOOGLE_DRIVE_CREDENTIALS_PATH in .env file")
    print()
    print("6. Configure scopes (already set in settings):")
    print(f"   - {settings.google_drive_scopes}")
    print()


async def test_google_drive_service() -> bool:
    """Test Google Drive service initialization and basic operations."""
    print("🔧 Testing Google Drive service...")
    
    try:
        # Initialize service
        service = GoogleDriveService()
        
        if not service.enabled:
            print("❌ Google Drive service is disabled in configuration")
            return False
        
        if not service.service:
            print("❌ Failed to initialize Google Drive service")
            return False
        
        print("✅ Google Drive service initialized successfully")
        
        # Test folder creation
        print("🗂️  Testing folder operations...")
        test_email = "test@example.com"
        
        try:
            folder_id = await service.create_customer_folder_structure(test_email)
            print(f"✅ Test folder created: {folder_id}")
            
            # Test folder info
            folder_info = await service.get_folder_info(folder_id)
            print(f"✅ Folder info retrieved: {folder_info.get('folder_name', 'Unknown')}")
            
            return True
            
        except GoogleDriveError as e:
            print(f"❌ Folder operation failed: {e.message}")
            return False
            
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return False


async def run_setup_tests() -> bool:
    """Run all setup tests."""
    print("🧪 Running Google Drive integration tests...")
    print()
    
    # Test 1: Check credentials
    if not check_credentials_file():
        print_setup_instructions()
        return False
    
    print()
    
    # Test 2: Test service
    if not await test_google_drive_service():
        return False
    
    print()
    print("✅ All tests passed! Google Drive integration is ready.")
    return True


def print_configuration_info():
    """Print current configuration information."""
    print()
    print("⚙️  Current Configuration:")
    print("=" * 30)
    print(f"Google Drive Enabled: {settings.google_drive_enabled}")
    print(f"Credentials Path: {settings.google_drive_credentials_path}")
    print(f"Token Path: {settings.google_drive_token_path}")
    print(f"Root Folder: {settings.google_drive_root_folder}")
    print(f"Application Name: {settings.google_drive_application_name}")
    print(f"Scopes: {settings.google_drive_scopes}")
    print()


def print_next_steps():
    """Print next steps after successful setup."""
    print()
    print("🚀 Next Steps:")
    print("=" * 15)
    print("1. Start the FastAPI server:")
    print("   python -m app.main")
    print()
    print("2. Test the upload endpoint:")
    print("   POST /api/upload")
    print("   - customer_email: your-email@example.com")
    print("   - target_language: es (or any target language)")
    print("   - files: upload test files")
    print()
    print("3. Check your Google Drive for the created folder structure")
    print()


async def main():
    """Main setup function."""
    print_header()
    print_configuration_info()
    
    # Run setup tests
    success = await run_setup_tests()
    
    if success:
        print_next_steps()
        return 0
    else:
        print()
        print("❌ Setup failed. Please check the instructions above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)