#!/bin/bash
# test.sh - Intelligent test runner with coverage tracking

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE=${1:-all}
COVERAGE_THRESHOLD=90

echo "🧪 FastAPI Test Runner"
echo "====================="

# Activate virtual environment if exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Function to run tests
run_tests() {
    local test_path=$1
    local test_name=$2
    
    echo -e "\n${YELLOW}Running $test_name tests...${NC}"
    
    if pytest $test_path -v --tb=short --cov=app --cov-report=term-missing --cov-report=json; then
        echo -e "${GREEN}✅ $test_name tests passed${NC}"
        return 0
    else
        echo -e "${RED}❌ $test_name tests failed${NC}"
        return 1
    fi
}

# Check coverage
check_coverage() {
    if [ -f "coverage.json" ]; then
        COVERAGE=$(python -c "import json; print(json.load(open('coverage.json'))['totals']['percent_covered'])")
        COVERAGE_INT=${COVERAGE%.*}
        
        echo -e "\n📊 Coverage: ${COVERAGE}%"
        
        if [ $COVERAGE_INT -lt $COVERAGE_THRESHOLD ]; then
            echo -e "${RED}⚠️  Coverage below threshold ($COVERAGE_THRESHOLD%)${NC}"
            return 1
        else
            echo -e "${GREEN}✅ Coverage meets threshold${NC}"
        fi
    fi
}

# Main test execution
case $TEST_TYPE in
    unit)
        run_tests "tests/unit" "Unit"
        ;;
    
    api|integration)
        run_tests "tests/integration" "Integration"
        ;;
    
    perf|performance)
        echo -e "\n${YELLOW}Running performance tests...${NC}"
        pytest tests/performance -v -m performance --tb=short
        ;;
    
    quick)
        echo -e "\n${YELLOW}Running quick smoke tests...${NC}"
        pytest tests/unit tests/integration/test_health.py -x --tb=short
        ;;
    
    all)
        FAILED=0
        
        run_tests "tests/unit" "Unit" || FAILED=1
        run_tests "tests/integration" "Integration" || FAILED=1
        
        check_coverage || FAILED=1
        
        if [ $FAILED -eq 0 ]; then
            echo -e "\n${GREEN}🎉 All tests passed!${NC}"
        else
            echo -e "\n${RED}💔 Some tests failed${NC}"
            exit 1
        fi
        ;;
    
    *)
        echo "Usage: $0 [unit|api|perf|quick|all]"
        exit 1
        ;;
esac

echo -e "\n✨ Done!"

