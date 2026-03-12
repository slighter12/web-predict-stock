import logging
from dataclasses import dataclass
from math import sqrt
from typing import Dict, List, Literal, Tuple

import numpy as np
import pandas as pd
import vectorbt as vbt

from .strategy_service import get_strategy_runner, resolve_strategy_config

Side = Literal["buy", "sell"]
DEFAULT_MATCHING_MODEL = "ohlc_default"
logger = logging.getLogger(__name__)


@dataclass
class MarketConfig:
    market: str
    slippage: float


def match_price(
    side: Side,
    ohlc: Dict[str, float],
    config: MarketConfig,
    model: str = "ohlc_default",
) -> float:
    if model != "ohlc_default":
        raise ValueError(f"Unknown matching model: {model}")

    market = config.market.upper()
    open_price = ohlc["open"]
    close_price = ohlc["close"]
    high = ohlc["high"]
    low = ohlc["low"]

    if market == "US":
        if side == "buy":
            return max(open_price, close_price)
        return min(open_price, high)

    # Default to TW behavior
    if side == "buy":
        return max(open_price, low)
    return min(open_price, high)


def build_signals(scores: pd.DataFrame, weights: pd.DataFrame) -> List[dict]:
    signals: List[dict] = []
    for dt, row in weights.iterrows():
        active = row[row > 0]
        if active.empty:
            continue
        for symbol, position in active.items():
            score = scores.at[dt, symbol]
            signals.append(
                {
                    "date": dt.date() if hasattr(dt, "date") else dt,
                    "symbol": symbol,
                    "score": float(score) if pd.notna(score) else 0.0,
                    "position": float(position),
                }
            )
    return signals


def compute_turnover(weights: pd.DataFrame) -> float:
    if weights.empty:
        return 0.0
    turnover = weights.diff().abs().sum(axis=1).fillna(0).mean() / 2.0
    return float(turnover)


def compute_metrics(equity: pd.Series) -> Dict[str, float]:
    if equity.empty:
        return {"total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}

    returns = equity.pct_change().dropna()
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    max_drawdown = (equity / equity.cummax() - 1.0).min()

    if returns.std() == 0 or np.isnan(returns.std()):
        sharpe = 0.0
    else:
        sharpe = (returns.mean() / returns.std()) * sqrt(252)

    return {
        "total_return": float(total_return),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_drawdown),
    }


def build_equity_curve(equity: pd.Series) -> List[dict]:
    curve: List[dict] = []
    for dt, value in equity.items():
        curve.append(
            {
                "date": dt.date() if hasattr(dt, "date") else dt,
                "equity": float(value),
            }
        )
    return curve


def validate_execution_prices(
    open_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    close_df: pd.DataFrame,
    weights: pd.DataFrame,
    execution_price: pd.DataFrame,
    market: str,
    matching_model: str = DEFAULT_MATCHING_MODEL,
) -> List[str]:
    warnings: List[str] = []

    if open_df.empty or weights.empty:
        return warnings

    # Basic OHLC sanity check
    ohlc_out_of_range = (open_df < low_df) | (open_df > high_df)
    if ohlc_out_of_range.any().any():
        warnings.append("OHLC data contains open prices outside low/high bounds.")

    # Check matching model constraints for buy orders.
    changes = weights.diff().fillna(weights)
    buys = changes > 0
    if matching_model == DEFAULT_MATCHING_MODEL and market.upper() == "US":
        violations = (execution_price < close_df) & buys
        count = int(violations.sum().sum())
        if count:
            warnings.append(f"{count} US buy executions below close; matching model expects buy >= close.")

    return warnings


def _select_close(
    open_df: pd.DataFrame,
    close_df: pd.DataFrame,
    return_target: str,
) -> pd.DataFrame:
    if return_target in {"close_to_close", "open_to_close"}:
        return close_df
    return open_df


def _build_execution_price(
    weights: pd.DataFrame,
    open_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    close_df: pd.DataFrame,
    market: str,
    matching_model: str = DEFAULT_MATCHING_MODEL,
) -> pd.DataFrame:
    if matching_model != DEFAULT_MATCHING_MODEL:
        raise ValueError(f"Unknown matching model: {matching_model}")

    changes = weights.diff().fillna(weights)
    buys = changes > 0
    sells = changes < 0

    if market.upper() == "US":
        buy_price = pd.DataFrame(
            np.maximum(open_df.values, close_df.values),
            index=open_df.index,
            columns=open_df.columns,
        )
        sell_price = pd.DataFrame(
            np.minimum(open_df.values, high_df.values),
            index=open_df.index,
            columns=open_df.columns,
        )
    else:
        buy_price = pd.DataFrame(
            np.maximum(open_df.values, low_df.values),
            index=open_df.index,
            columns=open_df.columns,
        )
        sell_price = pd.DataFrame(
            np.minimum(open_df.values, high_df.values),
            index=open_df.index,
            columns=open_df.columns,
        )

    price = open_df.copy()
    price = price.where(~buys, buy_price)
    price = price.where(~sells, sell_price)
    return price


def run_backtest_from_weights(
    weights: pd.DataFrame,
    open_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    close_df: pd.DataFrame,
    execution: object,
    market: str,
    return_target: str,
) -> Tuple[Dict[str, float], List[dict]]:
    if weights.empty:
        return {"total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "turnover": 0.0}, []

    close = _select_close(
        open_df=open_df.reindex(weights.index).ffill(),
        close_df=close_df.reindex(weights.index).ffill(),
        return_target=return_target,
    )
    price = _build_execution_price(
        weights=weights,
        open_df=open_df.reindex(weights.index).ffill(),
        high_df=high_df.reindex(weights.index).ffill(),
        low_df=low_df.reindex(weights.index).ffill(),
        close_df=close_df.reindex(weights.index).ffill(),
        market=market,
        matching_model=DEFAULT_MATCHING_MODEL,
    )

    pf = vbt.Portfolio.from_orders(
        close=close,
        size=weights,
        size_type="targetpercent",
        price=price,
        fees=execution.fees,
        slippage=execution.slippage,
        init_cash=1.0,
        cash_sharing=True,
        freq="D",
    )

    equity = pf.value()
    if isinstance(equity, pd.DataFrame):
        equity = equity.sum(axis=1)
    metrics = compute_metrics(equity)
    metrics["turnover"] = compute_turnover(weights)
    return metrics, build_equity_curve(equity)


def run_backtest(
    scores: pd.DataFrame,
    open_df: pd.DataFrame,
    high_df: pd.DataFrame,
    low_df: pd.DataFrame,
    close_df: pd.DataFrame,
    strategy: object,
    execution: object,
    market: str,
    return_target: str,
) -> Tuple[Dict[str, float], List[dict], List[dict], List[str]]:
    warnings: List[str] = []
    strategy_config = resolve_strategy_config(strategy)
    runner = get_strategy_runner(strategy_config.type)
    weights = runner.build_weights(scores=scores, strategy=strategy_config)

    weights = weights.reindex(scores.index).fillna(0.0)
    weights = weights.sort_index()
    logger.info(
        "Running backtest strategy=%s market=%s symbols=%s periods=%s",
        strategy_config.type,
        market,
        list(scores.columns),
        len(scores.index),
    )

    metrics, equity_curve = run_backtest_from_weights(
        weights=weights,
        open_df=open_df,
        high_df=high_df,
        low_df=low_df,
        close_df=close_df,
        execution=execution,
        market=market,
        return_target=return_target,
    )
    signals = build_signals(scores, weights)

    execution_price = _build_execution_price(
        weights=weights,
        open_df=open_df.reindex(weights.index).ffill(),
        high_df=high_df.reindex(weights.index).ffill(),
        low_df=low_df.reindex(weights.index).ffill(),
        close_df=close_df.reindex(weights.index).ffill(),
        market=market,
        matching_model=DEFAULT_MATCHING_MODEL,
    )

    warnings.extend(
        validate_execution_prices(
            open_df=open_df,
            high_df=high_df,
            low_df=low_df,
            close_df=close_df,
            weights=weights,
            execution_price=execution_price,
            market=market,
            matching_model=DEFAULT_MATCHING_MODEL,
        )
    )

    return metrics, equity_curve, signals, warnings
