import logging
from typing import Iterable, Tuple, Union

import numpy as np
import pandas as pd
import vectorbt as vbt

logger = logging.getLogger(__name__)

FEATURE_REGISTRY_VERSION = "technical_feature_registry_v1"
PRICE_SOURCE_OPTIONS = ("open", "high", "low", "close", "volume")
FEATURE_DEFINITIONS = (
    {
        "name": "ma",
        "label": "Moving Average",
        "description": "Simple moving average for baseline trend smoothing.",
        "default_window": 5,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
    },
    {
        "name": "ema",
        "label": "Exponential Moving Average",
        "description": "Faster trend-following average that reacts more quickly to recent data.",
        "default_window": 5,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
    },
    {
        "name": "rsi",
        "label": "Relative Strength Index",
        "description": "Momentum oscillator for overbought and oversold regimes.",
        "default_window": 14,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
    },
    {
        "name": "roc",
        "label": "Rate Of Change",
        "description": "Windowed percent change for momentum and breakout-style signals.",
        "default_window": 10,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
    },
    {
        "name": "volatility",
        "label": "Rolling Volatility",
        "description": "Annualized rolling standard deviation of returns for risk-sensitive models.",
        "default_window": 20,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
    },
    {
        "name": "zscore",
        "label": "Rolling Z-Score",
        "description": "Normalized distance from the rolling mean for mean-reversion style features.",
        "default_window": 20,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
    },
)
FEATURE_DEFINITION_BY_NAME = {
    feature["name"]: feature for feature in FEATURE_DEFINITIONS
}


def list_feature_definitions() -> list[dict[str, object]]:
    return [
        {**feature, "allowed_sources": list(feature["allowed_sources"])}
        for feature in FEATURE_DEFINITIONS
    ]


def get_feature_definition(name: str) -> dict[str, object] | None:
    feature = FEATURE_DEFINITION_BY_NAME.get(name)
    if feature is None:
        return None
    return {**feature, "allowed_sources": list(feature["allowed_sources"])}


def _returns(series: pd.Series) -> pd.Series:
    return series.pct_change().replace([np.inf, -np.inf], np.nan)


def _add_trend_feature(
    df: pd.DataFrame,
    *,
    indicator_name: str,
    window: int,
    source: str,
) -> None:
    series = df[source]
    if indicator_name == "MA":
        feature = vbt.MA.run(series, window=window, short_name=f"ma_{window}").ma
    else:
        feature = series.ewm(span=window, adjust=False, min_periods=window).mean()
    df[feature_col_name(indicator_name, window, source)] = feature


def _add_return_feature(
    df: pd.DataFrame,
    *,
    indicator_name: str,
    window: int,
    source: str,
) -> None:
    series = df[source]
    returns = _returns(series)

    if indicator_name == "ROC":
        feature = series.pct_change(periods=window).replace([np.inf, -np.inf], np.nan)
    elif indicator_name == "VOLATILITY":
        feature = returns.rolling(window=window, min_periods=window).std() * np.sqrt(252)
    else:
        rolling_mean = series.rolling(window=window, min_periods=window).mean()
        rolling_std = series.rolling(window=window, min_periods=window).std()
        feature = (series - rolling_mean) / rolling_std.mask(rolling_std == 0)

    df[feature_col_name(indicator_name, window, source)] = feature


def feature_col_name(name: str, window: int, source: str) -> str:
    suffix = "" if source == "close" else f"_{source}"
    return f"{name.upper()}_{window}{suffix}"


def _normalize_window_config(
    config_value: Union[int, Iterable[Union[int, dict]]],
    default_source: str = "close",
) -> list[Tuple[int, str]]:
    items: list[Tuple[int, str]] = []
    if isinstance(config_value, int):
        return [(config_value, default_source)]

    for entry in config_value:
        if isinstance(entry, dict):
            window = int(entry.get("window", 0))
            source = entry.get("source", default_source)
        else:
            window = int(entry)
            source = default_source
        if window <= 0:
            continue
        items.append((window, source))
    return items


def add_features(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Adds technical indicator features to an OHLCV DataFrame based on a configuration.

    Args:
        df (pd.DataFrame): DataFrame with 'open', 'high', 'low', 'close', 'volume' columns.
                           The index should be a DatetimeIndex.
        config (dict): A dictionary specifying the features to add.
                       Example: {'ma': [5, 20], 'rsi': 14}

    Returns:
        pd.DataFrame: The original DataFrame with added feature columns.
    """
    # Ensure the index is a DatetimeIndex for vbt compatibility
    if not isinstance(df.index, pd.DatetimeIndex):
        # Assuming the index is a date object, convert it
        df.index = pd.to_datetime(df.index)

    # Calculate Moving Averages (MA)
    if "ma" in config and config["ma"]:
        for window, source in _normalize_window_config(config["ma"]):
            try:
                _add_trend_feature(
                    df,
                    indicator_name="MA",
                    window=window,
                    source=source,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to calculate MA window=%s source=%s",
                    window,
                    source,
                )
                raise ValueError(
                    f"Could not calculate MA for window {window} on source '{source}'."
                ) from exc

    # Calculate Exponential Moving Average (EMA)
    if "ema" in config and config["ema"]:
        for window, source in _normalize_window_config(config["ema"]):
            try:
                _add_trend_feature(
                    df,
                    indicator_name="EMA",
                    window=window,
                    source=source,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to calculate EMA window=%s source=%s",
                    window,
                    source,
                )
                raise ValueError(
                    f"Could not calculate EMA for window {window} on source '{source}'."
                ) from exc

    # Calculate Relative Strength Index (RSI)
    if "rsi" in config and config["rsi"]:
        for window, source in _normalize_window_config(config["rsi"]):
            try:
                series = df[source]
                rsi = vbt.RSI.run(series, window=window, short_name=f"rsi_{window}")
                df[feature_col_name("RSI", window, source)] = rsi.rsi
            except Exception as exc:
                logger.exception(
                    "Failed to calculate RSI window=%s source=%s",
                    window,
                    source,
                )
                raise ValueError(
                    f"Could not calculate RSI for window {window} on source '{source}'."
                ) from exc

    # Calculate Rate of Change (ROC)
    if "roc" in config and config["roc"]:
        for window, source in _normalize_window_config(config["roc"]):
            try:
                _add_return_feature(
                    df,
                    indicator_name="ROC",
                    window=window,
                    source=source,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to calculate ROC window=%s source=%s",
                    window,
                    source,
                )
                raise ValueError(
                    f"Could not calculate ROC for window {window} on source '{source}'."
                ) from exc

    # Calculate rolling annualized volatility
    if "volatility" in config and config["volatility"]:
        for window, source in _normalize_window_config(config["volatility"]):
            try:
                _add_return_feature(
                    df,
                    indicator_name="VOLATILITY",
                    window=window,
                    source=source,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to calculate volatility window=%s source=%s",
                    window,
                    source,
                )
                raise ValueError(
                    "Could not calculate volatility "
                    f"for window {window} on source '{source}'."
                ) from exc

    # Calculate rolling z-score for mean-reversion style features
    if "zscore" in config and config["zscore"]:
        for window, source in _normalize_window_config(config["zscore"]):
            try:
                _add_return_feature(
                    df,
                    indicator_name="ZSCORE",
                    window=window,
                    source=source,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to calculate zscore window=%s source=%s",
                    window,
                    source,
                )
                raise ValueError(
                    f"Could not calculate zscore for window {window} on source '{source}'."
                ) from exc

    return df


if __name__ == "__main__":
    # --- Example Usage ---
    # Create a sample DataFrame
    data = {
        "open": [100, 102, 101, 103, 105, 104, 106, 108, 107, 109],
        "high": [103, 104, 103, 105, 106, 106, 109, 110, 109, 111],
        "low": [99, 101, 100, 102, 104, 103, 105, 107, 106, 108],
        "close": [102, 103, 102, 104, 105, 105, 108, 109, 108, 110],
        "volume": [1000, 1500, 1200, 1800, 2000, 1700, 2200, 2500, 2300, 2800],
    }
    sample_df = pd.DataFrame(
        data, index=pd.to_datetime(pd.date_range("2023-01-01", periods=10))
    )

    # Define the feature configuration
    feature_config = {"ma": [3, 5], "rsi": 4}

    # Add features to the DataFrame
    df_with_features = add_features(sample_df.copy(), feature_config)

    print("--- Original DataFrame ---")
    print(sample_df)
    print("\n--- DataFrame with Features ---")
    print(df_with_features)
