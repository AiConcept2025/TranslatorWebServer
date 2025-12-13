#!/usr/bin/env python3
"""
Configuration Diagnostic Tool

Checks .env file against required configuration fields and reports:
- ✅ Fields that are properly set
- ❌ Fields that are missing
- 📋 Suggested values for missing fields
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# Required fields with suggestions
REQUIRED_FIELDS = {
    # Application
    "ENVIRONMENT": "development",

    # Security
    "SECRET_KEY": "your-secret-key-min-32-chars-change-in-production-use-openssl-rand-hex-32",

    # Database
    "MONGODB_URI": "mongodb://localhost:27017",
    "MONGODB_DATABASE": "translation",

    # Payment
    "STRIPE_SECRET_KEY": "sk_test_your_stripe_secret_key_here",

    # Google Drive
    "GOOGLE_DRIVE_CREDENTIALS_PATH": "./credentials.json",
    "GOOGLE_DRIVE_PARENT_FOLDER_ID": "your_google_drive_folder_id_here",

    # CORS
    "CORS_ORIGINS": "http://localhost:3000,http://localhost:5173",

    # Email
    "SMTP_HOST": "localhost",
    "SMTP_PORT": "1025",
    "SMTP_USERNAME": "",  # Can be empty for development
    "SMTP_PASSWORD": "",  # Can be empty for development
    "EMAIL_FROM": "noreply@localhost",
    "EMAIL_FROM_NAME": "Translation Service",
    "TRANSLATION_SERVICE_COMPANY": "Your Company Name",
}

# Optional fields (nice to have but not required)
OPTIONAL_FIELDS = {
    "GOOGLE_TRANSLATE_API_KEY": "optional_for_google_translate",
    "DEEPL_API_KEY": "optional_for_deepl",
    "AZURE_TRANSLATOR_KEY": "optional_for_azure",
    "STRIPE_WEBHOOK_SECRET": "whsec_test_secret (auto-set in test mode)",
    "API_URL": "auto-inferred from host/port",
}


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Load .env file and return key-value pairs."""
    env_vars = {}

    if not env_path.exists():
        return env_vars

    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse key=value
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                env_vars[key] = value

    return env_vars


def check_configuration(env_path: Path) -> Tuple[List[str], List[str], List[Tuple[str, str]]]:
    """
    Check configuration status.

    Returns:
        - present: List of fields that are set
        - missing: List of fields that are missing
        - suggestions: List of (field, suggested_value) tuples
    """
    env_vars = load_env_file(env_path)

    present = []
    missing = []
    suggestions = []

    for field, suggested_value in REQUIRED_FIELDS.items():
        if field in env_vars and env_vars[field]:
            present.append(field)
        else:
            missing.append(field)
            suggestions.append((field, suggested_value))

    return present, missing, suggestions


def print_report(env_path: Path):
    """Print configuration status report."""
    print("=" * 80)
    print("CONFIGURATION DIAGNOSTIC REPORT")
    print("=" * 80)
    print()

    # Check if .env exists
    if not env_path.exists():
        print(f"❌ ERROR: .env file not found at: {env_path}")
        print()
        print("📋 Create .env file with these required fields:")
        print()
        for field, suggested_value in REQUIRED_FIELDS.items():
            print(f"{field}={suggested_value}")
        print()
        print("Copy .env.example if it exists, or create .env manually.")
        return

    print(f"📁 Checking: {env_path}")
    print()

    # Check configuration
    present, missing, suggestions = check_configuration(env_path)

    # Print present fields
    if present:
        print(f"✅ CONFIGURED FIELDS ({len(present)}):")
        print()
        for field in sorted(present):
            print(f"  ✅ {field}")
        print()

    # Print missing fields
    if missing:
        print(f"❌ MISSING REQUIRED FIELDS ({len(missing)}):")
        print()
        for field in sorted(missing):
            print(f"  ❌ {field}")
        print()

        print("📋 SUGGESTED .ENV ADDITIONS:")
        print()
        print("# Add these lines to your .env file:")
        print()
        for field, suggested_value in suggestions:
            print(f"{field}={suggested_value}")
        print()
    else:
        print("✅ ALL REQUIRED FIELDS ARE CONFIGURED!")
        print()

    # Print optional fields status
    env_vars = load_env_file(env_path)
    optional_present = [f for f in OPTIONAL_FIELDS.keys() if f in env_vars and env_vars[f]]
    optional_missing = [f for f in OPTIONAL_FIELDS.keys() if f not in env_vars or not env_vars[f]]

    if optional_missing:
        print(f"💡 OPTIONAL FIELDS (not required, {len(optional_missing)} not set):")
        print()
        for field in sorted(optional_missing):
            description = OPTIONAL_FIELDS[field]
            print(f"  💡 {field} - {description}")
        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"✅ Configured: {len(present)}/{len(REQUIRED_FIELDS)} required fields")
    print(f"❌ Missing: {len(missing)}/{len(REQUIRED_FIELDS)} required fields")
    print(f"💡 Optional: {len(optional_present)}/{len(OPTIONAL_FIELDS)} configured")
    print()

    if missing:
        print("⚠️  SERVER WILL FAIL TO START - Missing required configuration")
        print()
        print("Action: Add missing fields to .env file")
        sys.exit(1)
    else:
        print("✅ SERVER SHOULD START SUCCESSFULLY")
        print()
        sys.exit(0)


def main():
    """Main entry point."""
    # Find .env file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    env_path = project_root / ".env"

    print_report(env_path)


if __name__ == "__main__":
    main()
