---
status: accepted
date: 2026-08-10
legacy_id: DEC-PHASE-012
scope: TW daily
---

# TW daily no-data detection fails closed

A trading date is recorded as legitimately having no data only when **both** TWSE
and TPEX explicitly declare no data for it. An empty table container, a
malformed payload, or a missing section is treated as an **ingestion failure**,
not as a market holiday.

The two error directions are not symmetric. Treating a failed fetch as "no
trading that day" writes a permanent, silent hole into the price history that
looks identical to a real holiday and will never be noticed again. Treating a
real holiday as a failure produces a noisy retry that a human resolves in
minutes. We take the loud error every time.

This holds until an authoritative provider contract proves a specific payload
shape genuinely means no data.

## Consequences

- Ingestion is noisier and needs recovery tooling, which exists.
- Exchange-calendar authority is deliberately not assumed here; see ADR-0014.
- Scoped to TW daily.
