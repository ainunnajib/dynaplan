---
name: implement-feature
description: Implement a feature from features.json by ID
disable-model-invocation: true
---
Implement the feature: $ARGUMENTS

1. Read `claude-progress.txt` to understand current state
2. Read `features.json` to find the feature details
3. Use Plan Mode to design the implementation
4. Implement the feature incrementally
5. Write tests and run them: `pytest -x --tb=short` (backend) or `bun test --bail` (frontend)
6. Run linters: `ruff check .` (backend) or `bun lint` (frontend)
7. Commit with descriptive message
8. Update the feature status in `features.json` to "done"
9. Update `claude-progress.txt` with what was completed
