# Backend Architecture

This document defines the dependency direction for backend code. It is a
controlling maintenance specification, not a product roadmap.

## Contexts

The backend is organized around bounded contexts such as `research`,
`market_data`, `signals`, and `execution`. A context should expose data to
another context through contracts or services instead of exposing database
models and repositories directly.

`backend/shared/analytics/` contains reusable, deterministic analytics. It must
not load database state or call context services.

## Layers

Dependencies point inward in this order:

```text
api -> services -> domain/policies/contracts
             \-> repositories -> database
```

- `contracts/` owns transport and cross-boundary data shapes. It may call pure
  policy validators, but must not depend on domain, service, repository,
  database, or command-script code.
- `domain/` owns deterministic transformations and invariants. It may depend on
  contracts, but not on services, repositories, the database, or scripts.
- `policies/` owns stable named policy constants and recipe validation. It is
  transport-agnostic and must not import contracts, services, repositories,
  APIs, the database, or scripts. Types shared by contracts and policies belong
  in shared contracts rather than a bidirectional dependency.
- `repositories/` owns persistence queries and raw persistence snapshots. It
  does not build domain opinions, API responses, or service projections.
- `services/` orchestrates repositories, domain logic, and other context
  services.
- `api.py` performs HTTP translation and delegates work to services.
- `scripts/` is a command boundary. Backend modules must never import it.

## Current Research Boundaries

- Market-data research inputs are provided by
  `backend.market_data.services.research_inputs`.
- Research-run repositories return raw snapshots. Review summaries, version
  packs, diagnostics normalization, and opinion artifacts are assembled by
  `backend.research.services.run_projection`.
- Latest forward-signal snapshot selection is pure domain logic in
  `backend.research.domain.signal_snapshot`.
- Strict prospective recipes and constants live in
  `backend.research.policies.prospective`.

`backend.research.services._foundation_flow` temporarily imports the signals
repository directly. This is an explicit, narrow legacy exception enforced by
the architecture test; new exceptions should not be added. A future signals
service facade can remove it without changing the current public API.

## Compatibility

Supported compatibility surfaces are HTTP request and response contracts,
documented command entry points, database migrations, and persisted record
shapes. Internal `backend.*` Python module paths are not a supported SDK and may
move when context ownership changes.

Current same-symbol internal import migrations are:

- `backend.shared.analytics.market_data.get_data` to
  `backend.market_data.services.research_inputs.get_data`
- `backend.research.domain.prospective_recipe` to
  `backend.research.policies.prospective`
- `backend.research.services.eligibility` operations to
  `backend.market_data.services.research_inputs`

The removed repository facades do not have drop-in, same-symbol replacements.
Adaptive callers must use the workflow-level APIs in
`backend.research.services.adaptive`. Order and control callers must use the
workflow-level APIs in `backend.execution.services.orders` and
`backend.execution.services.controls`, adapting requests and response handling
to those service contracts.

Compatibility re-exports must not bypass context services or create additional
repository exceptions.

## Enforcement

Run the focused import-boundary checks with:

```bash
.venv/bin/python -m pytest -q tests/architecture/test_backend_import_boundaries.py
```

The checks resolve absolute and relative imports across the research,
market-data, signals, and execution contexts. They enforce contract, domain,
policy, repository, service, API, shared-analytics, and command-script
boundaries. They do not validate runtime behavior, database migrations, or HTTP
compatibility.
