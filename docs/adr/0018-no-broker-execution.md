---
status: accepted
date: 2026-08-10
legacy_id: DEC-PHASE-004, DEC-PHASE-005
---

# No broker execution, no live orders, no portfolio auto-control

The system does not connect to a broker, does not place or simulate live orders,
and does not act on real holdings. A run using `execution_route="research_only"`
stays `tradability_state="research_only"`; `execution_ready` requires an
explicitly non-research route that nothing currently sets.

This is the load-bearing constraint behind ADR-0002. Execution creep is the most
likely way this project stops being what it is: each individual step toward it
(paper trading, then order simulation, then a read-only broker connection) looks
small, and the aggregate is a different product with a different risk profile
built by one person with no operational safety net.

Portfolio automation is deferred behind the same line. Manual adoption tracking
and forward-outcome measurement come first (ADR-0022); automatic rebalancing and
position sizing against real holdings come no earlier than that.

## Consequences

- Backtest output is an offline research artifact and must not imply live-order
  readiness anywhere it is displayed.
- The promotion criteria that would have to be satisfied before broker work could
  even enter planning — safety model, audit, reconciliation, idempotency, manual
  confirmation, kill switches — are undecided and tracked in
  `docs/open-decisions.md`.
- Reversing this ADR is a product-identity change, not a feature addition.
