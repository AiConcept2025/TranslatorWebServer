#!/usr/bin/env python3
"""
Simple test script to verify VS Code debugging configuration works correctly.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_basic_functionality():
    """Test basic Python functionality for debugging."""
    print("🧪 Testing basic debugging functionality...")
    
    # Test 1: Basic variables and breakpoint location
    test_variable = "Hello from debugger!"
    debug_number = 42
    debug_list = [1, 2, 3, 4, 5]
    
    print(f"   Test variable: {test_variable}")
    print(f"   Debug number: {debug_number}")
    print(f"   Debug list: {debug_list}")
    
    # Test 2: Loop for step debugging
    print("   Testing loop (good for step debugging):")
    for i in range(3):
        result = i * 2
        print(f"      Iteration {i}: {i} * 2 = {result}")
    
    return True

def test_configuration_loading():
    """Test loading configuration (useful for debugging config issues)."""
    print("\n🔧 Testing configuration loading...")
    
    try:
        from app.config import settings
        
        print(f"   ✅ Configuration loaded successfully")
        print(f"   Default customer email: {settings.default_customer_email}")
        print(f"   Google Drive owner: {settings.google_drive_owner_email}")
        print(f"   Root folder: {settings.google_drive_root_folder}")
        print(f"   Debug mode: {settings.debug}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Configuration loading failed: {e}")
        logger.exception("Configuration loading error")
        return False

async def test_async_functionality():
    """Test async functionality for debugging async code."""
    print("\n⚡ Testing async functionality...")
    
    # Test async sleep (good for debugging async flows)
    print("   Starting async operation...")
    await asyncio.sleep(0.1)  # Small delay for debugging
    print("   Async operation completed")
    
    # Test async Google Drive service loading
    try:
        from app.services.google_drive_service import google_drive_service
        print("   ✅ Google Drive service loaded")
        print(f"   Service root folder: {google_drive_service.root_folder}")
        return True
        
    except Exception as e:
        print(f"   ❌ Google Drive service loading failed: {e}")
        logger.exception("Google Drive service error")
        return False

def test_file_operations():
    """Test file operations for debugging file handling."""
    print("\n📁 Testing file operations...")
    
    # Test current directory
    current_dir = Path.cwd()
    print(f"   Current directory: {current_dir}")
    
    # Test finding .md files (like in our upload tests)
    md_files = list(current_dir.glob("*.md"))
    print(f"   Found {len(md_files)} .md files:")
    for md_file in md_files[:3]:  # Show first 3
        print(f"      - {md_file.name}")
    
    # Test .env file existence
    env_file = current_dir / ".env"
    if env_file.exists():
        print(f"   ✅ .env file found: {env_file}")
    else:
        print(f"   ❌ .env file not found")
    
    return True

def main():
    """Main function for debugging entry point."""
    print("🚀 Starting VS Code Debug Configuration Test")
    print("=" * 50)
    
    # Set a breakpoint here to test debugging
    debug_checkpoint = "This is a good place to set a breakpoint!"
    print(f"Debug checkpoint: {debug_checkpoint}")
    
    # Test basic functionality
    basic_test = test_basic_functionality()
    
    # Test configuration
    config_test = test_configuration_loading()
    
    # Test file operations
    file_test = test_file_operations()
    
    # Test async functionality
    async_test = asyncio.run(test_async_functionality())
    
    # Summary
    print(f"\n📊 Debug Test Summary:")
    print(f"   Basic functionality: {'✅ PASS' if basic_test else '❌ FAIL'}")
    print(f"   Configuration loading: {'✅ PASS' if config_test else '❌ FAIL'}")
    print(f"   File operations: {'✅ PASS' if file_test else '❌ FAIL'}")
    print(f"   Async functionality: {'✅ PASS' if async_test else '❌ FAIL'}")
    
    all_passed = all([basic_test, config_test, file_test, async_test])
    print(f"\n🎉 Overall result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    # Final breakpoint location
    final_message = "Debug test completed - good place for final breakpoint!"
    print(f"\n{final_message}")
    
    return all_passed

if __name__ == "__main__":
    # Entry point for debugging
    result = main()
    exit(0 if result else 1)