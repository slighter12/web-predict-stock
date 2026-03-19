from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, select

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
        "latest_replayable_day": row.latest_replayable_day,
        "completed_trading_day_delta": row.completed_trading_day_delta,
        "abort_reason": row.abort_reason,
        "drill_started_at": row.drill_started_at,
        "drill_completed_at": row.drill_completed_at,
        "created_at": normalize_created_at(row.created_at),
    }


def persist_recovery_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    record.setdefault("created_at", utc_now())

    try:
        with SessionLocal() as session:
            row = RecoveryDrill(
                raw_payload_id=record["raw_payload_id"],
                replay_run_id=record.get("replay_run_id"),
                benchmark_profile_id=record.get("benchmark_profile_id"),
                notes=record.get("notes"),
                status=record["status"],
                latest_replayable_day=record.get("latest_replayable_day"),
                completed_trading_day_delta=record.get("completed_trading_day_delta"),
                abort_reason=record.get("abort_reason"),
                drill_started_at=record["drill_started_at"],
                drill_completed_at=record.get("drill_completed_at"),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _recovery_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist recovery drill raw_payload_id=%s",
            record["raw_payload_id"],
        )
        raise DataAccessError("Failed to persist recovery drill.") from exc


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
