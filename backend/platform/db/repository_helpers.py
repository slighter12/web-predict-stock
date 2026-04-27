from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from typing import Any


def clone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(payload)


def json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=_json_default, sort_keys=True)


def json_loads(value: str | None, default: Any) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def normalize_created_at(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _json_default(value: Any) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
