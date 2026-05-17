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

- status date: `2026-05-14`
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
| Start / Builder / Experiments / Data Support shell | implemented | frontend shell uses task-oriented surfaces instead of the old platform-first navigation |
| Baseline TW daily experiment builder | implemented | baseline workflow creates research runs from dataset, features, model, validation, and backtest settings |
| Regression diagnostics contract | implemented | backend, frontend types, and review UI include `model_diagnostics`, including residual samples |
| Persisted result artifacts | verified | new successful runs reload request config, diagnostics, equity curve, signals, baselines, metrics, warnings, runtime metadata, and artifact completeness summaries; old metadata-only records show explicit fallback copy |
| Experiments comparison | implemented | search, sort, load, and compare work for complete research-review runs; backend caveats block metadata-only, partial, and unfinished records |
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
- `Data Support`
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

## Code Reading Notes

The current codebase still contains names, metadata fields, and service modules
from the earlier platform-oriented design. That is expected historical context,
not a signal that v1 has returned to an execution or admin surface.

- data-plane repair, replay, lifecycle, and event endpoints support TW daily
  research data readiness; they are not the primary product loop
- execution, simulation, adaptive, peer, factor, external-signal, and tick
  archive code remains as compatibility or internal foundation inventory
- version-pack and foundation metadata may appear on research-run records so
  old records and future-promoted capabilities remain explainable
- Start, Experiment Builder, Experiments, and secondary Data Support remain the
  v1 information architecture for user-facing work

When reading code, treat advanced routes or metadata as retained foundations
unless `docs/plan.md` explicitly promotes them into a v1 milestone.

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

- v1 direction is current after the usable-loop verification
- docs should keep the historical context visible: retained platform-era code
  exists, but the current product contract is workbench-first
- developer-facing docs should keep the local data-prep caveat visible: a clean
  DB needs TW daily data loaded before the run path is useful
- future edits must keep advanced/platform modules out of the default research
  path unless `docs/plan.md` promotes them deliberately

### Frontend

- legacy or platform-era component names should be cleaned up only after the
  current workbench surfaces fully replace them
- residual diagnostics now have a dedicated sample section in the persisted run
  review surface
- comparison UI supports the v1 complete-run path; reason labels still need
  hardening so pairwise caveats are easier to interpret

### Backend

- classification remains specification-only
- comparison caveat labels and reason codes still need deeper hardening for
  non-comparable runs, such as sample-window, target, feature, and cost-basis
  mismatch cases
- artifact retention and payload sizing need a long-running-history policy, but
  this does not block the currently verified usable loop
- hidden advanced foundations may stay reachable for diagnostics and legacy
  tooling, but should not return to the v1 navigation without a roadmap
  decision

## Latest Local Verification

- usable-loop verification:
  - `main` was synced to `origin/main` at `5b042e0`
  - Docker DB started, migrations applied, backend and frontend started
  - `2330` TW daily data was loaded through the existing ingestion path because
    a clean DB had no daily rows
  - `agent-browser` verified Start -> Builder -> Run -> Review -> Reload ->
    Compare
  - result: the builder defaulted to Extra Trees, a successful run showed
    diagnostics, equity, validation, baselines, and signals, reload restored the
    persisted result, and two comparable runs showed aligned dataset, target,
    feature, model, and cost-basis fields
- focused verification:
  - `.venv/bin/python -m pytest -q tests/research tests/market_data/test_market_data_api.py`
  - result: `86 passed`
  - `bun x tsc -p frontend/tsconfig.json --noEmit`
  - result: passed
- persisted artifact reload verification:
  - Docker DB started with the default compose volume
  - migration applied with `.venv/bin/python -m alembic upgrade head`
  - deterministic `V1VERIFY` TW daily fixture created and cleaned up
  - successful run reloaded through `GET /api/v1/research/runs/{run_id}`
  - result: request config, diagnostics, residuals, equity curve, signals,
    baselines, warnings, metrics, and runtime metadata reloaded correctly
- browser smoke:
  - `agent-browser` verified the Experiments surface for a successful run and a
    metadata-only fallback record
  - result: successful run showed diagnostics, residuals, equity, validation,
    baselines, and signals; metadata-only run showed explicit fallback copy
- comparison eligibility verification:
  - two successful `V1COMPARE` runs were created through the API against a
    Docker DB fixture and reloaded from persisted records
  - result: both runs returned `research_only_comparable`, appeared as
    `Research-only comparable` in Experiments, and compared with model-config
    caveats instead of metadata-only warnings
- frontend typecheck:
  - `bun x tsc -p frontend/tsconfig.json --noEmit`
  - result: passed
- frontend build:
  - `cd frontend && bun run build`
  - result: passed
- lockfile check:
  - `uv lock --check`
  - result: passed
- backend regression:
  - `.venv/bin/python -m pytest -q`
  - result: `248 passed`
- public-surface targeted tests:
  - `.venv/bin/python -m pytest tests/research/test_research_api.py tests/market_data/test_market_data_api.py tests/platform/test_system_api.py tests/market_data/test_tick_archive_api.py -q`
  - result: `22 passed`
- advanced-foundation regression:
  - `.venv/bin/python -m pytest tests/signals tests/research/test_capability_gates.py tests/market_data/test_tick_archive.py -q`
  - result: `51 passed`

## Next Recommended Stage

Move from usable-loop verification to cleanup and hardening:

1. harden comparison caveats for non-comparable runs across sample-window,
   target, feature, and cost-basis mismatch cases
2. keep Data Support secondary to the main research loop, and keep retained
   platform-era foundations labeled as internal or deferred
3. document a clean-environment data-prep checklist for v1 demos and manual
   verification
4. clean up legacy naming only where it improves readability without widening
   v1 scope
