from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from ..time_utils import utc_now

_OLDEST_CREATED_AT = datetime.min.replace(tzinfo=timezone.utc)


def clone_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return deepcopy(payload)


def json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return deepcopy(fallback)
    return json.loads(value)


def normalize_created_at(value: datetime | None) -> datetime:
    return value or utc_now()
