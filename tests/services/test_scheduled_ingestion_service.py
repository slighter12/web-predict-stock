from __future__ import annotations

from datetime import date, datetime, timezone

import backend.services.scheduled_ingestion_service as scheduled_ingestion_service
from backend.database import ScheduledIngestionAttempt, ScheduledIngestionRun


def test_dispatch_due_scheduled_ingestions_creates_run_and_attempt(monkeypatch):
    persisted_runs: list[dict] = []
    persisted_attempts: list[dict] = []
    final_run = {
        "id": 7,
        "watchlist_id": 1,
        "symbol": "2330",
        "market": "TW",
        "scheduled_for_date": date(2026, 3, 20),
        "status": "succeeded",
        "attempt_count": 1,
        "last_error_message": None,
        "first_attempt_at": datetime.now(timezone.utc),
        "last_attempt_at": datetime.now(timezone.utc),
        "completed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "attempts": [],
    }

    monkeypatch.setattr(
        scheduled_ingestion_service,
        "list_watchlist_entries",
        lambda limit=500, active_only=True: [
            {"id": 1, "symbol": "2330", "market": "TW", "years": 5}
        ],
    )
    monkeypatch.setattr(
        scheduled_ingestion_service,
        "get_scheduled_ingestion_run",
        lambda watchlist_id, scheduled_for_date: (
            final_run if persisted_attempts else None
        ),
    )
    monkeypatch.setattr(
        scheduled_ingestion_service.scraper,
        "ingest_symbol",
        lambda **kwargs: {
            "backfill": {"raw_payload_id": None},
            "daily_update": {"raw_payload_id": 41},
        },
    )

    def capture_run(payload):
        persisted_runs.append(payload)
        return {**final_run, **payload, "id": 7, "attempts": []}

    def capture_attempt(run_id, payload):
        persisted_attempts.append({"run_id": run_id, **payload})
        return {"id": 3, **payload}

    monkeypatch.setattr(
        scheduled_ingestion_service, "persist_scheduled_ingestion_run", capture_run
    )
    monkeypatch.setattr(
        scheduled_ingestion_service,
        "persist_scheduled_ingestion_attempt",
        capture_attempt,
    )

    summary = scheduled_ingestion_service.dispatch_due_scheduled_ingestions(
        scheduled_for_date=date(2026, 3, 20)
    )

    assert summary["dispatched_count"] == 1
    assert summary["succeeded_count"] == 1
    assert persisted_runs[0]["attempt_count"] == 1
    assert persisted_attempts[0]["raw_payload_id"] == 41


def test_dispatch_due_scheduled_ingestions_skips_succeeded_and_retry_ceiling(
    monkeypatch,
):
    monkeypatch.setattr(
        scheduled_ingestion_service,
        "list_watchlist_entries",
        lambda limit=500, active_only=True: [
            {"id": 1, "symbol": "2330", "market": "TW", "years": 5},
            {"id": 2, "symbol": "2317", "market": "TW", "years": 5},
        ],
    )

    def existing_run(watchlist_id, scheduled_for_date):
        if watchlist_id == 1:
            return {
                "id": 10,
                "watchlist_id": 1,
                "status": "succeeded",
                "attempt_count": 1,
                "first_attempt_at": None,
            }
        return {
            "id": 11,
            "watchlist_id": 2,
            "status": "failed",
            "attempt_count": scheduled_ingestion_service.MAX_SCHEDULED_INGESTION_ATTEMPTS,
            "first_attempt_at": None,
        }

    monkeypatch.setattr(
        scheduled_ingestion_service, "get_scheduled_ingestion_run", existing_run
    )

    summary = scheduled_ingestion_service.dispatch_due_scheduled_ingestions(
        scheduled_for_date=date(2026, 3, 20)
    )

    assert summary["dispatched_count"] == 0
    assert summary["skipped_count"] == 2


def test_scheduled_ingestion_foreign_key_delete_policies():
    run_foreign_keys = list(ScheduledIngestionRun.__table__.c.watchlist_id.foreign_keys)
    attempt_foreign_keys = list(
        ScheduledIngestionAttempt.__table__.c.run_id.foreign_keys
    )

    assert len(run_foreign_keys) == 1
    assert run_foreign_keys[0].target_fullname == "ingestion_watchlist.id"
    assert run_foreign_keys[0].ondelete == "RESTRICT"
    assert len(attempt_foreign_keys) == 1
    assert attempt_foreign_keys[0].target_fullname == "scheduled_ingestion_runs.id"
    assert attempt_foreign_keys[0].ondelete == "CASCADE"
