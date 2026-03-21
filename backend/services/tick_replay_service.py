from __future__ import annotations

import logging

from ..errors import DataAccessError, UnsupportedConfigurationError
from ..repositories.tick_archive_repository import (
    get_tick_archive_object,
    list_tick_restore_runs,
    persist_tick_restore_run,
    replace_tick_observations,
)
from ..time_utils import utc_now
from .benchmark_profile_service import assert_benchmark_profile_exists
from .tick_archive_provider import parse_archive_entry
from .tick_archive_storage import read_archive_entries

logger = logging.getLogger(__name__)
_MIN_THROUGHPUT_ELAPSED_SECONDS = 1e-6


def create_tick_replay(
    *,
    archive_object_id: int,
    benchmark_profile_id: str | None = None,
    notes: str | None = None,
) -> dict:
    assert_benchmark_profile_exists(benchmark_profile_id)
    archive_object = get_tick_archive_object(archive_object_id)
    started_at = utc_now()
    replay_payload = {
        "archive_object_id": archive_object_id,
        "benchmark_profile_id": benchmark_profile_id,
        "notes": notes,
        "restore_status": "failed",
        "restored_row_count": 0,
        "restore_started_at": started_at,
        "restore_completed_at": None,
        "elapsed_seconds": None,
        "throughput_gb_per_minute": None,
        "abort_reason": None,
    }
    archive_object_reference = f"tick_archive_object:{archive_object_id}"

    try:
        archive_entries = read_archive_entries(archive_object["object_key"])
        observations: list[dict] = []
        for entry in archive_entries:
            observations.extend(parse_archive_entry(entry))
        restored_row_count = replace_tick_observations(
            archive_object_reference,
            observations,
        )
        completed_at = utc_now()
        elapsed_seconds = max(
            0.0,
            (completed_at - started_at).total_seconds(),
        )
        throughput = (
            (archive_object["compressed_bytes"] / (1024**3))
            / (elapsed_seconds / 60)
            if archive_object["compressed_bytes"] > 0
            and elapsed_seconds > _MIN_THROUGHPUT_ELAPSED_SECONDS
            else None
        )
        replay_payload["restore_status"] = "succeeded"
        replay_payload["restored_row_count"] = restored_row_count
        replay_payload["restore_completed_at"] = completed_at
        replay_payload["elapsed_seconds"] = elapsed_seconds
        replay_payload["throughput_gb_per_minute"] = throughput
        return persist_tick_restore_run(replay_payload)
    except Exception as exc:
        replay_payload["abort_reason"] = str(exc)
        replay_payload["restore_completed_at"] = utc_now()
        try:
            persisted = persist_tick_restore_run(replay_payload)
        except DataAccessError:
            logger.exception(
                "Failed to persist tick replay failure archive_object_id=%s",
                archive_object_id,
            )
        else:
            logger.warning(
                "Tick replay failed replay_id=%s archive_object_id=%s reason=%s",
                persisted["id"],
                archive_object_id,
                exc,
            )
        if isinstance(exc, ValueError):
            raise UnsupportedConfigurationError(str(exc)) from exc
        if isinstance(exc, DataAccessError):
            raise
        raise DataAccessError("Failed to replay tick archive.") from exc


def list_tick_replays(limit: int = 20) -> list[dict]:
    return list_tick_restore_runs(limit=limit)
