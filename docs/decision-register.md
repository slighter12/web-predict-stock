# Decision Register

This document records product and platform decisions that affect the
`TW daily Quant ML Research Workbench`.

Normative behavior still belongs in `docs/research-spec.md`; roadmap sequencing
belongs in `docs/plan.md`; acceptance checks belong in
`docs/validation-gates.md`.

## Purpose

- record accepted v1 product decisions
- track open v1 decisions that can affect implementation
- keep deferred platform decisions separate from v1 workbench scope

## Decision Rule

When a change needs a product tradeoff, record it here if the answer should be
stable across multiple implementation tasks.

## Accepted V1 Decisions

| ID | Decision | Status | Impact |
| --- | --- | --- | --- |
| `DEC-V1-001` | Product positioning is Workbench-first, platform-later | accepted | README, goals, plan, spec, and gates must optimize for the v1 research loop before platform breadth |
| `DEC-V1-002` | v1 market scope is TW daily | accepted | main workflow, examples, and readiness checks should default to TW daily data |
| `DEC-V1-003` | prediction tasks include regression and classification | accepted | specs must define both task families |
| `DEC-V1-004` | first implementation pass is regression diagnostics | accepted | classification is contract-defined but not required in first code delivery |
| `DEC-V1-005` | result pages are model-quality first | accepted | model diagnostics should appear before strategy backtest interpretation |
| `DEC-V1-006` | persisted experiments must be fully reviewable | accepted | new runs must reload with config, diagnostics, signals, equity, baselines, warnings, and runtime metadata |
| `DEC-V1-007` | advanced/platform modules are hidden by default | accepted | execution, adaptive, peer, factor, external-signal, and tick archive modules are not default workflow requirements |
| `DEC-V1-008` | v1 readiness denominator is requested-symbol coverage | accepted | readiness reports requested symbols over the requested date range using currently known TW daily market dates; exchange-calendar authority is deferred |
| `DEC-V1-009` | advanced APIs remain available as internal foundations | accepted | advanced routes may stay reachable for diagnostics and legacy tooling, but they must stay out of v1 navigation and baseline workflow requirements |
| `DEC-V1-010` | v1 baseline builder defaults to Extra Trees | accepted | the default research loop avoids requiring the XGBoost native runtime while keeping XGBoost and Random Forest selectable variants |
| `DEC-V1-011` | retained platform-era code is internal foundation inventory | accepted | code, metadata fields, and docs may mention execution, adaptive, peer, factor, external-signal, or tick foundations only as compatibility or future-promoted surfaces, not as v1 product commitments |
| `DEC-V1-012` | artifact completeness is derived, not migrated | accepted | run review and compare use `artifact_completeness`, artifact lists, and backend caveats derived from existing row JSON fields |

## Accepted Phase Direction Decisions

| ID | Decision | Status | Impact |
| --- | --- | --- | --- |
| `DEC-PHASE-001` | External trading and research tools are reference material, not default dependencies | accepted | Jesse, UZI-Skill, a-stock-data, OpenBB, FinGPT, FinRL, and similar projects may inform local contracts and methods, but their runtimes should not be integrated by default |
| `DEC-PHASE-002` | Jesse-style methods are valid research-method inputs | accepted | Strategy lifecycle, signal-to-position translation, robustness checks, parameter sensitivity, and backtest-report discipline may inform a future research method library without adopting Jesse's live trading runtime |
| `DEC-PHASE-003` | Phase 2 prioritizes backend opinion artifacts before frontend expansion | accepted | Next product work should synthesize diagnostics, signals, backtests, baselines, and warnings into decision-useful opinion artifacts before adding large UI surfaces |
| `DEC-PHASE-004` | Live trading concepts are deferred but retained for later guarded execution planning | accepted | Broker execution, live orders, paper/live separation, order lifecycle, reconciliation, audit logs, kill switches, and manual confirmations stay out of the current phase but remain reference material for future guarded execution work |
| `DEC-PHASE-005` | Portfolio automation is deferred behind manual adoption tracking | accepted | Nearer-term portfolio work should record manual adoption, forward outcomes, and portfolio impact before any automatic rebalancing or account-control behavior |
| `DEC-PHASE-006` | Phase 2 opinion artifact contract and reconstruction path are fixed | accepted | `opinion_artifact` serializes state, action rows, source references, and review checks in research responses; POST builds from current response artifacts, detail reload reconstructs from persisted run artifacts, and list responses remain summary-only |

## Open V1 Decisions

| ID | Topic | Owner area | Blocks | Next action |
| --- | --- | --- | --- | --- |
| `TBD-V1-002` | persisted artifact retention and size bounds | research persistence | long-running experiment history, not the current usable loop | define whether diagnostic samples, signals, and equity curves are stored fully or bounded per run |
| `TBD-V1-003` | comparison reason hardening | experiments UX | richer pairwise explanations, not basic compare usability | extend backend caveats beyond artifact completeness and keep UI-derived assumption mismatch labels aligned |

## Open Phase Direction Decisions

| ID | Topic | Owner area | Blocks | Acceptance trigger |
| --- | --- | --- | --- | --- |
| `TBD-PHASE-001` | research method library first slice | research services | Phase 2 method sequencing, not current v1 usability | accepted when the first method slice names its input artifacts, output artifact, validation check, persistence behavior, and comparison caveats |
| `TBD-PHASE-003` | portfolio ledger and manual adoption model | portfolio research | Phase 3 feedback loop | accepted when manual adoption record fields, holdings context, forward outcome comparison, and portfolio-impact reporting are specified without automatic trading |
| `TBD-PHASE-004` | guarded broker and live-order promotion criteria | execution planning | future guarded execution only | accepted when safety, audit, reconciliation, idempotency, manual-confirmation, and kill-switch gates are documented before broker integration can enter active planning |
| `TBD-PHASE-005` | US daily data-source strategy | market expansion | US daily future lane | accepted when source contracts, raw-payload audit rules, market-calendar policy, and TW/US comparison semantics are documented |

## Deferred Platform Decisions

The following historical platform decisions are retained for future planning.
They do not block v1 workbench acceptance gates unless a future roadmap promotes
them into the main workflow.

| ID | Topic | Status | Owner area | Deferred impact |
| --- | --- | --- | --- | --- |
| `TBD-001` | TW calibrated minimum traded-value floor | open | research policy | needed before investability claims or benchmark-relative investability policy |
| `TBD-002` | tick archive storage details | open | data platform | needed before durable tick archive operational qualification |
| `TBD-003` | simulation platform choice | open | execution integration | needed before simulation readback or execution platform qualification |
| `TBD-004` | cross-model missing-feature default policy | open | model governance | needed before broad cross-family model governance |
| `TBD-005` | guarded broker execution safety model | open | execution integration | needed before live-order routing, broker reconciliation, manual confirmation, or kill-switch behavior |
| `TBD-006` | portfolio auto-control boundary | open | portfolio research | needed before any automatic rebalancing, position sizing against real holdings, or account-control behavior |

## Deferred Decision Details

### TBD-001

- Topic: TW calibrated minimum traded-value floor
- Status: open
- Deferred scope:
  investability claims, investability-based threshold recalibration, and
  benchmark-relative investability policy.
- Next action:
  publish the calibration methodology, acceptance rule, and adopted floor
  version when investability work becomes active.

### TBD-002

- Topic: tick archive storage details
- Status: open
- Deferred scope:
  archive naming, compression, partitioning, retention, and restore
  qualification.
- Next action:
  freeze the archive policy before tick archive work becomes a main workflow
  dependency.

### TBD-003

- Topic: simulation platform choice
- Status: open
- Deferred scope:
  simulation readback, reconciliation, and failure-taxonomy measurement.
- Next action:
  select the simulation platform before execution-platform qualification work
  starts.

### TBD-004

- Topic: cross-model missing-feature default policy
- Status: open
- Deferred scope:
  broad model-family governance beyond the current regression-first workbench.
- Next action:
  define the shared default behavior or explicitly decide no shared default
  will exist.

### TBD-005

- Topic: guarded broker execution safety model
- Status: open
- Deferred scope:
  broker connectivity, live orders, order lifecycle reconciliation,
  idempotent order submission, audit logs, kill switches, and required manual
  confirmations.
- Next action:
  define a guarded execution safety model before any broker or live-order
  integration moves into active planning.

### TBD-006

- Topic: portfolio auto-control boundary
- Status: open
- Deferred scope:
  automatic rebalancing, account-level position sizing, holdings-aware order
  generation, and portfolio control loops.
- Next action:
  define manual adoption tracking and portfolio-impact measurement before
  considering automatic portfolio controls.
