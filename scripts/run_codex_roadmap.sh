#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Dynaplan Roadmap Executor — runs Codex CLI headless overnight
# Usage:
#   export OPENAI_API_KEY="sk-..."
#   nohup ./scripts/run_codex_roadmap.sh > codex-run.log 2>&1 &
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

REPO_DIR="/Users/ainunnajib/dynaplan"
cd "$REPO_DIR"
LOG_DIR="codex-logs/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOG_DIR"

# ── Prompt template (FEATURE_ID gets replaced per feature) ────
read -r -d '' PROMPT_TEMPLATE << 'PROMPT_EOF' || true
You are implementing feature FEATURE_ID for the Dynaplan project.

1. Read ROADMAP.md for the full specification of FEATURE_ID
2. Read CLAUDE.md for project conventions
3. Read claude-progress.txt for current status
4. Follow existing patterns:
   - Models: backend/app/models/ (SQLAlchemy async, UUID PKs)
   - Services: backend/app/services/ (async, db: AsyncSession)
   - APIs: backend/app/api/ (FastAPI routers)
   - Schemas: backend/app/schemas/ (Pydantic v2)
   - Tests: backend/tests/test_{name}.py (pytest-asyncio)
   - Frontend: frontend/src/components/{name}/ (React+TS+Tailwind)
5. For Rust features (F045-F050): create under engine/ directory with Cargo workspace
6. Register new routers in backend/app/main.py
7. Register new models in backend/app/models/__init__.py
8. Run tests: cd backend && .venv/bin/python -m pytest -x --tb=short -q
9. Run type check: cd frontend && bun tsc --noEmit
10. ALL tests must pass before you finish.

IMPORTANT constraints:
- Python 3.9 compat: use Optional[str] not str|None, List from typing not list[]
- SQLite test DB uses file-backed NullPool (not in-memory StaticPool)
- Do NOT add app.include_router() in test files — main.py handles registration
- Use selectinload() for async SQLAlchemy relationship loading
- Dimensions: POST /models/{model_id}/dimensions (not POST /dimensions)
- Modules: POST /models/{model_id}/modules (not POST /modules)
PROMPT_EOF

# ── Run a single feature sequentially ─────────────────────────
run_feature() {
  local fid="$1"
  local prompt="${PROMPT_TEMPLATE//FEATURE_ID/$fid}"
  echo "[$(date '+%H:%M:%S')] Starting $fid" | tee -a "$LOG_DIR/progress.log"

  local start_time=$SECONDS
  codex exec --full-auto \
    -o "$LOG_DIR/${fid}-result.txt" \
    "$prompt" \
    > "$LOG_DIR/${fid}-stdout.log" 2>&1

  local rc=$?
  local elapsed=$(( SECONDS - start_time ))
  local mins=$(( elapsed / 60 ))

  if [ $rc -eq 0 ]; then
    echo "[$(date '+%H:%M:%S')] ✓ $fid completed (${mins}m)" | tee -a "$LOG_DIR/progress.log"
    # Commit this feature
    git add -A
    git commit -m "Implement $fid

Co-Authored-By: OpenAI Codex <noreply@openai.com>" || true
  else
    echo "[$(date '+%H:%M:%S')] ✗ $fid FAILED exit=$rc (${mins}m)" | tee -a "$LOG_DIR/progress.log"
  fi
  return 0  # Don't abort the whole script on one failure
}

# ── Run a wave of features sequentially ───────────────────────
run_wave() {
  local wave_num="$1"
  shift
  local features=("$@")
  echo "" | tee -a "$LOG_DIR/progress.log"
  echo "═══════════════════════════════════════" | tee -a "$LOG_DIR/progress.log"
  echo "  WAVE $wave_num — ${#features[@]} features" | tee -a "$LOG_DIR/progress.log"
  echo "═══════════════════════════════════════" | tee -a "$LOG_DIR/progress.log"

  for f in "${features[@]}"; do
    run_feature "$f"
  done

  # Push after each wave
  git push || true
  echo "[$(date '+%H:%M:%S')] Wave $wave_num pushed to remote" | tee -a "$LOG_DIR/progress.log"
}

# ── Preflight checks ─────────────────────────────────────────
if ! command -v codex &> /dev/null; then
  echo "ERROR: codex CLI not found. Install: npm install -g @openai/codex"
  exit 1
fi

echo "Dynaplan Roadmap Executor" | tee "$LOG_DIR/progress.log"
echo "Started: $(date)" | tee -a "$LOG_DIR/progress.log"
echo "Logs: $LOG_DIR" | tee -a "$LOG_DIR/progress.log"

# ══════════════════════════════════════════════════════════════
# WAVE 1 — SKIPPED (already completed and pushed)
# ══════════════════════════════════════════════════════════════
echo "" | tee -a "$LOG_DIR/progress.log"
echo "WAVE 1 — SKIPPED (already completed)" | tee -a "$LOG_DIR/progress.log"

# ══════════════════════════════════════════════════════════════
# WAVE 2 — SKIPPED (already completed and pushed)
# ══════════════════════════════════════════════════════════════
echo "WAVE 2 — SKIPPED (already completed)" | tee -a "$LOG_DIR/progress.log"

# ══════════════════════════════════════════════════════════════
# WAVE 3 — Resume from F055 (F051-F054 already done)
# ══════════════════════════════════════════════════════════════
run_wave 3 F055 F060 F064 F065

# ══════════════════════════════════════════════════════════════
# WAVE 4 — Final features
# ══════════════════════════════════════════════════════════════
run_wave 4 F057 F058 F061 F067 F068 F070 F071 F073 F074 F075 F076 F077

# ── Summary ───────────────────────────────────────────────────
echo "" | tee -a "$LOG_DIR/progress.log"
echo "═══════════════════════════════════════" | tee -a "$LOG_DIR/progress.log"
echo "  ALL WAVES COMPLETE" | tee -a "$LOG_DIR/progress.log"
echo "  Finished: $(date)" | tee -a "$LOG_DIR/progress.log"
echo "═══════════════════════════════════════" | tee -a "$LOG_DIR/progress.log"

# Count successes/failures
success=$(grep -c "✓" "$LOG_DIR/progress.log" || true)
failed=$(grep -c "✗" "$LOG_DIR/progress.log" || true)
echo "Results: $success succeeded, $failed failed" | tee -a "$LOG_DIR/progress.log"
echo "Detailed logs: $LOG_DIR" | tee -a "$LOG_DIR/progress.log"
