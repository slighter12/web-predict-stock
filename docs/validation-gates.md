# Validation and KPI Gates

## Purpose

Define metric formulas, denominators, windows, thresholds, and gate truth
conditions.

## Owns

- KPI definitions and windows
- phase acceptance gates
- claim qualification gates
- metric-specific interpretation rules

## Does Not Own

- runtime behavior or portfolio semantics
- implementation sequencing
- local developer workflow
- open `TBD-*` decision definitions

## Consumes

- `docs/research-spec.md` for normative behavior and persisted-field semantics
- `docs/decision-register.md` for open `TBD-*` definitions
- `docs/plan.md` for phase labels and ordering

## Produces

- `KPI-*`
- `GATE-*`

## Decision Rule

Use this document when deciding which metrics prove readiness, how a metric is
computed, what threshold applies, and which gate passes or remains exploratory.

## Gate and KPI Index

- `KPI-DATA-*`: data and recovery metrics
- `KPI-MICRO-*`: market microstructure and coverage metrics
- `KPI-TICK-*`: tick archive metrics
- `KPI-COMP-*`: comparability metrics
- `KPI-THRESH-*`: threshold and calibration metrics
- `KPI-COST-*`: cost-model metrics
- `KPI-EXT-*`: external-signal freshness and coverage metrics
- `KPI-FACTOR-*`: factor-catalog coverage and usability metrics
- `KPI-RESEARCH-*`: research-governance metrics
- `KPI-ADOPT-*`: model-adoption metrics
- `KPI-SIM-*`: simulation readback metrics
- `KPI-LIVE-*`: live-control metrics
- `KPI-LIVEQ-*`: live execution-quality metrics
- `KPI-ADAPT-*`: adaptive-isolation metrics
- `GATE-VERIFICATION-*`: structural verification gates
- `GATE-PERF-*`: benchmark-relative performance qualification gates
- `GATE-POLICY-*`: investability-based policy qualification gates
- `GATE-ADOPT-*`: model-adoption qualification gates
- `GATE-LIVEQ-*`: live execution-quality qualification gates
- `GATE-P*-001`: phase acceptance gates
- `GATE-P*-OPS-001`: phase operational-validation gates

## Phase Gate Model

Use two gate layers for phase governance:

- phase exit gate:
  engineering-completion gate used to unblock dependent implementation work;
  it should rely on structural artifacts, deterministic fixtures, and short or
  bounded verification workloads rather than long observation windows
- operational validation gate:
  long-window readiness gate used to declare a phase operationally mature for
  stable monitoring, governance, or comparison surfaces; it must not block
  downstream engineering by default

Interpretation rule:

- `GATE-P*-001` means the phase exit gate
- `GATE-P*-OPS-001` means the operational validation gate
- performance, policy, adoption, and live-quality gates remain claim gates on
  top of those two layers

## Metric Definition Rules

- Trading-day basis:
  unless a metric states otherwise, horizons, completeness, overlap, and sample
  counts use the active exchange trading calendar
- Confidence-interval default:
  when a 95% interval is required, use a persisted bootstrap policy version
- Split-policy rule:
  comparable runs must persist `split_policy_version` together with training,
  validation, and embargo settings when applicable
- Missing-sample rule:
  symbols blocked by lifecycle state, unresolved corporate events, or missing
  target availability are excluded from denominators and recorded in run
  warnings
- Benchmark-profile rule:
  `KPI-DATA-005`, `KPI-TICK-002`, and `KPI-TICK-003` are reproducible only when
  the measured workload persists a `benchmark_profile_id` that records at
  minimum CPU class, memory size, storage type, compression settings, archive
  layout version, and network class when remote archive transfer is involved
- Tick-policy binding rule:
  until `TBD-002` is resolved and the archive storage policy is frozen as the
  binding baseline, `KPI-TICK-*` values are exploratory telemetry only; they
  may be measured and trended but must not determine durable `P2` pass or fail
- Simulation-platform binding rule:
  until `TBD-003` is resolved and the simulation platform is frozen as the
  binding baseline, `KPI-SIM-*` values are exploratory telemetry only; they may
  be measured and trended but must not determine durable `P9` pass or fail
- Investability-policy binding rule:
  `GATE-POLICY-001` and benchmark-relative policy qualification remain
  exploratory until `TBD-001` is resolved and the TW calibrated traded-value
  floor is part of the active investability baseline
- Review-matrix denominator rule:
  governance KPIs using family-day denominators must use scheduled family-day
  observations from a persisted `comparison_review_matrix_version`; ad hoc
  reruns do not expand the denominator
- Claim-bootstrap default:
  unless a newer persisted `bootstrap_policy_version` overrides it,
  `KPI-COMP-009` uses a paired stationary bootstrap on the matched daily net
  active return series with `95%` confidence intervals, `5000` replications,
  and block length
  `max(10, effective_label_horizon_trading_days, ceil(max(1, median_realized_holding_days)))`
- Multiple-comparison default:
  when more than one strategy or policy family is reviewed in the same declared
  claim set, claim gates must apply Holm-Bonferroni correction across the
  primary comparisons named in that review set unless a newer persisted
  multiple-comparison policy version overrides it
- Recovery-drill sampling rule:
  `KPI-DATA-004` is evaluated on scheduled monthly recovery drills and any real
  recovery incidents observed in the review window; `KPI-DATA-007` enforces the
  minimum scheduled drill cadence required for sample-complete status
- Important-event sample rule:
  `KPI-DATA-006` is a hard gate only when `KPI-DATA-008 >= 5`; when the sample
  is below that threshold, the metric must be reported as `insufficient_sample`
  and does not block `GATE-P1-OPS-001`

## KPI Dictionary

### Data and Recovery

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-DATA-001` | daily fetch success rate | `successful_fetches / scheduled_fetch_attempts` | rolling 20 trading days | `>= 99.0%` |
| `KPI-DATA-002` | retry-adjusted success rate | `fetches_succeeding_within_retry_policy / scheduled_fetch_attempts` | rolling 20 trading days | `>= 99.5%` |
| `KPI-DATA-003` | monthly per-symbol completeness | `valid_core_records / expected_core_market_records` per symbol | monthly | `>= 95.0%` |
| `KPI-DATA-004` | recovery point objective | completed-trading-day delta to latest replayable day | per recovery event | `<= 1 completed trading day` |
| `KPI-DATA-005` | one-week rebuild p95 | p95 elapsed time for one-week normalized rebuild with a persisted `benchmark_profile_id` | benchmark workload bucket | `< 4 hours` |
| `KPI-DATA-006` | important-event backfill window | `event_recover_ts - event_publication_ts` for `important_event` records defined by `SPEC-DATA-010` | active review window | `<= 24 hours` |
| `KPI-DATA-007` | recovery-drill coverage | completed scheduled recovery drills divided by scheduled recovery drills | rolling 90 calendar days | `= 100%` with at least 1 scheduled monthly drill |
| `KPI-DATA-008` | important-event sample sufficiency | important events with resolved publication timestamps in the active review window | rolling 90 calendar days | `>= 5` for direct gating; otherwise report `insufficient_sample` |

### Microstructure and Tradability

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-MICRO-001` | execution-universe ratio drift | active 20-trading-day average `execution_universe_count / full_universe_count` compared with trailing 60-trading-day baseline average | 20-day active window plus 60-day baseline with at least 40 valid days | absolute relative drift `<= 10%` |
| `KPI-MICRO-002` | required-bucket coverage drift | active 20-trading-day average bucket coverage ratio compared with trailing 60-trading-day baseline average for each required bucket | per required bucket using the same 20-day active window and 60-day baseline | every required bucket absolute relative drift `<= 10%` |
| `KPI-MICRO-003` | stale-risk share | `stale_mark_days_with_open_positions / comparison_window_days` with baseline drift check | active comparison window plus trailing 60-trading-day baseline monitor when available | absolute share `<= 5%` and absolute relative drift versus baseline `<= 20%` |

### Tick Archive

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-TICK-001` | compression target | size reduction versus uncompressed raw archive | per market and source archive | `>= 50%` |
| `KPI-TICK-002` | restore latency p95 | p95 restore time for up to 5 compressed GB per day with a persisted `benchmark_profile_id` | benchmark size bucket | `< 30 minutes` |
| `KPI-TICK-003` | restore throughput history | `compressed_restore_gb_per_minute` with p50 and p95 under a persisted `benchmark_profile_id` | rolling 20 trading days | required telemetry |

### Comparability and Performance Claims

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-COMP-001` | primary overlap window | matched overlap between directly compared run pairs | per run pair | `>= 252 trading days` |
| `KPI-COMP-002` | IC valid sample count | valid `IC_t` observations | per comparable family | `>= 120` |
| `KPI-COMP-003` | overlap-adjusted IC sample count | effective IC sample under `ic_overlap_policy_version` | per comparable family | `>= 24` |
| `KPI-COMP-004` | closed-lot count | closed trade lots in comparison window | per comparable family | `>= 60` |
| `KPI-COMP-005` | trade-day count | days with at least one executed entry or exit | per comparable family | `>= 40` |
| `KPI-COMP-006` | distinct entry cohorts | unique `(symbol, initial_entry_trade_date)` cohorts | per comparable family | `>= 20` |
| `KPI-COMP-007` | exposure floor | invested days or average gross exposure | per comparison window | `>= 60 invested days` or `>= 20%` average exposure |
| `KPI-COMP-008` | risk-metric completeness | complete risk-metric coverage after exclusions | per compared window | `>= 95%` for display, `>= 99%` for path-dependent ranking |
| `KPI-COMP-009` | outperformance claim gate | 95% lower bound and point estimate of annualized net active return | primary benchmark-relative surface | lower bound `> 0` and point estimate `>= +1.0%` |

### Threshold and Cost Policy

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-THRESH-001` | threshold review cadence | review checkpoint frequency | calendar cadence | every 4 weeks or after major training-window change |
| `KPI-THRESH-002` | recalibration minimum windows | completed out-of-sample windows | per policy comparison | `>= 2` |
| `KPI-THRESH-003` | recalibration effect floor | absolute underperformance magnitude in `active_return_ir` units | same overlap window | `>= 0.10` |
| `KPI-COST-001` | cost-model completeness | non-null cost-model version plus fee, tax, and slippage rules | per comparable family | required |

### External Signals

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-EXT-001` | exact-availability coverage | records with direct `available_at` metadata share | active review window | `>= 95%` |
| `KPI-EXT-002` | fallback-timestamp ratio | records using fallback mapping share | active review window | `<= 5%` |
| `KPI-EXT-003` | undocumented leakage rate | records lacking direct or persisted fallback timing | audited sample | `= 0` |

### Factor Catalog and Usability

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-FACTOR-001` | factor catalog completeness | declared scoring-eligible factors with persisted formula or definition, lineage, timing semantics, version, and missing-value policy divided by declared scoring-eligible factors in the active `factor_catalog_version` | per catalog version | `= 100%` |
| `KPI-FACTOR-002` | usable-factor ratio | scoring-eligible factors meeting the declared minimum coverage rule on the active execution universe divided by scoring-eligible factors in the active `factor_catalog_version` | rolling 20 trading days | `>= 80%` |
| `KPI-FACTOR-003` | factor materialization latency p95 | p95 of `factor_available_ts - source_available_at` or persisted fallback source availability timestamp for scoring-eligible factors | rolling 20 trading days | `<= 1 trading day` |

### Research Governance

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-RESEARCH-001` | research-only scheduled family-day ratio | distinct scheduled family-day pairs labeled research-only divided by scheduled family-day pairs in the persisted review matrix | active review window with at least 120 scheduled family-day observations | `<= 30%` |
| `KPI-RESEARCH-002` | alignment completeness | non-null `price_basis_version`, `threshold_policy_version`, and `comparison_eligibility` | per comparable family | required |
| `KPI-RESEARCH-003` | turnover and concentration reporting | turnover plus at least one concentration metric | per comparable family | required |
| `KPI-RESEARCH-004` | tradability-state completeness | share of phase `P3+` runs that persist all `SPEC-DATA-009` required fields with non-null values | rolling 20-run window | `= 100%` |
| `KPI-RESEARCH-005` | review-matrix completeness | scheduled family-day observations with persisted `comparison_review_matrix_version` and scheduled cadence metadata divided by scheduled family-day observations in the active review window | active review window | `= 100%` |

### Model Adoption

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-ADOPT-001` | model adoption uplift | point-estimate uplift in `active_return_ir` versus the accepted statistical baseline family on the matched comparison window under the same target, execution, and cost basis | matched comparison window satisfying `KPI-COMP-001` to `KPI-COMP-008` | `>= +0.10` |
| `KPI-ADOPT-002` | model adoption exposure mismatch | absolute difference in average gross exposure between the candidate model family and the accepted statistical baseline under the declared `adoption_comparison_policy_version` | matched comparison window | `<= 5 percentage points` |
| `KPI-ADOPT-003` | model adoption turnover mismatch | absolute relative difference in average turnover between the candidate model family and the accepted statistical baseline under the declared `adoption_comparison_policy_version` | matched comparison window | `<= 20%` |

### Simulation and Live Execution

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-SIM-001` | simulation readback rate | `readback_events_within_window / submitted_simulation_orders` | rolling 20 trading days per platform and market | `>= 99.0%` within 30 minutes |
| `KPI-SIM-002` | simulation readback latency p95 | p95 of `readback_ts - submit_ts` for successful readbacks | rolling 30-day window per platform and market | `<= 30 minutes` |
| `KPI-SIM-003` | simulation failure-taxonomy coverage | classified failed readbacks divided by total failed readbacks | rolling 20 trading days | `= 100%` |
| `KPI-LIVE-001` | manual-confirmation coverage | confirmed live orders divided by submitted live orders | rolling 20 live-order events | `= 100%` |
| `KPI-LIVE-002` | risk-check coverage | live orders with persisted pre-submit risk checks divided by submitted live orders | rolling 20 live-order events | `= 100%` |
| `KPI-LIVE-003` | unconfirmed live-order path count | live orders submitted without manual confirmation | rolling 20 live-order events | `= 0` |
| `KPI-LIVEQ-001` | broker reject rate | `broker_rejected_live_orders / submitted_live_orders` | rolling 20 live-order events | `<= 2.0%` |
| `KPI-LIVEQ-002` | broker acknowledgment latency p95 | p95 of `broker_ack_ts - submit_ts` for acknowledged live orders | rolling 20 live-order events | `<= 60 seconds` |
| `KPI-LIVEQ-003` | realized slippage p95 | p95 absolute realized slippage versus the declared live execution proxy, in basis points | rolling 20 filled live-order events | `<= 50 bps` |
| `KPI-LIVEQ-004` | reconciliation break rate | unreconciled live orders or fills divided by submitted live orders | rolling 20 live-order events | `= 0` |

### Adaptive Isolation

| ID | Metric | Formula or definition | Window | Gate |
| --- | --- | --- | --- | --- |
| `KPI-ADAPT-001` | adaptive opt-in coverage | adaptive runs with explicit opt-in flag divided by adaptive runs | rolling 50 adaptive runs or full history when fewer | `= 100%` |
| `KPI-ADAPT-002` | default-surface contamination count | adaptive runs appearing in default non-adaptive comparison or execution-ready surfaces | rolling 50 adaptive runs or full history when fewer | `= 0` |
| `KPI-ADAPT-003` | rollout-control completeness | adaptive runs with persisted rollout-control metadata divided by adaptive runs | rolling 50 adaptive runs or full history when fewer | `= 100%` |

## Comparison Metrics

Accepted comparable runs must publish the following comparison statistics:

- `gross_return`:
  compounded return before fees, taxes, slippage, and explicit market-impact
  deductions
- `net_return`:
  compounded return after configured execution costs
- `IC_mean`:
  mean cross-sectional Spearman rank correlation between model scores and the
  realized target
- `IC_IR`:
  `mean(IC_t) / std(IC_t)` when defined
- `hit_rate`:
  fraction of closed trade lots with strictly positive realized net return
- `open_lot_pnl_share`:
  `mtm_open_lot_pnl / realized_and_marked_portfolio_pnl`
- `distinct_entry_cohort_count`:
  number of unique `(symbol, initial_entry_trade_date)` cohorts
- `median_realized_holding_days`
- `realized_holding_days_p25`
- `realized_holding_days_p75`
- `exit_before_label_horizon_ratio`
- `turnover`
- `trade_days`
- `volatility`
- `max_drawdown`
- `sharpe`
- `exposure_adjusted_sharpe` when capital-efficiency reporting is enabled
- `active_return_ir`
- `annualized_net_active_return`
- concentration metrics such as `top10_weight_share` or `HHI`

## Metric-Specific Rules

### IC overlap handling

- `KPI-COMP-003` must use the persisted `ic_overlap_policy_version`
- offset-cohort counts must not be summed ad hoc

### Data completeness aggregation rules

- `KPI-DATA-003` remains a per-symbol metric
- for `GATE-P1-OPS-001`, the active symbol denominator is the set of symbols
  with `expected_core_market_records > 0` in the evaluated month after
  lifecycle-state exclusions already applied by the active data contract
- `GATE-P1-OPS-001` passes the `KPI-DATA-003` portion only when at least `95%`
  of active symbols individually satisfy `KPI-DATA-003 >= 95.0%`
- the gate report must also publish:
  - active symbol count
  - passing symbol count
  - passing symbol ratio
  - p50 and p05 of monthly per-symbol completeness

### Microstructure monitor rules

- `KPI-MICRO-001` and `KPI-MICRO-002` use the same deterministic drift rule:
  `abs(active_20d_avg - baseline_60d_avg) / max(baseline_60d_avg, 0.01)`
- required buckets for `KPI-MICRO-002` are all persisted liquidity or
  market-cap buckets whose trailing 60-trading-day average share of the full
  universe is `>= 5%`
- `KPI-MICRO-003` baseline drift uses:
  `abs(active_stale_risk_share - baseline_60d_avg_stale_risk_share) / max(baseline_60d_avg_stale_risk_share, 0.01)`
- if the 60-trading-day baseline window is unavailable, `KPI-MICRO-001` to
  `KPI-MICRO-003` may be reported as bootstrap-only and cannot be labeled
  operational-ready until the baseline exists

### Lot stitching

- trade-outcome metrics must be based on deterministic trade lots
- same-symbol add-ons create new lots
- partial exits close lots by a persisted lot-matching rule

### Headline metric usage

- pure strategy-pair research surfaces use a fixed descriptive metric pack
- benchmark-relative ranking, policy review, threshold recalibration, and
  outperformance review default to `active_return_ir`
- `exposure_adjusted_sharpe` is a side metric, not the default ranking headline

### Research-governance denominator rules

- `KPI-RESEARCH-001` and `KPI-RESEARCH-005` use only scheduled family-day
  observations from the persisted review matrix
- the review matrix must define the mandatory family set and fixed run cadence
- `KPI-RESEARCH-001` and `KPI-RESEARCH-005` may satisfy `GATE-P4-OPS-001` only
  when the active review matrix schedules at least `20` family-day observations
  per calendar month across the mandatory family set; slower cadences remain
  exploratory governance telemetry only
- reruns may overwrite the observation assigned to a scheduled family-day slot
  but may not add extra denominator slots

### Model-adoption comparison rules

- `KPI-ADOPT-001` to `KPI-ADOPT-003` must use a persisted
  `adoption_comparison_policy_version` as defined in `SPEC-COMP-007`
- the compared candidate and baseline runs must share the same
  `missing_feature_policy_version`; otherwise `KPI-ADOPT-*` is exploratory only
- adoption qualification requires both economic uplift and controlled
  exposure or turnover mismatch; otherwise the result is exploratory only
- durable adoption qualification additionally requires a paired uncertainty
  check on the matched comparison window using the active
  `bootstrap_policy_version`, or the claim-bootstrap default when no newer
  persisted policy exists
- unless a newer persisted adoption-policy version overrides it,
  `GATE-ADOPT-001` requires the paired `95%` lower bound of the candidate-minus-
  baseline `active_return_ir` uplift to remain `> 0`

### Factor metric rules

- `KPI-FACTOR-001` to `KPI-FACTOR-003` use only factors declared
  scoring-eligible in the active `factor_catalog_version`
- exploratory factors may be stored in the catalog but do not enter the
  denominator until they are promoted to scoring-eligible status
- the minimum coverage rule referenced by `KPI-FACTOR-002` must be versioned and
  persisted together with the active factor catalog

### External-signal audit rules

- `KPI-EXT-003` uses a per-source-family audited denominator within the active
  review window
- the audited denominator for each source family must be
  `min(source_window_record_count, max(50, ceil(0.05 * source_window_record_count)))`
- when fallback-timestamp records exist in the active review window, the audit
  sample must include at least `min(20, fallback_timestamp_record_count)` of
  those records
- the audit draw rule must be deterministic and persisted together with the
  audit result

### Live-quality qualification rules

- `KPI-LIVEQ-001` to `KPI-LIVEQ-004` on rolling 20 live-order events remain the
  short-window protection layer used to catch immediate regressions
- `GATE-LIVEQ-001` is a durable qualification gate only when the active review
  window also includes at least:
  - `100` submitted live orders for reject-rate, acknowledgment-latency, and
    reconciliation evaluation
  - `60` filled live-order events for realized-slippage evaluation
- when the long-window sample floor is not met, `KPI-LIVEQ-*` may still be
  published as protective telemetry, but `GATE-LIVEQ-001` remains
  `insufficient_sample`
- unless a newer persisted live-quality policy overrides it, durable
  qualification requires:
  - `KPI-LIVEQ-001`, `KPI-LIVEQ-002`, and `KPI-LIVEQ-004` to pass on both the
    rolling 20-event monitor and the trailing 100 submitted-live-order window
  - `KPI-LIVEQ-003` to pass on both the rolling 20-fill monitor and the
    trailing 60 filled-live-order window

## Verification Gates

### GATE-VERIFICATION-001

- no phase is complete if its required KPI inputs are structurally missing from
  implementation output
- fixture hardening uses the default v1 tolerance policy:
  - discrete transitions and states:
    exact match
  - deterministic floating metrics:
    `abs <= 1e-7` and `rel <= 1e-6`
  - documented reordering assumptions:
    explicit fixture-level tolerance with rationale

### GATE-VERIFICATION-002

- if a phase depends on a rolling or monthly KPI window longer than the
  implementation window, the phase may be bootstrap-complete but must not be
  labeled operationally validated until the required history exists

## Performance Qualification Gates

### GATE-PERF-001

- purpose:
  benchmark-relative outperformance and policy-level alpha claims
- preconditions:
  the relevant phase is already structural-complete and sample-complete
- pass condition:
  `KPI-COMP-009`

### GATE-POLICY-001

- purpose:
  investability-based threshold recalibration and benchmark-relative policy
  review
- preconditions:
  the relevant phase is already structural-complete and sample-complete
  and `investability_screening_active = true`
  and `TBD-001` is resolved through an active TW calibrated traded-value floor
- pass condition:
  `KPI-THRESH-001` to `KPI-THRESH-003`

### GATE-ADOPT-001

- purpose:
  adopting a new ML or DL model family into the accepted model set
- preconditions:
  phase `P6` is already structural-complete and sample-complete
  and the compared candidate and baseline runs share the same
  `missing_feature_policy_version`
- pass condition:
  `KPI-ADOPT-001` to `KPI-ADOPT-003`
  and the paired `95%` lower bound of candidate-minus-baseline
  `active_return_ir` uplift remains `> 0`

### GATE-LIVEQ-001

- purpose:
  durable live execution-quality qualification after guarded live controls
  exist, with short-window regression protection
- preconditions:
  phase `P10` is already structural-complete and sample-complete
  and the active review window includes at least `100` submitted live orders
  and at least `60` filled live-order events
- pass condition:
  the short-window protection layer and the long-window qualification layer
  both pass as defined in the live-quality qualification rules

## Phase Acceptance Gates

### GATE-P0-001

- required artifacts:
  versioned default bundle, runtime-mode regression fixtures, config-source
  persistence
- pass condition:
  zero ambiguous fallback cases and explicit coverage of both runtime modes

### GATE-P1-001

- required artifacts:
  raw archive, normalized restore flow, source metadata, lifecycle records,
  scheduled recovery drills, and important-event timestamp-source persistence
- pass condition:
  `KPI-DATA-004`, `KPI-DATA-005`, and `GATE-VERIFICATION-001`

### GATE-P1-OPS-001

- purpose:
  operationally validate the daily ingestion and recovery process over live
  observation windows
- preconditions:
  `GATE-P1-001`
- pass condition:
  `KPI-DATA-001`, `KPI-DATA-002`, the aggregated `KPI-DATA-003` rule defined in
  the data completeness aggregation rules, `KPI-DATA-004`, `KPI-DATA-005`,
  `KPI-DATA-007`, and either:
  - `KPI-DATA-006` passes with `KPI-DATA-008 >= 5`
  - `KPI-DATA-008 < 5` and `KPI-DATA-006` is recorded as `insufficient_sample`

### GATE-P2-001

- required artifacts:
  raw tick archive, normalized replay path, archive metadata, retention policy,
  and restore telemetry emission
- pass condition:
  `GATE-VERIFICATION-001`

### GATE-P2-OPS-001

- purpose:
  operationally validate tick archive compression and restore behavior
- preconditions:
  `GATE-P2-001`
  and `TBD-002` is resolved with a frozen archive storage baseline
- pass condition:
  `KPI-TICK-001` to `KPI-TICK-003`

### GATE-P3-001

- required artifacts:
  lifecycle-aware execution universe, missing-data states, stale-mark flags,
  liquidity and capacity labeling
- pass condition:
  `KPI-RESEARCH-004` and `GATE-VERIFICATION-001`

### GATE-P3-OPS-001

- purpose:
  operationally validate tradability-state and microstructure drift behavior
- preconditions:
  `GATE-P3-001`
- pass condition:
  `KPI-MICRO-001` to `KPI-MICRO-003` and `KPI-RESEARCH-004`

### GATE-P4-001

- required artifacts:
  run registry, version fields, comparison labels, execution-universe
  diagnostics, benchmark comparability flag, comparison review matrix, and
  scheduled review cadence metadata
- pass condition:
  `KPI-RESEARCH-002` and `GATE-VERIFICATION-001`

### GATE-P4-OPS-001

- purpose:
  operationally validate governance cadence and review-matrix coverage
- preconditions:
  `GATE-P4-001`
- pass condition:
  `KPI-RESEARCH-001` and `KPI-RESEARCH-005`

### GATE-P5-001

- required artifacts:
  deterministic label and execution implementation, threshold-policy
  persistence, cost-model persistence, golden fixtures, benchmark reporting,
  and final comparison-state promotion
- pass condition:
  `KPI-COST-001`, `KPI-RESEARCH-002`, `KPI-RESEARCH-003`, and
  `GATE-VERIFICATION-001`

### GATE-P5-OPS-001

- purpose:
  operationally validate comparable-run sample floors for the active daily
  strategy family
- preconditions:
  `GATE-P5-001`
- pass condition:
  `KPI-COMP-001` to `KPI-COMP-008`
- binding status:
  benchmark-relative policy or performance interpretation remains exploratory
  until `TBD-001` is resolved through an active TW calibrated traded-value floor

### GATE-P6-001

- required artifacts:
  comparable model-family metadata and shared training-output contract
- pass condition:
  `KPI-RESEARCH-002`, `KPI-COST-001`, and `GATE-VERIFICATION-001`

### GATE-P6-OPS-001

- purpose:
  operationally validate matched model-family comparison windows
- preconditions:
  `GATE-P6-001`
  and the compared candidate and baseline runs share the same
  `missing_feature_policy_version`
- pass condition:
  `KPI-COMP-001` to `KPI-COMP-008`

### GATE-P7-001

- required artifacts:
  external-signal lineage, timing mapping, raw external archives, and a
  versioned scoring-eligible factor catalog
- pass condition:
  `KPI-EXT-003` under the audited denominator defined in the external-signal
  audit rules, `KPI-FACTOR-001`, and `GATE-VERIFICATION-001`

### GATE-P7-OPS-001

- purpose:
  operationally validate external-signal freshness and factor usability
- preconditions:
  `GATE-P7-001`
- pass condition:
  `KPI-EXT-001`, `KPI-EXT-002`, `KPI-FACTOR-002`, and `KPI-FACTOR-003`

### GATE-P8-001

- required artifacts:
  point-in-time cluster snapshots, peer features, peer-relative comparison
  outputs
- pass condition:
  `KPI-RESEARCH-002`, `KPI-RESEARCH-003`, and `GATE-VERIFICATION-001`

### GATE-P8-OPS-001

- purpose:
  operationally validate peer-relative comparison windows
- preconditions:
  `GATE-P8-001`
- pass condition:
  `KPI-COMP-001` to `KPI-COMP-008`

### GATE-P9-001

- required artifacts:
  simulation adapter, fill and position readback, order-history persistence,
  failure-taxonomy registry, and readback telemetry emission
- pass condition:
  `GATE-VERIFICATION-001`

### GATE-P9-OPS-001

- purpose:
  operationally validate simulation readback and failure-taxonomy behavior
- preconditions:
  `GATE-P9-001`
  and `TBD-003` is resolved with a frozen simulation platform baseline
- pass condition:
  `KPI-SIM-001` to `KPI-SIM-003`

### GATE-P10-001

- required artifacts:
  manual-confirmation gate, risk checks, broker-order logging, kill switch
- pass condition:
  `KPI-LIVE-001` to `KPI-LIVE-003`

### GATE-P11-001

- required artifacts:
  isolated adaptive workflow, reward and state definitions, non-default rollout
  controls
- pass condition:
  `KPI-ADAPT-001` to `KPI-ADAPT-003`
