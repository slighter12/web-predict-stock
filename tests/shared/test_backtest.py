import pandas as pd
import pytest

from backend.research.contracts.runs import ExecutionConfig, SignalPoint, StrategyConfig
from backend.shared.analytics.backtest import (
    _build_execution_price,
    build_signals,
    compute_max_position_weight,
    compute_metrics,
    compute_turnover,
    run_backtest,
)
from backend.shared.analytics.strategy import build_weights_from_scores


def test_build_signals_preserves_latest_flat_decision_surface():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    scores = pd.DataFrame(
        {
            "A": [0.8, 0.2],
            "B": [float("nan"), 0.1],
            "C": [0.5, float("nan")],
        },
        index=idx,
    )
    weights = pd.DataFrame(
        {"A": [1.0, 0.0], "B": [0.0, 0.0], "C": [0.0, 0.4]}, index=idx
    )

    signals = build_signals(scores, weights)

    assert [
        (item["date"], item["symbol"], item["score"], item["position"])
        for item in signals
    ] == [
        (idx[0].date(), "A", 0.8, 1.0),
        (idx[1].date(), "A", 0.2, 0.0),
        (idx[1].date(), "B", 0.1, 0.0),
        (idx[1].date(), "C", None, 0.4),
    ]
    assert SignalPoint.model_validate(signals[-1]).score is None


def test_build_weights_from_scores_proactive():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    scores = pd.DataFrame(
        {
            "A": [0.01, 0.0],
            "B": [0.005, 0.006],
            "C": [0.0, 0.007],
        },
        index=idx,
    )

    weights = build_weights_from_scores(
        scores=scores,
        threshold=0.005,
        top_n=2,
        allow_proactive_sells=True,
    )

    assert weights.loc[idx[0], "A"] == pytest.approx(0.5)
    assert weights.loc[idx[0], "B"] == pytest.approx(0.5)
    assert weights.loc[idx[1], "B"] == pytest.approx(0.5)
    assert weights.loc[idx[1], "C"] == pytest.approx(0.5)


def test_build_weights_from_scores_hold():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    scores = pd.DataFrame(
        {
            "A": [0.01, 0.0],
            "B": [0.005, 0.006],
            "C": [0.0, 0.007],
        },
        index=idx,
    )

    weights = build_weights_from_scores(
        scores=scores,
        threshold=0.005,
        top_n=2,
        allow_proactive_sells=False,
    )

    assert weights.loc[idx[0]].sum() == pytest.approx(1.0)
    assert weights.loc[idx[1]].sum() == pytest.approx(1.0)
    assert weights.loc[idx[1], "A"] == pytest.approx(1.0 / 3.0)


def test_build_weights_from_scores_empty():
    idx = pd.to_datetime(["2024-01-02"])
    scores = pd.DataFrame({"A": [0.001], "B": [0.002]}, index=idx)
    weights = build_weights_from_scores(
        scores=scores,
        threshold=0.01,
        top_n=2,
        allow_proactive_sells=True,
    )
    assert weights.loc[idx[0]].sum() == pytest.approx(0.0)


def test_build_weights_from_scores_requires_direction_confirmation():
    idx = pd.to_datetime(["2024-01-02"])
    scores = pd.DataFrame(
        {"A": [0.02], "B": [0.01], "C": [float("inf")], "D": [0.03]},
        index=idx,
    )
    probabilities = pd.DataFrame(
        {"A": [0.4], "B": [0.8], "C": [0.8], "D": [float("inf")]},
        index=idx,
    )

    weights = build_weights_from_scores(
        scores=scores,
        threshold=0.005,
        top_n=2,
        allow_proactive_sells=True,
        confirmation_probabilities=probabilities,
        confirmation_threshold=0.5,
    )

    assert weights.loc[idx[0], "A"] == 0.0
    assert weights.loc[idx[0], "B"] == 1.0
    assert weights.loc[idx[0], "C"] == 0.0
    assert weights.loc[idx[0], "D"] == 0.0


def test_run_backtest_with_unavailable_confirmation_stays_flat_and_finite():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    scores = pd.DataFrame({"A": [0.02, 0.03]}, index=idx)
    probabilities = pd.DataFrame({"A": [float("nan"), float("nan")]}, index=idx)
    open_df = pd.DataFrame({"A": [100.0, 101.0]}, index=idx)
    high_df = pd.DataFrame({"A": [102.0, 103.0]}, index=idx)
    low_df = pd.DataFrame({"A": [99.0, 100.0]}, index=idx)
    close_df = pd.DataFrame({"A": [101.0, 102.0]}, index=idx)

    metrics, _, signals, _ = run_backtest(
        scores=scores,
        open_df=open_df,
        high_df=high_df,
        low_df=low_df,
        close_df=close_df,
        strategy=StrategyConfig(
            type="research_v1",
            threshold=0.005,
            top_n=1,
            allow_proactive_sells=True,
        ),
        execution=ExecutionConfig(),
        market="TW",
        return_target="open_to_open",
        confirmation_probabilities=probabilities,
    )

    assert metrics == {
        "total_return": 0.0,
        "sharpe": 0.0,
        "max_drawdown": 0.0,
        "turnover": 0.0,
        "max_position_weight": 0.0,
    }
    assert all(signal["position"] == 0.0 for signal in signals)


def test_build_execution_price_us_buy():
    idx = pd.to_datetime(["2024-01-02"])
    weights = pd.DataFrame({"A": [1.0]}, index=idx)

    open_df = pd.DataFrame({"A": [100.0]}, index=idx)
    high_df = pd.DataFrame({"A": [110.0]}, index=idx)
    low_df = pd.DataFrame({"A": [95.0]}, index=idx)
    close_df = pd.DataFrame({"A": [105.0]}, index=idx)

    price = _build_execution_price(
        weights=weights,
        open_df=open_df,
        high_df=high_df,
        low_df=low_df,
        close_df=close_df,
        market="US",
    )

    assert price.loc[idx[0], "A"] == pytest.approx(105.0)


def test_build_execution_price_tw_buy():
    idx = pd.to_datetime(["2024-01-02"])
    weights = pd.DataFrame({"A": [1.0]}, index=idx)

    open_df = pd.DataFrame({"A": [100.0]}, index=idx)
    high_df = pd.DataFrame({"A": [110.0]}, index=idx)
    low_df = pd.DataFrame({"A": [95.0]}, index=idx)
    close_df = pd.DataFrame({"A": [105.0]}, index=idx)

    price = _build_execution_price(
        weights=weights,
        open_df=open_df,
        high_df=high_df,
        low_df=low_df,
        close_df=close_df,
        market="TW",
    )

    assert price.loc[idx[0], "A"] == pytest.approx(100.0)


def test_compute_turnover_boundary():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    weights = pd.DataFrame({"A": [0.0, 1.0], "B": [1.0, 0.0]}, index=idx)
    assert compute_turnover(weights) == pytest.approx(0.5)


def test_compute_metrics_empty_equity():
    metrics = compute_metrics(pd.Series(dtype=float))
    assert metrics == {"total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}


def test_compute_max_position_weight():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    weights = pd.DataFrame({"A": [0.2, 0.7], "B": [0.8, 0.3]}, index=idx)

    assert compute_max_position_weight(weights) == pytest.approx(0.8)
