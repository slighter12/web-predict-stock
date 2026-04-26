# Implementation Status

This document is descriptive only. It records the current repository surface
against the `TW daily Quant ML Research Workbench` v1 direction.

Normative product behavior lives in:

- `docs/project-goals.md`
- `docs/research-spec.md`
- `docs/plan.md`
- `docs/validation-gates.md`

Do not use this file to decide whether an advanced backend surface should appear
in the v1 product navigation.

## Status Scope

- status date: `2026-04-26`
- status terms:
  - `implemented`: behavior exists and is usable in the current codebase
  - `partial`: meaningful foundation exists, but the v1 product expectation is
    not complete
  - `hidden advanced`: code exists but is not part of the v1 main workflow
  - `deferred`: documented future/platform concern

## V1 Alignment Summary

| Area | Status | Current reading |
| --- | --- | --- |
| Workbench product direction | implemented | README, goals, plan, spec, and gates describe the v1 workbench direction |
| Start / Builder / Experiments / Data Ops shell | implemented | frontend shell uses task-oriented surfaces instead of the old platform-first navigation |
| Baseline TW daily experiment builder | implemented | baseline workflow creates research runs from dataset, features, model, validation, and backtest settings |
| Regression diagnostics contract | partial | backend and frontend types include `model_diagnostics`; validation still needs end-to-end artifact checks |
| Persisted result artifacts | partial | DB/model/repository support exists for diagnostics, equity, signals, and baselines; old records still need fallback handling |
| Experiments comparison | partial | search, sort, load, and compare UI foundations exist; comparison explanations still need hardening |
| Classification | contract-defined | task and diagnostics are specified, but implementation is deferred |
| Data readiness | implemented | start surface uses requested-symbol TW daily readiness with ready/warning/missing-stale counts |
| Advanced/platform modules | hidden advanced | execution, adaptive, peer, factor, external-signal, and tick-archive surfaces remain code foundations, not v1 main-flow commitments |

## Current Product Surfaces

### Frontend

- `Start`
  - task entry for baseline study, recent experiments, and data readiness
- `Experiment Builder`
  - baseline TW daily research workflow
  - currently regression-first; classification remains a documented future task
- `Experiments`
  - persisted run lookup, result review, filtering, sorting, and comparison
- `Data Ops`
  - secondary diagnostic surface for data readiness and repair workflows

Legacy components such as `PredictionStudio` and `MaintenanceWorkspace` may
still exist under `frontend/src/lib/internal/legacy/`, and they are not part
of the v1 information architecture.

### Backend

- primary v1 research path:
  - `POST /api/v1/research/runs`
  - `GET /api/v1/research/runs`
  - `GET /api/v1/research/runs/{run_id}`
  - `GET /api/v1/research/feature-registry`
  - `GET /api/v1/research/gates/p3`
  - `GET /api/v1/research/micro-kpis`
- v1-supporting data path:
  - `POST /api/v1/data/readiness/tw-daily`
  - TW daily ingestion and replay foundations
  - raw ingest audit and normalized daily market-data persistence
- hidden advanced paths:
  - execution simulation and live-stub controls
  - adaptive profile and training-run lifecycle
  - factor, external-signal, peer, cluster, and tick archive foundations

Hidden advanced paths may remain reachable for internal diagnostics or legacy
tooling, but they should not be required to start, understand, or compare a
baseline experiment.

## Implemented Foundations

### Research Run Core

- successful, rejected, validation-failed, and failed run attempts are
  persisted
- request payloads, runtime metadata, config sources, fallback audit, warnings,
  and version-pack fields are persisted
- tree-based regression model families are available through the shared tabular
  training path
- strategy metrics, signals, equity curve, baselines, and validation summaries
  exist for new successful runs
- `model_diagnostics` exists in contracts and persistence fields

### Data Readiness Foundations

- TW daily ingestion, replay, lifecycle, important-event, and recovery
  workflows exist
- raw payload preservation exists through raw ingest audit records
- data repair and operational panels exist under secondary data surfaces

### Hidden Advanced Foundations

- tick archive dispatch, import, replay, and KPI surfaces exist
- factor catalog, external-signal, cluster, and peer-feature foundations exist
- simulation and live-stub execution foundations exist
- adaptive profile and adaptive training-run lifecycle surfaces exist

These foundations are implementation inventory, not v1 product scope.

## Remaining V1 Gaps

### Documentation

- no known v1 direction blocker after the current rewrite
- future edits must keep advanced/platform modules out of the default research
  path unless `docs/plan.md` promotes them deliberately

### Frontend

- legacy `PredictionStudio` and `MaintenanceWorkspace` should be removed once
  the current workbench surfaces fully replace them
- residual diagnostics need either a dedicated UI section or an explicit
  product decision that residuals are represented inside diagnostic sample rows
- comparison UI needs clearer reason labels for non-comparable or
  metadata-only runs

### Backend

- persisted artifact reload should be verified end to end after migration
  `0008`
- old records without artifact JSON need clear fallback responses and UI copy
- classification remains specification-only
- hidden advanced foundations may stay reachable for diagnostics and legacy
  tooling, but should not return to the v1 navigation without a roadmap
  decision

## Latest Local Verification

- frontend typecheck:
  - `bun x tsc -p frontend/tsconfig.json --noEmit`
  - result: passed
- public-surface targeted tests:
  - `.venv/bin/python -m pytest tests/research/test_research_api.py tests/market_data/test_market_data_api.py tests/platform/test_system_api.py tests/market_data/test_tick_archive_api.py -q`
  - result: `22 passed`
- advanced-foundation regression:
  - `.venv/bin/python -m pytest tests/signals tests/research/test_capability_gates.py tests/market_data/test_tick_archive.py -q`
  - result: `51 passed`

## Next Recommended Stage

Move to the v1 implementation cleanup stage:

1. replace advanced gate counts on the start surface with TW daily data
   readiness
2. verify migration `0008` and persisted artifact reload in a real database
3. close the residual diagnostics UI/spec interpretation gap
4. deprecate or remove legacy frontend surfaces once the replacement flow is
   confirmed
