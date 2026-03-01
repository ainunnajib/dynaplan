#!/usr/bin/env bash
# Run all checks with backpressure. Use this before committing.
# Each check prints ✓/✗ with minimal output. Full output only on failure.

set -uo pipefail
cd "$(dirname "$0")/.."

FAILED=0
RS="./scripts/run_silent.sh"

echo "=== Dynaplan Check Suite ==="

# Backend checks
$RS "backend tests"  "cd backend && pytest -x --tb=short -q" || FAILED=1
$RS "backend lint"   "cd backend && ruff check ." || FAILED=1

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
