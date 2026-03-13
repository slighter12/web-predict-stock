import logging
from typing import TYPE_CHECKING, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import mean_squared_error

# Use a relative import to access other modules within the same package
from .feature_engine import add_features

if TYPE_CHECKING:
    from xgboost import XGBRegressor

logger = logging.getLogger(__name__)


def _load_xgboost_regressor():
    try:
        from xgboost import XGBRegressor
    except Exception as exc:
        raise RuntimeError(
            "xgboost failed to import. On macOS, install OpenMP with `brew install libomp`."
        ) from exc
    return XGBRegressor


def compute_return_target(
    df: pd.DataFrame, return_target: str, horizon_days: int
) -> pd.Series:
    if horizon_days < 1:
        raise ValueError("horizon_days must be >= 1")

    if return_target == "open_to_open":
        return df["open"].shift(-horizon_days) / df["open"] - 1.0
    if return_target == "close_to_close":
        return df["close"].shift(-horizon_days) / df["close"] - 1.0
    if return_target == "open_to_close":
        shift = -(horizon_days - 1)
        return df["close"].shift(shift) / df["open"] - 1.0

    raise ValueError(f"Unsupported return_target: {return_target}")


def prepare_training_data(
    df: pd.DataFrame,
    return_target: str = "open_to_open",
    horizon_days: int = 1,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    df = df.copy()
    df["target"] = compute_return_target(df, return_target, horizon_days)
    df = df.dropna()

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
        "created_at",
    }
    features = [col for col in df.columns if col not in original_cols]
    if not features:
        raise ValueError("No features available for training. Ensure the feature engine added columns.")

    X = df[features]
    y = df["target"]
    logger.info("Prepared training frame rows=%s features=%s", len(df), features)
    return df, X, y


def time_series_split(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.2,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1.")

    split_idx = int(len(X) * (1 - test_size))
    if split_idx <= 0 or split_idx >= len(X):
        raise ValueError(f"Not enough data to create a train/test split with test_size={test_size}.")

    X_train = X.iloc[:split_idx]
    X_test = X.iloc[split_idx:]
    y_train = y.iloc[:split_idx]
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
