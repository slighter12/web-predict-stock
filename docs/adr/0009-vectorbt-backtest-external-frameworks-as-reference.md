---
status: accepted
date: 2026-08-10
legacy_id: DEC-PHASE-001, DEC-PHASE-002
---

# vectorbt runs the offline backtest; external trading frameworks are reference material only

Backtesting uses `vectorbt` in-process (`vbt.Portfolio.from_orders`). Several
mature open-source trading and research projects informed the design, but **none
of them is a runtime dependency**:

| Project | What we take from it |
| --- | --- |
| Jesse | strategy lifecycle, signal-to-position translation, robustness checks, parameter sensitivity, backtest-report discipline |
| UZI-Skill | multi-angle report structure, self-review gates, evidence/risk/invalidation sections, compact stock-brief patterns |
| a-stock-data, OpenBB | source/provider audit concepts, raw-source traceability, parser and source metadata, market-aware provider contracts |
| FinGPT | traceable evidence extraction, report summarization, risk/warning/invalidation support |
| FinRL | train/test/trade separation and policy evaluation for a later adaptive phase |

Adopting a framework like Jesse wholesale would import a live-trading runtime and
its broker adapters into a product whose entire boundary is that it does not
trade (ADR-0002). The methods are worth more to us than the runtimes, and the
methods are reimplementable locally against our own artifact contracts.

## Consequences

- These projects must never become runtime dependencies, broker adapters, or
  provider SDKs, and citing them is not evidence that a deferred feature belongs
  in scope.
- Backtest semantics are ours to define and persist: label basis, entry/exit
  price proxy, fees, slippage, and portfolio construction are all recorded per
  run rather than inherited from a framework's defaults.
