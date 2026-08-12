---
status: accepted
date: 2026-08-10
legacy_id: DEC-V1-007, DEC-V1-009, DEC-V1-011
---

# Platform-era modules are retained as internal foundations, not product surfaces

The codebase contains substantial machinery from an earlier, more ambitious
platform design: execution, adaptive workflows, peer inference and clustering,
factor catalogs, external signals, and tick archives. These modules stay in the
tree and their APIs may remain reachable for diagnostics and legacy tooling, but
they are **not** part of the main research workflow and are not product
commitments.

Deleting them was considered. They were kept because several are real
foundations for directions the project intends to take (external signals for
sentiment, factor catalogs for fundamentals), and rebuilding them from nothing
would cost more than the confusion of leaving them in place — provided the
confusion is addressed by writing this down.

## Consequences

- Presence of a module in the codebase is **not** evidence that it is in scope.
  This ADR is the answer to "why does this exist if we don't use it?"
- These surfaces must not be required to start or understand a baseline
  research run, and must not appear in main navigation.
- Promoting any of them into the main workflow requires a new ADR, because doing
  so changes the product's scope commitments.
