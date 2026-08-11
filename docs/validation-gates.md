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
researcher to create, inspect, reload, and compare TW daily ML research runs.

## V1 Gate and KPI Index

- `KPI-DATA-*`: TW daily data readiness and recoverability
- `KPI-ML-*`: prediction-task and model-diagnostic completeness
- `KPI-RESEARCH-*`: persisted research-run completeness
- `KPI-COMP-*`: research-run comparison clarity
- `KPI-COST-*`: offline backtest cost and price-assumption completeness
- `KPI-OPINION-*`: Phase 2 opinion artifact usefulness and safety
- `GATE-V1-*`: v1 acceptance gates
- `GATE-P2-*`: Phase 2 opinion-layer acceptance gates

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
- Old-run fallback rule: older records without artifacts pass only when the API
  marks them `metadata_only` or `partial` and the UI clearly labels missing
  artifacts as unavailable on the record.
- Opinion artifact rule: a Phase 2 opinion artifact passes only when it is
  traceable to persisted research artifacts and can produce `no-opinion` or
  `do-not-adopt` when evidence is insufficient.

## KPI Dictionary

### Data Readiness

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-DATA-001` | daily data availability | requested TW symbols have daily OHLCV rows in the requested range after exclusions | report |
| `KPI-DATA-002` | model-ready row count | rows remaining after feature generation, shifting, target alignment, and null filtering | `> 0` per trained symbol |
| `KPI-DATA-003` | data warning clarity | missing-data, stale-data, or event exclusions are represented in warnings or diagnostics, including symbol-level warning reasons on Start or Data Support surfaces | required |

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
| `KPI-RESEARCH-002` | strategy artifact persistence | persisted record includes every artifact required by `SPEC-RUN-001` | required for new runs |
| `KPI-RESEARCH-003` | old-run fallback clarity | historical records lacking artifacts expose artifact completeness and explicit fallback copy | required |

### Comparison

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-COMP-001` | comparison dimension coverage | comparison displays every dimension required by `SPEC-COMP-001` | required |
| `KPI-COMP-002` | comparability reason clarity | non-comparable or metadata-only runs show the reason or missing fields | required |
| `KPI-COMP-003` | model-first comparison | comparison does not treat strategy metrics as the only ranking surface | required |

### Offline Backtest Assumptions

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-COST-001` | cost-model completeness | fees, slippage, and cost-model version are present or explicitly unavailable | required |
| `KPI-COST-002` | price-basis clarity | label, entry, exit, and benchmark price-basis fields are present or explicitly unavailable | required |

### Opinion Layer

| ID | Metric | Definition | Gate |
| --- | --- | --- | --- |
| `KPI-OPINION-001` | opinion artifact shape | opinion output includes strategy-level state plus buy-candidate, sell-or-avoid, and watch lists | required for Phase 2 |
| `KPI-OPINION-002` | row evidence completeness | each populated opinion row includes symbol, model score, strategy-derived position signal, evidence reason, risk or warning, invalidation note, and source artifact references | required for Phase 2 |
| `KPI-OPINION-003` | evidence traceability | each populated row points to persisted diagnostics, signal, metric, baseline, validation, warning, completeness, or caveat artifacts | required for Phase 2 |
| `KPI-OPINION-004` | insufficient-evidence handling | incomplete, missing, stale, partial, or metadata-only evidence can produce `no-opinion` or `do-not-adopt` instead of forced candidates | required for Phase 2 |
| `KPI-OPINION-005` | manual-adoption boundary | opinion output does not imply broker routing, live-order readiness, automatic portfolio control, or personalized advice | required for Phase 2 |

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
- one click starts the research-run builder
- baseline workflow does not require P7-P11, operations, or execution concepts
- data readiness is visible as support context, not the primary hero

### GATE-V1-003: Regression Diagnostics

Passes when:

- new regression run response includes `model_diagnostics`
- diagnostics include `KPI-ML-001` fields
- result page places model diagnostics before strategy backtest interpretation

### GATE-V1-004: Persisted Review

Passes when:

- persisted successful run reload includes every artifact required by
  `SPEC-RUN-001`
- old runs without artifacts show the fallback required by `KPI-RESEARCH-003`

### GATE-V1-005: Research Runs and Comparison

Passes when:

- research runs can be searched, filtered, sorted, selected, and loaded
- two or more runs can be compared
- comparison shows every `SPEC-COMP-001` dimension, plus comparability caveats

## Phase 2 Acceptance Gates

Phase 2 gates do not block v1. They become pass/fail gates only when the
opinion layer is promoted into active implementation.

### GATE-P2-001: Opinion Artifact

Passes when:

- a complete successful research run can produce an opinion artifact
- the artifact includes the `KPI-OPINION-001` shape
- the artifact can represent empty buy, sell-or-avoid, or watch lists without
  treating them as failures
- the artifact can be reloaded or reconstructed from persisted research
  artifacts without relying on the latest in-session response only

### GATE-P2-002: Evidence Traceability

Passes when:

- each populated opinion row satisfies `KPI-OPINION-002`
- each populated opinion row satisfies `KPI-OPINION-003`
- unavailable artifacts are surfaced as evidence limitations, warnings,
  invalidation notes, `no-opinion`, or `do-not-adopt`

### GATE-P2-003: Invalidation Safety

Passes when:

- every actionable-looking row includes an invalidation note
- insufficient evidence produces `no-opinion` or `do-not-adopt`
- thresholds, confidence, or investability labels are provisional unless a
  later versioned policy explicitly promotes them

### GATE-P2-004: No Execution Creep

Passes when:

- opinion artifacts preserve the manual-adoption boundary
- no Phase 2 API, contract, or UI copy implies broker routing, live orders,
  automatic rebalancing, account control, or personalized investment advice
- live trading and guarded execution concepts remain deferred references until
  their own promotion criteria are met

### GATE-P2-005: Backend-First Slice

Passes when:

- the first Phase 2 implementation defines backend opinion artifacts before
  introducing a larger frontend workflow
- the opinion layer uses existing persisted research-run artifacts before
  adding external runtimes or data platforms
- external references are implemented as local method or evidence concepts, not
  as default runtime dependencies

## Deferred Gates

Execution, simulation, live-quality, adaptive, peer, factor, external-signal,
and tick-archive gates are future or hidden-advanced concerns. They should not
block any v1 gate unless a later roadmap explicitly promotes them into the main
research workbench.
