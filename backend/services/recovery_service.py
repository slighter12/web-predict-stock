from __future__ import annotations

import logging
from datetime import date

from scripts import scraper

from ..errors import DataAccessError, UnsupportedConfigurationError
from ..repositories.raw_ingest_repository import (
    get_latest_successful_raw_ingest,
    get_raw_ingest_record,
)
from ..repositories.recovery_repository import (
    list_recovery_records,
    persist_recovery_record,
)
from ..time_utils import utc_now
from .replay_service import replay_raw_payload

logger = logging.getLogger(__name__)


def create_recovery_drill(
    raw_payload_id: int | None,
    benchmark_profile_id: str | None = None,
    notes: str | None = None,
) -> dict:
    raw_record = (
        get_raw_ingest_record(raw_payload_id)
        if raw_payload_id
        else get_latest_successful_raw_ingest()
    )
    drill_payload = {
        "raw_payload_id": raw_record.id,
        "replay_run_id": None,
        "benchmark_profile_id": benchmark_profile_id,
        "notes": notes,
        "status": "failed",
        "latest_replayable_day": None,
        "completed_trading_day_delta": None,
        "abort_reason": None,
        "drill_started_at": utc_now(),
        "drill_completed_at": None,
    }

    try:
        replay_result = replay_raw_payload(
            raw_payload_id=raw_record.id,
            benchmark_profile_id=benchmark_profile_id,
            notes=notes,
        )
        latest_replayable_day = None
        replay_df, _ = scraper.replay_raw_ingest_record(raw_record)
        if not replay_df.empty:
            latest_replayable_day = max(replay_df["date"])
        drill_payload["replay_run_id"] = replay_result["id"]
        drill_payload["status"] = "succeeded"
        drill_payload["latest_replayable_day"] = latest_replayable_day
        if latest_replayable_day is not None:
            drill_payload["completed_trading_day_delta"] = max(
                0, (date.today() - latest_replayable_day).days
            )
        drill_payload["drill_completed_at"] = utc_now()
        return persist_recovery_record(drill_payload)
    except Exception as exc:
        drill_payload["abort_reason"] = str(exc)
        drill_payload["drill_completed_at"] = utc_now()
        drill_id = None
        try:
            persisted = persist_recovery_record(drill_payload)
        except DataAccessError:
            logger.exception(
                "Failed to persist recovery failure raw_payload_id=%s",
                raw_record.id,
            )
        else:
            drill_id = persisted["id"]
        logger.warning(
            "Recovery drill failed drill_id=%s raw_payload_id=%s reason=%s",
            drill_id,
            raw_record.id,
            exc,
        )
        if isinstance(exc, (ValueError, UnsupportedConfigurationError)):
            raise UnsupportedConfigurationError(str(exc)) from exc
        raise DataAccessError("Failed to execute recovery drill.") from exc


def list_recovery_drills(limit: int = 20) -> list[dict]:
    return list_recovery_records(limit=limit)
