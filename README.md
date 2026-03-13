# Platform: Personal Quantitative Research Platform

A personal, high-performance quantitative research platform designed for alpha discovery and strategy backtesting. The system focuses on medium-to-low frequency strategies and prioritizes research velocity over ultra-low latency.

## Vision

Provide an efficient research loop that allows users to define features, train models, run backtests, and evaluate strategies from a single API and dashboard.

## Key Features

- F-01 Data Pipeline: Scheduled scraper for daily OHLCV data (TWSE), cleaned and stored in PostgreSQL.
- F-01a Historical Backfill: Bootstrap 3-5 years of history via yfinance to enable immediate model training.
- F-02 Feature Engineering API: Build MA and RSI features from request configs.
- F-03 Modeling Engine: Train XGBoost models from backend request payloads.
- F-04 Research Strategy Runner: Execute the `research_v1` threshold + top-N workflow with multi-symbol support.
- F-05 Validation and Baselines: Compare model output with time-series validation and baseline portfolios.
- F-06 Research Dashboard: Guided Svelte dashboard for configuring and reviewing backtests from one screen.

## Tech Stack

- Language: Python 3.12+ (backend)
- Package Manager: uv (backend), bun (frontend)
- Backend: FastAPI
- Frontend: Svelte 5 + Vite + TanStack Svelte Query + ECharts
- Database: PostgreSQL + TimescaleDB
- Data Processing: Pandas, NumPy, yfinance, requests
- Modeling: XGBoost, scikit-learn
- Backtesting: VectorBT (fees and slippage)
- Infrastructure: Docker + Docker Compose

Data merge rule: official exchange data overrides yfinance when both are available.

## Project Structure

```bash
.
├── backend/                # FastAPI application and core logic
│   ├── main.py             # API entry point
│   ├── database.py         # DB connection and ORM models
│   ├── data_service.py     # Data fetching layer
│   ├── feature_engine.py   # Dynamic feature generation
│   ├── model_service.py    # XGBoost training and signal generation
│   ├── backtest_service.py # VectorBT integration with fees/slippage
│   └── requirements.txt    # Backend dependencies
├── frontend/               # Bun-based Svelte dashboard
│   ├── src/                # UI components, API client, styles
│   └── package.json        # Frontend dependency manifest
├── scripts/                # Utility scripts (scrapers, ETL)
│   ├── scraper.py          # TWSE + yfinance ingest entry point
│   └── smoke_backtest.py   # Manual DB-backed smoke path
└── docker-compose.yml      # PostgreSQL + TimescaleDB service
```

## Planning

Progress planning and milestones are tracked in PROPOSAL.md.

## Local Setup

Prereqs: Docker, Python 3.12+, `uv`, and `bun`.

1) Create or update `.env` (use `.env.example` as a base). Change `POSTGRES_PORT`
    if you need a non-default port.

2) Start the database:

    ```bash
    docker-compose up -d
    ```

3) Create the virtual environment and install backend dependencies:

    ```bash
    uv venv .venv
    uv sync
    ```

    Optional (dev/test deps):

    ```bash
    uv sync --extra dev
    ```

4) Load environment variables (zsh):

    ```bash

    set -a
    source .env
    set +a

    ```

5) Backfill + daily update (TWSE + yfinance):

    ```bash
    .venv/bin/python scripts/scraper.py
    ```

6) Verify data query:

    ```bash
    .venv/bin/python -m backend.data_service
    ```

7) Run the backend API:

    ```bash
    .venv/bin/python -m uvicorn backend.main:app --reload
    ```

8) Install frontend dependencies:

    ```bash
    cd frontend
    bun install
    cp .env.example .env
    ```

9) Run the research dashboard:

    ```bash
    bun run dev
    ```

Frontend env:

- `VITE_API_BASE_URL`: backend base URL, default `http://127.0.0.1:8000`

Backend env:

- `CORS_ALLOWED_ORIGINS`: comma-separated origins allowed by FastAPI CORS, default `http://localhost:5173,http://127.0.0.1:5173`

## Troubleshooting

- XGBoost import error on macOS (`libomp.dylib` missing): install OpenMP with
  `brew install libomp`. Without it, training will fail when model training runs.

## Testing

Unit tests:

```bash
.venv/bin/python -m pytest -q
```

Smoke test (requires DB + data loaded):

```bash
.venv/bin/python scripts/smoke_backtest.py
```

Frontend build:

```bash
cd frontend
bun run build
```

Browser automation note:

- If you use `agent-browser` auth state or session files locally, keep them out of git. Common state paths are already ignored in `.gitignore`.

## Supported API Contract

Current backend v1 support:

- `market`: `TW`, `US`
- `strategy.type`: `research_v1`
- `features`: `ma`, `rsi`
- `model.type`: `xgboost`
- `validation.method`: `holdout`, `walk_forward`, `rolling_window`, `expanding_window`
- `validation.metrics`: averaged standard metrics plus `avg_sharpe`
- `baselines`: `buy_and_hold`, `naive_momentum`, `ma_crossover`
- `GET /api/v1/health`: frontend connectivity check

Error responses from `/api/v1/backtest` use:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "請檢查輸入內容",
    "details": {
      "fields": []
    }
  },
  "meta": {
    "request_id": "req_abc123"
  }
}
```

## Configuration (Example)

This request shape reflects the currently supported backend contract.

```json
{
  "market": "TW",
  "symbols": ["2330"],
  "date_range": { "start": "2019-01-01", "end": "2024-01-01" },
  "return_target": "open_to_open",
  "horizon_days": 1,
  "features": [
    { "name": "ma", "window": 5, "source": "close", "shift": 1 },
    { "name": "rsi", "window": 14, "source": "close", "shift": 1 }
  ],
  "model": {
    "type": "xgboost",
    "params": {}
  },
  "strategy": {
    "type": "research_v1",
    "threshold": 0.003,
    "top_n": 5,
    "allow_proactive_sells": true
  },
  "execution": {
    "slippage": 0.001,
    "fees": 0.002
  },
  "validation": {
    "method": "walk_forward",
    "splits": 3,
    "test_size": 0.2
  },
  "baselines": ["buy_and_hold", "naive_momentum"]
}
```

## Smoke Path

Manual smoke test prerequisites:

- PostgreSQL/TimescaleDB is running
- Historical data has been loaded with `scripts/scraper.py`
- `xgboost` imports correctly on your machine

Expected output from `scripts/smoke_backtest.py`:

```json
{
  "run_id": "uuid",
  "metrics": { "total_return": 0.12, "sharpe": 1.1 },
  "equity_points": 120,
  "signals": 25,
  "baselines": { "buy_and_hold": { "total_return": 0.08 } },
  "validation": {
    "method": "walk_forward",
    "metrics": {
      "avg_sharpe": 0.9,
      "total_return": 0.09,
      "sharpe": 0.9,
      "max_drawdown": -0.07,
      "turnover": 0.25
    }
  },
  "warnings": []
}
```

Common failure cases:

- Database is empty or not reachable
- Requested symbol/date range has no rows
- Training split or validation split has too little data
- `xgboost` cannot import because native dependencies are missing
