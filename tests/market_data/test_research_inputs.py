from datetime import date

import pandas as pd

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
