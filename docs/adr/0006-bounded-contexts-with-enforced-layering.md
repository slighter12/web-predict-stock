---
status: accepted
date: 2026-08-10
---

# Backend is bounded contexts with inward layering, enforced by tests

The backend is a single deployable organized as bounded contexts — `research`,
`market_data`, `signals`, `execution` — with dependencies pointing inward:

```text
api -> services -> domain/policies/contracts
             \-> repositories -> database
```

A context exposes data to another context through contracts or services, never
by exporting its models and repositories. `backend/shared/analytics/` holds
reusable deterministic analytics and may not load database state or call context
services.

The decision that matters here is not the layering itself but that it is
**enforced by an executable test** rather than by convention:
`tests/architecture/test_backend_import_boundaries.py`. A layering rule that
lives only in a document is a rule that erodes silently over a year of changes;
this one fails a test run instead.

## Consequences

- Legacy violations are handled as an **explicit named baseline** rather than
  being grandfathered invisibly. The service-to-database exceptions are listed
  in `docs/backend-architecture.md` and the test rejects any new ones. This
  makes the debt finite and countable instead of ambient.
- Internal `backend.*` module paths are **not** a supported SDK and may move
  when context ownership changes. Supported compatibility surfaces are HTTP
  contracts, documented command entry points, migrations, and persisted record
  shapes.
- `scripts/` is a command boundary; backend modules never import it.
- Detailed dependency rules and the current exception list stay in
  `docs/backend-architecture.md`. This ADR records why the shape was chosen; the
  architecture doc records what the rules currently are.
