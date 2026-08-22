import numpy as np
import pandas as pd
import pytest
import vectorbt as vbt

from backend.shared.analytics.features import (
    FEATURE_REGISTRY_VERSION,
    FeatureConfigurationError,
    add_features,
    list_feature_definitions,
)


def test_feature_registry_exposes_versioned_independent_family_outputs() -> None:
    definitions = {
        definition["name"]: definition for definition in list_feature_definitions()
    }

    assert FEATURE_REGISTRY_VERSION == "technical_feature_registry_v3"
    expected_names = {
        "macd_line",
        "macd_signal",
        "macd_histogram",
        "bbands_upper",
        "bbands_middle",
        "bbands_lower",
        "atr",
        "stoch_k",
        "stoch_d",
        "obv",
        "adx",
        "dmi_plus",
        "dmi_minus",
        "mfi",
        "cmf",
    }
    assert set(definitions) == expected_names | {
        "ma",
        "ema",
        "rsi",
        "roc",
        "volatility",
        "zscore",
    }
    assert all("window_editable" in definitions[name] for name in expected_names)
    assert all(
        definitions[name]["window_editable"] is False
        for name in expected_names
    )

    assert definitions["macd_line"]["family"] == "macd"
    assert definitions["macd_line"]["parameter_tuple"] == {
        "fast_window": 12,
        "slow_window": 26,
        "signal_window": 9,
        "macd_ewm": True,
        "signal_ewm": True,
    }
    assert definitions["stoch_k"]["parameter_tuple"] == {
        "k_window": 14,
        "d_window": 3,
        "d_ewm": False,
    }
    assert definitions["bbands_upper"]["parameter_tuple"] == {
        "window": 20,
        "alpha": 2,
        "ewm": False,
    }
    assert definitions["atr"]["parameter_tuple"] == {
        "window": 14,
        "smoothing_method": "wilder",
        "seed_policy": "sma_first_window_true_ranges",
    }
    assert definitions["mfi"]["parameter_tuple"] == {
        "window": 14,
        "warmup_policy": "14_movements",
    }
    assert definitions["mfi"]["required_columns"] == [
        "high",
        "low",
        "close",
        "volume",
    ]


def _ohlcv_frame(rows: int = 60) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows)
    close = pd.Series(100 + np.arange(rows, dtype=float), index=index)
    return pd.DataFrame(
        {
            "open": close - 1,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": 1000 + np.arange(rows, dtype=float),
        },
        index=index,
    )


def test_installed_indicator_families_produce_independent_outputs() -> None:
    frame = _ohlcv_frame()
    config = {
        "macd_line": [{"window": 26, "source": "close"}],
        "macd_signal": [{"window": 26, "source": "close"}],
        "macd_histogram": [{"window": 26, "source": "close"}],
        "bbands_upper": [{"window": 20, "source": "close"}],
        "bbands_middle": [{"window": 20, "source": "close"}],
        "bbands_lower": [{"window": 20, "source": "close"}],
        "atr": [{"window": 14, "source": "close"}],
        "stoch_k": [{"window": 14, "source": "close"}],
        "stoch_d": [{"window": 14, "source": "close"}],
        "obv": [{"window": 1, "source": "close"}],
    }

    generated = add_features(frame.copy(), config)

    macd_reference = vbt.MACD.run(
        frame["close"],
        fast_window=12,
        slow_window=26,
        signal_window=9,
        macd_ewm=True,
        signal_ewm=True,
    )
    assert generated["MACD_LINE_26"].iloc[-1] == pytest.approx(
        macd_reference.macd.iloc[-1]
    )
    assert generated["MACD_SIGNAL_26"].iloc[-1] == pytest.approx(
        macd_reference.signal.iloc[-1]
    )
    assert generated["MACD_HISTOGRAM_26"].iloc[-1] == pytest.approx(
        (macd_reference.macd - macd_reference.signal).iloc[-1]
    )
    assert generated["BBANDS_MIDDLE_20"].iloc[-1] == 149.5
    assert generated["BBANDS_UPPER_20"].iloc[-1] == pytest.approx(
        161.0325625946708
    )
    assert generated["BBANDS_LOWER_20"].iloc[-1] == pytest.approx(
        137.9674374053292
    )
    assert generated["ATR_14"].iloc[-1] == 4.0
    assert generated["STOCH_K_14"].iloc[-1] == pytest.approx(
        88.23529411764706
    )
    assert generated["STOCH_D_14"].iloc[-1] == pytest.approx(88.235294117647)
    assert generated["OBV_1"].iloc[-1] == 61770.0


def test_macd_uses_ema_preset_on_nonlinear_prices() -> None:
    frame = _ohlcv_frame(80)
    close = pd.Series(
        100
        + np.array(
            [0, 3, -2, 8, 1, 11, -4, 14, 2, 17, -1, 20, 4, 16, -3, 22],
            dtype="float64",
        ).repeat(5)[:80],
        index=frame.index,
    )
    frame["open"] = close - 1
    frame["high"] = close + 2
    frame["low"] = close - 2
    frame["close"] = close

    generated = add_features(
        frame.copy(),
        {
            "macd_line": [{"window": 26, "source": "close"}],
            "macd_signal": [{"window": 26, "source": "close"}],
        },
    )
    ema_reference = vbt.MACD.run(
        close,
        fast_window=12,
        slow_window=26,
        signal_window=9,
        macd_ewm=True,
        signal_ewm=True,
    )
    sma_reference = vbt.MACD.run(
        close,
        fast_window=12,
        slow_window=26,
        signal_window=9,
        macd_ewm=False,
        signal_ewm=False,
    )

    assert np.allclose(
        generated["MACD_LINE_26"].to_numpy(),
        ema_reference.macd.to_numpy(),
        equal_nan=True,
    )
    assert not np.allclose(
        ema_reference.macd.to_numpy(),
        sma_reference.macd.to_numpy(),
        equal_nan=True,
    )


def test_vectorbt_catalog_features_reset_after_invalid_ohlcv_row() -> None:
    frame = _ohlcv_frame(90)
    gap_position = 35
    frame.iloc[gap_position] = np.nan

    generated = add_features(
        frame.copy(),
        {
            "macd_line": [{"window": 26, "source": "close"}],
            "obv": [{"window": 1, "source": "close"}],
        },
    )

    macd_reference = vbt.MACD.run(
        frame["close"].iloc[gap_position + 1 :],
        fast_window=12,
        slow_window=26,
        signal_window=9,
        macd_ewm=True,
        signal_ewm=True,
    )
    obv_reference = vbt.OBV.run(
        frame["close"].iloc[gap_position + 1 :],
        frame["volume"].iloc[gap_position + 1 :],
    )

    assert pd.isna(generated["MACD_LINE_26"].iloc[gap_position])
    assert pd.isna(generated["OBV_1"].iloc[gap_position])
    assert generated["MACD_LINE_26"].iloc[gap_position + 1 :].first_valid_index() == (
        macd_reference.macd.first_valid_index()
    )
    assert np.allclose(
        generated["MACD_LINE_26"].iloc[gap_position + 1 :].to_numpy(),
        macd_reference.macd.to_numpy(),
        equal_nan=True,
    )
    assert np.allclose(
        generated["OBV_1"].iloc[gap_position + 1 :].to_numpy(),
        obv_reference.obv.to_numpy(),
        equal_nan=True,
    )


def test_atr_uses_sma_seeded_wilder_smoothing() -> None:
    frame = _ohlcv_frame(40)
    close = pd.Series(
        100
        + np.array(
            [0, 2, -1, 4, 1, 6, 3, 8, 2, 10, 5, 12, 7, 9, 4, 13],
            dtype="float64",
        ).repeat(3)[:40],
        index=frame.index,
    )
    spread = np.resize(
        np.array([1.0, 3.0, 2.0, 5.0, 1.5, 4.0], dtype="float64"),
        len(frame),
    )
    frame["open"] = close
    frame["high"] = close + spread
    frame["low"] = close - spread
    frame["close"] = close

    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - frame["close"].shift(1)).abs(),
            (frame["low"] - frame["close"].shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1, skipna=False)
    true_range.iloc[0] = np.nan
    expected = pd.Series(np.nan, index=frame.index, dtype="float64")
    expected.iloc[14] = true_range.iloc[1:15].mean()
    for index in range(15, len(frame)):
        expected.iloc[index] = (
            expected.iloc[index - 1] * 13 + true_range.iloc[index]
        ) / 14

    generated = add_features(
        frame.copy(),
        {"atr": [{"window": 14, "source": "close"}]},
    )

    assert generated["ATR_14"].first_valid_index() == frame.index[14]
    assert np.allclose(
        generated["ATR_14"].to_numpy(),
        expected.to_numpy(),
        equal_nan=True,
    )


def test_catalog_calculation_errors_are_contextualized() -> None:
    frame = _ohlcv_frame()
    frame["close"] = frame["close"].astype(object)
    frame.loc[frame.index[20], "close"] = "not-a-number"

    with pytest.raises(ValueError, match="Could not calculate feature family 'atr'"):
        add_features(
            frame,
            {"atr": [{"window": 14, "source": "close"}]},
        )


def test_local_indicator_families_produce_deterministic_ohlcv_outputs() -> None:
    frame = _ohlcv_frame()
    config = {
        "adx": [{"window": 14, "source": "close"}],
        "dmi_plus": [{"window": 14, "source": "close"}],
        "dmi_minus": [{"window": 14, "source": "close"}],
        "mfi": [{"window": 14, "source": "close"}],
        "cmf": [{"window": 20, "source": "close"}],
    }

    generated = add_features(frame.copy(), config)

    assert generated["ADX_14"].iloc[-1] == pytest.approx(100.0)
    assert generated["DMI_PLUS_14"].iloc[-1] == pytest.approx(25.0)
    assert generated["DMI_MINUS_14"].iloc[-1] == pytest.approx(0.0)
    assert generated["MFI_14"].iloc[-1] == pytest.approx(100.0)
    assert generated["CMF_20"].iloc[-1] == pytest.approx(0.0)


def test_mfi_uses_positive_negative_flow_magnitudes() -> None:
    rows = 30
    index = pd.date_range("2024-01-01", periods=rows)
    close = pd.Series(
        [100.0 if offset % 2 == 0 else 101.0 for offset in range(rows)],
        index=index,
    )
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1000.0,
        },
        index=index,
    )

    generated = add_features(
        frame.copy(),
        {"mfi": [{"window": 14, "source": "close"}]},
    )

    expected = 100 - 100 / (1 + (7 * 101_000) / (7 * 100_000))
    assert generated["MFI_14"].iloc[14] == pytest.approx(expected)
    assert pd.isna(generated["MFI_14"].iloc[13])
    assert generated["MFI_14"].iloc[14] == pytest.approx(50.2487562189)
    assert generated["MFI_14"].dropna().between(0, 100).all()


def test_mfi_warmup_requires_movements_and_resets_after_invalid_row() -> None:
    frame = _ohlcv_frame(60)
    gap_index = frame.index[20]
    frame.loc[gap_index, ["high", "low", "close", "volume"]] = np.nan

    generated = add_features(
        frame.copy(),
        {"mfi": [{"window": 14, "source": "close"}]},
    )

    output = generated["MFI_14"]
    assert output.first_valid_index() == frame.index[14]
    assert output.loc[frame.index[13]] != output.loc[frame.index[13]]
    assert output.loc[frame.index[34]] != output.loc[frame.index[34]]
    assert output.loc[frame.index[35]] == pytest.approx(100.0)


def test_cmf_warmup_resets_after_invalid_row() -> None:
    frame = _ohlcv_frame(60)
    gap_index = frame.index[20]
    frame.loc[gap_index, ["high", "low", "close", "volume"]] = np.nan

    generated = add_features(
        frame.copy(),
        {"cmf": [{"window": 20, "source": "close"}]},
    )

    output = generated["CMF_20"]
    assert output.first_valid_index() == frame.index[19]
    assert pd.isna(output.loc[frame.index[39]])
    assert output.loc[frame.index[40]] == pytest.approx(0.0)


def test_local_indicator_zero_range_policy_preserves_neutral_values() -> None:
    frame = _ohlcv_frame()
    frame["open"] = 100.0
    frame["high"] = 100.0
    frame["low"] = 100.0
    frame["close"] = 100.0
    frame["volume"] = 1000.0

    generated = add_features(
        frame.copy(),
        {
            "adx": [{"window": 14, "source": "close"}],
            "dmi_plus": [{"window": 14, "source": "close"}],
            "dmi_minus": [{"window": 14, "source": "close"}],
            "mfi": [{"window": 14, "source": "close"}],
            "cmf": [{"window": 20, "source": "close"}],
        },
    )

    assert generated["ADX_14"].iloc[-1] == pytest.approx(0.0)
    assert generated["DMI_PLUS_14"].iloc[-1] == pytest.approx(0.0)
    assert generated["DMI_MINUS_14"].iloc[-1] == pytest.approx(0.0)
    assert generated["MFI_14"].iloc[-1] == pytest.approx(50.0)
    assert generated["CMF_20"].iloc[-1] == pytest.approx(0.0)

    declining = _ohlcv_frame()
    declining_close = pd.Series(
        200.0 - np.arange(len(declining), dtype=float),
        index=declining.index,
    )
    declining["open"] = declining_close
    declining["high"] = declining_close + 2
    declining["low"] = declining_close - 2
    declining["close"] = declining_close
    declining_output = add_features(
        declining,
        {"mfi": [{"window": 14, "source": "close"}]},
    )
    assert declining_output["MFI_14"].iloc[-1] == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("feature_name", "missing_column"),
    [
        ("macd_line", "close"),
        ("bbands_upper", "close"),
        ("atr", "high"),
        ("stoch_k", "low"),
        ("obv", "volume"),
        ("adx", "high"),
        ("mfi", "volume"),
        ("cmf", "volume"),
    ],
)
def test_catalog_features_require_declared_ohlcv_columns(
    feature_name: str,
    missing_column: str,
) -> None:
    frame = _ohlcv_frame().drop(columns=[missing_column])
    window = int(
        next(
            definition["default_window"]
            for definition in list_feature_definitions()
            if definition["name"] == feature_name
        )
    )

    with pytest.raises(FeatureConfigurationError, match="requires OHLCV columns"):
        add_features(
            frame,
            {feature_name: [{"window": window, "source": "close"}]},
        )


def test_fixed_feature_presets_and_required_columns_are_explicit() -> None:
    frame = _ohlcv_frame()

    with pytest.raises(
        FeatureConfigurationError,
        match="versioned preset window 26",
    ):
        add_features(
            frame.copy(),
            {"macd_line": [{"window": 12, "source": "close"}]},
        )

    with pytest.raises(FeatureConfigurationError, match="requires OHLCV columns"):
        add_features(
            frame.drop(columns=["volume"]),
            {"mfi": [{"window": 14, "source": "close"}]},
        )
