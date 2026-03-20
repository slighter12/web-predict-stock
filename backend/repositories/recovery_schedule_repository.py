from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, select

from ..database import RecoveryDrillSchedule, SessionLocal
from ..errors import DataAccessError
from ..time_utils import utc_now
from ._shared import clone_payload, normalize_created_at

logger = logging.getLogger(__name__)


def _schedule_row_to_dict(row: RecoveryDrillSchedule) -> dict[str, Any]:
    return {
        "id": row.id,
        "market": row.market,
        "symbol": row.symbol,
        "cadence": row.cadence,
        "day_of_month": row.day_of_month,
        "timezone": row.timezone,
        "benchmark_profile_id": row.benchmark_profile_id,
        "notes": row.notes,
        "is_active": row.is_active,
        "created_at": normalize_created_at(row.created_at),
    }


def persist_recovery_drill_schedule(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)

    try:
        with SessionLocal() as session:
            row = RecoveryDrillSchedule(
                market=record["market"],
                symbol=record.get("symbol"),
                cadence=record["cadence"],
                day_of_month=record["day_of_month"],
                timezone=record["timezone"],
                benchmark_profile_id=record["benchmark_profile_id"],
                notes=record.get("notes"),
                is_active=record.get("is_active", True),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _schedule_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist recovery drill schedule market=%s", record["market"]
        )
        raise DataAccessError("Failed to persist recovery drill schedule.") from exc


def list_recovery_drill_schedules(
    limit: int = 50, *, active_only: bool = False
) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = select(RecoveryDrillSchedule)
            if active_only:
                stmt = stmt.where(RecoveryDrillSchedule.is_active.is_(True))
            stmt = stmt.order_by(
                desc(RecoveryDrillSchedule.created_at), desc(RecoveryDrillSchedule.id)
            ).limit(limit)
            return [
                _schedule_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list recovery drill schedules from DB")
        raise DataAccessError("Failed to list recovery drill schedules.") from exc
