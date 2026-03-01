#!/usr/bin/env bash
# Autonomous feature implementation with backpressure.
# Runs claude -p to implement a feature from features.json, then runs checks.
#
# Usage: ./scripts/implement_feature.sh F001 [--model sonnet]
#
# This script:
# 1. Extracts feature details from features.json
# 2. Runs claude -p with the feature as the prompt
# 3. Runs the check suite with backpressure
# 4. Reports pass/fail

set -euo pipefail
cd "$(dirname "$0")/.."

FEATURE_ID="${1:?Usage: implement_feature.sh <feature-id> [--model sonnet]}"
MODEL="${2:---model sonnet}"

# Extract feature details
FEATURE=$(python3 -c "
import json, sys
with open('features.json') as f:
    features = json.load(f)['features']
match = [f for f in features if f['id'] == '$FEATURE_ID']
if not match:
    print(f'Feature $FEATURE_ID not found', file=sys.stderr)
    sys.exit(1)
f = match[0]
print(f'[{f[\"id\"]}] {f[\"name\"]}: {f[\"description\"]}')
")

echo ">>> Implementing: $FEATURE"
echo ""

PROMPT="You are implementing a feature for Dynaplan.

Feature: $FEATURE

Instructions:
1. Read claude-progress.txt and CLAUDE.md first
2. Implement the feature following the architecture in CLAUDE.md
3. Write tests that verify the feature works
4. Run tests using: ./scripts/run_silent.sh \"tests\" \"cd backend && pytest -x --tb=short -q\"
5. If tests pass, commit with a clear message
6. Update claude-progress.txt marking this feature as done
7. Update features.json setting this feature status to \"done\"

IMPORTANT: Use ./scripts/run_silent.sh for ALL test/lint commands (backpressure pattern)."

claude -p "$PROMPT" $MODEL --allowedTools "Read,Write,Edit,Glob,Grep,Bash(cd *),Bash(git *),Bash(./scripts/*),Bash(pytest *),Bash(bun *)"

echo ""
echo ">>> Post-implementation checks:"
./scripts/test_all.sh
