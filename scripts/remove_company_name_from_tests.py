#!/usr/bin/env python3
"""
Remove company_name field entirely from individual user test cases.

This script removes all occurrences of "company_name": None from test files
where it refers to individual users (not company/enterprise users).
"""

import re
from pathlib import Path

# Files to update
files_to_update = [
    "tests/integration/test_confirm_endpoints_split.py",
    "tests/integration/test_nested_translation_flow.py",
    "tests/integration/test_transaction_confirm_square.py",
    "tests/integration/test_confirm_square_payment.py",
    "tests/integration/test_enterprise_transaction_metadata.py",
]

def remove_company_name_field(file_path: Path):
    """Remove company_name field from individual user mock sessions and test data."""
    print(f"\n📝 Processing: {file_path}")

    if not file_path.exists():
        print(f"   ⚠️  File not found, skipping")
        return

    content = file_path.read_text()
    original_content = content

    # Pattern 1: Remove "company_name": None, from mock session data (with comment)
    # Example: "company_name": None,  # Individual user
    content = re.sub(
        r'\s+"company_name":\s*None,\s*(?:#.*Individual.*|#.*Non-enterprise.*|#.*NOT ENTERPRISE.*)?\n',
        '',
        content
    )

    # Pattern 2: Remove standalone "company_name": None,  }
    content = re.sub(
        r'\s+"company_name":\s*None,\s*\}\n',
        ' }\n',
        content
    )

    # Pattern 3: Remove "company_name": None from function calls
    content = re.sub(
        r',?\s*company_name=None,?\s*(?:#.*Individual.*|#.*Non-enterprise.*|#.*NOT ENTERPRISE.*)?',
        '',
        content
    )

    # Pattern 4: Remove assertion lines checking company_name is None
    content = re.sub(
        r'\s+assert call_args\[1\]\["company_name"\] is None.*\n',
        '',
        content
    )

    if content != original_content:
        file_path.write_text(content)
        print(f"   ✅ Removed company_name references")
    else:
        print(f"   ℹ️  No changes needed")

def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent

    print("🔧 Removing company_name field from individual user test cases...")

    for file_path_str in files_to_update:
        file_path = base_dir / file_path_str
        remove_company_name_field(file_path)

    print(f"\n✅ Completed")
    print("\n📋 Summary:")
    print("   - Removed all \"company_name\": None from mock sessions")
    print("   - Removed all company_name=None from function calls")
    print("   - Removed all company_name assertions")
    print("   - Individual users now have no company_name field reference")

if __name__ == "__main__":
    main()
