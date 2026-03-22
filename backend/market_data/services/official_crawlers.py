from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any

import requests

from backend.market_data.contracts.operations import (
    ImportantEventUpsert,
    LifecycleRecordUpsert,
)
from backend.market_data.repositories.raw_ingest import (
    FETCH_STATUS_FAILED,
    FETCH_STATUS_SUCCESS,
    persist_raw_ingest_record,
)
from backend.market_data.services.important_events import save_important_event
from backend.market_data.services.lifecycle import save_lifecycle_record
from backend.platform.errors import (
    DataAccessError,
    ExternalFetchError,
    UnsupportedConfigurationError,
)
from backend.platform.time import utc_now

logger = logging.getLogger(__name__)
LIFECYCLE_SOURCE_URL_ENV = "TW_LIFECYCLE_SOURCE_URL"
IMPORTANT_EVENT_SOURCE_URL_ENV = "TW_IMPORTANT_EVENT_SOURCE_URL"
LIFECYCLE_SOURCE_NAME = "tw_official_lifecycle"
IMPORTANT_EVENT_SOURCE_NAME = "tw_official_important_event"


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("records", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise UnsupportedConfigurationError(
        "Official crawler payload format is unsupported."
    )


def _fetch_official_feed(
    url_env: str, source_name: str
) -> tuple[int, list[dict[str, Any]]]:
    url = os.getenv(url_env)
    if not url:
        raise UnsupportedConfigurationError(f"{url_env} is required.")
    payload_body = ""
    fetch_timestamp = utc_now()
    expected_context = f"source={source_name};market=TW"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        payload_body = response.text
    except requests.exceptions.RequestException as exc:
        try:
            persist_raw_ingest_record(
                source_name=source_name,
                symbol="TW_OFFICIAL",
                market="TW",
                parser_version="official_feed_v1",
                fetch_status=FETCH_STATUS_FAILED,
                expected_symbol_context=expected_context,
                payload_body=payload_body,
                fetch_timestamp=fetch_timestamp,
            )
        except DataAccessError:
            logger.warning(
                "Failed to record crawler fetch failure source=%s", source_name
            )
        raise ExternalFetchError(f"Failed to fetch official feed: {exc}") from exc

    try:
        payload = json.loads(payload_body)
        records = _extract_records(payload)
    except Exception as exc:
        try:
            persist_raw_ingest_record(
                source_name=source_name,
                symbol="TW_OFFICIAL",
                market="TW",
                parser_version="official_feed_v1",
                fetch_status=FETCH_STATUS_FAILED,
                expected_symbol_context=expected_context,
                payload_body=payload_body,
                fetch_timestamp=fetch_timestamp,
            )
        except DataAccessError:
            logger.warning(
                "Failed to record crawler parse failure source=%s", source_name
            )
        raise UnsupportedConfigurationError(
            "Official crawler payload parsing failed."
        ) from exc

    raw_payload_id = persist_raw_ingest_record(
        source_name=source_name,
        symbol="TW_OFFICIAL",
        market="TW",
        parser_version="official_feed_v1",
        fetch_status=FETCH_STATUS_SUCCESS,
        expected_symbol_context=expected_context,
        payload_body=payload_body,
        fetch_timestamp=fetch_timestamp,
    )
    return raw_payload_id, records


def crawl_lifecycle_records() -> dict:
    raw_payload_id, records = _fetch_official_feed(
        LIFECYCLE_SOURCE_URL_ENV,
        LIFECYCLE_SOURCE_NAME,
    )
    archive_reference = f"raw_ingest_audit:{raw_payload_id}"
    upserted_count = 0
    errors: list[str] = []

    for item in records:
        try:
            save_lifecycle_record(
                LifecycleRecordUpsert(
                    symbol=str(item["symbol"]).upper(),
                    market=str(item.get("market", "TW")).upper(),
                    event_type=item["event_type"],
                    effective_date=_parse_iso_date(item["effective_date"]),
                    reference_symbol=item.get("reference_symbol"),
                    source_name=LIFECYCLE_SOURCE_NAME,
                    raw_payload_id=raw_payload_id,
                    archive_object_reference=archive_reference,
                    notes=item.get("notes"),
                )
            )
            upserted_count += 1
        except Exception as exc:
            errors.append(f"symbol={item.get('symbol')}: {exc}")

    return {
        "source_name": LIFECYCLE_SOURCE_NAME,
        "raw_payload_id": raw_payload_id,
        "processed_count": len(records),
        "upserted_count": upserted_count,
        "errors": errors,
    }


def crawl_important_events() -> dict:
    raw_payload_id, records = _fetch_official_feed(
        IMPORTANT_EVENT_SOURCE_URL_ENV,
        IMPORTANT_EVENT_SOURCE_NAME,
    )
    archive_reference = f"raw_ingest_audit:{raw_payload_id}"
    upserted_count = 0
    errors: list[str] = []

    for item in records:
        try:
            save_important_event(
                ImportantEventUpsert(
                    symbol=str(item["symbol"]).upper(),
                    market=str(item.get("market", "TW")).upper(),
                    event_type=item["event_type"],
                    effective_date=_parse_iso_date(item.get("effective_date")),
                    event_publication_ts=_parse_iso_datetime(
                        item["event_publication_ts"]
                    ),
                    timestamp_source_class=item["timestamp_source_class"],
                    source_name=IMPORTANT_EVENT_SOURCE_NAME,
                    raw_payload_id=raw_payload_id,
                    archive_object_reference=archive_reference,
                    notes=item.get("notes"),
                )
            )
            upserted_count += 1
        except Exception as exc:
            errors.append(f"symbol={item.get('symbol')}: {exc}")

    return {
        "source_name": IMPORTANT_EVENT_SOURCE_NAME,
        "raw_payload_id": raw_payload_id,
        "processed_count": len(records),
        "upserted_count": upserted_count,
        "errors": errors,
    }
