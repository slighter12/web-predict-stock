---
status: accepted
date: 2026-08-13
scope: TW daily
---

# Direction Gate labels use a volatility-scaled Positive Return Threshold

The workbench will evaluate 5- and 20-Market-Date `open_to_open` Return Targets
by asking its Direction Gate to identify materially positive outcomes, rather
than treating every return above zero as equally useful. The positive class is
therefore defined by a Volatility-Scaled Positive Return Threshold: a value
derived only from the Symbol's pre-signal return volatility and scaled to the
Horizon.

This avoids a universal percentage that silently means very different things at
different Horizons or during different volatility regimes. It also avoids an
outcome-distribution quantile that would redefine the desired economic result
as market conditions change. The policy version must record the volatility
estimator, historical lookback, scaling formula, multiplier, and return basis;
until those fields are decided, this ADR does not authorize a concrete numeric
threshold or implementation.

## Considered Options

- A fixed percentage per Horizon was rejected because it does not adapt to
  symbol-level or regime-level volatility.
- A training-return quantile was rejected because it defines relative ranking,
  rather than the desired absolute, Horizon-sensitive outcome.

## Consequences

- The Direction Gate's positive class is not interchangeable across Horizon 5
  and Horizon 20.
- Every Research Run must persist the applicable threshold-policy version before
  its results may be compared.
