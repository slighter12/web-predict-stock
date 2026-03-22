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
  - `execution.py`
- `backend/schemas/`
  - `common.py`
  - `runtime.py`
  - `research_runs.py`
  - `data_plane.py`
  - `foundations.py`
- `backend/services/`
  - research-run orchestration
  - backtest-engine execution
  - data-plane operations
  - foundation-phase orchestration
  - foundation gate evaluation
  - scheduled recovery-drill dispatch
  - scheduled ingestion dispatch
  - operational KPI calculation
  - official lifecycle and important-event crawling
  - TW company universe crawling
- `backend/repositories/`
  - research-run persistence
  - foundation persistence
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
- `GET /api/v1/research/gates/p7`
- `GET /api/v1/research/gates/p8`
- `GET /api/v1/research/gates/p9`
- `GET /api/v1/research/gates/p10`
- `GET /api/v1/research/gates/p11`
- `POST /api/v1/research/adaptive-profiles`
- `GET /api/v1/research/adaptive-profiles`
- `POST /api/v1/research/adaptive-training-runs`
- `GET /api/v1/research/adaptive-training-runs`
- `POST /api/v1/data/ingestions`
- `POST /api/v1/data/replays`
- `GET /api/v1/data/replays`
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
- `POST /api/v1/execution/simulation-orders`
- `GET /api/v1/execution/simulation-readbacks`
- `POST /api/v1/execution/live-orders`
- `GET /api/v1/execution/live-orders`
- `POST /api/v1/execution/live-controls/kill-switch`
- `GET /api/v1/execution/live-controls/kill-switch`

## Current Frontend Surface

- `Research Run Workspace`
  - `ResearchRunForm`
  - `ResearchRunInspector`
  - metrics, validation, signals, and run-registry inspection
  - optional P7-P11 foundation fields:
    - factor catalog and scoring factors
    - peer and cluster metadata
    - execution route and route-specific profile IDs
    - adaptive mode and adaptive contract metadata
  - P7-P11 structural gate inspection
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
  - `ExternalSignalPanel`
    - external archive build
    - audit execution
    - factor catalog seed
  - `PeerInferencePanel`
    - cluster snapshot creation
    - peer-feature run creation
  - `ExecutionControlPanel`
    - simulation order submission
    - live-stub order submission
    - kill-switch control
  - `AdaptiveWorkflowPanel`
    - adaptive profile creation
    - adaptive training-run creation
- Backend-only data-plane endpoints with no dedicated frontend panel yet:
  - `/api/v1/data/benchmark-profiles`
  - `/api/v1/data/ingestion-watchlist`
  - `/api/v1/data/ingestion-dispatches`
  - `/api/v1/data/ops/kpis`
  - `/api/v1/data/tick-gates/p2`
  - `/api/v1/data/tw-company-crawls`
  - `/api/v1/data/tw-company-profiles`
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
- tick archive objects now persist optional Google Drive mirror metadata when
  `GOOGLE_DRIVE_TICK_ARCHIVE_ROOT` is configured
- active TW company universe snapshots exist through:
  - `/api/v1/data/tw-company-crawls`
  - `/api/v1/data/tw-company-profiles`
  - `scripts/run_tw_company_crawler.py`
- tick symbol resolution now prefers persisted `tw_company_profiles` before
  lifecycle or `daily_ohlcv` fallbacks
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

### P4-P6 Foundations

Status: `partial foundation implemented`

- research runs now persist:
  - `comparison_review_matrix_version`
  - `scheduled_review_cadence`
  - `model_family`
  - `training_output_contract_version`
  - `adoption_comparison_policy_version`
- `split_policy_version`, `bootstrap_policy_version`, and
  `ic_overlap_policy_version` are now populated instead of remaining placeholders
- `comparison_eligibility` can now promote to `sample_window_pending` when the
  run has the final metadata contract but the required sample windows are not
  yet satisfied
- research execution now supports the shared tabular training-output contract
  across `xgboost`, `random_forest`, and `extra_trees`

Still not complete for `P1-OPS`:

- live observation-window qualification is still required before claiming gate pass
- official feed URLs must still be configured at runtime for automated crawlers

### P7-P11 Foundations

Status: `structural foundation implemented`

- research-run requests and persisted run records now include optional
  foundation fields for:
  - factor catalog and scoring-factor selection
  - external signal policy
  - cluster snapshot and peer policy
  - execution route plus simulation/live control profile IDs
  - adaptive mode plus reward/state/rollout contract versions
- version-pack and governance payloads now include:
  - `factor_catalog_version`
  - `external_lineage_version`
  - `cluster_snapshot_version`
  - `peer_comparison_policy_version`
  - `simulation_adapter_version`
  - `live_control_version`
  - `adaptive_contract_version`
- P7 external-signal and factor-catalog persistence exists through:
  - `external_raw_archives`
  - `external_signal_records`
  - `external_signal_audits`
  - `factor_catalogs`
  - `factor_catalog_entries`
  - `factor_materializations`
  - `factor_usability_observations`
- P7 data-plane and gate APIs exist through:
  - `/api/v1/data/external-signal-ingestions`
  - `/api/v1/data/external-signals`
  - `/api/v1/data/external-signal-audits`
  - `/api/v1/data/factor-catalogs`
  - `/api/v1/data/factor-materializations`
  - `/api/v1/research/gates/p7`
- research-run execution now materializes factor records point-in-time and
  persists timing classification including exact and fallback mappings
- important-event rows with a direct `event_publication_ts`, including
  `vendor_published` timestamps, are treated as exact-availability records
- external-signal audit sampling now reads the full source-family review window
  and deterministically guarantees the documented fallback-record minimum when
  fallback timestamps exist
- `GATE-P7-001` now requires persisted timing-mapping evidence from the latest
  audit result instead of treating archive and catalog presence as sufficient
- P8 clustering and peer inference persistence exists through:
  - `cluster_snapshots`
  - `cluster_memberships`
  - `peer_feature_runs`
  - `peer_comparison_overlays`
- P8 data-plane and gate APIs exist through:
  - `/api/v1/data/cluster-snapshots`
  - `/api/v1/data/peer-feature-runs`
  - `/api/v1/research/gates/p8`
- cluster snapshots now build their universe from `daily_ohlcv` on the requested
  `trading_date`, then filter it with point-in-time lifecycle state instead of
  current `tw_company_profiles.trading_status`
- peer-enabled research runs now scope cluster snapshot lookup by both
  `market` and `cluster_snapshot_version`, so same-version snapshots from other
  markets do not leak into TW/US overlays
- peer overlay output is now merged into the tabular training frame used by the
  backtest-engine baseline path
- `GATE-P8-001` no longer treats snapshot existence as a proxy for
  `KPI-RESEARCH-002` or `KPI-RESEARCH-003`; those KPI checks now evaluate
  peer-enabled research-run metadata and reporting evidence directly
- baseline backtest metrics now persist `max_position_weight` so the research
  reporting contract can satisfy the documented concentration requirement
- P9 and P10 execution foundations persist through:
  - `simulation_profiles`
  - `execution_orders`
  - `execution_order_events`
  - `execution_fill_events`
  - `execution_position_snapshots`
  - `execution_failure_taxonomies`
  - `live_risk_checks`
  - `kill_switch_events`
- execution APIs and gates now exist through:
  - `/api/v1/execution/simulation-orders`
  - `/api/v1/execution/simulation-readbacks`
  - `/api/v1/execution/live-orders`
  - `/api/v1/execution/live-controls/kill-switch`
  - `/api/v1/research/gates/p9`
  - `/api/v1/research/gates/p10`
- `simulation_internal_v1` writes a complete order ledger including submitted,
  acknowledged, filled, and position-readback artifacts
- `GATE-P9-001` now checks all documented structural artifacts, including
  order-history persistence and readback-telemetry emission, instead of only a
  partial subset
- `live_stub_v1` now also writes a complete synthetic completion ledger on the
  accepted path and a rejection-only ledger on blocked paths
- research-run-triggered `live_stub_v1` orders require an explicit
  `manual_confirmed` request flag; `live_control_profile_id` no longer implies
  human confirmation
- `GATE-P10-001` now requires `kill_switch` and `broker_order_logging`
  artifacts in addition to the live KPI checks before returning `pass`
- `broker_order_logging` for accepted live-stub orders now requires the full
  synthetic ledger (`submitted`, `acknowledged`, `filled`, `position_readback`)
  rather than only a `submitted` event
- execution API requests with an unknown `run_id` now return `404
  RESOURCE_NOT_FOUND` instead of surfacing a persistence-layer `500`
- P11 adaptive isolation persists through:
  - `adaptive_profiles`
  - `adaptive_training_runs`
  - `adaptive_rollout_controls`
  - `adaptive_surface_exclusions`
- P11 APIs and gate now exist through:
  - `/api/v1/research/adaptive-profiles`
  - `/api/v1/research/adaptive-training-runs`
  - `/api/v1/research/gates/p11`
- adaptive research runs now require explicit opt-in contract metadata when
  `adaptive_mode` is not `off`
- adaptive training-run creation now validates that reward/state/rollout
  versions exactly match the selected adaptive profile contract, and the
  frontend training form syncs those fields after profile creation
- `KPI-ADAPT-002` contamination now uses persisted comparison-eligibility and
  tradability-state exposure semantics together with adaptive-surface
  exclusions, rather than treating a missing exclusion row as contamination by
  itself
- `GATE-P11-001` now treats `isolated_adaptive_workflow` as a required
  artifact for `overall_status`, not just a reported detail

Still not complete for durable `P7-OPS` to `P11` qualification:

- this snapshot only reflects structural-complete foundation work, not the
  longer observation windows required for:
  - `GATE-P7-OPS-001`
  - `GATE-P8-OPS-001`
  - `GATE-P9-OPS-001`
  - `GATE-LIVEQ-001`
- `TBD-003` remains open, so P9 simulation telemetry is still exploratory for
  durable operational qualification
- adaptive workflow support is limited to trainer interface and lifecycle
  persistence; there is still no integrated RL backend

## Current Verification Snapshot

- last updated: `2026-03-21`
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
  - result: `P7`, `P8`, `P9`, `P10`, and `P11` gates all returned `pass`
- frontend browser verification:
  - `agent-browser` against `http://127.0.0.1:5173`
  - result:
    - page load and both workspaces rendered
    - P7-P11 data-plane panels issued live API requests
    - research-run submit path issued `/api/v1/research/runs` when invoked in-page
    - default research-run and snapshot form dates do not align with the current
      acceptance dataset, so untouched defaults can still trigger expected
      `RESOURCE_NOT_FOUND` responses

## Version Pack Status

Currently implemented fields:

- `threshold_policy_version`
- `price_basis_version`
- `benchmark_comparability_gate`
- `comparison_eligibility`
- `investability_screening_active`
- `capacity_screening_version`
- `adv_basis_version`
- `missing_feature_policy_version`
- `execution_cost_model_version`
- `split_policy_version`
- `bootstrap_policy_version`
- `ic_overlap_policy_version`
- `factor_catalog_version`
- `external_lineage_version`
- `cluster_snapshot_version`
- `peer_comparison_policy_version`
- `simulation_adapter_version`
- `live_control_version`
- `adaptive_contract_version`

Currently placeholder fields:

- none within the normative version-pack subset defined in `SPEC-RUNTIME-005`

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
