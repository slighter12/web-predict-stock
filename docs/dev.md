# Developer Notes

## Dependency Sync (uv)

This repo ships `uv.lock`. Use `uv sync` to install exactly the locked
dependencies into the active environment.

```bash
uv venv .venv
uv sync
```

Optional dev/test dependencies:

```bash
uv sync --extra dev
```

## Frontend Setup (bun)

The frontend lives in `frontend/` and uses `bun` only.

```bash
cd frontend
bun install
cp .env.example .env
```

Set `VITE_API_BASE_URL` to the FastAPI origin if you are not using the default
`http://127.0.0.1:8000`.

Run the frontend dev server:

```bash
bun run dev
```

Build the production bundle:

```bash
bun run build
```

## Makefile Shortcuts

```bash
make setup     # venv + deps + dev deps
make test      # pytest
make smoke     # DB-backed backtest
make db-up     # start TimescaleDB
make db-down   # stop TimescaleDB
make frontend-install
make frontend-dev
make frontend-build
```
