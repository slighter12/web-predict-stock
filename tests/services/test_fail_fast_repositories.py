from datetime import date, datetime, timezone

import pytest

import backend.repositories.important_event_repository as important_event_repository
import backend.repositories.lifecycle_repository as lifecycle_repository
import backend.repositories.recovery_repository as recovery_repository
import backend.repositories.replay_repository as replay_repository
import backend.repositories.research_run_repository as research_run_repository
from backend.errors import DataAccessError


def _broken_session_local():
    raise RuntimeError("db unavailable")


@pytest.mark.parametrize(
    ("module", "func_name", "payload"),
    [
        (
            research_run_repository,
            "persist_research_run_record",
            {"run_id": "run_123", "status": "failed"},
        ),
        (
            replay_repository,
            "persist_replay_record",
            {
                "raw_payload_id": 1,
                "source_name": "yfinance",
                "symbol": "2330",
                "market": "TW",
                "parser_version": "v1",
                "restore_status": "failed",
                "restored_row_count": 0,
                "replay_started_at": datetime.now(timezone.utc),
            },
        ),
        (
            recovery_repository,
            "persist_recovery_record",
            {
                "raw_payload_id": 1,
                "status": "failed",
                "drill_started_at": datetime.now(timezone.utc),
            },
        ),
        (
            lifecycle_repository,
            "upsert_lifecycle_record",
            {
                "symbol": "2330",
                "market": "TW",
                "event_type": "listing",
                "effective_date": date(2000, 1, 1),
                "source_name": "manual_data_plane",
            },
        ),
        (
            important_event_repository,
            "upsert_important_event_record",
            {
                "symbol": "2330",
                "market": "TW",
                "event_type": "cash_dividend",
                "event_publication_ts": datetime.now(timezone.utc),
                "timestamp_source_class": "official_exchange",
                "source_name": "manual_data_plane",
            },
        ),
    ],
)
def test_persist_repositories_fail_fast(monkeypatch, module, func_name, payload):
    monkeypatch.setattr(module, "SessionLocal", _broken_session_local)

    with pytest.raises(DataAccessError):
        getattr(module, func_name)(payload)


@pytest.mark.parametrize(
    ("module", "func_name", "args"),
    [
        (research_run_repository, "get_research_run_record", ("run_123",)),
        (research_run_repository, "list_research_run_records", (20,)),
        (replay_repository, "list_replay_records", (20,)),
        (recovery_repository, "list_recovery_records", (20,)),
        (lifecycle_repository, "list_lifecycle_records", (20,)),
        (important_event_repository, "list_important_event_records", (20,)),
    ],
)
def test_read_repositories_fail_fast(monkeypatch, module, func_name, args):
    monkeypatch.setattr(module, "SessionLocal", _broken_session_local)

    with pytest.raises(DataAccessError):
        getattr(module, func_name)(*args)
