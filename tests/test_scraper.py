import pandas as pd

from scripts import scraper


def test_validate_ohlcv_with_report_tracks_removed_rows():
    df = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "2330", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100},
            {"date": "2024-01-02", "symbol": "2330", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100},
            {"date": "2024-01-03", "symbol": "2330", "open": None, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100},
            {"date": "2024-01-04", "symbol": "2330", "open": -1.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100},
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
        [{"date": "2024-01-02", "symbol": "2330", "market": "TW", "source": "yfinance", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100}]
    )
    daily_df = pd.DataFrame(
        [{"date": "2024-01-03", "symbol": "2330", "market": "TW", "source": "twse", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100}]
    )
    calls = []

    monkeypatch.setattr(scraper, "backfill_history", lambda **kwargs: backfill_df)
    monkeypatch.setattr(scraper, "scrape_daily_twse", lambda **kwargs: daily_df)

    def fake_load(df):
        calls.append(df.iloc[0]["source"] if not df.empty else "empty")
        return {"validated_rows": len(df), "official_overrides": 1 if not df.empty and df.iloc[0]["source"] == "twse" else 0}

    monkeypatch.setattr(scraper, "load_to_db", fake_load)

    summary = scraper.ingest_symbol(symbol="2330", market="TW", years=5)

    assert calls == ["yfinance", "twse"]
    assert summary["daily_update"]["official_overrides"] == 1


def test_ingest_symbol_us_skips_daily_update(monkeypatch):
    backfill_df = pd.DataFrame(
        [{"date": "2024-01-02", "symbol": "AAPL", "market": "US", "source": "yfinance", "open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5, "volume": 100}]
    )

    monkeypatch.setattr(scraper, "backfill_history", lambda **kwargs: backfill_df)
    monkeypatch.setattr(scraper, "load_to_db", lambda df: {"validated_rows": len(df), "official_overrides": 0})

    summary = scraper.ingest_symbol(symbol="AAPL", market="US", years=5)

    assert summary["backfill"]["validated_rows"] == 1
    assert summary["daily_update"]["validated_rows"] == 0
