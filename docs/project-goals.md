# Project Goals and Scope Model

## Purpose

Define why the v1 product exists, what should be prioritized, what is in scope,
and what is deliberately hidden or deferred.

## Owns

- strategic goal hierarchy
- v1 scope boundaries and non-goals
- cross-goal tradeoff rules
- goal-to-evidence alignment for the TW daily research workbench

## Does Not Own

- local developer workflow
- exact KPI formulas or thresholds
- endpoint implementation details
- long-term platform sequencing beyond explicit future notes

## Decision Rule

Use this document when deciding whether work belongs in the v1 workbench and
which workstream wins when priorities conflict.

## Product Direction

V1 is the `TW daily Quant ML Research Workbench`.

The product should make one baseline research loop easy to complete before it
expands into a broader platform:

`Dataset -> Features -> Prediction Task -> Model Diagnostics -> Strategy Backtest -> Experiment Comparison`

The workbench should optimize for research clarity, reproducibility, and model
diagnosis. Strategy performance matters, but it is downstream of model quality
and should not be the only result surface.

## V1 Goal Hierarchy

The project has four v1 strategic layers:

1. TW daily data readiness
2. Research reproducibility and persisted artifacts
3. Model-quality diagnostics and prediction-task clarity
4. Experiment comparison and offline backtest discipline

Data readiness and reproducibility outrank model novelty, advanced signal
breadth, and any execution-path expansion.

## V1 Goal Table

| Goal | Outcome | Why it matters | Evidence family |
| --- | --- | --- | --- |
| `G1` | Durable TW daily market-data foundation | Research quality collapses when the raw daily data layer is fragile or hindsight-cleaned | `KPI-DATA-*` |
| `G2` | Reproducible and recoverable research outputs | A persisted experiment must be fully reviewable after reload, including config, diagnostics, predictions, signals, equity, baselines, warnings, and runtime metadata | `KPI-RESEARCH-*` |
| `G3` | Clear prediction-task semantics | Regression and classification must be explicit task families; first code delivery implements regression diagnostics while classification remains specified | `KPI-ML-*`, `KPI-RESEARCH-*` |
| `G4` | Model diagnostics before strategy claims | RMSE, MAE, residuals, actual-vs-predicted, rank/IC quality, and feature importance should be visible before backtest interpretation | `KPI-ML-*` |
| `G5` | Defensible offline backtests | Strategy metrics should use declared target, price, cost, and portfolio assumptions | `KPI-COMP-*`, `KPI-COST-*` |
| `G6` | Experiment comparison with caveats | The UI must explain which runs are comparable, why, and what changed across dataset, target, features, model config, diagnostics, and strategy metrics | `KPI-COMP-*` |

## Priority Order

Priority is not flat. Evaluate work in this order:

1. `G1` and `G2`
2. `G3` and `G4`
3. `G5`
4. `G6`

If a lower-priority feature weakens a higher-priority layer, defer it.

## Decision Principles

- Research usability should outrank product polish.
- Raw data recoverability should precede advanced analytics trust.
- Reproducibility should outrank model novelty.
- Model-quality diagnosis should precede strategy-performance claims.
- Comparability should outrank isolated backtest performance.
- TW daily should remain the operating assumption unless a later plan widens
  scope deliberately.
- Automation should remain auditable.

## V1 Scope Boundaries

### In Scope

- daily TW market-data readiness and rebuildability signals
- versioned research-run requests and persisted result artifacts
- regression prediction diagnostics
- classification task specification without first-pass implementation
- deterministic offline backtest semantics
- experiment registry, search, load, and comparison
- explicit fallback for old runs that lack complete artifacts

### Hidden Advanced Or Future Modules

- execution simulation and live-control paths
- adaptive or RL workflows
- peer inference and clustering
- factor catalog expansion beyond baseline inputs
- external-signal breadth
- tick archive and intraday strategy claims
- US-market parity

These modules may remain in code as internal diagnostics or future foundations,
but they should not appear in the v1 main research workflow.

## Non-Goals For V1

- broker execution
- investability claims from research-only runs
- real-time-first architecture
- multi-user productization
- premature microservice decomposition
- durable operational qualification for advanced modules

## Conflict Resolution Rule

When a proposal improves one goal but weakens another, resolve the conflict in
this order:

1. protect TW daily data readiness and recoverability
2. protect persisted experiment reproducibility
3. protect prediction-task, target, label, backtest, and comparison semantics
4. only then expand model families, signals, or advanced platform modules
