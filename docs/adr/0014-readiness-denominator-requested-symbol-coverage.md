---
status: accepted
date: 2026-08-10
legacy_id: DEC-V1-008
scope: TW daily
supersedes_language: none
---

# Data readiness is measured against requested symbols over known market dates

Readiness reports coverage of the **requested symbols** across the **requested
date range**, using distinct TW daily dates observed anywhere in the market-data
store. These are the Market Dates the system currently knows about, not weekdays
or an authoritative exchange calendar.

The honest alternative would be to assert an official trading calendar and
measure against it. We deferred that rather than approximate it: a hand-built or
inferred calendar would produce readiness numbers that look authoritative while
being wrong on exactly the edge cases — half-days, typhoon closures, makeup
sessions — that matter.

## Consequences

- Readiness answers "do I have what I asked for, on the days I know traded" and
  not "is my history complete against the exchange". These are different
  questions and the second is currently unanswerable.
- A date with no market-wide daily row is absent from this denominator. ADR-0013
  prevents an attempted fetch that failed from being recorded as confirmed
  no-data; it cannot identify a date for which ingestion was never attempted.
- Exchange-calendar authority remains deferred and would supersede this ADR when
  adopted.
