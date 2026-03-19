from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request

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


def mark_request_research_run_persist_attempted(request: Request) -> None:
    request.state.research_run_persist_attempted = True


def mark_request_research_run_persisted(request: Request) -> None:
    request.state.research_run_persisted = True


def request_research_run_persist_attempted(request: Request) -> bool:
    return getattr(request.state, "research_run_persist_attempted", False)
