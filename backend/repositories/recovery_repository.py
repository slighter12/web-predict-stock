from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from ..database import RecoveryDrill, SessionLocal
from ..errors import DataAccessError
from ..time_utils import utc_now
from ._shared import clone_payload, normalize_created_at

logger = logging.getLogger(__name__)


def _recovery_row_to_dict(row: RecoveryDrill) -> dict[str, Any]:
    return {
        "id": row.id,
        "raw_payload_id": row.raw_payload_id,
        "replay_run_id": row.replay_run_id,
        "benchmark_profile_id": row.benchmark_profile_id,
        "notes": row.notes,
        "status": row.status,
        "trigger_mode": row.trigger_mode,
        "schedule_id": row.schedule_id,
        "scheduled_for_date": row.scheduled_for_date,
        "latest_replayable_day": row.latest_replayable_day,
        "completed_trading_day_delta": row.completed_trading_day_delta,
        "abort_reason": row.abort_reason,
        "drill_started_at": row.drill_started_at,
        "drill_completed_at": row.drill_completed_at,
        "created_at": normalize_created_at(row.created_at),
    }


def _load_scheduled_recovery_record(
    session, schedule_id: int, scheduled_for_date: date
) -> dict[str, Any] | None:
    stmt = (
        select(RecoveryDrill)
        .where(RecoveryDrill.schedule_id == schedule_id)
        .where(RecoveryDrill.scheduled_for_date == scheduled_for_date)
        .limit(1)
    )
    row = session.execute(stmt).scalar_one_or_none()
    if row is None:
        return None
    return _recovery_row_to_dict(row)


def _is_duplicate_schedule_slot_integrity_error(
    exc: IntegrityError, record: dict[str, Any]
) -> bool:
    if record.get("id") is not None:
        return False
    if record.get("schedule_id") is None or record.get("scheduled_for_date") is None:
        return False

    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_recovery_drill_schedule_slot":
        return True

    message = str(exc.orig or exc)
    return (
        "uq_recovery_drill_schedule_slot" in message
        or "recovery_drills.schedule_id, recovery_drills.scheduled_for_date" in message
    )


def persist_recovery_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    record.setdefault("created_at", utc_now())

    try:
        with SessionLocal() as session:
            row = None
            if record.get("id") is not None:
                row = session.get(RecoveryDrill, record["id"])
            if row is None:
                row = RecoveryDrill()
            row.raw_payload_id = record["raw_payload_id"]
            row.replay_run_id = record.get("replay_run_id")
            row.benchmark_profile_id = record.get("benchmark_profile_id")
            row.notes = record.get("notes")
            row.status = record["status"]
            row.trigger_mode = record["trigger_mode"]
            row.schedule_id = record.get("schedule_id")
            row.scheduled_for_date = record.get("scheduled_for_date")
            row.latest_replayable_day = record.get("latest_replayable_day")
            row.completed_trading_day_delta = record.get("completed_trading_day_delta")
            row.abort_reason = record.get("abort_reason")
            row.drill_started_at = record["drill_started_at"]
            row.drill_completed_at = record.get("drill_completed_at")
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                if _is_duplicate_schedule_slot_integrity_error(exc, record):
                    session.rollback()
                    existing_record = _load_scheduled_recovery_record(
                        session,
                        int(record["schedule_id"]),
                        record["scheduled_for_date"],
                    )
                    if existing_record is not None:
                        return existing_record
                raise
            session.refresh(row)
            return _recovery_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist recovery drill raw_payload_id=%s",
            record["raw_payload_id"],
        )
        raise DataAccessError("Failed to persist recovery drill.") from exc


def get_scheduled_recovery_record(
    schedule_id: int, scheduled_for_date: date
) -> dict[str, Any] | None:
    try:
        with SessionLocal() as session:
            return _load_scheduled_recovery_record(
                session,
                schedule_id,
                scheduled_for_date,
            )
    except Exception as exc:
        logger.exception(
            "Failed to load scheduled recovery drill schedule_id=%s scheduled_for_date=%s",
            schedule_id,
            scheduled_for_date,
        )
        raise DataAccessError("Failed to load scheduled recovery drill.") from exc


def list_recovery_records(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(RecoveryDrill)
                .order_by(desc(RecoveryDrill.created_at), desc(RecoveryDrill.id))
                .limit(limit)
            )
            return [
                _recovery_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list recovery drills from DB")
        raise DataAccessError("Failed to list recovery drills.") from exc
