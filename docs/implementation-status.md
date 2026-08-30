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

- status date: `2026-07-27`
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
| Baseline TW daily research-run builder | implemented | baseline workflow creates research runs from dataset, features, model, validation, and backtest settings |
| Regression diagnostics contract | implemented | backend, frontend types, and review UI include `model_diagnostics`, including residual samples |
| Persisted result artifacts | verified | new successful runs reload every artifact required by `SPEC-RUN-001`, plus artifact completeness summaries; old metadata-only records show explicit fallback copy |
| Experiments comparison | implemented | search, sort, load, and compare work for complete research-review runs; backend caveats block metadata-only, partial, and unfinished records |
| Direction admission gate | implemented | provisionally calibrated tree classification admits candidates for regression ranking and persists diagnostics; artifact completeness does not establish out-of-sample skill or investment viability |
| Hybrid opinion review | implemented | the existing Opinion, direction-diagnostic, workflow-payload, and frontend type integration is retained; the frontend rewrite is planned but has not started, so no active frontend feature development is underway while the backend-first pause remains in effect |
| Data readiness | implemented | start surface uses requested-symbol TW daily readiness with ready/warning/missing-stale counts |
| Advanced/platform modules | hidden advanced | execution, adaptive, peer, factor, external-signal, and tick-archive surfaces remain code foundations, not v1 main-flow commitments |

## Current Product Surfaces

### Frontend

- `Start`
  - task entry for a baseline research run, recent research runs, and data readiness
- `Experiment Builder`
  - baseline TW daily research workflow
  - direction admission gate plus regression ranking by default
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
baseline research run.

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
- the strategy artifacts required by `SPEC-RUN-001`, plus validation summaries,
  exist for new successful runs
- `model_diagnostics` exists in contracts and persistence fields

### Data Readiness Foundations

- TW daily ingestion, replay, lifecycle, important-event, and recovery
  workflows exist
- raw payload preservation exists through raw ingest audit records
- data repair and operational panels exist under secondary data surfaces
- repository migration head is `0009`; the reconciled current-active profile universe
  contains `1,983` symbols (`TWSE 1,092`, `TPEX 891`)
- verified TW daily range `2023-07-24..2026-07-24` contains `1,349,401` rows
  across `1,983` symbols; raw traceability, duplicate groups, and invalid or
  null normalized OHLCV checks are clean
- date reconciliation recorded `785` attempted dates, `729` final successes,
  `56` explicit skips, and `0` unresolved dates; six transient TPEX transfer
  failures were retry-resolved

### Method Selection Matrix

- nested five-outer / three-inner Fold selection preserves the final 252
  Market-Date Holdout and target-end purging; Fold dates are drawn from the
  common Model-Ready rows after feature warmup
- two-stage Feature Family screening records baseline, add-one, full, and
  remove-one evidence before searching parameters only for the selected set
- common Full-Feature Model-Ready rows prevent Feature Family warmup from
  changing the comparison population; responses persist comparison caveats,
  resource evidence, availability, rankings, rejections, and no-opinion results
- migration `0010` is additive and retains Method Selection evidence during an
  application rollback

### Hidden Advanced Foundations

- tick archive dispatch, import, replay, and KPI surfaces exist
- factor catalog, external-signal, cluster, and peer-feature foundations exist
- simulation and live-stub execution foundations exist
- adaptive profile and adaptive training-run lifecycle surfaces exist

### Calibration Matrix

- pooled chronological calibration supports bounded TW requests, explicit
  model-family availability, resource evidence, and persisted comparison caveats
- calibration applies the versioned
  `tw_official_preferred_yfinance_fallback_v1` row policy before building one
  canonical pooled `(Symbol, Market Date)` row per source-resolved date
- target calculations use the global TW Market-Date axis from distinct TW dates
  with at least one official source row (excluding confirmed official no-data
  dates); missing Symbol dates remain target boundaries, while rolling features
  continue across missing observations without restarting warmup. Invalid OHLCV
  rows remain boundaries for both paths, and segment-local targets carry
  auditable `target_end_date` values that do not cross those boundaries
- the response records per-Symbol canonical, Market-Date-axis, missing-date,
  invalid-OHLCV, model-ready, and excluded-row counts
- fold summaries report rows removed by target-end purging, while unexpected
  model evaluation errors fail the request instead of becoming unavailable
  model results
- migration `0009` is additive and preserves calibration evidence during an
  application rollback

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

- the existing hybrid Opinion review, direction diagnostics, workflow payload,
  and type integration are retained
- the frontend rewrite is planned but has not started; no active frontend feature
  development is underway
- the backend-first pause remains in effect, so frontend work is limited to
  backend-contract compatibility, typecheck, and build verification
- legacy or platform-era component names should be cleaned up only after the
  current workbench surfaces fully replace them
- residual diagnostics now have a dedicated sample section in the persisted run
  review surface
- comparison UI supports the v1 complete-run path; reason labels still need
  hardening so pairwise caveats are easier to interpret

### Backend

- prospective opinions require a complete common-date hybrid snapshot; legacy
  and regression-only runs remain reviewable but return `no-opinion`
- direction metrics are currently pooled across symbols, and hybrid training
  cost grows with symbol and validation-fold counts; per-symbol diagnostics and
  performance optimization remain evidence-driven follow-up work
- comparison caveat labels and reason codes still need deeper hardening for
  non-comparable runs, such as sample-window, target, feature, and cost-basis
  mismatch cases
- artifact retention and payload sizing need a long-running-history policy, but
  this does not block the currently verified usable loop
- hidden advanced foundations may stay reachable for diagnostics and legacy
  tooling, but should not return to the v1 navigation without a roadmap
  decision

## Latest Local Verification

- authoritative data-readiness verification (`2026-07-27`):
  - the historical data-readiness snapshot was verified against migration head
    `0008`; the current repository migration head is `0009`
  - current-active profiles: `1,983` (`TWSE 1,092`, `TPEX 891`)
  - TW daily range `2023-07-24..2026-07-24`: `1,349,401` rows across `1,983`
    symbols
  - date reconciliation: `785` attempted, `729` final-success, `56`
    explicit-skip, `0` unresolved; six transient TPEX transfers were
    retry-resolved
  - raw traceability, duplicate groups, and invalid normalized OHLCV checks:
    clean
  - caveats: current-active survivorship; `891` TPEX profiles have null
    `listing_date`; this is not a complete daily-coverage, total-return, or
    model-viability claim

- usable-loop verification:
  - `main` was synced to `origin/main` at `5b042e0`
  - Docker DB started, migrations applied, backend and frontend started
  - `2330` TW daily data was loaded through the existing ingestion path because
    a clean DB had no daily rows
  - `agent-browser` verified Start -> Builder -> Run -> Review -> Reload ->
    Compare
  - result: the builder defaulted to Extra Trees, a successful run showed
    the `SPEC-RUN-001` artifacts plus validation, reload restored the persisted
    result, and two comparable runs showed aligned `SPEC-COMP-001` dimensions
- focused verification:
  - `.venv/bin/python -m pytest -q tests/research tests/market_data/test_market_data_api.py`
  - result: `86 passed`
  - `bun x tsc -p frontend/tsconfig.json --noEmit`
  - result: passed
- current Calibration Matrix hardening verification:
  - pooled, calibration, and migration regression tests cover invalid-date
    boundaries, request bounds, busy responses, contract validation, and
    evidence-preserving downgrade behavior
  - `.venv/bin/python -m pytest -q` result: `638 passed` with three existing
    warnings
  - `bun x tsc -p frontend/tsconfig.json --noEmit` result: passed
  - the Calibration Matrix response includes the TW point-in-time membership
    caveat, request-bounds policy version, and global Market-Date axis policy
- persisted artifact reload verification:
  - Docker DB started with the default compose volume
  - migration applied with `.venv/bin/python -m alembic upgrade head`
  - deterministic `V1VERIFY` TW daily fixture created and cleaned up
  - successful run reloaded through `GET /api/v1/research/runs/{run_id}`
  - result: every `SPEC-RUN-001` artifact, plus residuals, reloaded correctly
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
