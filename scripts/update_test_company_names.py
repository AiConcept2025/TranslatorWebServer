#!/usr/bin/env python3
"""
Update test files to use 'Individual Users' instead of None for company_name.

This script updates all test files that use company_name: None to use
company_name: "Individual Users" to comply with database validation.
"""

import re
from pathlib import Path

# Files to update (based on grep results)
files_to_update = [
    "tests/integration/test_transaction_confirm_square.py",
    "tests/integration/test_confirm_endpoints_split.py",
    "tests/integration/test_nested_translation_flow.py",
    "tests/integration/test_confirm_square_payment.py",
    "tests/integration/test_enterprise_transaction_metadata.py",
]

# Pattern to match company_name: None with optional comment
pattern = re.compile(r'"company_name":\s*None(?:\s*,)?\s*(?:#.*)?')

def update_file(file_path: Path):
    """Update company_name: None to company_name: 'Individual Users' in a file."""
    print(f"\n📝 Processing: {file_path}")

    if not file_path.exists():
        print(f"   ⚠️  File not found, skipping")
        return

    content = file_path.read_text()
    original_content = content

    # Count matches
    matches = pattern.findall(content)
    if not matches:
        print(f"   ℹ️  No matches found")
        return

    print(f"   Found {len(matches)} occurrences of company_name: None")

    # Replace all occurrences
    # Handle different patterns:
    # 1. "company_name": None,  # Individual customer
    # 2. "company_name": None  # Individual user
    # 3. company_name=None,  # Individual user
    # 4. company_name=None  # NOT ENTERPRISE

    # Replace dict-style assignments
    content = re.sub(
        r'"company_name":\s*None\s*,?\s*(#.*Individual.*|#.*NOT ENTERPRISE.*|#.*Non-enterprise.*)?',
        r'"company_name": "Individual Users",  \1' if r'\1' else r'"company_name": "Individual Users",',
        content
    )

    # Replace function argument style assignments
    content = re.sub(
        r'company_name\s*=\s*None\s*,?\s*(#.*Individual.*|#.*NOT ENTERPRISE.*|#.*Non-enterprise.*)?',
        r'company_name="Individual Users",  \1' if r'\1' else r'company_name="Individual Users",',
        content
    )

    if content != original_content:
        file_path.write_text(content)
        print(f"   ✅ Updated {len(matches)} occurrences")
    else:
        print(f"   ⚠️  No changes made")

def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent

    print("🔧 Updating test files to use 'Individual Users' instead of None...")

    updated_count = 0
    for file_path_str in files_to_update:
        file_path = base_dir / file_path_str
        update_file(file_path)
        updated_count += 1

    print(f"\n✅ Processed {updated_count} files")
    print("\n📋 Summary:")
    print("   - All company_name: None → company_name: 'Individual Users'")
    print("   - All company_name=None → company_name='Individual Users'")
    print("   - Comments preserved where present")

if __name__ == "__main__":
    main()
