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

Apply database migrations before using the data-plane workflows:

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

## Backend API

Run the API locally:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload
```

Current backend ownership is:

- `backend/app/`: FastAPI app assembly, middleware, exception registration, router include
- `backend/platform/`: HTTP request context, error envelopes, DB session/model aggregation, shared runtime helpers
- `backend/shared/`: analytics core and truly shared contracts
- `backend/system/`: system-health routes
- `backend/research/`: research-run routes, contracts, services, repositories, and run metadata domain helpers
- `backend/market_data/`: ingestion, replay, recovery, lifecycle, important-event, tick-archive, and TW company workflows
- `backend/signals/`: external-signal, factor-catalog, cluster, and peer-feature contracts and persistence
- `backend/execution/`: simulation, live-stub, and kill-switch routes and services

## Data Loading

Populate market data into the configured database:

```bash
.venv/bin/python -m scripts.market_data_ingestion
```

Default ingestion environment values:

- `INGEST_SYMBOL=2330`
- `INGEST_MARKET=TW`
- `INGEST_YEARS=5`

Run due scheduled recovery drills manually:

```bash
.venv/bin/python -m scripts.dispatch_scheduled_recovery_drills
```

Run due scheduled ingestions manually:

```bash
.venv/bin/python -m scripts.dispatch_scheduled_ingestions
```

Run lifecycle record crawler:

```bash
.venv/bin/python -m scripts.crawl_lifecycle_records
```

Run important event crawler:

```bash
.venv/bin/python -m scripts.crawl_important_events
```

Run TW company profile crawler:

```bash
.venv/bin/python -m scripts.crawl_tw_company_profiles
```

Run TW market daily batch ingestion:

```bash
.venv/bin/python -m scripts.crawl_tw_daily_batch 2026-03-20 --refresh-universe
```

Run a local TWSE tick snapshot smoke test:

```bash
export TWSE_MIS_SKIP_TLS_VERIFY=true
.venv/bin/python -c "from backend.market_data.services.tick_archive_provider import fetch_twse_public_snapshot; result = fetch_twse_public_snapshot(['2330','2317']); print(len(result['observations']))"
```

Run the deterministic tick-archive fixture for failed-run and partial-replay validation:

```bash
.venv/bin/python -m scripts.seed_tick_archive_fixture
```

Manual import note:

- `POST /api/v1/data/tick-archive-imports` now validates that uploaded archive
  observations match the submitted `market` and `trading_date`; mismatched
  payloads are rejected before archive metadata is persisted.
- upload validation is content-based after archive write/read/parse; the
  current tick-archive implementation does not treat browser MIME type as a trusted
  acceptance signal for JSONL.GZ payloads.
- operator-facing `trading_date` should be interpreted against the `Asia/Taipei`
  market calendar even though the browser date input defaults from the local
  workstation timezone.

Tick archive operational notes:

- archive storage is currently `local_filesystem` only under `backend/var/tick_archives/`
- each persisted tick archive part keeps the raw TWSE snapshot request envelope at
  the archive object path and writes a normalized observation sidecar under
  `backend/var/tick_archives/<market>/<trading_date>/<run_id>/normalized/`
- when `GOOGLE_DRIVE_TICK_ARCHIVE_ROOT` is configured, each new tick archive is
  mirrored into the same relative object-key layout under that Google Drive path
- when `TICK_ARCHIVE_BACKUP_REQUIRED=true`, tick archive dispatch and import
  fail fast if the Google Drive mirror is unavailable or the mirror write does
  not complete successfully
- symbol resolution prefers active `tw_company_profiles`, then lifecycle
  records, and falls back to `daily_ohlcv` only when the curated universe is
  unavailable
- tick KPI history intentionally uses a fixed rolling `20` trading-day window
  for comparability
- near-zero benchmark-window wall-clock restore durations are omitted from
  throughput telemetry rather than turned into extreme values
- TW company universe crawl defaults to the current TWSE/TPEX public company
  profile feeds and can be overridden through:
  - `TWSE_COMPANY_SOURCE_URL`
  - `TPEX_COMPANY_SOURCE_URL`

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
  and tick-archive panel
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

Run only the script entrypoint tests:

```bash
.venv/bin/python -m pytest tests/scripts -q
```

## Environment Variables

Backend:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `CORS_ALLOWED_ORIGINS`
- `TWSE_MIS_CA_BUNDLE`
- `TWSE_MIS_CA_CACHE_PATH`
- `TWSE_MIS_CA_BUNDLE_URL`
- `TWSE_MIS_CA_AUTO_DOWNLOAD`
- `TWSE_MIS_SKIP_TLS_VERIFY`
- `TWSE_MIS_ENABLE_INSECURE_FALLBACK`

Frontend:

- `VITE_API_BASE_URL`

## Troubleshooting

- `POSTGRES_HOST=localhost` is the normal host-machine setting
- `POSTGRES_HOST=db` is the container-network setting
- the default frontend API target is `http://127.0.0.1:8000`
- TWSE tick snapshot fetches use `requests`; prefer `TWSE_MIS_CA_BUNDLE` when a
  local CA chain is available, or configure `TWSE_MIS_CA_AUTO_DOWNLOAD=true`
  with `TWSE_MIS_CA_BUNDLE_URL`
- keep `TWSE_MIS_SKIP_TLS_VERIFY=true` or
  `TWSE_MIS_ENABLE_INSECURE_FALLBACK=true` for local emergency use only
- if XGBoost fails on macOS because `libomp.dylib` is missing, install OpenMP:
  `brew install libomp`
