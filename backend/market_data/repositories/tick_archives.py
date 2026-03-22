from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import delete, desc, distinct, or_, select

from backend.database import (
    DailyOHLCV,
    SessionLocal,
    SymbolLifecycleRecord,
    TickArchiveObject,
    TickArchiveRun,
    TickObservation,
    TickRestoreRun,
    TwCompanyProfile,
)
from backend.platform.db.repository_helpers import (
    clone_payload,
    json_dumps,
    normalize_created_at,
)
from backend.platform.errors import DataAccessError, DataNotFoundError

logger = logging.getLogger(__name__)

_ACTIVE_LIFECYCLE_EVENTS = {"listing", "re_listing"}


def _tick_archive_run_row_to_dict(row: TickArchiveRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "source_name": row.source_name,
        "market": row.market,
        "trading_date": row.trading_date,
        "trigger_mode": row.trigger_mode,
        "scope": row.scope,
        "status": row.status,
        "notes": row.notes,
        "symbol_count": row.symbol_count,
        "request_count": row.request_count,
        "observation_count": row.observation_count,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "abort_reason": row.abort_reason,
        "created_at": normalize_created_at(row.created_at),
    }


def _tick_archive_object_row_to_dict(row: TickArchiveObject) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "storage_backend": row.storage_backend,
        "object_key": row.object_key,
        "compression_codec": row.compression_codec,
        "archive_layout_version": row.archive_layout_version,
        "compressed_bytes": row.compressed_bytes,
        "uncompressed_bytes": row.uncompressed_bytes,
        "compression_ratio": row.compression_ratio,
        "record_count": row.record_count,
        "first_observation_ts": row.first_observation_ts,
        "last_observation_ts": row.last_observation_ts,
        "checksum": row.checksum,
        "retention_class": row.retention_class,
        "backup_backend": row.backup_backend,
        "backup_object_key": row.backup_object_key,
        "backup_status": row.backup_status,
        "backup_completed_at": row.backup_completed_at,
        "backup_error": row.backup_error,
        "created_at": normalize_created_at(row.created_at),
    }


def _tick_restore_run_row_to_dict(row: TickRestoreRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "archive_object_id": row.archive_object_id,
        "benchmark_profile_id": row.benchmark_profile_id,
        "notes": row.notes,
        "restore_status": row.restore_status,
        "restored_row_count": row.restored_row_count,
        "restore_started_at": row.restore_started_at,
        "restore_completed_at": row.restore_completed_at,
        "elapsed_seconds": row.elapsed_seconds,
        "throughput_gb_per_minute": row.throughput_gb_per_minute,
        "abort_reason": row.abort_reason,
        "created_at": normalize_created_at(row.created_at),
    }


def persist_tick_archive_run(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    try:
        with SessionLocal() as session:
            row = None
            if record.get("id") is not None:
                row = session.get(TickArchiveRun, record["id"])
            if row is None:
                row = TickArchiveRun()
            row.source_name = record["source_name"]
            row.market = record["market"]
            row.trading_date = record["trading_date"]
            row.trigger_mode = record["trigger_mode"]
            row.scope = record["scope"]
            row.status = record["status"]
            row.notes = record.get("notes")
            row.symbol_count = record.get("symbol_count", 0)
            row.request_count = record.get("request_count", 0)
            row.observation_count = record.get("observation_count", 0)
            row.started_at = record["started_at"]
            row.completed_at = record.get("completed_at")
            row.abort_reason = record.get("abort_reason")
            session.add(row)
            session.commit()
            session.refresh(row)
            return _tick_archive_run_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist tick archive run trading_date=%s trigger_mode=%s",
            record.get("trading_date"),
            record.get("trigger_mode"),
        )
        raise DataAccessError("Failed to persist tick archive run.") from exc


def list_tick_archive_runs(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(TickArchiveRun)
                .order_by(desc(TickArchiveRun.created_at), desc(TickArchiveRun.id))
                .limit(limit)
            )
            return [
                _tick_archive_run_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list tick archive runs")
        raise DataAccessError("Failed to list tick archive runs.") from exc


def persist_tick_archive_object(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    try:
        with SessionLocal() as session:
            row = TickArchiveObject(
                run_id=record["run_id"],
                storage_backend=record["storage_backend"],
                object_key=record["object_key"],
                compression_codec=record["compression_codec"],
                archive_layout_version=record["archive_layout_version"],
                compressed_bytes=record["compressed_bytes"],
                uncompressed_bytes=record["uncompressed_bytes"],
                compression_ratio=record["compression_ratio"],
                record_count=record["record_count"],
                first_observation_ts=record.get("first_observation_ts"),
                last_observation_ts=record.get("last_observation_ts"),
                checksum=record["checksum"],
                retention_class=record["retention_class"],
                backup_backend=record.get("backup_backend"),
                backup_object_key=record.get("backup_object_key"),
                backup_status=record.get("backup_status"),
                backup_completed_at=record.get("backup_completed_at"),
                backup_error=record.get("backup_error"),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _tick_archive_object_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist tick archive object run_id=%s object_key=%s",
            record.get("run_id"),
            record.get("object_key"),
        )
        raise DataAccessError("Failed to persist tick archive object.") from exc


def get_tick_archive_object(object_id: int) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = session.get(TickArchiveObject, object_id)
            if row is None:
                raise DataNotFoundError(
                    f"Tick archive object '{object_id}' was not found."
                )
            return _tick_archive_object_row_to_dict(row)
    except DataNotFoundError:
        raise
    except Exception as exc:
        logger.exception("Failed to load tick archive object object_id=%s", object_id)
        raise DataAccessError("Failed to load tick archive object.") from exc


def list_tick_archive_objects(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(TickArchiveObject)
                .order_by(
                    desc(TickArchiveObject.created_at), desc(TickArchiveObject.id)
                )
                .limit(limit)
            )
            return [
                _tick_archive_object_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list tick archive objects")
        raise DataAccessError("Failed to list tick archive objects.") from exc


def delete_tick_archive_objects(object_ids: Iterable[int]) -> int:
    ids = [int(item) for item in object_ids if item is not None]
    if not ids:
        return 0
    try:
        with SessionLocal() as session:
            result = session.execute(
                delete(TickArchiveObject).where(TickArchiveObject.id.in_(ids))
            )
            session.commit()
            return int(result.rowcount or 0)
    except Exception as exc:
        logger.exception("Failed to delete tick archive objects object_ids=%s", ids)
        raise DataAccessError("Failed to delete tick archive objects.") from exc


def persist_tick_restore_run(payload: dict[str, Any]) -> dict[str, Any]:
    record = clone_payload(payload)
    try:
        with SessionLocal() as session:
            row = None
            if record.get("id") is not None:
                row = session.get(TickRestoreRun, record["id"])
            if row is None:
                row = TickRestoreRun()
            row.archive_object_id = record["archive_object_id"]
            row.benchmark_profile_id = record.get("benchmark_profile_id")
            row.notes = record.get("notes")
            row.restore_status = record["restore_status"]
            row.restored_row_count = record.get("restored_row_count", 0)
            row.restore_started_at = record["restore_started_at"]
            row.restore_completed_at = record.get("restore_completed_at")
            row.elapsed_seconds = record.get("elapsed_seconds")
            row.throughput_gb_per_minute = record.get("throughput_gb_per_minute")
            row.abort_reason = record.get("abort_reason")
            session.add(row)
            session.commit()
            session.refresh(row)
            return _tick_restore_run_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist tick restore run archive_object_id=%s",
            record.get("archive_object_id"),
        )
        raise DataAccessError("Failed to persist tick restore run.") from exc


def list_tick_restore_runs(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(TickRestoreRun)
                .order_by(desc(TickRestoreRun.created_at), desc(TickRestoreRun.id))
                .limit(limit)
            )
            return [
                _tick_restore_run_row_to_dict(row)
                for row in session.execute(stmt).scalars().all()
            ]
    except Exception as exc:
        logger.exception("Failed to list tick restore runs")
        raise DataAccessError("Failed to list tick restore runs.") from exc


def replace_tick_observations(
    archive_object_reference: str, observations: Iterable[dict[str, Any]]
) -> int:
    try:
        with SessionLocal() as session:
            session.execute(
                delete(TickObservation).where(
                    TickObservation.archive_object_reference == archive_object_reference
                )
            )
            rows = list(observations)
            for record in rows:
                session.add(
                    TickObservation(
                        trading_date=record["trading_date"],
                        observation_ts=record["observation_ts"],
                        symbol=record["symbol"],
                        market=record["market"],
                        last_price=record.get("last_price"),
                        last_size=record.get("last_size"),
                        cumulative_volume=record.get("cumulative_volume"),
                        best_bid_prices_json=json_dumps(
                            record.get("best_bid_prices", [])
                        )
                        or "[]",
                        best_bid_sizes_json=json_dumps(record.get("best_bid_sizes", []))
                        or "[]",
                        best_ask_prices_json=json_dumps(
                            record.get("best_ask_prices", [])
                        )
                        or "[]",
                        best_ask_sizes_json=json_dumps(record.get("best_ask_sizes", []))
                        or "[]",
                        source_name=record["source_name"],
                        archive_object_reference=archive_object_reference,
                        parser_version=record["parser_version"],
                    )
                )
            session.commit()
            return len(rows)
    except Exception as exc:
        logger.exception(
            "Failed to replace tick observations archive_object_reference=%s",
            archive_object_reference,
        )
        raise DataAccessError("Failed to persist tick observations.") from exc


def list_recent_tick_archive_trading_dates(
    *,
    market: str = "TW",
    limit: int = 20,
    statuses: Iterable[str] | None = None,
) -> list[date]:
    try:
        with SessionLocal() as session:
            stmt = select(distinct(TickArchiveRun.trading_date)).where(
                TickArchiveRun.market == market
            )
            normalized_statuses = [item for item in (statuses or []) if item]
            if normalized_statuses:
                stmt = stmt.where(TickArchiveRun.status.in_(normalized_statuses))
            stmt = stmt.order_by(desc(TickArchiveRun.trading_date)).limit(limit)
            return [item for item in session.execute(stmt).scalars().all() if item]
    except Exception as exc:
        logger.exception("Failed to list recent tick archive trading dates")
        raise DataAccessError(
            "Failed to list recent tick archive trading dates."
        ) from exc


def list_tick_archive_objects_for_dates(
    trading_dates: Iterable[date],
    *,
    market: str = "TW",
    run_statuses: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    dates = list(trading_dates)
    if not dates:
        return []
    try:
        with SessionLocal() as session:
            stmt = (
                select(
                    TickArchiveObject,
                    TickArchiveRun.trading_date,
                    TickArchiveRun.status,
                    TickArchiveRun.source_name,
                    TickArchiveRun.completed_at,
                    TickArchiveRun.created_at,
                )
                .join(TickArchiveRun, TickArchiveRun.id == TickArchiveObject.run_id)
                .where(TickArchiveRun.market == market)
                .where(TickArchiveRun.trading_date.in_(dates))
            )
            normalized_statuses = [item for item in (run_statuses or []) if item]
            if normalized_statuses:
                stmt = stmt.where(TickArchiveRun.status.in_(normalized_statuses))
            stmt = stmt.order_by(
                desc(TickArchiveObject.created_at), desc(TickArchiveObject.id)
            )
            records: list[dict[str, Any]] = []
            for (
                row,
                trading_date,
                run_status,
                source_name,
                run_completed_at,
                run_created_at,
            ) in session.execute(stmt).all():
                record = _tick_archive_object_row_to_dict(row)
                record["trading_date"] = trading_date
                record["run_status"] = run_status
                record["source_name"] = source_name
                record["run_completed_at"] = normalize_created_at(run_completed_at)
                record["run_created_at"] = normalize_created_at(run_created_at)
                records.append(record)
            return records
    except Exception as exc:
        logger.exception("Failed to list tick archive objects for KPI window")
        raise DataAccessError("Failed to list tick archive objects.") from exc


def list_tick_restore_runs_for_dates(
    trading_dates: Iterable[date],
    *,
    market: str = "TW",
    benchmark_only: bool = False,
    archive_run_statuses: Iterable[str] | None = None,
    restore_statuses: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    dates = list(trading_dates)
    if not dates:
        return []
    try:
        with SessionLocal() as session:
            stmt = (
                select(
                    TickRestoreRun,
                    TickArchiveObject.compressed_bytes,
                    TickArchiveRun.trading_date,
                    TickArchiveRun.status,
                )
                .join(
                    TickArchiveObject,
                    TickArchiveObject.id == TickRestoreRun.archive_object_id,
                )
                .join(TickArchiveRun, TickArchiveRun.id == TickArchiveObject.run_id)
                .where(TickArchiveRun.market == market)
                .where(TickArchiveRun.trading_date.in_(dates))
            )
            if benchmark_only:
                stmt = stmt.where(TickRestoreRun.benchmark_profile_id.is_not(None))
            normalized_archive_run_statuses = [
                item for item in (archive_run_statuses or []) if item
            ]
            if normalized_archive_run_statuses:
                stmt = stmt.where(
                    TickArchiveRun.status.in_(normalized_archive_run_statuses)
                )
            normalized_restore_statuses = [
                item for item in (restore_statuses or []) if item
            ]
            if normalized_restore_statuses:
                stmt = stmt.where(
                    TickRestoreRun.restore_status.in_(normalized_restore_statuses)
                )
            stmt = stmt.order_by(
                desc(TickRestoreRun.created_at), desc(TickRestoreRun.id)
            )
            records: list[dict[str, Any]] = []
            for (
                row,
                compressed_bytes,
                trading_date,
                archive_run_status,
            ) in session.execute(stmt).all():
                record = _tick_restore_run_row_to_dict(row)
                record["compressed_bytes"] = compressed_bytes
                record["trading_date"] = trading_date
                record["archive_run_status"] = archive_run_status
                records.append(record)
            return records
    except Exception as exc:
        logger.exception("Failed to list tick restore runs for KPI window")
        raise DataAccessError("Failed to list tick restore runs.") from exc


def resolve_tw_tick_archive_symbols(*, trading_date: date) -> list[str]:
    try:
        with SessionLocal() as session:
            company_stmt = (
                select(TwCompanyProfile.symbol)
                .where(TwCompanyProfile.market == "TW")
                .where(TwCompanyProfile.trading_status == "active")
                .where(TwCompanyProfile.exchange.in_(("TWSE", "TPEX")))
                .where(
                    or_(
                        TwCompanyProfile.listing_date.is_(None),
                        TwCompanyProfile.listing_date <= trading_date,
                    )
                )
                .order_by(
                    TwCompanyProfile.exchange.asc(), TwCompanyProfile.symbol.asc()
                )
            )
            company_symbols = [
                item for item in session.execute(company_stmt).scalars().all() if item
            ]

            lifecycle_rows = (
                session.execute(
                    select(SymbolLifecycleRecord).where(
                        SymbolLifecycleRecord.market == "TW",
                        SymbolLifecycleRecord.effective_date <= trading_date,
                    )
                )
                .scalars()
                .all()
            )
            latest_events: dict[str, SymbolLifecycleRecord] = {}
            for row in lifecycle_rows:
                current = latest_events.get(row.symbol)
                if current is None or (
                    row.effective_date,
                    row.id,
                ) > (current.effective_date, current.id):
                    latest_events[row.symbol] = row
            active_symbols = sorted(
                symbol
                for symbol, row in latest_events.items()
                if row.event_type in _ACTIVE_LIFECYCLE_EVENTS
            )

            stmt = (
                select(distinct(DailyOHLCV.symbol))
                .where(DailyOHLCV.market == "TW")
                .where(DailyOHLCV.date <= trading_date)
                .order_by(DailyOHLCV.symbol)
            )
            daily_symbols = [
                item for item in session.execute(stmt).scalars().all() if item
            ]

            combined_symbols = sorted(set(company_symbols) | set(active_symbols))
            if combined_symbols:
                # Keep the company snapshot + lifecycle-derived active set
                # authoritative for current coverage. Only fall back to the
                # broader daily universe when curated sources are unavailable.
                return combined_symbols
            return daily_symbols
    except Exception as exc:
        logger.exception("Failed to resolve TW tick archive symbols")
        raise DataAccessError("Failed to resolve TW tick archive symbols.") from exc
