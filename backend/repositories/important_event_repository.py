from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from sqlalchemy import desc, select

from ..database import ImportantEvent, SessionLocal
from ..errors import DataAccessError
from ..time_utils import utc_now
from ._shared import (
    MEMORY_IMPORTANT_EVENTS,
    append_memory_record,
    next_memory_id,
    normalize_created_at,
    trim_memory_records,
)

logger = logging.getLogger(__name__)


def _important_event_row_to_dict(row: ImportantEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "market": row.market,
        "event_type": row.event_type,
        "effective_date": row.effective_date,
        "event_publication_ts": row.event_publication_ts,
        "timestamp_source_class": row.timestamp_source_class,
        "source_name": row.source_name,
        "raw_payload_id": row.raw_payload_id,
        "archive_object_reference": row.archive_object_reference,
        "notes": row.notes,
        "created_at": normalize_created_at(row.created_at),
    }


def upsert_important_event_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = deepcopy(payload)
    record.setdefault("created_at", utc_now())

    try:
        with SessionLocal() as session:
            stmt = (
                select(ImportantEvent)
                .where(ImportantEvent.symbol == record["symbol"])
                .where(ImportantEvent.market == record["market"])
                .where(ImportantEvent.event_type == record["event_type"])
                .where(
                    ImportantEvent.event_publication_ts
                    == record["event_publication_ts"]
                )
            )
            row = session.execute(stmt).scalar_one_or_none() or ImportantEvent()
            row.symbol = record["symbol"]
            row.market = record["market"]
            row.event_type = record["event_type"]
            row.effective_date = record.get("effective_date")
            row.event_publication_ts = record["event_publication_ts"]
            row.timestamp_source_class = record["timestamp_source_class"]
            row.source_name = record["source_name"]
            row.raw_payload_id = record.get("raw_payload_id")
            row.archive_object_reference = record.get("archive_object_reference")
            row.notes = record.get("notes")
            session.add(row)
            session.commit()
            session.refresh(row)
            persisted = _important_event_row_to_dict(row)
    except Exception:
        logger.exception(
            "Falling back to in-memory important-event persistence symbol=%s",
            record["symbol"],
        )
        for existing in MEMORY_IMPORTANT_EVENTS:
            if (
                existing["symbol"] == record["symbol"]
                and existing["market"] == record["market"]
                and existing["event_type"] == record["event_type"]
                and existing["event_publication_ts"] == record["event_publication_ts"]
            ):
                existing.update(record)
                trim_memory_records(MEMORY_IMPORTANT_EVENTS)
                return deepcopy(existing)
        record["id"] = next_memory_id("important_event")
        append_memory_record(MEMORY_IMPORTANT_EVENTS, record)
        persisted = deepcopy(record)

    return persisted


def list_important_event_records(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ImportantEvent)
                .order_by(
                    desc(ImportantEvent.event_publication_ts), desc(ImportantEvent.id)
                )
                .limit(limit)
            )
            return [
                _important_event_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list important events from DB")
        if MEMORY_IMPORTANT_EVENTS:
            return deepcopy(
                sorted(
                    MEMORY_IMPORTANT_EVENTS, key=lambda item: item["id"], reverse=True
                )[:limit]
            )
        raise DataAccessError("Failed to list important events.") from exc
