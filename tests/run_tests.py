#!/usr/bin/env python3
"""
Comprehensive test runner for TranslatorWebServer.

This script provides various test execution modes for the Google Drive integration
and other components of the TranslatorWebServer.
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path


def run_command(cmd: list, description: str = ""):
    """Run a command and handle errors."""
    if description:
        print(f"\n{'='*60}")
        print(f"Running: {description}")
        print(f"Command: {' '.join(cmd)}")
        print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def check_google_drive_credentials():
    """Check if Google Drive credentials are available for integration tests."""
    credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH', './credentials.json')
    token_path = os.getenv('GOOGLE_DRIVE_TOKEN_PATH', './token.json')
    
    creds_exist = os.path.exists(credentials_path)
    token_exist = os.path.exists(token_path)
    
    print(f"\nGoogle Drive Credentials Check:")
    print(f"  Credentials file ({credentials_path}): {'✓ Found' if creds_exist else '✗ Not found'}")
    print(f"  Token file ({token_path}): {'✓ Found' if token_exist else '✗ Not found'}")
    
    if creds_exist:
        print(f"  Integration tests will be enabled")
        return True
    else:
        print(f"  Integration tests will be skipped")
        print(f"  To enable integration tests:")
        print(f"    1. Set up Google Drive API credentials")
        print(f"    2. Place credentials.json in the project root")
        print(f"    3. Run authentication flow to generate token.json")
        return False


def run_unit_tests():
    """Run only unit tests (fast, no external dependencies)."""
    cmd = [
        "pytest", 
        "tests/unit/", 
        "-v",
        "--tb=short",
        "--cov=app",
        "--cov-report=term-missing",
        "-m", "not integration and not slow"
    ]
    return run_command(cmd, "Unit Tests (Google Drive Service, API Endpoints, Configuration)")


def run_integration_tests():
    """Run integration tests (requires Google Drive credentials)."""
    if not check_google_drive_credentials():
        print("\n⚠️  Skipping integration tests - Google Drive credentials not found")
        return True
    
    cmd = [
        "pytest",
        "tests/integration/", 
        "-v",
        "--tb=short",
        "--run-integration",
        "-m", "integration"
    ]
    return run_command(cmd, "Integration Tests (Real Google Drive API)")


def run_all_tests():
    """Run all tests (unit + integration if credentials available)."""
    print("🚀 Running comprehensive test suite for Google Drive integration")
    
    # Check credentials availability
    has_credentials = check_google_drive_credentials()
    
    # Run unit tests first
    if not run_unit_tests():
        print("❌ Unit tests failed. Stopping test execution.")
        return False
    
    # Run integration tests if credentials are available
    if has_credentials:
        if not run_integration_tests():
            print("❌ Integration tests failed.")
            return False
    else:
        print("\n⚠️  Integration tests skipped due to missing credentials")
    
    print("\n✅ All available tests completed successfully!")
    return True


def run_coverage_report():
    """Generate detailed coverage report."""
    cmd = [
        "pytest",
        "--cov=app",
        "--cov-report=html:htmlcov",
        "--cov-report=term-missing",
        "--cov-report=xml",
        "tests/"
    ]
    
    success = run_command(cmd, "Coverage Analysis")
    
    if success:
        print("\n📊 Coverage reports generated:")
        print("  - Terminal: Displayed above")
        print("  - HTML: htmlcov/index.html")
        print("  - XML: coverage.xml")
    
    return success


def run_performance_tests():
    """Run performance-focused tests."""
    cmd = [
        "pytest",
        "tests/",
        "-v",
        "-m", "slow or performance",
        "--tb=short"
    ]
    return run_command(cmd, "Performance Tests")


def run_specific_test(test_path: str):
    """Run a specific test file or test function."""
    if not os.path.exists(test_path) and not "::" in test_path:
        print(f"❌ Test path not found: {test_path}")
        return False
    
    cmd = ["pytest", test_path, "-v", "--tb=short"]
    return run_command(cmd, f"Specific Test: {test_path}")


def run_parallel_tests():
    """Run tests in parallel for faster execution."""
    try:
        import pytest_xdist
        cmd = [
            "pytest",
            "-n", "auto",  # Auto-detect number of CPUs
            "tests/unit/",  # Only unit tests for parallel execution
            "--tb=short"
        ]
        return run_command(cmd, "Parallel Unit Tests")
    except ImportError:
        print("❌ pytest-xdist not installed. Install with: pip install pytest-xdist")
        return False


def validate_environment():
    """Validate that the testing environment is set up correctly."""
    print("🔍 Validating test environment...")
    
    # Check if we're in the right directory
    if not os.path.exists("app") or not os.path.exists("tests"):
        print("❌ Must be run from the project root directory")
        return False
    
    # Check if pytest is available
    try:
        import pytest
        print(f"✅ pytest version: {pytest.__version__}")
    except ImportError:
        print("❌ pytest not installed. Run: pip install -r requirements.txt")
        return False
    
    # Check if main app modules exist
    required_files = [
        "app/main.py",
        "app/config.py", 
        "app/services/google_drive_service.py",
        "app/routers/upload.py"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ Missing required file: {file_path}")
            return False
    
    # Check test structure
    test_files = [
        "tests/conftest.py",
        "tests/unit/test_google_drive_service.py",
        "tests/unit/test_upload_endpoint.py",
        "tests/integration/test_google_drive_integration.py"
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"⚠️  Test file not found: {file_path}")
    
    return True


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="TranslatorWebServer Test Runner for Google Drive Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py unit                    # Run only unit tests
  python run_tests.py integration             # Run only integration tests  
  python run_tests.py all                     # Run all tests
  python run_tests.py coverage                # Generate coverage report
  python run_tests.py parallel                # Run tests in parallel
  python run_tests.py specific tests/unit/test_google_drive_service.py
  python run_tests.py validate                # Validate test environment

Note: Integration tests require Google Drive API credentials.
Place credentials.json in the project root and run authentication flow.
        """
    )
    
    parser.add_argument(
        "mode",
        choices=["unit", "integration", "all", "coverage", "performance", "specific", "parallel", "validate"],
        help="Test execution mode"
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        help="Specific test path (for 'specific' mode)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate environment first
    if not validate_environment():
        print("❌ Environment validation failed")
        return False
    
    # Execute based on mode
    if args.mode == "unit":
        success = run_unit_tests()
    elif args.mode == "integration":
        success = run_integration_tests()
    elif args.mode == "all":
        success = run_all_tests()
    elif args.mode == "coverage":
        success = run_coverage_report()
    elif args.mode == "performance":
        success = run_performance_tests()
    elif args.mode == "parallel":
        success = run_parallel_tests()
    elif args.mode == "specific":
        if not args.path:
            print("❌ Must provide test path for 'specific' mode")
            return False
        success = run_specific_test(args.path)
    elif args.mode == "validate":
        success = validate_environment()
        if success:
            print("\n✅ Environment validation passed!")
    else:
        print(f"❌ Unknown mode: {args.mode}")
        return False
    
    if success:
        print(f"\n🎉 Test execution completed successfully!")
        return True
    else:
        print(f"\n💥 Test execution failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)