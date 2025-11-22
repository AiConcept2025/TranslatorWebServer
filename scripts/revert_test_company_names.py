#!/usr/bin/env python3
"""
Revert test files to use None instead of 'Individual Users' for company_name.

This script reverts all test files that use company_name: "Individual Users"
back to company_name: None.
"""

import re
from pathlib import Path

# Files to update (based on previous changes)
files_to_update = [
    "tests/integration/test_transaction_confirm_square.py",
    "tests/integration/test_confirm_endpoints_split.py",
    "tests/integration/test_nested_translation_flow.py",
    "tests/integration/test_confirm_square_payment.py",
    "tests/integration/test_enterprise_transaction_metadata.py",
]

def update_file(file_path: Path):
    """Revert company_name: 'Individual Users' to company_name: None in a file."""
    print(f"\n📝 Processing: {file_path}")

    if not file_path.exists():
        print(f"   ⚠️  File not found, skipping")
        return

    content = file_path.read_text()
    original_content = content

    # Replace dict-style assignments
    content = re.sub(
        r'"company_name":\s*"Individual Users"\s*,?\s*(#.*)?',
        r'"company_name": None,  \1' if r'\1' else r'"company_name": None,',
        content
    )

    # Replace function argument style assignments
    content = re.sub(
        r'company_name\s*=\s*"Individual Users"\s*,?\s*(#.*)?',
        r'company_name=None,  \1' if r'\1' else r'company_name=None,',
        content
    )

    # Replace assertions
    content = re.sub(
        r'company_name"\]\s*==\s*"Individual Users"',
        r'company_name"] is None',
        content
    )

    if content != original_content:
        file_path.write_text(content)
        print(f"   ✅ Reverted to use None")
    else:
        print(f"   ℹ️  No changes needed")

def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent

    print("🔧 Reverting test files to use None instead of 'Individual Users'...")

    updated_count = 0
    for file_path_str in files_to_update:
        file_path = base_dir / file_path_str
        update_file(file_path)
        updated_count += 1

    print(f"\n✅ Processed {updated_count} files")
    print("\n📋 Summary:")
    print("   - All company_name: 'Individual Users' → company_name: None")
    print("   - All company_name='Individual Users' → company_name=None")
    print("   - All assertions reverted")

if __name__ == "__main__":
    main()
