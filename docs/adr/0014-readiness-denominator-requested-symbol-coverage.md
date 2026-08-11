---
status: accepted
date: 2026-08-10
legacy_id: DEC-V1-008
scope: TW daily
supersedes_language: none
---

# Data readiness is measured against requested symbols over known market dates

Readiness reports coverage of the **requested symbols** across the **requested
date range**, using the TW daily market dates the system currently knows about.
It does not use an authoritative exchange calendar, because the project does not
have one.

The honest alternative would be to assert an official trading calendar and
measure against it. We deferred that rather than approximate it: a hand-built or
inferred calendar would produce readiness numbers that look authoritative while
being wrong on exactly the edge cases — half-days, typhoon closures, makeup
sessions — that matter.

## Consequences

- Readiness answers "do I have what I asked for, on the days I know traded" and
  not "is my history complete against the exchange". These are different
  questions and the second is currently unanswerable.
- A date that was never ingested cannot be distinguished from a date that never
  traded, except through the fail-closed rule in ADR-0013.
- Exchange-calendar authority remains deferred and would supersede this ADR when
  adopted.
