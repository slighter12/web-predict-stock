from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import desc, select

from ..database import ScheduledIngestionAttempt, ScheduledIngestionRun, SessionLocal
from ..errors import DataAccessError
from ._shared import normalize_created_at

logger = logging.getLogger(__name__)


def _attempt_row_to_dict(row: ScheduledIngestionAttempt) -> dict[str, Any]:
    return {
        "id": row.id,
        "attempt_number": row.attempt_number,
        "status": row.status,
        "raw_payload_id": row.raw_payload_id,
        "error_message": row.error_message,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "created_at": normalize_created_at(row.created_at),
    }


def _run_row_to_dict(
    row: ScheduledIngestionRun, attempts: list[ScheduledIngestionAttempt] | None = None
) -> dict[str, Any]:
    payload = {
        "id": row.id,
        "watchlist_id": row.watchlist_id,
        "symbol": row.symbol,
        "market": row.market,
        "scheduled_for_date": row.scheduled_for_date,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "last_error_message": row.last_error_message,
        "first_attempt_at": row.first_attempt_at,
        "last_attempt_at": row.last_attempt_at,
        "completed_at": row.completed_at,
        "created_at": normalize_created_at(row.created_at),
    }
    if attempts is not None:
        payload["attempts"] = [_attempt_row_to_dict(item) for item in attempts]
    return payload


def get_scheduled_ingestion_run(
    watchlist_id: int, scheduled_for_date: date
) -> dict[str, Any] | None:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ScheduledIngestionRun)
                .where(ScheduledIngestionRun.watchlist_id == watchlist_id)
                .where(ScheduledIngestionRun.scheduled_for_date == scheduled_for_date)
                .limit(1)
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                return None
            attempt_stmt = (
                select(ScheduledIngestionAttempt)
                .where(ScheduledIngestionAttempt.run_id == row.id)
                .order_by(ScheduledIngestionAttempt.attempt_number)
            )
            attempts = session.execute(attempt_stmt).scalars().all()
            return _run_row_to_dict(row, attempts)
    except Exception as exc:
        logger.exception(
            "Failed to load scheduled ingestion run watchlist_id=%s scheduled_for_date=%s",
            watchlist_id,
            scheduled_for_date,
        )
        raise DataAccessError("Failed to load scheduled ingestion run.") from exc


def persist_scheduled_ingestion_run(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = None
            if payload.get("id") is not None:
                row = session.get(ScheduledIngestionRun, payload["id"])
            if row is None:
                row = ScheduledIngestionRun()
            row.watchlist_id = payload["watchlist_id"]
            row.symbol = payload["symbol"]
            row.market = payload["market"]
            row.scheduled_for_date = payload["scheduled_for_date"]
            row.status = payload["status"]
            row.attempt_count = payload["attempt_count"]
            row.last_error_message = payload.get("last_error_message")
            row.first_attempt_at = payload.get("first_attempt_at")
            row.last_attempt_at = payload.get("last_attempt_at")
            row.completed_at = payload.get("completed_at")
            session.add(row)
            session.commit()
            session.refresh(row)
            attempts = (
                session.execute(
                    select(ScheduledIngestionAttempt)
                    .where(ScheduledIngestionAttempt.run_id == row.id)
                    .order_by(ScheduledIngestionAttempt.attempt_number)
                )
                .scalars()
                .all()
            )
            return _run_row_to_dict(row, attempts)
    except Exception as exc:
        logger.exception(
            "Failed to persist scheduled ingestion run symbol=%s market=%s scheduled_for_date=%s",
            payload["symbol"],
            payload["market"],
            payload["scheduled_for_date"],
        )
        raise DataAccessError("Failed to persist scheduled ingestion run.") from exc


def persist_scheduled_ingestion_attempt(
    run_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        with SessionLocal() as session:
            row = ScheduledIngestionAttempt(
                run_id=run_id,
                attempt_number=payload["attempt_number"],
                status=payload["status"],
                raw_payload_id=payload.get("raw_payload_id"),
                error_message=payload.get("error_message"),
                started_at=payload["started_at"],
                completed_at=payload.get("completed_at"),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _attempt_row_to_dict(row)
    except Exception as exc:
        logger.exception(
            "Failed to persist scheduled ingestion attempt run_id=%s attempt_number=%s",
            run_id,
            payload["attempt_number"],
        )
        raise DataAccessError("Failed to persist scheduled ingestion attempt.") from exc


def list_scheduled_ingestion_runs(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with SessionLocal() as session:
            stmt = (
                select(ScheduledIngestionRun)
                .order_by(
                    desc(ScheduledIngestionRun.scheduled_for_date),
                    desc(ScheduledIngestionRun.id),
                )
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            run_ids = [row.id for row in rows]
            attempts_by_run: dict[int, list[ScheduledIngestionAttempt]] = {
                run_id: [] for run_id in run_ids
            }
            if run_ids:
                attempt_stmt = (
                    select(ScheduledIngestionAttempt)
                    .where(ScheduledIngestionAttempt.run_id.in_(run_ids))
                    .order_by(
                        ScheduledIngestionAttempt.run_id,
                        ScheduledIngestionAttempt.attempt_number,
                    )
                )
                for attempt in session.execute(attempt_stmt).scalars().all():
                    attempts_by_run.setdefault(attempt.run_id, []).append(attempt)
            return [
                _run_row_to_dict(row, attempts_by_run.get(row.id, [])) for row in rows
            ]
    except Exception as exc:
        logger.exception("Failed to list scheduled ingestion runs from DB")
        raise DataAccessError("Failed to list scheduled ingestion runs.") from exc
