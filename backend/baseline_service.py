from typing import Dict

import pandas as pd
import vectorbt as vbt


def buy_and_hold_weights(close_df: pd.DataFrame) -> pd.DataFrame:
    if close_df.empty:
        return close_df
    symbols = close_df.columns
    weights = pd.DataFrame(1.0 / len(symbols), index=close_df.index, columns=symbols)
    return weights


def naive_momentum_weights(close_df: pd.DataFrame, lookback: int = 1) -> pd.DataFrame:
    if close_df.empty:
        return close_df
    returns = close_df.pct_change(lookback)
    signal = returns.shift(1) > 0
    weights = signal.astype(float)
    counts = weights.sum(axis=1).replace(0, 1)
    weights = weights.div(counts, axis=0)
    return weights


def ma_crossover_weights(
    close_df: pd.DataFrame,
    short_window: int = 5,
    long_window: int = 20,
) -> pd.DataFrame:
    if close_df.empty:
        return close_df

    short_ma = vbt.MA.run(close_df, window=short_window).ma
    long_ma = vbt.MA.run(close_df, window=long_window).ma
    signal = (short_ma > long_ma).shift(1)

    weights = signal.astype(float)
    counts = weights.sum(axis=1).replace(0, 1)
    weights = weights.div(counts, axis=0)
    return weights


BASELINE_BUILDERS: Dict[str, callable] = {
    "buy_and_hold": buy_and_hold_weights,
    "naive_momentum": naive_momentum_weights,
    "ma_crossover": ma_crossover_weights,
}
