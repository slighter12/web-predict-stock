import numpy as np
import pandas as pd
import pytest

import backend.shared.analytics.models as model_service

from backend.shared.analytics.models import (
    build_classifier,
    compute_return_target,
    fit_calibrated_direction_classifier,
    fit_regressor,
    prepare_training_data,
    target_lookahead,
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


@pytest.mark.parametrize(
    ("return_target", "horizon_days", "expected"),
    [
        ("open_to_open", 5, 5),
        ("close_to_close", 5, 5),
        ("open_to_close", 5, 4),
        ("open_to_close", 1, 0),
    ],
)
def test_target_lookahead_matches_target_window(
    return_target, horizon_days, expected
):
    assert target_lookahead(return_target, horizon_days) == expected


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


def test_time_series_split_purges_overlapping_training_targets():
    X = pd.DataFrame({"x": range(10)})
    y = pd.Series(range(10))

    X_train, X_test, y_train, _ = time_series_split(
        X, y, test_size=0.2, purge=2
    )

    assert list(X_train.index) == list(range(6))
    assert list(y_train.index) == list(range(6))
    assert list(X_test.index) == [8, 9]


def test_direction_calibration_uses_chronological_tail_and_purge():
    X = pd.DataFrame({"x": range(100)})
    y = pd.Series([0, 1] * 50)

    model, reason, calibration_size = fit_calibrated_direction_classifier(
        model_type="extra_trees",
        X_train=X,
        y_train=y,
        model_params={"n_estimators": 5},
        purge=2,
    )

    train_indices, calibration_indices = model.cv[0]
    assert reason is None
    assert calibration_size == 20
    assert list(train_indices) == list(range(78))
    assert list(calibration_indices) == list(range(80, 100))
    assert model.predict_proba(X.tail(1)).shape == (1, 2)


@pytest.mark.parametrize("model_type", ["random_forest", "extra_trees"])
def test_build_classifier_supports_regression_model_families(model_type):
    model = build_classifier(model_type=model_type, model_params={"n_estimators": 5})

    assert model.get_params()["n_estimators"] == 5


def test_build_classifier_supports_xgboost_without_loading_native_runtime(monkeypatch):
    class _Classifier:
        def __init__(self, **params):
            self.params = params

        def get_params(self):
            return self.params

    monkeypatch.setattr(
        model_service, "_load_xgboost_classifier", lambda: _Classifier
    )

    model = build_classifier(model_type="xgboost", model_params={"n_estimators": 5})

    assert model.get_params()["n_estimators"] == 5


def test_direction_calibration_requires_both_classes_in_calibration_tail():
    X = pd.DataFrame({"x": range(100)})
    y = pd.Series([0, 1] * 40 + [0] * 4 + [1] * 16)

    model, reason, calibration_size = fit_calibrated_direction_classifier(
        model_type="random_forest",
        X_train=X,
        y_train=y,
        model_params={"n_estimators": 5},
    )

    assert model is None
    assert reason == (
        "Provisional direction model calibration window requires at least 5 rows "
        "per class (chronological_tail_20pct_min20_class5_v1)."
    )
    assert calibration_size == 0


def test_direction_calibration_requires_enough_rows_for_provisional_gate():
    X = pd.DataFrame({"x": range(39)})
    y = pd.Series([0, 1] * 19 + [0])

    model, reason, calibration_size = fit_calibrated_direction_classifier(
        model_type="random_forest",
        X_train=X,
        y_train=y,
        model_params={"n_estimators": 5},
    )

    assert model is None
    assert reason == (
        "Insufficient rows for provisional chronological direction calibration "
        "(chronological_tail_20pct_min20_class5_v1)."
    )
    assert calibration_size == 0


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


def test_prepare_training_data_excludes_non_finite_features_and_targets():
    df = pd.DataFrame(
        {
            "open": [10.0, 11.0, 12.0, 0.0, 14.0, 15.0],
            "high": [11.0, 12.0, 13.0, 1.0, 15.0, 16.0],
            "low": [9.0, 10.0, 11.0, 0.0, 13.0, 14.0],
            "close": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
            "volume": [100] * 6,
            "feature_a": [1.0, np.inf, 3.0, 4.0, -np.inf, 6.0],
        }
    )

    df_model, X, y = prepare_training_data(df, return_target="open_to_open")

    assert list(df_model.index) == [0, 2]
    assert np.isfinite(X.to_numpy()).all()
    assert np.isfinite(y.to_numpy()).all()


@pytest.mark.parametrize("model_type", ["xgboost", "random_forest", "extra_trees"])
def test_model_families_share_complete_case_inputs(monkeypatch, model_type):
    class _Regressor:
        def __init__(self, **params):
            self.params = params

        def fit(self, X, y):
            assert np.isfinite(X.to_numpy()).all()
            assert np.isfinite(y.to_numpy()).all()
            return self

        def predict(self, X):
            return [0.0] * len(X)

    monkeypatch.setattr(model_service, "_load_xgboost_regressor", lambda: _Regressor)
    rows = 30
    df = pd.DataFrame(
        {
            "open": [float(value) for value in range(100, 100 + rows)],
            "high": [float(value) for value in range(101, 101 + rows)],
            "low": [float(value) for value in range(99, 99 + rows)],
            "close": [float(value) for value in range(100, 100 + rows)],
            "volume": [1_000] * rows,
            "feature_a": [None, *[float(value) for value in range(1, rows)]],
            "feature_b": [
                *[float(value) for value in range(rows - 2)],
                None,
                float(rows - 1),
            ],
        }
    )

    _, X, y = prepare_training_data(df)
    model = fit_regressor(
        model_type=model_type,
        X_train=X,
        y_train=y,
        model_params={"n_estimators": 5},
    )

    assert np.isfinite(X.to_numpy()).all()
    assert np.isfinite(y.to_numpy()).all()
    assert len(model.predict(X.tail(2))) == 2


def test_direction_classifier_receives_complete_case_inputs():
    rows = 120
    df = pd.DataFrame(
        {
            "open": [float(value) for value in range(100, 100 + rows)],
            "high": [float(value) for value in range(101, 101 + rows)],
            "low": [float(value) for value in range(99, 99 + rows)],
            "close": [float(value) for value in range(100, 100 + rows)],
            "volume": [1_000] * rows,
            "feature_a": [None, *[float(value) for value in range(1, rows)]],
            "feature_b": [
                *[float(value) for value in range(rows - 2)],
                None,
                float(rows - 1),
            ],
        }
    )

    _, X, _ = prepare_training_data(df)
    direction_target = pd.Series(
        [index % 2 for index in range(len(X))],
        index=X.index,
    )
    classifier, reason, _ = fit_calibrated_direction_classifier(
        model_type="extra_trees",
        X_train=X,
        y_train=direction_target,
        model_params={"n_estimators": 5},
    )

    assert reason is None
    assert classifier is not None
    assert np.isfinite(X.to_numpy()).all()
    assert classifier.predict_proba(X.tail(2)).shape == (2, 2)
