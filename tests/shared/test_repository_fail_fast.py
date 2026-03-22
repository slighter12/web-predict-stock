from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

import backend.market_data.repositories.important_events as important_event_repository
import backend.market_data.repositories.lifecycle as lifecycle_repository
import backend.market_data.repositories.recovery as recovery_repository
import backend.market_data.repositories.replays as replay_repository
import backend.research.repositories.runs as research_run_repository
from backend.platform.errors import DataAccessError


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


def test_persist_recovery_record_returns_existing_row_on_duplicate_schedule_slot(
    monkeypatch,
):
    persisted_started_at = datetime.now(timezone.utc)
    existing_row = SimpleNamespace(
        id=88,
        raw_payload_id=7,
        replay_run_id=91,
        benchmark_profile_id="monthly_recovery_v1",
        notes="scheduled smoke",
        status="succeeded",
        trigger_mode="scheduled",
        schedule_id=5,
        scheduled_for_date=date(2026, 3, 19),
        latest_replayable_day=date(2026, 3, 18),
        completed_trading_day_delta=1,
        abort_reason=None,
        drill_started_at=persisted_started_at,
        drill_completed_at=persisted_started_at,
        created_at=persisted_started_at,
    )

    class _ScalarResult:
        def scalar_one_or_none(self):
            return existing_row

    class _FakeSession:
        def __init__(self):
            self.rolled_back = False

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, model, record_id):
            return None

        def add(self, row):
            self.row = row

        def commit(self):
            raise IntegrityError(
                "INSERT INTO recovery_drills ...",
                {},
                Exception(
                    "UNIQUE constraint failed: recovery_drills.schedule_id, recovery_drills.scheduled_for_date"
                ),
            )

        def rollback(self):
            self.rolled_back = True

        def execute(self, stmt):
            return _ScalarResult()

        def refresh(self, row):
            raise AssertionError("refresh should not be called for duplicate rows")

    fake_session = _FakeSession()
    monkeypatch.setattr(recovery_repository, "SessionLocal", lambda: fake_session)

    result = recovery_repository.persist_recovery_record(
        {
            "raw_payload_id": 7,
            "replay_run_id": 91,
            "benchmark_profile_id": "monthly_recovery_v1",
            "notes": "scheduled smoke",
            "status": "succeeded",
            "trigger_mode": "scheduled",
            "schedule_id": 5,
            "scheduled_for_date": date(2026, 3, 19),
            "latest_replayable_day": date(2026, 3, 18),
            "completed_trading_day_delta": 1,
            "abort_reason": None,
            "drill_started_at": persisted_started_at,
            "drill_completed_at": persisted_started_at,
        }
    )

    assert fake_session.rolled_back is True
    assert result["id"] == 88
    assert result["schedule_id"] == 5
