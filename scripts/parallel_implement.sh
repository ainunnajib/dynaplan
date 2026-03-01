#!/usr/bin/env bash
# Run multiple feature implementations in parallel using git worktrees.
# Each feature gets its own isolated worktree so agents don't conflict.
#
# Usage: ./scripts/parallel_implement.sh F001 F002 F003
#
# After all agents finish:
# - Each worktree has its own branch with commits
# - Review each branch, then merge to main

set -uo pipefail
cd "$(dirname "$0")/.."

ROOT=$(pwd)
WORKTREE_DIR="$ROOT/.worktrees"
PIDS=()
FEATURES=("$@")

if [ ${#FEATURES[@]} -eq 0 ]; then
    echo "Usage: parallel_implement.sh F001 F002 F003 ..."
    exit 1
fi

mkdir -p "$WORKTREE_DIR"

echo "=== Parallel Implementation ==="
echo "Features: ${FEATURES[*]}"
echo ""

for FID in "${FEATURES[@]}"; do
    BRANCH="feature/$(echo "$FID" | tr '[:upper:]' '[:lower:]')"
    WT_PATH="$WORKTREE_DIR/$FID"

    # Clean up existing worktree if present
    if [ -d "$WT_PATH" ]; then
        git worktree remove "$WT_PATH" --force 2>/dev/null || true
    fi

    # Create worktree on new branch
    git worktree add -b "$BRANCH" "$WT_PATH" main 2>/dev/null || {
        echo "✗ Failed to create worktree for $FID"
        continue
    }

    echo ">>> Starting $FID on branch $BRANCH"

    # Run claude -p in the worktree directory (background)
    (
        cd "$WT_PATH"

        FEATURE=$(python3 -c "
import json
with open('features.json') as f:
    features = json.load(f)['features']
match = [f for f in features if f['id'] == '$FID']
if match:
    f = match[0]
    print(f'[{f[\"id\"]}] {f[\"name\"]}: {f[\"description\"]}')
")

        claude -p "Implement this feature for Dynaplan: $FEATURE

Read CLAUDE.md first. Write code and tests. Use ./scripts/run_silent.sh for test commands.
Run tests, commit when passing, update claude-progress.txt." \
            --model sonnet \
            --allowedTools "Read,Write,Edit,Glob,Grep,Bash(cd *),Bash(git *),Bash(./scripts/*),Bash(pytest *),Bash(bun *)" \
            > "$WORKTREE_DIR/$FID.log" 2>&1

        echo "✓ $FID finished (see $WORKTREE_DIR/$FID.log)"
    ) &

    PIDS+=($!)
done

echo ""
echo "=== Waiting for ${#PIDS[@]} agents ==="

FAILED=0
for i in "${!PIDS[@]}"; do
    FID="${FEATURES[$i]}"
    if wait "${PIDS[$i]}"; then
        echo "✓ $FID completed successfully"
    else
        echo "✗ $FID failed (check $WORKTREE_DIR/$FID.log)"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "=== Results ==="
echo "Passed: $((${#FEATURES[@]} - FAILED))/${#FEATURES[@]}"

if [ $FAILED -gt 0 ]; then
    echo "Failed: $FAILED"
fi

echo ""
echo "Next steps:"
echo "  Review each branch:"
for FID in "${FEATURES[@]}"; do
    BRANCH="feature/$(echo "$FID" | tr '[:upper:]' '[:lower:]')"
    echo "    git diff main...$BRANCH"
done
echo "  Merge when ready:"
echo "    git merge feature/<id>"
echo "  Clean up worktrees:"
echo "    git worktree prune"
