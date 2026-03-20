from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

from scripts import scraper

from ..repositories.ingestion_watchlist_repository import list_watchlist_entries
from ..repositories.scheduled_ingestion_repository import (
    get_scheduled_ingestion_run,
    list_scheduled_ingestion_runs,
    persist_scheduled_ingestion_attempt,
    persist_scheduled_ingestion_run,
)
from ..time_utils import utc_now

logger = logging.getLogger(__name__)

MAX_SCHEDULED_INGESTION_ATTEMPTS = 3
MARKET_TIMEZONES = {
    "TW": "Asia/Taipei",
    "US": "America/New_York",
}


def _resolve_scheduled_for_date(
    market: str,
    scheduled_for_date: date | None,
    reference_time: datetime | None,
) -> date:
    if scheduled_for_date is not None:
        return scheduled_for_date
    local_now = (reference_time or utc_now()).astimezone(
        ZoneInfo(MARKET_TIMEZONES.get(market, "UTC"))
    )
    return local_now.date()


def _run_watchlist_attempt(
    watchlist: dict,
    scheduled_for_date: date,
    existing_run: dict | None,
) -> dict:
    attempt_number = int(existing_run["attempt_count"]) + 1 if existing_run else 1
    started_at = utc_now()
    raw_payload_id = None
    error_message = None
    status = "failed"

    try:
        summary = scraper.ingest_symbol(
            symbol=watchlist["symbol"],
            market=watchlist["market"],
            years=int(watchlist["years"]),
            date_str=scheduled_for_date.strftime("%Y%m%d"),
        )
        daily_update = summary.get("daily_update") or {}
        backfill = summary.get("backfill") or {}
        raw_payload_id = daily_update.get("raw_payload_id") or backfill.get(
            "raw_payload_id"
        )
        if raw_payload_id is not None:
            status = "succeeded"
        else:
            error_message = "Scheduled ingestion did not persist a raw payload."
    except Exception as exc:
        error_message = str(exc)
        logger.warning(
            "Scheduled ingestion failed symbol=%s market=%s scheduled_for_date=%s reason=%s",
            watchlist["symbol"],
            watchlist["market"],
            scheduled_for_date,
            exc,
        )

    completed_at = utc_now()
    is_final = status == "succeeded" or attempt_number >= MAX_SCHEDULED_INGESTION_ATTEMPTS
    run_payload = {
        "id": existing_run["id"] if existing_run else None,
        "watchlist_id": watchlist["id"],
        "symbol": watchlist["symbol"],
        "market": watchlist["market"],
        "scheduled_for_date": scheduled_for_date,
        "status": status,
        "attempt_count": attempt_number,
        "last_error_message": error_message,
        "first_attempt_at": (
            existing_run["first_attempt_at"] if existing_run else started_at
        ),
        "last_attempt_at": completed_at,
        "completed_at": completed_at if is_final else None,
    }
    persisted_run = persist_scheduled_ingestion_run(run_payload)
    persist_scheduled_ingestion_attempt(
        persisted_run["id"],
        {
            "attempt_number": attempt_number,
            "status": status,
            "raw_payload_id": raw_payload_id,
            "error_message": error_message,
            "started_at": started_at,
            "completed_at": completed_at,
        },
    )
    return (
        get_scheduled_ingestion_run(watchlist["id"], scheduled_for_date)
        or persisted_run
    )


def dispatch_due_scheduled_ingestions(
    *,
    scheduled_for_date: date | None = None,
    reference_time: datetime | None = None,
) -> dict[str, int | list[dict]]:
    watchlist_entries = list_watchlist_entries(limit=500, active_only=True)
    dispatched: list[dict] = []
    skipped_count = 0

    for watchlist in watchlist_entries:
        slot_date = _resolve_scheduled_for_date(
            watchlist["market"],
            scheduled_for_date,
            reference_time,
        )
        existing_run = get_scheduled_ingestion_run(watchlist["id"], slot_date)
        if existing_run is not None:
            if existing_run["status"] == "succeeded":
                skipped_count += 1
                continue
            if int(existing_run["attempt_count"]) >= MAX_SCHEDULED_INGESTION_ATTEMPTS:
                skipped_count += 1
                continue
        dispatched.append(
            _run_watchlist_attempt(
                watchlist=watchlist,
                scheduled_for_date=slot_date,
                existing_run=existing_run,
            )
        )

    failed_count = sum(1 for item in dispatched if item["status"] == "failed")
    succeeded_count = sum(1 for item in dispatched if item["status"] == "succeeded")
    return {
        "schedule_count": len(watchlist_entries),
        "dispatched_count": len(dispatched),
        "succeeded_count": succeeded_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "records": dispatched,
    }


def list_recent_scheduled_ingestion_runs(limit: int = 50) -> list[dict]:
    return list_scheduled_ingestion_runs(limit=limit)
