# Developer Notes

This document only covers local setup for the v1 research workbench. It is not
a product plan, feature inventory, or operations manual.

## Purpose

- start the local database, backend, and frontend
- apply migrations
- seed or load TW daily data for workbench development
- run focused checks when a task requires running commands

## Does Not Own

- product scope
- research semantics
- roadmap sequencing
- deferred module operations
- KPI formulas, thresholds, or gate truth conditions

For product scope, use `README.md`, `docs/project-goals.md`,
`docs/research-spec.md`, `docs/plan.md`, and `docs/validation-gates.md`.
Deferred modules live in `docs/deferred-feature-plan.md`.

## Local Tooling

- Python `3.12+`
- `uv`
- `bun`
- Docker

## Backend Setup

```bash
cp .env.example .env
uv venv .venv
uv sync

set -a
source .env
set +a
```

Optional developer dependencies:

```bash
uv sync --extra dev
```

Apply database migrations:

```bash
.venv/bin/python -m alembic upgrade head
```

Alternative Makefile path:

```bash
make setup
```

## Database

Start the local PostgreSQL and TimescaleDB service:

```bash
docker-compose up -d
```

Stop it:

```bash
docker-compose down
```

Makefile shortcuts:

```bash
make db-up
make db-down
```

The default host-machine PostgreSQL port is `65432`.

## Backend API

Run the API locally:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload
```

V1 backend development should usually stay inside:

- `backend/app/`
- `backend/platform/`
- `backend/shared/`
- `backend/system/`
- `backend/research/`
- `backend/market_data/`

## TW Daily Data Loading

Populate market data into the configured database:

```bash
.venv/bin/python -m scripts.market_data_ingestion
```

Default ingestion environment values:

- `INGEST_SYMBOL=2330`
- `INGEST_MARKET=TW`
- `INGEST_YEARS=5`

Run TW market daily batch ingestion when a broader local dataset is needed:

```bash
.venv/bin/python -m scripts.crawl_tw_daily_batch 2026-03-20 --refresh-universe
```

## Frontend

The frontend lives in `frontend/` and uses `bun`.

```bash
cd frontend
cp .env.example .env
bun install
bun run dev
```

Build the production bundle:

```bash
cd frontend
bun run build
```

Makefile shortcuts:

```bash
make frontend-install
make frontend-dev
make frontend-build
```

V1 frontend development should usually stay inside:

- `frontend/src/lib/api/`
- `frontend/src/lib/types/`
- `frontend/src/lib/state/`
- `frontend/src/lib/components/research-runs/`
- `frontend/src/lib/components/data-plane/`
- `frontend/src/lib/components/layout/`

## Smoke And Test Commands

These commands exist in the repository. Run them only when the task requires
running local checks.

```bash
make test
```

Equivalent direct command:

```bash
.venv/bin/python -m pytest -q
```

Frontend typecheck:

```bash
bun x tsc -p frontend/tsconfig.json --noEmit
```

## Environment Variables

Backend:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `CORS_ALLOWED_ORIGINS`

Frontend:

- `VITE_API_BASE_URL`

## Troubleshooting

- `POSTGRES_HOST=localhost` is the normal host-machine setting
- `POSTGRES_HOST=db` is the container-network setting
- the default frontend API target is `http://127.0.0.1:8000`
- if XGBoost fails on macOS because `libomp.dylib` is missing, install OpenMP:
  `brew install libomp`
