from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.market_data.repositories.raw_ingest as raw_ingest_repository
from backend.market_data.services import ingestion_runtime as scraper
from backend.database import Base, DailyOHLCV, RawIngestAudit
from backend.platform.time import utc_now


def test_get_latest_successful_raw_ingest_skips_empty_payload(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=[RawIngestAudit.__table__])
    monkeypatch.setattr(raw_ingest_repository, "SessionLocal", testing_session_local)

    now = utc_now()
    with testing_session_local() as session:
        session.add_all(
            [
                RawIngestAudit(
                    source_name=scraper.SOURCE_YFINANCE,
                    symbol="2330",
                    market="TW",
                    fetch_timestamp=now - timedelta(minutes=1),
                    parser_version=scraper.YFINANCE_PARSER_VERSION,
                    fetch_status=scraper.FETCH_STATUS_SUCCESS,
                    expected_symbol_context="replayable",
                    payload_body='{"rows": 1}',
                ),
                RawIngestAudit(
                    source_name=scraper.SOURCE_YFINANCE,
                    symbol="2330",
                    market="TW",
                    fetch_timestamp=now,
                    parser_version=scraper.YFINANCE_PARSER_VERSION,
                    fetch_status=scraper.FETCH_STATUS_SUCCESS,
                    expected_symbol_context="empty",
                    payload_body="",
                ),
            ]
        )
        session.commit()

    row = raw_ingest_repository.get_latest_successful_raw_ingest()

    assert row.expected_symbol_context == "replayable"
    assert row.payload_body == '{"rows": 1}'


def test_list_market_trading_days_can_restrict_sources(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.create_all(bind=engine, tables=[DailyOHLCV.__table__])
    monkeypatch.setattr(raw_ingest_repository, "SessionLocal", testing_session_local)

    with testing_session_local() as session:
        session.add_all(
            [
                DailyOHLCV(
                    date=date(2024, 1, 1),
                    symbol="OFFICIAL",
                    source="twse",
                    market="TW",
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                ),
                DailyOHLCV(
                    date=date(2024, 1, 1),
                    symbol="FALLBACK",
                    source="yfinance",
                    market="TW",
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                ),
                DailyOHLCV(
                    date=date(2024, 1, 2),
                    symbol="GHOST",
                    source="yfinance",
                    market="TW",
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                ),
                DailyOHLCV(
                    date=date(2024, 1, 3),
                    symbol="OFFICIAL-2",
                    source="tpex_aftertrading_otc",
                    market="TW",
                    open=1,
                    high=1,
                    low=1,
                    close=1,
                    volume=1,
                ),
            ]
        )
        session.commit()

    result = raw_ingest_repository.list_market_trading_days(
        "TW",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 3),
        source_names=("twse", "twse_mi_index", "tpex_aftertrading_otc"),
    )

    assert result == [date(2024, 1, 1), date(2024, 1, 3)]
