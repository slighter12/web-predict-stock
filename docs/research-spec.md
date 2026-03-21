# Research Specification

## Purpose

Define the normative source of truth for research and execution behavior.

## Owns

- versioned fields
- runtime modes
- data-plane rules
- target semantics
- execution semantics
- comparison labels

## Does Not Own

- implementation sequencing
- KPI formulas, thresholds, or gate truth conditions
- local developer workflow
- open `TBD-*` decision definitions

## Consumes

- `docs/validation-gates.md` for thresholds, sample floors, and gate truth
  conditions
- `docs/decision-register.md` for open `TBD-*` definitions
- `docs/plan.md` for delivery ordering

## Produces

- `SPEC-RUNTIME-*`
- `SPEC-DATA-*`
- `SPEC-EXEC-*`
- `SPEC-COMP-*`

## Decision Rule

Use this document when deciding what metadata must be persisted, what counts as
a valid research or execution state, what default semantics apply, and when two
runs are allowed to be compared.

## Spec ID Index

- `SPEC-RUNTIME-*`: runtime mode and default-bundle behavior
- `SPEC-DATA-*`: data-plane contract and tradability-state rules
- `SPEC-EXEC-*`: target, benchmark, execution, and portfolio rules
- `SPEC-COMP-*`: comparison labels and reporting semantics

## Normative Layers

The spec has four layers:

1. Runtime contract:
   how a run declares its operating mode and effective configuration
2. Data contract:
   how raw data, normalized data, and tradability states are defined
3. Execution contract:
   how targets, labels, fills, costs, and portfolios are interpreted
4. Comparison contract:
   how runs become comparable and what must be reported

## Runtime Contract

### Runtime Overview

| Concept | Requirement |
| --- | --- |
| Runtime mode | every run must persist it |
| Default bundle | required for spec-default fallback behavior |
| Config source | every configurable field must record effective value plus source |
| Auditability | fallback attempts must be explicit, not implicit |

### SPEC-RUNTIME-001: Runtime modes

- `runtime_mode` must be persisted on every run
- supported modes:
  - `runtime_compatibility_mode`
  - `vnext_spec_mode`

### SPEC-RUNTIME-002: Default bundle and config-source persistence

- `default_bundle_version` identifies the active research-spec default bundle
- every configurable run field must persist both:
  - effective value
  - value source:
    `request_override` or `spec_default`

### SPEC-RUNTIME-003: Compatibility-mode behavior

- in `runtime_compatibility_mode`, missing caller-provided
  `strategy.top_n` or `strategy.threshold` must be rejected

### SPEC-RUNTIME-004: Vnext default fallback behavior

- in `vnext_spec_mode`, omitted configurable fields may fall back to a
  `spec_default` only when the run declares the referenced
  `default_bundle_version`

### SPEC-RUNTIME-005: One-read version field pack

The following fields are part of the normative run-spec surface:

- `runtime_mode`
- `default_bundle_version`
- `threshold_policy_version`
- `price_basis_version`
- `benchmark_comparability_gate`
- `comparison_eligibility`
- `investability_screening_active`
- `capacity_screening_version`
- `adv_basis_version`
- `missing_feature_policy_version`
- `execution_cost_model_version`
- `split_policy_version`
- `bootstrap_policy_version`
- `ic_overlap_policy_version`

### SPEC-RUNTIME-006: P0 runtime-minimum field subset

The minimum metadata subset required for phase `P0` validation-ready status is:

- `runtime_mode`
- `default_bundle_version`
- per-field config-source persistence for request override versus spec default
- request-validation outcome for missing required runtime inputs
- explicit fallback audit fields showing whether default fallback was attempted,
  accepted, or rejected under the active runtime mode

## Data Contract

### Data-Plane Overview

| Topic | Requirement |
| --- | --- |
| Raw-source preservation | raw payloads must be saved before normalization |
| Replayability | raw to normalized flow must remain auditable |
| Universe logic | research universe and execution universe are distinct |
| Tradability state | missing, stale, and corporate-event states must be explicit |

### SPEC-DATA-001: Raw-source preservation

- raw source payloads must be persisted before normalization
- raw payload storage must preserve:
  - source name
  - fetch timestamp
  - parser version
  - fetch status
  - expected symbol context when applicable

### SPEC-DATA-002: Rebuild order

- rebuild flow is:
  `raw archive -> parser or versioned transform -> normalized table -> feature generation`

### SPEC-DATA-003: Raw-to-normalized traceability

- every replay unit must remain auditable through:
  - `raw_payload_id`
  - archive object reference
  - parser version
  - replay start and end timestamp
  - restore success or abort reason

### SPEC-DATA-004: Research universe and execution universe

- research universe target:
  full-market coverage
- execution universe:
  point-in-time executable subset filtered by lifecycle, completeness, event
  state, and active liquidity or capacity screens
- universe membership must remain point-in-time aware, including:
  - listing status
  - delisting date
  - ticker change mapping
  - re-listing state

### SPEC-DATA-005: Minimum execution readiness

- minimum history for execution eligibility:
  `120` trading days
- recent completeness requirement:
  at least `95%` over the latest `20` trading days
- core market data fields:
  `date`, `symbol`, `open`, `high`, `low`, `close`, `volume`

### SPEC-DATA-006: Missing data and stale-price handling

- symbols with core data gaps remain in the research universe but do not enter
  the model-ready or execution universe for that date
- held positions with core OHLCV gaps must be marked as a risk state and must
  not be increased
- suspended or stale-mark positions may remain marked at the last valid traded
  price for NAV continuity, but stale-mark periods must be flagged explicitly

### SPEC-DATA-007: Missing non-core feature policy

- missing non-core features do not block scoring when core OHLCV data is intact
- direct comparability requires the same `missing_feature_policy_version`
- model-adoption qualification also requires the same
  `missing_feature_policy_version`; otherwise any measured uplift is
  exploratory only
- tree-based models may rely on native missing handling
- other model families must declare explicit encoding, masking, imputation, or
  fallback behavior

### SPEC-DATA-008: Corporate-event handling

- dividends, splits, capital reduction, delisting, merger, tender, and ticker
  changes must be handled explicitly
- explicit handling does not imply that every event family blocks tradability
- deterministic price-adjustment families must be handled explicitly but do not
  enter `unresolved_corporate_event` solely because the event exists:
  - stock split
  - reverse split
  - cash dividend
  - stock dividend
  - capital reduction
- the following event families are blocking until point-in-time identity or
  terminal-state resolution is available:
  - merger
  - tender offer
  - delisting without a matching lifecycle terminal-state record
  - listing-status change without a matching lifecycle state transition
  - ticker change without a resolvable successor mapping
- unknown terminal events move the affected symbol and run into
  `unresolved_corporate_event` state until conversion terms are resolved
- `reference_symbol` on lifecycle `ticker_change` records is interpreted as
  `old -> new`; from `effective_date` onward the old symbol must resolve to the
  successor symbol for point-in-time execution-universe evaluation

### SPEC-DATA-009: Tradability-state required fields

Phase `P3` and later runs must persist:

- `tradability_state`
- `investability_screening_active`
- `capacity_screening_active`
- `missing_feature_policy_state`
- `corporate_event_state`
- `full_universe_count`
- `execution_universe_count`
- `execution_universe_ratio`
- bucket coverage summaries for at least one persisted liquidity or market-cap
  schema
- `tradability_contract_version` must identify the active P3 tradability
  contract used to qualify the run for governance windows; the current active
  value is `p3_tradability_monitoring_v1`
- until `TBD-001` is closed, `investability_screening_active` remains
  deliberately persisted as `false` for P3 runs; this is a policy lock that
  prevents durable investability claims, not a runtime inference failure

### SPEC-DATA-010: Important-event backfill scope

- `important_event` for `KPI-DATA-006` is limited to event families that affect
  lifecycle state, symbol identity, or deterministic price-adjustment logic:
  - listing status change
  - delisting notice or effective delisting
  - ticker change or symbol mapping change
  - stock split or reverse split
  - cash dividend or stock dividend
  - capital reduction
  - merger, swap, or tender event with published conversion terms
- event-source priority for `event_publication_ts` is:
  - official exchange or regulator publication timestamp
  - official issuer filing timestamp when the exchange copy does not expose a
    timestamp
  - vendor-published timestamp when no official timestamp is available
- if none of the above timestamps exist, the event is excluded from
  `KPI-DATA-006` and must be labeled `event_timestamp_unresolved`
- `KPI-DATA-006` must persist both `event_publication_ts` and the selected
  timestamp-source class

## Execution Contract

### Liquidity, Capacity, and Investability

### SPEC-EXEC-001: ADV basis

- base ADV window:
  `20` trading days
- default `adv_basis_version`:
  `raw_close_x_volume_active_session_v1`
- under the default basis, traded value is computed as
  `raw_close * raw_volume`
  on point-in-time active sessions with valid core OHLCV and no full-session
  halt

### SPEC-EXEC-002: Capacity AUM basis

- `portfolio_aum` is the run-level market-currency basis for capacity
  screening
- if `portfolio_aum` is omitted, ADV-based capacity screening is disabled and
  must be recorded as inactive

### SPEC-EXEC-003: Capacity screening version

- `capacity_screening_version` must encode the ex-ante pricing basis used to
  value buy-side order notional
- `capacity_screening_version` may still be persisted when
  `capacity_screening_active = false`; in that case it identifies the declared
  contract version for the run and must not be interpreted as evidence that the
  screen was applied

### SPEC-EXEC-004: Initial capacity defaults

- initial max order capacity when active:
  order notional `<= 0.5%` of `20`-day average traded value
- minimum average traded value default for v1 research runs:
  `0`

### SPEC-EXEC-005: Participation telemetry

- investable runs must persist:
  - aggregate rebalance-day buy-side participation
  - aggregate rebalance-day sell-side participation
  - touched-name count
  - `max_name_buy_participation`
  - `max_name_sell_participation`
  - `p95_name_participation`

### SPEC-EXEC-006: Investability semantics

- investability labeling and comparison eligibility are separate
- if `portfolio_aum` is missing or the traded-value floor remains `0`, the run
  must be labeled research-only and non-investable
- execution-universe filtering still applies even when the absolute
  traded-value floor is disabled
- investability-based threshold recalibration, benchmark-relative policy
  review, and benchmark-relative performance claims require
  `investability_screening_active = true`

### Target and Label Semantics

### SPEC-EXEC-007: Target family

- multiple target definitions are allowed
- the active target definition must be persisted on every run

### SPEC-EXEC-008: Signal timing

- default v1 signal timing:
  signals are formed after signal-day `S` close

### SPEC-EXEC-009: Gross label definition

- default label name:
  `gross_label_v1`
- entry day `T` is the next trading day after signal-day `S`
- label formula:
  `gross_label_v1 = adj_open[T+5_trading_days] / adj_close[T] - 1`

### SPEC-EXEC-010: Label interpretation

- `gross_label_v1` is the supervision target for cross-sectional expected
  5-trading-day gross-return ranking
- it is not a promise that every selected name will be held until
  `T+5_trading_days` open
- label prices must be corporate-action-aware and fee-free

### Execution and Price Basis Semantics

### SPEC-EXEC-011: Daily execution default

- sell flagged exits at entry-day `T` open
- keep retained positions through `T`
- buy new positions before entry-day `T` close
- daily-mode fill proxies use the official open for exits and official close
  for entries unless another declared proxy version overrides them

### SPEC-EXEC-012: Price-basis versioning

- `price_basis_version` must at minimum encode:
  - label basis
  - execution entry proxy basis
  - execution exit proxy basis
  - benchmark basis

### SPEC-EXEC-013: Benchmark compatibility

- `benchmark_comparability_gate` may be `true` only when the benchmark version
  and basis are explicitly compatible with the strategy return basis
- TW benchmark target is a total-return-compatible benchmark when available
- if only a price-return proxy is available, the run must persist a distinct
  benchmark version and must not present it as directly comparable to
  corporate-action-aware strategy returns

### SPEC-EXEC-014: Cost model versioning

- backtest results are net of configured fees, taxes, slippage, and corporate
  event handling
- every run must persist `execution_cost_model_version` together with the
  effective fee, tax, slippage, and market-impact configuration

### Portfolio Construction Defaults

### SPEC-EXEC-015: Strategy family

- default strategy family:
  threshold plus top-N with replacement logic
- default selection settings for the v1 research-spec bundle:
  - `strategy.top_n = 10`
  - entry threshold:
    predicted `gross_label_v1 > 1%`
  - replacement buffer:
    candidate exceeds existing holding by `+1%`
- these are versioned default-bundle values, not universal invariants across
  all requests or target families

### SPEC-EXEC-016: Threshold policy version

- default threshold-policy version:
  `static_absolute_gross_label_v1`
- non-`gross_label_v1` target families must define and persist their own
  explicit thresholding or ranking rules

### SPEC-EXEC-017: Position construction

- default weighting:
  equal weight
- partial cash is allowed
- `100%` cash is allowed
- default sell rule:
  exit when score falls below the active threshold or when replaced by a
  stronger candidate

## Comparison Contract

### Comparison-State Overview

| State | Meaning |
| --- | --- |
| `comparison_metadata_only` | metadata exists but final comparison semantics are not ready |
| `sample_window_pending` | final schema exists but sample floors are not yet met |
| `strategy_pair_comparable` | directly comparable for strategy-pair analysis |
| `research_only_comparable` | comparable for research views but not execution-ready claims |
| `unresolved_event_quarantine` | blocked by unresolved corporate-event issues |

### SPEC-COMP-001: Comparison eligibility labels

- allowed values:
  - `comparison_metadata_only`
  - `sample_window_pending`
  - `strategy_pair_comparable`
  - `research_only_comparable`
  - `unresolved_event_quarantine`

### SPEC-COMP-002: Provisional versus final comparison states

- `comparison_metadata_only` is the provisional state used when run-registry
  metadata exists but execution semantics, sample floors, or both are not yet
  ready for final comparability classification
- `sample_window_pending` is the provisional state used after the final
  comparison metadata schema exists but the required sample windows or
  observation floors are not yet satisfied
- `strategy_pair_comparable`, `research_only_comparable`, and
  `unresolved_event_quarantine` are final comparison states and must not be
  assigned until the required final semantics and sample-floor checks exist

### SPEC-COMP-003: Final comparison gate truth table

- a run may be labeled `strategy_pair_comparable` only when:
  - no unresolved corporate event remains open
  - `price_basis_version` is present
  - `threshold_policy_version` is present
  - `execution_cost_model_version` is present
  - effective sample floors defined in `docs/validation-gates.md` are satisfied
- benchmark-relative comparison additionally requires
  `benchmark_comparability_gate = true`
- investability or execution-ready views additionally require
  `investability_screening_active = true`

### SPEC-COMP-004: Comparison review matrix and cadence

- governance KPIs that use family-day denominators must rely on a persisted
  `comparison_review_matrix_version`
- each matrix version must define:
  - the mandatory family set
  - the scheduled review cadence
  - the denominator construction rule for scheduled family-day observations
- ad hoc reruns may add exploratory observations but must not expand the
  denominator of matrix-based governance KPIs

### SPEC-COMP-005: Primary comparison surfaces

- research-only exploratory strategy-pair views may include
  `strategy_pair_comparable` runs even when investability screening is inactive
- benchmark-relative ranking, policy review, threshold recalibration, and
  execution-ready views require both:
  - `benchmark_comparability_gate = true`
  - `investability_screening_active = true`
- threshold recalibration and benchmark-relative policy review are
  policy-qualification activities and do not block phase sample-complete status

### SPEC-COMP-006: Reporting fields

- comparable run reports must persist enough metadata to explain:
  - target definition
  - execution definition
  - benchmark definition
  - universe filters
  - capacity-screening basis
  - missing-feature policy
  - comparison eligibility
  - investability screening status

### SPEC-COMP-007: Model adoption comparison policy

- cross-model adoption claims must use a persisted
  `adoption_comparison_policy_version`
- the compared candidate and baseline runs must share the same:
  - target definition
  - execution definition
  - execution cost basis
  - `missing_feature_policy_version`
- the policy must control portfolio-construction confounders through one of the
  following approaches:
  - fixed selection-count and weighting rules under the same execution and cost
    basis
  - matched-exposure and matched-turnover comparison overlays recorded together
    with the adoption result
- raw score-scale differences alone must not be treated as evidence of model
  adoption value
