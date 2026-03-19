import pandas as pd

from backend.baseline_service import (
    buy_and_hold_weights,
    ma_crossover_weights,
    naive_momentum_weights,
)


def test_buy_and_hold_weights_shape():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    close_df = pd.DataFrame({"A": [10.0, 11.0], "B": [20.0, 21.0]}, index=idx)

    weights = buy_and_hold_weights(close_df)

    assert weights.shape == close_df.shape
    assert (weights.sum(axis=1) == 1.0).all()


def test_naive_momentum_weights_shifted_signal():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    close_df = pd.DataFrame({"A": [10.0, 11.0, 12.0]}, index=idx)

    weights = naive_momentum_weights(close_df)

    assert weights.iloc[0, 0] == 0.0
    assert weights.iloc[1, 0] == 0.0
    assert weights.iloc[2, 0] == 1.0


def test_ma_crossover_weights_shape():
    idx = pd.date_range("2024-01-01", periods=30)
    close_df = pd.DataFrame({"A": range(30), "B": range(30, 60)}, index=idx)

    weights = ma_crossover_weights(close_df, short_window=3, long_window=5)

    assert weights.shape == close_df.shape
