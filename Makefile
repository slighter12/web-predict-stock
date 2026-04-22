.PHONY: setup venv install dev test smoke db-up db-down frontend-install frontend-dev frontend-build

setup: venv install dev

venv:
	uv venv .venv

install:
	uv sync

dev:
	uv sync --extra dev

test:
	.venv/bin/python -m pytest -q

smoke:
	.venv/bin/python -m scripts.backtest_smoke

db-up:
	docker-compose up -d

db-down:
	docker-compose down

frontend-install:
	cd frontend && bun install

frontend-dev:
	cd frontend && bun run dev

frontend-build:
	cd frontend && bun run build
