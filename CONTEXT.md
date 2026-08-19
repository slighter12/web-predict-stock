# Quant Research-to-Opinion Workbench

This file is a **glossary and nothing else**. It answers *what a term means*.
It does not answer *what a term must satisfy* — that is `docs/research-spec.md`
— and it does not answer *why something was decided* — that is `docs/adr/`.
When a term appears in all three, each says a different kind of thing about it.

## Market and Data

**Market Lane**:
One market plus one bar frequency, ingested and researched as a unit. It is the
market-and-frequency axis, independent of Research Track, Prediction Task, and
Feature Family.
_Avoid_: market, region, exchange scope

**Symbol**:
The market-lane identifier for one listed security.
_Avoid_: ticker, stock, instrument, asset

**Market Date**:
A date the system knows trading occurred on, derived from observed provider data
rather than from an authoritative exchange calendar.
_Avoid_: trading day, session date

**Raw Payload**:
The provider response as received, before normalization.
_Avoid_: raw data, source data, original response

**Current-Active Universe**:
The set of symbols currently listed in a market lane. It describes today only
and carries no record of what was listed on any past date.
_Avoid_: universe, symbol list, active list

**Model-Ready Universe**:
The symbol-and-date rows that pass data-quality requirements and may enter a
research run. Distinct from the current-active universe, which governs what gets
ingested.
_Avoid_: clean data, usable universe, eligible symbols

**Readiness**:
How much of a requested symbol set exists over a requested date range, measured
against known market dates. A statement about what was asked for, not about
whether history is complete.
_Avoid_: data quality, coverage, completeness

## Research Dimensions

Market Lane, Research Track, Prediction Task, and Feature Family are orthogonal
axes: they identify market and frequency, research framing, model question, and
model-input family respectively. Changing one axis does not rename or redefine
the others.

**Research Track**:
The subject and analytical framing of a research run, independent of Market
Lane, Prediction Task, and Feature Family.
_Avoid_: research lane, technical lane, quantitative lane

**Technical Research Track**:
The Research Track focused on price-and-volume behavior in a Market Lane.
_Avoid_: technical track

**Feature Family**:
A group of Features that share a source or semantic role. It is the model-input
axis, independent of Market Lane, Research Track, and Prediction Task.
_Avoid_: feature lane

**Sentiment Feature Family**:
A Feature Family for sentiment-derived inputs. It distinguishes the
`external_signal` ingestion/audit layer from derived model inputs. It is not an
independent Opinion source.
_Avoid_: sentiment lane

## Research Loop

**Research Run**:
One execution of the research loop, covering a dataset, features, prediction
task, model, validation, and backtest.
_Avoid_: experiment, study, job, backtest run

**Method Candidate**:
One fixed combination of Prediction Task, Return Target, Horizon, Features,
model configuration, Direction Gate, and strategy policy evaluated as a single
research choice.
_Avoid_: approach, setup

**Pooled Cross-Sectional Model**:
A model trained on rows from all Model-Ready Universe Symbols, with Folds that
keep every row from the same Market Date on the same side of the time boundary.
_Avoid_: market-wide model, one model per stock

**Method Selection Matrix**:
A persisted comparison of Method Candidates and Fold summaries that records
selection evidence without representing every inner candidate as a Research Run.
_Avoid_: experiment log, grid search output

**Calibration Matrix**:
A limited Method Selection Matrix that verifies evaluation execution and
artifact capture without selecting a Method Candidate.
_Avoid_: smoke test

**Walk-Forward Evaluation**:
A chronological evaluation of Method Candidates in which each Fold trains only
on Market Dates earlier than its Holdout Market Dates.
_Avoid_: time-series test, rolling backtest

**Feature Ablation**:
A Walk-Forward Evaluation that compares otherwise identical Method Candidates
after adding or removing a Feature or Feature Family.
_Avoid_: feature analysis, feature filtering

**Dataset**:
The symbol, date, and price slice a research run trains and evaluates on.
_Avoid_: data, training data, sample

**Feature**:
A deterministic value derived per symbol per date from the dataset, used as
model input, with its derivation traceable.
_Avoid_: indicator, variable

**Prediction Task**:
The family of question a model answers — `regression` for a numeric forward
return, `classification` for direction. A run may use both, for different jobs.
It is the model-question axis, independent of Market Lane, Research Track, and
Feature Family.
_Avoid_: model type, problem, objective

**Fold**:
One train-and-test split in cross-sectional validation, where every symbol in
the fold shares the same train dates and the same test dates.
_Avoid_: split, partition, cv fold

**Holdout**:
Predictions produced for evaluation only. Holdout output measures quality and
never becomes a forward-looking opinion.
_Avoid_: validation output

**Baseline**:
A reference strategy computed for the same dataset, giving a run's strategy
metrics something to be better or worse than.
_Avoid_: benchmark, control, reference

**Artifact Completeness**:
A summary of which artifacts a Research Run contains.
_Avoid_: run status, data completeness, artifact status

**Comparable Runs**:
Runs whose dataset, target, and assumption choices permit reading their results
side by side. Comparability is a property of the pair, not of either run.
_Avoid_: similar runs, matching runs

## Prediction Semantics

**Return Target**:
The numeric forward return a regression task predicts, defined by its return
definition, horizon, and price basis.
_Avoid_: label, y, outcome, prediction

**Positive Return Threshold**:
The Horizon-scoped Return Target value at or above which a realized return is a
positive class for the Direction Gate.
_Avoid_: gain target, success rate

**Volatility-Scaled Positive Return Threshold**:
A Positive Return Threshold derived from the Symbol's pre-signal return
volatility and scaled to the Horizon, rather than a universal percentage.
_Avoid_: dynamic 3% threshold, volatility target

**Horizon**:
The number of forward market dates a target looks ahead.
_Avoid_: window, period

**Direction Gate**:
The calibrated classifier step that decides whether a symbol may enter the
candidate set at all. An admission decision, not a confirmation of a decision
already made.
_Avoid_: direction confirmation, direction filter, classifier check

**Magnitude Ranking**:
The regression score that orders and weights symbols after the direction gate
admits them.
_Avoid_: score, prediction, rank, alpha

**Calibration**:
A mapping from raw classifier output to a probability.
_Avoid_: probability tuning, scaling

**Prospective Opinion**:
A forward-looking opinion derived from a Research Run, distinct from Holdout
output.
_Avoid_: forecast, live prediction, forward signal

**No-Opinion**:
The explicit state a run returns when evidence is insufficient to say anything.
A valid and expected outcome, not a failure.
_Avoid_: empty result, null opinion, no signal

## Opinion Output

**Opinion Artifact**:
The structured serialization of an opinion for a Research Run, distinct from an
informal opinion.
_Avoid_: opinion, report, brief, recommendation

**Action Row**:
One symbol-level entry in an Opinion Artifact.
_Avoid_: recommendation, pick, position

**Evidence**:
The row-specific reference to the artifacts that support one action row. Shared
or generic text is not evidence.
_Avoid_: reason

**Invalidation Note**:
The row-specific statement of when an action row should **not** be adopted,
including limitations of the models that produced it.
_Avoid_: caveat, disclaimer, risk note

**Review Check**:
One self-review gate evaluated against a run's actual artifacts, producing a
result that can affect whether an opinion is viable.
_Avoid_: quality check
