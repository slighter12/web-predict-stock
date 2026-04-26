# Validation and KPI Gates

## Purpose

Define the v1 acceptance checks for the `TW daily Quant ML Research Workbench`
and identify advanced gates that are excluded from v1 pass/fail.

## Owns

- v1 acceptance checks
- metric families used by the research workbench
- explicit advanced/deferred gate boundaries

## Does Not Own

- runtime behavior
- local developer workflow
- broker execution qualification
- adaptive or RL rollout policy

## Decision Rule

Use this document when deciding whether the v1 workbench is ready for a
researcher to create, inspect, reload, and compare TW daily ML experiments.

## V1 Gate and KPI Index

- `KPI-DATA-*`: TW daily data readiness and recoverability
- `KPI-ML-*`: prediction-task and model-diagnostic completeness
- `KPI-RESEARCH-*`: persisted experiment completeness
- `KPI-COMP-*`: experiment comparison clarity
- `KPI-COST-*`: offline backtest cost and price-assumption completeness
- `GATE-V1-*`: v1 acceptance gates

The following families are not v1 pass/fail gates:

- `KPI-TICK-*`
- `KPI-SIM-*`
- `KPI-LIVE-*`
- `KPI-LIVEQ-*`
- `KPI-ADAPT-*`
- `GATE-P7-*` through `GATE-P11-*`
- `GATE-LIVEQ-*`

They may remain as internal diagnostics or future references, but they must not
drive the default workbench workflow.

## Metric Definition Rules

- Trading-day basis: use the active TW exchange trading calendar unless a
  metric states otherwise. The v1 readiness surface is an exception: it reports
  requested-symbol coverage over currently known TW daily market dates until a
  calendar-authoritative readiness service is promoted.
- Missing-sample rule: symbols blocked by lifecycle state, unresolved corporate
  events, missing OHLCV, or missing target availability are excluded from
  model-ready denominators and recorded in warnings when relevant.
- Artifact rule: a successful new run is incomplete for v1 review if persisted
  reload cannot show the same core diagnostics and backtest artifacts as the
  in-session response.
- Old-run fallback rule: older records without artifacts pass only when the UI
  clearly labels missing artifacts as unavailable.

## KPI Dictionary

### Data Readiness

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-DATA-001` | daily data availability | requested TW symbols have daily OHLCV rows in the requested range after exclusions | report |
| `KPI-DATA-002` | model-ready row count | rows remaining after feature generation, shifting, target alignment, and null filtering | `> 0` per trained symbol |
| `KPI-DATA-003` | data warning clarity | missing-data, stale-data, or event exclusions are represented in warnings or diagnostics, including symbol-level warning reasons on Start or Data Ops surfaces | required |

### Model Diagnostics

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-ML-001` | regression diagnostic completeness | successful regression run includes RMSE, MAE, rank IC, linear IC, sample count, actual-vs-predicted, residuals, and feature importance | required |
| `KPI-ML-002` | diagnostic persistence | persisted reload includes the same model diagnostics as the in-session response | required for new runs |
| `KPI-ML-003` | classification spec readiness | classification target and diagnostic requirements are documented | required; implementation deferred |

### Research Artifacts

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-RESEARCH-001` | request persistence | persisted record includes the original request config | required |
| `KPI-RESEARCH-002` | strategy artifact persistence | persisted record includes metrics, equity curve, signals, baselines, warnings, and runtime metadata | required for new runs |
| `KPI-RESEARCH-003` | old-run fallback clarity | historical records lacking artifacts show explicit fallback copy | required |

### Comparison

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-COMP-001` | comparison dimension coverage | comparison displays dataset/date range, target, features, model config, diagnostics, strategy metrics, baseline delta, and eligibility | required |
| `KPI-COMP-002` | comparability reason clarity | non-comparable or metadata-only runs show the reason or missing fields | required |
| `KPI-COMP-003` | model-first comparison | comparison does not treat strategy metrics as the only ranking surface | required |

### Offline Backtest Assumptions

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-COST-001` | cost-model completeness | fees, slippage, and cost-model version are present or explicitly unavailable | required |
| `KPI-COST-002` | price-basis clarity | label, entry, exit, and benchmark price-basis fields are present or explicitly unavailable | required |

## V1 Acceptance Gates

### GATE-V1-001: Documentation Direction

Passes when:

- README first screen describes `TW daily Quant ML Research Workbench`
- goals, plan, spec, and gates distinguish v1, hidden advanced, and deferred
  modules
- execution, adaptive, peer, factor, and tick archive modules are not described
  as v1 main-flow requirements

### GATE-V1-002: Baseline Workflow

Passes when:

- homepage exposes `Start Baseline Study`
- one click starts the experiment builder
- baseline workflow does not require P7-P11, operations, or execution concepts
- data readiness is visible as support context, not the primary hero

### GATE-V1-003: Regression Diagnostics

Passes when:

- new regression run response includes `model_diagnostics`
- diagnostics include `KPI-ML-001` fields
- result page places model diagnostics before strategy backtest interpretation

### GATE-V1-004: Persisted Review

Passes when:

- persisted successful run reload includes request config, diagnostics, signals,
  equity curve, baselines, metrics, warnings, and runtime metadata
- old runs without artifacts show the fallback required by `KPI-RESEARCH-003`

### GATE-V1-005: Experiments and Comparison

Passes when:

- experiments can be searched, filtered, sorted, selected, and loaded
- two or more runs can be compared
- comparison shows model diagnostics, strategy metrics, baseline delta, and
  comparability caveats

## Deferred Gates

Execution, simulation, live-quality, adaptive, peer, factor, external-signal,
and tick-archive gates are future or hidden-advanced concerns. They should not
block any v1 gate unless a later roadmap explicitly promotes them into the main
research workbench.
