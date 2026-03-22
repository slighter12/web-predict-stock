import pandas as pd
import pytest
import requests

from scripts import market_data_ingestion as scraper


def test_validate_ohlcv_with_report_tracks_removed_rows():
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            },
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            },
            {
                "date": "2024-01-03",
                "symbol": "2330",
                "open": None,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            },
            {
                "date": "2024-01-04",
                "symbol": "2330",
                "open": -1.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            },
        ]
    )

    cleaned, report = scraper.validate_ohlcv_with_report(df, label="test")

    assert len(cleaned) == 1
    assert report.duplicates_removed == 1
    assert report.null_rows_removed == 1
    assert report.invalid_rows_removed == 1
    assert report.output_rows == 1


def test_load_to_db_empty_summary():
    summary = scraper.load_to_db(pd.DataFrame())

    assert summary["validated_rows"] == 0
    assert summary["upserted_rows"] == 0
    assert summary["official_overrides"] == 0


def test_ingest_symbol_tw_calls_daily_update(monkeypatch):
    backfill_df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "market": "TW",
                "source": "yfinance",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    backfill_meta = scraper.RawTraceMetadata(
        raw_payload_id=1,
        archive_object_reference="raw_ingest_audit:1",
        parser_version=scraper.YFINANCE_PARSER_VERSION,
    )
    daily_df = pd.DataFrame(
        [
            {
                "date": "2024-01-03",
                "symbol": "2330",
                "market": "TW",
                "source": "twse",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    daily_meta = scraper.RawTraceMetadata(
        raw_payload_id=2,
        archive_object_reference="raw_ingest_audit:2",
        parser_version=scraper.TWSE_PARSER_VERSION,
    )
    calls = []

    monkeypatch.setattr(
        scraper, "backfill_history", lambda **kwargs: (backfill_df, backfill_meta)
    )
    monkeypatch.setattr(
        scraper, "scrape_daily_twse", lambda **kwargs: (daily_df, daily_meta)
    )

    def fake_load(df, metadata=None):
        calls.append(df.iloc[0]["source"] if not df.empty else "empty")
        return {
            "validated_rows": len(df),
            "official_overrides": 1
            if not df.empty and df.iloc[0]["source"] == "twse"
            else 0,
        }

    monkeypatch.setattr(scraper, "load_to_db", fake_load)

    summary = scraper.ingest_symbol(symbol="2330", market="TW", years=5)

    assert calls == ["yfinance", "twse"]
    assert summary["daily_update"]["official_overrides"] == 1


def test_ingest_symbol_us_skips_daily_update(monkeypatch):
    backfill_df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "AAPL",
                "market": "US",
                "source": "yfinance",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    backfill_meta = scraper.RawTraceMetadata(
        raw_payload_id=1,
        archive_object_reference="raw_ingest_audit:1",
        parser_version=scraper.YFINANCE_PARSER_VERSION,
    )

    monkeypatch.setattr(
        scraper, "backfill_history", lambda **kwargs: (backfill_df, backfill_meta)
    )
    monkeypatch.setattr(
        scraper,
        "load_to_db",
        lambda df, metadata=None: {"validated_rows": len(df), "official_overrides": 0},
    )

    summary = scraper.ingest_symbol(symbol="AAPL", market="US", years=5)

    assert summary["backfill"]["validated_rows"] == 1
    assert summary["daily_update"]["validated_rows"] == 0


def test_scrape_twse_data_records_success(monkeypatch):
    class FakeResponse:
        def __init__(self):
            self.text = (
                '{"stat":"OK","fields":["日期","成交股數","成交金額","開盤價","最高價","最低價","收盤價","漲跌價差","成交筆數"],'
                '"data":[["103/01/02","1000","0","10","11","9","10.5","0","10"]]}'
            )

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "stat": "OK",
                "fields": [
                    "日期",
                    "成交股數",
                    "成交金額",
                    "開盤價",
                    "最高價",
                    "最低價",
                    "收盤價",
                    "漲跌價差",
                    "成交筆數",
                ],
                "data": [
                    ["103/01/02", "1000", "0", "10", "11", "9", "10.5", "0", "10"],
                ],
            }

    records = []
    monkeypatch.setattr(
        scraper, "_request_twse_daily_report", lambda *args, **kwargs: FakeResponse()
    )
    monkeypatch.setattr(
        scraper,
        "persist_raw_ingest_record",
        lambda **kwargs: (records.append(kwargs), 101)[1],
    )

    cleaned, metadata = scraper.scrape_twse_data(symbol="2330", date_str="20240101")
    assert not cleaned.empty
    assert len(records) == 1
    assert records[0]["fetch_status"] == "success"
    assert "symbol=2330" in records[0]["expected_symbol_context"]
    assert metadata is not None
    assert metadata.raw_payload_id == 101
    assert metadata.archive_object_reference == "raw_ingest_audit:101"
    assert metadata.parser_version == scraper.TWSE_PARSER_VERSION


def test_persist_raw_ingest_record_failure_is_not_swallowed(monkeypatch):
    class BrokenTransaction:
        def __enter__(self):
            raise RuntimeError("db unavailable")

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(scraper.engine, "begin", lambda: BrokenTransaction())

    with pytest.raises(RuntimeError, match="Failed to persist raw ingest audit record"):
        scraper.persist_raw_ingest_record(
            source_name=scraper.SOURCE_TWSE,
            symbol="2330",
            market="TW",
            parser_version=scraper.TWSE_PARSER_VERSION,
            fetch_status=scraper.FETCH_STATUS_SUCCESS,
            expected_symbol_context="symbol=2330;market=TW",
            payload_body='{"stat":"OK"}',
        )


def test_scrape_twse_data_records_failure(monkeypatch):
    def raise_exc(*args, **kwargs):
        raise requests.exceptions.RequestException("twse down")

    records = []
    monkeypatch.setattr(scraper, "_request_twse_daily_report", raise_exc)
    monkeypatch.setattr(
        scraper, "persist_raw_ingest_record", lambda **kwargs: records.append(kwargs)
    )

    result, metadata = scraper.scrape_twse_data(symbol="2330", date_str="20240101")
    assert result.empty
    assert metadata is None
    assert len(records) == 1
    assert records[0]["fetch_status"] == "failed"


def test_backfill_history_records_success(monkeypatch):
    class FakeTicker:
        def __init__(self, symbol: str):
            pass

        def history(self, start, auto_adjust, actions):
            idx = pd.DatetimeIndex(["2024-01-02"], name="Date")
            return pd.DataFrame(
                {
                    "Open": [10.0],
                    "High": [11.0],
                    "Low": [9.0],
                    "Close": [10.5],
                    "Volume": [100],
                },
                index=idx,
            )

    records = []
    monkeypatch.setattr(scraper.yf, "Ticker", lambda symbol: FakeTicker(symbol))
    monkeypatch.setattr(
        scraper,
        "persist_raw_ingest_record",
        lambda **kwargs: (records.append(kwargs), 202)[1],
    )

    cleaned, metadata = scraper.backfill_history(symbol="2330", years=1, market="TW")
    assert not cleaned.empty
    assert len(records) == 1
    assert records[0]["fetch_status"] == "success"
    assert '"Open"' in records[0]["payload_body"]
    assert '"symbol"' not in records[0]["payload_body"]
    assert metadata is not None
    assert metadata.raw_payload_id == 202
    assert metadata.archive_object_reference == "raw_ingest_audit:202"
    assert metadata.parser_version == scraper.YFINANCE_PARSER_VERSION


def test_backfill_history_records_failure(monkeypatch):
    def bad_ticker(*args, **kwargs):
        raise ValueError("network error")

    records = []
    monkeypatch.setattr(scraper.yf, "Ticker", bad_ticker)
    monkeypatch.setattr(
        scraper, "persist_raw_ingest_record", lambda **kwargs: records.append(kwargs)
    )

    result, metadata = scraper.backfill_history(symbol="2330", years=1, market="TW")
    assert result.empty
    assert metadata is None
    assert len(records) == 1
    assert records[0]["fetch_status"] == "failed"


def test_scrape_twse_data_audit_failure_blocks_scrape(monkeypatch):
    """Success-path persist_raw_ingest_record failure should block normalized ingest."""

    class FakeResponse:
        def __init__(self):
            self.text = '{"stat":"OK"}'

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "stat": "OK",
                "fields": [
                    "日期",
                    "成交股數",
                    "成交金額",
                    "開盤價",
                    "最高價",
                    "最低價",
                    "收盤價",
                    "漲跌價差",
                    "成交筆數",
                ],
                "data": [
                    ["103/01/02", "1000", "0", "10", "11", "9", "10.5", "0", "10"],
                ],
            }

    monkeypatch.setattr(
        scraper, "_request_twse_daily_report", lambda *args, **kwargs: FakeResponse()
    )

    def failing_persist(**kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(scraper, "persist_raw_ingest_record", failing_persist)

    with pytest.raises(RuntimeError, match="db unavailable"):
        scraper.scrape_twse_data(symbol="2330", date_str="20240101")


def test_backfill_history_audit_failure_blocks_ingest(monkeypatch):
    class FakeTicker:
        def __init__(self, symbol: str):
            pass

        def history(self, start, auto_adjust, actions):
            idx = pd.DatetimeIndex(["2024-01-02"], name="Date")
            return pd.DataFrame(
                {
                    "Open": [10.0],
                    "High": [11.0],
                    "Low": [9.0],
                    "Close": [10.5],
                    "Volume": [100],
                },
                index=idx,
            )

    monkeypatch.setattr(scraper.yf, "Ticker", lambda symbol: FakeTicker(symbol))

    def failing_persist(**kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(scraper, "persist_raw_ingest_record", failing_persist)

    with pytest.raises(RuntimeError, match="db unavailable"):
        scraper.backfill_history(symbol="2330", years=1, market="TW")


def test_parse_twse_payload_body_replays_successfully():
    payload = """
    {
      "stat": "OK",
      "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數"],
      "data": [["113/01/02", "1000", "0", "10", "11", "9", "10.5", "0", "10"]]
    }
    """

    cleaned, metadata = scraper.parse_twse_payload_body(
        payload_body=payload, symbol="2330", raw_payload_id=99
    )

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["source"] == scraper.SOURCE_TWSE
    assert metadata.raw_payload_id == 99
    assert metadata.archive_object_reference == "raw_ingest_audit:99"


def test_parse_yfinance_payload_body_replays_successfully():
    payload_df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2024-01-02"]),
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [10.5],
            "Volume": [100],
        }
    )
    payload = payload_df.to_json(orient="table", date_format="iso")

    cleaned, metadata = scraper.parse_yfinance_payload_body(
        payload_body=payload,
        symbol="2330",
        market="TW",
        raw_payload_id=77,
    )

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["source"] == scraper.SOURCE_YFINANCE
    assert metadata.parser_version == scraper.YFINANCE_PARSER_VERSION


def test_replay_raw_ingest_record_rejects_unknown_source():
    raw_record = type(
        "RawRecord",
        (),
        {
            "id": 12,
            "source_name": "manual",
            "symbol": "2330",
            "market": "TW",
            "payload_body": '{"ok": true}',
        },
    )()

    with pytest.raises(ValueError, match="Unsupported source"):
        scraper.replay_raw_ingest_record(raw_record)


def test_ingest_symbol_summary_includes_stage_metadata(monkeypatch):
    backfill_df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "market": "TW",
                "source": "yfinance",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    backfill_meta = scraper.RawTraceMetadata(
        raw_payload_id=10,
        archive_object_reference="raw_ingest_audit:10",
        parser_version=scraper.YFINANCE_PARSER_VERSION,
    )
    daily_df = pd.DataFrame(
        [
            {
                "date": "2024-01-03",
                "symbol": "2330",
                "market": "TW",
                "source": "twse",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    daily_meta = scraper.RawTraceMetadata(
        raw_payload_id=11,
        archive_object_reference="raw_ingest_audit:11",
        parser_version=scraper.TWSE_PARSER_VERSION,
    )

    monkeypatch.setattr(
        scraper, "backfill_history", lambda **kwargs: (backfill_df, backfill_meta)
    )
    monkeypatch.setattr(
        scraper, "scrape_daily_twse", lambda **kwargs: (daily_df, daily_meta)
    )
    monkeypatch.setattr(
        scraper,
        "load_to_db",
        lambda df, metadata=None: {
            "input_rows": len(df),
            "validated_rows": len(df),
            "dropped_rows": 0,
            "duplicates_removed": 0,
            "null_rows_removed": 0,
            "invalid_rows_removed": 0,
            "gap_warnings": 0,
            "upserted_rows": len(df),
            "official_overrides": 1
            if metadata and metadata.parser_version == scraper.TWSE_PARSER_VERSION
            else 0,
        },
    )

    summary = scraper.ingest_symbol(symbol="2330", market="TW", years=5)

    assert summary["backfill"]["raw_payload_id"] == 10
    assert summary["backfill"]["parser_version"] == scraper.YFINANCE_PARSER_VERSION
    assert summary["daily_update"]["raw_payload_id"] == 11
    assert summary["daily_update"]["official_overrides"] == 1
