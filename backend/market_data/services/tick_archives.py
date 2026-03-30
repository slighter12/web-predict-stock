from __future__ import annotations

import logging
import os
from datetime import date

from backend.market_data.repositories.tick_archives import (
    delete_tick_archive_objects,
    list_tick_archive_objects,
    list_tick_archive_runs,
    persist_tick_archive_object,
    persist_tick_archive_run,
    resolve_tw_tick_archive_symbols,
)
from backend.market_data.services._normalization import clean_optional_text
from backend.market_data.services.tick_archive_provider import (
    TWSE_PUBLIC_SNAPSHOT_SOURCE,
    fetch_twse_public_snapshot,
    parse_archive_entry,
)
from backend.market_data.services.tick_archive_storage import (
    delete_archive_object,
    delete_google_drive_archive_mirror,
    mirror_archive_to_google_drive,
    read_archive_entries,
    write_archive_part,
    write_normalized_archive_part,
    write_uploaded_archive,
)
from backend.platform.errors import (
    DataAccessError,
    ExternalFetchError,
    UnsupportedConfigurationError,
)
from backend.platform.time import utc_now

logger = logging.getLogger(__name__)

TICK_ARCHIVE_CHUNK_SIZE = 50
TICK_ARCHIVE_LAYOUT_VERSION = "twse_public_observation_v1"
TICK_ARCHIVE_RETENTION_CLASS = "provisional_until_tbd_002_resolved"
TICK_STORAGE_BACKEND = "local_filesystem"
TICK_COMPRESSION_CODEC = "gzip"
TICK_ARCHIVE_BACKUP_REQUIRED_ENV = "TICK_ARCHIVE_BACKUP_REQUIRED"


def _chunk_symbols(symbols: list[str], chunk_size: int) -> list[list[str]]:
    return [
        symbols[index : index + chunk_size]
        for index in range(0, len(symbols), chunk_size)
    ]


def _base_run_payload(
    *,
    market: str,
    trading_date: date,
    trigger_mode: str,
    scope: str,
    notes: str | None,
) -> dict:
    return {
        "source_name": TWSE_PUBLIC_SNAPSHOT_SOURCE,
        "market": market,
        "trading_date": trading_date,
        "trigger_mode": trigger_mode,
        "scope": scope,
        "status": "failed",
        "notes": notes,
        "symbol_count": 0,
        "request_count": 0,
        "observation_count": 0,
        "started_at": utc_now(),
        "completed_at": None,
        "abort_reason": None,
    }


def _build_archive_object_payload(
    *,
    run_id: int,
    file_metadata: dict,
    observations: list[dict],
    backup_metadata: dict | None = None,
) -> dict:
    observation_ts_values = [item["observation_ts"] for item in observations]
    backup_metadata = backup_metadata or {}
    return {
        "run_id": run_id,
        "storage_backend": TICK_STORAGE_BACKEND,
        "object_key": file_metadata["object_key"],
        "compression_codec": TICK_COMPRESSION_CODEC,
        "archive_layout_version": TICK_ARCHIVE_LAYOUT_VERSION,
        "compressed_bytes": file_metadata["compressed_bytes"],
        "uncompressed_bytes": file_metadata["uncompressed_bytes"],
        "compression_ratio": file_metadata["compression_ratio"],
        "record_count": len(observations),
        "first_observation_ts": min(observation_ts_values)
        if observation_ts_values
        else None,
        "last_observation_ts": max(observation_ts_values)
        if observation_ts_values
        else None,
        "checksum": file_metadata["checksum"],
        "retention_class": TICK_ARCHIVE_RETENTION_CLASS,
        "backup_backend": backup_metadata.get("backup_backend"),
        "backup_object_key": backup_metadata.get("backup_object_key"),
        "backup_status": backup_metadata.get("backup_status"),
        "backup_completed_at": backup_metadata.get("backup_completed_at"),
        "backup_error": backup_metadata.get("backup_error"),
    }


def _persist_tick_archive_failure(
    *,
    run_payload: dict,
    reason: Exception | str,
) -> dict | None:
    run_payload["status"] = "failed"
    run_payload["abort_reason"] = str(reason)
    run_payload["completed_at"] = utc_now()
    try:
        return persist_tick_archive_run(run_payload)
    except DataAccessError:
        logger.exception(
            "Failed to persist tick archive failure run_id=%s",
            run_payload.get("id"),
        )
        return None


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _backup_is_required() -> bool:
    return _is_truthy(os.getenv(TICK_ARCHIVE_BACKUP_REQUIRED_ENV))


def _collect_backup_metadata(*, object_key: str) -> dict:
    backup_required = _backup_is_required()
    try:
        backup_metadata = mirror_archive_to_google_drive(object_key=object_key)
    except Exception as exc:
        logger.exception(
            "Tick archive mirror failed object_key=%s reason=%s",
            object_key,
            exc,
        )
        if backup_required:
            raise ValueError(
                "Tick archive backup is required but mirror_archive_to_google_drive "
                f"failed for object_key='{object_key}': {exc}"
            ) from exc
        return {
            "backup_backend": "google_drive_mirror",
            "backup_object_key": None,
            "backup_status": "failed",
            "backup_completed_at": None,
            "backup_error": str(exc),
        }

    backup_status = str(backup_metadata.get("backup_status") or "").strip().lower()
    if backup_required and backup_status != "succeeded":
        if backup_status == "not_configured":
            raise UnsupportedConfigurationError(
                "Tick archive backup is required but "
                "GOOGLE_DRIVE_TICK_ARCHIVE_ROOT is not configured."
            )
        raise ValueError(
            "Tick archive backup is required but did not succeed for "
            f"object_key='{object_key}' (status='{backup_status or 'unknown'}')."
        )
    return backup_metadata


def _translate_tick_archive_dispatch_error(exc: Exception) -> Exception:
    if isinstance(exc, (ValueError, UnsupportedConfigurationError)):
        return exc
    if isinstance(exc, ExternalFetchError):
        return exc
    if isinstance(exc, DataAccessError):
        return exc
    return DataAccessError("Failed to dispatch tick archive crawl.")


def _cleanup_tick_archive_parts(parts: list[dict[str, object]]) -> list[str]:
    cleanup_failures: list[str] = []
    object_ids = [
        int(item["object_id"]) for item in parts if item.get("object_id") is not None
    ]
    if object_ids:
        try:
            delete_tick_archive_objects(object_ids)
        except DataAccessError as exc:
            cleanup_failures.append(f"db_cleanup_failed: {exc}")
    for item in parts:
        backup_object_key = item.get("backup_object_key")
        if isinstance(backup_object_key, str) and backup_object_key:
            try:
                delete_google_drive_archive_mirror(backup_object_key=backup_object_key)
            except ValueError as exc:
                cleanup_failures.append(f"backup_cleanup_failed: {exc}")
        storage_backend = item.get("storage_backend")
        if not isinstance(storage_backend, str):
            continue
        for key_name in ("normalized_object_key", "object_key"):
            object_key = item.get(key_name)
            if not isinstance(object_key, str):
                continue
            try:
                delete_archive_object(
                    object_key=object_key,
                    storage_backend=storage_backend,
                )
            except ValueError as exc:
                cleanup_failures.append(f"storage_cleanup_failed: {exc}")
    return cleanup_failures


def _validate_import_observations(
    *,
    observations: list[dict],
    market: str,
    trading_date: date,
) -> None:
    if not observations:
        raise ValueError("Tick archive import must contain at least one observation.")

    observed_markets = {
        str(item.get("market") or "").strip().upper() for item in observations
    }
    observed_dates = {
        item.get("trading_date")
        for item in observations
        if item.get("trading_date") is not None
    }

    if observed_markets != {market}:
        raise ValueError(
            "Tick archive import market does not match archive observations."
        )
    if observed_dates != {trading_date}:
        raise ValueError(
            "Tick archive import trading_date does not match archive observations."
        )


def create_tick_archive_dispatch(request) -> dict:
    market = request.market.strip().upper()
    if market != "TW":
        raise ValueError("Tick archive dispatch currently supports market 'TW' only.")
    if request.mode != "post_close_crawl":
        raise ValueError("Tick archive dispatch mode must be 'post_close_crawl'.")

    run_payload = _base_run_payload(
        market=market,
        trading_date=request.trading_date,
        trigger_mode=request.mode,
        scope="full_market",
        notes=clean_optional_text(request.notes),
    )
    run = persist_tick_archive_run(run_payload)
    failures: list[str] = []
    failure_exceptions: list[Exception] = []
    persisted_parts: list[dict[str, object]] = []
    observation_count = 0
    request_count = 0
    failure_recorded = False

    try:
        symbols = resolve_tw_tick_archive_symbols(trading_date=request.trading_date)
        if not symbols:
            raise ValueError("No TW symbols are available for tick archive dispatch.")
        run_payload["id"] = run["id"]
        run_payload["symbol_count"] = len(symbols)

        for part_number, chunk in enumerate(
            _chunk_symbols(symbols, TICK_ARCHIVE_CHUNK_SIZE),
            start=1,
        ):
            request_count += 1
            try:
                fetch_result = fetch_twse_public_snapshot(chunk)
                archive_entry = {
                    "source_name": TWSE_PUBLIC_SNAPSHOT_SOURCE,
                    "market": market,
                    "fetch_timestamp": fetch_result["fetch_timestamp"].isoformat(),
                    "request_symbols": fetch_result["request_symbols"],
                    "request_url": fetch_result["request_url"],
                    "response_status": fetch_result["response_status"],
                    "raw_response_body": fetch_result["raw_response_body"],
                }
                file_metadata = write_archive_part(
                    market=market,
                    trading_date=request.trading_date,
                    run_id=run["id"],
                    part_number=part_number,
                    entries=[archive_entry],
                )
                persisted_part = {
                    "object_id": None,
                    "object_key": file_metadata["object_key"],
                    "normalized_object_key": None,
                    "storage_backend": TICK_STORAGE_BACKEND,
                    "backup_object_key": None,
                }
                persisted_parts.append(persisted_part)
                observations = fetch_result["observations"]
                normalized_file_metadata = write_normalized_archive_part(
                    market=market,
                    trading_date=request.trading_date,
                    run_id=run["id"],
                    part_number=part_number,
                    observations=observations,
                )
                persisted_part["normalized_object_key"] = normalized_file_metadata[
                    "object_key"
                ]
                backup_metadata = _collect_backup_metadata(
                    object_key=file_metadata["object_key"]
                )
                persisted_part["backup_object_key"] = backup_metadata.get(
                    "backup_object_key"
                )
                observation_count += len(observations)
                archive_object = persist_tick_archive_object(
                    _build_archive_object_payload(
                        run_id=run["id"],
                        file_metadata=file_metadata,
                        observations=observations,
                        backup_metadata=backup_metadata,
                    )
                )
                persisted_part["object_id"] = archive_object["id"]
            except Exception as exc:
                logger.exception(
                    "Tick archive dispatch failed run_id=%s part_number=%s",
                    run["id"],
                    part_number,
                )
                failures.append(f"part={part_number}: {exc}")
                failure_exceptions.append(exc)

        run_payload["request_count"] = request_count
        run_payload["observation_count"] = observation_count
        if failures or request_count == 0:
            reason = (
                "; ".join(failures[:10])
                if failures
                else "Tick archive dispatch did not produce any archive requests."
            )
            cleanup_failures = _cleanup_tick_archive_parts(persisted_parts)
            if cleanup_failures:
                reason = f"{reason}; {'; '.join(cleanup_failures[:10])}"
            run_payload["observation_count"] = 0
            _persist_tick_archive_failure(run_payload=run_payload, reason=reason)
            failure_recorded = True
            first_exception = (
                failure_exceptions[0] if failure_exceptions else ValueError(reason)
            )
            raise _translate_tick_archive_dispatch_error(first_exception)

        run_payload["status"] = "succeeded"
        run_payload["abort_reason"] = None
        run_payload["completed_at"] = utc_now()
        return persist_tick_archive_run(run_payload)
    except Exception as exc:
        run_payload["id"] = run["id"]
        if not failure_recorded:
            cleanup_failures = _cleanup_tick_archive_parts(persisted_parts)
            failure_reason = str(exc)
            if cleanup_failures:
                failure_reason = f"{failure_reason}; {'; '.join(cleanup_failures[:10])}"
            run_payload["observation_count"] = 0
            _persist_tick_archive_failure(
                run_payload=run_payload, reason=failure_reason
            )
        raise _translate_tick_archive_dispatch_error(exc)


def create_tick_archive_import(
    *,
    market: str,
    trading_date: date,
    notes: str | None,
    file_bytes: bytes,
) -> dict:
    normalized_market = market.strip().upper()
    if normalized_market != "TW":
        raise ValueError("Tick archive import currently supports market 'TW' only.")
    if not file_bytes:
        raise ValueError("Tick archive import file must not be empty.")

    run_payload = _base_run_payload(
        market=normalized_market,
        trading_date=trading_date,
        trigger_mode="manual_import",
        scope="manual_file",
        notes=clean_optional_text(notes),
    )
    run = persist_tick_archive_run(run_payload)
    uploaded_object_key: str | None = None
    uploaded_normalized_object_key: str | None = None
    uploaded_backup_object_key: str | None = None
    try:
        file_metadata = write_uploaded_archive(
            market=normalized_market,
            trading_date=trading_date,
            run_id=run["id"],
            file_bytes=file_bytes,
        )
        uploaded_object_key = file_metadata["object_key"]
        archive_entries = read_archive_entries(file_metadata["object_key"])
        observations: list[dict] = []
        request_symbols: set[str] = set()
        for entry in archive_entries:
            request_symbols.update(entry.get("request_symbols", []) or [])
            observations.extend(parse_archive_entry(entry))
        _validate_import_observations(
            observations=observations,
            market=normalized_market,
            trading_date=trading_date,
        )
        normalized_file_metadata = write_normalized_archive_part(
            market=normalized_market,
            trading_date=trading_date,
            run_id=run["id"],
            part_number=1,
            observations=observations,
        )
        uploaded_normalized_object_key = normalized_file_metadata["object_key"]
        backup_metadata = _collect_backup_metadata(
            object_key=file_metadata["object_key"]
        )
        uploaded_backup_object_key = backup_metadata.get("backup_object_key")
        archive_object = persist_tick_archive_object(
            _build_archive_object_payload(
                run_id=run["id"],
                file_metadata=file_metadata,
                observations=observations,
                backup_metadata=backup_metadata,
            )
        )
        run_payload["id"] = run["id"]
        run_payload["status"] = "succeeded"
        run_payload["symbol_count"] = len(request_symbols)
        run_payload["request_count"] = len(archive_entries)
        run_payload["observation_count"] = len(observations)
        run_payload["completed_at"] = utc_now()
        run = persist_tick_archive_run(run_payload)
        return {"run": run, "archive_object": archive_object}
    except Exception as exc:
        run_payload["id"] = run["id"]
        run_payload["abort_reason"] = str(exc)
        run_payload["completed_at"] = utc_now()
        run = persist_tick_archive_run(run_payload)
        if uploaded_object_key:
            try:
                delete_archive_object(
                    object_key=uploaded_object_key,
                    storage_backend=TICK_STORAGE_BACKEND,
                )
            except ValueError:
                logger.exception(
                    "Failed to cleanup uploaded tick archive run_id=%s object_key=%s",
                    run["id"],
                    uploaded_object_key,
                )
        if uploaded_normalized_object_key:
            try:
                delete_archive_object(
                    object_key=uploaded_normalized_object_key,
                    storage_backend=TICK_STORAGE_BACKEND,
                )
            except ValueError:
                logger.exception(
                    "Failed to cleanup uploaded normalized tick archive run_id=%s object_key=%s",
                    run["id"],
                    uploaded_normalized_object_key,
                )
        if uploaded_backup_object_key:
            try:
                delete_google_drive_archive_mirror(
                    backup_object_key=uploaded_backup_object_key
                )
            except ValueError:
                logger.exception(
                    "Failed to cleanup uploaded tick archive mirror run_id=%s backup_object_key=%s",
                    run["id"],
                    uploaded_backup_object_key,
                )
        raise ValueError(f"Failed to import tick archive: {exc}") from exc


def list_tick_archive_dispatches(limit: int = 20) -> list[dict]:
    return list_tick_archive_runs(limit=limit)


def list_tick_archives(limit: int = 50) -> list[dict]:
    return list_tick_archive_objects(limit=limit)
