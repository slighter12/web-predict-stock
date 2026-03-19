from __future__ import annotations

from ..repositories.lifecycle_repository import (
    list_lifecycle_records,
    upsert_lifecycle_record,
)


def save_lifecycle_record(payload: dict) -> dict:
    return upsert_lifecycle_record(payload)


def list_lifecycle(limit: int = 50) -> list[dict]:
    return list_lifecycle_records(limit=limit)
