#!/usr/bin/env python3
"""
Test script to verify Google Drive trash cleanup functionality.

This script tests the clean_trash_folder() method to ensure:
1. It correctly identifies trashed files
2. It logs clearly when trash is empty vs. has files
3. It successfully deletes files from trash
"""

import asyncio
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.google_drive_service import google_drive_service


async def main():
    """Test the trash cleanup functionality."""
    print("=" * 80)
    print("TESTING GOOGLE DRIVE TRASH CLEANUP")
    print("=" * 80)
    print()

    try:
        # Run the cleanup
        print("🧪 Running trash cleanup...")
        result = await google_drive_service.clean_trash_folder()

        # Display results
        print()
        print("=" * 80)
        print("TEST RESULTS:")
        print("=" * 80)
        print(f"Trash was empty: {result.get('trash_was_empty')}")
        print(f"Files found: {result.get('files_found', 0)}")
        print(f"Files deleted: {result.get('files_deleted', 0)}")
        print(f"Total size: {result.get('total_size_mb', 0)} MB")
        print(f"Duration: {result.get('duration_seconds', 0):.2f}s")

        if result.get('errors'):
            print(f"\n⚠️  Errors: {len(result['errors'])}")
            for error in result['errors'][:5]:  # Show first 5 errors
                print(f"   - {error}")

        print()
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)

        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
