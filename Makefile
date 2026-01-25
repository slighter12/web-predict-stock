.PHONY: setup venv install dev test smoke db-up db-down

setup: venv install dev

venv:
	uv venv .venv

install:
	uv pip install --python .venv/bin/python -r backend/requirements.txt

dev:
	uv pip install --python .venv/bin/python ".[dev]"

test:
	.venv/bin/python -m pytest -q

smoke:
	.venv/bin/python scripts/smoke_backtest.py

db-up:
	docker-compose up -d

db-down:
	docker-compose down
