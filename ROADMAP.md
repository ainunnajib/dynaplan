# Dynaplan → Production Anaplan Replacement: Complete Roadmap

## Context

Dynaplan has 44 features implemented (1358 tests) covering the core Anaplan paradigm: dimensions, modules, line items, formulas, time/versions, dashboards, ALM, CloudWorks, SCIM, DCA, workflows, and UX pages. However, significant gaps remain versus production Anaplan — most critically the calculation engine (pure Python, single-threaded, ~1000x slower than Hyperblock), incomplete formula language (20 vs 150+ functions), missing execution runtimes for CloudWorks/Pipelines/ALM, and no real connector infrastructure.

This roadmap is designed for **Codex 5.3 AI Agents** to implement autonomously. Each phase is self-contained with clear inputs, outputs, and test criteria. Phases are ordered by dependency — later phases build on earlier ones.

---

## Phase 1: Rust Calculation Engine (Hyperblock Replacement)

**Goal**: Replace the Python formula evaluator with a Rust-based in-memory calculation engine exposed via PyO3 FFI, achieving 100-1000x speedup.

### F045: Rust Engine Core — Sparse Block Storage
**Priority**: P0 | **Est. Tests**: 60 | **Depends on**: None

Create a new Rust crate `dynaplan-engine` with:

- **Sparse block array**: `HashMap<DimensionKey, f64>` where `DimensionKey` is a sorted tuple of dimension member IDs (u128 UUIDs)
- **Block partitioning**: Group cells by line item into `CalculationBlock` structs
- **Memory layout**: Column-oriented storage within blocks for cache-line locality
- **Dimension metadata**: `DimensionDef { id: Uuid, member_count: usize, members: Vec<Uuid> }`
- **Model container**: `ModelState` holding all blocks, dimension defs, and dependency edges

**Files to create**:
```
engine/                          # New top-level Rust workspace
├── Cargo.toml
├── dynaplan-core/
│   ├── src/lib.rs               # Public API
│   ├── src/block.rs             # CalculationBlock, sparse storage
│   ├── src/dimension.rs         # DimensionDef, DimensionKey
│   ├── src/model.rs             # ModelState container
│   └── src/value.rs             # CellValue enum (f64, String, bool)
└── dynaplan-core/Cargo.toml
```

**Test criteria**: Unit tests in Rust — create model with 5 dimensions × 100 members, write/read 100K cells, verify O(1) lookup by dimension key.

---

### F046: Rust Formula Engine — Tokenizer, Parser, Evaluator
**Priority**: P0 | **Est. Tests**: 120 | **Depends on**: F045

Port `backend/app/engine/tokenizer.py`, `parser.py`, `evaluator.py` to Rust:

- **Tokenizer**: Same token types (NUMBER, STRING, BOOLEAN, IDENTIFIER, OPERATOR, etc.)
- **Parser**: Recursive-descent with same precedence (OR < AND < NOT < COMPARISON < +/- < */÷ < ^ < UNARY < PRIMARY)
- **AST nodes**: `enum ASTNode { Number(f64), String(String), Bool(bool), Ident(String), BinaryOp{op,left,right}, UnaryOp{op,operand}, FunctionCall{name, args} }`
- **Evaluator**: Walk AST with context `HashMap<String, CellValue>`, lazy IF evaluation
- **All 20 existing functions**: ABS, ROUND, MIN, MAX, POWER, SQRT, LOG, SUM, AVERAGE, COUNT, IF, AND, OR, NOT, ISBLANK, CONCATENATE, LEFT, RIGHT, LEN, UPPER, LOWER, TRIM, LOOKUP

**Files to create**:
```
engine/dynaplan-core/src/formula/
├── mod.rs
├── tokenizer.rs
├── parser.rs
├── evaluator.rs
└── functions.rs          # Built-in function registry
```

**Test criteria**: Port all 102 formula engine tests from `test_formula.py` to Rust. Verify identical output for every test case.

---

### F047: Rust Dependency Graph — Topo Sort, Partial Recalc, Cycle Detection
**Priority**: P0 | **Est. Tests**: 50 | **Depends on**: F046

Port `backend/app/engine/dependency_graph.py` to Rust:

- **DependencyGraph struct**: `nodes: HashSet<Uuid>`, `deps: HashMap<Uuid, HashSet<Uuid>>`, `dependents: HashMap<Uuid, HashSet<Uuid>>`
- **Kahn's algorithm** for topological sort
- **BFS downstream** for `get_recalc_order(changed: HashSet<Uuid>) -> Vec<Uuid>`
- **DFS cycle detection** returning cycle paths
- **`build_from_formulas`**: Takes `HashMap<Uuid, String>` + reference extractor

**Files to create**:
```
engine/dynaplan-core/src/graph/
├── mod.rs
├── topo_sort.rs
├── cycle_detect.rs
└── recalc.rs
```

**Test criteria**: Port all 42 dependency graph tests. Verify identical ordering, cycle detection results.

---

### F048: Rust Parallel Calculation Engine
**Priority**: P0 | **Est. Tests**: 40 | **Depends on**: F046, F047

The core recalculation runtime:

- **Recalc orchestrator**: Given `changed_cells: Vec<(Uuid, DimensionKey)>`, compute downstream
- **Topological level parallelism**: Group recalc order into levels (nodes at same topo depth). Execute each level in parallel using **rayon** thread pool
- **Block-level parallelism**: Within a level, each `CalculationBlock` runs independently across threads
- **Context builder**: For each formula evaluation, gather referenced values from other blocks
- **SIMD aggregation**: Use `packed_simd` or auto-vectorization for SUM/AVERAGE/COUNT across large dimension arrays

**Files to create**:
```
engine/dynaplan-core/src/calc/
├── mod.rs
├── orchestrator.rs       # Main recalc loop
├── parallel.rs           # Rayon-based level parallelism
├── context.rs            # Build evaluation context per cell
└── aggregation.rs        # Vectorized SUM/AVG/COUNT
```

**Test criteria**: Recalculate 100K cells across 50 line items with dependencies. Verify correctness matches Python engine. Benchmark: must be >100x faster than Python for 100K cells.

---

### F049: PyO3 Bridge — Rust Engine ↔ Python FastAPI
**Priority**: P0 | **Est. Tests**: 30 | **Depends on**: F045-F048

Expose the Rust engine to Python via PyO3:

- **Python module**: `dynaplan_engine` importable from Python
- **Key Python-callable functions**:
  - `load_model(model_json: str) -> ModelHandle` — deserialize model into Rust memory
  - `write_cell(handle, line_item_id, dimension_key, value) -> RecalcResult`
  - `write_cells_bulk(handle, cells: list) -> RecalcResult`
  - `read_cell(handle, line_item_id, dimension_key) -> CellValue`
  - `read_cells(handle, line_item_id, filters: dict) -> list[CellValue]`
  - `evaluate_formula(text: str, context: dict) -> CellValue`
  - `get_recalc_order(handle, changed: list) -> list[str]`
- **Model serialization**: JSON format for model load/unload from DB
- **Integration with FastAPI**: Replace calls in `backend/app/services/cell.py` to use Rust engine when available, fall back to Python engine

**Files to create/modify**:
```
engine/dynaplan-py/                # PyO3 wrapper crate
├── Cargo.toml
├── src/lib.rs
├── src/model_handle.rs
└── src/conversions.rs             # Python <-> Rust type conversions

backend/app/engine/rust_bridge.py  # Python-side import + fallback logic
```

**Modify**: `backend/app/services/cell.py` — add engine selection (Rust if available, else Python)

**Test criteria**: Run all 1358 existing backend tests with Rust engine active. All must pass identically.

---

### F050: Spread & Aggregation in Rust
**Priority**: P1 | **Est. Tests**: 40 | **Depends on**: F048, F049

Port `backend/app/engine/spread.py` and aggregation logic:

- **Spread methods**: even, proportional, weighted, manual — vectorized with SIMD
- **Summary methods**: sum, average, min, max, none, formula
- **Hierarchy aggregation**: Bottom-up tree traversal with parallel leaf-to-root computation
- **Expose via PyO3**: `spread_top_down(handle, ...)`, `aggregate_bottom_up(handle, ...)`

**Files to create**:
```
engine/dynaplan-core/src/spread/
├── mod.rs
├── top_down.rs
├── bottom_up.rs
└── hierarchy.rs
```

**Modify**: `backend/app/services/planning.py` — use Rust spread/aggregate when available

---

## Phase 2: Complete Formula Language (130+ Missing Functions)

**Goal**: Reach parity with Anaplan's 150+ formula functions.

### F051: Time Functions (20 functions)
**Priority**: P1 | **Est. Tests**: 60 | **Depends on**: F046

Add to Rust formula engine:
- `YEARVALUE`, `MONTHVALUE`, `QUARTERVALUE`, `WEEKVALUE`
- `CURRENTPERIODSTART`, `CURRENTPERIODEND`, `PERIODSTART`, `PERIODEND`
- `TIMESUM`, `TIMEAVERAGE`, `TIMECOUNT`
- `LAG(expr, n)`, `LEAD(expr, n)`, `OFFSET(expr, n)`
- `MOVINGSUM(expr, n)`, `MOVINGAVERAGE(expr, n)`
- `CUMULATE(expr)`, `PREVIOUS(expr)`, `NEXT(expr)`
- `INPERIOD(date, period)`, `HALFYEARVALUE`

### F052: Lookup & Cross-Module Functions (15 functions)
**Priority**: P1 | **Est. Tests**: 45 | **Depends on**: F046

- `FINDITEM(list, name)` — find dimension member by name
- `ITEM(list)` — current dimension member in context
- `PARENT(item)`, `CHILDREN(item)`, `ISLEAF(item)`, `ISANCESTOR(a, b)`
- `SELECT(source, mapping)` — cross-dimensional lookup (Anaplan's core mapping function)
- `SUM(source, mapping)`, `LOOKUP(source, mapping)` — mapped aggregation
- `NAME(item)`, `CODE(item)` — member properties
- `RANK(expr, dimension)`, `RANKLIST(expr, dimension, n)`
- `COLLECT(expr, dimension)` — gather values across dimension
- `POST(target, value)` — write to another line item (trigger action)

### F053: Text & Conversion Functions (15 functions)
**Priority**: P2 | **Est. Tests**: 30 | **Depends on**: F046

- `MID(text, start, len)`, `FIND(search, text)`, `SUBSTITUTE(text, old, new)`
- `TEXT(number, format)`, `VALUE(text)` — number↔text conversion
- `TEXTLIST(list_member)` — dimension member to text
- `MAKETEXT(pattern, args...)` — formatted text builder
- `YEARTODATE()`, `MONTHTODATE()` — period-aware text
- `DATE(year, month, day)`, `DATEVALUE(text)`, `TODAY()`
- `ROUND(n, decimals)`, `CEILING(n)`, `FLOOR(n)`, `MOD(a, b)`, `SIGN(n)`

### F054: Advanced Aggregation & Statistical Functions (10 functions)
**Priority**: P2 | **Est. Tests**: 25 | **Depends on**: F046

- `SUMIF(range, criteria)`, `COUNTIF(range, criteria)`, `AVERAGEIF(range, criteria)`
- `MEDIAN(range)`, `STDEV(range)`, `VARIANCE(range)`
- `PERCENTILE(range, k)`, `LARGE(range, k)`, `SMALL(range, k)`
- `GROWTH(known_y, known_x, new_x)` — linear regression

### F055: Summary Method Expansion
**Priority**: P1 | **Est. Tests**: 20 | **Depends on**: F050

Add missing summary methods to LineItem model and Rust engine:
- `OPENING_BALANCE` — value at start of period
- `CLOSING_BALANCE` — value at end of period (default for balance sheet items)
- `WEIGHTED_AVERAGE` — weighted by another line item
- `FORMULA` — use formula instead of automatic aggregation
- `FIRST`, `LAST` — first/last non-blank value in period

**Modify**: `backend/app/models/module.py` (SummaryMethod enum), Rust `spread/` module

---

## Phase 3: Model Structure Gaps

**Goal**: Fill structural gaps that prevent modeling real-world Anaplan workspaces.

### F056: Numbered Lists (Auto-Increment Dimensions)
**Priority**: P1 | **Est. Tests**: 25 | **Depends on**: None

- Add `DimensionType.numbered` to enum
- Auto-generate integer item codes on insert (1, 2, 3...)
- Support `ITEMCOUNT()` function
- Max items configurable per numbered list
- Common use: transactional data (invoice lines, journal entries)

**Modify**: `backend/app/models/dimension.py`, `backend/app/services/dimension.py`

### F057: Composite Dimensions (Multi-Dimensional Intersections)
**Priority**: P2 | **Est. Tests**: 30 | **Depends on**: None

- New model: `CompositeDimension` — references 2+ source dimensions
- Auto-generate intersection members (Product × Region)
- Sparse: only create intersections that have data
- Support in formula context and grid pivoting

**Files**: `backend/app/models/composite_dimension.py`, service, schema, API, tests

### F058: Saved Views (User-Specific Grid Configurations)
**Priority**: P2 | **Est. Tests**: 20 | **Depends on**: None

- New model: `SavedView` — user_id, module_id, view_config (JSON: row dims, col dims, filters, sort)
- CRUD API for views
- "Set as default" per user per module
- Frontend: save/load view selector in grid toolbar

**Files**: `backend/app/models/saved_view.py`, service, schema, API, frontend component

### F059: Applies-To Normalization (Junction Table)
**Priority**: P1 | **Est. Tests**: 15 | **Depends on**: None

Replace `LineItem.applies_to_dimensions` JSON column with proper junction table:
- New model: `LineItemDimension(line_item_id, dimension_id, sort_order)`
- Migration: read existing JSON, populate junction table, drop JSON column
- Update all services that read `applies_to_dimensions`
- Enables efficient "which line items apply to dimension X?" queries

**Modify**: `backend/app/models/module.py`, `backend/app/services/module.py`, `backend/app/services/cell.py`

### F060: Version Dimension Integration
**Priority**: P1 | **Est. Tests**: 20 | **Depends on**: F059

- Add `version_id` FK to `CellValue` model (or make version a proper applies-to dimension)
- Actuals/forecast switchover logic: query cells where period < switchover from actuals version, >= from forecast version
- Version comparison operates on same line item across version dimension
- Migrate existing cells to include version context

**Modify**: `backend/app/models/cell.py`, `backend/app/services/cell.py`, `backend/app/services/version.py`

### F061: Model Calendar Enhancements
**Priority**: P2 | **Est. Tests**: 20 | **Depends on**: None

- Weekly periods (ISO weeks + custom week patterns)
- 4-4-5, 4-5-4, 5-4-4 retail calendar patterns
- Half-year periods (H1/H2)
- Fiscal calendar persistence to DB (currently rebuilt on demand)
- Calendar-aware formula functions (INPERIOD, PERIODOFFSET)

**Modify**: `backend/app/engine/time_calendar.py`, `backend/app/models/time_range.py`

---

## Phase 4: Execution Runtimes (CloudWorks, Pipelines, ALM)

**Goal**: Turn CRUD shells into working execution engines.

### F062: Background Job Executor
**Priority**: P0 | **Est. Tests**: 25 | **Depends on**: None

Foundation for CloudWorks scheduler and Pipeline runner:

- **APScheduler integration** for cron-based triggers
- **Async task worker** using `asyncio.Queue` + worker pool
- **Job state machine**: pending → queued → running → completed/failed/retrying
- **Retry logic**: exponential backoff, max retries, dead letter queue
- **Job registry**: track active jobs, cancel support, timeout enforcement

**Files to create**:
```
backend/app/engine/job_executor.py    # Core executor
backend/app/engine/job_scheduler.py   # APScheduler wrapper
backend/app/engine/job_registry.py    # Active job tracking
```

### F063: CloudWorks Connector SDK
**Priority**: P1 | **Est. Tests**: 40 | **Depends on**: F062

Real connector implementations:
- **Base class**: `CloudWorksConnector(config: dict)` with `read() -> DataFrame` and `write(data: DataFrame)`
- **S3 connector**: boto3-based, supports CSV/Parquet, auth via access key or IAM role
- **Database connector**: SQLAlchemy-based, supports PostgreSQL/MySQL/SQLite, custom SQL queries
- **SFTP connector**: paramiko-based, file upload/download
- **HTTP/REST connector**: httpx-based, configurable auth (API key, OAuth, basic)
- **File connector**: Local filesystem read/write (for dev/testing)

**Files to create**:
```
backend/app/connectors/
├── __init__.py
├── base.py               # Abstract ConnectorBase
├── s3.py
├── database.py
├── sftp.py
├── http_rest.py
└── local_file.py
```

**Modify**: `backend/app/services/cloudworks.py` — wire run execution to connector SDK

### F064: CloudWorks Scheduler Activation
**Priority**: P1 | **Est. Tests**: 20 | **Depends on**: F062, F063

- Parse CRON expressions and register with APScheduler
- On schedule trigger: create CloudWorksRun, execute connector, update status
- Notification webhooks on completion/failure
- Schedule enable/disable without deleting

**Modify**: `backend/app/services/cloudworks.py`, `backend/app/api/cloudworks.py`

### F065: Pipeline Step Execution Runtime
**Priority**: P1 | **Est. Tests**: 35 | **Depends on**: F062, F063

Real step execution:
- **Source step**: Use connector SDK to read data into in-memory DataFrame (Pandas/Polars)
- **Transform step**: Column rename, type cast, expression evaluation, join
- **Filter step**: Row filtering with expression syntax
- **Map step**: Value mapping (lookup table replacement)
- **Aggregate step**: Group-by aggregation (sum, count, avg, min, max)
- **Publish step**: Write DataFrame to model cells via bulk write API
- **Step chaining**: Output of step N is input to step N+1
- **Logging**: records_in/records_out per step, error capture

**Files to create**:
```
backend/app/engine/pipeline_runtime/
├── __init__.py
├── executor.py            # Step-by-step execution
├── transforms.py          # Transform/filter/map/aggregate handlers
├── config_parser.py       # Parse step config JSON into operations
└── dataframe_utils.py     # DataFrame helpers
```

**Modify**: `backend/app/services/pipeline.py` — wire trigger to runtime

### F066: ALM Promotion Engine
**Priority**: P1 | **Est. Tests**: 30 | **Depends on**: None

Real model promotion:
- **Deep structural diff**: Compare dimension structures, module schemas, line item definitions, formulas between source and target environments
- **Change detection**: Added/removed/modified dimensions, items, modules, line items
- **Conflict detection**: If target was modified since last sync, flag conflicts
- **Merge strategy**: Additive (add new, keep existing), Replace (overwrite target), Manual (flag each conflict)
- **Promotion execution**: Apply structural changes to target model, copy cell data for new structures
- **Rollback**: Store pre-promotion snapshot, restore on failure

**Modify**: `backend/app/services/alm.py`

---

## Phase 5: Data Hub & Enterprise Integration

### F067: Anaplan Data Hub (Staging Area)
**Priority**: P2 | **Est. Tests**: 30 | **Depends on**: F063

- New model: `DataHubTable` — staging tables for ETL before loading into models
- Schema-on-write: define columns with types
- Import from connectors into hub tables
- Transform/clean in hub before publishing to model
- Lineage tracking: which hub table feeds which model/module

**Files**: `backend/app/models/data_hub.py`, service, schema, API, frontend

### F068: Anaplan Connect (Bulk API CLI)
**Priority**: P2 | **Est. Tests**: 20 | **Depends on**: F049

- CLI tool (`dynaplan-cli`) for bulk operations
- Commands: `import`, `export`, `run-process`, `run-pipeline`
- Auth: API key from F019
- Batch mode: read operations from YAML/JSON file
- Progress output for long operations

**Files**: `cli/` directory with Click-based CLI

---

## Phase 6: Scale, Security & Multi-Tenancy

### F069: Workspace Quotas & Cell Limits
**Priority**: P1 | **Est. Tests**: 15 | **Depends on**: None

- `WorkspaceQuota` model: max_models, max_cells_per_model, max_dimensions_per_model, storage_limit_mb
- Enforce limits on create/write operations
- Usage tracking dashboard in frontend

### F070: Data Encryption at Rest
**Priority**: P2 | **Est. Tests**: 10 | **Depends on**: None

- Per-model encryption key management
- Encrypt cell values before DB write, decrypt on read
- Key rotation support
- Integration with external KMS (AWS KMS, Vault)

### F071: IP Allowlisting & Certificate Auth
**Priority**: P2 | **Est. Tests**: 15 | **Depends on**: None

- Workspace-level IP allowlist
- mTLS certificate-based API authentication
- Rate limiting per API key

### F072: PostgreSQL Migration
**Priority**: P1 | **Est. Tests**: 10 | **Depends on**: None

- Alembic migrations for SQLite → PostgreSQL
- Connection pool management (asyncpg)
- Read replicas for query scaling
- Update `conftest.py` with PostgreSQL test container

---

## Phase 7: Advanced UX & Frontend

### F073: New UX App Builder
**Priority**: P2 | **Est. Tests**: 20 (frontend) | **Depends on**: None

- Custom app pages with navigation tree
- Interactive card types: grid, chart, button, filter, text
- Card-to-card linking (click product in grid → filter chart)
- Page-level context selectors propagating to all cards
- Responsive mobile layout

### F074: Conditional Cell Formatting
**Priority**: P2 | **Est. Tests**: 15 | **Depends on**: None

- Rule-based formatting: if value > threshold → color/bold/icon
- Format rules stored per line item or per module
- Supports: background color, text color, bold, italic, number format, icon
- Frontend: color picker in grid settings

### F075: Grid Performance at Scale
**Priority**: P1 | **Est. Tests**: 15 | **Depends on**: F049

- Server-side pagination for grids with >100K cells
- Lazy loading dimension members in pivot controls
- WebSocket push for cell updates (replace polling)
- Client-side caching with invalidation

---

## Phase 8: Monitoring, Observability & DevOps

### F076: Metrics & Health Dashboard
**Priority**: P2 | **Est. Tests**: 10 | **Depends on**: F049

- Engine metrics: calc time per model, cache hit ratio, memory usage
- API metrics: request latency, error rate, active users
- Integration metrics: CloudWorks run success rate, pipeline throughput
- Prometheus-compatible `/metrics` endpoint
- Grafana dashboard templates

### F077: Horizontal Scaling
**Priority**: P2 | **Est. Tests**: 10 | **Depends on**: F072, F049

- Stateless API servers behind load balancer
- Redis for session state, pub/sub, cache
- Model state pinned to engine nodes (sticky sessions or shared memory)
- Kubernetes deployment manifests

---

## Implementation Order (Dependency-Sorted)

```
WAVE 1 (Foundation — no dependencies):
  F045 F046 F047 F056 F059 F062 F069 F072

WAVE 2 (Depends on Wave 1):
  F048 (needs F046, F047)
  F049 (needs F045-F048)
  F050 (needs F048, F049)
  F063 (needs F062)
  F066 (needs nothing, can parallel)

WAVE 3 (Depends on Wave 2):
  F051 F052 F053 F054 (need F046)
  F055 (needs F050)
  F060 (needs F059)
  F064 (needs F062, F063)
  F065 (needs F062, F063)

WAVE 4 (Depends on Wave 3):
  F057 F058 F061 F067 F068 F070 F071 F073 F074 F075 F076 F077
```

## Agent Parallelization Strategy

Each wave should be run as parallel agents:
- **Wave 1**: 8 agents in isolated worktrees
- **Wave 2**: 5 agents (F048 must wait for F046+F047; F049 must wait for F045-F048)
- **Wave 3**: 8 agents (F051-F054 can all run in parallel)
- **Wave 4**: 12 agents (all independent)

Integration after each wave: merge worktrees, run full test suite, fix conflicts, commit.

## Test Strategy

- **Rust tests**: Each Rust module has `#[cfg(test)]` unit tests + integration tests in `tests/`
- **Python integration tests**: All existing 1358 tests must continue passing after Rust bridge
- **Benchmark suite**: `cargo bench` for engine performance (target: 100K cells recalc < 100ms)
- **Frontend tests**: Vitest for new components
- **E2E tests**: Playwright for critical flows (import → calculate → export)

## Total Scope

| Phase | Features | Est. Tests |
|-------|----------|-----------|
| Phase 1: Rust Engine | F045-F050 | 340 |
| Phase 2: Formula Language | F051-F055 | 180 |
| Phase 3: Model Structure | F056-F061 | 130 |
| Phase 4: Execution Runtimes | F062-F066 | 150 |
| Phase 5: Data Hub & CLI | F067-F068 | 50 |
| Phase 6: Scale & Security | F069-F072 | 50 |
| Phase 7: Advanced UX | F073-F075 | 50 |
| Phase 8: Observability | F076-F077 | 20 |
| **Total** | **F045-F077 (33 features)** | **~970 new tests** |

Combined with existing 1358 tests → **~2328 total tests** across Python + Rust.
