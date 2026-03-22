# Implementation Snapshot

This document is descriptive only. It records the current implementation
surface and should not be used as the source of truth for normative behavior.
Use `docs/research-spec.md`, `docs/plan.md`, and `docs/validation-gates.md`
for rules, sequencing, and gate truth conditions.

## Snapshot Scope

- snapshot date: `2026-03-22`
- verification evidence in this document is the latest recorded evidence, not a
  fresh execution performed during this document-only update
- status terms used below:
  - `implemented`: usable backend surface exists and the phase area is no
    longer just a placeholder
  - `implemented structurally`: the structural API and persistence surface
    exists, but durable operational qualification or external integration is
    still pending
  - `partial`: meaningful foundation exists, but the phase is not fully closed
    or still lacks part of the intended operating surface
  - `pending`: planned work, durable qualification, or production-hardening
    still remains open

## Phase Status Summary

| Phase | Status | Current reading |
| --- | --- | --- |
| `P0` | `implemented` | research runs, runtime metadata, config-source persistence, and run registry exist |
| `P1` | `implemented` | daily ingest, replay, recovery drills, scheduled recovery, and ops KPI surfaces exist |
| `P2` | `implemented` | tick archive dispatch, import, replay, KPI, and gate surfaces exist, but storage policy is still provisional |
| `P3` | `implemented` | tradability-state persistence, `GATE-P3-001`, and micro KPI telemetry for `GATE-P3-OPS-001` exist |
| `P4` | `partial` | comparison-governance metadata exists, but the roadmap phase is not fully closed |
| `P5` | `partial` | execution and comparison-alignment foundations exist, but durable policy qualification is still pending |
| `P6` | `partial` | shared tabular model-family contract exists for several tree-based families, but broader model expansion is still incomplete |
| `P7` | `implemented structurally` | external signal, factor catalog, and gate foundations exist |
| `P8` | `implemented structurally` | clustering, peer inference, and gate foundations exist |
| `P9` | `implemented structurally` | simulation-order, readback, and gate foundations exist, but platform baseline remains open |
| `P10` | `implemented structurally` | guarded live-stub controls and gate foundations exist, but no real broker adapter is implemented |
| `P11` | `implemented structurally` | adaptive profile and training-run lifecycle exists, but no integrated RL backend exists |

## Implemented Today

### Core Repository Surface

- Backend stack:
  - FastAPI on Python `3.12+`
  - PostgreSQL plus TimescaleDB persistence
- Frontend stack:
  - Svelte `5`
  - Vite
  - TanStack Svelte Query
  - ECharts
- Research execution stack:
  - VectorBT-based research execution
  - XGBoost plus scikit-learn based workflows

### Implemented Backend Areas

#### System And Research Runs

- `GET /api/v1/health`
- `GET /api/v1/system/health`
- `POST /api/v1/backtest`
- `POST /api/v1/research/runs`
- `GET /api/v1/research/runs/{run_id}`
- `GET /api/v1/research/runs`
- `GET /api/v1/research/gates/p3`
- `GET /api/v1/research/micro-kpis`
- `GET /api/v1/research/gates/p7`
- `GET /api/v1/research/gates/p8`
- `GET /api/v1/research/gates/p9`
- `GET /api/v1/research/gates/p10`
- `GET /api/v1/research/gates/p11`
- `POST /api/v1/research/adaptive-profiles`
- `GET /api/v1/research/adaptive-profiles`
- `POST /api/v1/research/adaptive-training-runs`
- `GET /api/v1/research/adaptive-training-runs`

Implemented behavior:

- research-run requests persist successful, rejected, validation-failed, and
  failed attempts
- runtime metadata, config sources, fallback audit, and version-pack fields are
  persisted on runs
- tradability summaries now persist on run records and are used by the `P3`
  gate and micro KPI surfaces
- research execution supports the shared tabular training-output contract for
  `xgboost`, `random_forest`, and `extra_trees`

#### Data Plane

Daily ingestion and recovery:

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

Implemented behavior:

- raw-ingest preservation exists through `raw_ingest_audit.payload_body`
- normalized replay persistence exists through `/api/v1/data/replays`
- recovery drills persist trigger metadata, including `trigger_mode`,
  `schedule_id`, and `scheduled_for_date`
- scheduled monthly recovery dispatch exists through
  `backend.services.recovery_service.dispatch_due_recovery_drills` and
  `scripts/run_scheduled_recovery_drills.py`
- scheduled ingestion watchlist and dispatch exist through
  `/api/v1/data/ingestion-watchlist`,
  `/api/v1/data/ingestion-dispatches`, and
  `scripts/run_scheduled_ingestion.py`
- lifecycle and important-event records support both direct upsert and official
  crawler ingestion

Tick archive and market-universe support:

- `POST /api/v1/data/tick-archive-dispatches`
- `GET /api/v1/data/tick-archive-dispatches`
- `POST /api/v1/data/tick-archive-imports`
- `GET /api/v1/data/tick-archives`
- `POST /api/v1/data/tw-company-crawls`
- `GET /api/v1/data/tw-company-profiles`
- `POST /api/v1/data/tick-replays`
- `GET /api/v1/data/tick-replays`
- `GET /api/v1/data/tick-ops/kpis`
- `GET /api/v1/data/tick-gates/p2`

Implemented behavior:

- `tick_archive_runs`, `tick_archive_objects`, `tick_restore_runs`, and
  `tick_observations` persist the P2 data plane
- manual archive import validates embedded `market` and `trading_date` against
  submitted metadata before persisting archive metadata
- tick archive objects can persist optional Google Drive mirror metadata when
  `GOOGLE_DRIVE_TICK_ARCHIVE_ROOT` is configured
- active TW company universe snapshots exist through TW company crawl and
  profile-list surfaces
- tick symbol resolution prefers `tw_company_profiles`, then lifecycle data,
  then `daily_ohlcv`

P7 and P8 foundation data-plane surfaces:

- `POST /api/v1/data/external-signal-ingestions`
- `GET /api/v1/data/external-signals`
- `POST /api/v1/data/external-signal-audits`
- `GET /api/v1/data/external-signal-audits`
- `POST /api/v1/data/factor-catalogs`
- `GET /api/v1/data/factor-catalogs`
- `GET /api/v1/data/factor-materializations`
- `POST /api/v1/data/cluster-snapshots`
- `GET /api/v1/data/cluster-snapshots`
- `POST /api/v1/data/peer-feature-runs`
- `GET /api/v1/data/peer-feature-runs`

Implemented behavior:

- external raw archives, signals, audits, factor catalogs, factor
  materializations, factor usability observations, cluster snapshots, cluster
  memberships, peer feature runs, and peer comparison overlays all persist
- external-signal timing classification supports exact and fallback mappings
- peer overlays are merged into the tabular training frame used by the baseline
  backtest path

#### Execution Foundations

- `POST /api/v1/execution/simulation-orders`
- `GET /api/v1/execution/simulation-readbacks`
- `POST /api/v1/execution/live-orders`
- `GET /api/v1/execution/live-orders`
- `POST /api/v1/execution/live-controls/kill-switch`
- `GET /api/v1/execution/live-controls/kill-switch`

Implemented behavior:

- simulation foundations persist orders, order events, fill events, position
  snapshots, and failure taxonomy records
- `simulation_internal_v1` writes a complete synthetic order ledger
- `live_stub_v1` writes accepted-path synthetic completion ledgers and
  rejection-only ledgers on blocked paths
- research-run-triggered live-stub orders require explicit
  `manual_confirmed=true`
- unknown execution `run_id` values return `404 RESOURCE_NOT_FOUND`

### Implemented Frontend Areas

#### Research Run Workspace

- `ResearchRunForm`
- `ResearchRunInspector`
- `ResearchRunMetrics`
- `ResearchRunSignals`
- `ResearchRunValidation`

Current coverage:

- research-run submission
- persisted run lookup
- system-health display
- P7 to P11 gate inspection
- metrics, validation, and signal rendering for persisted run data

#### Data Plane Workspace

- `DataIngestionPanel`
- `ReplayPanel`
- `RecoveryDrillPanel`
- `LifecyclePanel`
- `ImportantEventPanel`
- `TickArchivePanel`
- `ExternalSignalPanel`
- `PeerInferencePanel`
- `ExecutionControlPanel`
- `AdaptiveWorkflowPanel`

Current coverage:

- manual data ingestion and replay
- manual and scheduled recovery operations
- lifecycle and important-event data management
- tick archive dispatch, import, replay, and KPI display
- external-signal ingestion and audit workflow
- factor catalog creation and materialization inspection through the external
  signal workflow
- cluster snapshot and peer-feature workflow
- simulation/live-stub control workflow
- adaptive profile and adaptive training-run workflow

## Partial Or Constrained Areas

### Cross-Phase Constraints

- durable operational qualification is still separate from structural
  completion for `P1`, `P2`, `P3`, and `P7` to `P11`
- open decisions still block durable policy in key areas:
  - `TBD-001`: TW calibrated minimum traded-value floor
  - `TBD-002`: tick archive storage baseline
  - `TBD-003`: simulation platform baseline
  - `TBD-004`: cross-model missing-feature default policy

### `P1` Constraints

- `P1` operational maturity still depends on the longer observation windows
  required by `GATE-P1-OPS-001`
- official feed URLs still need runtime configuration for crawler automation

### `P2` Constraints

- `KPI-TICK-*` values remain exploratory telemetry until `TBD-002` is closed
- archive storage is limited to `local_filesystem` under `var/tick_archives/`
  with optional Google Drive mirroring
- there is no S3, GCS, cross-instance archive sharing, or storage redundancy
- some operational list endpoints are still optimized for recent inspection
  rather than large-scale browsing
- browser-facing date defaults are still local-input driven even though market
  authority is `Asia/Taipei`

### `P3` Constraints

- the structural gate and ops telemetry exist, but durable operational
  qualification still depends on longer observation windows
- investability claims remain intentionally locked until `TBD-001` is resolved

### `P4` To `P6` Constraints

- these phases have important metadata and model-family foundations, but the
  repository does not yet represent them as fully closed roadmap milestones
- current model-family expansion is limited to the implemented tree-based
  contract paths rather than a broader ML and DL surface

### `P7` To `P11` Constraints

- the current repository snapshot reflects structural-complete foundation work,
  not mature operational qualification
- `P9` simulation telemetry remains exploratory until `TBD-003` is resolved
- adaptive workflow support currently stops at contract management, lifecycle
  persistence, and training-run orchestration

## Not Implemented Yet

- dedicated frontend panels for backend-only operational endpoints:
  - benchmark profiles
  - ingestion watchlist and dispatch management
  - daily ops KPI view
  - `P2` gate readout
  - TW company crawl and profile management
  - lifecycle and important-event crawler triggers
  - `P3` gate and micro KPI inspection
- remote object-store archive backends beyond local filesystem plus optional
  Google Drive mirroring
- a fixed external simulation-platform baseline that closes `TBD-003`
- a real broker integration path beyond `live_stub_v1`
- an integrated RL backend behind the adaptive surfaces

## Version-Pack Status

All normative version-pack fields in `SPEC-RUNTIME-005` are implemented. There
are currently no placeholder fields left inside that documented subset.

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

## Latest Recorded Verification Snapshot

- last recorded verification date: `2026-03-21`
- targeted backend tests:
  - `.venv/bin/python -m pytest tests/services/test_research_run_service.py tests/services/test_research_run_registry_service.py tests/services/test_foundation_service.py tests/services/test_backtest_engine_service.py tests/services/test_foundation_repository.py -q`
  - result: `15 passed`
- targeted foundation follow-up tests:
  - `.venv/bin/python -m pytest tests/services/test_foundation_repository.py tests/services/test_foundation_service.py -q`
  - result: `6 passed`
- frontend typecheck:
  - `bun x tsc -p frontend/tsconfig.json --noEmit`
  - result: `passed`
- migration acceptance:
  - strict reset via `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`
  - `alembic upgrade head`
  - `alembic downgrade base`
  - `alembic upgrade head`
  - result: `passed`
- fresh acceptance verification:
  - clean database reseed plus manual API checks
  - result: `P7`, `P8`, `P9`, `P10`, and `P11` gates returned `pass`
- frontend browser verification:
  - `agent-browser` against `http://127.0.0.1:5173`
  - result:
    - page load and both workspaces rendered
    - P7 to P11 data-plane panels issued live API requests
    - research-run submit path issued `/api/v1/research/runs` when invoked
    - default research-run and snapshot form dates do not align with the
      recorded acceptance dataset, so untouched defaults can still trigger
      expected `RESOURCE_NOT_FOUND` responses
