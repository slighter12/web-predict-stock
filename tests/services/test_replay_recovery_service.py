import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

import backend.services.recovery_service as recovery_service
import backend.services.replay_service as replay_service
from backend.database import RecoveryDrill
from backend.errors import (
    DataAccessError,
    DataNotFoundError,
    UnsupportedConfigurationError,
)


def _raise_value_error(raw_record):
    raise ValueError("bad payload")


def _raise_data_access_error(payload):
    raise DataAccessError("db unavailable")


def _raise_recovery_configuration_error(**kwargs):
    raise UnsupportedConfigurationError("bad recovery config")


def test_replay_preserves_value_error_when_failure_audit_write_fails(monkeypatch):
    monkeypatch.setattr(
        replay_service,
        "get_raw_ingest_record",
        lambda raw_payload_id: SimpleNamespace(
            id=raw_payload_id,
            source_name="yfinance",
            symbol="2330",
            market="TW",
            parser_version="v1",
        ),
    )
    monkeypatch.setattr(
        replay_service.scraper,
        "replay_raw_ingest_record",
        _raise_value_error,
    )
    monkeypatch.setattr(
        replay_service,
        "persist_replay_record",
        _raise_data_access_error,
    )

    with pytest.raises(UnsupportedConfigurationError, match="bad payload"):
        replay_service.replay_raw_payload(raw_payload_id=1)


def test_recovery_preserves_rejection_when_failure_audit_write_fails(monkeypatch):
    monkeypatch.setattr(
        recovery_service,
        "get_latest_successful_raw_ingest",
        lambda: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(
        recovery_service,
        "replay_raw_payload",
        _raise_recovery_configuration_error,
    )
    monkeypatch.setattr(
        recovery_service,
        "persist_recovery_record",
        _raise_data_access_error,
    )

    with pytest.raises(UnsupportedConfigurationError, match="bad recovery config"):
        recovery_service.create_recovery_drill(raw_payload_id=None)


def test_create_recovery_drill_validates_benchmark_profile(monkeypatch):
    monkeypatch.setattr(
        recovery_service,
        "assert_benchmark_profile_exists",
        lambda profile_id: (_ for _ in ()).throw(
            DataNotFoundError("Benchmark profile 'missing' was not found.")
        ),
    )

    with pytest.raises(DataNotFoundError, match="Benchmark profile 'missing'"):
        recovery_service.create_recovery_drill(
            raw_payload_id=None,
            benchmark_profile_id="missing",
        )


def test_execute_recovery_drill_returns_in_memory_payload_when_persist_fails(
    monkeypatch,
):
    monkeypatch.setattr(
        recovery_service,
        "_persist_recovery_failure",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        recovery_service,
        "replay_raw_payload",
        _raise_recovery_configuration_error,
    )

    result = recovery_service._execute_recovery_drill(
        raw_record=SimpleNamespace(id=1, market="TW"),
        benchmark_profile_id=None,
        notes=None,
        trigger_mode="scheduled",
        raise_on_failure=False,
    )
    assert result["status"] == "failed"
    assert result["id"] is None
    assert result["trigger_mode"] == "scheduled"


def test_execute_recovery_drill_raises_when_raise_on_failure_true(monkeypatch):
    monkeypatch.setattr(
        recovery_service,
        "_persist_recovery_failure",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        recovery_service,
        "replay_raw_payload",
        _raise_recovery_configuration_error,
    )

    with pytest.raises(UnsupportedConfigurationError, match="bad recovery config"):
        recovery_service._execute_recovery_drill(
            raw_record=SimpleNamespace(id=1, market="TW"),
            benchmark_profile_id=None,
            notes=None,
            trigger_mode="scheduled",
            raise_on_failure=True,
        )


def test_dispatch_due_recovery_drills_creates_scheduled_record(monkeypatch):
    persisted_payloads: list[dict] = []
    reference_time = datetime(2026, 3, 19, 2, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        recovery_service,
        "list_recovery_drill_schedules",
        lambda limit=200, active_only=True: [
            {
                "id": 5,
                "market": "TW",
                "symbol": "2330",
                "cadence": "monthly",
                "day_of_month": 19,
                "timezone": "Asia/Taipei",
                "benchmark_profile_id": "monthly_recovery_v1",
                "notes": "scheduled smoke",
                "is_active": True,
            }
        ],
    )
    monkeypatch.setattr(
        recovery_service,
        "get_scheduled_recovery_record",
        lambda schedule_id, scheduled_for_date: None,
    )
    monkeypatch.setattr(
        recovery_service,
        "_resolve_schedule_raw_record",
        lambda schedule: SimpleNamespace(id=7, market="TW"),
    )
    monkeypatch.setattr(
        recovery_service,
        "replay_raw_payload",
        lambda **kwargs: {"id": 99},
    )
    monkeypatch.setattr(
        recovery_service.scraper,
        "replay_raw_ingest_record",
        lambda raw_record: (pd.DataFrame({"date": [pd.Timestamp("2026-03-18")]}), None),
    )
    monkeypatch.setattr(
        recovery_service,
        "get_completed_trading_day_delta",
        lambda market, latest_replayable_day: 1,
    )

    def capture(payload):
        persisted_payloads.append(payload)
        return {"id": 44, **payload}

    monkeypatch.setattr(recovery_service, "persist_recovery_record", capture)

    summary = recovery_service.dispatch_due_recovery_drills(
        reference_time=reference_time
    )

    assert summary["dispatched_count"] == 1
    assert summary["succeeded_count"] == 1
    assert summary["failed_count"] == 0
    assert persisted_payloads[0]["trigger_mode"] == "scheduled"
    assert persisted_payloads[0]["schedule_id"] == 5
    assert str(persisted_payloads[0]["scheduled_for_date"]) == "2026-03-19"
    assert persisted_payloads[0]["latest_replayable_day"] == date(2026, 3, 18)
    assert not isinstance(persisted_payloads[0]["latest_replayable_day"], pd.Timestamp)


def test_dispatch_due_recovery_drills_skips_schedule_created_after_slot(monkeypatch):
    reference_time = datetime(2026, 3, 19, 2, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        recovery_service,
        "list_recovery_drill_schedules",
        lambda limit=200, active_only=True: [
            {
                "id": 9,
                "market": "TW",
                "symbol": "2330",
                "cadence": "monthly",
                "day_of_month": 18,
                "timezone": "Asia/Taipei",
                "benchmark_profile_id": "monthly_recovery_v1",
                "notes": "created after slot",
                "is_active": True,
                "created_at": datetime(2026, 3, 19, 0, 0, tzinfo=timezone.utc),
            }
        ],
    )

    summary = recovery_service.dispatch_due_recovery_drills(
        reference_time=reference_time
    )

    assert summary["dispatched_count"] == 0
    assert summary["skipped_count"] == 1


def test_dispatch_due_recovery_drills_persists_missing_raw_payload_failure(monkeypatch):
    reference_time = datetime(2026, 3, 19, 2, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        recovery_service,
        "list_recovery_drill_schedules",
        lambda limit=200, active_only=True: [
            {
                "id": 8,
                "market": "TW",
                "symbol": None,
                "cadence": "monthly",
                "day_of_month": 19,
                "timezone": "Asia/Taipei",
                "benchmark_profile_id": "monthly_recovery_v1",
                "notes": "missing raw payload",
                "is_active": True,
            }
        ],
    )
    monkeypatch.setattr(
        recovery_service,
        "get_scheduled_recovery_record",
        lambda schedule_id, scheduled_for_date: None,
    )

    def raise_not_found(schedule):
        raise DataNotFoundError(
            "No replayable raw payload is available for market 'TW'."
        )

    monkeypatch.setattr(
        recovery_service, "_resolve_schedule_raw_record", raise_not_found
    )
    monkeypatch.setattr(
        recovery_service,
        "persist_recovery_record",
        lambda payload: {"id": 55, **payload},
    )

    summary = recovery_service.dispatch_due_recovery_drills(
        reference_time=reference_time
    )

    assert summary["dispatched_count"] == 1
    assert summary["failed_count"] == 1
    assert summary["error_count"] == 0
    assert summary["records"][0]["status"] == "failed"
    assert summary["records"][0]["raw_payload_id"] is None
    assert summary["records"][0]["trigger_mode"] == "scheduled"


def test_dispatch_due_recovery_drills_accepts_existing_record_from_duplicate_slot(
    monkeypatch,
):
    reference_time = datetime(2026, 3, 19, 2, 0, tzinfo=timezone.utc)
    existing_record = {
        "id": 44,
        "raw_payload_id": 7,
        "replay_run_id": 99,
        "benchmark_profile_id": "monthly_recovery_v1",
        "notes": "scheduled smoke",
        "status": "succeeded",
        "trigger_mode": "scheduled",
        "schedule_id": 5,
        "scheduled_for_date": date(2026, 3, 19),
        "latest_replayable_day": date(2026, 3, 18),
        "completed_trading_day_delta": 1,
        "abort_reason": None,
        "drill_started_at": datetime.now(timezone.utc),
        "drill_completed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }

    monkeypatch.setattr(
        recovery_service,
        "list_recovery_drill_schedules",
        lambda limit=200, active_only=True: [
            {
                "id": 5,
                "market": "TW",
                "symbol": "2330",
                "cadence": "monthly",
                "day_of_month": 19,
                "timezone": "Asia/Taipei",
                "benchmark_profile_id": "monthly_recovery_v1",
                "notes": "scheduled smoke",
                "is_active": True,
            }
        ],
    )
    monkeypatch.setattr(
        recovery_service,
        "get_scheduled_recovery_record",
        lambda schedule_id, scheduled_for_date: None,
    )
    monkeypatch.setattr(
        recovery_service,
        "_resolve_schedule_raw_record",
        lambda schedule: SimpleNamespace(id=7, market="TW"),
    )
    monkeypatch.setattr(
        recovery_service,
        "replay_raw_payload",
        lambda **kwargs: {"id": 99},
    )
    monkeypatch.setattr(
        recovery_service.scraper,
        "replay_raw_ingest_record",
        lambda raw_record: (pd.DataFrame({"date": [pd.Timestamp("2026-03-18")]}), None),
    )
    monkeypatch.setattr(
        recovery_service,
        "get_completed_trading_day_delta",
        lambda market, latest_replayable_day: 1,
    )
    monkeypatch.setattr(
        recovery_service,
        "persist_recovery_record",
        lambda payload: existing_record,
    )

    summary = recovery_service.dispatch_due_recovery_drills(
        reference_time=reference_time
    )

    assert summary["dispatched_count"] == 1
    assert summary["error_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["records"][0]["id"] == 44


def test_create_recovery_drill_schedule_rejects_invalid_timezone(monkeypatch):
    monkeypatch.setattr(
        recovery_service,
        "assert_benchmark_profile_exists",
        lambda profile_id: None,
    )

    with pytest.raises(ValueError, match="Unknown timezone 'Mars/Phobos'"):
        recovery_service.create_recovery_drill_schedule(
            recovery_service.RecoveryDrillScheduleRequest(
                market="TW",
                cadence="monthly",
                day_of_month=1,
                timezone="Mars/Phobos",
                benchmark_profile_id="monthly_recovery_v1",
            )
        )


def test_iter_due_schedule_slot_dates_spans_months_and_caps_day_of_month():
    local_now = datetime(2026, 3, 31, 12, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    due_slots = recovery_service._iter_due_schedule_slot_dates(
        {
            "day_of_month": 31,
            "created_at": datetime(2026, 1, 30, 0, 0, tzinfo=timezone.utc),
        },
        local_now,
    )

    assert due_slots == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31)]


def test_recovery_drill_schedule_id_has_restrict_foreign_key():
    foreign_keys = list(RecoveryDrill.__table__.c.schedule_id.foreign_keys)

    assert len(foreign_keys) == 1
    assert foreign_keys[0].target_fullname == "recovery_drill_schedules.id"
    assert foreign_keys[0].ondelete == "RESTRICT"


def test_recovery_drill_schedule_migration_downgrade_fails_on_null_raw_payload_ids(
    monkeypatch,
):
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "backend/alembic/versions/202603190001_recovery_drill_schedules.py"
    )
    spec = importlib.util.spec_from_file_location(
        "recovery_drill_schedule_migration",
        migration_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    class _ScalarResult:
        def scalar(self):
            return 1

    fake_bind = SimpleNamespace(execute=lambda statement: _ScalarResult())
    monkeypatch.setattr(module, "_has_table", lambda table_name: True)
    monkeypatch.setattr(module, "_has_column", lambda table_name, column_name: True)
    monkeypatch.setattr(module, "op", SimpleNamespace(get_bind=lambda: fake_bind))

    with pytest.raises(RuntimeError, match="raw_payload_id contains NULL values"):
        module._assert_no_null_recovery_drill_raw_payload_ids()
