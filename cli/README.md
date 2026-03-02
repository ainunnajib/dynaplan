# Dynaplan CLI

`dynaplan-cli` provides API-key-based bulk operations for Dynaplan.

## Commands

- `import`
- `export`
- `run-process`
- `run-pipeline`
- `batch`

## Auth

Set API key via `--api-key` or `DYNAPLAN_API_KEY`.

## Examples

```bash
dynaplan-cli --base-url http://localhost:8000 --api-key "$DYNAPLAN_API_KEY" \
  import --module-id <module-id> ./data.csv

dynaplan-cli --base-url http://localhost:8000 --api-key "$DYNAPLAN_API_KEY" \
  export --module-id <module-id> --format csv --output ./module.csv

dynaplan-cli --base-url http://localhost:8000 --api-key "$DYNAPLAN_API_KEY" \
  run-process --process-id <process-id>

dynaplan-cli --base-url http://localhost:8000 --api-key "$DYNAPLAN_API_KEY" \
  run-pipeline --pipeline-id <pipeline-id>

dynaplan-cli --base-url http://localhost:8000 --api-key "$DYNAPLAN_API_KEY" \
  batch ./operations.yaml
```
