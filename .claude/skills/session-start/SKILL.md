---
name: session-start
description: Start a new development session by reading progress and picking next task
disable-model-invocation: true
---
Start a new autonomous development session:

1. Read `claude-progress.txt` to understand what's been done
2. Read `features.json` to see all features and their status
3. Run `git log --oneline -20` to see recent work
4. Run tests to verify current state: backend `cd backend && pytest -x --tb=short`, frontend `cd frontend && bun test --bail`
5. Pick the next pending P0 feature (or highest priority pending feature)
6. Report what you'll work on and your plan
