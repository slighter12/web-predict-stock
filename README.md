# TW Daily Quant ML Research Workbench

This repository is a research-first workbench for TW daily quantitative ML
experiments. The v1 product is intentionally narrow: help a researcher create a
baseline study, inspect model quality, review the resulting strategy backtest,
and compare persisted experiments without treating the app as an execution or
operations platform.

## V1 Product Flow

The main workflow is:

1. Dataset and date range
2. Feature set
3. Prediction task
4. Model diagnostics
5. Strategy backtest
6. Experiment comparison

Prediction tasks include both regression and classification at the specification
level. The first implementation pass supports regression diagnostics; the
classification contract is documented so it can be added without changing the
research workflow shape.

## What This Repository Owns

- TW daily research-run creation and persisted review
- feature selection for model-ready daily data
- tabular regression model diagnostics
- strategy backtest artifacts derived from model scores
- experiment registry and comparison context
- data-readiness diagnostics needed to explain research reliability

## What This Repository Does Not Own For V1

- broker execution or live-order semantics
- simulation-platform integration as a primary product surface
- adaptive or RL workflows
- peer inference, factor expansion, external-signal breadth, or tick archive UX
  as main-flow requirements
- multi-user productization or operations-console completeness

Those advanced capabilities may exist as backend foundations or internal
diagnostics, but they are hidden from the v1 research path unless a future plan
promotes them deliberately.

## Current Status At A Glance

| Area | V1 status | Notes |
| --- | --- | --- |
| Research-run core | implemented | run creation, registry records, runtime metadata, and saved-run lookup exist |
| TW daily data readiness | implemented with diagnostics | ingestion, replay, lifecycle, important-event, and recovery surfaces support data trust checks |
| Baseline experiment builder | implemented | a researcher can start from the baseline workflow without editing API payloads |
| Regression diagnostics | in progress | v1 requires persisted model-quality artifacts, not strategy metrics alone |
| Experiment comparison | in progress | persisted runs must be searchable, loadable, and comparable with clear caveats |
| Advanced/platform modules | hidden advanced | execution, adaptive, peer, factor, and tick archive capabilities are not v1 main-flow surfaces |

For the fuller implementation inventory, use
[`docs/implementation-status.md`](docs/implementation-status.md). That file may
include lower-level or advanced foundations that are not v1 product commitments.

## Implemented Today

### Backend

- FastAPI route groups for system health, research runs, data-readiness
  diagnostics, and advanced internal foundations
- PostgreSQL plus TimescaleDB-backed persistence for research-run metadata and
  market-data support records
- daily research-run creation using tabular features, tree-based regressors,
  backtest metrics, signals, warnings, and registry records

### Frontend

- Start surface for the three common tasks:
  - start a baseline study
  - open recent experiments
  - check data readiness
- Experiment Builder for the baseline TW daily research workflow
- Experiments surface for persisted run lookup, review, and comparison
- Data Ops as a secondary diagnostic surface, not the default research path

## Still Partial Or Deferred

- persisted runs need complete model diagnostics, predictions/signals, equity
  curve, baselines, warnings, runtime metadata, and request config available
  after reload
- classification is specified but not implemented in the first code pass
- comparison needs clearer eligibility and reason labels when runs should not be
  compared
- execution, adaptive, peer, factor, and tick archive modules are deferred from
  the v1 main workflow

## Documentation Map

| Question | Owner |
| --- | --- |
| Why does this project exist and what is in or out of v1 scope? | `docs/project-goals.md` |
| What behavior, fields, diagnostics, and comparison rules must exist? | `docs/research-spec.md` |
| What should be built next and in what order? | `docs/plan.md` |
| How is success measured and what is excluded from v1 gates? | `docs/validation-gates.md` |
| How do I run the repository locally? | `docs/dev.md` |
| What is implemented today, what is partial, and what is still pending? | `docs/implementation-status.md` |
| Which open decisions still block durable policy? | `docs/decision-register.md` |
| Which removed advanced features are future candidates? | `docs/deferred-feature-plan.md` |

## Suggested Reading Paths

### New To The Repository

1. `README.md`
2. `docs/project-goals.md`
3. `docs/research-spec.md`
4. `docs/dev.md`

### Planning The Next Chunk Of Work

1. `docs/project-goals.md`
2. `docs/research-spec.md`
3. `docs/plan.md`
4. `docs/validation-gates.md`
5. `docs/implementation-status.md`

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
├── frontend/               # Svelte workbench surfaces for builder, experiments, and data diagnostics
├── scripts/                # local operational entrypoints and utilities
├── docs/                   # goals, spec, plan, validation, dev, status
├── tests/                  # domain tests plus script entrypoint coverage
└── docker-compose.yml      # PostgreSQL + TimescaleDB service
```
