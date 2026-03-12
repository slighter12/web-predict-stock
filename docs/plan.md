# Development Flow and Implementation Plan

This document expands the MVP phases from `PROPOSAL.md` into actionable tasks,
acceptance criteria, and a draft API contract to unblock backend and frontend
work.

Status update:
- Phase I complete (DB + ingestion + schema + integrity checks).
- Phase II complete (features, model training, backtest, baselines, validation, API).
- Frontend remains deferred; backend-only contract is the active deliverable.

## Current Backend v1

- `README.md` and `backend/api_models.py` define the live request/response contract.
- Current backend scope: `TW`/`US`, multi-symbol, `strategy.type=research_v1`, MA/RSI features, XGBoost, baselines, validation, and averaged validation metrics including `avg_sharpe`.
- The sections below keep the broader target-state plan, so frontend and more extensible strategy/execution ideas should be read as future work unless they also appear in README.

Developer workflow notes are in `docs/dev.md`.

## Phase 0: Spec Alignment

Goals
- Freeze config shape and defaults (market, return target, horizon).
- Confirm timing alignment (t-1 features, t open execution, t+1 evaluation).
- Confirm data merge rule (official exchange overrides yfinance).
- Draft the API contract for /api/v1/backtest (request/response).

Acceptance
- A minimal config example is agreed and versioned.
- API request/response draft is recorded and referenced by backend/frontend.

## Phase I: Infrastructure and Data

Tasks
- Confirm `docker-compose.yml` launches PostgreSQL + TimescaleDB.
- Implement `DailyOHLCV` schema in `backend/database.py` with multi-symbol
  indexing (e.g., unique on (symbol, date, source) or (symbol, date)).
- Implement `backfill_history(symbol, years=3-5)` via yfinance.
- Implement `scrape_daily_twse()` for daily updates from official data.
- Apply merge rule: official exchange data overwrites yfinance for conflicts.
- Add minimal integrity checks (missing dates, nulls, negatives).
- Define market defaults (TW/US fees, slippage, matching model).

Acceptance
- DB container starts cleanly and is reachable from backend.
- Data loads for symbol 2330 with no duplicate rows.
- Sample query returns OHLCV rows for a known date range.

## Phase II: Backend Core Logic

Tasks
- `feature_engine.py`: `add_features(df, config)` for MA/RSI (extensible).
- `model_service.py`: XGBoost-based training with time-ordered
  split and configurable return targets.
- Validation module: walk-forward, rolling window, expanding window, holdout.
- Baselines: buy-and-hold, naive momentum, MA crossover.
- Metrics: total return, Sharpe, max drawdown, turnover, and `avg_sharpe`.
- `backtest_service.py`: run backtest with fees/slippage and matching model.
- Implement matching model interface and default TW/US OHLC behavior.
- Trading rules: daily rebalance, no intraday, no leverage, same-day reinvest.
- Multi-symbol selection: threshold + top-N, equal weight, cash if empty.
- Exit rules: proactive sells, default liquidation at next open.
- `main.py`: `POST /api/v1/backtest` for the backend-only workflow.

Acceptance
- One API call returns KPIs and validation metrics for a full train -> backtest
  flow.

## Phase III: Frontend (Svelte 5)

Tasks
- Deferred until backend-only scope is stable.
- Initialize Svelte 5 + Vite + TypeScript.
- Sidebar config inputs (symbol, date range, features).
- ECharts equity curve.
- Run Backtest -> API -> render KPIs.

Acceptance
- User can run a backtest and see a chart + KPI summary.

## Phase IV: Hardening and Quality

Tasks
- Logging, error handling, and input validation.
- Minimal tests for data pipeline and backtest outputs.
- Fixtures for validation methods and baseline comparisons.
- README setup and run instructions.

Acceptance
- Basic test suite passes and docs describe the local workflow.

## API Contract Draft (Target State)

Current-state note:
- The implemented backend v1 request is narrower than this draft.
- For the live contract, use `README.md` and `backend/api_models.py` as the source of truth.
- Current backend v1 already exposes `avg_sharpe` inside `validation.metrics` as a convenience metric.

Request (minimal + extensible)
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
  "model": { "type": "xgboost", "params": {} },
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

Response (UI + report minimums)
```json
{
  "run_id": "uuid",
  "metrics": {
    "total_return": 0.12,
    "sharpe": 1.1,
    "max_drawdown": -0.08,
    "turnover": 0.3
  },
  "equity_curve": [
    { "date": "2023-01-02", "equity": 1.0 }
  ],
  "signals": [
    { "date": "2023-01-02", "symbol": "2330", "score": 0.004, "position": 0.2 }
  ],
  "validation": {
    "method": "walk_forward",
    "metrics": {
      "avg_sharpe": 0.9,
      "sharpe": 0.9
    }
  },
  "baselines": {
    "buy_and_hold": { "total_return": 0.08 }
  },
  "warnings": []
}
```

## Minimal Config Example

```json
{
  "market": "TW",
  "return_target": "open_to_open",
  "horizon_days": 1,
  "features": [
    { "name": "ma", "window": 5, "source": "close", "shift": 1 }
  ],
  "strategy": {
    "type": "research_v1",
    "threshold": 0.003,
    "top_n": 5,
    "allow_proactive_sells": true
  },
  "execution": {
    "slippage": 0.001,
    "fees": 0.002
  }
}
```
