import logging
from typing import TYPE_CHECKING, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error

# Use a relative import to access other modules within the same package
from backend.shared.analytics.features import add_features

if TYPE_CHECKING:
    from xgboost import XGBClassifier, XGBRegressor

logger = logging.getLogger(__name__)

MODEL_FAMILY_BY_TYPE = {
    "xgboost": "gradient_boosted_trees",
    "random_forest": "bagging_trees",
    "extra_trees": "bagging_trees",
}
TRAINING_OUTPUT_CONTRACT_VERSION = "tabular_regression_scores_v1"
DIRECTION_CALIBRATION_SUPPORT_POLICY_VERSION = (
    "chronological_tail_20pct_min20_class5_v1"
)
DIRECTION_CALIBRATION_MIN_SAMPLES = 20
DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT = 5


def _load_xgboost_regressor():
    try:
        from xgboost import XGBRegressor
    except Exception as exc:
        raise RuntimeError(
            "xgboost failed to import. On macOS, install OpenMP with `brew install libomp`."
        ) from exc
    return XGBRegressor


def _load_xgboost_classifier():
    try:
        from xgboost import XGBClassifier
    except Exception as exc:
        raise RuntimeError(
            "xgboost failed to import. On macOS, install OpenMP with `brew install libomp`."
        ) from exc
    return XGBClassifier


def _load_sklearn_regressor(model_type: str):
    try:
        from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
    except Exception as exc:
        raise RuntimeError(
            "scikit-learn failed to import. Install project dependencies before using sklearn model families."
        ) from exc
    regressor_cls = {
        "random_forest": RandomForestRegressor,
        "extra_trees": ExtraTreesRegressor,
    }.get(model_type)
    if regressor_cls is None:
        raise ValueError(f"Unsupported sklearn model type: {model_type}")
    return regressor_cls


def _load_sklearn_classifier(model_type: str):
    try:
        from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
    except Exception as exc:
        raise RuntimeError(
            "scikit-learn failed to import. Install project dependencies before using sklearn model families."
        ) from exc
    classifier_cls = {
        "random_forest": RandomForestClassifier,
        "extra_trees": ExtraTreesClassifier,
    }.get(model_type)
    if classifier_cls is None:
        raise ValueError(f"Unsupported sklearn model type: {model_type}")
    return classifier_cls


def compute_return_target(
    df: pd.DataFrame, return_target: str, horizon_days: int
) -> pd.Series:
    lookahead = target_lookahead(return_target, horizon_days)

    if return_target == "open_to_open":
        return df["open"].shift(-lookahead) / df["open"] - 1.0
    if return_target == "close_to_close":
        return df["close"].shift(-lookahead) / df["close"] - 1.0
    return df["close"].shift(-lookahead) / df["open"] - 1.0


def target_lookahead(return_target: str, horizon_days: int) -> int:
    if horizon_days < 1:
        raise ValueError("horizon_days must be >= 1")

    if return_target in {"open_to_open", "close_to_close"}:
        return horizon_days
    if return_target == "open_to_close":
        return horizon_days - 1

    raise ValueError(f"Unsupported return_target: {return_target}")


def prepare_training_data(
    df: pd.DataFrame,
    return_target: str = "open_to_open",
    horizon_days: int = 1,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    df = df.copy()
    df["target"] = compute_return_target(df, return_target, horizon_days)

    original_cols = {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "target",
        "date",
        "symbol",
        "source",
        "market",
        "raw_payload_id",
        "archive_object_reference",
        "parser_version",
        "created_at",
    }
    features = [col for col in df.columns if col not in original_cols]
    if not features:
        raise ValueError(
            "No features available for training. Ensure the feature engine added columns."
        )

    # Ignore nullable metadata columns when preparing the training frame.
    df = df.dropna(subset=[*features, "target"])

    X = df[features]
    y = df["target"]
    logger.info("Prepared training frame rows=%s features=%s", len(df), features)
    return df, X, y


def time_series_split(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
    purge: int = 0,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1.")

    if purge < 0:
        raise ValueError("purge must be >= 0.")

    split_idx = int(len(X) * (1 - test_size))
    train_end = split_idx - purge
    if train_end <= 0 or split_idx >= len(X):
        raise ValueError(
            "Not enough data to create a train/test split with "
            f"test_size={test_size} and purge={purge}."
        )

    X_train = X.iloc[:train_end]
    X_test = X.iloc[split_idx:]
    y_train = y.iloc[:train_end]
    y_test = y.iloc[split_idx:]
    logger.info("Created time-series split train=%s test=%s", len(X_train), len(X_test))
    return X_train, X_test, y_train, y_test


def fit_xgboost_regressor(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_params: Dict[str, object] = None,
):
    XGBRegressor = _load_xgboost_regressor()
    params = {
        "objective": "reg:squarederror",
        "n_estimators": 200,
        "random_state": 42,
    }
    if model_params:
        params.update(model_params)
    model = XGBRegressor(**params)
    model.fit(X_train, y_train)
    logger.info("Trained xgboost regressor rows=%s params=%s", len(X_train), params)
    return model


def fit_sklearn_regressor(
    *,
    model_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_params: Dict[str, object] | None = None,
):
    params = {
        "n_estimators": 200,
        "random_state": 42,
        "n_jobs": -1,
    }
    if model_params:
        params.update(model_params)
    regressor_cls = _load_sklearn_regressor(model_type)
    model = regressor_cls(**params)
    model.fit(X_train, y_train)
    logger.info(
        "Trained %s regressor rows=%s params=%s", model_type, len(X_train), params
    )
    return model


def fit_regressor(
    *,
    model_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_params: Dict[str, object] | None = None,
):
    if model_type == "xgboost":
        return fit_xgboost_regressor(X_train, y_train, model_params)
    if model_type in {"random_forest", "extra_trees"}:
        return fit_sklearn_regressor(
            model_type=model_type,
            X_train=X_train,
            y_train=y_train,
            model_params=model_params,
        )
    raise ValueError(f"Unsupported model type: {model_type}")


def build_classifier(
    *,
    model_type: str,
    model_params: Dict[str, object] | None = None,
):
    params: Dict[str, object] = {
        "n_estimators": 200,
        "random_state": 42,
        "n_jobs": -1,
    }
    if model_type == "xgboost":
        params.update({"objective": "binary:logistic", "eval_metric": "logloss"})
        classifier_cls = _load_xgboost_classifier()
    elif model_type in {"random_forest", "extra_trees"}:
        classifier_cls = _load_sklearn_classifier(model_type)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")
    if model_params:
        params.update(model_params)
    return classifier_cls(**params)


def fit_calibrated_direction_classifier(
    *,
    model_type: str,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model_params: Dict[str, object] | None = None,
    purge: int = 0,
) -> tuple[object | None, str | None, int]:
    from sklearn.calibration import CalibratedClassifierCV

    calibration_size = max(
        DIRECTION_CALIBRATION_MIN_SAMPLES,
        int(len(X_train) * 0.2),
    )
    calibration_start = len(X_train) - calibration_size
    base_end = calibration_start - purge
    if base_end < DIRECTION_CALIBRATION_MIN_SAMPLES:
        return (
            None,
            "Insufficient rows for provisional chronological direction calibration "
            f"({DIRECTION_CALIBRATION_SUPPORT_POLICY_VERSION}).",
            0,
        )

    base_labels = y_train.iloc[:base_end]
    calibration_labels = y_train.iloc[calibration_start:]
    if base_labels.value_counts().reindex([0, 1], fill_value=0).min() < (
        DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT
    ):
        return (
            None,
            "Provisional direction model training window requires at least "
            f"{DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT} rows per class "
            f"({DIRECTION_CALIBRATION_SUPPORT_POLICY_VERSION}).",
            0,
        )
    if calibration_labels.value_counts().reindex([0, 1], fill_value=0).min() < (
        DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT
    ):
        return (
            None,
            "Provisional direction model calibration window requires at least "
            f"{DIRECTION_CALIBRATION_MIN_CLASS_SUPPORT} rows per class "
            f"({DIRECTION_CALIBRATION_SUPPORT_POLICY_VERSION}).",
            0,
        )

    model = CalibratedClassifierCV(
        build_classifier(model_type=model_type, model_params=model_params),
        method="sigmoid",
        cv=[
            (
                np.arange(base_end),
                np.arange(calibration_start, len(X_train)),
            )
        ],
        ensemble=True,
    )
    model.fit(X_train, y_train)
    return model, None, calibration_size


def build_model_family(model_type: str) -> str:
    family = MODEL_FAMILY_BY_TYPE.get(model_type)
    if family is None:
        raise ValueError(f"Unsupported model type: {model_type}")
    return family


if __name__ == "__main__":
    # --- Example Usage ---
    # Create a sample DataFrame
    data = {
        "open": np.random.rand(100) * 10 + 100,
        "high": np.random.rand(100) * 10 + 102,
        "low": np.random.rand(100) * 10 + 98,
        "close": np.random.rand(100) * 10 + 100,
        "volume": np.random.randint(1000, 5000, 100),
    }
    sample_df = pd.DataFrame(
        data, index=pd.to_datetime(pd.date_range("2023-01-01", periods=100))
    )

    # 1. Add features
    feature_config = {"ma": [5, 10, 20], "rsi": 14}
    df_with_features = add_features(sample_df.copy(), feature_config)

    # 2. Train the model
    try:
        df_model, X, y = prepare_training_data(df_with_features)
        X_train, X_test, y_train, y_test = time_series_split(X, y)
        trained_model = fit_xgboost_regressor(X_train, y_train)
        preds = trained_model.predict(X_test)

        print("\n--- Model Training Complete ---")
        print(f"Model: {trained_model}")
        print(f"X_test shape: {X_test.shape}")
        print(f"y_test shape: {y_test.shape}")
        print(f"Test RMSE: {mean_squared_error(y_test, preds, squared=False):.6f}")
    except ValueError as e:
        print(f"Error during model training: {e}")
