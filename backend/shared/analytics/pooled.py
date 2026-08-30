from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

import numpy as np
import pandas as pd

from backend.shared.analytics import features as feature_engine
from backend.shared.analytics.models import (
    compute_return_target,
    normalize_non_finite_values,
    target_lookahead,
)


@dataclass(frozen=True)
class MarketDateFold:
    """One chronological pooled evaluation partition."""

    number: int
    train_dates: tuple[date, ...]
    purge_dates: tuple[date, ...]
    holdout_dates: tuple[date, ...]


@dataclass(frozen=True)
class PooledDatasetExclusion:
    symbol: str
    reason: str
    excluded_row_count: int


@dataclass(frozen=True)
class PooledSymbolCoverage:
    """Observed, aligned, and model-ready row counts for one Symbol."""

    symbol: str
    canonical_row_count: int
    market_date_axis_row_count: int
    missing_market_date_row_count: int
    invalid_ohlcv_row_count: int
    model_ready_row_count: int
    excluded_canonical_row_count: int


@dataclass(frozen=True)
class PooledModelReadyDataset:
    frame: pd.DataFrame
    feature_names: tuple[str, ...]
    exclusions: tuple[PooledDatasetExclusion, ...]
    market_dates: tuple[date, ...] = ()
    deduplicated_row_count: int = 0
    symbol_coverage: tuple[PooledSymbolCoverage, ...] = ()
    counterfactual_complete_case_row_counts: Mapping[str, int] = field(
        default_factory=dict
    )


_REQUIRED_CORE_COLUMNS = ("open", "high", "low", "close", "volume")
FeatureConfigurationError = feature_engine.FeatureConfigurationError


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported Market Date value: {value!r}")


def build_market_date_folds(
    dates: Iterable[date | datetime | str],
    *,
    splits: int = 3,
    test_size: float = 0.2,
    purge: int = 0,
) -> list[MarketDateFold]:
    """Build expanding folds over unique Market Dates.

    ``purge`` dates immediately before each holdout are excluded from training
    because their forward targets can reach into that holdout. Rows are never
    partitioned independently of their Market Date.
    """
    unique_dates = tuple(sorted({_as_date(value) for value in dates}))
    if not unique_dates:
        raise ValueError("dates must contain at least one Market Date")
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1")
    if splits < 1:
        raise ValueError("splits must be >= 1")
    if purge < 0:
        raise ValueError("purge must be >= 0")

    test_len = int(len(unique_dates) * test_size)
    if test_len <= 0:
        raise ValueError("test_size too small for available Market Dates")
    if len(unique_dates) <= test_len * splits:
        raise ValueError("Not enough dates for the requested number of splits")

    train_len = len(unique_dates) - test_len * splits
    folds: list[MarketDateFold] = []
    for index in range(splits):
        train_end = train_len + index * test_len
        holdout_end = train_end + test_len
        purge_start = max(0, train_end - purge)
        train_dates = unique_dates[:purge_start]
        purge_dates = unique_dates[purge_start:train_end]
        holdout_dates = unique_dates[train_end:holdout_end]
        if not train_dates:
            raise ValueError("Not enough training dates after purge")
        folds.append(
            MarketDateFold(
                number=index + 1,
                train_dates=train_dates,
                purge_dates=purge_dates,
                holdout_dates=holdout_dates,
            )
        )
    return folds


def _normalize_input_frame(
    frame: pd.DataFrame,
    *,
    requested_symbols: tuple[str, ...],
    source_priority: Mapping[str, int],
) -> tuple[pd.DataFrame, int]:
    if frame.empty:
        return pd.DataFrame(columns=["date", "symbol"]), 0

    normalized = frame.copy() if "date" in frame.columns else frame.reset_index()
    if "date" not in normalized.columns:
        raise ValueError("pooled input must include a date column or date index")
    if "symbol" not in normalized.columns:
        if len(requested_symbols) != 1:
            raise ValueError("pooled input must include a symbol column")
        normalized["symbol"] = requested_symbols[0]

    normalized["symbol"] = normalized["symbol"].astype(str).str.strip().str.upper()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    normalized = normalized.dropna(subset=["date"])
    normalized["date"] = normalized["date"].dt.date
    normalized = normalized.loc[
        normalized["symbol"].isin(requested_symbols)
    ].copy()
    if normalized.empty:
        return normalized, 0

    canonical_source_priority = {
        str(source).strip().lower(): int(priority)
        for source, priority in source_priority.items()
    }
    normalized["_input_order"] = np.arange(len(normalized))
    if "source" in normalized.columns:
        source_values = normalized["source"].astype(str).str.strip().str.lower()
    else:
        source_values = pd.Series("", index=normalized.index)
    normalized["_source_priority"] = source_values.map(
        canonical_source_priority
    ).fillna(
        len(canonical_source_priority) + 1
    )
    if "raw_payload_id" in normalized.columns:
        normalized["_raw_payload_sort"] = pd.to_numeric(
            normalized["raw_payload_id"], errors="coerce"
        ).fillna(-1)
    else:
        normalized["_raw_payload_sort"] = -1
    before_count = len(normalized)
    normalized = (
        normalized.sort_values(
            [
                "symbol",
                "date",
                "_source_priority",
                "_raw_payload_sort",
                "_input_order",
            ],
            ascending=[True, True, True, False, True],
            kind="stable",
        )
        .drop_duplicates(["symbol", "date"], keep="first")
        .sort_values(["symbol", "date"], kind="stable")
        .drop(
            columns=["_input_order", "_source_priority", "_raw_payload_sort"],
        )
    )
    return normalized, before_count - len(normalized)


def _assert_core_columns(frame: pd.DataFrame) -> None:
    missing = sorted(set(_REQUIRED_CORE_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"pooled input is missing core columns: {missing}")


def _normalize_core_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    _assert_core_columns(frame)
    required = list(_REQUIRED_CORE_COLUMNS)
    numeric = frame.copy()
    for column in required:
        numeric[column] = pd.to_numeric(numeric[column], errors="coerce")
    finite = np.isfinite(numeric[required].to_numpy(dtype=float)).all(axis=1)
    positive_prices = (numeric[["open", "high", "low", "close"]] > 0).all(axis=1)
    non_negative_volume = numeric["volume"] >= 0
    valid = finite & positive_prices & non_negative_volume
    numeric.loc[~valid, required] = np.nan
    return numeric, valid


def _feature_names_from_config(feature_config: Mapping[str, object]) -> set[str]:
    names: set[str] = set()
    for feature_name, config_value in feature_config.items():
        if isinstance(config_value, int):
            entries: Iterable[object] = (config_value,)
        elif isinstance(config_value, Iterable) and not isinstance(
            config_value, (str, bytes)
        ):
            entries = config_value
        else:
            raise FeatureConfigurationError(
                "feature configuration entries must be iterable or integer."
            )

        for entry in entries:
            if isinstance(entry, dict):
                window = entry.get("window")
                source = entry.get("source", "close")
            else:
                window = entry
                source = "close"
            try:
                normalized_window = int(window)
            except (TypeError, ValueError) as exc:
                raise FeatureConfigurationError(
                    f"feature configuration has an invalid window for '{feature_name}'."
                ) from exc
            if normalized_window <= 0 or source not in _REQUIRED_CORE_COLUMNS:
                raise FeatureConfigurationError(
                    f"feature configuration is invalid for '{feature_name}'."
                )
            try:
                feature_engine.validate_feature_config_entry(
                    str(feature_name),
                    window=normalized_window,
                    source=str(source),
                )
            except ValueError as exc:
                raise FeatureConfigurationError(str(exc)) from exc
            names.add(
                feature_engine.feature_col_name(
                    str(feature_name), normalized_window, str(source)
                )
            )
    return names


def _validate_feature_configuration(
    feature_config: Mapping[str, object], feature_names: tuple[str, ...]
) -> None:
    configured_names = set(feature_names)
    expected_names = _feature_names_from_config(feature_config)
    missing_names = sorted(configured_names - expected_names)
    extra_names = sorted(expected_names - configured_names)
    if missing_names or extra_names:
        raise FeatureConfigurationError(
            "feature configuration does not match shift_map: "
            f"missing={missing_names}, extra={extra_names}"
        )


def _contiguous_valid_segments(valid: pd.Series) -> tuple[tuple[int, int], ...]:
    positions = np.flatnonzero(valid.to_numpy(dtype=bool))
    if len(positions) == 0:
        return ()

    breaks = np.flatnonzero(np.diff(positions) > 1) + 1
    groups = np.split(positions, breaks)
    return tuple((int(group[0]), int(group[-1]) + 1) for group in groups)


def build_pre_signal_open_to_open_volatility(
    open_prices: pd.Series,
    *,
    continuity: pd.Series,
    lookbacks: Iterable[int],
) -> pd.DataFrame:
    """Build strict, pre-signal sample volatility without crossing boundaries.

    A signal-date open is observable at signal time, so its completed return
    from the preceding open participates in the trailing window. Missing or
    invalid Market Dates break continuity; no return is bridged or filled.
    """
    normalized_lookbacks = tuple(sorted({int(value) for value in lookbacks}))
    if not normalized_lookbacks or any(value < 2 for value in normalized_lookbacks):
        raise ValueError("lookbacks must contain integers >= 2")
    if not open_prices.index.equals(continuity.index):
        raise ValueError("continuity must share the open price index")

    result = pd.DataFrame(index=open_prices.index)
    for lookback in normalized_lookbacks:
        result[f"open_to_open_volatility_{lookback}"] = np.nan

    numeric_open = pd.to_numeric(open_prices, errors="coerce")
    valid = continuity.astype(bool) & np.isfinite(numeric_open)
    for start, end in _contiguous_valid_segments(valid):
        segment = numeric_open.iloc[start:end]
        returns = segment.pct_change(fill_method=None)
        for lookback in normalized_lookbacks:
            result.iloc[start:end, result.columns.get_loc(
                f"open_to_open_volatility_{lookback}"
            )] = returns.rolling(
                window=lookback,
                min_periods=lookback,
            ).std(ddof=1).to_numpy()
    return result


def _compute_segment_targets(
    indexed: pd.DataFrame,
    valid_mask: pd.Series,
    *,
    return_target: str,
    horizon_days: int,
) -> tuple[pd.Series, pd.Series]:
    """Compute targets only inside valid contiguous Market-Date segments."""
    target = pd.Series(np.nan, index=indexed.index, dtype="float64")
    target_end_date = pd.Series(
        pd.NaT,
        index=indexed.index,
        dtype="datetime64[ns]",
    )
    lookahead = target_lookahead(return_target, horizon_days)
    for start, end in _contiguous_valid_segments(valid_mask):
        segment = indexed.iloc[start:end].copy()
        segment_target = compute_return_target(
            segment,
            return_target,
            horizon_days,
        )
        segment_target_end = pd.to_datetime(
            segment["date"], errors="coerce"
        ).shift(-lookahead)
        segment_target_end = segment_target_end.where(
            np.isfinite(segment_target.to_numpy(dtype=float))
        )
        target.iloc[start:end] = segment_target.to_numpy(dtype=float)
        target_end_date.iloc[start:end] = segment_target_end.to_numpy()
    return target, target_end_date


def _compute_observed_features(
    indexed: pd.DataFrame,
    valid_mask: pd.Series,
    *,
    feature_config: dict,
    feature_names: tuple[str, ...],
    shift_map: dict[str, int],
) -> pd.DataFrame:
    """Compute features on observed rows; only invalid rows reset continuity."""
    generated = indexed.copy()
    for column, shift in shift_map.items():
        if shift < 1:
            raise ValueError(f"feature shift for '{column}' must be >= 1")
        generated[column] = np.nan

    for start, end in _contiguous_valid_segments(valid_mask):
        segment = indexed.iloc[start:end].copy()
        segment_generated = feature_engine.add_features(segment, feature_config)
        missing_features = sorted(
            set(feature_names) - set(segment_generated.columns)
        )
        if missing_features:
            raise FeatureConfigurationError(
                f"feature engine did not produce columns: {missing_features}"
            )
        for column, shift in shift_map.items():
            segment_generated[column] = segment_generated[column].shift(shift)
            generated.iloc[start:end, generated.columns.get_loc(column)] = (
                segment_generated[column].to_numpy()
            )
    return generated


def build_pooled_model_ready_dataset(
    frame: pd.DataFrame,
    *,
    feature_config: dict,
    shift_map: dict[str, int],
    return_target: str,
    horizon_days: int,
    requested_symbols: Iterable[str],
    market_dates: Iterable[date | datetime | str],
    source_priority: Mapping[str, int],
    volatility_lookbacks: Iterable[int] | None = None,
    complete_case_extra_columns: Iterable[str] = (),
    counterfactual_feature_sets: Mapping[str, Iterable[str]] | None = None,
) -> PooledModelReadyDataset:
    """Prepare pooled rows with separate target-axis and feature continuity rules."""
    symbols = tuple(
        sorted({str(symbol).strip().upper() for symbol in requested_symbols if str(symbol).strip()})
    )
    if not symbols:
        raise ValueError("requested_symbols must include at least one Symbol")
    axis_dates = tuple(sorted({_as_date(value) for value in market_dates}))

    normalized, deduplicated_row_count = _normalize_input_frame(
        frame,
        requested_symbols=symbols,
        source_priority=source_priority,
    )
    if not normalized.empty:
        _assert_core_columns(normalized)
    feature_names = tuple(shift_map)
    complete_case_extra_columns = tuple(complete_case_extra_columns)
    counterfactual_feature_sets = counterfactual_feature_sets or {}
    counterfactual_counts = {key: 0 for key in counterfactual_feature_sets}
    _validate_feature_configuration(feature_config, feature_names)
    ready_frames: list[pd.DataFrame] = []
    exclusions: list[PooledDatasetExclusion] = []
    symbol_coverage: list[PooledSymbolCoverage] = []
    axis_date_set = set(axis_dates)

    for symbol in symbols:
        source_symbol_frame = normalized.loc[normalized["symbol"] == symbol].copy()
        raw_count = len(source_symbol_frame)
        if raw_count == 0:
            axis_count = len(axis_dates)
            symbol_coverage.append(
                PooledSymbolCoverage(
                    symbol=symbol,
                    canonical_row_count=0,
                    market_date_axis_row_count=axis_count,
                    missing_market_date_row_count=axis_count,
                    invalid_ohlcv_row_count=0,
                    model_ready_row_count=0,
                    excluded_canonical_row_count=0,
                )
            )
            exclusions.append(
                PooledDatasetExclusion(symbol, "no_market_data", 0)
            )
            continue

        axis_count = len(axis_dates)
        symbol_dates = set(source_symbol_frame["date"])
        missing_market_date_count = len(axis_date_set - symbol_dates)
        observed_core, observed_valid_mask = _normalize_core_rows(
            source_symbol_frame
        )
        invalid_ohlcv_count = raw_count - int(observed_valid_mask.sum())
        try:
            if not observed_valid_mask.any():
                symbol_coverage.append(
                    PooledSymbolCoverage(
                        symbol=symbol,
                        canonical_row_count=raw_count,
                        market_date_axis_row_count=axis_count,
                        missing_market_date_row_count=missing_market_date_count,
                        invalid_ohlcv_row_count=invalid_ohlcv_count,
                        model_ready_row_count=0,
                        excluded_canonical_row_count=raw_count,
                    )
                )
                exclusions.append(
                    PooledDatasetExclusion(
                        symbol,
                        "core_ohlcv_non_finite_or_non_positive",
                        raw_count,
                    )
                )
                continue

            axis_frame = source_symbol_frame.set_index("date").reindex(axis_dates)
            axis_frame["date"] = axis_dates
            axis_frame["symbol"] = symbol
            axis_core, axis_valid_mask = _normalize_core_rows(axis_frame)
            axis_indexed = axis_core.set_index(
                pd.to_datetime(axis_core["date"])
            )
            target, target_end_date = _compute_segment_targets(
                axis_indexed,
                axis_valid_mask,
                return_target=return_target,
                horizon_days=horizon_days,
            )
            volatility = (
                build_pre_signal_open_to_open_volatility(
                    axis_indexed["open"],
                    continuity=axis_valid_mask.set_axis(axis_indexed.index),
                    lookbacks=volatility_lookbacks,
                )
                if volatility_lookbacks is not None
                else pd.DataFrame(index=axis_indexed.index)
            )

            observed_indexed = observed_core.set_index(
                pd.to_datetime(observed_core["date"])
            )
            generated = _compute_observed_features(
                observed_indexed,
                observed_valid_mask,
                feature_config=feature_config,
                feature_names=feature_names,
                shift_map=shift_map,
            )
            generated["target"] = target.reindex(generated.index).to_numpy()
            generated["target_end_date"] = target_end_date.reindex(
                generated.index
            ).to_numpy()
            for column in volatility.columns:
                generated[column] = volatility[column].reindex(generated.index).to_numpy()

            finite_generated = normalize_non_finite_values(generated)
            complete_case_columns = [
                *feature_names,
                "target",
                "target_end_date",
                *complete_case_extra_columns,
            ]
            missing_complete_case_columns = sorted(
                set(complete_case_columns) - set(finite_generated.columns)
            )
            if missing_complete_case_columns:
                raise FeatureConfigurationError(
                    "complete-case requirements reference missing columns: "
                    f"{missing_complete_case_columns}"
                )

            for (
                feature_set_id,
                comparison_features,
            ) in counterfactual_feature_sets.items():
                comparison_columns = [
                    *comparison_features,
                    "target",
                    "target_end_date",
                    *complete_case_extra_columns,
                ]
                missing_comparison_columns = sorted(
                    set(comparison_columns) - set(finite_generated.columns)
                )
                if missing_comparison_columns:
                    raise FeatureConfigurationError(
                        "counterfactual_feature_sets references missing columns: "
                        f"{missing_comparison_columns}"
                    )
                counterfactual_counts[feature_set_id] += len(
                    finite_generated.dropna(subset=comparison_columns)
                )

            ready = finite_generated.dropna(subset=complete_case_columns).copy()
            ready["date"] = ready.index.date
            ready["symbol"] = symbol
            removed_count = raw_count - len(ready)
            symbol_coverage.append(
                PooledSymbolCoverage(
                    symbol=symbol,
                    canonical_row_count=raw_count,
                    market_date_axis_row_count=axis_count,
                    missing_market_date_row_count=missing_market_date_count,
                    invalid_ohlcv_row_count=invalid_ohlcv_count,
                    model_ready_row_count=len(ready),
                    excluded_canonical_row_count=removed_count,
                )
            )
            if ready.empty:
                exclusions.append(
                    PooledDatasetExclusion(
                        symbol,
                        "feature_warmup_or_target_unavailable",
                        removed_count,
                    )
                )
                continue
            if removed_count:
                exclusions.append(
                    PooledDatasetExclusion(
                        symbol,
                        "core_data_feature_warmup_or_target_unavailable",
                        removed_count,
                    )
                )
            ready_frames.append(ready.reset_index(drop=True))
        except FeatureConfigurationError:
            raise
        except (KeyError, TypeError, ValueError):
            symbol_coverage.append(
                PooledSymbolCoverage(
                    symbol=symbol,
                    canonical_row_count=raw_count,
                    market_date_axis_row_count=axis_count,
                    missing_market_date_row_count=missing_market_date_count,
                    invalid_ohlcv_row_count=invalid_ohlcv_count,
                    model_ready_row_count=0,
                    excluded_canonical_row_count=raw_count,
                )
            )
            exclusions.append(
                PooledDatasetExclusion(
                    symbol,
                    "feature_generation_failed",
                    raw_count,
                )
            )

    if not ready_frames:
        empty_columns = [
            "date",
            "symbol",
            *feature_names,
            "target",
            "target_end_date",
        ]
        return PooledModelReadyDataset(
            frame=pd.DataFrame(columns=empty_columns),
            feature_names=feature_names,
            exclusions=tuple(exclusions),
            market_dates=axis_dates,
            deduplicated_row_count=deduplicated_row_count,
            symbol_coverage=tuple(symbol_coverage),
            counterfactual_complete_case_row_counts=counterfactual_counts,
        )

    pooled = pd.concat(ready_frames, ignore_index=True, sort=False)
    pooled = pooled.sort_values(["date", "symbol"]).reset_index(drop=True)
    return PooledModelReadyDataset(
        frame=pooled,
        feature_names=feature_names,
        exclusions=tuple(exclusions),
        market_dates=axis_dates,
        deduplicated_row_count=deduplicated_row_count,
        symbol_coverage=tuple(symbol_coverage),
        counterfactual_complete_case_row_counts=counterfactual_counts,
    )
