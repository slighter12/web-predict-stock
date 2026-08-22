# Evidence Note: Walk-Forward Method Selection for Multi-Symbol Return Targets

Status: non-normative research note. This note informs later specifications; it
does not by itself establish an implementation policy or an adoption claim.

## Question

How should the workbench compare Method Candidates for 5- and 20-Market-Date,
multi-Symbol, `open_to_open` Return Targets without mistaking historical fit for
forward skill?

## Findings

1. **Keep time order intact.** scikit-learn's `TimeSeriesSplit` exists because
   ordinary cross-validation can train on future observations and evaluate past
   ones; it also provides a `gap` parameter to exclude observations between
   train and test partitions. The workbench's Return Target implementation
   looks ahead by `horizon_days` for `open_to_open`, so a Walk-Forward
   Evaluation must ensure that the training side cannot contain labels whose
   look-ahead reaches the Holdout period. For the proposed targets, this calls
   for an explicitly recorded purge/gap policy for Horizon 5 and Horizon 20.
   [scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
   and [workbench target implementation](../backend/shared/analytics/models.py).

2. **Compare a fixed set of candidates; do not crown a winner from an
   unconstrained search.** Bailey et al. show that selecting strategies from
   historical simulations can overfit the backtest and propose measuring that
   risk. Therefore the candidate matrix, selection metric, and final untouched
   Holdout must be set before interpreting results.
   [Bailey et al., *The Probability of Backtest Overfitting*](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253).

3. **Judge model quality before strategy output, and retain multiple views.**
   The workbench already requires regression diagnostics (RMSE, MAE, rank IC,
   linear IC, residuals, and feature importance) before strategy
   interpretation. This is consistent with Gu, Kelly, and Xiu's comparative
   analysis of machine-learning methods for expected-return measurement, which
   reports out-of-sample comparisons and attributes gains to nonlinear
   interactions. Their US-market evidence motivates comparison; it does not
   establish that a method will work for TW daily data.
   [Gu, Kelly, and Xiu, *Empirical Asset Pricing via Machine Learning*](https://www.nber.org/papers/w25398)
   and [workbench validation gates](validation-gates.md).

   Tree impurity importances may help generate a Feature Ablation hypothesis,
   but they are not the decision by themselves. Permutation importance can be
   calculated on a held-out set to show which Features contribute to the fitted
   model's generalization; it remains model-specific, and correlated Features
   can mask one another. Therefore a removal or addition should be judged by
   the same Walk-Forward Evaluation as the original Method Candidate, not by a
   single importance ranking.
   [scikit-learn permutation importance](https://scikit-learn.org/stable/modules/permutation_importance.html)
   and [correlated-Feature caveat](https://scikit-learn.org/stable/auto_examples/inspection/plot_permutation_importance_multicollinear.html).

4. **Treat 5 and 20 as separate Research Run families.** Different Horizons
   produce different Return Targets, label overlap, and decision timing. Their
   metrics may be displayed together, but they should not share one winner or
   be ranked as directly Comparable Runs without an explicit later policy.

5. **Historical selection is not forward validation.** A selected candidate
   should subsequently produce persisted Prospective Opinions, whose outcomes
   are reconciled only after their respective Horizons mature. This preserves
   the workbench boundary: a model opinion remains research evidence for manual
   review, rather than a claim of personalized advice or an execution command.

## Design Consequences To Decide

- the fixed multi-Symbol evaluation set and its inclusion rule;
- the historical date boundary and final untouched Holdout period;
- the candidate matrix (model families, Feature sets, and strategy policies);
- the selection hierarchy across predictive diagnostics, Baseline-relative
  strategy results, and robustness across Folds; and
- the persisted evidence needed to reconcile a later Prospective Opinion.

## Additional Daily-OHLCV Indicator Review

The versioned technical Feature Catalog includes the initial expansion
(`MACD`, `BBANDS`, `ATR`, `STOCH`, `OBV`, `ADX`/`DMI`, `MFI`, and `CMF`).
`MACD`, `BBANDS`, `STOCH`, and `OBV` use the installed vectorbt runtime;
`ATR`, `ADX`/`DMI`, `MFI`, and `CMF` use deterministic local calculations. The
table records the current availability of these families and the remaining
deferred candidates; every retained family still requires an outer-Fold
evidence record:

| Feature Family | Candidate | Input bars | Initial status |
| --- | --- | --- | --- |
| momentum and trend | `MACD` | close | implemented in `technical_feature_registry_v3`; vectorbt runtime |
| price dispersion | `BBANDS` | close | implemented in `technical_feature_registry_v3`; vectorbt runtime |
| volatility range | `ATR` | high, low, close | implemented in `technical_feature_registry_v3`; local Wilder calculation |
| momentum oscillator | `STOCH` | high, low, close | implemented in `technical_feature_registry_v3`; vectorbt runtime |
| volume direction | `OBV` | close, volume | implemented in `technical_feature_registry_v3`; vectorbt runtime |
| trend strength | `ADX` / `DMI` | high, low, close | implemented in `technical_feature_registry_v3`; local calculation |
| price-volume flow | `MFI` | high, low, close, volume | implemented in `technical_feature_registry_v3`; local calculation |
| price-volume flow | `CMF` | high, low, close, volume | implemented in `technical_feature_registry_v3`; local calculation |
| range oscillator | `CCI`, Williams %R | high, low, close | defer; overlaps materially with `STOCH`, `RSI`, and `zscore` |
| volume-weighted price | intraday VWAP | intraday prices and volume | exclude from daily-OHLCV scope; daily bars cannot reconstruct true VWAP |

Technical-rule studies commonly group MACD, stochastic, directional movement,
and OBV as distinct technical mechanisms, but their measured results vary by
market. The table is therefore a candidate catalog, not evidence that any entry
has predictive skill in TW daily data.
[Nguyen and Le, *Performance of technical trading rules: evidence from Southeast Asian stock markets*](https://pmc.ncbi.nlm.nih.gov/articles/PMC4583561/).

Every retained entry requires the same held-out Feature Ablation and
Walk-Forward Evaluation as the initial catalog expansion. Permutation
importance should be computed on held-out data and interpreted at the Feature
Family level where correlated Features can mask each other.
[scikit-learn permutation importance](https://scikit-learn.org/stable/modules/permutation_importance.html).

## Confirmed Research Configuration

- The initial evaluation scope is the TW daily Model-Ready Universe, with the
  existing point-in-time membership caveat disclosed.
- Horizon 5 and Horizon 20 are separate `open_to_open` Return Target families.
- Validation uses chronological expanding Walk-Forward Evaluation and a final
  contiguous Holdout that is not opened during Method Candidate selection.
- The final Holdout contains the latest 252 observed Market Dates: 2025-07-30
  through 2026-08-12 in the current local dataset. It is recorded as
  `final_holdout_252_market_dates_provisional_v1` until the research policy is
  promoted or revised.
- Candidate construction begins with Feature Ablation and incremental Feature
  additions/removals. It evaluates Feature Families before individual Features,
  then compares the resulting Feature sets with model configurations under the
  same evaluation protocol.
- Each outer Walk-Forward Fold performs candidate-parameter selection only
  inside its training period. Its outer Holdout is never used for that
  selection, and neither is the final Holdout.
- Each Horizon keeps a shortlist for subsequent Prospective Opinion evaluation;
  offline results do not force selection of a single winner.
- The Direction Gate's Positive Return Threshold is Horizon-scoped rather than
  a universal 3% constant. It is derived from pre-signal Symbol volatility and
  Horizon scaling under ADR-0024; its reproducible calculation policy is not
  yet settled.
- The volatility multiplier and `top_n` are Method Candidate parameters. A
  pre-recorded provisional candidate set is selected only inside each outer
  Fold's training period; no outer Holdout or final Holdout value may choose
  either parameter.
- The provisional volatility-threshold grid uses rolling lookbacks of 20, 60,
  and 252 Market Dates and Horizon-scaled standard-deviation multipliers of
  0.5, 0.75, and 1.0. The provisional `top_n` grid is 5, 10, and 20 Action
  Rows per Market Date.
- `Extra Trees`, `Random Forest`, and `XGBoost` are compared as the initial
  model-family set, with their parameters selected under the same inner-Fold
  rule.
- Within the initial research matrix, the regression model and Direction Gate
  use the same model family and named capacity preset. Independent pairings are
  deferred until a shortlisted candidate justifies the added search space.
- Each model family exposes exactly three pre-recorded provisional capacity
  presets: `conservative`, `balanced`, and `flexible`.
- The Volatility-Scaled Positive Return Threshold uses rolling daily
  `open_to_open` returns available before the signal date, then scales to the
  Horizon. Its rolling lookback and multiplier remain pre-recorded,
  inner-Fold-selected candidate parameters.
- Formal comparison uses five expanding outer Folds. A three-Fold run may
  validate the execution path as a Calibration Matrix, but cannot select a Method
  Candidate.
- Each outer Fold uses three expanding inner Folds for Method Candidate
  selection.
- The initial model is a Pooled Cross-Sectional Model over the TW daily
  Model-Ready Universe. Every Fold keeps all rows from each Market Date on the
  same side of its time boundary; Cluster-specific models are deferred.
- Candidate ranking first maximizes the Action Row rate meeting its applicable
  Positive Return Threshold. Ties are broken by the mean realized return above
  that threshold, then by Action Row stability across outer Folds and
  cost-aware Baseline-relative results.
- A candidate with no Action Rows in any outer Fold produces `no-opinion` and
  is ineligible for the shortlist.
- Outer-Fold results fix each Horizon's shortlist before any final-Holdout work.
  Each shortlisted candidate then refits on all pre-final-Holdout data and is
  evaluated once on the untouched final Holdout; that result cannot revise the
  candidate configuration.
- Before that final refit, each shortlisted recipe runs its three-Fold inner
  selection against all pre-final-Holdout data to select its final Feature,
  model, threshold, and strategy configuration.
- The initial catalog expansion adds `MACD`, `BBANDS`, `ATR`, `STOCH`, and
  `OBV`, `ADX`/`DMI`, `MFI`, and `CMF` as new technical Feature Families derived
  solely from daily OHLCV. `MACD`, `BBANDS`, `STOCH`, and `OBV` use the
  installed indicator runtime; `ATR`, `ADX`/`DMI`, `MFI`, and `CMF` use
  deterministic local calculations. Each family is added and removed against
  the existing six-Feature baseline under the same nested Walk-Forward
  Evaluation.
- Each new indicator starts from a versioned provisional conventional parameter
  tuple. Its window parameters join inner-Fold search only after its Feature
  Family has demonstrated outer-Fold value.
- The provisional initial tuples are MACD 12/26/9, BBANDS 20, ATR 14, STOCH
  14, ADX/DMI 14, MFI 14, and CMF 20.
- Cost-aware comparison includes a same-Market-Date, same-`top_n`, equal-weight
  cross-sectional Baseline. Existing `buy_and_hold`, `naive_momentum`, and
  `ma_crossover` Baselines remain supplemental context.
- Every candidate and Baseline uses the existing provisional execution
  assumptions: 0.2% fee and 0.1% slippage on each side.
- Every shortlisted Method Candidate produces a Prospective Opinion on each
  Market Date. Its 5- or 20-Market-Date result is reconciled at maturity, and
  outcome reporting discloses overlapping-Horizon dependence.
- A daily Prospective Opinion uses every Symbol that is then in the Model-Ready
  Universe. It persists the participating Symbol count and per-Symbol exclusion
  reasons instead of requiring every currently active Symbol to be present.
- A Method Selection Matrix persists the candidate manifest, Fold summaries,
  ranking, and rejection reasons. Only final shortlisted results become full
  Research Runs. Each Horizon's shortlist contains at most three candidates.
- A versioned Calibration Matrix precedes the formal evaluation. It verifies
  pooled-data shape, XGBoost availability, resource use, Fold boundaries, and
  artifact capture with a limited candidate matrix; it cannot select a Method
  Candidate or contribute to a shortlist.

## Technical Feature Catalog Operational Contract

`technical_feature_registry_v3` is the backend Feature Catalog authority. The
frontend requests `/api/v1/research/feature-registry` and uses its metadata for
available outputs, Feature Families, required OHLCV columns, and parameter
tuples. A declarative frontend fallback with the same version and catalog
contract is used only while that request is unavailable. The standard
`make feature-registry-check` gate compares the complete backend catalog
metadata with that fallback, including version, labels, descriptions, editable
windows, sources, parameter tuples, and required columns.

ATR intentionally uses the local calculation even though vectorbt exposes an
ATR runtime. The installed runtime offers simple or span-based exponential
smoothing, while this catalog preset requires the conventional SMA-seeded
Wilder recurrence; using the local path keeps the implementation aligned with
the recorded preset rather than silently changing its smoothing semantics.

The fixed compatibility presets are MACD 12/26/9 with both MACD and signal
EWM enabled, BBANDS 20 with its existing vectorbt parameters, ATR 14 with
Wilder smoothing, STOCH 14/3, OBV 1, ADX/DMI 14, MFI 14, and CMF 20. These
fixed outputs are not editable in the workflow. Existing MA, EMA, RSI, ROC,
volatility, and z-score rows retain editable windows. A fixed output is reset
to its catalog preset when selected after a custom-window row, so the request
cannot contain a window rejected by the backend validator.

The deterministic local calculations use the following zero-range policy:

- CMF assigns a zero money-flow multiplier to a `high - low == 0` row.
- ATR leaves the first true range undefined because it has no prior close,
  seeds the first value with the SMA of the first 14 defined true ranges, and
  then applies `(previous * 13 + current) / 14`.
- DMI compares prior highs and lows before assigning directional movement and
  uses the same SMA-seeded Wilder recurrence; a zero smoothed true-range
  denominator or no directional movement produces zero DMI/DX values after
  warmup.
- MFI leaves the first price movement undefined and requires 14 valid price
  movements before its first value. Invalid or non-finite OHLCV rows restart
  that movement count. MFI returns 50 when both rolling flow totals are zero,
  100 when only negative flow is zero, and 0 when only positive flow is zero.
- Normal insufficient-history warmup remains `NaN`. A valid zero-range OHLCV
  row does not reset pooled Feature continuity; invalid or non-finite core
  OHLCV rows still form continuity boundaries and are excluded by the existing
  complete-case policy.

The backend owns the registry version. New Research Runs persist the actual
version as resolved result metadata and expose it as
`feature_registry_version`; new Calibration Matrices persist the same metadata
in their result payload. Research Run storage keeps the metadata in a reserved
internal envelope within the existing JSON storage, while the user request
projection remains the original request and does not claim a backend-resolved
catalog version. Legacy records without this field project it as
`null`/unavailable rather than being assigned the current catalog version. This
traceability metadata requires no database migration.

Before rollout, operators should verify the registry endpoint version, the
catalog output count, and a representative request for each required-input
group. After rollout, inspect research-run warnings and feature-calculation
errors, and compare model-ready row counts across the same data window. The
rollback path is to restore the previous application artifact and registry
version; this catalog change has no database migration. If a new family is
temporarily disabled, existing catalog outputs remain available and research
runs using the disabled output should fail closed with an unsupported-feature
configuration error.
