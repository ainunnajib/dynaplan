#!/usr/bin/env bash
# Backpressure wrapper: suppress verbose output on success, show on failure.
# Saves 2-3% of agent context per test run.
#
# Usage: ./scripts/run_silent.sh "label" "command"
# Examples:
#   ./scripts/run_silent.sh "backend tests" "cd backend && pytest -x --tb=short"
#   ./scripts/run_silent.sh "frontend tests" "cd frontend && bun test --bail"
#   ./scripts/run_silent.sh "lint backend" "cd backend && ruff check ."
#   ./scripts/run_silent.sh "type check" "cd frontend && bun tsc --noEmit"

set -euo pipefail

LABEL="${1:?Usage: run_silent.sh <label> <command>}"
CMD="${2:?Usage: run_silent.sh <label> <command>}"

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

if eval "$CMD" > "$TMP" 2>&1; then
    # Success — extract just the summary line
    SUMMARY=""

    # pytest: "5 passed in 0.12s"
    if grep -q "passed" "$TMP"; then
        SUMMARY=$(grep -oE '[0-9]+ passed' "$TMP" | tail -1 || true)
    fi

    # vitest/jest: "Tests: X passed, X total"
    if grep -q "Tests:" "$TMP"; then
        SUMMARY=$(grep "Tests:" "$TMP" | tail -1 | sed 's/^[[:space:]]*//')
    fi

    # ruff/eslint: no output means clean
    if [ ! -s "$TMP" ]; then
        SUMMARY="clean"
    fi

    if [ -n "$SUMMARY" ]; then
        echo "✓ $LABEL ($SUMMARY)"
    else
        echo "✓ $LABEL"
    fi
    exit 0
else
    EXIT_CODE=$?
    echo "✗ $LABEL (exit $EXIT_CODE)"
    echo "---"

    # Filter the output to only show useful parts
    # Remove timing lines, blank lines, and framework boilerplate
    grep -v -E '^(={2,}|_{2,}|-{5,}|$)' "$TMP" \
        | grep -v -E '^\s*(platform|cachedir|rootdir|configfile|plugins|collecting)' \
        | grep -v -E '^\s*$' \
        | head -60

    echo "---"
    echo "(showing first 60 relevant lines)"
    exit $EXIT_CODE
fi
