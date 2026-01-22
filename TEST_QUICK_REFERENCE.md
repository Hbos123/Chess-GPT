# Test Suite Quick Reference

**119 tests across backend and frontend**  
**Updated:** November 22, 2025

---

## 🚀 Quick Start

### Run Everything
```bash
./run_all_tests.sh
```

### Run Backend Tests Only
```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

### Run Frontend E2E Tests Only
```bash
cd frontend
npm run test:e2e
```

---

## 🧪 Backend Tests (67 tests)

### All Backend Tests
```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

### By Category

**Engine Queue (7 tests)**
```bash
PYTHONPATH=. pytest tests/test_engine_queue.py -v
```

**API Endpoints (10 tests)**
```bash
PYTHONPATH=. pytest tests/test_api_endpoints.py -v
```

**Confidence Accuracy (7 tests)**
```bash
PYTHONPATH=. pytest tests/test_confidence_accuracy.py -v
```

**Tree Structure (11 tests)**
```bash
PYTHONPATH=. pytest tests/test_tree_structure.py -v
```

**Branching Logic (8 tests - 6 skipped when disabled)**
```bash
PYTHONPATH=. pytest tests/test_branching_logic.py -v
```

**Edge Cases (13 tests)**
```bash
PYTHONPATH=. pytest tests/test_edge_cases.py -v
```

**Play Mode Integration (5 tests)**
```bash
PYTHONPATH=. pytest tests/test_play_mode_integration.py -v
```

**State Consistency (5 tests)**
```bash
PYTHONPATH=. pytest tests/test_state_consistency.py -v
```

### Specific Tests

**Single Test**
```bash
PYTHONPATH=. pytest tests/test_confidence_accuracy.py::test_confidence_ranges_valid -v
```

**Tests Matching Pattern**
```bash
PYTHONPATH=. pytest tests/ -v -k "confidence"
```

**Only Passing Tests (Skip Known Failures)**
```bash
PYTHONPATH=. pytest tests/ -v -k "not (test_checkmate or test_stalemate)"
```

### With Coverage
```bash
PYTHONPATH=. pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html to view report
```

### Verbose Output
```bash
PYTHONPATH=. pytest tests/ -vv --tb=short
```

### Stop on First Failure
```bash
PYTHONPATH=. pytest tests/ -x -v
```

---

## 🎭 Frontend E2E Tests (52 tests)

### Setup (One Time Only)
```bash
cd frontend
npm install
npx playwright install chromium
```

### All E2E Tests
```bash
cd frontend
npm run test:e2e
```

### By Suite

**Play Mode Outcomes (10 tests)**
```bash
npm run test:e2e -- play-mode-outcome-verification.spec.ts
```

**Confidence Tree Outcomes (13 tests)**
```bash
npm run test:e2e -- confidence-tree-outcomes.spec.ts
```

**PGN Parsing Outcomes (10 tests)** ⭐ Catches your bug
```bash
npm run test:e2e -- pgn-parsing-outcomes.spec.ts
```

**Board Sync Outcomes (11 tests)**
```bash
npm run test:e2e -- board-sync-outcomes.spec.ts
```

**LLM Integration Outcomes (10 tests)**
```bash
npm run test:e2e -- llm-integration-outcomes.spec.ts
```

**Performance Outcomes (11 tests)**
```bash
npm run test:e2e -- performance-outcomes.spec.ts
```

### Specific Test
```bash
npm run test:e2e -- -g "PGN after user move"
```

### Debug Mode (See Browser)
```bash
npm run test:e2e:debug
# OR
npx playwright test --debug
```

### Headed Mode (Watch Tests Run)
```bash
npx playwright test --headed
```

### Slow Motion (See What's Happening)
```bash
npx playwright test --headed --slow-mo=1000
```

### Update Screenshots (If Using Visual Regression)
```bash
npx playwright test --update-snapshots
```

---

## 🔍 Debugging Tests

### Backend Test Debugging

**Show Full Traceback**
```bash
PYTHONPATH=. pytest tests/ -vv --tb=long
```

**Print Statements**
```bash
PYTHONPATH=. pytest tests/ -v -s
```

**Run in Debug Mode**
```bash
PYTHONPATH=. pytest tests/ --pdb
```

**Only Failed Tests**
```bash
PYTHONPATH=. pytest tests/ --lf -v
```

### Frontend Test Debugging

**Show Browser**
```bash
npm run test:e2e:debug
```

**Screenshot on Failure**
```bash
npx playwright test --screenshot=only-on-failure
```

**Video Recording**
```bash
npx playwright test --video=retain-on-failure
```

**Trace Viewer (Best for Debugging)**
```bash
npx playwright test --trace=on
# Then: npx playwright show-trace trace.zip
```

---

## 📊 Test Reports

### Backend Coverage Report
```bash
cd backend
PYTHONPATH=. pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html
```

### Frontend Test Report
```bash
cd frontend
npm run test:e2e
npx playwright show-report
```

---

## 🎯 Common Test Scenarios

### Before Making Changes
```bash
# Establish baseline
./run_all_tests.sh > baseline_results.txt
```

### After Making Changes
```bash
# Verify no regressions
./run_all_tests.sh > new_results.txt
diff baseline_results.txt new_results.txt
```

### Testing Specific Feature
```bash
# Example: Testing confidence tree changes
cd backend
PYTHONPATH=. pytest tests/test_confidence_accuracy.py tests/test_tree_structure.py -v

cd ../frontend
npm run test:e2e -- confidence-tree-outcomes.spec.ts
```

### CI/CD Simulation
```bash
# Run as CI would
cd backend
PYTHONPATH=. pytest tests/ -v --tb=short --junit-xml=test-results.xml

cd ../frontend
npm run test:e2e -- --reporter=junit
```

---

## 🔧 Test Configuration

### Backend Config
**File:** `backend/pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
asyncio_mode = auto
```

### Frontend Config
**File:** `frontend/playwright.config.ts`
```typescript
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  use: {
    baseURL: 'http://localhost:3000',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
  },
});
```

---

## 🐛 Known Failing Tests (Expected)

These tests are expected to fail until bugs are fixed:

### Backend
- `test_confidence_calculation_formula` - Formula validation issue
- `test_overall_vs_line_confidence` - Calculation bug
- `test_confidence_with_different_baselines` - Baseline interaction bug
- `test_pv_spine_structure` - Empty nodes issue
- `test_node_shapes_when_no_branching` - Empty nodes issue
- `test_metadata_accuracy` - Empty nodes issue
- `test_position_with_all_high_confidence` - Edge case bug
- `test_position_with_all_low_confidence` - Edge case bug
- `test_position_with_one_legal_move` - Edge case bug
- `test_checkmate_position` - Checkmate handling bug
- `test_stalemate_position` - Stalemate handling bug
- `test_very_long_pv` - Deep analysis bug
- `test_position_with_en_passant` - Special FEN bug

**Total: 13 known failures (bugs to fix)**

---

## ✅ Tests That Should Always Pass

### Critical Backend Tests
```bash
# These verify core functionality
PYTHONPATH=. pytest tests/test_engine_queue.py -v
PYTHONPATH=. pytest tests/test_api_endpoints.py -v
```

### Critical E2E Tests
```bash
# These catch your "Invalid move" bug
npm run test:e2e -- pgn-parsing-outcomes.spec.ts
npm run test:e2e -- play-mode-outcome-verification.spec.ts
```

---

## 📈 Monitoring Test Health

### Daily Health Check
```bash
# Quick smoke test
cd backend
PYTHONPATH=. pytest tests/test_engine_queue.py tests/test_api_endpoints.py -v

# Should show: 17/17 passing
```

### Weekly Full Run
```bash
# Comprehensive check
./run_all_tests.sh

# Review any new failures
# Update known issues list
```

### Before Release
```bash
# Full suite + coverage
cd backend && PYTHONPATH=. pytest tests/ --cov=. --cov-report=html
cd ../frontend && npm run test:e2e
# Review all reports
```

---

## 🎯 Test Outcome Verification Examples

### Backend: Verifying Confidence Calculation
```python
# BAD: Just check status
assert response.status_code == 200

# GOOD: Verify actual outcome
nodes = response.json()["position_confidence"]["nodes"]
for node in nodes:
    conf = node["ConfidencePercent"]
    assert 0 <= conf <= 100  # Valid range
    
    if conf >= baseline:
        assert node["color"] == "green"  # Logic verification
```

### Frontend: Verifying Board State
```typescript
// BAD: Just check no crash
await page.click('[data-square="e2"]');
await page.click('[data-square="e4"]');

// GOOD: Verify actual outcome
await page.click('[data-square="e2"]');
await page.click('[data-square="e4"]');
await page.waitForTimeout(500);

const fen = await page.evaluate(() => (window as any).currentFEN);
expect(fen).toMatch(/4P3/); // e4 pawn present
expect(fen).not.toMatch(/e2/); // e2 pawn gone

const e4Piece = page.locator('[data-square="e4"] .piece');
await expect(e4Piece).toBeVisible(); // Visual verification
```

---

## 🎊 Summary

```
Total Tests:        119
Backend Tests:       67 (48 passing, 13 failing, 6 skipped)
Frontend E2E:        52 (ready to run)
Helper Functions:    11
Bugs Discovered:     13
Pass Rate:          72% (backend)

Files Created:       14
Test Suites:         13
Documentation:        3 guides
```

**Run all tests:** `./run_all_tests.sh`  
**Backend only:** `cd backend && PYTHONPATH=. pytest tests/ -v`  
**Frontend only:** `cd frontend && npm run test:e2e`

---

## 📚 Additional Resources

- `COMPREHENSIVE_TEST_IMPLEMENTATION.md` - Full implementation details
- `COMPREHENSIVE_TEST_SUITE_COMPLETE.md` - Complete overview
- `PHASE_3_E2E_TESTS_STARTED.md` - E2E test documentation

---

**🎯 Quick Reference for 119 Comprehensive Tests with Outcome Verification**

