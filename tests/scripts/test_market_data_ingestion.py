from datetime import date

import pandas as pd
import pytest
import requests

from scripts import market_data_ingestion as scraper


class _FakeResult:
    def __init__(self, *, scalar_value=None, rowcount=None):
        self._scalar_value = scalar_value
        self.rowcount = rowcount

    def scalar_one(self):
        return self._scalar_value


class _FakeTransaction:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.transaction_depth += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.connection.transaction_depth -= 1
        return False


class _FakeConnection:
    def __init__(self, execute_plan=None):
        self.execute_plan = list(execute_plan or [])
        self.statements = []
        self.to_sql_names = []
        self.dropped_tables = []
        self.transaction_depth = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def begin(self):
        return _FakeTransaction(self)

    def in_transaction(self):
        return self.transaction_depth > 0

    def execute(self, statement, params=None):
        sql = str(statement).strip()
        self.statements.append((sql, params))
        if sql.startswith("DROP TABLE IF EXISTS "):
            self.dropped_tables.append(sql.removeprefix("DROP TABLE IF EXISTS ").strip())
        if not self.execute_plan:
            return _FakeResult()
        action = self.execute_plan.pop(0)
        if isinstance(action, Exception):
            raise action
        return action


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


def test_load_to_db_uses_unique_staging_tables_and_cleans_up(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "market": "TW",
                "source": scraper.SOURCE_TWSE,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    connections = []
    execute_plans = [
        [_FakeResult(), _FakeResult(scalar_value=1), _FakeResult(rowcount=1), _FakeResult()],
        [_FakeResult(), _FakeResult(scalar_value=1), _FakeResult(rowcount=1), _FakeResult()],
    ]

    def fake_connect():
        connection = _FakeConnection(execute_plan=execute_plans.pop(0))
        connections.append(connection)
        return connection

    def fake_to_sql(self, name, conn, if_exists="fail", index=True, **kwargs):
        conn.to_sql_names.append((name, if_exists, index))

    monkeypatch.setattr(scraper.engine, "connect", fake_connect)
    monkeypatch.setattr(
        scraper,
        "validate_ohlcv_with_report",
        lambda frame, label: (
            frame.copy(),
            scraper.QualityReport(input_rows=len(frame), output_rows=len(frame)),
        ),
    )
    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)

    summary_a = scraper.load_to_db(df)
    summary_b = scraper.load_to_db(df)

    first_name = connections[0].to_sql_names[0][0]
    second_name = connections[1].to_sql_names[0][0]
    first_create_sql = connections[0].statements[0][0]
    second_create_sql = connections[1].statements[0][0]
    assert summary_a["official_overrides"] == 1
    assert summary_a["upserted_rows"] == 1
    assert summary_b["official_overrides"] == 1
    assert summary_b["upserted_rows"] == 1
    assert first_name != second_name
    assert connections[0].to_sql_names[0][1] == "append"
    assert connections[1].to_sql_names[0][1] == "append"
    assert first_create_sql.startswith("CREATE TEMP TABLE")
    assert second_create_sql.startswith("CREATE TEMP TABLE")
    assert "ON COMMIT DROP" in first_create_sql
    assert "ON COMMIT DROP" in second_create_sql
    assert connections[0].dropped_tables == [first_name]
    assert connections[1].dropped_tables == [second_name]


def test_load_to_db_cleans_up_staging_table_on_failure(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "market": "TW",
                "source": scraper.SOURCE_TWSE,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    connection = _FakeConnection(
        execute_plan=[
            _FakeResult(),
            _FakeResult(scalar_value=1),
            RuntimeError("insert failed"),
            _FakeResult(),
        ]
    )

    def fake_to_sql(self, name, conn, if_exists="fail", index=True, **kwargs):
        conn.to_sql_names.append((name, if_exists, index))

    monkeypatch.setattr(scraper.engine, "connect", lambda: connection)
    monkeypatch.setattr(
        scraper,
        "validate_ohlcv_with_report",
        lambda frame, label: (
            frame.copy(),
            scraper.QualityReport(input_rows=len(frame), output_rows=len(frame)),
        ),
    )
    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)

    with pytest.raises(RuntimeError, match="insert failed"):
        scraper.load_to_db(df)

    staging_name = connection.to_sql_names[0][0]
    assert connection.statements[0][0].startswith("CREATE TEMP TABLE")
    assert connection.dropped_tables == [staging_name]


def test_load_to_db_cleanup_failure_does_not_override_insert_error(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "symbol": "2330",
                "market": "TW",
                "source": scraper.SOURCE_TWSE,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    connection = _FakeConnection(
        execute_plan=[
            _FakeResult(),
            _FakeResult(scalar_value=1),
            RuntimeError("insert failed"),
            RuntimeError("drop failed"),
        ]
    )

    def fake_to_sql(self, name, conn, if_exists="fail", index=True, **kwargs):
        conn.to_sql_names.append((name, if_exists, index))

    monkeypatch.setattr(scraper.engine, "connect", lambda: connection)
    monkeypatch.setattr(
        scraper,
        "validate_ohlcv_with_report",
        lambda frame, label: (
            frame.copy(),
            scraper.QualityReport(input_rows=len(frame), output_rows=len(frame)),
        ),
    )
    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)

    with pytest.raises(RuntimeError, match="insert failed"):
        scraper.load_to_db(df)

    staging_name = connection.to_sql_names[0][0]
    assert connection.statements[0][0].startswith("CREATE TEMP TABLE")
    assert connection.dropped_tables == [staging_name]


def test_load_minute_to_db_uses_unique_staging_tables_and_cleans_up(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "trading_date": date(2024, 1, 2),
                "bar_ts": pd.Timestamp("2024-01-02T01:00:00Z"),
                "symbol": "2330",
                "market": "TW",
                "source": scraper.SOURCE_YFINANCE_MINUTE_1M,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    connections = []
    execute_plans = [
        [_FakeResult(), _FakeResult(rowcount=1), _FakeResult()],
        [_FakeResult(), _FakeResult(rowcount=1), _FakeResult()],
    ]

    def fake_connect():
        connection = _FakeConnection(execute_plan=execute_plans.pop(0))
        connections.append(connection)
        return connection

    def fake_to_sql(self, name, conn, if_exists="fail", index=True, **kwargs):
        conn.to_sql_names.append((name, if_exists, index))

    monkeypatch.setattr(scraper.engine, "connect", fake_connect)
    monkeypatch.setattr(
        scraper,
        "validate_minute_ohlcv_with_report",
        lambda frame, label: (
            frame.copy(),
            scraper.QualityReport(input_rows=len(frame), output_rows=len(frame)),
        ),
    )
    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)

    summary_a = scraper.load_minute_to_db(df)
    summary_b = scraper.load_minute_to_db(df)

    first_name = connections[0].to_sql_names[0][0]
    second_name = connections[1].to_sql_names[0][0]
    first_create_sql = connections[0].statements[0][0]
    second_create_sql = connections[1].statements[0][0]
    assert summary_a["upserted_rows"] == 1
    assert summary_b["upserted_rows"] == 1
    assert first_name != second_name
    assert connections[0].to_sql_names[0][1] == "append"
    assert connections[1].to_sql_names[0][1] == "append"
    assert first_create_sql.startswith("CREATE TEMP TABLE")
    assert second_create_sql.startswith("CREATE TEMP TABLE")
    assert "ON COMMIT DROP" in first_create_sql
    assert "ON COMMIT DROP" in second_create_sql
    assert connections[0].dropped_tables == [first_name]
    assert connections[1].dropped_tables == [second_name]


def test_load_minute_to_db_cleans_up_staging_table_on_failure(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "trading_date": date(2024, 1, 2),
                "bar_ts": pd.Timestamp("2024-01-02T01:00:00Z"),
                "symbol": "2330",
                "market": "TW",
                "source": scraper.SOURCE_YFINANCE_MINUTE_1M,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    connection = _FakeConnection(
        execute_plan=[
            _FakeResult(),
            RuntimeError("insert failed"),
            _FakeResult(),
        ]
    )

    def fake_to_sql(self, name, conn, if_exists="fail", index=True, **kwargs):
        conn.to_sql_names.append((name, if_exists, index))

    monkeypatch.setattr(scraper.engine, "connect", lambda: connection)
    monkeypatch.setattr(
        scraper,
        "validate_minute_ohlcv_with_report",
        lambda frame, label: (
            frame.copy(),
            scraper.QualityReport(input_rows=len(frame), output_rows=len(frame)),
        ),
    )
    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)

    with pytest.raises(RuntimeError, match="insert failed"):
        scraper.load_minute_to_db(df)

    staging_name = connection.to_sql_names[0][0]
    assert connection.statements[0][0].startswith("CREATE TEMP TABLE")
    assert connection.dropped_tables == [staging_name]


def test_load_minute_to_db_cleanup_failure_does_not_override_insert_error(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "trading_date": date(2024, 1, 2),
                "bar_ts": pd.Timestamp("2024-01-02T01:00:00Z"),
                "symbol": "2330",
                "market": "TW",
                "source": scraper.SOURCE_YFINANCE_MINUTE_1M,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            }
        ]
    )
    connection = _FakeConnection(
        execute_plan=[
            _FakeResult(),
            RuntimeError("insert failed"),
            RuntimeError("drop failed"),
        ]
    )

    def fake_to_sql(self, name, conn, if_exists="fail", index=True, **kwargs):
        conn.to_sql_names.append((name, if_exists, index))

    monkeypatch.setattr(scraper.engine, "connect", lambda: connection)
    monkeypatch.setattr(
        scraper,
        "validate_minute_ohlcv_with_report",
        lambda frame, label: (
            frame.copy(),
            scraper.QualityReport(input_rows=len(frame), output_rows=len(frame)),
        ),
    )
    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)

    with pytest.raises(RuntimeError, match="insert failed"):
        scraper.load_minute_to_db(df)

    staging_name = connection.to_sql_names[0][0]
    assert connection.statements[0][0].startswith("CREATE TEMP TABLE")
    assert connection.dropped_tables == [staging_name]


def test_sanitize_numeric_value_strips_html_tags():
    assert scraper._sanitize_numeric_value("<p style='color:red'>+1,234</p>") == 1234.0
    assert scraper._sanitize_numeric_value("<span>--</span>") == 0.0


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
    monkeypatch.setattr(
        scraper,
        "supplement_yahoo_minute_history",
        lambda **kwargs: {
            "status": "succeeded",
            "window_start": date(2024, 1, 1),
            "window_end": date(2024, 1, 31),
            "segment_count": 1,
            "segments_succeeded": 1,
            "segments_failed": 0,
            "covered_trading_days": 1,
            "input_rows": 2,
            "upserted_rows": 2,
            "duplicates_removed": 0,
            "skipped_reason": None,
        },
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
    assert summary["minute_supplement"]["status"] == "succeeded"


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
    assert summary["minute_supplement"]["status"] == "skipped"
    assert summary["minute_supplement"]["skipped_reason"] == "market_not_supported"


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


def test_parse_yfinance_minute_payload_body_replays_successfully():
    payload_df = pd.DataFrame(
        {
            "Datetime": pd.to_datetime(["2024-01-02 09:00:00+08:00"]),
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [10.5],
            "Volume": [100],
        }
    )
    payload = payload_df.to_json(orient="table", date_format="iso")

    cleaned, metadata = scraper.parse_yfinance_minute_payload_body(
        payload_body=payload,
        symbol="2330",
        market="TW",
        raw_payload_id=78,
    )

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["source"] == scraper.SOURCE_YFINANCE_MINUTE_1M
    assert cleaned.iloc[0]["trading_date"] == date(2024, 1, 2)
    assert metadata.raw_payload_id == 78
    assert metadata.parser_version == scraper.YFINANCE_MINUTE_PARSER_VERSION


def test_build_minute_fetch_segments_groups_missing_days():
    window_start = pd.Timestamp("2024-01-01 10:00:00", tz="Asia/Taipei").to_pydatetime()
    window_end = pd.Timestamp("2024-01-31 15:00:00", tz="Asia/Taipei").to_pydatetime()

    segments = scraper._build_minute_fetch_segments(
        missing_days=[
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 20),
        ],
        window_start=window_start,
        window_end=window_end,
    )

    assert len(segments) == 2
    assert segments[0][0].date() == date(2024, 1, 2)
    assert segments[0][1].date() == date(2024, 1, 9)
    assert segments[1][0].date() == date(2024, 1, 20)


def test_supplement_yahoo_minute_history_skips_historical_override(monkeypatch):
    monkeypatch.setattr(
        scraper,
        "_resolve_minute_window",
        lambda reference_time=None: (
            pd.Timestamp("2024-01-01 00:00:01", tz="Asia/Taipei").to_pydatetime(),
            pd.Timestamp("2024-01-31 12:00:00", tz="Asia/Taipei").to_pydatetime(),
        ),
    )

    summary = scraper.supplement_yahoo_minute_history(
        symbol="2330",
        market="TW",
        date_str="20240130",
    )

    assert summary["status"] == "skipped"
    assert summary["skipped_reason"] == "historical_date_override_not_supported"


def test_supplement_yahoo_minute_history_fetches_missing_segments(monkeypatch):
    window_start = pd.Timestamp("2024-01-01 00:00:01", tz="Asia/Taipei").to_pydatetime()
    window_end = pd.Timestamp("2024-01-31 12:00:00", tz="Asia/Taipei").to_pydatetime()
    segment_calls = []
    covered_calls = {"count": 0}

    monkeypatch.setattr(
        scraper,
        "_resolve_minute_window",
        lambda reference_time=None: (window_start, window_end),
    )
    monkeypatch.setattr(
        scraper,
        "_list_symbol_daily_trading_days",
        lambda **kwargs: [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 20)],
    )

    def fake_minute_days(**kwargs):
        covered_calls["count"] += 1
        if covered_calls["count"] == 1:
            return [date(2024, 1, 2)]
        return [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 20)]

    monkeypatch.setattr(scraper, "_list_symbol_minute_trading_days", fake_minute_days)
    monkeypatch.setattr(scraper.yf, "Ticker", lambda symbol: object())

    def fake_fetch(**kwargs):
        segment_calls.append((kwargs["start_dt"], kwargs["end_dt"]))
        segment_start = kwargs["start_dt"].astimezone(scraper.TW_TIMEZONE)
        df = pd.DataFrame(
            [
                {
                    "trading_date": segment_start.date(),
                    "bar_ts": kwargs["start_dt"].astimezone(scraper.timezone.utc),
                    "symbol": "2330",
                    "market": "TW",
                    "source": scraper.SOURCE_YFINANCE_MINUTE_1M,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.5,
                    "volume": 100,
                }
            ]
        )
        return (
            df,
            scraper.RawTraceMetadata(
                raw_payload_id=501,
                archive_object_reference="raw_ingest_audit:501",
                parser_version=scraper.YFINANCE_MINUTE_PARSER_VERSION,
            ),
        )

    monkeypatch.setattr(scraper, "fetch_yfinance_minute_segment", fake_fetch)
    monkeypatch.setattr(
        scraper,
        "load_minute_to_db",
        lambda df, metadata=None: {
            "input_rows": len(df),
            "validated_rows": len(df),
            "duplicates_removed": 0,
            "upserted_rows": len(df),
        },
    )

    summary = scraper.supplement_yahoo_minute_history(
        symbol="2330",
        market="TW",
        date_str="20240131",
    )

    assert len(segment_calls) == 2
    assert summary["status"] == "succeeded"
    assert summary["segment_count"] == 2
    assert summary["segments_succeeded"] == 2
    assert summary["segments_failed"] == 0
    assert summary["covered_trading_days"] == 3
    assert summary["input_rows"] == 2
    assert summary["upserted_rows"] == 2


def test_parse_twse_mi_index_payload_body_replays_successfully():
    payload = """
    {
      "stat": "OK",
      "tables": [
        {
          "fields": ["指數", "收盤指數"],
          "data": [["發行量加權股價指數", "20,000"]]
        },
        {
          "fields": [
            "證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額",
            "開盤價", "最高價", "最低價", "收盤價", "漲跌(+/-)", "漲跌價差",
            "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量", "本益比"
          ],
          "data": [
            ["2330", "台積電", "1,000", "10", "10,000", "10", "11", "9", "10.5", "+", "0.5", "10.5", "1", "10.6", "2", "20"]
          ]
        }
      ]
    }
    """

    cleaned, metadata = scraper.parse_twse_mi_index_payload_body(
        payload,
        trading_date=date(2024, 1, 2),
        raw_payload_id=301,
    )

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["symbol"] == "2330"
    assert cleaned.iloc[0]["source"] == scraper.SOURCE_TWSE_MI_INDEX
    assert metadata.raw_payload_id == 301
    assert metadata.parser_version == scraper.TWSE_MI_INDEX_PARSER_VERSION


def test_parse_tpex_aftertrading_payload_body_replays_successfully():
    payload = """
    {
      "stat": "ok",
      "tables": [
        {
          "fields": [
            "Code", "Name", "Close ", "Change (%)", "Open ", "High ", "Low",
            "Trade Vol. (shares) ", "Trade Amt. (NTD)"
          ],
          "data": [
            ["8049", "ABC", "10.5", "+0.2", "10", "11", "9", "1,000", "10,000"]
          ]
        }
      ]
    }
    """

    cleaned, metadata = scraper.parse_tpex_aftertrading_payload_body(
        payload,
        trading_date=date(2024, 1, 2),
        raw_payload_id=302,
    )

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["symbol"] == "8049"
    assert cleaned.iloc[0]["source"] == scraper.SOURCE_TPEX_AFTERTRADING_OTC
    assert metadata.raw_payload_id == 302
    assert metadata.parser_version == scraper.TPEX_AFTERTRADING_OTC_PARSER_VERSION


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


def test_ingest_tw_market_batch_filters_to_active_universe(monkeypatch):
    twse_df = pd.DataFrame(
        [
            {
                "date": date(2024, 1, 2),
                "symbol": "2330",
                "market": "TW",
                "source": scraper.SOURCE_TWSE_MI_INDEX,
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "volume": 100,
            },
            {
                "date": date(2024, 1, 2),
                "symbol": "9999",
                "market": "TW",
                "source": scraper.SOURCE_TWSE_MI_INDEX,
                "open": 12.0,
                "high": 13.0,
                "low": 11.0,
                "close": 12.5,
                "volume": 200,
            },
        ]
    )
    tpex_df = pd.DataFrame(
        [
            {
                "date": date(2024, 1, 2),
                "symbol": "8049",
                "market": "TW",
                "source": scraper.SOURCE_TPEX_AFTERTRADING_OTC,
                "open": 20.0,
                "high": 21.0,
                "low": 19.0,
                "close": 20.5,
                "volume": 300,
            }
        ]
    )
    captured = {}

    monkeypatch.setattr(
        scraper,
        "resolve_tw_active_universe",
        lambda: {"TWSE": {"2330", "2317"}, "TPEX": {"8049"}},
    )
    monkeypatch.setattr(
        scraper,
        "fetch_twse_market_batch",
        lambda trading_date: scraper.BatchFetchResult(
            source_name=scraper.SOURCE_TWSE_MI_INDEX,
            dataframe=twse_df,
            raw_row_count=len(twse_df),
            metadata=scraper.RawTraceMetadata(
                raw_payload_id=401,
                archive_object_reference="raw_ingest_audit:401",
                parser_version=scraper.TWSE_MI_INDEX_PARSER_VERSION,
            ),
        ),
    )
    monkeypatch.setattr(
        scraper,
        "fetch_tpex_market_batch",
        lambda trading_date: scraper.BatchFetchResult(
            source_name=scraper.SOURCE_TPEX_AFTERTRADING_OTC,
            dataframe=tpex_df,
            raw_row_count=len(tpex_df),
            metadata=scraper.RawTraceMetadata(
                raw_payload_id=402,
                archive_object_reference="raw_ingest_audit:402",
                parser_version=scraper.TPEX_AFTERTRADING_OTC_PARSER_VERSION,
            ),
        ),
    )

    def fake_load(df, metadata=None):
        captured["symbols"] = sorted(df["symbol"].tolist())
        captured["raw_payload_ids"] = sorted(df["raw_payload_id"].tolist())
        return {
            "input_rows": len(df),
            "validated_rows": len(df),
            "dropped_rows": 0,
            "duplicates_removed": 0,
            "null_rows_removed": 0,
            "invalid_rows_removed": 0,
            "gap_warnings": 0,
            "upserted_rows": len(df),
            "official_overrides": 0,
        }

    monkeypatch.setattr(scraper, "load_to_db", fake_load)

    summary = scraper.ingest_tw_market_batch(trading_date=date(2024, 1, 2))

    assert captured["symbols"] == ["2330", "8049"]
    assert captured["raw_payload_ids"] == [401, 402]
    assert summary["universe_count"] == 3
    assert summary["twse_rows"] == 2
    assert summary["tpex_rows"] == 1
    assert summary["filtered_rows"] == 2
    assert summary["missing_symbol_count"] == 1
    assert summary["upserted_rows"] == 2
    assert summary["raw_payload_ids"] == [401, 402]
    assert summary["errors"] == []


def test_ingest_tw_market_batch_collects_source_errors(monkeypatch):
    tpex_df = pd.DataFrame(
        [
            {
                "date": date(2024, 1, 2),
                "symbol": "8049",
                "market": "TW",
                "source": scraper.SOURCE_TPEX_AFTERTRADING_OTC,
                "open": 20.0,
                "high": 21.0,
                "low": 19.0,
                "close": 20.5,
                "volume": 300,
            }
        ]
    )

    monkeypatch.setattr(
        scraper,
        "resolve_tw_active_universe",
        lambda: {"TWSE": {"2330"}, "TPEX": {"8049"}},
    )
    monkeypatch.setattr(
        scraper,
        "fetch_twse_market_batch",
        lambda trading_date: scraper.BatchFetchResult(
            source_name=scraper.SOURCE_TWSE_MI_INDEX,
            dataframe=pd.DataFrame(),
            raw_row_count=0,
            error_message="TWSE batch fetch failed: timeout",
        ),
    )
    monkeypatch.setattr(
        scraper,
        "fetch_tpex_market_batch",
        lambda trading_date: scraper.BatchFetchResult(
            source_name=scraper.SOURCE_TPEX_AFTERTRADING_OTC,
            dataframe=tpex_df,
            raw_row_count=len(tpex_df),
            metadata=scraper.RawTraceMetadata(
                raw_payload_id=501,
                archive_object_reference="raw_ingest_audit:501",
                parser_version=scraper.TPEX_AFTERTRADING_OTC_PARSER_VERSION,
            ),
        ),
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
            "official_overrides": 0,
        },
    )

    summary = scraper.ingest_tw_market_batch(trading_date=date(2024, 1, 2))

    assert summary["filtered_rows"] == 1
    assert summary["missing_symbol_count"] == 1
    assert summary["raw_payload_ids"] == [501]
    assert summary["errors"] == [
        {
            "source_name": scraper.SOURCE_TWSE_MI_INDEX,
            "message": "TWSE batch fetch failed: timeout",
        }
    ]


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
    monkeypatch.setattr(
        scraper,
        "supplement_yahoo_minute_history",
        lambda **kwargs: {
            "status": "succeeded",
            "window_start": date(2026, 2, 28),
            "window_end": date(2026, 3, 29),
            "segment_count": 1,
            "segments_succeeded": 1,
            "segments_failed": 0,
            "covered_trading_days": 2,
            "input_rows": 2,
            "upserted_rows": 2,
            "duplicates_removed": 0,
            "skipped_reason": None,
        },
    )

    summary = scraper.ingest_symbol(symbol="2330", market="TW", years=5)

    assert summary["backfill"]["raw_payload_id"] == 10
    assert summary["backfill"]["parser_version"] == scraper.YFINANCE_PARSER_VERSION
    assert summary["daily_update"]["raw_payload_id"] == 11
    assert summary["daily_update"]["official_overrides"] == 1
    assert summary["minute_supplement"]["covered_trading_days"] == 2
