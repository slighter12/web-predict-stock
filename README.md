# Personal Quant Research Platform

This repository is a docs-first quantitative research platform for two
workspaces:

- `research runs`: model execution, validation, comparison metadata, and run
  registry
- `data plane`: raw ingest preservation, replay, recovery drills, lifecycle
  records, and important events

This file is descriptive and navigational. Normative rules live in the
governance documents under `docs/`.

## Purpose

- orient new readers to the repository and documentation model
- point each question to a single owning document
- provide the shortest local startup path

## Owns

- repository orientation
- document routing for common questions
- the shortest quickstart path

## Does Not Own

- research or execution rules
- KPI formulas, thresholds, or gate truth conditions
- phase sequencing or delivery policy
- the authoritative description of the currently implemented API surface

## Consumes

- `docs/project-goals.md`
- `docs/research-spec.md`
- `docs/plan.md`
- `docs/validation-gates.md`
- `docs/dev.md`
- `docs/implementation-snapshot.md`
- `docs/decision-register.md`

## Produces

- the repository entrypoint for human readers
- the document map used to route review questions

## Decision Rule

Use this file first for orientation, then move to the single document that owns
the question you are trying to answer.

## Documentation Map

Use the document that owns the question you are trying to answer.

| Question | Owner |
| --- | --- |
| Why does this project exist, what matters most, and what is out of scope? | `docs/project-goals.md` |
| What behavior, fields, and comparison rules must exist? | `docs/research-spec.md` |
| What should be built next and in what order? | `docs/plan.md` |
| How is success measured quantitatively and when does a gate pass? | `docs/validation-gates.md` |
| How do I run the repository locally? | `docs/dev.md` |
| What is currently implemented today? | `docs/implementation-snapshot.md` |
| Which open decisions still block durable policy? | `docs/decision-register.md` |

## Reading Order

1. Read `README.md` for orientation.
2. Read `docs/project-goals.md` for priority and scope.
3. Read `docs/research-spec.md` for normative behavior.
4. Read `docs/plan.md` for delivery order and dependencies.
5. Read `docs/validation-gates.md` for formulas, thresholds, and gates.
6. Read `docs/dev.md` for local operations only.
7. Use `docs/implementation-snapshot.md` and `docs/decision-register.md` as
   descriptive support files when needed.

## Repository Snapshot

- Backend: FastAPI on Python 3.12+
- Frontend: Svelte 5 + Vite + TanStack Svelte Query + ECharts
- Database: PostgreSQL + TimescaleDB
- Modeling: XGBoost and scikit-learn based research workflows
- Data sources: TWSE plus yfinance bootstrap or backfill support
- Research execution: VectorBT with fees and slippage support

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

Frontend setup, data loading, optional developer dependencies, and smoke or
test commands are intentionally owned by [`docs/dev.md`](docs/dev.md).

## Repository Structure

```bash
.
├── backend/                # app, api, schemas, services, repositories, runtime, domain
├── frontend/               # Svelte workspaces for research runs and data plane
├── scripts/                # ingestion and smoke utilities
├── docs/                   # goals, spec, plan, validation, dev, snapshots
├── tests/                  # repository tests
└── docker-compose.yml      # PostgreSQL + TimescaleDB service
```

## Descriptive Support Files

- [`docs/implementation-snapshot.md`](docs/implementation-snapshot.md)
  records the current implementation snapshot. It is descriptive only and is
  never the source of truth for normative behavior.
- [`docs/decision-register.md`](docs/decision-register.md)
  records open `TBD-*` decisions, owners, blocking impact, and next actions.
