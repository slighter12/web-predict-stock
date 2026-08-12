# Research Specification

## Purpose

Define the normative source of truth for the `TW daily Quant ML Research
Workbench` v1.

## Owns

- prediction task semantics
- dataset and feature contracts
- model diagnostics
- offline backtest artifacts
- persisted research-run artifacts
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
a valid research result, and when two research runs can be compared.

## Normative Layers

The v1 spec has six layers:

1. Dataset contract
2. Feature contract
3. Prediction task contract
4. Model diagnostics contract
5. Offline backtest contract
6. Persisted research-run and comparison contract

Phase 2 adds an opinion layer on top of the persisted research artifacts. The
opinion layer is not a broker, live-order, or portfolio-control contract.

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

### SPEC-DATA-004: TW universe caveat

Successful TW runs must make the lack of point-in-time membership visible where
results are read. New runs persist the warning; reloaded TW runs expose the
non-blocking comparison caveat
`TW_POINT_IN_TIME_MEMBERSHIP_UNAVAILABLE`, including legacy records whose market
can be recovered from their saved request. The caveat does not establish that
historical price coverage is complete and does not change comparison eligibility
or opinion viability by itself.

## Feature Contract

### SPEC-FEATURE-001: Feature specification

Every feature row must persist:

- `name`
- `window`
- `source`
- `shift`

Feature shifts are part of the leakage-control contract and must remain visible
in the request config. New research-run requests require `shift >= 1`; persisted
legacy request payloads with `shift=0` remain reviewable, but must be updated
before rerun.

### SPEC-FEATURE-002: Feature lineage

Advanced factor, peer, and external-signal fields may exist on the request, but
they are hidden advanced modules in v1. A baseline research run must not require
them.

### SPEC-FEATURE-003: Missing-feature policy

Extra Trees, XGBoost, and Random Forest use the same complete-case policy: any
row with a non-finite model input is excluded before training or prediction.
Each run persists `missing_feature_policy_version="complete_case_model_inputs_v1"`
and `missing_feature_policy_state="complete_case_applied"`. Legacy metadata
values remain readable but do not define current model behavior.

## Prediction Task Contract

### SPEC-TASK-001: Supported task families

The v1 workbench recognizes two prediction task families:

- `regression`
- `classification`

The two families have different jobs and neither is subordinate to the other
(ADR-0005). Because the strategy is long-only, the binary direction classifier
is the **admission gate**: it decides whether a symbol may enter the candidate
set at all. The regression score is the **ranking and weighting** signal: it
orders and sizes what the gate admitted.

Regression-only requests remain supported, but they cannot emit a prospective
hybrid opinion — without a gate there is no admission decision.

### SPEC-TASK-002: Regression target

Regression predicts a numeric forward return target derived from:

- `return_target`
- `horizon_days`
- active price basis

The active implementation uses tabular tree regressors and produces continuous
scores used by the strategy backtest.

The v1 baseline builder defaults to Extra Trees so the common local research
loop does not require the XGBoost native runtime. XGBoost and Random Forest
remain selectable tree-regression variants.

### SPEC-TASK-003: Classification target

Direction classification persists:

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

The direction admission classifier is implemented as part of the hybrid
regression-ranking workflow; a standalone classification Research Run remains
deferred. The current chronological sigmoid calibration gate is provisional and
versioned as `chronological_tail_20pct_min20_class5_v1`: the calibration tail
uses at least 20 samples, and both the base-training and calibration windows
require at least five samples from each class. These are minimum support checks,
not proof of calibrated performance; the positive-return and confirmation
thresholds remain separately identifiable in persisted run configuration and
diagnostics.

Holdout predictions are evaluation artifacts. A prospective opinion requires
one finite regression score and calibrated up probability for every requested
symbol on the same latest feature date; incomplete or mixed-date snapshots must
return `no-opinion`.

Direction diagnostic metrics are pooled across evaluated symbols. `sample_count`
is the pooled holdout-row count and `calibration_sample_count` is the sum across
symbols; neither field establishes per-symbol skill. Prospective full-data model
fits and fold-level validation classifiers scale with the requested symbol and
fold counts, so performance claims require separate profiling evidence.

### SPEC-TASK-004: Validation outcome

Cross-sectional validation must split one sorted intersection of model-ready
symbol dates so every symbol in a fold uses the same train and test dates.
Validation summaries expose `evaluation_status` and `status_reason`: an
`evaluated` summary has non-empty metrics, while a `not_evaluated` summary has
empty metrics and a concrete reason. An unavailable auxiliary validation result
does not fail an otherwise successful research run, and its reason must also be
persisted as a warning.

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
execution and must not imply live-order readiness. A run using
`execution_route="research_only"` remains `tradability_state="research_only"`;
`execution_ready` requires an explicitly non-research execution route and is an
internal-foundation state under ADR-0017, not public v1 capability.

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

## Persisted Research-Run Contract

### SPEC-RUN-001: Persisted artifact completeness

A persisted successful research run must be reviewable after reload with the same
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

Persisted run responses expose an additive artifact summary derived from the
saved row and request payload:

- `artifact_completeness`: `complete`, `partial`, or `metadata_only`
- `present_artifacts`
- `missing_artifacts`
- `not_required_artifacts`
- `comparison_caveats`

Validation and baselines are `not_required` when they were not requested.
Missing values mean the artifact is unavailable on that saved record, not that
the research run evaluated the artifact and produced an empty artifact.

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

Research-run comparison must expose:

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

Artifact completeness caveats are blocking comparison context. A run that is
`partial` or `metadata_only`, or a run that did not finish successfully, must
not be treated as a complete comparable result.

## Phase 2 Opinion Contract

### SPEC-OPINION-001: Opinion artifact shape

A Phase 2 opinion artifact must be derived from an existing persisted research
run. It must include:

- strategy-level opinion state: `viable`, `no-opinion`, or `do-not-adopt`
- buy-candidate list
- sell-or-avoid list
- watch list
- evidence and risk context for each populated list item
- invalidation notes explaining when the opinion should not be adopted

Each populated symbol row must include:

- symbol
- model score
- strategy-derived weight or position signal
- evidence reason
- risk or warning
- invalidation note
- source artifact references

Candidate lists may be empty. If the evidence is insufficient, the artifact
must return `no-opinion` or `do-not-adopt` instead of forcing a buy, sell, or
watch result.

Artifact completeness only means the model output is reviewable and traceable.
It does not establish out-of-sample predictive skill or investment viability;
the opinion builder does not invent a performance-quality threshold for either
claim.

### SPEC-OPINION-002: Evidence traceability

Each populated opinion row must point back to at least one persisted research
artifact that explains the row. Valid source artifact families include:

- model diagnostics
- score, prediction, signal, or position output
- strategy metrics
- baseline deltas
- validation summary
- warnings
- artifact completeness or comparison caveats

When a required artifact is missing, partial, metadata-only, or not evaluated,
the opinion artifact must make that limitation visible through the evidence
reason, risk or warning, invalidation note, or strategy-level state.

### SPEC-OPINION-003: Research-method references

External tools may inform local research methods, but they must not become
implicit runtime dependencies. Jesse-style strategy lifecycle, signal-to-position
translation, robustness checks, parameter sensitivity, and report discipline may
be implemented locally when they improve opinion quality.

Research methods added from external references must preserve:

- persisted request and result artifacts
- model-first diagnostics before strategy claims
- offline backtest posture
- explicit source, version, or policy metadata
- comparison caveats when assumptions differ

### SPEC-OPINION-004: Opinion boundary

An opinion artifact is a model-backed research opinion for manual adoption. It
must not imply:

- personalized investment advice
- broker routing
- live-order readiness
- automatic rebalancing
- account-level portfolio control

Direct action-language labels are allowed only when the artifact preserves the
manual-adoption boundary and can also output `no-opinion` or `do-not-adopt`.
An artifact reconstructed from a persisted run with `execution_ready` or other
non-research execution metadata must fail the manual-adoption review check,
return no actionable rows, and remain `no-opinion` or `do-not-adopt`.

## Hidden Advanced Modules

Execution, adaptive, peer, factor, external-signal, and tick archive modules
are hidden advanced or future modules for v1. Internal simulation and live-stub
foundations may remain under ADR-0017, but no execution route is a public v1
product capability and none may be required for the default research loop.
