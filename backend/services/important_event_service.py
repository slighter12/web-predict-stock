from __future__ import annotations

from ..repositories.important_event_repository import (
    list_important_event_records,
    upsert_important_event_record,
)


def save_important_event(payload: dict) -> dict:
    return upsert_important_event_record(payload)


def list_important_events(limit: int = 50) -> list[dict]:
    return list_important_event_records(limit=limit)
