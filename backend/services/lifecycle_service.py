from __future__ import annotations

import logging

from ..repositories.lifecycle_repository import list_lifecycle_records, upsert_lifecycle_record
from ..schemas.data_plane import LifecycleRecordUpsert
from ._normalization import clean_optional_text, clean_required_text

logger = logging.getLogger(__name__)


def _normalize_lifecycle_payload(request: LifecycleRecordUpsert) -> dict:
    payload = request.model_dump(mode="python")
    payload["symbol"] = clean_required_text(request.symbol).upper()
    payload["market"] = clean_required_text(request.market).upper()
    payload["source_name"] = clean_required_text(request.source_name)
    payload["reference_symbol"] = clean_optional_text(request.reference_symbol)
    payload["archive_object_reference"] = clean_optional_text(
        request.archive_object_reference
    )
    payload["notes"] = clean_optional_text(request.notes)
    return payload


def save_lifecycle_record(request: LifecycleRecordUpsert) -> dict:
    payload = _normalize_lifecycle_payload(request)
    logger.info(
        "Saving lifecycle record symbol=%s market=%s event_type=%s raw_payload_id=%s",
        payload["symbol"],
        payload["market"],
        payload["event_type"],
        payload.get("raw_payload_id"),
    )
    record = upsert_lifecycle_record(payload)
    logger.info(
        "Saved lifecycle record id=%s symbol=%s market=%s",
        record["id"],
        record["symbol"],
        record["market"],
    )
    return record


def list_lifecycle(limit: int = 50) -> list[dict]:
    records = list_lifecycle_records(limit=limit)
    logger.info("Listed lifecycle records count=%s limit=%s", len(records), limit)
    return records
