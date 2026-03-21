import pandas as pd
import pytest

from backend.model_service import (
    compute_return_target,
    prepare_training_data,
    time_series_split,
)


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


def test_prepare_training_data_ignores_nullable_metadata_columns():
    df = pd.DataFrame(
        {
            "open": [10.0, 11.0, 12.0, 13.0],
            "high": [10.5, 11.5, 12.5, 13.5],
            "low": [9.5, 10.5, 11.5, 12.5],
            "close": [10.2, 11.2, 12.2, 13.2],
            "volume": [100, 110, 120, 130],
            "raw_payload_id": [None, None, None, None],
            "archive_object_reference": [None, None, None, None],
            "parser_version": [None, None, None, None],
            "created_at": pd.to_datetime(
                [
                    "2026-01-01T00:00:00Z",
                    "2026-01-02T00:00:00Z",
                    "2026-01-03T00:00:00Z",
                    "2026-01-04T00:00:00Z",
                ]
            ),
            "MA_2": [None, 10.7, 11.7, 12.7],
        }
    )

    df_model, X, y = prepare_training_data(df, return_target="open_to_open")

    assert len(df_model) == 2
    assert list(X.columns) == ["MA_2"]
    assert not y.isna().any()
