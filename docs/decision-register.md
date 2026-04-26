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

## Open V1 Decisions

| ID | Topic | Owner area | Blocks | Next action |
| --- | --- | --- | --- | --- |
| `TBD-V1-002` | persisted artifact retention and size bounds | research persistence | long-running experiment history | define whether diagnostic samples, signals, and equity curves are stored fully or bounded per run |
| `TBD-V1-003` | comparison eligibility reason taxonomy | experiments UX | richer comparison explanations | define stable reason labels for metadata-only, missing artifacts, sample-window mismatch, target mismatch, and feature/model mismatch |

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
