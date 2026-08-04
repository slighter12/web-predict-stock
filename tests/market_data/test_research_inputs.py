from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest

import backend.market_data.services.research_inputs as research_inputs


def test_load_research_eligible_tw_bars_filters_and_maps_multi_symbol_rows(
    monkeypatch,
):
    no_data_date = date(2024, 1, 4)
    end_date = date(2024, 1, 5)
    frame = pd.DataFrame(
        [
            {
                "date": no_data_date,
                "symbol": "2330",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "source": research_inputs.official_daily.SOURCE_TWSE_MI_INDEX,
                "raw_payload_id": 11,
            },
            {
                "date": no_data_date,
                "symbol": "2317",
                "open": 90.0,
                "high": 92.0,
                "low": 89.0,
                "close": 91.0,
                "source": "yfinance",
                "raw_payload_id": 12,
            },
            {
                "date": end_date,
                "symbol": "2317",
                "open": 93.0,
                "high": 95.0,
                "low": 92.0,
                "close": 94.0,
                "source": "yfinance",
                "raw_payload_id": 13,
            },
            {
                "date": end_date,
                "symbol": "2454",
                "open": 0.0,
                "high": 601.0,
                "low": 598.0,
                "close": 600.0,
                "source": research_inputs.official_daily.SOURCE_TWSE,
                "raw_payload_id": 14,
            },
            {
                "date": end_date,
                "symbol": "2603",
                "open": 200.0,
                "high": float("inf"),
                "low": 198.0,
                "close": 199.0,
                "source": research_inputs.official_daily.SOURCE_TWSE,
                "raw_payload_id": 15,
            },
        ]
    ).set_index(["date", "symbol"])
    captured = {}

    def _get_data(symbols, **kwargs):
        captured["symbols"] = symbols
        captured.update(kwargs)
        return frame

    monkeypatch.setattr(research_inputs, "get_data", _get_data)
    monkeypatch.setattr(
        research_inputs,
        "load_official_no_data_dates",
        lambda **kwargs: captured.update({"audit_range": kwargs})
        or {no_data_date},
    )

    result = research_inputs.load_research_eligible_tw_bars(
        ["2330", " 2317 ", "2454", "2330", "2603", ""],
        start_date=no_data_date,
        end_date=end_date,
    )

    assert captured == {
        "symbols": ["2317", "2330", "2454", "2603"],
        "start_date": no_data_date,
        "end_date": end_date,
        "market": "TW",
        "audit_range": {
            "start_date": no_data_date,
            "end_date": end_date,
        },
    }
    assert result == {
        "2317": [
            research_inputs.EligibleBar(
                date=end_date,
                open=93.0,
                high=95.0,
                low=92.0,
                close=94.0,
                source="yfinance",
                raw_payload_id=13,
            )
        ],
        "2330": [
            research_inputs.EligibleBar(
                date=no_data_date,
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                source=research_inputs.official_daily.SOURCE_TWSE_MI_INDEX,
                raw_payload_id=11,
            )
        ],
    }


def test_load_research_eligible_tw_bars_uses_tw_date_for_default_audit_end(monkeypatch):
    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz == research_inputs.TW_TIMEZONE
            return cls(2024, 1, 5, 0, 30, tzinfo=tz)

    captured = {}
    frame = pd.DataFrame(
        [
            {
                "date": date(2024, 1, 4),
                "symbol": "2317",
                "open": 90.0,
                "high": 91.0,
                "low": 89.0,
                "close": 90.5,
                "source": "twse",
                "raw_payload_id": 1,
            },
            {
                "date": date(2024, 1, 5),
                "symbol": "2317",
                "open": 91.0,
                "high": 92.0,
                "low": 90.0,
                "close": 91.5,
                "source": "twse",
                "raw_payload_id": 2,
            },
            {
                "date": date(2024, 1, 4),
                "symbol": "2330",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "source": "twse",
                "raw_payload_id": 3,
            },
            {
                "date": date(2024, 1, 4),
                "symbol": "2454",
                "open": 0.0,
                "high": 1.0,
                "low": -1.0,
                "close": 0.5,
                "source": "twse",
                "raw_payload_id": 4,
            },
        ]
    ).set_index(["date", "symbol"])
    monkeypatch.setattr(research_inputs, "datetime", _FixedDatetime)
    monkeypatch.setattr(research_inputs, "get_data", lambda *args, **kwargs: frame)
    monkeypatch.setattr(
        research_inputs,
        "load_official_no_data_dates",
        lambda **kwargs: captured.update(kwargs) or set(),
    )

    result = research_inputs.load_research_eligible_tw_bars(
        ["2317", "2330", "2454"],
        start_date=date(2024, 1, 4),
    )

    assert captured == {
        "start_date": date(2024, 1, 4),
        "end_date": date(2024, 1, 5),
    }
    assert {
        symbol: [bar.date for bar in bars]
        for symbol, bars in result.items()
    } == {
        "2317": [date(2024, 1, 4), date(2024, 1, 5)],
        "2330": [date(2024, 1, 4)],
    }


def test_load_research_eligible_tw_bars_accepts_single_symbol_date_index(
    monkeypatch,
):
    trading_date = date(2024, 1, 4)
    frame = pd.DataFrame(
        [
            {
                "date": trading_date,
                "symbol": "2330",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "source": research_inputs.official_daily.SOURCE_TWSE,
                "raw_payload_id": 21,
            }
        ]
    ).set_index("date")
    monkeypatch.setattr(
        research_inputs,
        "get_data",
        lambda *args, **kwargs: frame,
    )
    monkeypatch.setattr(
        research_inputs,
        "load_official_no_data_dates",
        lambda **kwargs: set(),
    )

    result = research_inputs.load_research_eligible_tw_bars(
        ["2330"],
        start_date=trading_date,
        end_date=trading_date,
    )

    assert result == {
        "2330": [
            research_inputs.EligibleBar(
                date=trading_date,
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                source=research_inputs.official_daily.SOURCE_TWSE,
                raw_payload_id=21,
            )
        ]
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, None),
        (False, None),
        (np.int64(7), 7),
        (np.float64(8.0), 8),
        (np.nan, None),
        (np.float64(8.5), None),
        ("invalid", None),
    ],
)
def test_as_raw_payload_id_normalizes_integral_values(value, expected):
    result = research_inputs._as_raw_payload_id(value)

    assert result == expected
    if expected is not None:
        assert type(result) is int


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (pd.NaT, None),
        (date(2024, 1, 4), date(2024, 1, 4)),
        (datetime(2024, 1, 4, 12, 30), date(2024, 1, 4)),
        ("2024-01-04", date(2024, 1, 4)),
    ],
)
def test_as_date_normalizes_supported_values(value, expected):
    assert research_inputs._as_date(value) == expected


@pytest.mark.parametrize(
    "value",
    [None, "invalid", np.nan, np.inf, 0, -1],
)
def test_as_positive_float_rejects_invalid_values(value):
    assert research_inputs._as_positive_float(value) is None


def test_load_research_eligible_tw_bars_skips_invalid_dates_and_ohlc(
    monkeypatch,
):
    trading_date = pd.Timestamp("2024-01-04")
    frame = pd.DataFrame(
        [
            {
                "date": trading_date,
                "symbol": "2330",
                "open": "100.0",
                "high": np.float64(102.0),
                "low": 99,
                "close": 101.0,
                "source": research_inputs.official_daily.SOURCE_TWSE,
                "raw_payload_id": np.int64(21),
            },
            {
                "date": trading_date,
                "symbol": "2317",
                "open": None,
                "high": 92.0,
                "low": 89.0,
                "close": 91.0,
                "source": research_inputs.official_daily.SOURCE_TWSE,
                "raw_payload_id": np.float64(22.0),
            },
            {
                "date": pd.NaT,
                "symbol": "2454",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "source": research_inputs.official_daily.SOURCE_TWSE,
                "raw_payload_id": np.nan,
            },
            {
                "date": "not-a-date",
                "symbol": "2603",
                "open": 100.0,
                "high": np.inf,
                "low": 99.0,
                "close": 101.0,
                "source": research_inputs.official_daily.SOURCE_TWSE,
                "raw_payload_id": 23.5,
            },
        ]
    ).set_index(["date", "symbol"])
    monkeypatch.setattr(research_inputs, "get_data", lambda *args, **kwargs: frame)
    monkeypatch.setattr(
        research_inputs,
        "load_official_no_data_dates",
        lambda **kwargs: set(),
    )

    result = research_inputs.load_research_eligible_tw_bars(
        ["2330", "2317", "2454", "2603"],
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 5),
    )

    assert result == {
        "2330": [
            research_inputs.EligibleBar(
                date=date(2024, 1, 4),
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                source=research_inputs.official_daily.SOURCE_TWSE,
                raw_payload_id=21,
            )
        ]
    }
