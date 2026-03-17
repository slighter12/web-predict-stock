# Implementation Snapshot

This document is descriptive only. It records the current implementation
surface and must never be used as the source of truth for normative behavior.

## Purpose

- capture the current backend and request-surface snapshot
- record descriptive implementation notes that do not belong in governance
  documents
- help reviewers distinguish implemented state from target-state rules

## Owns

- descriptive implementation snapshots
- descriptive API and error-envelope examples
- descriptive notes about the current repository surface

## Does Not Own

- research or execution policy
- KPI formulas or gate truth conditions
- delivery sequencing
- open decision resolution

## Consumes

- repository implementation state
- `README.md` for routing context

## Produces

- the descriptive surface used to compare implementation state with target-state
  governance

## Decision Rule

Use this document only when the question is what the repository implements
today. If it conflicts with governance documents, governance documents win.

## Current Repository Snapshot

- Backend: FastAPI on Python 3.12+
- Frontend: Svelte 5 + Vite + TanStack Svelte Query + ECharts
- Database: PostgreSQL + TimescaleDB
- Modeling: XGBoost and scikit-learn based research workflows
- Data sources: TWSE plus yfinance bootstrap or backfill support
- Backtesting: VectorBT with fees and slippage support

## Current Merge Rule in Implementation

Official exchange data overrides yfinance when both are available.

## Current Implemented Backend Surface

The implemented request surface includes:

- markets: `TW`, `US`
- `strategy.type`: `research_v1`
- features: `ma`, `rsi`
- `model.type`: `xgboost`
- validation methods:
  `holdout`, `walk_forward`, `rolling_window`, `expanding_window`
- baselines:
  `buy_and_hold`, `naive_momentum`, `ma_crossover`
- endpoints:
  - `GET /api/v1/health`
  - `POST /api/v1/backtest`

Example `/api/v1/backtest` request:

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

## Current Error Envelope

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "請檢查輸入內容。",
    "details": {
      "fields": []
    }
  },
  "meta": {
    "request_id": "req_abc123"
  }
}
```
