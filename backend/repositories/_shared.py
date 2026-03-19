from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ..time_utils import utc_now

MEMORY_FALLBACK_LIMIT = 200
_OLDEST_CREATED_AT = datetime.min.replace(tzinfo=timezone.utc)

MEMORY_RUNS: dict[str, dict[str, Any]] = {}
MEMORY_REPLAYS: list[dict[str, Any]] = []
MEMORY_DRILLS: list[dict[str, Any]] = []
MEMORY_LIFECYCLE: list[dict[str, Any]] = []
MEMORY_IMPORTANT_EVENTS: list[dict[str, Any]] = []
MEMORY_COUNTERS = {
    "replay": 1,
    "drill": 1,
    "lifecycle": 1,
    "important_event": 1,
}


def json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return deepcopy(fallback)
    return json.loads(value)


def next_memory_id(name: str) -> int:
    current = MEMORY_COUNTERS[name]
    MEMORY_COUNTERS[name] += 1
    return current


def _record_created_at(record: dict[str, Any]) -> datetime:
    created_at = record.get("created_at")
    if isinstance(created_at, datetime):
        return created_at
    return _OLDEST_CREATED_AT


def trim_memory_mapping(store: dict[str, dict[str, Any]]) -> None:
    overflow = len(store) - MEMORY_FALLBACK_LIMIT
    if overflow <= 0:
        return

    oldest_keys = sorted(
        store,
        key=lambda key: (_record_created_at(store[key]), key),
    )[:overflow]
    for key in oldest_keys:
        store.pop(key, None)


def remember_memory_mapping(
    store: dict[str, dict[str, Any]], key: str, record: dict[str, Any]
) -> None:
    store[key] = deepcopy(record)
    trim_memory_mapping(store)


def trim_memory_records(store: list[dict[str, Any]]) -> None:
    overflow = len(store) - MEMORY_FALLBACK_LIMIT
    if overflow <= 0:
        return

    store.sort(key=_record_created_at)
    del store[:overflow]


def append_memory_record(store: list[dict[str, Any]], record: dict[str, Any]) -> None:
    store.append(deepcopy(record))
    trim_memory_records(store)


def normalize_created_at(value: datetime | None) -> datetime:
    return value or utc_now()
