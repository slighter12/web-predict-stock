# Project Proposal: Personal Quantitative Research Platform

This document tracks the MVP execution plan and milestones. For the full spec and architecture, see README.md.

## Current Assumptions (Confirmed)

- Prediction target is forward return (regression). Default is open-to-open, and the horizon is configurable.
- Signals must be generated with data available before execution; default uses features up to t-1 close, trade at t open, evaluate to t+1 open.
- Supported return targets (configurable): open-to-open (default), close-to-close, open-to-close.
- Data source preference is official exchange data. Use raw, unadjusted prices as the default.
- Data merge rule: official exchange data overrides yfinance when both are available.
- Corporate action adjustment is optional and should be provided as a helper function, not a default.
- Validation should include multiple time-series methods and baselines.
- Execution price model is configurable and pluggable. Default uses OHLC ranges (TW: buy above low, sell below high; US: buy above close, sell below high). OHLC matching is for execution validation only and must not affect signal generation.
- Trading rules: daily frequency, single rebalance, no intraday trading, no leverage, same-day reinvest allowed, PnL compounds.
- Portfolio selection: apply a return threshold, then pick top-N symbols; equal weight; stay in cash if none qualify. Threshold metric and N are configurable.
- Exit rules: allow proactive sells; default worst-case is full liquidation at next open.
- Universe can be multi-symbol with a capital limit per run.

## Matching Model Interface (Initial Design)

Purpose: allow easy swapping of execution price logic without changing core backtest flow.

Example interface:

```python
from dataclasses import dataclass
from typing import Literal

Side = Literal["buy", "sell"]

@dataclass
class MarketConfig:
    market: str  # "TW" or "US"
    slippage: float

def match_price(
    side: Side,
    ohlc: dict,
    config: MarketConfig,
    model: str = "ohlc_default",
) -> float:
    """Return executable price based on the selected matching model."""
    ...
```

Default model behavior:
- TW: buy above low, sell below high
- US: buy above close, sell below high

## Progress Plan (MVP)

### Phase I: Infrastructure and Data

Status: Not started

- Define folder structure: backend/, frontend/, scripts/.
- Add docker-compose for PostgreSQL + TimescaleDB.
- Initialize backend with uv and core dependencies (include yfinance).
- Implement DailyOHLCV model in backend/database.py.
- Implement backfill_history(symbol) via yfinance for 3-5 years of data.
- Implement scrape_daily_twse() for daily updates.
- Load and verify with symbol 2330.
- Store raw, unadjusted prices; add a helper to compute adjusted series if needed.
- Ensure schema supports multi-symbol queries.
- Define market-specific config (TW/US) for fees, slippage, and matching model selection.

Definition of done:
- Database container starts, data loads successfully, and sample queries return OHLCV rows.

### Phase II: Backend Core Logic

Status: Not started

- feature_engine.py: add_features(df, config) for MA/RSI (extensible).
- model_service.py: train_xgboost(df, target_shift=-1) with time-ordered split and return target.
- define configurable return targets (open-to-open default) with no look-ahead alignment to execution timing.
- evaluation module: implement multiple validation methods (walk-forward, rolling window, expanding window, holdout).
- add baselines (buy-and-hold, naive momentum, moving average crossover) for comparison.
- define minimum evaluation metrics: total return, Sharpe, max drawdown, turnover.
- backtest_service.py: run_backtest(model, X_test, price_data) with fees, slippage, and a swappable matching model.
- implement matching model interface and provide default OHLC-based TW/US implementations.
- enforce trading rules: single rebalance per day, no leverage, same-day reinvest, compounding PnL.
- implement multi-symbol selection: threshold filter + top-N, equal weight, keep cash if empty, all driven by config.
- implement exit rule logic: proactive sells with next-open liquidation as default.
- main.py: POST /api/v1/backtest with CORS enabled for localhost frontend.

Definition of done:
- Single API call returns KPIs and validation metrics from a complete train -> backtest flow.

### Phase III: Frontend (Svelte 5)

Status: Not started

- Initialize Svelte 5 + Vite + TypeScript scaffold.
- Build sidebar for symbol, date range, and feature config using runes state.
- Integrate ECharts equity curve component.
- Connect Run Backtest to backend API and render KPIs.

Definition of done:
- User can run a backtest from the UI and see a chart and KPI summary.

### Phase IV: Hardening and Quality

Status: Not started

- Add logging, error handling, and input validation.
- Add minimal tests for data pipeline and backtest outputs.
- Document local setup and usage flows.
- Add test fixtures for validation methods and baseline comparisons.

Definition of done:
- Basic test suite passes and README includes setup and run instructions.
