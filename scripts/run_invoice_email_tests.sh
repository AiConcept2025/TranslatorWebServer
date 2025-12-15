#!/bin/bash
#
# Invoice Email Testing Script
#
# This script runs the invoice email integration and E2E tests.
# It assumes the test server is already running at http://localhost:8000
#
# PREREQUISITES:
# 1. Test server must be running with test database:
#    DATABASE_MODE=test uvicorn app.main:app --reload --port 8000
#
# 2. MongoDB test database must be accessible:
#    translation_test database on localhost:27017
#
# USAGE:
#   ./scripts/run_invoice_email_tests.sh [options]
#
# OPTIONS:
#   integration   - Run only integration tests
#   e2e          - Run only E2E tests
#   all          - Run all tests (default)
#   -v           - Verbose output
#   -vv          - Very verbose output with logs
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Invoice Email Testing Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}Error: Virtual environment not found at .venv${NC}"
    echo "Please create virtual environment: python3 -m venv .venv"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Verify reportlab is installed
echo -e "${YELLOW}Verifying dependencies...${NC}"
if ! python -c "import reportlab" 2>/dev/null; then
    echo -e "${RED}Error: reportlab not installed${NC}"
    echo "Installing reportlab..."
    pip install reportlab==4.2.5
fi

if ! python -c "import PyPDF2" 2>/dev/null; then
    echo -e "${RED}Error: PyPDF2 not installed${NC}"
    echo "Installing PyPDF2..."
    pip install PyPDF2==3.0.1
fi

echo -e "${GREEN}✓ Dependencies verified${NC}"
echo ""

# Check if server is running
echo -e "${YELLOW}Checking if test server is running...${NC}"
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${RED}Error: Test server not running at http://localhost:8000${NC}"
    echo ""
    echo "Please start the test server in a separate terminal:"
    echo -e "${YELLOW}  cd $PROJECT_ROOT${NC}"
    echo -e "${YELLOW}  DATABASE_MODE=test uvicorn app.main:app --reload --port 8000${NC}"
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Test server is running${NC}"
echo ""

# Parse command line arguments
TEST_TYPE="all"
VERBOSE=""

for arg in "$@"; do
    case $arg in
        integration)
            TEST_TYPE="integration"
            ;;
        e2e)
            TEST_TYPE="e2e"
            ;;
        all)
            TEST_TYPE="all"
            ;;
        -v)
            VERBOSE="-v"
            ;;
        -vv)
            VERBOSE="-vv"
            ;;
        *)
            echo -e "${RED}Unknown option: $arg${NC}"
            echo "Usage: $0 [integration|e2e|all] [-v|-vv]"
            exit 1
            ;;
    esac
done

# Run tests based on type
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Running Tests: $TEST_TYPE${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$TEST_TYPE" = "integration" ] || [ "$TEST_TYPE" = "all" ]; then
    echo -e "${YELLOW}Running Integration Tests...${NC}"
    echo ""
    pytest tests/integration/test_invoice_email_integration.py $VERBOSE
    echo ""
fi

if [ "$TEST_TYPE" = "e2e" ] || [ "$TEST_TYPE" = "all" ]; then
    echo -e "${YELLOW}Running E2E Tests...${NC}"
    echo ""
    pytest tests/e2e/test_invoice_email_flow.py $VERBOSE
    echo ""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ All Tests Completed${NC}"
echo -e "${GREEN}========================================${NC}"
