from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from sqlalchemy import desc, select

from ..database import NormalizedReplayRun, SessionLocal
from ..errors import DataAccessError
from ..time_utils import utc_now
from ._shared import (
    MEMORY_REPLAYS,
    append_memory_record,
    next_memory_id,
    normalize_created_at,
)

logger = logging.getLogger(__name__)


def _replay_row_to_dict(row: NormalizedReplayRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "raw_payload_id": row.raw_payload_id,
        "source_name": row.source_name,
        "symbol": row.symbol,
        "market": row.market,
        "archive_object_reference": row.archive_object_reference,
        "parser_version": row.parser_version,
        "benchmark_profile_id": row.benchmark_profile_id,
        "notes": row.notes,
        "restore_status": row.restore_status,
        "abort_reason": row.abort_reason,
        "restored_row_count": row.restored_row_count,
        "replay_started_at": row.replay_started_at,
        "replay_completed_at": row.replay_completed_at,
        "created_at": normalize_created_at(row.created_at),
    }


def persist_replay_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(payload)
    record.setdefault("created_at", utc_now())

    try:
        with SessionLocal() as session:
            row = NormalizedReplayRun(
                raw_payload_id=record["raw_payload_id"],
                source_name=record["source_name"],
                symbol=record["symbol"],
                market=record["market"],
                archive_object_reference=record.get("archive_object_reference"),
                parser_version=record["parser_version"],
                benchmark_profile_id=record.get("benchmark_profile_id"),
                notes=record.get("notes"),
                restore_status=record["restore_status"],
                abort_reason=record.get("abort_reason"),
                restored_row_count=record["restored_row_count"],
                replay_started_at=record["replay_started_at"],
                replay_completed_at=record.get("replay_completed_at"),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            persisted = _replay_row_to_dict(row)
    except Exception:
        logger.exception(
            "Falling back to in-memory replay persistence raw_payload_id=%s",
            record["raw_payload_id"],
        )
        record["id"] = next_memory_id("replay")
        append_memory_record(MEMORY_REPLAYS, record)
        persisted = deepcopy(record)

    return persisted


def list_replay_records(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(NormalizedReplayRun)
                .order_by(
                    desc(NormalizedReplayRun.created_at), desc(NormalizedReplayRun.id)
                )
                .limit(limit)
            )
            return [
                _replay_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list replay records from DB")
        if MEMORY_REPLAYS:
            return deepcopy(
                sorted(MEMORY_REPLAYS, key=lambda item: item["id"], reverse=True)[
                    :limit
                ]
            )
        raise DataAccessError("Failed to list replay records.") from exc
