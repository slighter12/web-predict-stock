import logging
from collections.abc import Callable, Mapping
from typing import Iterable, Tuple, Union

import numpy as np
import pandas as pd
import vectorbt as vbt

logger = logging.getLogger(__name__)

FEATURE_REGISTRY_VERSION = "technical_feature_registry_v3"
PRICE_SOURCE_OPTIONS = ("open", "high", "low", "close", "volume")


class FeatureConfigurationError(ValueError):
    """Raised when feature configuration cannot produce requested columns."""


FEATURE_DEFINITIONS = (
    {
        "name": "ma",
        "family": "ma",
        "label": "Moving Average",
        "description": "Simple moving average for baseline trend smoothing.",
        "default_window": 5,
        "window_editable": True,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
        "parameter_tuple": {"window": 5},
        "required_columns": (),
    },
    {
        "name": "ema",
        "family": "ema",
        "label": "Exponential Moving Average",
        "description": "Faster trend-following average that reacts more quickly to recent data.",
        "default_window": 5,
        "window_editable": True,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
        "parameter_tuple": {"window": 5},
        "required_columns": (),
    },
    {
        "name": "rsi",
        "family": "rsi",
        "label": "Relative Strength Index",
        "description": "Momentum oscillator for overbought and oversold regimes.",
        "default_window": 14,
        "window_editable": True,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
        "parameter_tuple": {"window": 14},
        "required_columns": (),
    },
    {
        "name": "roc",
        "family": "roc",
        "label": "Rate Of Change",
        "description": "Windowed percent change for momentum and breakout-style signals.",
        "default_window": 10,
        "window_editable": True,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
        "parameter_tuple": {"window": 10},
        "required_columns": (),
    },
    {
        "name": "volatility",
        "family": "volatility",
        "label": "Rolling Volatility",
        "description": "Annualized rolling standard deviation of returns for risk-sensitive models.",
        "default_window": 20,
        "window_editable": True,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
        "parameter_tuple": {"window": 20},
        "required_columns": (),
    },
    {
        "name": "zscore",
        "family": "zscore",
        "label": "Rolling Z-Score",
        "description": "Normalized distance from the rolling mean for mean-reversion style features.",
        "default_window": 20,
        "window_editable": True,
        "allowed_sources": PRICE_SOURCE_OPTIONS,
        "parameter_tuple": {"window": 20},
        "required_columns": (),
    },
    {
        "name": "macd_line",
        "family": "macd",
        "label": "MACD Line",
        "description": "Moving Average Convergence Divergence line.",
        "default_window": 26,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {
            "fast_window": 12,
            "slow_window": 26,
            "signal_window": 9,
            "macd_ewm": True,
            "signal_ewm": True,
        },
        "required_columns": ("close",),
    },
    {
        "name": "macd_signal",
        "family": "macd",
        "label": "MACD Signal",
        "description": "Signal line derived from the MACD line.",
        "default_window": 26,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {
            "fast_window": 12,
            "slow_window": 26,
            "signal_window": 9,
            "macd_ewm": True,
            "signal_ewm": True,
        },
        "required_columns": ("close",),
    },
    {
        "name": "macd_histogram",
        "family": "macd",
        "label": "MACD Histogram",
        "description": "Difference between the MACD line and signal line.",
        "default_window": 26,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {
            "fast_window": 12,
            "slow_window": 26,
            "signal_window": 9,
            "macd_ewm": True,
            "signal_ewm": True,
        },
        "required_columns": ("close",),
    },
    {
        "name": "bbands_upper",
        "family": "bbands",
        "label": "Bollinger Upper Band",
        "description": "Upper Bollinger Band using the conventional two-standard-deviation multiplier.",
        "default_window": 20,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 20, "alpha": 2, "ewm": False},
        "required_columns": ("close",),
    },
    {
        "name": "bbands_middle",
        "family": "bbands",
        "label": "Bollinger Middle Band",
        "description": "Rolling Bollinger middle band.",
        "default_window": 20,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 20, "alpha": 2, "ewm": False},
        "required_columns": ("close",),
    },
    {
        "name": "bbands_lower",
        "family": "bbands",
        "label": "Bollinger Lower Band",
        "description": "Lower Bollinger Band using the conventional two-standard-deviation multiplier.",
        "default_window": 20,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 20, "alpha": 2, "ewm": False},
        "required_columns": ("close",),
    },
    {
        "name": "atr",
        "family": "atr",
        "label": "Average True Range",
        "description": "Wilder-smoothed true range over the conventional 14-period window, seeded with the first 14 true ranges.",
        "default_window": 14,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {
            "window": 14,
            "smoothing_method": "wilder",
            "seed_policy": "sma_first_window_true_ranges",
        },
        "required_columns": ("high", "low", "close"),
    },
    {
        "name": "stoch_k",
        "family": "stoch",
        "label": "Stochastic %K",
        "description": "Fast stochastic oscillator %K line.",
        "default_window": 14,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"k_window": 14, "d_window": 3, "d_ewm": False},
        "required_columns": ("high", "low", "close"),
    },
    {
        "name": "stoch_d",
        "family": "stoch",
        "label": "Stochastic %D",
        "description": "Smoothed stochastic oscillator %D line.",
        "default_window": 14,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"k_window": 14, "d_window": 3, "d_ewm": False},
        "required_columns": ("high", "low", "close"),
    },
    {
        "name": "obv",
        "family": "obv",
        "label": "On-Balance Volume",
        "description": "Cumulative volume signed by close-to-close direction; window 1 is a fixed compatibility sentinel.",
        "default_window": 1,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 1},
        "required_columns": ("close", "volume"),
    },
    {
        "name": "adx",
        "family": "adx_dmi",
        "label": "Average Directional Index",
        "description": "Wilder-smoothed trend-strength component of directional movement.",
        "default_window": 14,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 14},
        "required_columns": ("high", "low", "close"),
    },
    {
        "name": "dmi_plus",
        "family": "adx_dmi",
        "label": "Positive Directional Movement",
        "description": "Positive directional indicator component paired with ADX.",
        "default_window": 14,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 14},
        "required_columns": ("high", "low", "close"),
    },
    {
        "name": "dmi_minus",
        "family": "adx_dmi",
        "label": "Negative Directional Movement",
        "description": "Negative directional indicator component paired with ADX.",
        "default_window": 14,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 14},
        "required_columns": ("high", "low", "close"),
    },
    {
        "name": "mfi",
        "family": "mfi",
        "label": "Money Flow Index",
        "description": "Volume-weighted money-flow oscillator requiring 14 valid price movements per warmup segment.",
        "default_window": 14,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 14, "warmup_policy": "14_movements"},
        "required_columns": ("high", "low", "close", "volume"),
    },
    {
        "name": "cmf",
        "family": "cmf",
        "label": "Chaikin Money Flow",
        "description": "Rolling money-flow volume ratio over the conventional 20-period window.",
        "default_window": 20,
        "window_editable": False,
        "allowed_sources": ("close",),
        "parameter_tuple": {"window": 20},
        "required_columns": ("high", "low", "close", "volume"),
    },
)
FEATURE_DEFINITION_BY_NAME = {
    feature["name"]: feature for feature in FEATURE_DEFINITIONS
}
_FIXED_FEATURE_FAMILIES = frozenset(
    str(feature["family"])
    for feature in FEATURE_DEFINITIONS
    if not bool(feature["window_editable"])
)


def list_feature_definitions() -> list[dict[str, object]]:
    return [
        {
            **feature,
            "allowed_sources": list(feature["allowed_sources"]),
            "parameter_tuple": dict(feature["parameter_tuple"]),
            "required_columns": list(feature["required_columns"]),
        }
        for feature in FEATURE_DEFINITIONS
    ]


def get_feature_definition(name: str) -> dict[str, object] | None:
    feature = FEATURE_DEFINITION_BY_NAME.get(name)
    if feature is None:
        return None
    return {
        **feature,
        "allowed_sources": list(feature["allowed_sources"]),
        "parameter_tuple": dict(feature["parameter_tuple"]),
        "required_columns": list(feature["required_columns"]),
    }


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


def validate_feature_config_entry(
    feature_name: str,
    *,
    window: int,
    source: str,
) -> dict[str, object]:
    definition = FEATURE_DEFINITION_BY_NAME.get(feature_name)
    if definition is None:
        raise FeatureConfigurationError(f"Unsupported feature '{feature_name}'.")

    allowed_sources = definition["allowed_sources"]
    if source not in allowed_sources:
        raise FeatureConfigurationError(
            f"Feature '{feature_name}' does not support source '{source}'; "
            f"allowed sources are {list(allowed_sources)}."
        )

    if not bool(definition["window_editable"]):
        expected_window = int(definition["default_window"])
        if window != expected_window:
            raise FeatureConfigurationError(
                f"Feature '{feature_name}' uses the versioned preset window "
                f"{expected_window}; received {window}."
            )
    return definition


def _assert_required_columns(df: pd.DataFrame, feature_name: str) -> None:
    definition = FEATURE_DEFINITION_BY_NAME[feature_name]
    required = tuple(definition["required_columns"])
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise FeatureConfigurationError(
            f"Feature '{feature_name}' requires OHLCV columns: {missing}."
        )


def _wilder_smooth(series: pd.Series, window: int) -> pd.Series:
    """Apply Wilder smoothing with an SMA seed to each finite data segment."""
    if window <= 0:
        raise ValueError("Wilder smoothing window must be positive.")

    values = series.to_numpy(dtype="float64")
    smoothed = np.full(len(values), np.nan, dtype="float64")
    finite = np.isfinite(values)
    segment_start = 0
    while segment_start < len(values):
        if not finite[segment_start]:
            segment_start += 1
            continue

        segment_end = segment_start
        while segment_end < len(values) and finite[segment_end]:
            segment_end += 1
        if segment_end - segment_start >= window:
            seed_index = segment_start + window - 1
            smoothed[seed_index] = values[segment_start:seed_index + 1].mean()
            for index in range(seed_index + 1, segment_end):
                smoothed[index] = (
                    smoothed[index - 1] * (window - 1) + values[index]
                ) / window
        segment_start = segment_end

    return pd.Series(smoothed, index=series.index, name=series.name)


def _true_range(df: pd.DataFrame) -> pd.Series:
    """Calculate true range, leaving rows without a prior close undefined."""
    previous_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - previous_close).abs(),
            (df["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=False)
    if not true_range.empty:
        true_range.iloc[0] = np.nan
    return true_range


def _rolling_sum_by_segment(series: pd.Series, window: int) -> pd.Series:
    """Roll sums without carrying observations across undefined rows."""
    values = series.to_numpy(dtype="float64")
    totals = np.full(len(values), np.nan, dtype="float64")
    finite = np.isfinite(values)
    segment_start = 0
    while segment_start < len(values):
        if not finite[segment_start]:
            segment_start += 1
            continue

        segment_end = segment_start
        while segment_end < len(values) and finite[segment_end]:
            segment_end += 1
        segment = pd.Series(values[segment_start:segment_end])
        totals[segment_start:segment_end] = segment.rolling(
            window,
            min_periods=window,
        ).sum().to_numpy()
        segment_start = segment_end

    return pd.Series(totals, index=series.index, name=series.name)


def _calculate_adx_dmi(
    df: pd.DataFrame,
    *,
    window: int,
) -> dict[str, pd.Series]:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    true_range = _true_range(df)
    upward_move = high.diff()
    downward_move = -low.diff()
    known_movement = upward_move.notna() & downward_move.notna()
    positive_movement = upward_move.where(
        (upward_move > downward_move) & (upward_move > 0),
        0.0,
    ).mask(~known_movement)
    negative_movement = downward_move.where(
        (downward_move > upward_move) & (downward_move > 0),
        0.0,
    ).mask(~known_movement)

    smoothed_true_range = _wilder_smooth(true_range, window)
    smoothed_positive_movement = _wilder_smooth(positive_movement, window)
    smoothed_negative_movement = _wilder_smooth(negative_movement, window)
    zero_true_range = smoothed_true_range.eq(0) & smoothed_true_range.notna()
    positive_direction = (
        100 * smoothed_positive_movement / smoothed_true_range
    ).mask(zero_true_range, 0.0)
    negative_direction = (
        100 * smoothed_negative_movement / smoothed_true_range
    ).mask(zero_true_range, 0.0)
    direction_sum = positive_direction + negative_direction
    zero_direction_sum = direction_sum.eq(0) & direction_sum.notna()
    direction_index = (
        100
        * (positive_direction - negative_direction).abs()
        / direction_sum
    ).mask(zero_direction_sum, 0.0)
    adx = _wilder_smooth(direction_index, window)

    return {
        "adx": adx,
        "dmi_plus": positive_direction,
        "dmi_minus": negative_direction,
    }


def _calculate_mfi(df: pd.DataFrame, *, window: int) -> pd.Series:
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    raw_money_flow = typical_price * df["volume"]
    direction = typical_price.diff()
    positive_flow = raw_money_flow.where(direction > 0, 0.0)
    negative_flow = raw_money_flow.where(direction < 0, 0.0)
    known_flow = (
        direction.notna()
        & raw_money_flow.notna()
        & np.isfinite(raw_money_flow)
    )
    positive_flow = positive_flow.mask(~known_flow)
    negative_flow = negative_flow.mask(~known_flow)
    positive_total = _rolling_sum_by_segment(positive_flow, window)
    negative_total = _rolling_sum_by_segment(negative_flow, window)

    mfi = pd.Series(np.nan, index=df.index, dtype="float64")
    valid = positive_total.notna() & negative_total.notna()
    nonzero_negative = valid & negative_total.gt(0)
    mfi.loc[nonzero_negative] = (
        100
        - 100
        / (
            1
            + positive_total.loc[nonzero_negative]
            / negative_total.loc[nonzero_negative]
        )
    )
    no_negative = valid & negative_total.eq(0)
    mfi.loc[no_negative & positive_total.gt(0)] = 100.0
    mfi.loc[valid & positive_total.eq(0) & negative_total.gt(0)] = 0.0
    mfi.loc[valid & positive_total.eq(0) & negative_total.eq(0)] = 50.0
    return mfi


def _calculate_cmf(df: pd.DataFrame, *, window: int) -> pd.Series:
    price_range = df["high"] - df["low"]
    money_flow_multiplier = pd.Series(np.nan, index=df.index, dtype="float64")
    zero_range = price_range.eq(0) & price_range.notna()
    nonzero_range = price_range.ne(0) & price_range.notna()
    money_flow_multiplier.loc[zero_range] = 0.0
    money_flow_multiplier.loc[nonzero_range] = (
        (2 * df["close"] - df["high"] - df["low"]) / price_range
    ).loc[nonzero_range]
    money_flow_volume = money_flow_multiplier * df["volume"]
    valid_flow = money_flow_multiplier.notna() & np.isfinite(df["volume"])
    volume_total = _rolling_sum_by_segment(
        df["volume"].where(valid_flow),
        window,
    )
    money_flow_total = _rolling_sum_by_segment(
        money_flow_volume.where(valid_flow),
        window,
    )
    cmf = money_flow_total / volume_total
    zero_volume = volume_total.eq(0) & volume_total.notna()
    return cmf.mask(zero_volume, 0.0)


def _calculate_macd_outputs(
    df: pd.DataFrame,
    parameters: Mapping[str, object],
) -> dict[str, pd.Series]:
    result = vbt.MACD.run(
        df["close"],
        fast_window=int(parameters["fast_window"]),
        slow_window=int(parameters["slow_window"]),
        signal_window=int(parameters["signal_window"]),
        macd_ewm=bool(parameters["macd_ewm"]),
        signal_ewm=bool(parameters["signal_ewm"]),
    )
    return {
        "macd_line": result.macd,
        "macd_signal": result.signal,
        "macd_histogram": result.macd - result.signal,
    }


def _calculate_bbands_outputs(
    df: pd.DataFrame,
    parameters: Mapping[str, object],
) -> dict[str, pd.Series]:
    result = vbt.BBANDS.run(
        df["close"],
        window=int(parameters["window"]),
        alpha=float(parameters["alpha"]),
        ewm=bool(parameters["ewm"]),
    )
    return {
        "bbands_upper": result.upper,
        "bbands_middle": result.middle,
        "bbands_lower": result.lower,
    }


def _calculate_atr_outputs(
    df: pd.DataFrame,
    parameters: Mapping[str, object],
) -> dict[str, pd.Series]:
    return {
        "atr": _wilder_smooth(
            _true_range(df),
            int(parameters["window"]),
        )
    }


def _calculate_stoch_outputs(
    df: pd.DataFrame,
    parameters: Mapping[str, object],
) -> dict[str, pd.Series]:
    result = vbt.STOCH.run(
        df["high"],
        df["low"],
        df["close"],
        k_window=int(parameters["k_window"]),
        d_window=int(parameters["d_window"]),
        d_ewm=bool(parameters["d_ewm"]),
    )
    return {"stoch_k": result.percent_k, "stoch_d": result.percent_d}


def _calculate_obv_outputs(
    df: pd.DataFrame,
    _parameters: Mapping[str, object],
) -> dict[str, pd.Series]:
    result = vbt.OBV.run(df["close"], df["volume"])
    return {"obv": result.obv}


def _calculate_adx_dmi_outputs(
    df: pd.DataFrame,
    parameters: Mapping[str, object],
) -> dict[str, pd.Series]:
    return _calculate_adx_dmi(df, window=int(parameters["window"]))


def _calculate_mfi_outputs(
    df: pd.DataFrame,
    parameters: Mapping[str, object],
) -> dict[str, pd.Series]:
    return {"mfi": _calculate_mfi(df, window=int(parameters["window"]))}


def _calculate_cmf_outputs(
    df: pd.DataFrame,
    parameters: Mapping[str, object],
) -> dict[str, pd.Series]:
    return {"cmf": _calculate_cmf(df, window=int(parameters["window"]))}


_CATALOG_CALCULATORS: dict[
    str,
    Callable[[pd.DataFrame, Mapping[str, object]], dict[str, pd.Series]],
] = {
    "macd": _calculate_macd_outputs,
    "bbands": _calculate_bbands_outputs,
    "atr": _calculate_atr_outputs,
    "stoch": _calculate_stoch_outputs,
    "obv": _calculate_obv_outputs,
    "adx_dmi": _calculate_adx_dmi_outputs,
    "mfi": _calculate_mfi_outputs,
    "cmf": _calculate_cmf_outputs,
}


def _contiguous_finite_segments(
    finite_mask: np.ndarray,
) -> Iterable[tuple[int, int]]:
    """Yield row ranges that do not cross an invalid continuity boundary."""
    segment_start = 0
    while segment_start < len(finite_mask):
        if not finite_mask[segment_start]:
            segment_start += 1
            continue

        segment_end = segment_start
        while segment_end < len(finite_mask) and finite_mask[segment_end]:
            segment_end += 1
        yield segment_start, segment_end
        segment_start = segment_end


def _calculate_catalog_outputs(
    df: pd.DataFrame,
    *,
    feature_name: str,
) -> dict[str, pd.Series]:
    definition = FEATURE_DEFINITION_BY_NAME[feature_name]
    family = str(definition["family"])
    calculator = _CATALOG_CALCULATORS.get(family)
    if calculator is None:
        raise ValueError(f"Unsupported feature family '{family}'.")

    output_names = tuple(
        str(candidate["name"])
        for candidate in FEATURE_DEFINITIONS
        if str(candidate["family"]) == family
    )
    output_values = {
        output_name: np.full(len(df), np.nan, dtype="float64")
        for output_name in output_names
    }

    # Required columns are validated by the safe entry point. When a complete
    # OHLCV frame is available, every present core column participates in the
    # continuity boundary so no catalog family carries state through a bad row.
    continuity_columns = tuple(
        column for column in PRICE_SOURCE_OPTIONS if column in df.columns
    )
    finite_mask = np.isfinite(
        df.loc[:, continuity_columns].to_numpy(dtype="float64")
    ).all(axis=1)
    for start, end in _contiguous_finite_segments(finite_mask):
        segment_outputs = calculator(
            df.iloc[start:end],
            definition["parameter_tuple"],
        )
        for output_name, series in segment_outputs.items():
            if output_name not in output_values:
                raise ValueError(
                    f"Feature family '{family}' produced unexpected output "
                    f"'{output_name}'."
                )
            if len(series) != end - start:
                raise ValueError(
                    f"Feature family '{family}' produced an output with an "
                    "unexpected length."
                )
            output_values[output_name][start:end] = series.to_numpy(
                dtype="float64"
            )

    return {
        output_name: pd.Series(values, index=df.index)
        for output_name, values in output_values.items()
    }


def _calculate_catalog_outputs_safely(
    df: pd.DataFrame,
    *,
    feature_name: str,
) -> dict[str, pd.Series]:
    definition = FEATURE_DEFINITION_BY_NAME[feature_name]
    family = str(definition["family"])
    try:
        _assert_required_columns(df, feature_name)
        return _calculate_catalog_outputs(df, feature_name=feature_name)
    except FeatureConfigurationError as exc:
        logger.warning(
            "Failed to calculate feature family=%s requested_feature=%s: %s",
            family,
            feature_name,
            exc,
        )
        raise
    except ValueError as exc:
        logger.warning(
            "Failed to calculate feature family=%s requested_feature=%s: %s",
            family,
            feature_name,
            exc,
        )
        raise ValueError(
            f"Could not calculate feature family '{family}' for "
            f"requested feature '{feature_name}'."
        ) from exc
    except Exception as exc:
        logger.exception(
            "Failed to calculate feature family=%s requested_feature=%s",
            family,
            feature_name,
        )
        raise ValueError(
            f"Could not calculate feature family '{family}' for "
            f"requested feature '{feature_name}'."
        ) from exc


def _add_catalog_feature(
    df: pd.DataFrame,
    *,
    feature_name: str,
    window: int,
    source: str,
    outputs: dict[str, pd.Series],
) -> None:
    try:
        feature = outputs.get(feature_name)
        if feature is None:
            raise ValueError(
                f"Feature family did not produce requested output '{feature_name}'."
            )
        df[feature_col_name(feature_name, window, source)] = feature
    except ValueError as exc:
        logger.warning(
            "Failed to calculate feature=%s window=%s source=%s: %s",
            feature_name,
            window,
            source,
            exc,
        )
        raise
    except Exception as exc:
        logger.exception(
            "Failed to calculate feature=%s window=%s source=%s",
            feature_name,
            window,
            source,
        )
        raise ValueError(
            f"Could not calculate feature '{feature_name}' for window {window} "
            f"on source '{source}'."
        ) from exc


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

    catalog_outputs: dict[
        tuple[str, tuple[tuple[str, str], ...]], dict[str, pd.Series]
    ] = {}
    for definition in FEATURE_DEFINITIONS:
        feature_name = str(definition["name"])
        if definition["family"] not in _FIXED_FEATURE_FAMILIES:
            continue
        if feature_name not in config or not config[feature_name]:
            continue
        for window, source in _normalize_window_config(config[feature_name]):
            validate_feature_config_entry(
                feature_name,
                window=window,
                source=source,
            )
            family = str(definition["family"])
            parameters = dict(definition["parameter_tuple"])
            parameter_key = tuple(
                sorted((str(key), repr(value)) for key, value in parameters.items())
            )
            # Every output in a family currently shares required_columns. The
            # cache key intentionally relies on that catalog invariant.
            cache_key = (family, parameter_key)
            outputs = catalog_outputs.get(cache_key)
            if outputs is None:
                outputs = _calculate_catalog_outputs_safely(
                    df,
                    feature_name=feature_name,
                )
                catalog_outputs[cache_key] = outputs
            _add_catalog_feature(
                df,
                feature_name=feature_name,
                window=window,
                source=source,
                outputs=outputs,
            )

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
