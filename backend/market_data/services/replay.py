from __future__ import annotations

import logging

from backend.market_data.repositories.raw_ingest import get_raw_ingest_record
from backend.market_data.repositories.replays import (
    list_replay_records,
    persist_replay_record,
)
from backend.market_data.services.benchmark_profiles import (
    assert_benchmark_profile_exists,
)
from backend.platform.errors import DataAccessError, UnsupportedConfigurationError
from backend.platform.time import utc_now
from scripts import market_data_ingestion as scraper

logger = logging.getLogger(__name__)


def replay_raw_payload(
    raw_payload_id: int,
    benchmark_profile_id: str | None = None,
    notes: str | None = None,
) -> dict:
    assert_benchmark_profile_exists(benchmark_profile_id)
    raw_record = get_raw_ingest_record(raw_payload_id)
    started_at = utc_now()
    replay_payload = {
        "raw_payload_id": raw_record.id,
        "source_name": raw_record.source_name,
        "symbol": raw_record.symbol,
        "market": raw_record.market,
        "archive_object_reference": f"raw_ingest_audit:{raw_record.id}",
        "parser_version": raw_record.parser_version,
        "benchmark_profile_id": benchmark_profile_id,
        "notes": notes,
        "restore_status": "failed",
        "abort_reason": None,
        "restored_row_count": 0,
        "replay_started_at": started_at,
        "replay_completed_at": None,
    }

    try:
        replay_df, metadata = scraper.replay_raw_ingest_record(raw_record)
        summary = scraper.load_to_db(replay_df, metadata=metadata)
        replay_payload["restore_status"] = "succeeded"
        replay_payload["restored_row_count"] = summary["upserted_rows"]
        replay_payload["replay_completed_at"] = utc_now()
        return persist_replay_record(replay_payload)
    except Exception as exc:
        replay_payload["abort_reason"] = str(exc)
        replay_payload["replay_completed_at"] = utc_now()
        replay_id = None
        try:
            persisted = persist_replay_record(replay_payload)
        except DataAccessError:
            logger.exception(
                "Failed to persist replay failure raw_payload_id=%s",
                raw_payload_id,
            )
        else:
            replay_id = persisted["id"]
        logger.warning(
            "Replay failed raw_payload_id=%s replay_id=%s reason=%s",
            raw_payload_id,
            replay_id,
            exc,
        )
        if isinstance(exc, ValueError):
            raise UnsupportedConfigurationError(str(exc)) from exc
        raise DataAccessError("Failed to replay raw payload.") from exc


def list_replays(limit: int = 20) -> list[dict]:
    return list_replay_records(limit=limit)
