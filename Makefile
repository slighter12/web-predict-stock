.PHONY: setup venv install dev test smoke db-up db-down frontend-install frontend-dev frontend-build frontend-test feature-registry-check

setup: venv install dev

venv:
	uv venv .venv

install:
	uv sync

dev:
	uv sync --extra dev

test:
	.venv/bin/python -m pytest -q
	$(MAKE) feature-registry-check

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

frontend-test:
	cd frontend && bun run test

feature-registry-check: frontend-test
	.venv/bin/python -m scripts.check_feature_registry_consistency
