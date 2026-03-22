from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.market_data.repositories.raw_ingest as raw_ingest_repository
from backend.database import Base, RawIngestAudit
from backend.platform.time import utc_now
from scripts import scraper


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
