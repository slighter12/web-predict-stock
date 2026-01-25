import pandas as pd
import pytest

from backend.backtest_service import _build_execution_price, build_weights_from_scores


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
        weighting="equal",
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
        weighting="equal",
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
        weighting="equal",
    )
    assert weights.loc[idx[0]].sum() == pytest.approx(0.0)


def test_build_weights_from_scores_invalid_weighting():
    scores = pd.DataFrame({"A": [0.01]}, index=[pd.Timestamp("2024-01-02")])
    with pytest.raises(ValueError):
        build_weights_from_scores(
            scores=scores,
            threshold=0.0,
            top_n=1,
            allow_proactive_sells=True,
            weighting="custom",
        )


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
        matching_model="ohlc_default",
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
        matching_model="ohlc_default",
    )

    assert price.loc[idx[0], "A"] == pytest.approx(100.0)
