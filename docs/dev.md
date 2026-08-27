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

Calibration Matrix releases require the additive `0009` migration before the
new endpoint is enabled. Back up the database before upgrading. Rolling back
the application is the normal recovery path; the `0009` downgrade intentionally
keeps `calibration_matrices` and its research evidence so an older application
can ignore the extra table without deleting records. Dropping this table is a
separate retention operation and is not part of an application rollback.

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

See `docs/backend-architecture.md` for dependency direction and the enforced
contract, domain, repository, service, and script boundaries.

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

The batch command bootstraps the TWSE/TPEX company universe when it is empty.
Backfill a weekday date range with bounded universe refresh retries:

```bash
.venv/bin/python -m scripts.crawl_tw_daily_batch \
  --start-date 2023-07-24 \
  --end-date 2026-07-24 \
  --refresh-universe \
  --delay-seconds 1
```

Range runs emit one progress JSON object per attempted date to stderr and one
final aggregate JSON object to stdout. `--delay-seconds` defaults to `1.0` and
controls the pause between attempted dates; adjust it when throttling long
range backfills. The aggregate field
`universe_refresh_succeeded` is `true` only after a confirmed refresh, `false`
after an attempted refresh without confirmed success, and `null` when the range
runner did not attempt its bounded refresh.

For an explicit canary-first sequence, first run the canary date with a
refreshed universe, then run the requested range without refreshing it:

```bash
.venv/bin/python -m scripts.crawl_tw_daily_batch 2026-07-24 --refresh-universe
REFRESH_UNIVERSE=0 .venv/bin/python -m scripts.crawl_tw_daily_batch \
  --start-date 2023-07-24 \
  --end-date 2026-07-24 \
  --delay-seconds 1
```

If `failed_dates` exists, the range continues remaining dates and exits
non-zero. Retry each failed date with
`.venv/bin/python -m scripts.crawl_tw_daily_batch YYYY-MM-DD` before rerunning
the range. The current official TWSE/TPEX profile set is the canonical broad
universe; `ingestion_watchlist` remains the heavier per-symbol scheduling
surface.

## Strict Prospective Evidence Cohorts

Historical backtests and older forward signals are regression artifacts; they
do not count as prospective evidence. After the official batch for a trading
date has completed, create strict cohorts on that same Taiwan calendar date:

```bash
.venv/bin/python -m scripts.run_tw_prospective_cohorts \
  --basis-date YYYY-MM-DD --dry-run
.venv/bin/python -m scripts.run_tw_prospective_cohorts \
  --basis-date YYYY-MM-DD --cohort both
```

The command creates the fixed 2330 and active-profile TW cohorts serially.
The broad cohort is not created when its pre-decision model-ready coverage is
below 95%. It does not refresh market data or call external providers.

When each signal has two later research-eligible daily bars, inspect the
read-only outcome scorecard:

```bash
.venv/bin/python -m scripts.evaluate_tw_prospective_cohorts --cohort 2330
.venv/bin/python -m scripts.evaluate_tw_prospective_cohorts --cohort all
```

Only strict runs whose persisted `signal_frozen_at` and `basis_date` share the
Taiwan calendar date are counted. Do not change the fixed cohort recipe while
accumulating its first 120 completed trading days; a changed recipe starts a
new cohort.

## Calibration Matrix Operations

The Calibration Matrix endpoint is intentionally bounded by the versioned
`calibration_request_bounds_v1` policy:

- at most 200 symbols
- at most 12 features
- at most 1,827 inclusive calendar dates

Requests outside these limits return `422 VALIDATION_FAILED`. Only one
Calibration Matrix may run at a time in a backend process. A concurrent request
returns `429 CALIBRATION_BUSY` with `Retry-After: 1`. This process-local
semaphore does not provide a global guarantee across multiple workers; a
deployment that requires one active Calibration Matrix globally must use a
single worker or a database-level mutex, and still needs an external rate limit
or queue for public traffic.

Calibration responses expose the current-active TW membership caveat through
`comparison_caveats`; this is not point-in-time membership evidence. The
versioned `tw_official_preferred_yfinance_fallback_v1` policy resolves duplicate
`(Symbol, Market Date)` rows before target calculation and fold construction use
one pooled Market-Date axis under the
`tw_official_market_lane_excluding_confirmed_no_data_v2` policy: distinct TW
dates with at least one official source row in the market-data store for the
requested date range,
independent of requested Symbols and excluding confirmed official no-data dates.
Rolling features continue over
canonical observed rows when a Symbol is missing an axis date; an invalid OHLCV
row resets both feature and target continuity. The response records the source,
axis, and feature continuity policy versions, per-Symbol coverage counts, and the
number of defensively deduplicated rows. `excluded_row_count` counts canonical
observed rows that did not become model-ready; synthetic missing-axis rows are
reported separately rather than counted as exclusions.

Known model dependency or runtime-unavailable errors remain recorded as
model-unavailable results and are not replaced by another model family. Other
model, data-shape, or prediction errors fail the request with
`500 CALIBRATION_EVALUATION_FAILED`; no incomplete Matrix is persisted. A
request with no market rows returns `404 RESOURCE_NOT_FOUND`.

For a local Calibration Matrix verification after data and migrations are
ready, issue one bounded POST and reload the returned matrix:

Create `calibration-request.json` with a request within
`calibration_request_bounds_v1`, for example:

```json
{
  "symbols": ["2330"],
  "date_range": {"start": "2024-01-01", "end": "2024-03-31"},
  "features": [
    {"name": "ma", "window": 20, "source": "close", "shift": 1}
  ],
  "model_families": ["extra_trees"],
  "horizon_days": 5
}
```

```bash
curl -X POST http://127.0.0.1:8000/api/v1/research/calibration-matrices \
  -H 'Content-Type: application/json' \
  -d @calibration-request.json
curl http://127.0.0.1:8000/api/v1/research/calibration-matrices/MATRIX_ID
```

Replace `MATRIX_ID` with the `matrix_id` returned by the POST response.

## V1 Usable-Loop Verification

The core manual path is:

```text
Start -> Builder -> Run -> Review -> Reload -> Compare
```

For a clean local database, load at least the default TW daily symbol before
expecting the run path to succeed:

```bash
INGEST_SYMBOL=2330 INGEST_MARKET=TW INGEST_YEARS=3 \
  .venv/bin/python -m scripts.market_data_ingestion
```

The Start readiness panel may report `warning` when some known TW market dates
in the requested range are missing. That does not automatically block v1
research runs; the blocker is insufficient model-ready rows after feature
generation, shifting, target alignment, and complete-case exclusion of training
rows with non-finite model inputs or target values.

After DB, migrations, backend, frontend, and data are ready, verify:

- Start shows TW daily readiness context for the requested symbol
- Builder opens from the baseline task and defaults to Extra Trees
- Run creates a successful research record
- Review shows the artifacts required by `SPEC-RUN-001`, plus validation when
  requested
- Reload restores the persisted result and shows whether review artifacts are
  complete, partial, metadata-only, not requested, or unavailable on the record
- Compare two complete runs and confirm every `SPEC-COMP-001` dimension is
  visible, along with cost-basis and caveat fields
- Compare complete versus partial or old metadata-only records and confirm the
  compare status blocks optimistic interpretation
- Compare assumption mismatch cases and confirm the table flags dataset, target,
  cost, price-basis, or missing-feature policy differences

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

`make test` is the complete repository test gate. It runs the backend test suite,
the frontend feature-registry contract check, and the backend/frontend catalog
consistency check.

Backend-only regression test:

```bash
.venv/bin/python -m pytest -q
```

Feature-registry consistency gate:

```bash
make feature-registry-check
```

Frontend typecheck:

```bash
bun x tsc -p frontend/tsconfig.json --noEmit
```

Frontend production build:

```bash
make frontend-build
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
