from datetime import date, timedelta

import pandas as pd
import pytest

from backend.shared.analytics import features as feature_engine
from backend.shared.analytics.pooled import (
    FeatureConfigurationError,
    build_pre_signal_open_to_open_volatility,
    build_market_date_folds,
    build_pooled_model_ready_dataset,
)


SOURCE_PRIORITY = {"official": 0, "yfinance": 1}


def test_pre_signal_open_volatility_uses_completed_sample_returns_and_resets_gaps():
    dates = pd.date_range("2024-01-01", periods=7, freq="D")
    open_prices = pd.Series(
        [100.0, 110.0, 121.0, 133.1, 146.41, 161.051, 177.1561],
        index=dates,
    )
    continuity = pd.Series([True, True, True, True, False, True, True], index=dates)

    result = build_pre_signal_open_to_open_volatility(
        open_prices,
        continuity=continuity,
        lookbacks=(2,),
    )

    # The signal-date open is known, so 10% returns ending on days 3 and 4
    # produce the first complete two-return sample window. The invalid day
    # resets continuity instead of bridging a missing/invalid Market Date.
    assert result.loc[dates[3], "open_to_open_volatility_2"] == pytest.approx(0.0)
    assert result.loc[dates[4], "open_to_open_volatility_2"] != result.loc[
        dates[4], "open_to_open_volatility_2"
    ]
    assert result.loc[dates[6], "open_to_open_volatility_2"] != result.loc[
        dates[6], "open_to_open_volatility_2"
    ]


def test_market_date_folds_keep_dates_together_and_purge_target_lookahead():
    dates = [date(2024, 1, 1) + timedelta(days=offset) for offset in range(30)]

    folds = build_market_date_folds(
        dates,
        splits=3,
        test_size=0.2,
        purge=5,
    )

    assert len(folds) == 3
    for fold in folds:
        assert set(fold.train_dates).isdisjoint(fold.purge_dates)
        assert set(fold.train_dates).isdisjoint(fold.holdout_dates)
        assert set(fold.purge_dates).isdisjoint(fold.holdout_dates)
        assert list(fold.train_dates) == sorted(fold.train_dates)
        assert list(fold.purge_dates) == sorted(fold.purge_dates)
        assert list(fold.holdout_dates) == sorted(fold.holdout_dates)
        assert max(fold.train_dates) < min(fold.purge_dates)
        assert max(fold.purge_dates) < min(fold.holdout_dates)

    assert folds[0].holdout_dates == tuple(dates[12:18])
    assert folds[1].holdout_dates == tuple(dates[18:24])
    assert folds[2].holdout_dates == tuple(dates[24:30])


def test_market_date_folds_reject_insufficient_dates_after_purge():
    dates = [date(2024, 1, 1) + timedelta(days=offset) for offset in range(6)]

    with pytest.raises(ValueError, match="training dates after purge"):
        build_market_date_folds(dates, splits=3, test_size=0.2, purge=5)


def test_pooled_dataset_builds_features_per_symbol_and_records_exclusions():
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    rows = []
    for symbol, base in (("AAA", 100.0), ("BBB", 200.0)):
        for offset, timestamp in enumerate(dates):
            rows.append(
                {
                    "date": timestamp,
                    "symbol": symbol,
                    "open": base + offset,
                    "high": base + offset + 1,
                    "low": base + offset - 1,
                    "close": base + offset + 0.5,
                    "volume": 1000 + offset,
                    "source": "official",
                }
            )
    rows[1]["open"] = 0.0

    result = build_pooled_model_ready_dataset(
        pd.DataFrame(rows),
        feature_config={"ma": [{"window": 2, "source": "close"}]},
        shift_map={"MA_2": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA", "BBB"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
    )

    assert result.feature_names == ("MA_2",)
    assert set(result.frame["symbol"]) == {"AAA", "BBB"}
    assert result.frame["date"].nunique() == 5
    assert result.frame.groupby("symbol")["date"].nunique().to_dict() == {
        "AAA": 3,
        "BBB": 5,
    }
    assert result.frame["target"].notna().all()
    assert "index" not in result.frame.columns
    assert [item.symbol for item in result.exclusions] == ["AAA", "BBB"]
    assert result.exclusions[0].excluded_row_count == 5
    aaa_coverage = result.symbol_coverage[0]
    assert aaa_coverage.canonical_row_count == 8
    assert aaa_coverage.market_date_axis_row_count == 8
    assert aaa_coverage.missing_market_date_row_count == 0
    assert aaa_coverage.invalid_ohlcv_row_count == 1
    assert aaa_coverage.model_ready_row_count == 3
    assert aaa_coverage.excluded_canonical_row_count == 5


def test_pooled_dataset_records_counterfactual_complete_case_counts_once():
    dates = pd.date_range("2024-01-01", periods=12, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["AAA"] * len(dates),
            "open": [100.0 + offset for offset in range(len(dates))],
            "high": [101.0 + offset for offset in range(len(dates))],
            "low": [99.0 + offset for offset in range(len(dates))],
            "close": [100.5 + offset for offset in range(len(dates))],
            "volume": [1000.0] * len(dates),
            "source": ["official"] * len(dates),
        }
    )

    result = build_pooled_model_ready_dataset(
        frame,
        feature_config={"ma": [{"window": 1, "source": "close"}, {"window": 3, "source": "close"}]},
        shift_map={"MA_1": 1, "MA_3": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
        volatility_lookbacks=(2,),
        complete_case_extra_columns=("open_to_open_volatility_2",),
        counterfactual_feature_sets={"short": ("MA_1",), "full": ("MA_1", "MA_3")},
    )

    assert result.counterfactual_complete_case_row_counts["full"] == len(result.frame)
    assert result.counterfactual_complete_case_row_counts["short"] > len(result.frame)


def test_pooled_dataset_shifts_new_feature_outputs_without_crossing_invalid_rows():
    dates = pd.date_range("2024-01-01", periods=65, freq="D")
    close = 100.0 + pd.Series(range(len(dates)), dtype="float64")
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": "AAA",
            "open": close.to_numpy(),
            "high": (close + 2).to_numpy(),
            "low": (close - 2).to_numpy(),
            "close": close.to_numpy(),
            "volume": (1000 + pd.Series(range(len(dates)))).to_numpy(),
            "source": "official",
        }
    )
    frame.loc[30, "open"] = 0.0

    result = build_pooled_model_ready_dataset(
        frame,
        feature_config={"macd_line": [{"window": 26, "source": "close"}]},
        shift_map={"MACD_LINE_26": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
    )

    assert result.feature_names == ("MACD_LINE_26",)
    assert result.frame.loc[
        result.frame["date"] == dates[27].date(), "MACD_LINE_26"
    ].iloc[0] == pytest.approx(5.38143504527612)
    post_gap = result.frame[result.frame["date"] > dates[30].date()]
    assert post_gap["date"].min() >= dates[56].date()


def test_pooled_new_feature_families_reset_continuity_after_invalid_ohlcv_row():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    close = 100.0 + pd.Series(range(len(dates)), dtype="float64")
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": "AAA",
            "open": close.to_numpy(),
            "high": (close + 2).to_numpy(),
            "low": (close - 2).to_numpy(),
            "close": close.to_numpy(),
            "volume": (1000 + pd.Series(range(len(dates)))).to_numpy(),
            "source": "official",
        }
    )
    frame.loc[30, "open"] = 0.0
    preset_windows = {
        str(definition["name"]): int(definition["default_window"])
        for definition in feature_engine.list_feature_definitions()
        if definition["window_editable"] is False
    }
    feature_config = {
        name: [{"window": window, "source": "close"}]
        for name, window in preset_windows.items()
    }
    shift_map = {
        feature_engine.feature_col_name(name, window, "close"): 1
        for name, window in preset_windows.items()
    }

    result = build_pooled_model_ready_dataset(
        frame,
        feature_config=feature_config,
        shift_map=shift_map,
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
    )

    assert dates[30].date() not in set(result.frame["date"])
    post_gap = result.frame[result.frame["date"] > dates[30].date()]
    assert post_gap["date"].min() >= dates[56].date()
    assert post_gap[list(shift_map)].notna().all().all()


def test_pooled_dataset_keeps_zero_range_ohlcv_rows_valid():
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": "AAA",
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 1000.0,
            "source": "official",
        }
    )

    result = build_pooled_model_ready_dataset(
        frame,
        feature_config={"cmf": [{"window": 20, "source": "close"}]},
        shift_map={"CMF_20": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
    )

    assert result.symbol_coverage[0].invalid_ohlcv_row_count == 0
    assert result.frame["CMF_20"].iloc[-1] == pytest.approx(0.0)


def test_pooled_dataset_rejects_missing_core_columns():
    frame, dates = _coverage_frame(set())
    frame = frame.drop(columns=["volume"])

    with pytest.raises(ValueError, match="missing core columns"):
        build_pooled_model_ready_dataset(
            frame,
            feature_config={"ma": [{"window": 20, "source": "close"}]},
            shift_map={"MA_20": 1},
            return_target="open_to_open",
            horizon_days=20,
            requested_symbols=["AAA", "BBB"],
            market_dates=tuple(timestamp.date() for timestamp in dates),
            source_priority=SOURCE_PRIORITY,
        )


def test_pooled_dataset_rejects_feature_configuration_mismatch():
    frame, dates = _coverage_frame(set())

    with pytest.raises(FeatureConfigurationError, match="feature configuration"):
        build_pooled_model_ready_dataset(
            frame,
            feature_config={"ma": [{"window": 20, "source": "close"}]},
            shift_map={"MA_21": 1},
            return_target="open_to_open",
            horizon_days=20,
            requested_symbols=["AAA", "BBB"],
            market_dates=tuple(timestamp.date() for timestamp in dates),
            source_priority=SOURCE_PRIORITY,
        )


def test_pooled_dataset_rejects_invalid_catalog_preset_before_symbol_processing():
    frame, dates = _coverage_frame(set())

    with pytest.raises(FeatureConfigurationError, match="versioned preset window 26"):
        build_pooled_model_ready_dataset(
            frame,
            feature_config={
                "macd_line": [{"window": 12, "source": "close"}],
            },
            shift_map={"MACD_LINE_12": 1},
            return_target="open_to_open",
            horizon_days=1,
            requested_symbols=["AAA", "BBB"],
            market_dates=tuple(timestamp.date() for timestamp in dates),
            source_priority=SOURCE_PRIORITY,
        )


def test_pooled_dataset_rejects_unsupported_feature():
    frame, dates = _coverage_frame(set())

    with pytest.raises(FeatureConfigurationError, match="Unsupported feature"):
        build_pooled_model_ready_dataset(
            frame,
            feature_config={"unsupported": [{"window": 1, "source": "close"}]},
            shift_map={"UNSUPPORTED_1": 1},
            return_target="open_to_open",
            horizon_days=1,
            requested_symbols=["AAA", "BBB"],
            market_dates=tuple(timestamp.date() for timestamp in dates),
            source_priority=SOURCE_PRIORITY,
        )


def test_pooled_dataset_keeps_invalid_dates_as_target_boundaries():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": "AAA",
            "open": [
                100.0,
                101.0,
                0.0,
                103.0,
                104.0,
                105.0,
                106.0,
                107.0,
                108.0,
                109.0,
            ],
            "high": [
                101.0,
                102.0,
                104.0,
                104.0,
                105.0,
                106.0,
                107.0,
                108.0,
                109.0,
                110.0,
            ],
            "low": [
                99.0,
                100.0,
                102.0,
                102.0,
                103.0,
                104.0,
                105.0,
                106.0,
                107.0,
                108.0,
            ],
            "close": [
                100.5,
                101.5,
                103.5,
                103.5,
                104.5,
                105.5,
                106.5,
                107.5,
                108.5,
                109.5,
            ],
            "volume": [
                1000,
                1001,
                1002,
                1003,
                1004,
                1005,
                1006,
                1007,
                1008,
                1009,
            ],
        }
    )

    result = build_pooled_model_ready_dataset(
        frame,
        feature_config={"ma": [{"window": 1, "source": "close"}]},
        shift_map={"MA_1": 1},
        return_target="open_to_open",
        horizon_days=3,
        requested_symbols=["AAA"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
    )

    assert result.frame["date"].tolist() == [
        date(2024, 1, 5),
        date(2024, 1, 6),
        date(2024, 1, 7),
    ]
    assert result.frame["target_end_date"].dt.date.tolist() == [
        date(2024, 1, 8),
        date(2024, 1, 9),
        date(2024, 1, 10),
    ]
    assert result.frame["target"].tolist() == [
        107.0 / 104.0 - 1.0,
        108.0 / 105.0 - 1.0,
        109.0 / 106.0 - 1.0,
    ]
    assert result.frame["MA_1"].tolist() == [103.5, 104.5, 105.5]


def test_pooled_dataset_uses_global_market_date_axis_for_missing_symbol_dates():
    dates = pd.date_range("2024-01-01", periods=8, freq="D")
    rows = []
    for symbol in ("AAA", "BBB"):
        for timestamp in dates:
            if symbol == "BBB" and timestamp.date() == date(2024, 1, 3):
                continue
            offset = (timestamp - dates[0]).days
            rows.append(
                {
                    "date": timestamp,
                    "symbol": symbol,
                    "open": 100.0 + offset,
                    "high": 101.0 + offset,
                    "low": 99.0 + offset,
                    "close": 100.5 + offset,
                    "volume": 1000 + offset,
                    "source": "official",
                }
            )

    result = build_pooled_model_ready_dataset(
        pd.DataFrame(rows),
        feature_config={"ma": [{"window": 1, "source": "close"}]},
        shift_map={"MA_1": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA", "BBB"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
    )

    bbb = result.frame.loc[result.frame["symbol"] == "BBB"]
    assert result.market_dates == tuple(timestamp.date() for timestamp in dates)
    assert bbb["date"].tolist() == [
        date(2024, 1, 4),
        date(2024, 1, 5),
        date(2024, 1, 6),
        date(2024, 1, 7),
    ]
    assert bbb["target_end_date"].dt.date.tolist() == [
        date(2024, 1, 5),
        date(2024, 1, 6),
        date(2024, 1, 7),
        date(2024, 1, 8),
    ]
    assert pd.api.types.is_datetime64_ns_dtype(bbb["target_end_date"])
    assert bbb["MA_1"].iloc[0] == 101.5
    bbb_coverage = next(
        item for item in result.symbol_coverage if item.symbol == "BBB"
    )
    assert bbb_coverage.canonical_row_count == 7
    assert bbb_coverage.market_date_axis_row_count == 8
    assert bbb_coverage.missing_market_date_row_count == 1
    assert bbb_coverage.invalid_ohlcv_row_count == 0
    assert bbb_coverage.model_ready_row_count == 4
    assert bbb_coverage.excluded_canonical_row_count == 3


def test_pooled_dataset_does_not_derive_axis_from_single_symbol_rows():
    market_dates = pd.date_range("2024-01-01", periods=5, freq="D")
    observed_dates = market_dates[[0, 1, 3, 4]]
    frame = pd.DataFrame(
        {
            "date": observed_dates,
            "symbol": "BBB",
            "open": [100.0, 101.0, 103.0, 104.0],
            "high": [101.0, 102.0, 104.0, 105.0],
            "low": [99.0, 100.0, 102.0, 103.0],
            "close": [100.5, 101.5, 103.5, 104.5],
            "volume": [1000, 1001, 1003, 1004],
            "source": "official",
        }
    )

    result = build_pooled_model_ready_dataset(
        frame,
        feature_config={"ma": [{"window": 1, "source": "close"}]},
        shift_map={"MA_1": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["BBB"],
        market_dates=tuple(timestamp.date() for timestamp in market_dates),
        source_priority=SOURCE_PRIORITY,
    )

    assert result.market_dates == tuple(
        timestamp.date() for timestamp in market_dates
    )
    assert result.frame["date"].tolist() == [date(2024, 1, 4)]
    assert result.frame["target_end_date"].dt.date.tolist() == [
        date(2024, 1, 5)
    ]
    assert not (result.frame["target_end_date"].dt.date == date(2024, 1, 4)).any()


def _coverage_frame(missing_offsets: set[int]) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    dates = pd.date_range("2024-01-01", periods=300, freq="D")
    rows = []
    for symbol in ("AAA", "BBB"):
        for offset, timestamp in enumerate(dates):
            if symbol == "BBB" and offset in missing_offsets:
                continue
            rows.append(
                {
                    "date": timestamp,
                    "symbol": symbol,
                    "open": 100.0 + offset,
                    "high": 101.0 + offset,
                    "low": 99.0 + offset,
                    "close": 100.5 + offset,
                    "volume": 1000 + offset,
                    "source": "official",
                }
            )
    return pd.DataFrame(rows), dates


def _coverage_result(frame: pd.DataFrame):
    return build_pooled_model_ready_dataset(
        frame,
        feature_config={"ma": [{"window": 20, "source": "close"}]},
        shift_map={"MA_20": 1},
        return_target="open_to_open",
        horizon_days=20,
        requested_symbols=["AAA", "BBB"],
        market_dates=tuple(sorted(set(pd.to_datetime(frame["date"]).dt.date))),
        source_priority=SOURCE_PRIORITY,
    )


def test_missing_dates_do_not_restart_feature_warmup_but_invalid_rows_do():
    complete_frame, dates = _coverage_frame(set())
    one_missing_frame, _ = _coverage_frame({100})
    four_missing_frame, _ = _coverage_frame({100, 160, 220, 260})
    invalid_frame = complete_frame.copy()
    invalid_frame.loc[
        (invalid_frame["symbol"] == "BBB")
        & (invalid_frame["date"] == dates[100]),
        "open",
    ] = 0.0

    complete = _coverage_result(complete_frame)
    one_missing = _coverage_result(one_missing_frame)
    four_missing = _coverage_result(four_missing_frame)
    invalid = _coverage_result(invalid_frame)

    complete_bbb = complete.symbol_coverage[1]
    one_missing_bbb = one_missing.symbol_coverage[1]
    four_missing_bbb = four_missing.symbol_coverage[1]
    invalid_bbb = invalid.symbol_coverage[1]

    assert complete_bbb.canonical_row_count == 300
    assert complete_bbb.market_date_axis_row_count == 300
    assert complete_bbb.missing_market_date_row_count == 0
    assert complete_bbb.invalid_ohlcv_row_count == 0
    assert complete_bbb.model_ready_row_count == 260
    assert complete_bbb.excluded_canonical_row_count == 40

    assert one_missing_bbb.canonical_row_count == 299
    assert one_missing_bbb.market_date_axis_row_count == 300
    assert one_missing_bbb.missing_market_date_row_count == 1
    assert one_missing_bbb.invalid_ohlcv_row_count == 0
    assert one_missing_bbb.model_ready_row_count == 239
    assert one_missing_bbb.model_ready_row_count < complete_bbb.model_ready_row_count
    assert one_missing_bbb.excluded_canonical_row_count == (
        one_missing_bbb.canonical_row_count - one_missing_bbb.model_ready_row_count
    )
    first_post_missing = one_missing.frame.loc[
        (one_missing.frame["symbol"] == "BBB")
        & (one_missing.frame["date"] == dates[101].date())
    ]
    assert len(first_post_missing) == 1
    assert first_post_missing["MA_20"].notna().all()

    assert four_missing_bbb.canonical_row_count == 296
    assert four_missing_bbb.missing_market_date_row_count == 4
    assert four_missing_bbb.invalid_ohlcv_row_count == 0
    assert four_missing_bbb.model_ready_row_count == 176

    assert invalid_bbb.canonical_row_count == 300
    assert invalid_bbb.missing_market_date_row_count == 0
    assert invalid_bbb.invalid_ohlcv_row_count == 1
    assert invalid_bbb.model_ready_row_count < one_missing_bbb.model_ready_row_count
    assert invalid_bbb.excluded_canonical_row_count == (
        invalid_bbb.canonical_row_count - invalid_bbb.model_ready_row_count
    )
    invalid_post_rows = invalid.frame.loc[
        (invalid.frame["symbol"] == "BBB")
        & (invalid.frame["date"] > dates[100].date())
    ]
    assert invalid_post_rows["date"].min() >= dates[121].date()


def test_feature_generation_fallback_preserves_invalid_ohlcv_count(monkeypatch):
    frame, _ = _coverage_frame(set())
    frame.loc[
        (frame["symbol"] == "BBB")
        & (frame["date"] == pd.Timestamp("2024-02-10")),
        "open",
    ] = 0.0

    def _raise_feature_error(*args, **kwargs):
        raise ValueError("feature generation failed")

    monkeypatch.setattr(feature_engine, "add_features", _raise_feature_error)

    result = _coverage_result(frame)

    bbb = next(item for item in result.symbol_coverage if item.symbol == "BBB")
    assert bbb.invalid_ohlcv_row_count == 1
    assert bbb.model_ready_row_count == 0


def test_pooled_dataset_prefers_official_source_for_duplicate_market_dates():
    dates = pd.date_range("2024-01-01", periods=6, freq="D")
    rows = []
    for offset, timestamp in enumerate(dates):
        for source, base in (("yfinance", 1000.0), ("official", 100.0)):
            rows.append(
                {
                    "date": timestamp,
                    "symbol": "AAA",
                    "open": base + offset,
                    "high": base + offset + 1,
                    "low": base + offset - 1,
                    "close": base + offset + 0.5,
                    "volume": 1000 + offset,
                    "source": source,
                }
            )

    result = build_pooled_model_ready_dataset(
        pd.DataFrame(rows),
        feature_config={"ma": [{"window": 1, "source": "close"}]},
        shift_map={"MA_1": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
    )

    assert result.deduplicated_row_count == len(dates)
    assert result.frame.iloc[0]["target"] == 102.0 / 101.0 - 1.0
    assert result.frame.iloc[0]["MA_1"] == 100.5


def test_pooled_dataset_returns_exclusions_for_empty_input():
    result = build_pooled_model_ready_dataset(
        pd.DataFrame(),
        feature_config={"ma": [{"window": 1, "source": "close"}]},
        shift_map={"MA_1": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA", "BBB"],
        market_dates=(),
        source_priority=SOURCE_PRIORITY,
    )

    assert result.frame.empty
    assert "target_end_date" in result.frame.columns
    assert [item.reason for item in result.exclusions] == [
        "no_market_data",
        "no_market_data",
    ]


def test_pooled_dataset_requires_explicit_source_priority_policy():
    with pytest.raises(TypeError, match="source_priority"):
        build_pooled_model_ready_dataset(
            pd.DataFrame(),
            feature_config={"ma": [{"window": 1, "source": "close"}]},
            shift_map={"MA_1": 1},
            return_target="open_to_open",
            horizon_days=1,
            requested_symbols=["AAA"],
            market_dates=(),
        )


def test_pooled_dataset_reports_global_axis_for_symbol_without_rows():
    dates = pd.date_range("2024-01-01", periods=3, freq="D")
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": "AAA",
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1001, 1002],
            "source": "official",
        }
    )

    result = build_pooled_model_ready_dataset(
        frame,
        feature_config={"ma": [{"window": 1, "source": "close"}]},
        shift_map={"MA_1": 1},
        return_target="open_to_open",
        horizon_days=1,
        requested_symbols=["AAA", "BBB"],
        market_dates=tuple(timestamp.date() for timestamp in dates),
        source_priority=SOURCE_PRIORITY,
    )

    bbb = next(item for item in result.symbol_coverage if item.symbol == "BBB")
    assert bbb.canonical_row_count == 0
    assert bbb.market_date_axis_row_count == 3
    assert bbb.missing_market_date_row_count == 3
    assert bbb.model_ready_row_count == 0
    assert bbb.excluded_canonical_row_count == 0
