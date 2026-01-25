# Platform: Personal Quantitative Research Platform

A personal, high-performance quantitative research platform designed for alpha discovery and strategy backtesting. The system focuses on medium-to-low frequency strategies and prioritizes research velocity over ultra-low latency.

## Vision

Provide an efficient, visual research loop that allows users to define features, train models, run backtests, and evaluate strategies from a single workspace.

## Key Features

- F-01 Data Pipeline: Scheduled scraper for daily OHLCV data (TWSE), cleaned and stored in PostgreSQL.
- F-01a Historical Backfill: Bootstrap 3-5 years of history via yfinance to enable immediate model training.
- F-02 Dynamic Feature Engineering UI: A no-code interface for feature vector definitions.
- F-03 Modeling Engine: Train ML models from user-defined feature configs.
- F-04 Vectorized Backtesting: Use model signals with transaction costs and slippage.
- F-05 Strategy Dashboard: Visualize equity curves, signals, and KPIs.

## Tech Stack

- Language: Python 3.12+ (backend), TypeScript (frontend)
- Package Manager: uv (backend), npm (frontend)
- Backend: FastAPI (CORS enabled for local dev)
- Frontend: Svelte 5 + Vite
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
│   ├── main.py             # API entry point (CORS enabled)
│   ├── database.py         # DB connection and ORM models
│   ├── data_service.py     # Data fetching layer
│   ├── feature_engine.py   # Dynamic feature generation
│   ├── model_service.py    # XGBoost training and signal generation
│   ├── backtest_service.py # VectorBT integration with fees/slippage
│   └── requirements.txt    # Backend dependencies
├── frontend/               # Svelte 5 application
│   ├── src/
│   │   ├── lib/            # Svelte components and stores
│   │   └── App.svelte      # Main layout
│   └── package.json
├── scripts/                # Utility scripts (scrapers, ETL)
│   └── scraper.py          # TWSE daily updates + yfinance backfill
└── docker-compose.yml      # PostgreSQL + TimescaleDB service
```

## Planning

Progress planning and milestones are tracked in PROPOSAL.md.

## Local Setup

Prereqs: Docker, Python 3.12+, and `uv`.

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
uv sync --group dev
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

## Troubleshooting

- XGBoost import error on macOS (`libomp.dylib` missing): install OpenMP with
  `brew install libomp`. Without it, training will fail when `train_xgboost` runs.

## Testing

Unit tests:
```bash
.venv/bin/python -m pytest -q
```

Smoke test (requires DB + data loaded):
```bash
.venv/bin/python scripts/smoke_backtest.py
```

## Configuration (Example)

This config is the reference format for implementation. All values are adjustable per run.

```json
{
  "market": "TW",
  "return_target": "open_to_open",
  "horizon_days": 1,
  "selection": {
    "threshold_metric": "predicted_return",
    "threshold": 0.003,
    "top_n": 5,
    "weighting": "equal"
  },
  "trading_rules": {
    "rebalance": "daily_open",
    "allow_same_day_reinvest": true,
    "allow_intraday": false,
    "allow_leverage": false
  },
  "exit_rules": {
    "allow_proactive_sells": true,
    "default_liquidation": "next_open"
  },
  "execution": {
    "matching_model": "ohlc_default",
    "slippage": 0.001,
    "fees": 0.002
  }
}
```

## Reference Logic (Model + Backtest)

Model is swappable. It only needs to implement fit/predict and output a numeric score used by the selection threshold.

```python
import vectorbt as vbt
from sklearn.model_selection import train_test_split

def build_model(config):
    # Swap model implementation here (e.g., XGBoost regressor).
    ...

def train_and_backtest_demo(df, config):
    # Build features using data available at t-1 close.
    df["MA_5"] = vbt.MA.run(df["close"], 5).ma.shift(1)
    df["RSI"] = vbt.RSI.run(df["close"], 14).rsi.shift(1)

    # Default target: open-to-open forward return.
    df["target"] = (df["open"].shift(-1) / df["open"] - 1.0)
    df = df.dropna()

    feature_cols = ["MA_5", "RSI"]
    X = df[feature_cols]
    y = df["target"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, shuffle=False
    )
    model = build_model(config)
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    threshold = config["selection"]["threshold"]
    entries = preds >= threshold
    exits = preds < threshold

    price_data = df.loc[X_test.index]["open"]
    pf = vbt.Portfolio.from_signals(
        price_data,
        entries,
        exits,
        fees=config["execution"]["fees"],
        slippage=config["execution"]["slippage"],
        freq="D",
    )
    return pf.stats()
```
