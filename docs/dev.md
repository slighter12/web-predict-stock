# Developer Notes

## Purpose

Describe local environment setup, repository operations, and troubleshooting.

## Owns

- local tooling requirements
- local setup commands
- environment variables and local run commands
- troubleshooting notes for day-to-day development

## Does Not Own

- research or execution semantics
- roadmap sequencing
- KPI formulas, thresholds, or gate truth conditions
- strategic scope decisions

## Consumes

- `README.md` for repository orientation
- `.env.example`, `Makefile`, and project config files for operational details

## Produces

- the local operator workflow for backend, frontend, and database setup
- the authoritative list of local commands referenced by `README.md`

## Decision Rule

Use this document when the question is how to run, configure, or troubleshoot
the repository locally.

## Local Tooling

- Python `3.12+`
- `uv`
- `bun`
- Docker

## Backend Setup

Primary path:

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

## Backend API

Run the API locally:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload
```

Current backend ownership is:

- `backend/app.py`: FastAPI app, middleware, exception registration, router include
- `backend/api/`: HTTP routes for `system`, `research_runs`, and `data_plane`
- `backend/schemas/`: request and response contracts
- `backend/services/`: orchestration and domain-facing operations
- `backend/repositories/`: DB persistence and row mapping
- `backend/runtime/`: request-id, run-id, and error-envelope helpers
- `backend/domain/`: version-pack and runtime-bundle rules

## Data Loading

Populate market data into the configured database:

```bash
.venv/bin/python scripts/scraper.py
```

Default ingestion environment values:

- `INGEST_SYMBOL=2330`
- `INGEST_MARKET=TW`
- `INGEST_YEARS=5`

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

Current frontend ownership is:

- `frontend/src/lib/api/`: typed HTTP clients grouped by domain
- `frontend/src/lib/types/`: domain contracts and UI-facing shared types
- `frontend/src/lib/state/`: form defaults and payload mappers
- `frontend/src/lib/components/research-runs/`: research-run form and inspector
- `frontend/src/lib/components/data-plane/`: ingestion, replay, recovery, lifecycle, important-event panels
- `frontend/src/lib/components/layout/`: shared workspace shells

## Smoke and Test Commands

These commands exist in the repository. Run them only when the task requires
execution.

```bash
make test
```

Equivalent direct commands:

```bash
.venv/bin/python -m pytest -q
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
