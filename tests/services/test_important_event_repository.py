from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.repositories.important_event_repository as important_event_repository
from backend.database import Base, ImportantEvent


def test_important_event_repository_preserves_timestamp_source(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=[ImportantEvent.__table__])
    monkeypatch.setattr(
        important_event_repository, "SessionLocal", testing_session_local
    )

    publication_ts = datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc)
    stored = important_event_repository.upsert_important_event_record(
        {
            "symbol": "2330",
            "market": "TW",
            "event_type": "cash_dividend",
            "effective_date": None,
            "event_publication_ts": publication_ts,
            "timestamp_source_class": "official_exchange",
            "source_name": "manual_data_plane",
            "notes": "cash dividend declared",
        }
    )

    assert stored["timestamp_source_class"] == "official_exchange"
    assert stored["event_publication_ts"].replace(tzinfo=timezone.utc) == publication_ts
