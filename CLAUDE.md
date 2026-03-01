# Dynaplan - Enterprise Planning Platform

## Overview
Dynaplan is an open-source replacement for Anaplan — a connected planning platform with multidimensional modeling, financial planning, scenario analysis, and collaborative workflows.

## Tech Stack
- **Frontend**: Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy, Alembic
- **Database**: PostgreSQL (primary), Redis (caching/sessions)
- **Calculation Engine**: Python with NumPy/Pandas for multidimensional modeling
- **Auth**: NextAuth.js with JWT
- **Testing**: pytest (backend), vitest (frontend)

## Build & Test Commands
- Frontend: `cd frontend && bun install && bun dev` (port 3000)
- Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload` (port 8000)
- Frontend tests: `cd frontend && bun test --bail`
- Backend tests: `cd backend && pytest -x --tb=short`
- Lint frontend: `cd frontend && bun lint`
- Lint backend: `cd backend && ruff check .`
- Type check: `cd frontend && bun tsc --noEmit`

## IMPORTANT Workflow Rules
- YOU MUST read `claude-progress.txt` at the start of every session
- YOU MUST update `claude-progress.txt` before ending any session
- Work on ONE feature at a time, commit after each
- Never mark a feature done without passing tests
- Use subagents for research tasks to preserve main context

## Backpressure (CRITICAL — read this)
YOU MUST use `./scripts/run_silent.sh` for ALL test, lint, and build commands.
NEVER run pytest, bun test, ruff, tsc, or bun lint directly — always wrap them.

```bash
# CORRECT — backpressure: ✓ or ✗ + filtered output
./scripts/run_silent.sh "backend tests" "cd backend && pytest -x --tb=short -q"
./scripts/run_silent.sh "frontend tests" "cd frontend && bun test --bail"
./scripts/run_silent.sh "lint backend" "cd backend && ruff check ."
./scripts/run_silent.sh "lint frontend" "cd frontend && bun lint"
./scripts/run_silent.sh "type check" "cd frontend && bun tsc --noEmit"

# Run ALL checks at once:
./scripts/test_all.sh

# WRONG — wastes context with 200+ lines of output
cd backend && pytest        # ← NEVER do this
cd frontend && bun test     # ← NEVER do this
```

Why: A single pytest run can dump 200+ lines. That's 2-3% of your context window
wasted on info that could be "✓ backend tests (5 passed)". Over a session with
10+ test runs, that's 20-30% of context gone to noise. Backpressure keeps you sharp.

## Code Style
- Python: PEP 8, type hints on all function signatures, async by default for API endpoints
- TypeScript: strict mode, prefer server components, use `use client` only when needed
- SQL: use SQLAlchemy ORM, never raw SQL in application code
- API: RESTful with consistent error responses `{"error": string, "detail": string}`
- Components: one component per file, colocate styles

## Architecture Decisions
- Multidimensional model engine runs server-side in Python (not in browser)
- Frontend is thin client — all calculations happen on backend
- Models are stored as versioned JSON schemas in the database
- Real-time collaboration via WebSocket (FastAPI WebSocket + Redis pub/sub)
- Module/line item structure mirrors Anaplan's paradigm but with modern UX

## Git Conventions
- Branch: `feature/<name>`, `fix/<name>`
- Commits: imperative mood, concise ("Add model dimension CRUD", not "Added stuff")
- PR per feature, squash merge to main

@features.json
