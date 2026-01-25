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
uv sync --group dev
```

## Makefile Shortcuts

```bash
make setup     # venv + deps + dev deps
make test      # pytest
make smoke     # DB-backed backtest
make db-up     # start TimescaleDB
make db-down   # stop TimescaleDB
```
