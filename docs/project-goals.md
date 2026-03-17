# Project Goals and Scope Model

## Purpose

Define why the project exists, what should be prioritized, what is in scope,
and what should be deferred.

## Owns

- strategic goal hierarchy
- scope boundaries and non-goals
- cross-goal tradeoff rules
- goal-to-evidence-to-phase alignment

## Does Not Own

- runtime or execution semantics
- persisted field definitions
- KPI formulas, thresholds, or gate truth conditions
- local developer workflow

## Consumes

- `docs/plan.md` for phase labels and delivery ordering
- `docs/validation-gates.md` for KPI and gate identifiers referenced as
  evidence families

## Produces

- goal IDs `G1` to `G11`
- project priority order
- scope and deferral rules used by roadmap and review

## Decision Rule

Use this document when deciding whether work should exist, whether it belongs
in the present stage, and which workstream wins when priorities conflict.

## Goal Hierarchy

The project has four strategic layers:

1. Data durability
2. Research reproducibility and comparability
3. Signal and model expansion
4. Guarded execution readiness

Data durability and research reproducibility should outrank model novelty,
external-signal breadth, and execution-path expansion.

## Goal Table

| Goal | Outcome | Why it matters | Evidence family | Primary phases |
| --- | --- | --- | --- | --- |
| `G1` | Durable TW-first market-data foundation | Research quality collapses when the raw data layer is fragile or hindsight-cleaned | `KPI-DATA-*` | `P1`, `P2`, `P3` |
| `G2` | Reproducible and recoverable research outputs | Results should be rebuildable, auditable, and recoverable after failure | `KPI-DATA-*`, `KPI-RESEARCH-*` | `P0`, `P1`, `P4` |
| `G3` | Defensible backtests and comparisons | Performance claims should rest on comparable definitions and sample floors | `KPI-COMP-*`, `KPI-RESEARCH-*` | `P0`, `P3`, `P4`, `P5` |
| `G4` | Expand from statistical baselines to ML and DL | Model expansion should happen only after the baseline contract is stable | `KPI-ADOPT-*`, `KPI-COMP-*` | `P6` |
| `G5` | Configurable feature and factor system | Features should be structured inputs instead of ad hoc experiments | `KPI-RESEARCH-*`, `KPI-FACTOR-*` | `P4`, `P7` |
| `G6` | Company and market information layers | News and fundamentals should remain timing-auditable | `KPI-EXT-*` | `P7` |
| `G7` | Clustering and peer-based inference | Peer signals should remain point-in-time correct | `KPI-COMP-*`, `KPI-RESEARCH-*` | `P8` |
| `G8` | Preserve the path to intraday research | Raw tick preservation should precede formal intraday claims | `KPI-TICK-*` | `P2` |
| `G9` | Move from paper validation to guarded execution | Execution should remain downstream of controls and readback | `KPI-SIM-*`, `KPI-LIVE-*`, `KPI-LIVEQ-*` | `P3`, `P5`, `P9`, `P10` |
| `G10` | Explore RL and adaptive methods later | Adaptive methods should remain downstream of a stable baseline stack | `KPI-ADAPT-*` | `P11` |
| `G11` | Keep US-market support optional | US support should not block the TW-first foundation | descriptive scope rule | optional |

## Goal to Evidence to Phase Matrix

| Goal | Evidence anchor | Delivery anchor |
| --- | --- | --- |
| `G1` | `KPI-DATA-*`, `KPI-TICK-*` | `P1`, `P2`, `P3` |
| `G2` | `KPI-DATA-*`, `KPI-RESEARCH-*` | `P0`, `P1`, `P4` |
| `G3` | `KPI-COMP-*`, `KPI-RESEARCH-*` | `P0`, `P3`, `P4`, `P5` |
| `G4` | `KPI-ADOPT-*`, `KPI-COMP-*` | `P6` |
| `G5` | `KPI-FACTOR-*`, `KPI-RESEARCH-*` | `P4`, `P7` |
| `G6` | `KPI-EXT-*` | `P7` |
| `G7` | `KPI-COMP-*`, `KPI-RESEARCH-*` | `P8` |
| `G8` | `KPI-TICK-*` | `P2` |
| `G9` | `KPI-SIM-*`, `KPI-LIVE-*`, `KPI-LIVEQ-*` | `P3`, `P5`, `P9`, `P10` |
| `G10` | `KPI-ADAPT-*` | `P11` |
| `G11` | descriptive scope rule | optional |

## Priority Order

Priority is not flat. The project should be evaluated in this order:

1. `G1` and `G2`
2. `G3`
3. `G4`, `G5`, `G6`, and `G7`
4. `G8`, `G9`, and `G10`
5. `G11` remains optional

If a lower-priority feature risks slowing or weakening a higher-priority layer,
the lower-priority feature should be deferred.

## Decision Principles

- Research usability should outrank product polish.
- Raw data recoverability should precede advanced analytics trust.
- Reproducibility should outrank model novelty.
- Comparability should outrank isolated backtest performance.
- Investability claims should require stricter evidence than research-only
  claims.
- Automation should remain auditable.
- TW-first should remain the operating assumption unless a later phase widens
  scope deliberately.

## Scope Boundaries

### In Scope

- daily TW market-data ingestion and rebuildability
- versioned research runs and comparison metadata
- deterministic backtest semantics
- reproducible KPI and gate evaluation
- controlled expansion into factors, news, fundamentals, and model families

### Deliberately Deferred

- intraday or tick strategy claims before archive and replay are trustworthy
- broker execution before paper or simulation controls are stable
- RL or adaptive control layers before the baseline stack is stable
- heavy real-time infrastructure before the daily research loop is reliable

## Non-Goals for This Stage

- multi-user productization
- premature microservice decomposition
- real-time-first architecture
- claiming investability from research-only runs
- broad US-market feature parity before the TW-first stack is durable

## Conflict Resolution Rule

When a proposal improves one goal but weakens another, resolve the conflict in
this order:

1. protect data durability and recoverability
2. protect reproducibility and comparability
3. protect execution semantics and gating clarity
4. only then expand model families or external signals
