#!/usr/bin/env bash
# Run all checks with backpressure. Use this before committing.
# Each check prints ✓/✗ with minimal output. Full output only on failure.

set -uo pipefail
cd "$(dirname "$0")/.."

FAILED=0
RS="./scripts/run_silent.sh"

echo "=== Dynaplan Check Suite ==="

# Backend checks
$RS "backend tests"  "cd backend && if [ -x .venv/bin/pytest ]; then .venv/bin/pytest -x --tb=short -q; else pytest -x --tb=short -q; fi" || FAILED=1
$RS "backend backpressure" "cd backend && if [ -x .venv/bin/pytest ]; then .venv/bin/pytest tests/test_cell.py tests/test_api_keys.py tests/test_action.py tests/test_chunked_upload.py tests/test_cloudworks.py tests/test_pipeline.py tests/test_engine_profile.py tests/test_backpressure_journeys.py -m backpressure -q; else pytest tests/test_cell.py tests/test_api_keys.py tests/test_action.py tests/test_chunked_upload.py tests/test_cloudworks.py tests/test_pipeline.py tests/test_engine_profile.py tests/test_backpressure_journeys.py -m backpressure -q; fi" || FAILED=1
$RS "backend lint"   "cd backend && if [ -x .venv/bin/ruff ]; then .venv/bin/ruff check .; else ruff check .; fi" || FAILED=1

# Frontend checks
$RS "frontend tests" "cd frontend && bun test --bail 2>&1" || FAILED=1
$RS "frontend lint"  "cd frontend && bun lint 2>&1" || FAILED=1
$RS "type check"     "cd frontend && bun tsc --noEmit 2>&1" || FAILED=1

echo "==========================="

if [ $FAILED -eq 0 ]; then
    echo "✓ All checks passed"
    exit 0
else
    echo "✗ Some checks failed"
    exit 1
fi
