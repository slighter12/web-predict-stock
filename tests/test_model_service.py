import pandas as pd
import pytest

from backend.model_service import compute_return_target, time_series_split


def test_compute_return_target_open_to_open():
    df = pd.DataFrame(
        {
            "open": [10.0, 12.0, 15.0],
            "close": [11.0, 13.0, 16.0],
        }
    )
    result = compute_return_target(df, "open_to_open", 1)
    assert result.iloc[0] == pytest.approx(0.2)
    assert result.iloc[1] == pytest.approx(0.25)
    assert pd.isna(result.iloc[2])


def test_compute_return_target_open_to_close():
    df = pd.DataFrame(
        {
            "open": [10.0, 12.0, 15.0],
            "close": [11.0, 13.0, 16.0],
        }
    )
    result = compute_return_target(df, "open_to_close", 1)
    assert result.iloc[0] == pytest.approx(0.1)
    assert result.iloc[1] == pytest.approx(0.0833333333)
    assert result.iloc[2] == pytest.approx(0.0666666667)


def test_compute_return_target_horizon_two():
    df = pd.DataFrame(
        {
            "open": [10.0, 12.0, 15.0],
            "close": [11.0, 13.0, 16.0],
        }
    )
    result = compute_return_target(df, "open_to_open", 2)
    assert result.iloc[0] == pytest.approx(0.5)
    assert pd.isna(result.iloc[1])


def test_compute_return_target_invalid():
    df = pd.DataFrame({"open": [10.0], "close": [11.0]})
    with pytest.raises(ValueError):
        compute_return_target(df, "bad_target", 1)


def test_time_series_split_basic():
    X = pd.DataFrame({"x": range(10)})
    y = pd.Series(range(10))
    X_train, X_test, y_train, y_test = time_series_split(X, y, test_size=0.2)
    assert len(X_train) == 8
    assert len(X_test) == 2
    assert X_test.index[0] == 8
    assert y_test.iloc[0] == 8


def test_time_series_split_invalid():
    X = pd.DataFrame({"x": range(10)})
    y = pd.Series(range(10))
    with pytest.raises(ValueError):
        time_series_split(X, y, test_size=1.0)
