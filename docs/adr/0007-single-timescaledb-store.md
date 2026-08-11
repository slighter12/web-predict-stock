---
status: accepted
date: 2026-08-10
---

# One TimescaleDB instance holds everything

All persistence — daily market data, company profiles, ingestion state, research
runs, and persisted artifacts — lives in a single TimescaleDB (PostgreSQL 18)
instance, accessed through SQLAlchemy with Alembic migrations.

The obvious alternative for a quant workload is splitting storage by shape: a
timeseries store for bars, a relational store for metadata, object storage for
run artifacts. We rejected that for a single-researcher system. Research runs
need to join price history against persisted artifacts and reconstruct old runs
exactly; keeping that in one transactional store makes reproducibility a
property of the database rather than a cross-store coordination problem.
TimescaleDB gives the timeseries ergonomics without adding a second system.

## Consequences

- This is the heaviest lock-in in the project. Persisted run artifacts are
  stored as JSON columns in the same database as the price data, so moving
  either one alone is not a small change.
- Artifact retention and size bounds are undecided and become a real problem as
  run history grows (see `docs/open-decisions.md`).
- Tick-level archive storage is deliberately **not** covered by this decision;
  it remains open, because tick volume is the one workload where the single-store
  assumption plausibly breaks.
