---
status: accepted
date: 2026-08-10
legacy_id: DEC-V1-006, DEC-V1-012
---

# A persisted run must reload as completely as it ran, and completeness is derived

A successful research run persists every artifact `SPEC-RUN-001` requires, so it
can be reviewed later without re-running. Reloading a research run must give the
same review quality as the session that produced it.

Reproducibility outranks model novelty in this project's priority order, and a
result that cannot be re-examined six months later is not a research artifact —
it is a screenshot.

**Completeness is derived, not migrated.** `artifact_completeness`, artifact
lists, and backend caveats are computed from the JSON fields already present on
a row. Older records that predate a field are not backfilled; they surface an
explicit fallback state instead.

The alternative — a migration that stamps a completeness flag onto every
historical row — would require inventing values for runs whose artifacts were
never captured, turning "we don't know what this old run contained" into a
confident-looking answer. Deriving keeps the unknown visible.

## Consequences

- Old metadata-only runs display explicit fallback copy rather than a partial
  review that looks whole.
- Comparison must refuse to compare runs whose artifacts are incomplete, and say
  why (ADR-0016).
- Retention and size bounds for diagnostics samples, signals, and equity curves
  are undecided (see `docs/open-decisions.md`).
