# Personal Quant Research Platform

This repository is a docs-first quantitative research platform centered on two
surfaces:

- `Prediction Studio`: a staged prediction workflow for data context, feature
  selection, model choice, validation, and results
- `Maintenance`: operational repair and verification tools for replay,
  recovery, lifecycle correction, important events, tick archives, and control
  checks

Use this file for orientation, current-project status, and document routing.
Normative rules still live under `docs/`.

## What This Repository Owns

- repository orientation
- current implementation summary
- document routing for common questions
- the shortest local startup path

## What This Repository Does Not Own

- runtime or execution semantics
- KPI formulas, thresholds, or gate truth conditions
- phase sequencing or delivery policy
- local troubleshooting details

## Current Status At A Glance

| Area | Status | Notes |
| --- | --- | --- |
| `P0` research-run core | `implemented` | run creation, run registry, runtime bundle metadata, and research-run inspector exist |
| `P1` TW daily data durability | `implemented` | ingestion, replay, recovery drills, schedules, lifecycle and important-event records, and ops KPI surfaces exist |
| `P2` tick archive durability | `implemented with constraints` | archive dispatch, import, replay, KPI, and gate surfaces exist; storage baseline is still provisional |
| `P3` tradability governance | `implemented` | tradability-state persistence, `GATE-P3-001`, and `GATE-P3-OPS-001` telemetry exist |
| `P4` to `P6` governance and model foundations | `partial foundation implemented` | comparison/governance metadata and shared tabular model-contract support exist, but these phases are not fully closed |
| `P7` to `P11` advanced foundations | `structural foundation implemented` | external signals, factor catalog, clustering, execution stubs, and adaptive lifecycle persistence exist |
| Durable operational qualification | `pending` | long-window ops gates and open `TBD-*` decisions still separate structural completion from durable qualification |

For the fuller status breakdown, including implemented, partial, and pending
areas, use [`docs/implementation-status.md`](docs/implementation-status.md).

## Implemented Today

### Backend

- FastAPI backend with route groups for:
  - system health
  - research runs and phase gates
  - daily data-plane workflows
  - tick archive workflows
  - execution simulation and live-stub controls
- PostgreSQL plus TimescaleDB-backed persistence for research runs, replay and
  recovery records, tick archive records, lifecycle and important-event data,
  and P7 to P11 foundation records
- scripts for scheduled recovery dispatch, scheduled ingestions, official
  record crawlers, TW company crawling, and tick-archive fixture support

### Frontend

- `Prediction Studio`
  - staged flow for `data -> feature -> model -> validation -> results`
  - same-page result review after submission
  - advanced details surface for saved-run lookup, health, and readiness gates
- `Maintenance`
  - manual data repair and recovery drills
  - replay and tick-archive verification
  - lifecycle and important-event correction
  - factor, peer, execution, and adaptive diagnostics

## Still Partial Or Not Implemented Yet

- durable ops qualification for `P1`, `P2`, `P3`, and `P7` to `P11` still
  depends on observation windows, not just structural artifacts
- tick archive storage is still local-first; remote object-store backends and
  storage redundancy are not implemented
- no dedicated frontend surfaces yet for several backend-only operational
  endpoints, including benchmark profiles, ingestion watchlist and dispatch,
  daily ops KPIs, crawler triggers, and TW company profile management
- simulation-platform baseline policy is still open under `TBD-003`
- live execution is still a guarded stub path, not a real broker adapter
- adaptive workflow support persists contracts and training-run lifecycle, but
  there is still no integrated RL backend

## Documentation Map

Use the document that owns the question you are trying to answer.

| Question | Owner |
| --- | --- |
| Why does this project exist and what is in or out of scope? | `docs/project-goals.md` |
| What behavior, fields, and comparison rules must exist? | `docs/research-spec.md` |
| What should be built next and in what order? | `docs/plan.md` |
| How is success measured quantitatively and when does a gate pass? | `docs/validation-gates.md` |
| How do I run the repository locally? | `docs/dev.md` |
| What is implemented today, what is partial, and what is still pending? | `docs/implementation-status.md` |
| Which open decisions still block durable policy? | `docs/decision-register.md` |

## Suggested Reading Paths

### New To The Repository

1. `README.md`
2. `docs/project-goals.md`
3. `docs/implementation-status.md`
4. `docs/dev.md`

### Planning The Next Chunk Of Work

1. `docs/project-goals.md`
2. `docs/research-spec.md`
3. `docs/plan.md`
4. `docs/decision-register.md`
5. `docs/implementation-status.md`

### Checking What Is Missing Before Building

1. `docs/implementation-status.md`
2. `docs/plan.md`
3. `docs/decision-register.md`

## Quickstart

Use [`docs/dev.md`](docs/dev.md) for the full local workflow. The shortest path
is:

```bash
cp .env.example .env
docker-compose up -d
uv venv .venv
uv sync
set -a
source .env
set +a
.venv/bin/python -m uvicorn backend.main:app --reload
```

If you need the data-plane schema locally, run migrations first:

```bash
.venv/bin/python -m alembic upgrade head
```

Frontend setup, data loading, optional developer dependencies, and smoke or
test commands are intentionally owned by [`docs/dev.md`](docs/dev.md).

## Repository Structure

```bash
.
├── backend/                # app, platform, shared, system, research, market_data, signals, execution
├── frontend/               # Svelte surfaces for prediction workflow and maintenance
├── scripts/                # local operational entrypoints and utilities
├── docs/                   # goals, spec, plan, validation, dev, status
├── tests/                  # domain tests plus script entrypoint coverage
└── docker-compose.yml      # PostgreSQL + TimescaleDB service
```
