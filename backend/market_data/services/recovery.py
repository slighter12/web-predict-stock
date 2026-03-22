from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from backend.market_data.contracts.operations import RecoveryDrillScheduleRequest
from backend.market_data.repositories.raw_ingest import (
    get_completed_trading_day_delta,
    get_latest_successful_raw_ingest,
    get_latest_successful_raw_ingest_for_scope,
    get_raw_ingest_record,
)
from backend.market_data.repositories.recovery import (
    get_scheduled_recovery_record,
    list_recovery_records,
    persist_recovery_record,
)
from backend.market_data.repositories.recovery_schedules import (
    list_recovery_drill_schedules,
    persist_recovery_drill_schedule,
)
from backend.market_data.services._normalization import clean_optional_text
from backend.market_data.services._schedule_slots import resolve_schedule_slot_date
from backend.market_data.services.benchmark_profiles import (
    assert_benchmark_profile_exists,
)
from backend.market_data.services.replay import replay_raw_payload
from backend.platform.errors import (
    DataAccessError,
    DataNotFoundError,
    UnsupportedConfigurationError,
)
from backend.platform.time import utc_now
from scripts import scraper

logger = logging.getLogger(__name__)
DEFAULT_SCHEDULE_TIMEZONE = "Asia/Taipei"
RECOVERY_SCHEDULE_DISPATCH_LIMIT = 200


def _normalize_schedule_payload(request: RecoveryDrillScheduleRequest) -> dict:
    timezone_name = clean_optional_text(request.timezone) or DEFAULT_SCHEDULE_TIMEZONE
    benchmark_profile_id = clean_optional_text(request.benchmark_profile_id)
    if benchmark_profile_id is None:
        raise ValueError("Benchmark profile ID is required.")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone '{timezone_name}'.") from exc
    assert_benchmark_profile_exists(benchmark_profile_id)

    return {
        "market": request.market.strip().upper(),
        "symbol": clean_optional_text(
            request.symbol.strip().upper() if request.symbol else None
        ),
        "cadence": request.cadence,
        "day_of_month": request.day_of_month,
        "timezone": timezone_name,
        "benchmark_profile_id": benchmark_profile_id,
        "notes": clean_optional_text(request.notes),
        "is_active": True,
    }


def create_recovery_drill_schedule(request: RecoveryDrillScheduleRequest) -> dict:
    payload = _normalize_schedule_payload(request)
    logger.info(
        "Creating recovery drill schedule market=%s symbol=%s cadence=%s day_of_month=%s",
        payload["market"],
        payload["symbol"],
        payload["cadence"],
        payload["day_of_month"],
    )
    return persist_recovery_drill_schedule(payload)


def list_recovery_schedules(limit: int = 50) -> list[dict]:
    return list_recovery_drill_schedules(limit=limit)


def _build_recovery_payload(
    *,
    record_id: int | None = None,
    raw_payload_id: int | None,
    benchmark_profile_id: str | None,
    notes: str | None,
    trigger_mode: str,
    schedule_id: int | None,
    scheduled_for_date: date | None,
) -> dict:
    return {
        "id": record_id,
        "raw_payload_id": raw_payload_id,
        "replay_run_id": None,
        "benchmark_profile_id": benchmark_profile_id,
        "notes": notes,
        "status": "failed",
        "trigger_mode": trigger_mode,
        "schedule_id": schedule_id,
        "scheduled_for_date": scheduled_for_date,
        "latest_replayable_day": None,
        "completed_trading_day_delta": None,
        "abort_reason": None,
        "drill_started_at": utc_now(),
        "drill_completed_at": None,
    }


def _persist_recovery_failure(
    *,
    drill_payload: dict,
    reason: Exception | str,
    raw_payload_id: int | None,
) -> dict | None:
    drill_payload["abort_reason"] = str(reason)
    drill_payload["drill_completed_at"] = utc_now()
    try:
        return persist_recovery_record(drill_payload)
    except DataAccessError:
        logger.exception(
            "Failed to persist recovery failure raw_payload_id=%s schedule_id=%s",
            raw_payload_id,
            drill_payload.get("schedule_id"),
        )
        return None


def _translate_recovery_error(exc: Exception) -> Exception:
    if isinstance(exc, (ValueError, UnsupportedConfigurationError, DataNotFoundError)):
        return UnsupportedConfigurationError(str(exc))
    if isinstance(exc, DataAccessError):
        return exc
    return DataAccessError("Failed to execute recovery drill.")


def _normalize_latest_replayable_day(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        normalized = value.date()
        if isinstance(normalized, date):
            return normalized
    raise ValueError(f"Unsupported latest replayable day value: {value!r}")


def _execute_recovery_drill(
    *,
    raw_record,
    benchmark_profile_id: str | None,
    notes: str | None,
    trigger_mode: str,
    schedule_id: int | None = None,
    scheduled_for_date: date | None = None,
    existing_record_id: int | None = None,
    raise_on_failure: bool = True,
) -> dict:
    drill_payload = _build_recovery_payload(
        record_id=existing_record_id,
        raw_payload_id=raw_record.id,
        benchmark_profile_id=benchmark_profile_id,
        notes=notes,
        trigger_mode=trigger_mode,
        schedule_id=schedule_id,
        scheduled_for_date=scheduled_for_date,
    )

    try:
        replay_result = replay_raw_payload(
            raw_payload_id=raw_record.id,
            benchmark_profile_id=benchmark_profile_id,
            notes=notes,
        )
        latest_replayable_day = None
        replay_df, _ = scraper.replay_raw_ingest_record(raw_record)
        if not replay_df.empty:
            latest_replayable_day = _normalize_latest_replayable_day(
                max(replay_df["date"])
            )
        drill_payload["replay_run_id"] = replay_result["id"]
        drill_payload["status"] = "succeeded"
        drill_payload["latest_replayable_day"] = latest_replayable_day
        if latest_replayable_day is not None:
            drill_payload["completed_trading_day_delta"] = (
                get_completed_trading_day_delta(
                    raw_record.market,
                    latest_replayable_day,
                )
            )
        drill_payload["drill_completed_at"] = utc_now()
        return persist_recovery_record(drill_payload)
    except Exception as exc:
        persisted = _persist_recovery_failure(
            drill_payload=drill_payload,
            reason=exc,
            raw_payload_id=raw_record.id,
        )
        drill_id = persisted["id"] if persisted else None
        logger.warning(
            "Recovery drill failed drill_id=%s raw_payload_id=%s reason=%s",
            drill_id,
            raw_record.id,
            exc,
        )
        if not raise_on_failure:
            if persisted is not None:
                return persisted
            # Persist failed — return the in-memory payload so the caller
            # still gets a record in the dispatched list.
            drill_payload["id"] = None
            return drill_payload
        raise _translate_recovery_error(exc) from exc


def _iter_due_schedule_slot_dates(schedule: dict, local_now: datetime) -> list[date]:
    created_at = schedule.get("created_at")
    start_date = local_now.date()
    if isinstance(created_at, datetime):
        start_date = created_at.astimezone(local_now.tzinfo).date()

    year = start_date.year
    month = start_date.month
    due_slots: list[date] = []
    while (year, month) <= (local_now.year, local_now.month):
        slot_date = resolve_schedule_slot_date(
            year,
            month,
            schedule["day_of_month"],
        )
        if start_date <= slot_date <= local_now.date():
            due_slots.append(slot_date)
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return due_slots


def _resolve_schedule_raw_record(schedule: dict):
    if schedule.get("symbol"):
        return get_latest_successful_raw_ingest_for_scope(
            market=schedule["market"],
            symbol=schedule["symbol"],
        )
    return get_latest_successful_raw_ingest_for_scope(market=schedule["market"])


def create_recovery_drill(
    raw_payload_id: int | None,
    benchmark_profile_id: str | None = None,
    notes: str | None = None,
) -> dict:
    assert_benchmark_profile_exists(benchmark_profile_id)
    raw_record = (
        get_raw_ingest_record(raw_payload_id)
        if raw_payload_id
        else get_latest_successful_raw_ingest()
    )
    return _execute_recovery_drill(
        raw_record=raw_record,
        benchmark_profile_id=benchmark_profile_id,
        notes=notes,
        trigger_mode="manual",
        raise_on_failure=True,
    )


def dispatch_due_recovery_drills(
    reference_time: datetime | None = None,
) -> dict[str, int | list[dict] | list[str]]:
    current_time = reference_time or utc_now()
    schedules = list_recovery_drill_schedules(
        limit=RECOVERY_SCHEDULE_DISPATCH_LIMIT,
        active_only=True,
    )
    if len(schedules) == RECOVERY_SCHEDULE_DISPATCH_LIMIT:
        logger.warning(
            "Scheduled recovery drill dispatch reached schedule limit=%s; results may be truncated",
            RECOVERY_SCHEDULE_DISPATCH_LIMIT,
        )
    dispatched: list[dict] = []
    errors: list[str] = []
    skipped_count = 0

    for schedule in schedules:
        try:
            local_now = current_time.astimezone(ZoneInfo(schedule["timezone"]))
        except Exception as exc:
            errors.append(f"schedule_id={schedule['id']}: {exc}")
            logger.exception(
                "Scheduled recovery dispatch errored schedule_id=%s",
                schedule["id"],
            )
            continue

        due_slot_dates = _iter_due_schedule_slot_dates(schedule, local_now)
        if not due_slot_dates:
            skipped_count += 1
            continue

        for scheduled_for_date in due_slot_dates:
            existing_record = None
            try:
                existing_record = get_scheduled_recovery_record(
                    schedule["id"],
                    scheduled_for_date,
                )
                if existing_record and existing_record["status"] == "succeeded":
                    skipped_count += 1
                    continue

                raw_record = _resolve_schedule_raw_record(schedule)
                dispatched.append(
                    _execute_recovery_drill(
                        raw_record=raw_record,
                        benchmark_profile_id=schedule["benchmark_profile_id"],
                        notes=schedule.get("notes"),
                        trigger_mode="scheduled",
                        schedule_id=schedule["id"],
                        scheduled_for_date=scheduled_for_date,
                        existing_record_id=(
                            int(existing_record["id"]) if existing_record else None
                        ),
                        raise_on_failure=False,
                    )
                )
            except DataNotFoundError as exc:
                persisted = _persist_recovery_failure(
                    drill_payload=_build_recovery_payload(
                        record_id=int(existing_record["id"])
                        if existing_record
                        else None,
                        raw_payload_id=None,
                        benchmark_profile_id=schedule["benchmark_profile_id"],
                        notes=schedule.get("notes"),
                        trigger_mode="scheduled",
                        schedule_id=schedule["id"],
                        scheduled_for_date=scheduled_for_date,
                    ),
                    reason=exc,
                    raw_payload_id=None,
                )
                if persisted is not None:
                    dispatched.append(persisted)
                logger.warning(
                    "Scheduled recovery drill failed schedule_id=%s scheduled_for_date=%s reason=%s",
                    schedule["id"],
                    scheduled_for_date,
                    exc,
                )
            except Exception as exc:
                errors.append(
                    f"schedule_id={schedule['id']} scheduled_for_date={scheduled_for_date}: {exc}"
                )
                logger.exception(
                    "Scheduled recovery dispatch errored schedule_id=%s scheduled_for_date=%s",
                    schedule["id"],
                    scheduled_for_date,
                )

    failed_count = sum(1 for item in dispatched if item["status"] == "failed")
    succeeded_count = sum(1 for item in dispatched if item["status"] == "succeeded")
    return {
        "schedule_count": len(schedules),
        "dispatched_count": len(dispatched),
        "succeeded_count": succeeded_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "error_count": len(errors),
        "records": dispatched,
        "errors": errors,
    }


def list_recovery_drills(limit: int = 20) -> list[dict]:
    return list_recovery_records(limit=limit)
