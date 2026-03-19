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
- `backend/repositories/`
  - research-run persistence
  - replay / recovery persistence
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
  - `LifecyclePanel`
  - `ImportantEventPanel`

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

Status: `partial`

- raw-ingest preservation exists through `raw_ingest_audit.payload_body`
- normalized replay persistence exists through `/api/v1/data/replays`
- recovery-drill persistence exists through `/api/v1/data/recovery-drills`
- lifecycle-record upsert and listing exist through `/api/v1/data/lifecycle-records`
- important-event upsert and listing exist through `/api/v1/data/important-events`
- frontend includes a data-plane workspace for manual operations

Still not complete for `P1`:

- no scheduled recovery drills
- no operational KPI collection for `P1-OPS`
- no official automated lifecycle or important-event crawlers
- trading-day delta remains a simplified calendar-day approximation

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
