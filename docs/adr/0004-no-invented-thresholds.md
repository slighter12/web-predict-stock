---
status: accepted
date: 2026-08-10
---

# Numeric thresholds are provisional-and-labeled or versioned-and-explainable

A quant workbench accumulates magic numbers fast: minimum RMSE to trust a model,
IC floors, drawdown limits, turnover caps, confidence cutoffs, minimum traded
value for investability. Each one silently encodes a judgment that nobody
recorded.

Two states are allowed and nothing else:

- **Provisional** — permitted during prototype validation, but must be visibly
  labeled as provisional wherever it affects output.
- **Versioned policy** — a named, versioned identifier with a written rationale,
  for example the current calibration gate
  `chronological_tail_20pct_min20_class5_v1`.

A stable-looking constant with no version name and no provisional label is a
defect, not a default.

## Consequences

- Support checks (minimum sample counts) must not be presented as evidence of
  performance. They gate whether a metric is computable, not whether it is good.
- The TW minimum traded-value floor stays an open decision rather than becoming
  an unversioned constant (see `docs/open-decisions.md`).
- Any composite score that blends two signals needs a weight, and that weight is
  a threshold under this ADR. This is a direct reason for the shape chosen in
  ADR-0005.
