from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from fastapi import Request

from ..domain.research_run_payload import build_research_run_payload
from ..errors import DataAccessError
from ..repositories.research_run_repository import persist_research_run_record

logger = logging.getLogger(__name__)
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", request_id_var.get())


def get_request_run_id(request: Request) -> str | None:
    return getattr(request.state, "run_id", None)


def clear_request_run_id(request: Request) -> None:
    request.state.run_id = None


def ensure_request_run_id(request: Request) -> str:
    run_id = get_request_run_id(request)
    if run_id is not None:
        return run_id
    run_id = f"run_{uuid4().hex}"
    request.state.run_id = run_id
    return run_id


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


def persist_request_research_run(
    request: Request, payload: dict[str, Any], *, raise_on_failure: bool
) -> bool:
    request.state.research_run_persist_attempted = True
    try:
        persist_research_run_record(payload)
        request.state.research_run_persisted = True
        return True
    except DataAccessError:
        clear_request_run_id(request)
        if raise_on_failure:
            raise
        logger.exception(
            "Failed to persist research run request_id=%s run_id=%s",
            get_request_id(request),
            payload.get("run_id"),
        )
        return False


def build_request_research_run_payload(**kwargs: Any) -> dict[str, Any]:
    return build_research_run_payload(**kwargs)
