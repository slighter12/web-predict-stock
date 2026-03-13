# Project Proposal: Personal Quantitative Research Platform

This document tracks the MVP execution plan and milestones. For the full spec and architecture, see README.md.

## Current Backend v1

- `README.md` and `backend/api_models.py` are the source of truth for the live backend contract.
- Current backend scope: `TW`/`US`, multi-symbol, `strategy.type=research_v1`, MA/RSI features, XGBoost model, baselines, validation, and averaged validation metrics including `avg_sharpe`.
- Frontend dashboard is now in scope for the local MVP. Deployment-oriented UI work remains out of scope.

## Target Architecture Assumptions

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

Status: Completed

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

Status: Backend v1 contract completed; target-state expansion remains planned

- feature_engine.py: add_features(df, config) for MA/RSI (extensible).
- model_service.py: XGBoost-based training with time-ordered split and return target.
- define configurable return targets (open-to-open default) with no look-ahead alignment to execution timing.
- evaluation module: implement multiple validation methods (walk-forward, rolling window, expanding window, holdout).
- add baselines (buy-and-hold, naive momentum, moving average crossover) for comparison.
- define minimum evaluation metrics: total return, Sharpe, max drawdown, turnover, and `avg_sharpe`.
- target-state: keep backtest_service extensible for fees, slippage, and swappable matching models.
- target-state: keep matching model interface capable of multiple TW/US execution implementations.
- target-state: keep room for explicit trading rules and exit rule configuration beyond backend v1.
- current backend v1: multi-symbol threshold + top-N + equal weight + cash-if-empty via `strategy.type=research_v1`.
- main.py: POST /api/v1/backtest for the backend-only workflow.

Definition of done:
- Single API call returns KPIs and validation metrics from a complete train -> backtest flow.

### Phase III: Frontend (Svelte 5)

Status: Completed for local MVP

- Initialize Svelte 5 + Vite + TypeScript scaffold with bun.
- Build a single-screen dashboard for symbol, date range, features, strategy, validation, and baselines.
- Integrate ECharts equity curve component.
- Connect Run Backtest to backend API and render KPIs, validation, baselines, warnings, and signals.

Definition of done:
- User can run a backtest from the UI and see chart, KPI summary, validation output, baselines, warnings, and signals.

### Phase IV: Hardening and Quality

Status: In progress

- Add logging, error handling, and input validation.
- Add minimal tests for data pipeline and backtest outputs.
- Document local setup and usage flows.
- Add test fixtures for validation methods and baseline comparisons.

Definition of done:
- Basic test suite passes and README includes setup and run instructions.

## Development Flow (Expanded)

The detailed execution flow, acceptance criteria, and API contract draft are
captured in `docs/plan.md`. This section summarizes the sequence only.

Phase 0: Spec alignment
- Freeze config shape, return targets, trading rules, and timing alignment.
- Confirm data merge rule and corporate action policy.
- Draft API request/response contract for /api/v1/backtest.

Phase I: Infrastructure and data
- DB + Timescale startup, schema, and ingestion (TWSE + yfinance backfill).
- Multi-symbol support and data integrity checks.

Phase II: Backend core
- Feature engine, model training, validation methods, baselines.
- Backtest service with matching model interface and trading rules.
- Single API call returns KPIs and validation outputs.

Phase III: Frontend
- Deferred until backend-only scope is stable.
- Svelte 5 UI for config inputs and run backtest.
- Equity curve + KPI display from API.

Phase IV: Hardening and quality
- Logging, input validation, tests, fixtures, and docs.
