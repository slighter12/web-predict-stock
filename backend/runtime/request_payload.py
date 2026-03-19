from __future__ import annotations

import json
from typing import Any

from fastapi import Request


async def read_request_payload(request: Request) -> dict[str, Any] | None:
    try:
        body = await request.body()
    except Exception:
        return None
    if not body:
        return None
    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {"raw_body": body.decode("utf-8", errors="replace")}
    if isinstance(parsed, dict):
        return parsed
    return {"raw_payload": parsed}
