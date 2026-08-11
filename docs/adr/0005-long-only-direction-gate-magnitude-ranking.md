---
status: accepted
date: 2026-08-10
legacy_id: DEC-PHASE-008, DEC-PHASE-010, DEC-V1-004, DEC-V1-003
supersedes_language: confirms direction, confirmation model, primary ranking model, direction confirmation
---

# Long-only makes direction an admission gate and magnitude the ranking

The strategy is **long-only**. This was true in the code from the beginning —
`backend/shared/analytics/backtest.py` builds positions through
`vbt.Portfolio.from_orders` with threshold plus top-N selection and has no short
leg — but it was never written down as a contract. It is written down here,
because it determines what the two prediction tasks mean.

Under long-only, direction and magnitude fail differently:

- A **direction** error means holding something that falls. It is a loss.
- A **magnitude** error means ranking the wrong winners first. It is opportunity
  cost and misallocation.

Both matter, so neither is subordinate to the other. They have different jobs:

- The **direction classifier is an admission gate** — it decides whether a
  symbol may enter the candidate set at all.
- The **regression score is the ranking and weighting signal** — it orders and
  sizes what got admitted.

This replaces the earlier framing of regression as the primary model with
direction as a confirmation step. The mechanism is largely unchanged; the
description of what it means was wrong.

## Considered Options

**A single composite score** blending calibrated up-probability with expected
return was rejected. Combining them requires a weighting coefficient, and under
ADR-0004 that coefficient would be an invented threshold — the least
explainable number in the entire product, sitting at the center of every
opinion.

**Two independent opinion lists** (one by direction, one by magnitude) was
rejected because it pushes the synthesis cost back onto the single researcher
the product exists to help.

## Consequences

- Regression-only requests remain supported but cannot emit a prospective
  opinion, because with no gate there is no admission decision.
- A prospective opinion requires a finite regression score **and** a calibrated
  up-probability for every requested symbol on the same latest feature date.
  Incomplete or mixed-date snapshots return `no-opinion`.
- **The gate rests on pooled evidence.** Direction diagnostics are pooled across
  symbols; `sample_count` and `calibration_sample_count` establish no per-symbol
  skill. The product therefore admits individual symbols using a model that does
  not claim individual-symbol skill. This gap is accepted for now, but it must
  be **disclosed in the opinion artifact's invalidation notes**, not only
  recorded here — a limitation visible only in an ADR is a limitation hidden
  from the user. Closing it is tracked in `docs/open-decisions.md`.
