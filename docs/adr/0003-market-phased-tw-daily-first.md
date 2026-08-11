---
status: accepted
date: 2026-08-10
legacy_id: DEC-V1-002
---

# The product is market-phased: TW daily first, contracts stay market-agnostic

The v1 implementation lane is Taiwan daily equity data. This is a sequencing
decision, not a scope ceiling. TW-first is not TW-only.

We prove the research loop on one market before widening, because a second
market added early would double the data-quality surface before the loop itself
is trustworthy. But contracts, artifact shapes, and domain concepts stay
market-agnostic so a second lane can be added without reshaping them.

## Consequences

- Market-specific ingestion honesty rules (ADR-0011 through ADR-0014) are
  explicitly scoped to TW daily. A US lane gets **parallel** ADRs, not
  supersessions — the two markets have different provider contracts, calendars,
  and universe semantics, and collapsing them into one rule would be wrong for
  both.
- Cross-market comparison semantics are undecided and must be settled before a
  second lane produces comparable runs (see ADR-0021).
- Reading "TW daily" in a spec as "this product is only for Taiwan" is a
  misreading of this ADR.
