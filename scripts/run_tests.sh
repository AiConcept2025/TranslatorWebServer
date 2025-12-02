#!/bin/bash
# =============================================================================
# Run Tests Script with Output Logging
# =============================================================================
# This script runs pytest and saves output to a timestamped file.
#
# Usage:
#   ./scripts/run_tests.sh                    # Run all tests
#   ./scripts/run_tests.sh integration        # Run only integration tests
#   ./scripts/run_tests.sh unit               # Run only unit tests
#   ./scripts/run_tests.sh path/to/test.py    # Run specific test file
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$SERVER_DIR/test-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTPUT_FILE="$OUTPUT_DIR/test_run_$TIMESTAMP.log"
ENV_FILE="$SERVER_DIR/.env"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Change to server directory
cd "$SERVER_DIR"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "=============================================="
echo "  Running Tests - $(date)"
echo "=============================================="
echo ""

# =============================================================================
# DATABASE_MODE AUTO-SWITCHING
# =============================================================================
ORIGINAL_DB_MODE=""

if [ -f "$ENV_FILE" ]; then
    ORIGINAL_DB_MODE=$(grep "^DATABASE_MODE=" "$ENV_FILE" | cut -d'=' -f2)

    if [ "$ORIGINAL_DB_MODE" != "test" ]; then
        echo -e "${YELLOW}🔄 Switching DATABASE_MODE: $ORIGINAL_DB_MODE → test${NC}"
        sed -i.bak "s/^DATABASE_MODE=.*/DATABASE_MODE=test/" "$ENV_FILE"
    else
        echo -e "${GREEN}✅ DATABASE_MODE already set to test${NC}"
    fi
else
    echo -e "${RED}⚠️  .env file not found at $ENV_FILE${NC}"
fi

# Cleanup function to restore original DATABASE_MODE
cleanup() {
    if [ -n "$ORIGINAL_DB_MODE" ] && [ "$ORIGINAL_DB_MODE" != "test" ] && [ -f "$ENV_FILE" ]; then
        echo -e "\n${YELLOW}🔄 Restoring DATABASE_MODE: test → $ORIGINAL_DB_MODE${NC}"
        sed -i.bak "s/^DATABASE_MODE=.*/DATABASE_MODE=$ORIGINAL_DB_MODE/" "$ENV_FILE"
        rm -f "${ENV_FILE}.bak"
    fi
}

# Register cleanup to run on script exit (success or failure)
trap cleanup EXIT

echo ""
echo "Output will be saved to:"
echo "  $OUTPUT_FILE"
echo ""

# Determine test path
if [ -z "$1" ]; then
    TEST_PATH="tests/"
    TEST_NAME="all tests"
elif [ "$1" == "integration" ]; then
    TEST_PATH="tests/integration/"
    TEST_NAME="integration tests"
elif [ "$1" == "unit" ]; then
    TEST_PATH="tests/unit/"
    TEST_NAME="unit tests"
else
    TEST_PATH="$1"
    TEST_NAME="$1"
fi

echo "Running: $TEST_NAME"
echo ""

# Run tests with output to both console and file using tee
# Note: set -o pipefail ensures we capture pytest's exit code through tee
set -o pipefail

{
    echo "=============================================="
    echo "Test Run: $(date)"
    echo "Test Path: $TEST_PATH"
    echo "DATABASE_MODE: $(grep '^DATABASE_MODE' .env 2>/dev/null || echo 'not found')"
    echo "=============================================="
    echo ""

    python -m pytest "$TEST_PATH" \
        -v \
        --tb=short \
        --continue-on-collection-errors \
        2>&1

    echo ""
    echo "=============================================="
    echo "Test Run Complete: $(date)"
    echo "=============================================="
} 2>&1 | tee "$OUTPUT_FILE"

# Get exit code from pytest (pipefail ensures tee preserves it)
TEST_EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=============================================="
echo "  Output saved to: $OUTPUT_FILE"
echo "=============================================="

# Also create a symlink to latest
ln -sf "$OUTPUT_FILE" "$OUTPUT_DIR/latest.log"
echo "  Latest link: $OUTPUT_DIR/latest.log"
echo ""

exit $TEST_EXIT_CODE
