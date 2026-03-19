from __future__ import annotations

import logging

from ..repositories.important_event_repository import list_important_event_records, upsert_important_event_record
from ..schemas.data_plane import ImportantEventUpsert
from ._normalization import clean_optional_text, clean_required_text

logger = logging.getLogger(__name__)


def _normalize_important_event_payload(request: ImportantEventUpsert) -> dict:
    payload = request.model_dump(mode="python")
    payload["symbol"] = clean_required_text(request.symbol).upper()
    payload["market"] = clean_required_text(request.market).upper()
    payload["source_name"] = clean_required_text(request.source_name)
    payload["archive_object_reference"] = clean_optional_text(
        request.archive_object_reference
    )
    payload["notes"] = clean_optional_text(request.notes)
    return payload


def save_important_event(request: ImportantEventUpsert) -> dict:
    payload = _normalize_important_event_payload(request)
    logger.info(
        "Saving important event symbol=%s market=%s event_type=%s raw_payload_id=%s",
        payload["symbol"],
        payload["market"],
        payload["event_type"],
        payload.get("raw_payload_id"),
    )
    record = upsert_important_event_record(payload)
    logger.info(
        "Saved important event id=%s symbol=%s market=%s",
        record["id"],
        record["symbol"],
        record["market"],
    )
    return record


def list_important_events(limit: int = 50) -> list[dict]:
    records = list_important_event_records(limit=limit)
    logger.info("Listed important events count=%s limit=%s", len(records), limit)
    return records
