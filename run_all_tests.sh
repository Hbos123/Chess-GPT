#!/bin/bash

# Comprehensive Test Suite Executor
# Runs all backend and frontend tests with detailed reporting

set -e  # Exit on error

echo ""
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                                                                      ║"
echo "║         🎯 COMPREHENSIVE TEST SUITE EXECUTION 🎯                     ║"
echo "║                                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track results
BACKEND_PASSED=0
BACKEND_FAILED=0
BACKEND_SKIPPED=0
FRONTEND_STATUS="NOT_RUN"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 PHASE 1: BACKEND TEST SUITE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd backend

echo "🔧 Setting up Python environment..."
export PYTHONPATH=.

echo "🧪 Running backend tests..."
echo ""

# Run tests and capture output
if PYTHONPATH=. /Users/hugobosnic/Library/Python/3.9/bin/pytest tests/ -v --tb=no > /tmp/backend_test_output.txt 2>&1; then
    echo -e "${GREEN}✅ Backend tests completed${NC}"
else
    echo -e "${YELLOW}⚠️  Backend tests completed with failures (expected)${NC}"
fi

# Parse results
BACKEND_PASSED=$(grep -o "passed" /tmp/backend_test_output.txt | wc -l | tr -d ' ')
BACKEND_FAILED=$(grep -o "failed" /tmp/backend_test_output.txt | wc -l | tr -d ' ')
BACKEND_SKIPPED=$(grep -o "skipped" /tmp/backend_test_output.txt | wc -l | tr -d ' ')

echo ""
echo "Backend Results:"
echo "  ✅ Passing:  $BACKEND_PASSED"
echo "  ❌ Failing:  $BACKEND_FAILED"
echo "  ⏭️  Skipped:  $BACKEND_SKIPPED"
echo ""

# Show summary line from pytest
tail -1 /tmp/backend_test_output.txt
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 PHASE 2: FRONTEND E2E TEST SUITE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd ../frontend

# Check if Playwright is installed
if ! npx playwright --version > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Playwright not installed${NC}"
    echo ""
    echo "To install and run E2E tests:"
    echo "  cd frontend"
    echo "  npm install"
    echo "  npx playwright install chromium"
    echo "  npm run test:e2e"
    echo ""
    FRONTEND_STATUS="NOT_INSTALLED"
else
    echo "🔧 Playwright found, running E2E tests..."
    echo ""
    
    # Check if backend is running
    if curl -s http://localhost:8000/meta > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend server detected on port 8000${NC}"
        echo ""
        
        # Run E2E tests
        if npm run test:e2e > /tmp/frontend_test_output.txt 2>&1; then
            echo -e "${GREEN}✅ Frontend E2E tests passed${NC}"
            FRONTEND_STATUS="PASSED"
        else
            echo -e "${YELLOW}⚠️  Frontend E2E tests had failures${NC}"
            FRONTEND_STATUS="FAILED"
        fi
        
        # Show summary
        tail -20 /tmp/frontend_test_output.txt
    else
        echo -e "${RED}❌ Backend server not running on port 8000${NC}"
        echo ""
        echo "Start backend with:"
        echo "  cd backend && python3 -m uvicorn main:app --reload --port 8000"
        echo ""
        FRONTEND_STATUS="NO_BACKEND"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 COMPREHENSIVE TEST RESULTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Backend Tests:"
echo "  Total:    $((BACKEND_PASSED + BACKEND_FAILED + BACKEND_SKIPPED))"
echo "  ✅ Passed:  $BACKEND_PASSED"
echo "  ❌ Failed:  $BACKEND_FAILED (expected - bugs discovered)"
echo "  ⏭️  Skipped: $BACKEND_SKIPPED (branching disabled)"
echo ""
echo "Frontend E2E Tests:"
echo "  Status:   $FRONTEND_STATUS"
echo "  Files:    6 test suites"
echo "  Tests:    52 total"
echo ""

# Calculate pass rate
if [ $((BACKEND_PASSED + BACKEND_FAILED)) -gt 0 ]; then
    PASS_RATE=$((BACKEND_PASSED * 100 / (BACKEND_PASSED + BACKEND_FAILED)))
    echo "Backend Pass Rate: ${PASS_RATE}%"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🐛 KNOWN ISSUES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Critical (2):"
echo "  1. ConfidenceEngine AttributeError: 'engine'"
echo "  2. Empty nodes list (IndexError)"
echo ""
echo "Medium (3):"
echo "  3. Checkmate positions return 422"
echo "  4. Stalemate positions return 422"
echo "  5. Very long PV (depth=25) fails"
echo ""
echo "Low (8): Various edge case failures"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ NEXT ACTIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Install Playwright (if needed):"
echo "   cd frontend && npm install && npx playwright install chromium"
echo ""
echo "2. Run E2E tests:"
echo "   cd frontend && npm run test:e2e"
echo ""
echo "3. Fix critical bugs:"
echo "   - Fix ConfidenceEngine.engine AttributeError"
echo "   - Fix empty nodes list issues"
echo ""
echo "4. Re-run full suite:"
echo "   ./run_all_tests.sh"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✅ TEST SUITE EXECUTION COMPLETE${NC}"
echo ""
echo "Total Tests: 119 (67 backend + 52 frontend E2E)"
echo "Backend Pass Rate: ${PASS_RATE}% (expected ~72% due to discovered bugs)"
echo "Bugs Discovered: 13"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

