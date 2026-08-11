---
status: proposed
date: 2026-08-10
legacy_id: TBD-PHASE-005
---

# US daily is the second market lane

**Proposed.** Direction is settled by ADR-0003; the terms are not.

US daily equity data is the intended second lane. Per ADR-0003, it arrives as
**parallel ADRs alongside** ADR-0011 through ADR-0014 rather than superseding
them — the two markets have different provider contracts, calendars, universe
semantics, and corporate-action conventions, and one shared rule would be wrong
for both.

## Conditions before acceptance

1. **Source contracts** named, with raw-payload audit rules matching ADR-0011.
2. **Market-calendar policy** decided. This is where the US lane differs most
   sharply: unlike ADR-0014's deferral, reliable US trading calendars are
   readily available, so continuing to infer dates from observed data would be a
   deliberate choice rather than a forced one.
3. **Universe policy** decided, including whether a point-in-time universe is
   achievable for US data where it was not for TW (ADR-0012).
4. **Cross-market comparison semantics** defined: whether a TW run and a US run
   are ever comparable, and what caveats attach if so. Without this, the
   run-comparison surface will quietly compare incomparable runs.
