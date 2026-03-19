from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from sqlalchemy import desc, select

from ..database import SessionLocal, SymbolLifecycleRecord
from ..errors import DataAccessError
from ..time_utils import utc_now
from ._shared import (
    MEMORY_LIFECYCLE,
    append_memory_record,
    next_memory_id,
    normalize_created_at,
    trim_memory_records,
)

logger = logging.getLogger(__name__)


def _lifecycle_row_to_dict(row: SymbolLifecycleRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "market": row.market,
        "event_type": row.event_type,
        "effective_date": row.effective_date,
        "reference_symbol": row.reference_symbol,
        "source_name": row.source_name,
        "raw_payload_id": row.raw_payload_id,
        "archive_object_reference": row.archive_object_reference,
        "notes": row.notes,
        "created_at": normalize_created_at(row.created_at),
    }


def upsert_lifecycle_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(payload)
    record.setdefault("created_at", utc_now())

    try:
        with SessionLocal() as session:
            stmt = (
                select(SymbolLifecycleRecord)
                .where(SymbolLifecycleRecord.symbol == record["symbol"])
                .where(SymbolLifecycleRecord.market == record["market"])
                .where(SymbolLifecycleRecord.event_type == record["event_type"])
                .where(SymbolLifecycleRecord.effective_date == record["effective_date"])
            )
            row = session.execute(stmt).scalar_one_or_none() or SymbolLifecycleRecord()
            row.symbol = record["symbol"]
            row.market = record["market"]
            row.event_type = record["event_type"]
            row.effective_date = record["effective_date"]
            row.reference_symbol = record.get("reference_symbol")
            row.source_name = record["source_name"]
            row.raw_payload_id = record.get("raw_payload_id")
            row.archive_object_reference = record.get("archive_object_reference")
            row.notes = record.get("notes")
            session.add(row)
            session.commit()
            session.refresh(row)
            persisted = _lifecycle_row_to_dict(row)
    except Exception:
        logger.exception(
            "Falling back to in-memory lifecycle persistence symbol=%s",
            record["symbol"],
        )
        for existing in MEMORY_LIFECYCLE:
            if (
                existing["symbol"] == record["symbol"]
                and existing["market"] == record["market"]
                and existing["event_type"] == record["event_type"]
                and existing["effective_date"] == record["effective_date"]
            ):
                existing.update(record)
                trim_memory_records(MEMORY_LIFECYCLE)
                return deepcopy(existing)
        record["id"] = next_memory_id("lifecycle")
        append_memory_record(MEMORY_LIFECYCLE, record)
        persisted = deepcopy(record)

    return persisted


def list_lifecycle_records(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(SymbolLifecycleRecord)
                .order_by(
                    desc(SymbolLifecycleRecord.effective_date),
                    desc(SymbolLifecycleRecord.id),
                )
                .limit(limit)
            )
            return [
                _lifecycle_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list lifecycle records from DB")
        if MEMORY_LIFECYCLE:
            return deepcopy(
                sorted(MEMORY_LIFECYCLE, key=lambda item: item["id"], reverse=True)[
                    :limit
                ]
            )
        raise DataAccessError("Failed to list lifecycle records.") from exc
