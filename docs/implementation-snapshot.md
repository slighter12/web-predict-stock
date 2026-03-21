# Implementation Snapshot

This document is descriptive only. It records the current implementation
surface and must never be used as the source of truth for normative behavior.

## Current Repository Snapshot

- Backend: FastAPI on Python 3.12+
- Frontend: Svelte 5 + Vite + TanStack Svelte Query + ECharts
- Database: PostgreSQL + TimescaleDB
- Modeling: XGBoost and scikit-learn based research workflows
- Data sources: TWSE plus yfinance bootstrap or backfill support
- Research execution: VectorBT with fees and slippage support

## Current Backend Structure

- `backend/app.py`
  - FastAPI app creation
  - middleware registration
  - exception-envelope wiring
  - router include
- `backend/api/`
  - `system.py`
  - `research_runs.py`
  - `data_plane.py`
- `backend/schemas/`
  - `common.py`
  - `runtime.py`
  - `research_runs.py`
  - `data_plane.py`
- `backend/services/`
  - research-run orchestration
  - backtest-engine execution
  - data-plane operations
  - scheduled recovery-drill dispatch
  - scheduled ingestion dispatch
  - operational KPI calculation
  - official lifecycle and important-event crawling
- `backend/repositories/`
  - research-run persistence
  - replay / recovery persistence
  - recovery-drill schedule persistence
  - benchmark-profile persistence
  - ingestion watchlist persistence
  - scheduled ingestion persistence
  - lifecycle / important-event upsert and list
- `backend/runtime/`
  - request-id and run-id handling
  - error-envelope helpers
- `backend/domain/`
  - version-pack payload assembly

## Current API Surface

- `GET /api/v1/system/health`
- `POST /api/v1/research/runs`
- `GET /api/v1/research/runs/{run_id}`
- `GET /api/v1/research/runs`
- `POST /api/v1/data/ingestions`
- `POST /api/v1/data/replays`
- `GET /api/v1/data/replays`
- `POST /api/v1/data/tick-archive-dispatches`
- `GET /api/v1/data/tick-archive-dispatches`
- `POST /api/v1/data/tick-archive-imports`
- `GET /api/v1/data/tick-archives`
- `POST /api/v1/data/tick-replays`
- `GET /api/v1/data/tick-replays`
- `GET /api/v1/data/tick-ops/kpis`
- `GET /api/v1/data/tick-gates/p2`
- `POST /api/v1/data/recovery-drills`
- `GET /api/v1/data/recovery-drills`
- `POST /api/v1/data/recovery-drill-schedules`
- `GET /api/v1/data/recovery-drill-schedules`
- `POST /api/v1/data/benchmark-profiles`
- `GET /api/v1/data/benchmark-profiles`
- `POST /api/v1/data/ingestion-watchlist`
- `GET /api/v1/data/ingestion-watchlist`
- `POST /api/v1/data/ingestion-dispatches`
- `GET /api/v1/data/ops/kpis`
- `POST /api/v1/data/lifecycle-crawls`
- `POST /api/v1/data/important-event-crawls`
- `POST /api/v1/data/lifecycle-records`
- `GET /api/v1/data/lifecycle-records`
- `POST /api/v1/data/important-events`
- `GET /api/v1/data/important-events`

## Current Frontend Surface

- `Research Run Workspace`
  - `ResearchRunForm`
  - `ResearchRunInspector`
  - metrics, validation, signals, and run-registry inspection
- `Data Plane Workspace`
  - `DataIngestionPanel`
  - `ReplayPanel`
  - `TickArchivePanel`
    - post-close tick archive dispatch
    - manual tick archive import
    - tick archive replay
    - `KPI-TICK-*` telemetry display
  - `RecoveryDrillPanel`
    - manual recovery drill execution
    - monthly recovery drill schedule creation
    - recovery trigger-mode and schedule-slot inspection
  - `LifecyclePanel`
  - `ImportantEventPanel`
- Backend-only data-plane endpoints with no dedicated frontend panel yet:
  - `/api/v1/data/benchmark-profiles`
  - `/api/v1/data/ingestion-watchlist`
  - `/api/v1/data/ingestion-dispatches`
  - `/api/v1/data/ops/kpis`
  - `/api/v1/data/tick-gates/p2`
  - `/api/v1/data/lifecycle-crawls`
  - `/api/v1/data/important-event-crawls`

## Current Phase Coverage

### P0

Status: `implemented`

- research-run requests persist successful, rejected, validation-failed, and failed attempts
- research-run responses expose:
  - runtime mode
  - default bundle version
  - effective strategy
  - config sources
  - fallback audit
  - version pack fields
- run-registry lookup exists through:
  - `GET /api/v1/research/runs/{run_id}`
  - `GET /api/v1/research/runs`
- frontend includes a persisted research-run inspector

### P1

Status: `exit-gate implemented; ops instrumentation implemented`

- raw-ingest preservation exists through `raw_ingest_audit.payload_body`
- normalized replay persistence exists through `/api/v1/data/replays`
- recovery-drill persistence exists through `/api/v1/data/recovery-drills`
- recovery-drill schedules exist through `/api/v1/data/recovery-drill-schedules`
- recovery drills persist trigger metadata through:
  - `trigger_mode`
  - `schedule_id`
  - `scheduled_for_date`
- scheduled monthly recovery dispatch exists through:
  - `backend.services.recovery_service.dispatch_due_recovery_drills`
  - `scripts/run_scheduled_recovery_drills.py`
- benchmark-profile registry exists through `/api/v1/data/benchmark-profiles`
- scheduled ingestion watchlist and dispatch exist through:
  - `/api/v1/data/ingestion-watchlist`
  - `/api/v1/data/ingestion-dispatches`
  - `scripts/run_scheduled_ingestion.py`
- lifecycle-record upsert and listing exist through `/api/v1/data/lifecycle-records`
- important-event upsert and listing exist through `/api/v1/data/important-events`
- official lifecycle and important-event crawlers exist through:
  - `/api/v1/data/lifecycle-crawls`
  - `/api/v1/data/important-event-crawls`
  - `scripts/run_lifecycle_crawler.py`
  - `scripts/run_important_event_crawler.py`
- operational KPI reporting exists through `/api/v1/data/ops/kpis`
- `GATE-P1-OPS-001` evaluation currently requires `KPI-DATA-001` to
  `KPI-DATA-005`, `KPI-DATA-007`, and the conditional `KPI-DATA-006/008`
  sample rule defined in `docs/validation-gates.md`
- recovery trading-day delta uses persisted market trading dates from `daily_ohlcv`
- frontend includes a data-plane workspace for manual and scheduled recovery operations
- frontend does not yet expose dedicated panels or API clients for benchmark
  profiles, ingestion watchlist or dispatch management, or official crawler
  triggers

### P2

Status: `exit-gate implemented; ops telemetry implemented`

- `tick_archive_runs`, `tick_archive_objects`, `tick_restore_runs`, and
  `tick_observations` persist the P2 data plane
- tick archive dispatch, manual import, and replay exist through:
  - `/api/v1/data/tick-archive-dispatches`
  - `/api/v1/data/tick-archive-imports`
  - `/api/v1/data/tick-replays`
- tick archive storage currently uses local filesystem `jsonl.gz` objects under
  `var/tick_archives/`
- `GET /api/v1/data/tick-gates/p2` exposes the phase-scoped `GATE-P2-001`
  artifact report
- `GET /api/v1/data/tick-ops/kpis` exposes `KPI-TICK-001` to `KPI-TICK-003`
  with succeeded-run filtering, the current benchmark window policy, and an
  explicit exploratory binding status while `TBD-002` remains open
- benchmark telemetry currently uses only succeeded archive runs, succeeded
  restore runs, persisted `benchmark_profile_id`, and full-day benchmark
  windows capped at `5` compressed GB for the latest succeeded archive run per
  `(trading_date, benchmark_profile_id)`; restore timing uses benchmark-window
  wall-clock duration instead of summed per-object elapsed seconds
- `GET /api/v1/data/tick-gates/p2` evaluates retention policy against the
  latest succeeded archive object's actual `retention_class` and
  `archive_layout_version`, while still exposing the expected baseline values
- manual archive import validates the embedded observation `market` and
  `trading_date` against the submitted metadata before persisting archive
  object metadata
- frontend includes a `TickArchivePanel` in the data-plane workspace

Still not complete for durable `P2-OPS`:

- `TBD-002` remains open, so `KPI-TICK-*` values are still exploratory
  telemetry rather than binding durable qualification
- TWSE TLS verification may still require local CA configuration depending on
  the runtime environment
- full-market dispatch quality depends on the current coverage of
  `symbol_lifecycle_records` or the `daily_ohlcv` fallback, evaluated against
  the requested `trading_date`

Current accepted `P2` constraints and follow-ups:

- archive retention policy is still provisional:
  `TICK_ARCHIVE_RETENTION_CLASS` remains
  `provisional_until_tbd_002_resolved`, so retention evidence is useful for
  telemetry and gate inspection but not yet a durable production baseline
- archive storage is limited to `local_filesystem`; `TickArchiveObject` already
  persists `storage_backend`, but there is no S3/GCS-backed implementation,
  cross-instance sharing, or storage redundancy yet
- symbol resolution falls back to `daily_ohlcv` when lifecycle coverage is
  incomplete; this is acceptable for `P2`, but it can include stale symbols if
  lifecycle events are missing and must not be treated as a formally governed
  investability universe
- list endpoints use fixed `limit` values without cursor or offset pagination;
  current panel scope is recent operational inspection only
- manual upload validates archive content after write/read/parse, not by MIME
  type alone; invalid or mismatched payloads are rejected during import, but
  upload preflight does not enforce a browser-supplied content type contract
- frontend trading-date defaults come from the browser local date input; this
  is acceptable for now because `trading_date` is a user-editable field, but
  operators should treat `Asia/Taipei` as the authoritative market calendar
- `TICK_KPI_TRADING_DAY_WINDOW` is intentionally fixed at `20` trading days so
  KPI history is comparable across runs; changing it currently requires a code
  change
- replay samples with effectively zero benchmark-window wall-clock duration are
  excluded from throughput telemetry rather than coerced into extreme values;
  this is a telemetry hygiene choice, not a replay failure signal
- snapshot parsing does not pre-deduplicate duplicated symbols inside one raw
  payload; current protection relies on replay replacement semantics and the
  normalized storage path rather than parser-side duplicate rejection

Still not complete for `P1-OPS`:

- live observation-window qualification is still required before claiming gate pass
- official feed URLs must still be configured at runtime for automated crawlers

## Current Verification Snapshot

- last updated: `2026-03-21`
- backend test suite:
  - `.venv/bin/python -m pytest -q`
  - result: `133 passed`
- frontend production build:
  - `cd frontend && bun run build`
  - result: `passed (Vite chunk-size warning only)`
- frontend browser smoke test:
  - `agent-browser` against `http://127.0.0.1:5173`
  - result: `passed` for page load, API health rendering, and recovery-drill form validation messages

## Version Pack Status

Currently implemented fields:

- `threshold_policy_version`
- `price_basis_version`
- `benchmark_comparability_gate`
- `comparison_eligibility`

Currently placeholder fields:

- `investability_screening_active`
- `capacity_screening_version`
- `adv_basis_version`
- `missing_feature_policy_version`
- `execution_cost_model_version`
- `split_policy_version`
- `bootstrap_policy_version`
- `ic_overlap_policy_version`

## Current Error Envelope

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "請檢查輸入內容。",
    "details": {
      "fields": []
    }
  },
  "meta": {
    "request_id": "req_abc123",
    "run_id": "run_abc123"
  }
}
```
