# Pooled Cross-Sectional Method Selection Matrix

## Problem Statement

The workbench can create and persist individual Research Runs, but its current
path trains independently per Symbol and only supports a one-Market-Date strict
Prospective Opinion recipe. It cannot determine, reproducibly, whether a
multi-Symbol technical Method Candidate is useful for 5- or 20-Market-Date
`open_to_open` Return Targets.

The current Feature Catalog is narrow, candidate selection can overfit past
results, and the saved one-Market-Date forward rows do not answer the intended
5- and 20-Market-Date question. A researcher needs one auditable path from a
limited Calibration Matrix through nested Walk-Forward Evaluation, final
Holdout, and recurring prospective outcome reconciliation.

## Solution

Introduce a Method Selection Matrix for the TW daily Model-Ready Universe. It
trains Pooled Cross-Sectional Models with Market-Date Fold boundaries, evaluates
separate Horizon 5 and Horizon 20 Method Candidate families, records every
candidate decision, and promotes no more than three candidates per Horizon to
complete Research Runs.

Each Method Candidate is assessed by the Action Row rate meeting its
Volatility-Scaled Positive Return Threshold. Ties use mean realized excess
return, outer-Fold Action Row stability, and cost-aware matched Baseline
results. Final Holdout results are evaluated once and cannot alter the
configuration. Shortlisted candidates then emit daily Prospective Opinions and
reconcile outcomes at their Horizons.

## User Stories

1. As a researcher, I want to create a Calibration Matrix, so that I can prove
   the pooled evaluation path, artifacts, resources, and model dependencies
   work before spending time on formal selection.
2. As a researcher, I want Calibration Matrix output to be unable to select a
   Method Candidate, so that a runtime check cannot be mistaken for evidence.
3. As a researcher, I want one Pooled Cross-Sectional Model over the daily
   Model-Ready Universe, so that the initial model has broader evidence than
   independent Symbol fits.
4. As a researcher, I want every Fold to keep all rows from one Market Date on
   one side of its boundary, so that the model cannot learn from information
   contemporaneous with its Holdout.
5. As a researcher, I want Horizon 5 and Horizon 20 evaluated separately, so
   that differing Return Targets do not share a forced winner.
6. As a researcher, I want an expanding five-Fold outer evaluation and a
   three-Fold inner evaluation, so that configuration selection and evidence
   measurement are separated.
7. As a researcher, I want the latest 252 Market Dates kept as a final
   Holdout, so that candidate selection has one untouched result.
8. As a researcher, I want a Direction Gate whose positive class is a
   Volatility-Scaled Positive Return Threshold based only on pre-signal daily
   `open_to_open` returns, so that the target scales with Symbol volatility and
   Horizon.
9. As a researcher, I want the rolling-volatility lookback and multiplier to
   be inner-Fold candidate parameters, so that they are selected without using
   outer or final Holdout results.
10. As a researcher, I want `top_n` to be an inner-Fold candidate parameter,
    so that the number of Action Rows does not receive a hidden advantage.
11. As a researcher, I want Feature Ablation by Feature Family before individual
    Feature windows are searched, so that correlated technical inputs do not
    create uncontrolled candidate growth.
12. As a researcher, I want the eight agreed technical Feature Families to be
    available, so that trend, momentum, volatility, range, and price-volume
    information can be measured under one contract.
13. As a researcher, I want initial conventional indicator parameters versioned
    and visible, so that they are not mistaken for proven settings.
14. As a researcher, I want Extra Trees, Random Forest, and XGBoost compared
    through three named capacity presets, so that model complexity is explicit
    and bounded.
15. As a researcher, I want the regression model and Direction Gate to share
    a model family and capacity preset initially, so that results remain
    interpretable.
16. As a researcher, I want a candidate with no Action Rows in any outer Fold
    to yield `no-opinion`, so that inactivity cannot look like high precision.
17. As a researcher, I want a same-Market-Date, same-`top_n`, equal-weight
    cross-sectional Baseline, so that selected Action Rows are compared fairly.
18. As a researcher, I want fees and slippage applied equally to candidates and
    Baselines, so that a small apparent excess cannot win only by ignoring
    costs.
19. As a researcher, I want every candidate configuration, Fold boundary,
    summary, ranking, and rejection reason retained in a Method Selection
    Matrix, so that a shortlist can be reconstructed without re-running it.
20. As a researcher, I want only final shortlisted results persisted as complete
    Research Runs, so that full reload guarantees remain meaningful.
21. As a researcher, I want at most three shortlisted candidates per Horizon,
    so that final evaluation and recurring Prospective Opinions remain
    reviewable.
22. As a researcher, I want each shortlist recipe to run final inner selection
    using all pre-final-Holdout rows, so that final training uses available
    history without touching the final Holdout.
23. As a researcher, I want a daily Prospective Opinion to use each Symbol then
    in the Model-Ready Universe and disclose exclusions, so that a missing
    Symbol does not silently change coverage.
24. As a researcher, I want each prospective 5- or 20-Market-Date outcome
    reconciled when mature, so that historical selection and forward evidence
    remain distinct.
25. As a researcher, I want outcome reports to disclose overlapping-Horizon
    dependence, so that daily observations are not presented as independent
    evidence.
26. As a researcher, I want XGBoost unavailability surfaced clearly until its
    local OpenMP dependency is installed, so that a missing family is never
    substituted silently.

## Implementation Decisions

- Add a high-level Method Selection Matrix service and API surface. It owns
  candidate manifests, Calibration Matrix execution, nested evaluation,
  ranking, final-Holdout orchestration, and selection-summary persistence.
- Reuse the existing complete Research Run creation and registry path only for
  shortlisted and final-Holdout results. Do not represent partial inner
  candidates as Research Runs.
- Add persistence and retrieval contracts for Method Selection Matrices,
  including candidate identity, Feature Catalog version, date boundaries,
  Fold summaries, Action Row metrics, Baseline metrics, resource evidence,
  selection decisions, and rejection reasons.
- Train the initial model on Pooled Cross-Sectional rows. Resolve one
  versioned canonical source row for each `(Symbol, Market Date)`, align each
  Symbol's target calculation to the pooled ordered Market-Date axis, and build
  all outer and inner partitions from that axis. Assign all available Symbol
  rows for a date to the same partition. Compute rolling features on each
  Symbol's canonical observed rows: a missing Market Date is a target boundary
  but does not reset feature warmup, while an invalid OHLCV row resets both
  feature and target segments. Persist observed, missing-axis, invalid, and
  model-ready counts per Symbol so this coverage policy remains auditable. The
  pooled axis comes from distinct TW Market Dates with at least one official
  source row in the market-data store for the requested range, excluding
  confirmed official no-data dates; it does not come from the requested
  Symbols' date union or non-official fallback rows.
- Keep Horizon 5 and Horizon 20 manifests, outputs, and shortlists separate.
- Use the final 252 observed Market Dates as
  `final_holdout_252_market_dates_provisional_v1`; preserve the chosen date
  range in every result.
- Define the Volatility-Scaled Positive Return Threshold from pre-signal rolling
  daily `open_to_open` volatility times the square root of Horizon. The inner
  candidate grid is lookback `{20, 60, 252}` and multiplier `{0.5, 0.75, 1.0}`.
- Use `top_n` `{5, 10, 20}` as the inner candidate grid. Preserve each chosen
  value and the provisional policy version.
- Add Feature Catalog support for `MACD`, `BBANDS`, `ATR`, `STOCH`, `OBV`,
  `ADX`/`DMI`, `MFI`, and `CMF`. `MACD`, `BBANDS`, `STOCH`, and `OBV` use the
  installed indicator runtime; `ATR`, `ADX`/`DMI`, `MFI`, and `CMF` use local
  deterministic calculations. ATR uses the conventional SMA-seeded Wilder
  recurrence rather than the installed runtime's alternate smoothing modes.
- Start indicator Families from versioned conventional tuples: MACD 12/26/9,
  BBANDS 20, ATR 14, STOCH 14/3, OBV 1, ADX/DMI 14, MFI 14, and CMF 20. Search
  a Family's window parameters only after it has outer-Fold value.
- Compare Extra Trees, Random Forest, and XGBoost through `conservative`,
  `balanced`, and `flexible` capacity presets. Persist the concrete preset
  values in the Matrix manifest; use the same family and preset for regression
  and the Direction Gate in the initial path.
- Apply existing provisional costs of 0.2% fees and 0.1% slippage per side to
  candidates and Baselines. Add the matched equal-weight cross-sectional
  Baseline; retain existing Baselines as supplemental context.
- Rank candidates by Action Row threshold-hit rate, then mean realized return
  above the threshold, Action Row stability across outer Folds, and cost-aware
  Baseline-relative results. A candidate with no Action Rows in an outer Fold
  is `no-opinion`.
- Use a Calibration Matrix before formal selection. It may check resource use,
  artifact capture, Pooled Cross-Sectional partitioning, and XGBoost readiness,
  but it cannot enter a shortlist.
- After final Holdout, generate daily prospective records for each shortlisted
  candidate. Preserve the Model-Ready Universe participant count, exclusions,
  Horizon maturity date, and realized outcome.

## Testing Decisions

- Test public Method Selection Matrix behavior: creation, retrieval, manifest
  persistence, candidate summaries, ranking, `no-opinion`, final-Holdout
  isolation, and prospective maturity reconciliation.
- Test Market-Date partitioning rather than implementation details: no date may
  span both train and Holdout; the Horizon purge and each row's
  `target_end_date` prevent labels crossing a boundary.
- Test that inner selection never reads outer or final Holdout rows, and that a
  final refit uses only pre-final-Holdout data.
- Test Pooled Cross-Sectional construction with multiple Symbols, canonical
  duplicate-source resolution, global Market-Date alignment, and date-based
  complete-case exclusions that also block target lookahead across invalid
  boundaries, including a date absent from every requested Symbol but present
  on the global TW Market-Date axis.
- Test each new Feature Family for deterministic values, correct pre-signal
  shifting, required OHLCV inputs, and missing-data behavior.
- Test Feature Ablation summaries and candidate rejection when a Family fails
  to improve the configured evidence hierarchy.
- Test that the matched Baseline uses the same Market Dates, `top_n`, equal
  weights, and execution assumptions as its candidate.
- Test the existing three model families through a test double or controlled
  small dataset; test that XGBoost dependency failure is recorded as unavailable
  rather than substituted.
- Test complete Research Run reload behavior for shortlisted and final results,
  and summary-only Method Selection Matrix reload behavior for all candidates.
- Extend current research execution, prospective cohort, feature registry,
  run repository, and script test patterns rather than introducing a parallel
  test harness.

## Out of Scope

- Cluster-specific models and the Cluster policy.
- External fundamental, news, sentiment, peer, factor, tick, or intraday data.
- True intraday VWAP reconstruction.
- `CCI` and Williams %R before the agreed Feature Families show evidence.
- Broker execution, automated portfolio control, or personalized advice.
- Treating a Calibration Matrix or offline result as forward validation.
- Changing the current-active membership history limitation into a claim of
  point-in-time historical membership coverage.

## Further Notes

- ADR-0024 governs the Volatility-Scaled Positive Return Threshold.
- ADR-0025 governs pooled cross-sectional training before Cluster-specific
  models.
- ADR-0026 governs Method Selection Matrix summary retention versus complete
  Research Run retention.
- XGBoost is currently unavailable locally because macOS lacks `libomp`.
  Installing it is a separate explicitly approved environment change before
  the formal Matrix includes XGBoost.
- The current initial universe remains subject to the existing point-in-time
  membership caveat. Every result must disclose that limitation, including
  Calibration Matrix responses through `comparison_caveats`.
