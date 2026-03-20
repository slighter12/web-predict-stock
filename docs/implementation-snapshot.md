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
  profiles, ingestion watchlist or dispatch management, ops KPI reporting, or
  official crawler triggers

Still not complete for `P1-OPS`:

- live observation-window qualification is still required before claiming gate pass
- official feed URLs must still be configured at runtime for automated crawlers

## Current Verification Snapshot

- last updated: `2026-03-20`
- backend test suite:
  - `.venv/bin/python -m pytest -q`
  - result: `96 passed`
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
