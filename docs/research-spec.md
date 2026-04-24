# Research Specification

## Purpose

Define the normative source of truth for the `TW daily Quant ML Research
Workbench` v1.

## Owns

- prediction task semantics
- dataset and feature contracts
- model diagnostics
- offline backtest artifacts
- persisted experiment artifacts
- comparison labels and caveats

## Does Not Own

- implementation sequencing
- local developer workflow
- broker execution semantics
- live-order controls
- adaptive or RL policy
- broad platform operations

## Decision Rule

Use this document when deciding what metadata must be persisted, what counts as
a valid research result, and when two experiments can be compared.

## Normative Layers

The v1 spec has six layers:

1. Dataset contract
2. Feature contract
3. Prediction task contract
4. Model diagnostics contract
5. Offline backtest contract
6. Persisted experiment and comparison contract

## Dataset Contract

### SPEC-DATA-001: TW daily default

- v1 defaults to TW daily research
- every run must persist:
  - `market`
  - `symbols`
  - `date_range.start`
  - `date_range.end`
  - `return_target`
  - `horizon_days`

### SPEC-DATA-002: Raw-source preservation

- raw source payloads must be saved before normalization when data is ingested
- raw payload storage should preserve:
  - source name
  - fetch timestamp
  - parser version
  - fetch status
  - expected symbol context when applicable

### SPEC-DATA-003: Model-ready universe

- symbols with core daily OHLCV gaps remain part of the research request but do
  not enter the model-ready rows for affected dates
- missing rows must be explainable through warnings or data-readiness surfaces
- tradability and liquidity fields are diagnostic for v1, not investability
  claims

## Feature Contract

### SPEC-FEATURE-001: Feature specification

Every feature row must persist:

- `name`
- `window`
- `source`
- `shift`

Feature shifts are part of the leakage-control contract and must remain visible
in the request config.

### SPEC-FEATURE-002: Feature lineage

Advanced factor, peer, and external-signal fields may exist on the request, but
they are hidden advanced modules in v1. A baseline experiment must not require
them.

## Prediction Task Contract

### SPEC-TASK-001: Supported task families

The v1 workbench recognizes two prediction task families:

- `regression`
- `classification`

The first implementation pass supports regression diagnostics. Classification
is specified here so it can be added later without changing the workbench flow.

### SPEC-TASK-002: Regression target

Regression predicts a numeric forward return target derived from:

- `return_target`
- `horizon_days`
- active price basis

The active implementation uses tabular tree regressors and produces continuous
scores used by the strategy backtest.

### SPEC-TASK-003: Classification target

Classification must persist, when implemented:

- positive-class definition
- class horizon
- label threshold or quantile rule
- class-balance policy
- probability calibration policy when probabilities are shown

Classification diagnostics should include at least:

- confusion matrix
- precision and recall
- ROC AUC or PR AUC when sample size supports it
- calibration summary when probabilities are shown

## Model Diagnostics Contract

### SPEC-DIAG-001: Required regression diagnostics

New regression runs must return and persist `model_diagnostics` with:

- task family
- sample count
- RMSE
- MAE
- rank IC or Spearman correlation
- linear IC or Pearson correlation
- actual-vs-predicted sample points
- residual sample points
- feature importance

### SPEC-DIAG-002: Diagnostic samples

Diagnostic samples should be bounded so responses remain usable. Each sample
point must preserve enough context to debug a run:

- `date`
- `symbol`
- `actual`
- `predicted`
- `residual`

### SPEC-DIAG-003: Feature importance

Feature importance must be associated with the model feature names used during
training. If a model family cannot expose importance, the run must return an
empty list and a warning instead of inventing values.

## Offline Backtest Contract

### SPEC-BACKTEST-001: Backtest posture

The strategy backtest is an offline research artifact. It is not broker
execution and must not imply live-order readiness.

### SPEC-BACKTEST-002: Strategy defaults

The default strategy family is threshold plus top-N selection with replacement
logic. The effective strategy must persist:

- `threshold`
- `top_n`
- whether the value came from a request override or spec default

### SPEC-BACKTEST-003: Price and cost assumptions

Every run must persist the versions or effective values that explain:

- label basis
- entry and exit price proxy
- fees
- slippage
- portfolio construction

### SPEC-BACKTEST-004: Strategy artifacts

New successful runs must return and persist:

- strategy metrics
- equity curve
- predictions or signals
- baseline metrics
- warnings

Strategy metrics remain important, but the result page should show model
quality first.

## Persisted Experiment Contract

### SPEC-RUN-001: Persisted artifact completeness

A persisted successful experiment must be reviewable after reload with the same
core artifacts available in the latest in-session response:

- request config
- runtime metadata
- model diagnostics
- predictions or signals
- equity curve
- baseline metrics
- strategy metrics
- warnings

### SPEC-RUN-002: Old-run fallback

Old runs that lack persisted artifacts must show an explicit fallback message.
The UI must not imply that missing diagnostics, signals, equity, or baselines
were evaluated.

### SPEC-RUN-003: Runtime metadata

Every run must persist:

- `runtime_mode`
- `default_bundle_version`
- effective strategy values
- config sources
- fallback audit
- version-pack fields that explain target, price, cost, split, bootstrap, and
  comparison semantics

## Comparison Contract

### Comparison-State Overview

| State | Meaning |
| --- | --- |
| `comparison_metadata_only` | metadata exists but final comparison semantics or artifacts are incomplete |
| `sample_window_pending` | artifacts exist but sample floors are not yet met |
| `strategy_pair_comparable` | directly comparable for strategy-pair analysis |
| `research_only_comparable` | comparable for research views but not investability claims |
| `unresolved_event_quarantine` | blocked by unresolved corporate-event issues |

### SPEC-COMP-001: Comparison dimensions

Experiment comparison must expose:

- dataset and date range
- target family and horizon
- features
- model config
- model diagnostics
- strategy metrics
- baseline deltas
- comparison eligibility and reasons

### SPEC-COMP-002: Comparable runs

Two runs should be treated as directly comparable only when the comparison view
can explain their shared and differing assumptions. At minimum, compare:

- market
- date range
- return target
- horizon
- feature set
- model family and variant
- price basis
- cost basis
- missing-feature policy

### SPEC-COMP-003: Eligibility is advisory

Comparison eligibility helps the researcher avoid invalid claims. It must not
hide model diagnostics or persisted artifacts.

## Hidden Advanced Modules

Execution, adaptive, peer, factor, external-signal, and tick archive modules
are hidden advanced or future modules for v1. They may remain in code, but they
must not be required for the default research loop.
