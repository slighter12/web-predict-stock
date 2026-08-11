# Quant Research-to-Opinion Workbench

This repository turns quantitative research artifacts into model opinions a solo
investor-researcher reads before deciding for themselves. It is market-phased and
starts with Taiwan daily equity data (ADR-0003).

The v1 loop is intentionally narrow: create a baseline research run, inspect
model quality, review the resulting strategy backtest, and compare persisted
research runs. It is not a broker, a live-trading system, or a personalized
advisory product — see ADR-0002 for where that boundary sits.

## V1 Product Flow

The main workflow is:

1. Dataset and date range
2. Feature set
3. Prediction task
4. Model diagnostics
5. Strategy backtest
6. Research-run comparison

The default prediction task combines forward-return regression with a
provisionally calibrated direction classifier. Because the strategy is
long-only, the classifier is the admission gate deciding which symbols may enter
the candidate set at all, and the regression score ranks and weights what it
admitted (ADR-0005). Artifact completeness does not establish
out-of-sample skill or investment viability.

## What This Repository Owns

- TW daily research-run creation and persisted review
- feature selection for model-ready daily data
- tabular regression model diagnostics
- calibrated direction-classification diagnostics
- strategy backtest artifacts derived from model scores
- research-run registry and comparison context
- data-readiness diagnostics needed to explain research reliability

## What This Repository Does Not Own For V1

- broker execution or live-order semantics
- simulation-platform integration as a primary product surface
- adaptive or RL workflows
- peer inference, factor expansion, external-signal breadth, or tick archive UX
  as main-flow requirements
- multi-user productization or admin-console completeness

Those advanced capabilities may exist as backend foundations or internal
diagnostics, but they are hidden from the v1 research path unless a future plan
promotes them deliberately.

## Current Status At A Glance

| Area | V1 status | Notes |
| --- | --- | --- |
| Research-run core | implemented | run creation, registry records, runtime metadata, and saved-run lookup exist |
| TW daily data readiness | implemented with diagnostics | ingestion, replay, lifecycle, important-event, and recovery surfaces support data trust checks |
| Baseline research-run builder | implemented | a researcher can start from the baseline workflow without editing API payloads |
| Regression diagnostics | implemented | successful regression runs return and reload model-quality artifacts before strategy interpretation |
| Hybrid model opinion | implemented | regression ranking and the direction gate produce a common-date, manual-review opinion; holdout signals remain evaluation-only |
| Persisted artifact reload | verified | new successful runs reload every artifact required by `SPEC-RUN-001`, plus artifact completeness summaries |
| Research-run comparison | usable for v1 loop | search, load, and compare work for complete research-review runs; metadata-only and partial records expose backend caveats before comparison |
| Advanced/platform modules | hidden advanced | execution, adaptive, peer, factor, and tick archive capabilities are not v1 main-flow surfaces |

For the fuller implementation inventory, use
[`docs/implementation-status.md`](docs/implementation-status.md). That file may
include lower-level or advanced foundations that are not v1 product commitments.
Retained backend foundations and metadata fields are compatibility or internal
diagnostic surfaces unless a future roadmap promotes them.

## Implemented Today

### Backend

- FastAPI route groups for system health, research runs, data-readiness
  diagnostics, and advanced internal foundations
- PostgreSQL plus TimescaleDB-backed persistence for research-run metadata and
  market-data support records
- daily research-run creation using tabular features, tree-based regressors,
  backtest metrics, signals, warnings, and registry records

### Frontend

The frontend rewrite is planned but has not started. No active frontend feature
development is underway; the backend-first pause remains in effect while backend
contracts and evaluation mature.

- Start surface for the three common tasks:
  - start a baseline research run
  - open recent research runs
  - check data readiness
- Experiment Builder for the baseline TW daily research workflow
- Experiments surface for persisted run lookup, review, and comparison
- Data Support as a secondary diagnostic surface, not the default research path

## Still Partial Or Deferred

- the direction admission gate is provisionally calibrated; its calibration
  gates and pooled diagnostics do not establish per-symbol skill
- richer pairwise comparison explanations can still improve review workflow, but
  incomplete artifacts and backend comparison caveats now block optimistic compare
- execution, adaptive, peer, factor, and tick archive modules are deferred from
  the v1 main workflow

## Documentation Map

| Question | Owner |
| --- | --- |
| What does this term mean? | [`CONTEXT.md`](CONTEXT.md) |
| Why was something decided this way? | [`docs/adr/`](docs/adr/) |
| Where do I start when picking up any task? | [`docs/agents/domain.md`](docs/agents/domain.md) |
| How do I review a product-direction proposal? | [`docs/review-checklist.md`](docs/review-checklist.md) |
| Which decisions are still missing? | [`docs/open-decisions.md`](docs/open-decisions.md) |
| Why does this project exist and what is in or out of v1 scope? | `docs/project-goals.md` |
| What behavior, fields, diagnostics, and comparison rules must exist? | `docs/research-spec.md` |
| What should be built next and in what order? | `docs/plan.md` |
| How is success measured and what is excluded from v1 gates? | `docs/validation-gates.md` |
| How do I run the repository locally? | `docs/dev.md` |
| Which dependency directions and internal compatibility rules apply? | `docs/backend-architecture.md` |
| What is implemented today, what is partial, and what is still pending? | `docs/implementation-status.md` |
| Which removed advanced features are future candidates? | `docs/deferred-feature-plan.md` |

The first three rows answer three different kinds of question about the same
thing and do not overlap: a glossary entry says what a term *means*, a spec says
what it must *satisfy*, an ADR says why it was *decided*. See ADR-0001.

## Suggested Reading Paths

### New To The Repository

1. `README.md`
2. [`CONTEXT.md`](CONTEXT.md)
3. `docs/project-goals.md`
4. `docs/research-spec.md`
5. `docs/dev.md`

### Planning The Next Chunk Of Work

1. [`docs/adr/README.md`](docs/adr/README.md)
2. [`docs/review-checklist.md`](docs/review-checklist.md)
3. [`docs/open-decisions.md`](docs/open-decisions.md)
4. `docs/project-goals.md`
5. `docs/research-spec.md`
6. `docs/plan.md`
7. `docs/validation-gates.md`
8. `docs/implementation-status.md`

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
├── docs/                   # adr, open decisions, goals, spec, plan, validation, dev, status
├── tests/                  # domain tests plus script entrypoint coverage
└── docker-compose.yml      # PostgreSQL + TimescaleDB service
```
