from dataclasses import dataclass
from math import sqrt
from typing import Dict, Iterable, List, Literal, Tuple

import numpy as np
import pandas as pd
import vectorbt as vbt

Side = Literal["buy", "sell"]


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


def build_weights_from_scores(
    scores: pd.DataFrame,
    threshold: float,
    top_n: int,
    allow_proactive_sells: bool,
    weighting: str,
) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    current_holdings: set[str] = set()

    for idx, row in scores.iterrows():
        row = row.dropna()
        eligible = row[row >= threshold]
        selected = eligible.nlargest(top_n).index.tolist()

        if allow_proactive_sells:
            holdings = selected
        else:
            current_holdings.update(selected)
            holdings = sorted(current_holdings)

        if not holdings:
            continue

        if weighting != "equal":
            raise ValueError(f"Unsupported weighting method: {weighting}")

        weight = 1.0 / len(holdings)
        weights.loc[idx, holdings] = weight

    return weights


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
    matching_model: str,
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
    if matching_model == "ohlc_default" and market.upper() == "US":
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
    matching_model: str,
) -> pd.DataFrame:
    if matching_model != "ohlc_default":
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
        matching_model=execution.matching_model,
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
    selection: object,
    trading_rules: object,
    exit_rules: object,
    execution: object,
    market: str,
    return_target: str,
) -> Tuple[Dict[str, float], List[dict], List[dict], List[str]]:
    warnings: List[str] = []

    if selection.threshold_metric != "predicted_return":
        warnings.append("threshold_metric is not supported; using predicted_return.")

    if trading_rules.rebalance != "daily_open":
        warnings.append("Only daily_open rebalance is supported; using daily_open.")

    if trading_rules.allow_intraday:
        warnings.append("Intraday trading is not supported; ignoring allow_intraday.")

    if not trading_rules.allow_same_day_reinvest:
        warnings.append("allow_same_day_reinvest is not supported; proceeds are reinvested daily.")

    if trading_rules.allow_leverage:
        warnings.append("Leverage is not supported; weights are capped to fully invested long-only.")

    if exit_rules.default_liquidation != "next_open":
        warnings.append("Only next_open liquidation is supported; using next_open.")

    if execution.matching_model != "ohlc_default":
        warnings.append("Only ohlc_default matching model is supported; using ohlc_default.")

    weights = build_weights_from_scores(
        scores=scores,
        threshold=selection.threshold,
        top_n=selection.top_n,
        allow_proactive_sells=exit_rules.allow_proactive_sells,
        weighting=selection.weighting,
    )

    weights = weights.reindex(scores.index).fillna(0.0)
    weights = weights.sort_index()

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
        matching_model=execution.matching_model,
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
            matching_model=execution.matching_model,
        )
    )

    return metrics, equity_curve, signals, warnings
