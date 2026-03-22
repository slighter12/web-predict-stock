from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.market_data.repositories.lifecycle as lifecycle_repository
from backend.database import Base, SymbolLifecycleRecord


def test_lifecycle_record_upsert_reuses_existing_row(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, tables=[SymbolLifecycleRecord.__table__])
    monkeypatch.setattr(lifecycle_repository, "SessionLocal", testing_session_local)

    first = lifecycle_repository.upsert_lifecycle_record(
        {
            "symbol": "2330",
            "market": "TW",
            "event_type": "listing",
            "effective_date": date(2000, 1, 1),
            "reference_symbol": None,
            "source_name": "manual_data_plane",
            "notes": "initial",
        }
    )
    second = lifecycle_repository.upsert_lifecycle_record(
        {
            "symbol": "2330",
            "market": "TW",
            "event_type": "listing",
            "effective_date": date(2000, 1, 1),
            "reference_symbol": None,
            "source_name": "manual_data_plane",
            "notes": "updated",
        }
    )

    assert first["id"] == second["id"]
    assert second["notes"] == "updated"
