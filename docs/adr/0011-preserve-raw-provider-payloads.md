---
status: accepted
date: 2026-08-10
scope: TW daily
---

# TW daily ingestion preserves raw provider payloads and stays rebuildable

Ingested TW daily data keeps its raw provider payload alongside the normalized
rows, with source and parser metadata attached. The derived model-ready dataset
must be reconstructible from what was stored, without re-fetching from the
provider.

The failure this prevents is hindsight cleaning. If normalization rules change —
and they will, because provider formats drift — a system that stored only the
cleaned result cannot tell whether an old research run was trained on data that
today's rules would produce. Every historical result silently becomes
unauditable. Keeping the raw payload makes normalization a replayable step
rather than a one-way door.

This is scoped to TW daily. A US lane will need its own version of this rule
against different provider contracts (ADR-0003).

## Consequences

- Storage cost is paid deliberately in exchange for auditability.
- Research quality claims are traceable to a specific payload and parser
  version, which is what makes the source/provider audit in the opinion artifact
  honest rather than decorative.
