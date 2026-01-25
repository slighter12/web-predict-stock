from typing import Iterable, Tuple, Union

import pandas as pd
import vectorbt as vbt


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
                series = df[source]
                ma = vbt.MA.run(series, window=window, short_name=f"ma_{window}")
                df[feature_col_name("MA", window, source)] = ma.ma
            except Exception as e:
                print(f"Could not calculate MA for window {window} on {source}: {e}")

    # Calculate Relative Strength Index (RSI)
    if "rsi" in config and config["rsi"]:
        for window, source in _normalize_window_config(config["rsi"]):
            try:
                series = df[source]
                rsi = vbt.RSI.run(series, window=window, short_name=f"rsi_{window}")
                df[feature_col_name("RSI", window, source)] = rsi.rsi
            except Exception as e:
                print(f"Could not calculate RSI for window {window} on {source}: {e}")

    return df

if __name__ == '__main__':
    # --- Example Usage ---
    # Create a sample DataFrame
    data = {
        'open': [100, 102, 101, 103, 105, 104, 106, 108, 107, 109],
        'high': [103, 104, 103, 105, 106, 106, 109, 110, 109, 111],
        'low': [99, 101, 100, 102, 104, 103, 105, 107, 106, 108],
        'close': [102, 103, 102, 104, 105, 105, 108, 109, 108, 110],
        'volume': [1000, 1500, 1200, 1800, 2000, 1700, 2200, 2500, 2300, 2800]
    }
    sample_df = pd.DataFrame(data, index=pd.to_datetime(pd.date_range('2023-01-01', periods=10)))

    # Define the feature configuration
    feature_config = {
        'ma': [3, 5],
        'rsi': 4
    }

    # Add features to the DataFrame
    df_with_features = add_features(sample_df.copy(), feature_config)

    print("--- Original DataFrame ---")
    print(sample_df)
    print("\n--- DataFrame with Features ---")
    print(df_with_features)
